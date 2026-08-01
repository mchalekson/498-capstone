"""
build_rigor_v5.py -- the v5 rigor index
Run date 2026-07-31 · input Capstone_Org_Data_extended_v4_full_2026-07-31.xlsx

v5 extends the v4 specification (docs/RIGOR_FORMULA_V4.pdf) along three axes:
  (a) decomposes v4's "CRDC coursework" grab-bag into three named components,
      so dual enrollment and IB each carry explicit, auditable weight;
  (b) adds the three client rigor factors v4 had no component for --
      STEM course-taking, college placement, faculty investment;
  (c) re-weights test participation down, from nominal 0.15 to 0.05, because the
      v4 variance decomposition measured its effective weight at 0.074.

Layer 0-4 architecture, proportional weight reallocation and Jenks tiering are
carried over from v4 unchanged so the two indices stay directly comparable.
"""
import os
import re
import warnings

import numpy as np
import pandas as pd
from scipy.stats import norm, spearmanr
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression

warnings.filterwarnings('ignore')

SRC = '/mnt/project'
NEW = '/mnt/user-data/uploads/Capstone_Org_Data_extended_v4_full_2026-07-31.xlsx'
OUT = 'out5'
os.makedirs(f'{OUT}/fig', exist_ok=True)
audit = {}
RS = 42


def num(s):
    return pd.to_numeric(s, errors='coerce')


def band_mid(s):
    """Org export stores several fields as text bands. Map to interval midpoints.
    Open-ended bands: '<= X' -> X/2, '> X' -> 1.05X. Verified against every
    distinct raw value present in the export (see docs, band-parse audit)."""
    t = (s.astype(str).str.strip()
         .str.replace('%', '', regex=False).str.replace(',', '', regex=False))
    out = pd.Series(np.nan, index=s.index, dtype=float)
    rng = t.str.extract(r'^(\d+)\s*[-–—]\s*(\d+)')
    ok = rng[0].notna()
    out[ok] = (num(rng[0][ok]) + num(rng[1][ok])) / 2
    for pat, f in [(r'^(?:over|more than|greater than)\s*(\d+)', 1.05),
                   (r'^(\d+)\s*(?:or fewer|or less)', 0.5),
                   (r'^(\d+)\s*(?:or more|\+)$', 1.05)]:
        e = t.str.extract(pat, flags=re.I)[0]
        sel = e.notna() & out.isna()
        out[sel] = num(e[sel]) * f
    solo = t.str.fullmatch(r'\d+(?:\.\d+)?') & out.isna()
    out[solo] = num(t[solo])
    return out


def z(s):
    s = num(s)
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0.0


def zw(s, p=0.99):
    """Winsorise at the p-th percentile then z-score (v4 Layer 0/1 convention)."""
    s = num(s)
    if s.notna().sum() < 30:
        return s * np.nan
    return z(s.clip(s.quantile(1 - p), s.quantile(p)))


# ===================================================== 1. LOAD + UNIVERSE
print('[1] load + universe')
d = pd.read_excel(NEW, 'Export', dtype=str)
audit['rows_in_export'] = len(d)

d['ceeb_len'] = d['CEEB'].fillna('').str.strip().str.len()
is_college = d.ceeb_len.eq(4) | d.Category.eq('College')
is_junk = d.ceeb_len.isin([7, 9])

# The CEEB-length rule and the org Category field each catch cases the other
# misses, so the exclusion is their union -- see the v5 spec, section 2.
audit['excl_ceeb4_only'] = int((d.ceeb_len.eq(4) & ~d.Category.eq('College')).sum())
audit['excl_category_only'] = int((d.Category.eq('College') & ~d.ceeb_len.eq(4)).sum())
audit['excl_both'] = int((d.ceeb_len.eq(4) & d.Category.eq('College')).sum())
audit['excl_nonHS_total'] = int(is_college.sum())
audit['excl_junk'] = int(is_junk.sum())

m = d[~is_college & ~is_junk].copy()
m['_orig_row'] = m.index
m = m.reset_index(drop=True)
audit['universe'] = len(m)
audit['dup_guid'] = int(m.GUID.dropna().duplicated().sum())
audit['dup_ceeb6'] = int(m.loc[m.ceeb_len == 6, 'CEEB'].duplicated().sum())

