"""
build_decks.py -- assembles the two Week-6 decks (.pptx) from docs/fig/ figures + v4 results.

Styled to match the user's own deck aesthetic: minimal (plain black title top-left, no color
bars/kickers), figure-forward, dash bullets in a "Term: explanation" format with inline
citations. Re-runnable: regenerate figures, re-run this.

  1. docs/Bob_Week6_Update.pptx   -- client update for Bob/Adam (tied to their Wk5 asks)
  2. docs/MSDS_498_Midterm.pptx   -- Week-6 midterm presentation (methods/rigor)

Run: python etl/build_decks.py
"""
import os

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

try:
    from PIL import Image
    def _img_wh(p):
        with Image.open(p) as im:
            return im.size
except Exception:
    def _img_wh(p):
        return (1600, 900)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(ROOT, "docs", "fig")

BLACK = RGBColor(0x1A, 0x1A, 0x1A)
GREY = RGBColor(0x55, 0x55, 0x55)
FONT = "Arial"
SW, SH = Inches(13.333), Inches(7.5)


def _fit(path, max_w, max_h):
    w, h = _img_wh(path)
    ar = w / h
    if ar >= max_w / max_h:
        return max_w, max_w / ar
    return max_h * ar, max_h


def _set(run, size, color=BLACK, bold=False):
    run.font.size = Pt(size); run.font.color.rgb = color
    run.font.bold = bold; run.font.name = FONT


def title_slide(prs, title, subtitle, foot):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.7), Inches(2.6), Inches(12), Inches(2.2))
    tf = tb.text_frame; tf.word_wrap = True
    r = tf.paragraphs[0].add_run(); r.text = title; _set(r, 38, BLACK, True)
    p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = subtitle; _set(r2, 19, GREY)
    fb = s.shapes.add_textbox(Inches(0.7), Inches(6.7), Inches(12), Inches(0.5))
    fr = fb.text_frame.paragraphs[0].add_run(); fr.text = foot; _set(fr, 12, GREY)
    return s


def _bullets(frame, bullets):
    for i, b in enumerate(bullets):
        p = frame.paragraphs[0] if i == 0 else frame.add_paragraph()
        sub = b.startswith("- ")
        if sub:
            b = b[2:]
        r = p.add_run()
        r.text = ("     ·  " if sub else "-  ") + b
        _set(r, 13 if sub else 15.5, GREY if sub else BLACK)
        p.space_after = Pt(9 if not sub else 5)
        p.line_spacing = 1.05


