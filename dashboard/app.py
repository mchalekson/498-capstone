"""
Capstone rigor dashboard (Streamlit).

A live view over the frozen v4 modeling layer:
  - Overview          headline counts, tier mix, match rates, coverage
  - Rigor explorer    move the component weights and cut method, watch tiers move
  - Clustering        cluster sizes, PCA scatter, interpretable cluster profiles
  - Benchmarking      where a school sits within its peer group
  - Crosswalk         CEEB <-> NCES <-> NU match rates + OPE<->CEEB junction status
  - School lookup     one school's rigor, components, cluster, peers

It reads the newest v4 CSVs in ../csv_exports (so a re-dated rebuild is picked up
automatically) and imports the *real* scoring functions from etl/build_rigor_classification.py
so the explorer reproduces the pipeline exactly rather than reimplementing it.

Run:
    cd dashboard && streamlit run app.py
"""
import glob
import os
import sys

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
CSV = os.path.join(REPO, "csv_exports")
sys.path.insert(0, os.path.join(REPO, "etl"))

import build_rigor_classification as rc  # noqa: E402

TIERS = rc.TIER_LABELS
TIER_COLORS = {
    "Below Average": "#c9c4d6",
    "Average": "#b3a9e2",
    "Demanding": "#8878cd",
    "Very Demanding": "#5f4cb8",
    "Most Demanding": "#372a80",
}
COMPONENT_LABELS = {
    "ap_opportunity": "AP opportunity (offered / taken)",
    "ap_performance": "AP performance (qualifying density)",
    "ib": "IB (excluded by default — see caveat)",
    "crdc_coursework": "CRDC coursework (AP part. / dual enr. / IB)",
    "test_participation": "Test participation (SAT / testtaker)",
    "test_performance": "Test performance (SAT / ACT score)",
}

st.set_page_config(page_title="Capstone rigor dashboard", page_icon="🎓", layout="wide")


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
def _newest(stem, version=None):
    """Newest csv_exports file for <stem>, by filename sort.

    version pinned  -> <stem>_<version>_*.csv (keeps v4 pages off the v5 file, which
                       would otherwise sort newest and hijack them).
    version None    -> try <stem>_v*_*.csv, then <stem>_*.csv (date-only tags like the
                       v5 aux files), then an exact <stem>.csv.
    """
    # [0-9]* before the catch-all so a date-tagged file (college_clustering_2026-...)
    # isn't shadowed by a sibling sharing its prefix (college_clustering_coverage_...).
    patterns = ([f"{stem}_{version}_*.csv"] if version
                else [f"{stem}_v*_*.csv", f"{stem}_[0-9]*.csv", f"{stem}_*.csv"])
    for pat in patterns:
        dated = sorted(glob.glob(os.path.join(CSV, pat)))
        if dated:
            return dated[-1]
    exact = os.path.join(CSV, f"{stem}.csv")
    return exact if os.path.exists(exact) else None


@st.cache_data(show_spinner=False)
def load_csv(stem, version=None, **kw):
    path = _newest(stem, version)
    if not path:
        return None, None
    return pd.read_csv(path, low_memory=False, **kw), os.path.basename(path)


@st.cache_data(show_spinner=False)
def load_components(model_path):
    df = pd.read_csv(model_path, low_memory=False)
    comp = rc.build_components(df, rc.COMPONENTS)
    return df, comp


def fmt_int(n):
    return f"{int(n):,}"