m['n12'] = m['nces_id_12digit'].astype(str).str.zfill(12)
m.loc[m['nces_id_12digit'].isna(), 'n12'] = np.nan
m['leaid7'] = num(m['leaid']).astype('Int64').astype(str).str.zfill(7)
m.loc[m['leaid'].isna(), 'leaid7'] = np.nan
audit['leaid_nunique'] = int(m.leaid7.nunique())


# ===================================================== 2. ENRICHMENT JOINS
print('[2] enrichment joins')
n0 = len(m)

stem = pd.read_csv(f'{SRC}/crdc_stem_clean.csv', dtype={'nces_id_12': str})
stem['n12'] = stem.nces_id_12.str.zfill(12)
stem = stem.drop_duplicates('n12')[['n12', 'calculus_offered', 'advmath_offered',
                                    'chemistry_offered', 'physics_offered']]
m = m.merge(stem, on='n12', how='left')

old = pd.read_csv(f'{SRC}/schools_org_all.csv', dtype={'nces_id_12': str}, low_memory=False)
old['n12'] = old.nces_id_12.astype(str).str.zfill(12)
fac = (old[old.nces_id_12.notna()]
       .drop_duplicates('n12')[['n12', 'crdc_pct_teachers_certified', 'crdc_ap_courses',
                                'crdc_fte_counselors', 'total_enrollment']])
m = m.merge(fac, on='n12', how='left')

fin = pd.read_excel(f'{SRC}/census_school_finances_FY2024_alldistricts.xlsx', 'elsec24',
                    usecols=['NCESID', 'V33', 'TCURINST'])
fin['leaid7'] = fin.NCESID.astype(str).str.strip().str.zfill(7)
fin['instr_spend_per_pupil'] = (fin.TCURINST * 1000) / fin.V33.replace(0, np.nan)
fin.loc[~fin.instr_spend_per_pupil.between(1000, 60000), 'instr_spend_per_pupil'] = np.nan
m = m.merge(fin.drop_duplicates('leaid7')[['leaid7', 'instr_spend_per_pupil']],
            on='leaid7', how='left')

assert len(m) == n0, f'join fan-out {n0} -> {len(m)}'
audit['joined_stem'] = int(m.calculus_offered.notna().sum())
audit['joined_faculty'] = int(m.crdc_pct_teachers_certified.notna().sum())
audit['joined_finance'] = int(m.instr_spend_per_pupil.notna().sum())


# ===================================================== 3. LAYER 0 -- derived inputs
print('[3] Layer 0 derived inputs')
m['ap_tests_taken'] = num(m['Avg # AP tests taken'])
m['ap_tests_offered'] = num(m['Avg # AP tests offered'])
m['ap_score'] = num(m['Avg AP score'])
m['ap_take_rate_x'] = num(m['ap_take_rate'])
m['ap_classes_band'] = band_mid(m['Number of AP Classes offered'])
m['ap_capstone'] = m['AP Capstone School'].eq('Yes').astype(float)
m.loc[m['AP Capstone School'].isna() & m.ap_tests_offered.isna(), 'ap_capstone'] = np.nan

# v4 Layer 0: AP qualifying density  QD = t * Phi((sbar - 2.5)/1.2)
qd_recomputed = m.ap_tests_taken * norm.cdf((m.ap_score - 2.5) / 1.2)
m['qd'] = num(m['ap_qualifying_density']).fillna(qd_recomputed)
audit['qd_from_file'] = int(num(m['ap_qualifying_density']).notna().sum())
audit['qd_recomputed'] = int((num(m['ap_qualifying_density']).isna() & qd_recomputed.notna()).sum())

# v4 Layer 0: IB intensity
m['ib_int'] = num(m['ib_intensity_v2'])

m['sat_score'] = num(m['Avg Freshman SAT']).fillna(num(m['Mean SAT']))
m['act'] = num(m['act_composite_il'])
m['sat_part'] = num(m['% seniors taking SAT'])
m['ttr'] = num(m['testtaker_rate'])
m['ap_part_crdc'] = num(m['ap_participation'])
m['de_rate'] = num(m['dual_enrollment_rate'])
m['pct_college'] = band_mid(m['Percent going to college'])
m['pct_4yr'] = band_mid(m['Percent going to 4yr college'])
m['stem_breadth'] = m[['calculus_offered', 'advmath_offered',
                       'chemistry_offered', 'physics_offered']].sum(axis=1, min_count=1)