def content_slide(prs, title, bullets, image=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    tb = s.shapes.add_textbox(Inches(0.55), Inches(0.3), Inches(12.2), Inches(1.0))
    tr = tb.text_frame.paragraphs[0].add_run(); tr.text = title; _set(tr, 30, BLACK, True)
    tb.text_frame.word_wrap = True

    has_img = image and os.path.exists(os.path.join(FIG, image))
    if has_img:
        # figure large on the left, a few key-point bullets on the right
        path = os.path.join(FIG, image)
        w, h = _fit(path, 8.0, 5.4)
        top = Inches(1.55) + Inches((5.4 - h) / 2)
        s.shapes.add_picture(path, Inches(0.45), top, width=Inches(w), height=Inches(h))
        bx = s.shapes.add_textbox(Inches(8.7), Inches(1.6), Inches(4.35), Inches(5.4))
    else:
        bx = s.shapes.add_textbox(Inches(0.7), Inches(1.7), Inches(12), Inches(5.3))
    bx.text_frame.word_wrap = True
    _bullets(bx.text_frame, bullets)
    return s


def new_deck():
    prs = Presentation(); prs.slide_width = SW; prs.slide_height = SH
    return prs


# ===================================================================== BOB DECK
def build_bob():
    prs = new_deck()
    title_slide(prs,
        "High School Rigor Methodology",
        "Week-6 Client Update  ·  for Bob & Adam, NU Admissions",
        "MSDS 498 Capstone  ·  July 2026")

    content_slide(prs, "Where we are", [
        "Goal: a transparent, institution-level measure of high-school academic rigor, from public data, that NU can tie to its own internal data.",
        "Built from your Week-5 asks: AP exam scores, the low-offering/high-scores idea, coverage transparency, STEM, graduation rate.",
        "Validated: the tiers predict real outcomes, and are not just a proxy for socioeconomic status.",
    ])

    content_slide(prs, "How we measure rigor — an index, not a black box", [
        "Composite index: a weighted average of five standardized components → one rigor score.",
        "Decomposable: every tier traces back to the features that produced it (the Landscape lesson).",
        "Performance-weighted: AP exam scores, not just what's offered (Geiser & Santelices, 2004).",
        "Tiers: natural breaks, so sizes vary — 'Most Demanding' = 295 schools, not a forced 20%.",
    ], image="index_schematic.png")

    content_slide(prs, "Your idea: low AP offering / high AP scores", [
        "Selective & effective: few APs offered, high exam scores — 1,597 schools.",
        "The catch: only 3 reach the top tier; a thin catalog drags the composite down.",
        "So: these 'do a lot with little' schools are hidden by the tier alone.",
        "Use: a recruiting signal — ships alongside the tier, not folded in.",
    ], image="ap_efficiency.png")

    content_slide(prs, "Data coverage — public vs private", [
        "Not missing-at-random: reported per sector.",
        "CRDC: AP participation, testtaker rate, grad rate — public-only by law → ~0% private.",
        "NU analytics: AP/SAT scores track your recruiting universe (~35%).",
        "Consequence: private-school tiers rest on the thin NU block + IB — a documented blind spot.",
    ], image="coverage_by_sector.png")

    content_slide(prs, "Does the tier mean something? Yes.", [
        "Checked against measures the tier was NOT built from:",
        "- SAT rises across tiers: 1052 → 1303, no inversions.",
        "- Grad rate separates the bottom tier sharply (~70% vs ~86–90%).",
        "Honest note: the top tier reflects exam performance, not catalog size — so grad rate/STEM plateau at the top rather than peaking.",
    ], image="rigor_validation.png")

    content_slide(prs, "It predicts outcomes — and isn't just an SES proxy", [
        "Model: graduation rate ~ opportunity features (Adelman, 1999).",
        "Result: opportunity adds +5 pts R² beyond socioeconomic status — stable across models.",
        "Tension: the outcome IS SES-driven (free-lunch rate dominates)…",
        "…yet the index correlates with poverty at only −0.11 → opportunity, not laundered demographics.",
    ], image="predictive_validation.png")

    content_slide(prs, "What we'd need from you, and how it ties in", [
        "Data ask: per-course AP score distributions (Calc BC vs Calc BC across schools) — lets us verify rigor at the course level.",
        "Level: our tier is institution-level; your counselor 'most demanding coursework' field is per-student — they complement each other.",
        "Handoff: the methodology is built to recalibrate against your internal outcomes (enrollment, GPA, retention).",
    ])

    content_slide(prs, "Next steps & discussion", [
        "Finalize the v4 index (qualifying density + verified IB).",
        "Tier public and private separately — they aren't built from the same data.",
        "Validate on a second outcome (college-going).",
        "Your input: tier definitions, the per-course data ask, priority use-case (contextualization vs. outreach).",
    ])
    out = os.path.join(ROOT, "docs", "Bob_Week6_Update.pptx")
    prs.save(out); return out


# ================================================================= MIDTERM DECK
def build_midterm():
    prs = new_deck()
    title_slide(prs,
        "An AI-Driven High School Rigor Classification",
        "MSDS 498 Capstone — Midterm  ·  Week 6",
        "Capstone Team  ·  July 2026   (add team member names)")

    content_slide(prs, "Problem & objective", [
        "College Board discontinued Landscape (Sept 2025) — admissions lost standardized high-school context.",
        "~25% of applicants arrive with no school-context profile (Bastedo et al., 2023).",
        "Objective: a transparent, reproducible, defensible methodology to classify high-school rigor…",
        "…built from public data, that NU can adopt and tie to its internal data.",
    ])

    content_slide(prs, "Data & reproducible pipeline", [
        "Sources: NCES, CRDC 2021-22, Census F-33/SAIPE, NU export, IB, ISBE.",
        "Pipeline: Dockerized ETL, re-runnable without engineering support (Boettiger, 2015).",
        "Scale: ~34,000 high schools.",
        "Governance: per-variable data dictionary + source/vintage tracking (client requirement).",
    ], image="pipeline.png")

    content_slide(prs, "Record linkage without a shared identifier", [
        "Problem: CEEB and NCES have no common key.",
        "Decision rule: auto-accept / review / reject = Fellegi–Sunter three-way (1969).",
        "Similarity: token-based over edit distance for school names (Cohen et al., 2003).",
        "Reporting: match rates reported as a matter of course.",
    ], image="match_rates.png")

    content_slide(prs, "Feature engineering → the rigor index", [
        "Form: a weighted composite index — transparent and decomposable, not a black box.",
        "Principle: performance over availability (Geiser & Santelices, 2004).",
        "Structure: five components, per-row proportional weighting over available components.",
        "v4: adds AP qualifying density + verified IB intensity.",
    ], image="index_schematic.png")

    content_slide(prs, "Nominal vs. effective weights", [
        "Issue: assigned weights ≠ actual influence when features correlate (CADRE, 2024).",
        "Finding: AP performance leads the effective weight (~0.31); participation is absorbed.",
        "Practice: both reported, plus a sensitivity analysis across weighting schemes.",
    ], image="weights.png")

    content_slide(prs, "From score to tiers — natural breaks", [
        "Method: Jenks natural breaks (Jenks, 1967; Fisher, 1958) — cuts at gaps in the distribution.",
        "Why not quantiles: Reardon cautions against splitting near-identical schools.",
        "Frame: norm-referenced (Glaser, 1963); criterion-referenced is the alternative (Cizek & Bunch, 2007).",
        "Result: 'Most Demanding' = 295 schools, not a forced top fifth.",
    ], image="tier_cutpoints.png")

    content_slide(prs, "Validation against independent outcomes", [
        "SAT: rises across tiers (1052 → 1303), no inversions — and not a model input.",
        "Grad rate: sharply separates the bottom tier.",
        "Honest finding: grad rate/STEM plateau at the top — 'most demanding' = performance, not catalog size.",
    ], image="rigor_validation.png")

    content_slide(prs, "Predictive validation — the supervised model", [
        "Design: gradient boosting + linear; grad rate ~ opportunity, SES-controlled (Adelman; Reardon).",
        "Result: opportunity adds +0.05 R² beyond SES — stable across two specs, both model families.",
        "Importance: free-lunch rate dominates (0.53) — the outcome is SES-driven…",
        "…yet the index correlates with poverty only −0.11 → evidence it is not an SES proxy.",
    ], image="predictive_validation.png")

    content_slide(prs, "A three-layer modeling system", [
        "Measurement model: the composite rigor index (the deliverable).",
        "Unsupervised ML: K-means + hierarchical clustering with PCA (school segments).",
        "Supervised ML: gradient boosting predicting outcomes (validation).",
        "Rationale: no ground-truth rigor label exists — so an auditable index, validated by ML.",
    ])

    content_slide(prs, "Limitations (documented, not hidden)", [
        "Ecological inference: we measure the school, not the student.",
        "Levels, not growth: Reardon's caution — we report the SES-confounding check.",
        "Coverage: performance data ~35%, skewed to the recruiting universe.",
        "Gaps: private-school blind spot (CRDC public-only); per-course AP scores unavailable.",
        "Framing: most map onto NU's internal-data handoff — extension points, not dead ends.",
    ])

    content_slide(prs, "Grounded in literature", [
        "Adelman (1999, 2006): curriculum intensity predicts degree completion.",
        "Geiser & Santelices (2004): exam performance predicts; availability does not.",
        "Reardon / SEDA: levels reproduce SES — check for confounding.",
        "Landscape / ECD: keep the indicators transparent.",
        "Jenks/Fisher, Glaser, Cizek & Bunch, Nardo et al.: the tiering methodology.",
    ])

    content_slide(prs, "Next steps (Weeks 6 → 10)", [
        "Finalize v4 and commit its generation code (reproducibility).",
        "Separate public/private tiering; second-outcome validation (college-going).",
        "Methodology handoff guide for NU integration.",
        "Final report: Methods, results, limitations.",
    ])
    out = os.path.join(ROOT, "docs", "MSDS_498_Midterm.pptx")
    prs.save(out); return out


if __name__ == "__main__":
    for path in (build_bob(), build_midterm()):
        n = len(Presentation(path).slides._sldIdLst)
        print(f"wrote {path}  ({n} slides)")
