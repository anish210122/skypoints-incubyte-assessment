-- 1. Raw Landing Table (Bronze Layer)
CREATE TABLE IF NOT EXISTS raw_member_landing (
    record_type     TEXT,
    member_name     TEXT,
    member_id       TEXT,
    enrollment_date TEXT,
    flight_date     TEXT,
    tier_code       TEXT,
    agent_name      TEXT,
    state           TEXT,
    country         TEXT,
    post_code       TEXT,
    dob             TEXT,
    is_active       TEXT,
    loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Cleaned Staging Table (Silver Layer)
CREATE TABLE IF NOT EXISTS stg_member_profiles (
    member_id        TEXT PRIMARY KEY,
    member_name      TEXT NOT NULL,
    enrollment_date  DATE NOT NULL,
    flight_date      DATE,
    tier_code        TEXT,
    agent_name       TEXT,
    state            TEXT,
    country          TEXT NOT NULL,
    post_code        TEXT,
    dob              DATE,
    age              INTEGER,
    is_stale_member  INTEGER,
    is_active        TEXT
);

-- 3. Country Target Tables (Gold Layer)
CREATE TABLE IF NOT EXISTS table_usa (
    member_id        TEXT PRIMARY KEY,
    member_name      TEXT NOT NULL,
    enrollment_date  DATE NOT NULL,
    flight_date      DATE,
    tier_code        TEXT,
    agent_name       TEXT,
    state            TEXT,
    country          TEXT DEFAULT 'USA',
    post_code        TEXT,
    dob              DATE,
    age              INTEGER,
    is_stale_member  INTEGER,
    is_active        TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS table_ind (
    member_id        TEXT PRIMARY KEY,
    member_name      TEXT NOT NULL,
    enrollment_date  DATE NOT NULL,
    flight_date      DATE,
    tier_code        TEXT,
    agent_name       TEXT,
    state            TEXT,
    country          TEXT DEFAULT 'IND',
    post_code        TEXT,
    dob              DATE,
    age              INTEGER,
    is_stale_member  INTEGER,
    is_active        TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS table_aus (
    member_id        TEXT PRIMARY KEY,
    member_name      TEXT NOT NULL,
    enrollment_date  DATE NOT NULL,
    flight_date      DATE,
    tier_code        TEXT,
    agent_name       TEXT,
    state            TEXT,
    country          TEXT DEFAULT 'AUS',
    post_code        TEXT,
    dob              DATE,
    age              INTEGER,
    is_stale_member  INTEGER,
    is_active        TEXT,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Flattened Fact Table for Partner Redemptions
CREATE TABLE IF NOT EXISTS fct_member_redemptions (
    txn_id          TEXT PRIMARY KEY,
    member_id       TEXT NOT NULL,
    feed_date       DATE,
    txn_date        DATE,
    partner         TEXT,
    miles_redeemed  INTEGER,
    status          TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