m['pct_certified'] = num(m['crdc_pct_teachers_certified'])
m['e912'] = num(m['enrollment_9_12'])
m['poverty'] = num(m['child_poverty_saipe'])
m['frl'] = num(m['frl_rate']).fillna(num(m['Avg % FRL']))
m['grad'] = num(m['grad_rate_2021'])


# ===================================================== 4. LAYER 1/2 -- components
print('[4] Layer 1-2 components')
SUB = {
    'ap_opportunity':      ['z_ap_taken', 'z_ap_offered', 'z_ap_classes', 'z_ap_take', 'z_capstone'],
    'ap_performance':      ['z_qd'],
    'advanced_access':     ['z_ap_part', 'z_de'],
    'ib':                  ['z_ib'],
    'stem_depth':          ['z_stem'],
    'test_performance':    ['z_sat', 'z_act'],
    'test_participation':  ['z_ttr', 'z_satpart'],
    'college_placement':   ['z_college', 'z_4yr'],
    'faculty_investment':  ['z_cert', 'z_spend'],
}
W = {'ap_opportunity': 0.15, 'ap_performance': 0.20, 'advanced_access': 0.10, 'ib': 0.05,
     'stem_depth': 0.10, 'test_performance': 0.20, 'test_participation': 0.05,
     'college_placement': 0.10, 'faculty_investment': 0.05}
assert abs(sum(W.values()) - 1) < 1e-9

m['z_ap_taken'] = zw(m.ap_tests_taken)
m['z_ap_offered'] = zw(m.ap_tests_offered)
m['z_ap_classes'] = zw(m.ap_classes_band)
m['z_ap_take'] = zw(m.ap_take_rate_x)
m['z_capstone'] = z(m.ap_capstone)
m['z_qd'] = zw(m.qd)
m['z_ap_part'] = zw(m.ap_part_crdc)
m['z_de'] = zw(m.de_rate)
m['z_ib'] = zw(m.ib_int)
m['z_stem'] = z(m.stem_breadth)
m['z_sat'] = zw(m.sat_score)
m['z_act'] = zw(m.act)
m['z_ttr'] = zw(m.ttr)
m['z_satpart'] = zw(m.sat_part)
m['z_college'] = zw(m.pct_college)
m['z_4yr'] = zw(m.pct_4yr)
m['z_cert'] = zw(m.pct_certified)
m['z_spend'] = zw(m.instr_spend_per_pupil)

for k, cols in SUB.items():
    m[f'C_{k}'] = m[cols].mean(axis=1, skipna=True)


# ===================================================== 5. LAYER 3 -- composite
print('[5] Layer 3 composite')


def composite(frame, weights):
    num_ = pd.Series(0.0, index=frame.index)
    den = pd.Series(0.0, index=frame.index)
    cnt = pd.Series(0, index=frame.index)
    for k, w in weights.items():
        if w == 0:
            continue
        v = frame[f'C_{k}']
        ok = v.notna()
        num_[ok] += v[ok] * w
        den[ok] += w
        cnt[ok] += 1
    return pd.Series(np.where(den > 0, num_ / den.replace(0, np.nan), np.nan),
                     index=frame.index), cnt, den


m['rigor_score_v5_raw'], m['n_components'], m['weight_covered'] = composite(m, W)

# v5 addition -- minimum coverage floor.
# v4 had no floor, so a school reporting only the IB component (nominal weight
# 0.05) still received a tier, and every extreme score in the index came from
# such rows: single-component schools carry ~2x the score variance of the full
# population and produced all 10 scores beyond |3|. Requiring a quarter of the
# index weight removes that artefact. Schools below the floor are logged
# unscored -- never defaulted to a middle tier (v4 Layer 3 convention).
MIN_WEIGHT = 0.25
m['below_coverage_floor'] = m.rigor_score_v5_raw.notna() & (m.weight_covered < MIN_WEIGHT)
m['rigor_score_v5'] = m.rigor_score_v5_raw.where(~m.below_coverage_floor)
audit['min_weight_floor'] = MIN_WEIGHT
audit['dropped_by_floor'] = int(m.below_coverage_floor.sum())
audit['dropped_by_floor_private'] = int((m.below_coverage_floor & m.sector.eq('private')).sum())
audit['dropped_by_floor_public'] = int((m.below_coverage_floor & m.sector.eq('public')).sum())
audit['score_max_before_floor'] = round(float(m.rigor_score_v5_raw.max()), 2)
audit['score_max_after_floor'] = round(float(m.rigor_score_v5.max()), 2)