# ─────────────────────────────────────────────────────────────────────────────
# Pages
# ─────────────────────────────────────────────────────────────────────────────
def page_overview(model, rigor, cover, files):
    st.header("Overview")
    st.caption(f"Frozen modeling layer · {files['rigor']}")

    n = len(rigor)
    scored = rigor["rigor_tier_label"].notna().sum()
    matched = int(model["is_school_match"].fillna(False).sum()) if "is_school_match" in model else np.nan
    nu = int(model["has_nu_analytics"].fillna(False).sum()) if "has_nu_analytics" in model else np.nan

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Schools in universe", fmt_int(n))
    c2.metric("Rigor-scored", fmt_int(scored), f"{100*scored/n:.0f}% of universe")
    c3.metric("Matched to NU org", fmt_int(matched) if matched == matched else "—")
    c4.metric("With NU analytics", fmt_int(nu) if nu == nu else "—")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("Rigor tier distribution")
        vc = rigor["rigor_tier_label"].value_counts().reindex(TIERS).fillna(0)
        fig = px.bar(x=vc.index, y=vc.values, color=vc.index,
                     color_discrete_map=TIER_COLORS, labels={"x": "", "y": "schools"})
        fig.update_layout(showlegend=False, height=360, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("By sector")
        if "sector" in rigor:
            sec = rigor.groupby("sector")["rigor_tier_label"].apply(lambda s: s.notna().sum())
            tot = rigor["sector"].value_counts()
            tbl = pd.DataFrame({"schools": tot, "scored": sec}).fillna(0).astype(int)
            tbl["scored %"] = (100 * tbl["scored"] / tbl["schools"]).round(0)
            st.dataframe(tbl, use_container_width=True)

    if cover is not None:
        st.subheader("Feature coverage, public vs private")
        st.caption("Coverage is NOT missing-at-random: CRDC is public-only by federal design; "
                   "NU analytics track NU's recruiting universe. Read low private coverage as a "
                   "structural gap, not random missingness.")
        st.dataframe(cover, use_container_width=True, height=300)


def page_rigor_explorer(model_path):
    st.header("Rigor formula explorer")
    st.caption("Move the component weights and the cut method; tiers recompute live using the "
               "pipeline's own scoring code. Baseline = the shipped 'designed' scheme.")

    df, comp = load_components(model_path)
    base = rc.WEIGHT_SCHEMES[rc.DEFAULT_SCHEME]

    with st.sidebar:
        st.subheader("Component weights")
        preset = st.selectbox("Start from scheme", list(rc.WEIGHT_SCHEMES), index=0)
        pre = rc.WEIGHT_SCHEMES[preset]
        if st.button("↺ reset to preset"):
            for k in COMPONENT_LABELS:
                st.session_state[f"w_{k}"] = float(pre[k])
        weights = {}
        for k, label in COMPONENT_LABELS.items():
            weights[k] = st.slider(label, 0.0, 0.5, float(st.session_state.get(f"w_{k}", pre[k])),
                                   0.05, key=f"w_{k}")
        method = st.radio("Tier cut method", ["natural", "quantile"], index=0,
                          help="natural = Jenks breaks (sizes vary); quantile = equal buckets")

    total = sum(weights.values())
    if total == 0:
        st.warning("All weights are zero — give at least one component weight.")
        return
    norm = {k: v / total for k, v in weights.items()}

    score, avail = rc.weighted_composite(comp, norm)
    tier_label, tier_num = rc.assign_tiers(score, method=method)
    base_score, _ = rc.weighted_composite(comp, base)
    base_tier, base_num = rc.assign_tiers(base_score, method=method)

    both = score.notna() & base_score.notna()
    rank_corr = score[both].corr(base_score[both], method="spearman") if both.sum() > 1 else np.nan
    both_t = tier_num.notna() & base_num.notna()
    changed = int((tier_num[both_t] != base_num[both_t]).sum())
    pct_changed = 100 * changed / both_t.sum() if both_t.sum() else np.nan

    c1, c2, c3 = st.columns(3)
    c1.metric("Scored schools", fmt_int(score.notna().sum()))
    c2.metric("Spearman vs designed", f"{rank_corr:.3f}" if rank_corr == rank_corr else "—")
    c3.metric("Changed tier vs designed", fmt_int(changed), f"{pct_changed:.1f}%")

    st.subheader("Tier distribution — your weights vs designed")
    cur = tier_label.value_counts().reindex(TIERS).fillna(0)
    bas = base_tier.value_counts().reindex(TIERS).fillna(0)
    fig = go.Figure()
    fig.add_bar(name="your weights", x=TIERS, y=cur.values, marker_color="#eb6834")
    fig.add_bar(name="designed", x=TIERS, y=bas.values, marker_color="#8878cd")
    fig.update_layout(barmode="group", height=360, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Nominal vs effective weight")
        st.caption("Effective weight = each component's share of composite variance, on the "
                   "full-coverage subset. Divergence means covariance is redistributing influence.")
        full_mask = avail[[k for k, w in norm.items() if w > 0]].all(axis=1)
        eff, tvar, n_full = rc.effective_weights(comp, norm, full_mask)
        rows = [{"component": COMPONENT_LABELS[k].split(" (")[0], "nominal": round(norm[k], 3),
                 "effective": round(eff.get(k, np.nan), 3)}
                for k, w in norm.items() if w > 0]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"full-coverage subset n = {n_full:,} · composite variance = {tvar:.3f}")
    with colB:
        st.subheader("Does it reproduce SES ordering?")
        st.caption("Spearman(tier, poverty/funding). Offerings-based indices tend to track SES — "
                   "reported explicitly, not hidden as enrichment.")
        pf = rc.poverty_funding_correlation(df, tier_num)
        st.dataframe(pd.DataFrame([{"overlay": k, "spearman(tier, ·)": v} for k, v in pf.items()]),
                     use_container_width=True, hide_index=True)

    st.info("This explorer is a *what-if* tool. The shipped tiers use the 'designed' scheme; "
            "changing sliders here does not rewrite any file.")


def page_clustering(clust, profiles, gap, files):
    st.header("Clustering")
    st.caption(f"{files['clustering']} · complete-case k-means over location + academic + "
               "funding + poverty features")

    clustered = clust["cluster_kmeans"].notna().sum()
    st.metric("Schools clustered (complete-case)", fmt_int(clustered),
              f"{100*clustered/len(clust):.0f}% of universe")

    left, right = st.columns([3, 2])
    with left:
        st.subheader("PCA projection (PC1 × PC2), colored by cluster")
        sub = clust.dropna(subset=["cluster_kmeans", "pca_component_1", "pca_component_2"]).copy()
        sub["cluster"] = sub["cluster_kmeans"].astype(int).astype(str)
        fig = px.scatter(sub, x="pca_component_1", y="pca_component_2", color="cluster",
                         hover_data=["school_name", "state", "rigor_tier_label"],
                         opacity=0.6, labels={"pca_component_1": "PC1", "pca_component_2": "PC2"})
        fig.update_layout(height=440, margin=dict(t=10, b=10))
        fig.update_traces(marker=dict(size=5))
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.subheader("Cluster sizes")
        vc = clust["cluster_kmeans"].dropna().astype(int).value_counts().sort_index()
        fig2 = px.bar(x=vc.index.astype(str), y=vc.values, labels={"x": "cluster", "y": "schools"})
        fig2.update_layout(height=220, margin=dict(t=10, b=10), showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
        if gap is not None:
            st.subheader("Gap statistic")
            fig3 = px.line(gap, x="k", y="gap", markers=True)
            fig3.update_layout(height=200, margin=dict(t=10, b=10))
            st.plotly_chart(fig3, use_container_width=True)

    if profiles is not None:
        st.subheader("Cluster profiles — what distinguishes each group")
        st.caption("Mean of key features per cluster (z-relative to the clustered population). "
                   "Read across a row to see a cluster's signature.")
        st.dataframe(profiles, use_container_width=True)


def page_benchmarking(bench, files):
    st.header("Benchmarking")
    st.caption(f"{files['benchmarking']} · a school's percentile within its peer group")

    pctl_cols = [c for c in bench.columns if c.startswith("sat_percentile_by_")]
    grp = st.selectbox("Peer group", pctl_cols,
                       format_func=lambda c: c.replace("sat_percentile_by_", "by ").replace("_", " "))
    sub = bench.dropna(subset=[grp])
    st.metric("Schools with a percentile in this grouping", fmt_int(len(sub)))
    fig = px.histogram(sub, x=grp, nbins=20, labels={grp: "SAT percentile within peer group"})
    fig.update_layout(height=340, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top of each rigor tier by peer-group percentile")
    show = ["school_name", "state", "sector", "rigor_tier_label", grp]
    st.dataframe(sub[show].sort_values(grp, ascending=False).head(50),
                 use_container_width=True, hide_index=True)


def page_crosswalk(xwalks, ope_status):
    st.header("Crosswalk & junctions")
    st.caption("The CEEB-anchored junction linking NU org data to federal school IDs.")

    rows = []
    for name, (df, fn) in xwalks.items():
        if df is None:
            continue
        acc = df["tier"].eq("auto_accept").sum() if "tier" in df else np.nan
        rows.append({"junction": name, "candidate rows": len(df),
                     "auto-accepted": int(acc) if acc == acc else "—",
                     "auto-accept %": round(100 * acc / len(df)) if acc == acc and len(df) else "—",
                     "source file": fn})
    st.subheader("NCES / IB / ISBE / CPS ↔ CEEB")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("OPE ↔ CEEB junction (postsecondary)")
    st.markdown(ope_status)


def page_lookup(model, clust, bench):
    st.header("School lookup")
    q = st.text_input("Search by school name, CEEB, or state", "")
    df = clust.copy()
    if q:
        ql = q.strip().lower()
        mask = (df["school_name"].astype(str).str.lower().str.contains(ql, na=False)
                | df["ceeb"].astype(str).str.lower().str.contains(ql, na=False)
                | df["state"].astype(str).str.lower().eq(ql))
        df = df[mask]
        st.caption(f"{len(df):,} match(es)")
    else:
        # No query: lead with rigor-scored schools (highest first) so the default view is
        # informative rather than a wall of unscored rows.
        df = df.sort_values("rigor_score", ascending=False, na_position="last")
        st.caption(f"{len(clust):,} schools · showing rigor-scored first — type to search all")
    show = ["ceeb", "school_name", "state", "sector", "rigor_tier_label", "rigor_score",
            "cluster_kmeans"]
    show = [c for c in show if c in df.columns]
    st.dataframe(df[show].head(200), use_container_width=True, hide_index=True)

    if len(df) and len(df) <= 200:
        names = df["school_name"].dropna().head(200).tolist()
        pick = st.selectbox("Inspect one school", ["—"] + names)
        if pick and pick != "—":
            row = df[df["school_name"] == pick].iloc[0]
            c1, c2, c3 = st.columns(3)
            c1.metric("Rigor tier", str(row.get("rigor_tier_label", "—")))
            c2.metric("Rigor score", f"{row.get('rigor_score', float('nan')):.2f}"
                      if pd.notna(row.get("rigor_score")) else "—")
            c3.metric("Cluster", str(int(row["cluster_kmeans"]))
                      if pd.notna(row.get("cluster_kmeans")) else "—")
            comps = ["ap_take_rate", "ap_qualifying_density", "dual_enrollment_rate",
                     "testtaker_rate", "sat_participation_nu", "sat_score_nu", "act_composite_il",
                     "frl_rate", "child_poverty_saipe", "per_pupil_state_local"]
            comps = [c for c in comps if c in row.index]
            st.dataframe(pd.DataFrame({"feature": comps, "value": [row[c] for c in comps]}),
                         use_container_width=True, hide_index=True)


def page_rigor_v5(v5, v5w, v5val, v5ses, audit, fn):
    st.header("Rigor v5 (candidate)")
    st.caption(f"{fn} · Qifan's v5 formula — see docs/RIGOR_FORMULA_V5.md. Nine components, "
               "coverage floor ω≥0.25, plus an opportunity-adjusted residual and a within-sector track.")

    def _num(key, default=0):
        try:
            return int(float(audit.get(key, default)))
        except (TypeError, ValueError):
            return default

    scored = int(v5["rigor_tier_label_v5"].notna().sum())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Universe", fmt_int(len(v5)))
    c2.metric("Scored", fmt_int(scored), f"{100*scored/len(v5):.0f}% (coverage floor)")
    if audit:
        c3.metric("v4→v5 change tier", f"{audit.get('v4_v5_pct_changed','—')}%",
                  f"ρ={audit.get('v4_v5_spearman','—')}")
        c4.metric("High-need overperformers", fmt_int(_num('overperformers_high_need')),
                  f"vs {_num('top_tier_high_need')} in raw top tier")

    track = st.radio("Tier track", ["Pooled", "Within-sector (public/private separately)"],
                     horizontal=True)
    col = "rigor_tier_label_v5" if track == "Pooled" else "rigor_tier_label_v5_sector"
    st.subheader(f"v5 tier distribution — {track.split(' (')[0].lower()}")
    st.caption("Pooled scores every school on one instrument (favours public schools with full CRDC "
               "coverage); within-sector re-standardizes inside public / private. Which to use is a "
               "client decision (spec §11), not a modeling one — both ship.")
    vc = v5[col].value_counts().reindex(TIERS).fillna(0)
    fig = px.bar(x=vc.index, y=vc.values, color=vc.index, color_discrete_map=TIER_COLORS,
                 labels={"x": "", "y": "schools"})
    fig.update_layout(showlegend=False, height=340, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Nominal vs effective weight")
        st.caption("AP performance is designed 0.20 but carries ~0.36 of index variance.")
        if v5w is not None:
            st.dataframe(v5w, use_container_width=True, hide_index=True, height=360)
    with right:
        st.subheader("SES entanglement (ρ vs child poverty)")
        st.caption("The cost of the shift toward exam performance — reported, not hidden.")
        if v5ses is not None:
            st.dataframe(v5ses, use_container_width=True, hide_index=True, height=360)

    st.subheader("Opportunity-adjusted: high-need overperformers")
    st.caption("Residual of the rigor score on poverty + FRL — schools outperforming their "
               "circumstances (`overperformer_v5`), even where the raw tier is modest.")
    op = v5[v5["overperformer_v5"].astype(str).isin(["True", "TRUE", "1", "1.0"])].copy()
    if "poverty" in op.columns and len(op):
        hi = op[op["poverty"] > op["poverty"].quantile(0.75)]
        show = [c for c in ["Name", "sector", "rigor_tier_label_v5", "rigor_residual_v5", "poverty"]
                if c in op.columns]
        st.dataframe(hi.sort_values("rigor_residual_v5", ascending=False)[show].head(40),
                     use_container_width=True, hide_index=True)

    st.subheader("Tier validation vs external measures")
    st.caption("Tier means. Grad rate / SAT / % to college are NOT model inputs; monotone across "
               "tiers = convergent validity.")
    if v5val is not None:
        st.dataframe(v5val, use_container_width=True, hide_index=True)


def page_college_clustering(cc, prof, cov, fn):
    st.header("College clustering")
    st.caption(f"{fn} · OPE↔CEEB junction → College Scorecard/IPEDS, enriched with IPEDS HD2023 "
               "(locale, lat/long, Carnegie). Groups colleges by location, academics, price, "
               "and student funding.")

    seg = st.radio("Segmentation", ["Fine segments (k=6)", "Natural split (k=2)"], horizontal=True)
    col = "cluster_fine" if seg.startswith("Fine") else "cluster"
    sub = cc.dropna(subset=[col, "latitude", "longitude"]).copy()
    sub["segment"] = sub[col].astype(int).astype(str)

    c1, c2 = st.columns(2)
    c1.metric("Colleges clustered", fmt_int(cc[col].notna().sum()))
    c2.metric("Segments", fmt_int(sub["segment"].nunique()))

    st.subheader("Where they are — colored by segment")
    fig = px.scatter_geo(sub, lat="latitude", lon="longitude", color="segment",
                         scope="usa", hover_name="org_name",
                         hover_data={"state": True, "sc_ugds": True, "latitude": False,
                                     "longitude": False, "segment": True})
    fig.update_traces(marker=dict(size=5, opacity=0.65))
    fig.update_layout(height=430, margin=dict(t=10, b=10, l=0, r=0), legend_title="segment")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Segment profiles — {seg.split(' (')[0].lower()}")
    st.caption("Median size/price, mean Pell + selectivity/outcome overlays. Admission rate, SAT and "
               "completion are overlays (thinly covered), NOT clustering inputs.")
    which = prof["fine"] if col == "cluster_fine" else prof["main"]
    if which is not None:
        st.dataframe(which, use_container_width=True, hide_index=True)

    if cov is not None:
        st.subheader("Feature coverage / gaps")
        st.caption("Share non-null over the degree-granting universe. `sc_act_mid` is dropped "
                   "(0% populated); selectivity is thin by design (open-admission & 2-yr schools "
                   "are exempt from the IPEDS admissions component).")
        st.dataframe(cov, use_container_width=True, hide_index=True, height=300)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.sidebar.title("🎓 Rigor dashboard")
    page = st.sidebar.radio("Page", ["Overview", "Rigor explorer (v4)", "Rigor v5", "Clustering",
                                     "College clustering", "Benchmarking", "Crosswalk & junctions",
                                     "School lookup"])

    model, model_fn = load_csv("modeling_dataset")
    rigor, rigor_fn = load_csv("rigor_classification", version="v4")  # pin: keep v5 off v4 pages
    clust, clust_fn = load_csv("clustering")
    bench, bench_fn = load_csv("benchmarking")
    cover, _ = load_csv("coverage_by_sector")
    gap, _ = load_csv("gap_statistic")
    profiles, _ = load_csv("cluster_profiles")

    if model is None or rigor is None:
        st.error(f"Could not find the v4 modeling CSVs in {CSV}. Run the modeling layer first.")
        return

    files = {"model": model_fn, "rigor": rigor_fn, "clustering": clust_fn, "benchmarking": bench_fn}
    model_path = _newest("modeling_dataset")

    xwalks = {
        "NCES public ↔ CEEB": load_csv("nces_public_ceeb_crosswalk"),
        "NCES private ↔ CEEB": load_csv("nces_private_ceeb_crosswalk"),
        "IB ↔ CEEB": load_csv("ib_ceeb_crosswalk"),
        "ISBE ↔ CEEB": load_csv("isbe_ceeb_crosswalk"),
        "CPS ↔ CEEB": load_csv("cps_ceeb_crosswalk"),
    }
    ope_df, ope_fn = load_csv("ope_ceeb_junction")
    if ope_df is not None:
        ope_status = (f"**{len(ope_df):,} OPE↔CEEB pairs** loaded from `{ope_fn}`. "
                      "Built by `etl/build_ope_ceeb_junction.py`.")
    else:
        ope_status = (
            "No OPE↔CEEB junction is loaded yet. OPE IDs identify **postsecondary** institutions "
            "(colleges) and are not present in the current school-level sources. The builder "
            "`etl/build_ope_ceeb_junction.py` is ready to materialize the junction once a college "
            "crosswalk with both an OPE ID and a CEEB code is supplied (e.g. the federal College "
            "Scorecard / IPEDS `OPEID` joined to a College Board CEEB college list). See "
            "`docs/OPE_CEEB_JUNCTION.md` for the sourcing plan.")

    if page == "Overview":
        page_overview(model, rigor, cover, files)
    elif page == "Rigor explorer (v4)":
        page_rigor_explorer(model_path)
    elif page == "Rigor v5":
        v5, v5_fn = load_csv("rigor_classification", version="v5")
        if v5 is None:
            st.warning("v5 outputs not found. Run `python etl/build_rigor_v5.py` to generate them.")
        else:
            v5w, _ = load_csv("rigor_v5_weights")
            v5val, _ = load_csv("rigor_v5_validation")
            v5ses, _ = load_csv("rigor_v5_ses_entanglement")
            audit_path = _newest("rigor_v5_audit")
            audit = (pd.read_csv(audit_path, index_col=0).iloc[:, 0].to_dict()
                     if audit_path else {})
            page_rigor_v5(v5, v5w, v5val, v5ses, audit, v5_fn)
    elif page == "Clustering":
        page_clustering(clust, profiles, gap, files)
    elif page == "College clustering":
        cc, cc_fn = load_csv("college_clustering")
        if cc is None:
            st.warning("College clustering outputs not found. Run "
                       "`python etl/build_college_clustering.py <merged_clean.csv>`.")
        else:
            pmain, _ = load_csv("college_cluster_profiles")
            pfine, _ = load_csv("college_cluster_profiles_fine")
            ccov, _ = load_csv("college_clustering_coverage")
            page_college_clustering(cc, {"main": pmain, "fine": pfine}, ccov, cc_fn)
    elif page == "Benchmarking":
        page_benchmarking(bench, files)
    elif page == "Crosswalk & junctions":
        page_crosswalk(xwalks, ope_status)
    elif page == "School lookup":
        page_lookup(model, clust, bench)


if __name__ == "__main__":
    main()
