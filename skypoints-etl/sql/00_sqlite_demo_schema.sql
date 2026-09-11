-- SQLite schema used only for the executable local demonstration.
-- Snowflake production DDL is in 01_snowflake_ddl.sql.

CREATE TABLE IF NOT EXISTS raw_member_landing (
    record_type TEXT,
    member_key TEXT,
    member_id TEXT,
    member_name TEXT,
    enrollment_date_raw TEXT,
    flight_date_raw TEXT,
    tier_code TEXT,
    agent_name TEXT,
    state TEXT,
    country TEXT,
    post_code TEXT,
    dob_raw TEXT,
    is_active TEXT,
    individual_or_corporate TEXT,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stg_member_profiles (
    record_type TEXT,
    member_key TEXT NOT NULL,
    member_id TEXT NOT NULL,
    member_name TEXT NOT NULL,
    enrollment_date_raw TEXT,
    flight_date_raw TEXT,
    tier_code TEXT,
    agent_name TEXT,
    state TEXT,
    country TEXT NOT NULL,
    post_code TEXT,
    dob_raw TEXT,
    is_active TEXT,
    individual_or_corporate TEXT,
    source_file TEXT NOT NULL,
    source_row_number INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    enrollment_date TEXT NOT NULL,
    flight_date TEXT,
    dob TEXT,
    age INTEGER,
    stale_member INTEGER,
    processed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rejected_member_records AS SELECT *, '' AS rejection_reason
FROM stg_member_profiles WHERE 1=0;

CREATE TABLE IF NOT EXISTS table_usa (
    member_key TEXT PRIMARY KEY, member_id TEXT, member_name TEXT, enrollment_date TEXT,
    flight_date TEXT, tier_code TEXT, country TEXT, dob TEXT, age INTEGER,
    stale_member INTEGER, is_active TEXT, source_file TEXT, source_row_number INTEGER,
    ingested_at TEXT
);
CREATE TABLE IF NOT EXISTS table_ind AS SELECT * FROM table_usa WHERE 1=0;
CREATE TABLE IF NOT EXISTS table_aus AS SELECT * FROM table_usa WHERE 1=0;

CREATE TABLE IF NOT EXISTS fct_member_redemptions (
    txn_id TEXT PRIMARY KEY,
    member_id TEXT NOT NULL,
    feed_date TEXT,
    txn_date TEXT,
    partner TEXT,
    miles_redeemed INTEGER,
    status TEXT
);
CREATE TABLE IF NOT EXISTS rejected_redemptions AS SELECT *, '' AS rejection_reason
FROM fct_member_redemptions WHERE 1=0;
