# SkyPoints Data Engineering Assessment

A production-minded solution for the Incubyte SkyPoints assessment. The repository contains two complementary pieces:

1. **Runnable local ETL demonstration** using Python + SQLite against the supplied USA, India and Australia files.
2. **Snowflake production design** showing typed DDL, set-based transformation, `QUALIFY ROW_NUMBER()` for latest-record-wins, JSON `VARIANT` + `LATERAL FLATTEN`, validations and reconciliation.

The local database is a demo harness, not a claim that pandas/SQLite is appropriate for billions of daily rows.

## Requirements covered

| Assessment requirement | Implementation |
|---|---|
| Raw/landing, staging and country DDL | `sql/01_snowflake_ddl.sql` |
| Age and Stale_Member (>90 days) | `src/transformations.py`, `sql/02_snowflake_member_transform.sql` |
| Per-country split + latest record wins | `latest_record_wins()` and Snowflake `QUALIFY ROW_NUMBER()` |
| Flatten JSON redemption feed | `src/redemption_parser.py`, `sql/03_snowflake_redemptions.sql` |
| Join redemptions to member profiles | `LEFT JOIN` example in `sql/03_snowflake_redemptions.sql` |
| Data-quality checks | `src/validations.py`, `sql/04_data_quality.sql` |
| Production/scaling thinking | `docs/architecture.md` |
| Automated tests | `tests/` |
| Reproducible package/test config | `pyproject.toml` |
| CI on every push/PR | `.github/workflows/tests.yml` |

## Architecture at a glance

```text
USA.csv / IND.csv / AUS.xlsx          Redemption JSON
              |                             |
              v                             v
      RAW_MEMBER_LANDING          RAW_REDEMPTION_JSON (VARIANT)
              |                             |
       parse + validate              LATERAL FLATTEN
         /           \                       |
        v             v                      v
REJECTED_MEMBER   STG_MEMBER_PROFILES  FCT_MEMBER_REDEMPTIONS
                      |
              latest-record-wins
                      |
        +-------------+-------------+
        |             |             |
        v             v             v
    TABLE_USA     TABLE_IND     TABLE_AUS
```

The executable Python/SQLite pipeline demonstrates the same logical flow on the supplied sample files. The Snowflake SQL shows the set-based, replay-safe production pattern.

## Source schema normalization

The supplied files have intentionally different column names and date formats:

- **USA.csv**: `ID`, `Name`, `TierCode`, numeric `EnrollmentDate`, numeric `FlightDate`.
- **IND.csv**: adds `DOB`, `Individual or Corporate`, and slash-separated dates.
- **AUS.xlsx**: uses `Unique ID`, `Member Name`, `Tier Type`, `Date of Birth`, `Date of Enrollment`, `Date of Flight`.

`src/ingestion.py` maps all three sources into one raw canonical record. The original date values are preserved as strings in the raw layer before parsing.

## Data quality strategy

Bad source values are not silently fixed. A malformed value such as the Australian enrollment date `2021-13-13` becomes an explicit rejected record with a reason code.

Checks include mandatory `member_id`, `member_name`, and `enrollment_date`; valid country/tier/active flag; DOB not in the future; enrollment not before DOB; flight date not before enrollment; reasonable age; duplicate transaction IDs; valid redemption status; non-negative miles; orphan redemption-member checks; and source/stage/target reconciliation.

## Latest record wins

Staging intentionally allows multiple versions of a member. The current record is selected deterministically using:

1. latest flight date,
2. latest enrollment date,
3. latest ingestion timestamp,
4. latest source row number.

In Snowflake this is implemented with `ROW_NUMBER() OVER (...) QUALIFY = 1`.

### Member key assumption

The supplied country samples reuse IDs `1`, `2`, `3` for different people. The executable demo therefore uses `country:member_id` as a safe logical key. If the production feed guarantees a global SkyPoints membership ID, that global ID should be used instead; it is then possible to detect a member moving countries and route only the latest version to the new country's target table.

## Redemption JSON

The local demo parses one row per redemption. The production Snowflake pattern stores the unmodified feed in a `VARIANT` landing table and flattens `payload:redemptions` using `LATERAL FLATTEN`. The analytical example uses a `LEFT JOIN` so member profiles remain visible even if the member has no redemption activity.

## Run locally

From the `skypoints-etl-revised` directory:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m src.pipeline --as-of-date 2026-09-11
python -m pytest -q
```

The pipeline writes `data/output/skypoints_demo.db` and prints a processing summary. GitHub Actions runs the same test suite on every push and pull request.

## Repository layout

```text
skypoints-etl-revised/
├── data/
│   ├── input/
│   │   ├── USA.csv
│   │   ├── IND.csv
│   │   ├── AUS.xlsx
│   │   └── redemptions.json
│   └── output/
├── .github/workflows/tests.yml
├── pyproject.toml
├── docs/
│   └── architecture.md
├── sql/
│   ├── 00_sqlite_demo_schema.sql
│   ├── 01_snowflake_ddl.sql
│   ├── 02_snowflake_member_transform.sql
│   ├── 03_snowflake_redemptions.sql
│   └── 04_data_quality.sql
├── src/
│   ├── ingestion.py
│   ├── pipeline.py
│   ├── redemption_parser.py
│   ├── transformations.py
│   └── validations.py
└── tests/
```

## AI usage

AI was used as an engineering accelerator for code review, test-case brainstorming, identifying edge cases in the supplied sample files, and documenting trade-offs. All generated suggestions were reviewed against the assignment, sample data and executable tests before inclusion. Engineering decisions (for example NULL stale status for missing flight dates, rejection instead of silent correction, and local-ID namespacing) are explicitly documented so they can be defended in an interview.

## Idempotency and replay

The production SQL is written to tolerate reprocessing: member staging uses `MERGE` at `source_file + source_row_number` grain, redemption facts use `MERGE` on `txn_id`, reject rows are protected against duplicate insertion, and the country tables are rebuilt from the deterministic current-state result. In a real deployment I would also track a load/batch ID plus file checksum in an audit table and skip files already marked successful.

## Suggested incremental commit sequence

Do not upload this as one giant commit. A transparent sequence would be:

```text
1. refactor: ingest actual USA IND AUS source files
2. feat: add raw landing and normalized staging layers
3. feat: add quarantine and data quality checks
4. feat: implement deterministic latest-record-wins routing
5. feat: flatten redemption JSON and analytical join
6. test: expand transformation and validation coverage
7. docs: add Snowflake architecture scaling and assumptions
```
