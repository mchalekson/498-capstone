-- ============================================================
-- Analytical views — run after all ETL loaders have completed
-- ============================================================

-- 1. Illinois public schools enriched with ISBE report card data
--    Joins NCES school info to ISBE via state + school name
--    (RCDTS does not appear in NCES — name/city match is the best available key)
--    NOTE: this NCES export's ncessch is a 7-digit ID, not the standard
--    12-digit NCESSCH, so there's no reliable school-to-district crosswalk
--    in the data as provided. n.leaid (the first five characters of
--    ncessch) does NOT correspond to Census's 7-digit LEAID, so the
--    finance join below will not find matches (district_total_revenue and
--    district_federal_revenue will be NULL for now, pending a real
--    crosswalk). The SAIPE poverty figures are aggregated to state level
--    to avoid a many-to-many join blow-up.
CREATE OR REPLACE VIEW illinois_schools_enriched AS
SELECT
    n.ncessch,
    n.school_name_2024_25                                AS school_name,
    n.location_city_2024_25                              AS city,
    n.location_state_abbr_2024_25                        AS state,
    n.location_zip_2024_25                               AS zip,
    n.school_level_2024_25                               AS school_level,
    n.total_students_all_grades_2024_25                  AS total_students,
    n.free_and_reduced_lunch_students_2024_25            AS frl_students,
    n.pupil_teacher_ratio_2024_25                        AS pupil_teacher_ratio,
    i.rcdts,
    i.summative_designation,
    i.title_i_status,
    i.count_student_enrollment                           AS isbe_enrollment,
    f.total_revenue_000s                                 AS district_total_revenue,
    f.federal_revenue_000s                               AS district_federal_revenue,
    p.state_child_poverty_est,
    p.state_child_pop
FROM nces_public_schools_clean n
LEFT JOIN isbe_general i
       ON LOWER(TRIM(n.school_name_2024_25)) = LOWER(TRIM(i.school_name))
      AND LOWER(TRIM(n.location_city_2024_25)) = LOWER(TRIM(i.city))
LEFT JOIN census_school_finances_clean f ON n.leaid = f.leaid
LEFT JOIN (
    SELECT fips_state,
           SUM(child_poverty_estimate) AS state_child_poverty_est,
           SUM(child_population_5_17)  AS state_child_pop
    FROM census_saipe_poverty_clean
    GROUP BY fips_state
) p ON n.ansi_fips_state_code_latest_available_year = p.fips_state
WHERE TRIM(n.location_state_abbr_2024_25) = 'IL';


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
    n.school_name_2024_25 AS nces_name,
    n.location_city_2024_25 AS city,
    n.location_state_abbr_2024_25 AS state
FROM ib_schools i
LEFT JOIN nces_public_schools_clean n
       ON LOWER(TRIM(i.name)) = LOWER(TRIM(n.school_name_2024_25));
