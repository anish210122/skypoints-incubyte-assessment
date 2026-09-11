-- Member transformation for Snowflake.
--
-- Design goals:
--   * preserve the raw feed unchanged for replay/audit;
--   * parse each source's known date format explicitly rather than relying on
--     session-dependent automatic date parsing;
--   * quarantine malformed rows before they reach the typed staging table;
--   * make re-runs idempotent at source-file + row-number grain;
--   * retain multiple versions in staging, then apply deterministic
--     latest-record-wins before routing to country targets.

-- 1) Parse raw strings once. Country-specific parsing reflects the supplied
-- sample files: USA=MMDDYYYY (sometimes 7 digits due to leading-zero loss),
-- IND=MM/DD/YYYY, AUS=YYYY-MM-DD. YYYYMMDD is retained as a safe fallback for
-- the format described in the assessment specification.
CREATE OR REPLACE TEMP TABLE PARSED_MEMBER_BATCH AS
SELECT
    COUNTRY || ':' || MEMBER_ID AS MEMBER_KEY,
    MEMBER_ID,
    MEMBER_NAME,
    CASE
        WHEN NULLIF(TRIM(ENROLLMENT_DATE_RAW), '') IS NULL THEN NULL
        WHEN COUNTRY = 'USA' AND REGEXP_LIKE(TRIM(ENROLLMENT_DATE_RAW), '^[0-9]{7,8}$')
            THEN TRY_TO_DATE(LPAD(TRIM(ENROLLMENT_DATE_RAW), 8, '0'), 'MMDDYYYY')
        WHEN COUNTRY = 'IND'
            THEN TRY_TO_DATE(TRIM(ENROLLMENT_DATE_RAW), 'MM/DD/YYYY')
        WHEN COUNTRY = 'AUS'
            THEN TRY_TO_DATE(TRIM(ENROLLMENT_DATE_RAW), 'YYYY-MM-DD')
        WHEN REGEXP_LIKE(TRIM(ENROLLMENT_DATE_RAW), '^[0-9]{8}$')
            THEN TRY_TO_DATE(TRIM(ENROLLMENT_DATE_RAW), 'YYYYMMDD')
        ELSE TRY_TO_DATE(TRIM(ENROLLMENT_DATE_RAW))
    END AS ENROLLMENT_DATE,
    CASE
        WHEN NULLIF(TRIM(LAST_FLIGHT_DATE_RAW), '') IS NULL THEN NULL
        WHEN COUNTRY = 'USA' AND REGEXP_LIKE(TRIM(LAST_FLIGHT_DATE_RAW), '^[0-9]{7,8}$')
            THEN TRY_TO_DATE(LPAD(TRIM(LAST_FLIGHT_DATE_RAW), 8, '0'), 'MMDDYYYY')
        WHEN COUNTRY = 'IND'
            THEN TRY_TO_DATE(TRIM(LAST_FLIGHT_DATE_RAW), 'MM/DD/YYYY')
        WHEN COUNTRY = 'AUS'
            THEN TRY_TO_DATE(TRIM(LAST_FLIGHT_DATE_RAW), 'YYYY-MM-DD')
        WHEN REGEXP_LIKE(TRIM(LAST_FLIGHT_DATE_RAW), '^[0-9]{8}$')
            THEN TRY_TO_DATE(TRIM(LAST_FLIGHT_DATE_RAW), 'YYYYMMDD')
        ELSE TRY_TO_DATE(TRIM(LAST_FLIGHT_DATE_RAW))
    END AS FLIGHT_DATE,
    TIER_CODE,
    AGENT_NAME,
    STATE,
    COUNTRY,
    POST_CODE,
    CASE
        WHEN NULLIF(TRIM(DOB_RAW), '') IS NULL THEN NULL
        WHEN COUNTRY = 'USA' AND REGEXP_LIKE(TRIM(DOB_RAW), '^[0-9]{7,8}$')
            THEN TRY_TO_DATE(LPAD(TRIM(DOB_RAW), 8, '0'), 'MMDDYYYY')
        WHEN COUNTRY = 'IND'
            THEN TRY_TO_DATE(TRIM(DOB_RAW), 'MM/DD/YYYY')
        WHEN COUNTRY = 'AUS'
            THEN TRY_TO_DATE(TRIM(DOB_RAW), 'YYYY-MM-DD')
        WHEN REGEXP_LIKE(TRIM(DOB_RAW), '^[0-9]{8}$')
            THEN TRY_TO_DATE(TRIM(DOB_RAW), 'YYYYMMDD')
        ELSE TRY_TO_DATE(TRIM(DOB_RAW))
    END AS DOB,
    IS_ACTIVE,
    SOURCE_FILE,
    SOURCE_ROW_NUMBER,
    INGESTED_AT,
    OBJECT_CONSTRUCT_KEEP_NULL(
        'member_name', MEMBER_NAME,
        'member_id', MEMBER_ID,
        'enrollment_date_raw', ENROLLMENT_DATE_RAW,
        'last_flight_date_raw', LAST_FLIGHT_DATE_RAW,
        'tier_code', TIER_CODE,
        'agent_name', AGENT_NAME,
        'state', STATE,
        'country', COUNTRY,
        'post_code', POST_CODE,
        'dob_raw', DOB_RAW,
        'is_active', IS_ACTIVE
    ) AS RAW_PAYLOAD
