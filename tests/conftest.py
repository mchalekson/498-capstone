"""Shared pytest fixtures. etl/ isn't a package (no __init__.py, imported as flat scripts
throughout this project), so it's added to sys.path here rather than restructured -- keeps
the test suite additive to the existing pipeline instead of requiring a refactor."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

ETL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "etl")
sys.path.insert(0, ETL_DIR)


@pytest.fixture
def tiny_schools_org_all():
    """
    A small, hand-built stand-in for schools_org_all.csv covering the cases that matter:
    a public HS with full signal, a private HS with only a school-side pss_id record (no
    nu_type) -- the exact case the is_private_hs bug used to miss, an IB candidate at
    'review' tier and one at 'reject' tier -- the exact case the old ib_flag bug conflated,
    and an org-only row with no school-side match at all.
    """
    rows = [
        {  # public HS, full signal
            "ceeb": "100001", "nu_ceeb": "100001", "school_id": "S1", "school_name": "Public HS A",
            "state": "IL", "school_level": "High", "pss_id": np.nan, "nu_type": "Public",
            "nu_guid": "G1", "nces_id_12": "170001000001",
            "enrollment_9_12": 500, "crdc_ap_offered": 1, "crdc_ap_enrollment": 100,
            "crdc_satact_takers": 200, "crdc_dual_enr_offered": 1, "crdc_dual_enrollment": 50,
            "nu_avg_num_ap_tests_taken": 2.5, "nu_avg_freshman_sat": 1200,
            "nu_pct_seniors_taking_sat": 80, "nu_median_family_income": 60,
            "nu_crime_risk": 40, "nu_educational_attainment": 55, "nu_family_stability": 50,
            "nu_housing_stability": 45, "grad_rate_2021": 90, "frl_students": 50,
            "total_enrollment": 500, "county_pct_child_poverty_saipe": 12,
            "total_per_pupil_expenditures_state_local": np.nan,
            "ib_school_id": np.nan, "ib_match_tier": np.nan, "nu_setting": "Suburban",
            "locale": "Suburban", "nu_name": "Public HS A", "nu_ap_capstone_school": "No",
            "grade_9": 130, "grade_10": 125, "grade_11": 122, "grade_12": 123,
        },
        {  # private HS: school-side pss_id record, NO nu_type -- the sector bug's exact case
            "ceeb": "100002", "nu_ceeb": "100002", "school_id": "S2", "school_name": "Private HS B",
            "state": "CA", "school_level": np.nan, "pss_id": "P1", "nu_type": np.nan,
            "nu_guid": "G2", "nces_id_12": np.nan,
            "enrollment_9_12": 200, "crdc_ap_offered": np.nan, "crdc_ap_enrollment": np.nan,
            "crdc_satact_takers": np.nan, "crdc_dual_enr_offered": np.nan, "crdc_dual_enrollment": np.nan,
            "nu_avg_num_ap_tests_taken": 1.0, "nu_avg_freshman_sat": 1100,
            "nu_pct_seniors_taking_sat": 70, "nu_median_family_income": 70,
            "nu_crime_risk": 30, "nu_educational_attainment": 65, "nu_family_stability": 60,
            "nu_housing_stability": 55, "grad_rate_2021": np.nan, "frl_students": np.nan,
            "total_enrollment": np.nan, "county_pct_child_poverty_saipe": 8,
            "total_per_pupil_expenditures_state_local": np.nan,
            "ib_school_id": "IB1", "ib_match_tier": "review", "nu_setting": "Urban",
            "locale": np.nan, "nu_name": "Private HS B", "nu_ap_capstone_school": "Yes",
            "grade_9": 50, "grade_10": 50, "grade_11": 50, "grade_12": 50,
        },
        {  # another private HS -- IB match at 'reject' tier (must NOT count as a candidate)
            "ceeb": "100003", "nu_ceeb": "100003", "school_id": "S3", "school_name": "Private HS C",
            "state": "TX", "school_level": np.nan, "pss_id": "P2", "nu_type": "Private Secular",
            "nu_guid": "G3", "nces_id_12": np.nan,
            "enrollment_9_12": 150, "crdc_ap_offered": np.nan, "crdc_ap_enrollment": np.nan,
            "crdc_satact_takers": np.nan, "crdc_dual_enr_offered": np.nan, "crdc_dual_enrollment": np.nan,
            "nu_avg_num_ap_tests_taken": np.nan, "nu_avg_freshman_sat": np.nan,
            "nu_pct_seniors_taking_sat": np.nan, "nu_median_family_income": 50,
            "nu_crime_risk": 50, "nu_educational_attainment": 50, "nu_family_stability": 50,
            "nu_housing_stability": 50, "grad_rate_2021": np.nan, "frl_students": np.nan,
            "total_enrollment": np.nan, "county_pct_child_poverty_saipe": np.nan,
            "total_per_pupil_expenditures_state_local": np.nan,
            "ib_school_id": "IB2", "ib_match_tier": "reject", "nu_setting": "Rural",
            "locale": np.nan, "nu_name": "Private HS C", "nu_ap_capstone_school": "No",
            "grade_9": np.nan, "grade_10": np.nan, "grade_11": np.nan, "grade_12": np.nan,
        },
        {  # org-only row (no school-side match at all)
            "ceeb": "100004", "nu_ceeb": "100004", "school_id": np.nan, "school_name": np.nan,
            "state": np.nan, "school_level": np.nan, "pss_id": np.nan, "nu_type": "College",
            "nu_guid": "G4", "nces_id_12": np.nan,
            "enrollment_9_12": np.nan, "crdc_ap_offered": np.nan, "crdc_ap_enrollment": np.nan,
            "crdc_satact_takers": np.nan, "crdc_dual_enr_offered": np.nan, "crdc_dual_enrollment": np.nan,
            "nu_avg_num_ap_tests_taken": np.nan, "nu_avg_freshman_sat": np.nan,
            "nu_pct_seniors_taking_sat": np.nan, "nu_median_family_income": np.nan,
            "nu_crime_risk": np.nan, "nu_educational_attainment": np.nan, "nu_family_stability": np.nan,
            "nu_housing_stability": np.nan, "grad_rate_2021": np.nan, "frl_students": np.nan,
            "total_enrollment": np.nan, "county_pct_child_poverty_saipe": np.nan,
            "total_per_pupil_expenditures_state_local": np.nan,
            "ib_school_id": np.nan, "ib_match_tier": np.nan, "nu_setting": np.nan,
            "locale": np.nan, "nu_name": "Some College", "nu_ap_capstone_school": np.nan,
            "grade_9": np.nan, "grade_10": np.nan, "grade_11": np.nan, "grade_12": np.nan,
        },
    ]
    df = pd.DataFrame(rows)
    for c in ["nu_percent_going_to_college", "nu_percent_going_to_4yr_college",
              "nu_percent_federal_lunch_aid", "nu_percent_first_gen_college",
              "nu_number_of_ap_classes_offered", "nu_size_of_senior_class",
              "county_median_hh_income", "nu_avg_num_ap_tests_offered",
              "nu_avg_ap_score", "nu_pct_students_taking_ap",
              "nu_latitude", "nu_longitude", "nu_us_region"]:
        df[c] = np.nan
    # Give the two NU-covered rows real AP-performance / offered values so the Wk5 features
    # (ap_score_nu, ap_take_rate) are actually exercised, not just present-and-null.
    new_ap = ["nu_avg_num_ap_tests_offered", "nu_avg_ap_score", "nu_pct_students_taking_ap"]
    df.loc[0, new_ap] = [15.0, 3.5, 45.0]   # public HS A: take_rate = 2.5/15
    df.loc[1, new_ap] = [10.0, 2.8, 30.0]   # private HS B: take_rate = 1.0/10
    return df