m['components_available'] = m[[f'C_{k}' for k in W]].notna().apply(
    lambda r: ','.join([k for k, v in zip(W, r) if v]), axis=1)
audit['scored'] = int(m.rigor_score_v5.notna().sum())
audit['unscored'] = int(m.rigor_score_v5.isna().sum())
audit['scored_public'] = int((m.rigor_score_v5.notna() & m.sector.eq('public')).sum())
audit['scored_private'] = int((m.rigor_score_v5.notna() & m.sector.eq('private')).sum())


# ===================================================== 6. LAYER 4 -- tiers
print('[6] Layer 4 tiers')
LAB = {1: 'Below Average', 2: 'Average', 3: 'Demanding', 4: 'Very Demanding', 5: 'Most Demanding'}


def jenks(x, k=5):
    v = num(x)
    ok = v.notna()
    out = pd.Series(np.nan, index=x.index)
    if ok.sum() < k:
        return out
    km = KMeans(n_clusters=k, n_init=10, random_state=RS).fit(v[ok].values.reshape(-1, 1))
    remap = {c: i + 1 for i, c in enumerate(np.argsort(km.cluster_centers_.ravel()))}
    out[ok] = [remap[c] for c in km.labels_]
    return out


m['rigor_tier_num_v5'] = jenks(m.rigor_score_v5)
m['rigor_tier_label_v5'] = m.rigor_tier_num_v5.map(LAB)
q = m.rigor_score_v5.rank(pct=True)
m['rigor_tier_num_v5_quantile'] = np.ceil(q * 5).clip(1, 5)
m['rigor_tier_label_v5_quantile'] = m.rigor_tier_num_v5_quantile.map(LAB)
agree = m[['rigor_tier_num_v5', 'rigor_tier_num_v5_quantile']].dropna()
audit['jenks_quantile_agreement_pct'] = round(float(
    (agree.rigor_tier_num_v5 == agree.rigor_tier_num_v5_quantile).mean() * 100), 1)

# within-sector track (the "public rigor / private rigor" question)
m['rigor_score_v5_sector'] = np.nan
m['rigor_tier_num_v5_sector'] = np.nan
for sec in ['public', 'private']:
    i = m.sector == sec
    m.loc[i, 'rigor_score_v5_sector'] = z(m.loc[i, 'rigor_score_v5'])
    m.loc[i, 'rigor_tier_num_v5_sector'] = jenks(m.loc[i, 'rigor_score_v5_sector'])
m['rigor_tier_label_v5_sector'] = m.rigor_tier_num_v5_sector.map(LAB)


# ===================================================== 7. DIAGNOSTICS
print('[7] diagnostics')

# 7a. nominal vs effective weight (variance decomposition, full-coverage subset)
full = m[[f'C_{k}' for k in W]].notna().all(axis=1)
audit['full_coverage_n'] = int(full.sum())
S = m.loc[full, [f'C_{k}' for k in W]]
cov = S.cov()
wv = np.array([W[k] for k in W])
var_total = float(wv @ cov.values @ wv)
eff = {k: float(W[k] * (cov.values[i] @ wv) / var_total) for i, k in enumerate(W)}
weights_tbl = pd.DataFrame({'component': list(W), 'nominal_weight': [W[k] for k in W],
                            'effective_weight': [round(eff[k], 3) for k in W]})

# 7b. sensitivity to alternate weighting schemes
SCHEMES = {
    'v4_equivalent': {'ap_opportunity': .25, 'ap_performance': .20, 'advanced_access': .133,
                      'ib': .067, 'stem_depth': 0, 'test_performance': .20,
                      'test_participation': .15, 'college_placement': 0, 'faculty_investment': 0},
    'equal': {k: 1 / len(W) for k in W},
    'performance_heavy': {'ap_opportunity': .05, 'ap_performance': .30, 'advanced_access': .05,
                          'ib': .05, 'stem_depth': .05, 'test_performance': .30,
                          'test_participation': 0, 'college_placement': .15, 'faculty_investment': .05},
    'no_new_factors': {'ap_opportunity': .20, 'ap_performance': .25, 'advanced_access': .15,
                       'ib': .075, 'stem_depth': 0, 'test_performance': .25,
                       'test_participation': .075, 'college_placement': 0, 'faculty_investment': 0},
}
sens = []
# v5 cut points, frozen, so alternate schemes can be tiered without refitting Jenks
_ok = m.rigor_score_v5.notna()
_cuts = [m.loc[_ok & (m.rigor_tier_num_v5 == i), 'rigor_score_v5'].max() for i in range(1, 5)]


