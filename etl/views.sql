-- ============================================================
-- Analytical views — run after all ETL loaders have completed
-- ============================================================

-- 1. Illinois public schools enriched with ISBE report card data
--    Joins NCES school info to ISBE via state + school name
--    (RCDTS does not appear in NCES; name/city match is the best available key)
CREATE OR REPLACE VIEW illinois_schools_enriched AS
SELECT
    n.ncessch,
    n.school_name_public_school_2024_25                  AS school_name,
    n.location_city_public_school_2024_25                AS city,
    n.location_state_abbr_public_school_latest_available_year AS state,
    n.location_zip_public_school_2024_25                 AS zip,
    n.school_level_sy_2017_18_onward_public_school_2024_25 AS school_level,
    n.total_students_all_grades_excludes_ae_public_school_2024_25 AS total_students,
    n.free_and_reduced_lunch_students_public_school_2024_25 AS frl_students,
    n.pupil_teacher_ratio_public_school_2024_25          AS pupil_teacher_ratio,
    i.rcdts,
    i.summative_designation,
    i.title_i_status,
    i.student_enrollment                                 AS isbe_enrollment,
    f.totalrev                                           AS district_total_revenue,
    f.tfedrev                                            AS district_federal_revenue,
    p.saepov5_17rv_24                                    AS district_child_poverty_est,
    p.rpop5_17v_24                                       AS district_child_pop
FROM nces_public_schools n
LEFT JOIN isbe_general i
       ON LOWER(TRIM(n.school_name_public_school_2024_25)) = LOWER(TRIM(i.school_name))
      AND LOWER(TRIM(n.location_city_public_school_2024_25)) = LOWER(TRIM(i.city))
LEFT JOIN census_school_finances f ON n.leaid = f.leaid
LEFT JOIN census_saipe_poverty p
       ON n.ansi_fips_state_code_public_school_latest_available_year = p.state
WHERE n.location_state_abbr_public_school_latest_available_year = 'IL';


-- 2. District-level summary (national)
--    Combines Census finances and SAIPE poverty
CREATE OR REPLACE VIEW districts_enriched AS
SELECT
    f.leaid,
    f.name                  AS district_name,
    f.fipst                 AS fips_state,
    f.totalrev              AS total_revenue,
    f.tfedrev               AS federal_revenue,
    f.totalrev - f.tfedrev  AS state_local_revenue,
    p.stabrev               AS state_abbr,
    p.name                  AS saipe_district_name,
    p.rpopall_24            AS total_pop,
    p.saepov5_17rv_24       AS child_poverty_est,
    p.rpop5_17v_24          AS child_pop,
    ROUND(
        p.saepov5_17rv_24::numeric / NULLIF(p.rpop5_17v_24, 0) * 100, 2
    )                       AS pct_child_poverty
FROM census_school_finances f
LEFT JOIN census_saipe_poverty p
       ON f.fipst = p.state
      AND CAST(f.leaid AS TEXT) LIKE (CAST(p.state AS TEXT) || CAST(p.distid AS TEXT) || '%');


-- 3. National IB school presence (joined to NCES by name + state for reference)
--    Note: IB has no NCESSCH — this is a best-effort name match
CREATE OR REPLACE VIEW ib_nces_crosswalk AS
SELECT
    i.school_id     AS ibo_school_id,
    i.name          AS ib_name,
    i.offers_dp,
    i.offers_cp,
    i.offers_myp,
    i.offers_pyp,
    i.programmes,
    n.ncessch,
    n.school_name_public_school_2024_25 AS nces_name,
    n.location_city_public_school_2024_25 AS city,
    n.location_state_abbr_public_school_latest_available_year AS state
FROM ib_schools i
LEFT JOIN nces_public_schools n
       ON LOWER(TRIM(i.name)) = LOWER(TRIM(n.school_name_public_school_2024_25));