FROM RAW_MEMBER_LANDING;

-- 2) Quarantine invalid rows. NOT EXISTS makes this safe to run again for the
-- same source file/row without multiplying reject records.
INSERT INTO REJECTED_MEMBER_RECORDS (
    SOURCE_FILE, SOURCE_ROW_NUMBER, MEMBER_ID, RAW_PAYLOAD,
    REJECTION_REASON, REJECTED_AT
)
SELECT
    p.SOURCE_FILE,
    p.SOURCE_ROW_NUMBER,
    p.MEMBER_ID,
    p.RAW_PAYLOAD,
    ARRAY_TO_STRING(ARRAY_CONSTRUCT_COMPACT(
        IFF(NULLIF(TRIM(p.MEMBER_ID), '') IS NULL, 'MISSING_MEMBER_ID', NULL),
        IFF(NULLIF(TRIM(p.MEMBER_NAME), '') IS NULL, 'MISSING_MEMBER_NAME', NULL),
        IFF(p.ENROLLMENT_DATE IS NULL, 'INVALID_OR_MISSING_ENROLLMENT_DATE', NULL),
        IFF(p.DOB IS NOT NULL AND p.DOB > CURRENT_DATE(), 'DOB_IN_FUTURE', NULL),
        IFF(p.DOB IS NOT NULL AND p.ENROLLMENT_DATE IS NOT NULL AND p.ENROLLMENT_DATE < p.DOB, 'ENROLLMENT_BEFORE_DOB', NULL),
        IFF(p.FLIGHT_DATE IS NOT NULL AND p.ENROLLMENT_DATE IS NOT NULL AND p.FLIGHT_DATE < p.ENROLLMENT_DATE, 'FLIGHT_BEFORE_ENROLLMENT', NULL),
        IFF(p.TIER_CODE IS NOT NULL AND p.TIER_CODE NOT IN ('SLV', 'GLD', 'PLT'), 'INVALID_TIER_CODE', NULL),
        IFF(p.COUNTRY NOT IN ('USA', 'IND', 'AUS'), 'INVALID_COUNTRY', NULL),
        IFF(p.IS_ACTIVE IS NOT NULL AND p.IS_ACTIVE NOT IN ('A', 'I'), 'INVALID_ACTIVE_FLAG', NULL)
    ), '|') AS REJECTION_REASON,
    CURRENT_TIMESTAMP()
FROM PARSED_MEMBER_BATCH p
WHERE (
       NULLIF(TRIM(p.MEMBER_ID), '') IS NULL
    OR NULLIF(TRIM(p.MEMBER_NAME), '') IS NULL
    OR p.ENROLLMENT_DATE IS NULL
    OR (p.DOB IS NOT NULL AND p.DOB > CURRENT_DATE())
    OR (p.DOB IS NOT NULL AND p.ENROLLMENT_DATE IS NOT NULL AND p.ENROLLMENT_DATE < p.DOB)
    OR (p.FLIGHT_DATE IS NOT NULL AND p.ENROLLMENT_DATE IS NOT NULL AND p.FLIGHT_DATE < p.ENROLLMENT_DATE)
    OR (p.TIER_CODE IS NOT NULL AND p.TIER_CODE NOT IN ('SLV', 'GLD', 'PLT'))
    OR p.COUNTRY NOT IN ('USA', 'IND', 'AUS')
    OR (p.IS_ACTIVE IS NOT NULL AND p.IS_ACTIVE NOT IN ('A', 'I'))
)
AND NOT EXISTS (
    SELECT 1
    FROM REJECTED_MEMBER_RECORDS r
    WHERE r.SOURCE_FILE = p.SOURCE_FILE
      AND r.SOURCE_ROW_NUMBER = p.SOURCE_ROW_NUMBER
);