def tier_frozen(sc):
    return pd.Series(np.digitize(sc, _cuts, right=True) + 1.0, index=sc.index).where(sc.notna())


for name, ws in SCHEMES.items():
    sc, _, wcov = composite(m, ws)
    sc = sc.where(wcov >= MIN_WEIGHT)
    tr_refit = jenks(sc)
    tr_froz = tier_frozen(sc)
    both = m.rigor_score_v5.notna() & sc.notna()
    b1 = m.rigor_tier_num_v5.notna() & tr_refit.notna()
    b2 = m.rigor_tier_num_v5.notna() & tr_froz.notna()
    sens.append({'scheme': name, 'vs': 'designed_v5', 'n_compared': int(both.sum()),
                 'spearman_rank_corr': round(float(spearmanr(sc[both], m.rigor_score_v5[both]).statistic), 3),
                 'pct_changed_tier_refit': round(float((tr_refit[b1] != m.rigor_tier_num_v5[b1]).mean() * 100), 1),
                 'pct_changed_tier_frozen_cuts': round(float((tr_froz[b2] != m.rigor_tier_num_v5[b2]).mean() * 100), 1)})
sens = pd.DataFrame(sens)

# 7c. CRDC-loss scenario
NOCRDC = {k: (0 if k in ('advanced_access', 'stem_depth', 'faculty_investment') else v)
          for k, v in W.items()}
sc_nc, _, wcov_nc = composite(m, NOCRDC)
sc_nc = sc_nc.where(wcov_nc >= MIN_WEIGHT)
tr_nc = jenks(sc_nc)
has_crdc = m[['C_advanced_access', 'C_stem_depth']].notna().any(axis=1)
cmpb = has_crdc & m.rigor_tier_num_v5.notna() & tr_nc.notna()
audit['crdc_loss_n'] = int(cmpb.sum())
audit['crdc_loss_spearman'] = round(float(spearmanr(sc_nc[cmpb], m.rigor_score_v5[cmpb]).statistic), 3)
audit['crdc_loss_pct_changed'] = round(float((tr_nc[cmpb] != m.rigor_tier_num_v5[cmpb]).mean() * 100), 1)

# 7d. v4 -> v5 migration (v4 tier ships in the export)
v4lab = m['rigor_tier_label'].where(m['rigor_tier_label'].notna())
both45 = v4lab.notna() & m.rigor_tier_label_v5.notna()
audit['v4_v5_n_compared'] = int(both45.sum())
audit['v4_v5_pct_changed'] = round(float((v4lab[both45] != m.rigor_tier_label_v5[both45]).mean() * 100), 1)
v4s = num(m['rigor_score'])
bs = v4s.notna() & m.rigor_score_v5.notna()
audit['v4_v5_spearman'] = round(float(spearmanr(v4s[bs], m.rigor_score_v5[bs]).statistic), 3)

# 7e. SES entanglement
def sp(a, b):
    s = m[[a, b]].dropna()
    return round(float(spearmanr(s[a], s[b]).statistic), 3) if len(s) > 100 else np.nan


audit['rho_v5_poverty'] = sp('rigor_score_v5', 'poverty')
audit['rho_v4_poverty'] = sp('rigor_score', 'poverty') if v4s.notna().any() else np.nan
m['_v4s'] = v4s
audit['rho_v4_poverty'] = sp('_v4s', 'poverty')
ent = pd.DataFrame([{'component': k, 'n': int(m[[f'C_{k}', 'poverty']].dropna().shape[0]),
                     'rho_vs_child_poverty': sp(f'C_{k}', 'poverty')} for k in W])

# 7f. component coverage by sector
cov_tbl = pd.DataFrame([{
    'component': k, 'nominal_weight': W[k],
    'public_pct': round(float(m.loc[m.sector == 'public', f'C_{k}'].notna().mean() * 100), 1),
    'private_pct': round(float(m.loc[m.sector == 'private', f'C_{k}'].notna().mean() * 100), 1),
    'overall_pct': round(float(m[f'C_{k}'].notna().mean() * 100), 1)} for k in W])


# ===================================================== 8. OPPORTUNITY-ADJUSTED
print('[8] opportunity-adjusted layer')
ctx = ['poverty', 'frl']
fitrows = m.rigor_score_v5.notna() & m[ctx].notna().any(axis=1)
X = m.loc[fitrows, ctx].copy()
for c in ctx:
    X[c] = X[c].fillna(m[c].median())
