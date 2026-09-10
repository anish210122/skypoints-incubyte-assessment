-- 1. Analytical Join: Active members across country tables joined with partner redemptions
WITH unified_members AS (
    SELECT member_id, member_name, country, tier_code, is_stale_member, age FROM table_usa
    UNION ALL
    SELECT member_id, member_name, country, tier_code, is_stale_member, age FROM table_ind
    UNION ALL
    SELECT member_id, member_name, country, tier_code, is_stale_member, age FROM table_aus
)
SELECT 
    m.member_id,
    m.member_name,
    m.country,
    m.tier_code,
    m.age,
    m.is_stale_member,
    r.txn_id,
    r.partner,
    r.miles_redeemed,
    r.status,
    r.txn_date
FROM unified_members m
INNER JOIN fct_member_redemptions r
    ON m.member_id = r.member_id;

-- 2. Data Validation Audit: Catch anomalies in staging
SELECT
    COUNT(*) AS total_records,
    SUM(CASE WHEN member_id IS NULL OR member_name IS NULL OR enrollment_date IS NULL THEN 1 ELSE 0 END) AS missing_mandatory_fields,
    SUM(CASE WHEN age < 0 OR age > 115 THEN 1 ELSE 0 END) AS invalid_age_values,
    SUM(CASE WHEN flight_date < enrollment_date THEN 1 ELSE 0 END) AS flight_before_enrollment
FROM stg_member_profiles;