-- 3) Merge valid records into staging. Staging intentionally keeps different
-- source versions of a logical member; source-file + row-number identifies the
-- physical source record and makes file replay idempotent.
MERGE INTO STG_MEMBER_PROFILES t
USING (
    SELECT
        MEMBER_KEY,
        MEMBER_ID,
        MEMBER_NAME,
        ENROLLMENT_DATE,
        FLIGHT_DATE,
        TIER_CODE,
        AGENT_NAME,
        STATE,
        COUNTRY,
        POST_CODE,
        DOB,
        CASE
            WHEN DOB IS NULL THEN NULL
            ELSE DATEDIFF('year', DOB, CURRENT_DATE())
                 - IFF(TO_CHAR(CURRENT_DATE(), 'MMDD') < TO_CHAR(DOB, 'MMDD'), 1, 0)
        END AS AGE,
        CASE
            WHEN FLIGHT_DATE IS NULL THEN NULL
            ELSE DATEDIFF('day', FLIGHT_DATE, CURRENT_DATE()) > 90
        END AS STALE_MEMBER,
        IS_ACTIVE,
        SOURCE_FILE,
        SOURCE_ROW_NUMBER,
        INGESTED_AT
    FROM PARSED_MEMBER_BATCH
    WHERE NULLIF(TRIM(MEMBER_ID), '') IS NOT NULL
      AND NULLIF(TRIM(MEMBER_NAME), '') IS NOT NULL
      AND ENROLLMENT_DATE IS NOT NULL
      AND (DOB IS NULL OR DOB <= CURRENT_DATE())
      AND (DOB IS NULL OR ENROLLMENT_DATE >= DOB)
      AND (FLIGHT_DATE IS NULL OR FLIGHT_DATE >= ENROLLMENT_DATE)
      AND (TIER_CODE IS NULL OR TIER_CODE IN ('SLV', 'GLD', 'PLT'))
      AND COUNTRY IN ('USA', 'IND', 'AUS')
      AND (IS_ACTIVE IS NULL OR IS_ACTIVE IN ('A', 'I'))
) s
ON t.SOURCE_FILE = s.SOURCE_FILE
AND t.SOURCE_ROW_NUMBER = s.SOURCE_ROW_NUMBER
WHEN MATCHED THEN UPDATE SET
    t.MEMBER_KEY = s.MEMBER_KEY,
    t.MEMBER_ID = s.MEMBER_ID,
    t.MEMBER_NAME = s.MEMBER_NAME,
    t.ENROLLMENT_DATE = s.ENROLLMENT_DATE,
    t.FLIGHT_DATE = s.FLIGHT_DATE,
    t.TIER_CODE = s.TIER_CODE,
    t.AGENT_NAME = s.AGENT_NAME,
    t.STATE = s.STATE,
    t.COUNTRY = s.COUNTRY,
    t.POST_CODE = s.POST_CODE,
    t.DOB = s.DOB,
    t.AGE = s.AGE,
    t.STALE_MEMBER = s.STALE_MEMBER,
    t.IS_ACTIVE = s.IS_ACTIVE,
    t.INGESTED_AT = s.INGESTED_AT,
    t.PROCESSED_AT = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
    MEMBER_KEY, MEMBER_ID, MEMBER_NAME, ENROLLMENT_DATE, FLIGHT_DATE,
    TIER_CODE, AGENT_NAME, STATE, COUNTRY, POST_CODE, DOB, AGE,
    STALE_MEMBER, IS_ACTIVE, SOURCE_FILE, SOURCE_ROW_NUMBER, INGESTED_AT
) VALUES (
    s.MEMBER_KEY, s.MEMBER_ID, s.MEMBER_NAME, s.ENROLLMENT_DATE, s.FLIGHT_DATE,
    s.TIER_CODE, s.AGENT_NAME, s.STATE, s.COUNTRY, s.POST_CODE, s.DOB, s.AGE,
    s.STALE_MEMBER, s.IS_ACTIVE, s.SOURCE_FILE, s.SOURCE_ROW_NUMBER, s.INGESTED_AT
);

-- 4) Deterministic latest-record-wins. In production, if MEMBER_ID is globally
-- unique across countries, set MEMBER_KEY = MEMBER_ID so a move from IND to USA
-- is treated as two versions of one member rather than two different members.
CREATE OR REPLACE TEMP TABLE LATEST_MEMBER AS
SELECT *
FROM STG_MEMBER_PROFILES
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY MEMBER_KEY
    ORDER BY FLIGHT_DATE DESC NULLS LAST,
             ENROLLMENT_DATE DESC,
             INGESTED_AT DESC,
             SOURCE_ROW_NUMBER DESC
) = 1;

-- 5) Country targets represent current-state snapshots. Rebuilding them from
-- LATEST_MEMBER is deliberately idempotent and also removes a member from the
-- old country table after a country move.
BEGIN;
TRUNCATE TABLE TABLE_USA;
INSERT INTO TABLE_USA SELECT * FROM LATEST_MEMBER WHERE COUNTRY = 'USA';
TRUNCATE TABLE TABLE_IND;
INSERT INTO TABLE_IND SELECT * FROM LATEST_MEMBER WHERE COUNTRY = 'IND';
TRUNCATE TABLE TABLE_AUS;
INSERT INTO TABLE_AUS SELECT * FROM LATEST_MEMBER WHERE COUNTRY = 'AUS';
COMMIT;
