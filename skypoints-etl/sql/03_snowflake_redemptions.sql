-- Raw JSON is retained in VARIANT for replay/audit, then flattened with
-- LATERAL FLATTEN. MERGE on TXN_ID makes repeated processing idempotent.

MERGE INTO FCT_MEMBER_REDEMPTIONS t
USING (
    SELECT
        r.value:txn_id::VARCHAR AS TXN_ID,
        j.PAYLOAD:member_id::VARCHAR AS MEMBER_ID,
        TRY_TO_DATE(j.PAYLOAD:feed_date::VARCHAR, 'YYYYMMDD') AS FEED_DATE,
        TRY_TO_DATE(r.value:txn_date::VARCHAR, 'YYYYMMDD') AS TXN_DATE,
        r.value:partner::VARCHAR AS PARTNER,
        r.value:miles_redeemed::NUMBER AS MILES_REDEEMED,
        UPPER(r.value:status::VARCHAR) AS STATUS,
        j.SOURCE_FILE AS SOURCE_FILE
    FROM RAW_REDEMPTION_JSON j,
         LATERAL FLATTEN(input => j.PAYLOAD:redemptions) r
    WHERE NULLIF(TRIM(r.value:txn_id::VARCHAR), '') IS NOT NULL
      AND NULLIF(TRIM(j.PAYLOAD:member_id::VARCHAR), '') IS NOT NULL
      AND TRY_TO_DATE(r.value:txn_date::VARCHAR, 'YYYYMMDD') IS NOT NULL
      AND r.value:miles_redeemed::NUMBER >= 0
      AND UPPER(r.value:status::VARCHAR) IN ('COMPLETED', 'PENDING', 'CANCELLED', 'FAILED')
) s
ON t.TXN_ID = s.TXN_ID
WHEN MATCHED THEN UPDATE SET
    t.MEMBER_ID = s.MEMBER_ID,
    t.FEED_DATE = s.FEED_DATE,
    t.TXN_DATE = s.TXN_DATE,
    t.PARTNER = s.PARTNER,
    t.MILES_REDEEMED = s.MILES_REDEEMED,
    t.STATUS = s.STATUS,
    t.SOURCE_FILE = s.SOURCE_FILE
WHEN NOT MATCHED THEN INSERT (
    TXN_ID, MEMBER_ID, FEED_DATE, TXN_DATE, PARTNER,
    MILES_REDEEMED, STATUS, SOURCE_FILE
) VALUES (
    s.TXN_ID, s.MEMBER_ID, s.FEED_DATE, s.TXN_DATE, s.PARTNER,
    s.MILES_REDEEMED, s.STATUS, s.SOURCE_FILE
);

-- Member profile + transaction grain. LEFT JOIN deliberately preserves members
-- that have never redeemed miles.
WITH MEMBERS AS (
    SELECT * FROM TABLE_USA
    UNION ALL
    SELECT * FROM TABLE_IND
    UNION ALL
    SELECT * FROM TABLE_AUS
)
SELECT
    m.MEMBER_ID,
    m.MEMBER_NAME,
    m.COUNTRY,
    m.TIER_CODE,
    m.AGE,
    m.STALE_MEMBER,
    r.TXN_ID,
    r.TXN_DATE,
    r.PARTNER,
    r.MILES_REDEEMED,
    r.STATUS
FROM MEMBERS m
LEFT JOIN FCT_MEMBER_REDEMPTIONS r
    ON m.MEMBER_ID = r.MEMBER_ID;