lr = LinearRegression().fit(X, m.loc[fitrows, 'rigor_score_v5'])
m['rigor_expected_ses'] = np.nan
m.loc[fitrows, 'rigor_expected_ses'] = lr.predict(X)
m['rigor_residual_v5'] = m.rigor_score_v5 - m.rigor_expected_ses
thr = m.rigor_residual_v5.quantile(0.90)
m['overperformer_v5'] = m.rigor_residual_v5 > thr
audit['opp_adj_n'] = int(fitrows.sum())
audit['opp_adj_r2'] = round(float(lr.score(X, m.loc[fitrows, 'rigor_score_v5'])), 3)
audit['rho_residual_poverty'] = sp('rigor_residual_v5', 'poverty')
hi = m.poverty > m.poverty.quantile(0.75)
audit['overperformers_total'] = int(m.overperformer_v5.sum())
audit['overperformers_high_need'] = int((m.overperformer_v5 & hi).sum())
audit['top_tier_high_need'] = int(((m.rigor_tier_num_v5 == 5) & hi).sum())


# ===================================================== 9. VALIDATION
print('[9] validation')
val = []
for i in range(1, 6):
    s = m[m.rigor_tier_num_v5 == i]
    def mn(c, r=1):
        return round(float(s[c].mean()), r) if s[c].notna().any() else np.nan
    val.append({'tier': LAB[i], 'n': len(s), 'grad_rate': mn('grad'), 'sat': mn('sat_score', 0),
                'ap_score': mn('ap_score', 2), 'pct_to_college': mn('pct_college'),
                'stem_breadth': mn('stem_breadth', 2), 'child_poverty': mn('poverty')})
validation = pd.DataFrame(val)


# ===================================================== 10. WRITE
print('[10] write')
m['rigor_weighting_scheme_v5'] = 'designed_v5'
m['rigor_tier_method_v5'] = 'jenks_natural_breaks_k5'
OUTCOLS = ['_orig_row', 'GUID', 'CEEB', 'Name', 'Region', 'City', 'sector', 'n12', 'leaid7'] + \
          [f'C_{k}' for k in W] + \
          ['rigor_score_v5', 'rigor_tier_num_v5', 'rigor_tier_label_v5',
           'rigor_tier_num_v5_quantile', 'rigor_tier_label_v5_quantile',
           'rigor_score_v5_sector', 'rigor_tier_num_v5_sector', 'rigor_tier_label_v5_sector',
           'rigor_expected_ses', 'rigor_residual_v5', 'overperformer_v5',
           'n_components', 'weight_covered', 'components_available',
           'rigor_weighting_scheme_v5', 'rigor_tier_method_v5',
           'rigor_score_v5_raw', 'below_coverage_floor', 'qd', 'ib_int', 'stem_breadth', 'pct_college', 'pct_certified',
           'instr_spend_per_pupil', 'sat_score', 'ap_score', 'grad', 'poverty']
m[OUTCOLS].to_csv(f'{OUT}/rigor_classification_v5_2026-07-31.csv', index=False)
validation.to_csv(f'{OUT}/rigor_v5_validation_2026-07-31.csv', index=False)
sens.to_csv(f'{OUT}/rigor_v5_sensitivity_2026-07-31.csv', index=False)
weights_tbl.to_csv(f'{OUT}/rigor_v5_weights_2026-07-31.csv', index=False)
cov_tbl.to_csv(f'{OUT}/rigor_v5_component_coverage_2026-07-31.csv', index=False)
ent.to_csv(f'{OUT}/rigor_v5_ses_entanglement_2026-07-31.csv', index=False)
pd.Series(audit).to_csv(f'{OUT}/rigor_v5_audit_2026-07-31.csv', header=['value'])
m.to_pickle('m5.pkl')

print('\n=== AUDIT ===')
for k, v in audit.items():
    print(f'  {k:30s} {v}')
print('\n=== WEIGHTS ===');       print(weights_tbl.to_string(index=False))
print('\n=== COVERAGE ===');      print(cov_tbl.to_string(index=False))
print('\n=== VALIDATION ===');    print(validation.to_string(index=False))
print('\n=== SENSITIVITY ===');   print(sens.to_string(index=False))
print('\n=== SES ENTANGLEMENT ==='); print(ent.to_string(index=False))
