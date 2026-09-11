# Changes to apply to your GitHub repository

This revised version is intended to replace/extend the current `skypoints-etl` folder.

## Existing files to replace

- `README.md` → expanded architecture, assumptions, run instructions, AI usage and commit strategy.
- `requirements.txt` → simplified runtime/test dependencies.
- `src/pipeline.py` → now reads the real USA/IND/AUS inputs instead of hard-coded records.

## Existing files to retire or replace

- `sql/01_ddl_tables.sql` → replace with:
  - `sql/00_sqlite_demo_schema.sql`
  - `sql/01_snowflake_ddl.sql`
- `sql/02_analytics_and_validations.sql` → replace with:
  - `sql/02_snowflake_member_transform.sql`
  - `sql/03_snowflake_redemptions.sql`
  - `sql/04_data_quality.sql`
- `tests/test_quality_checks.py` → replace with the expanded files under `tests/`.

## New Python modules

- `src/ingestion.py` — source-specific schema mapping for USA CSV, India CSV and Australia XLSX.
- `src/transformations.py` — date parsing, age, stale flag and deterministic latest-record-wins.
- `src/validations.py` — mandatory, domain and chronology validations plus quarantine split.
- `src/redemption_parser.py` — flattened redemption transaction parser and validation.

## New documentation

- `docs/architecture.md` — separates the laptop demo from the billion-row Snowflake production design.

## New source data layout

Move/rename your supplied files into:

- `data/input/USA.csv`
- `data/input/IND.csv`
- `data/input/AUS.xlsx`
- `data/input/redemptions.json`

## Recommended commits

1. `refactor: ingest actual USA IND AUS source files`
2. `feat: add raw landing and normalized staging layers`
3. `feat: add quarantine and data quality checks`
4. `feat: implement deterministic latest-record-wins routing`
5. `feat: flatten redemption JSON and analytical join`
6. `test: expand transformation and validation coverage`
7. `docs: add Snowflake architecture scaling and assumptions`

Do not commit `data/output/skypoints_demo.db`.

## Final polish included

- `pyproject.toml` added so imports/tests work reliably from a clean clone.
- `.github/workflows/tests.yml` added to run `python -m pytest -q` on every push/PR.
- Snowflake member-date parsing is explicit for USA/IND/AUS formats, with quarantine before typed staging.
- Snowflake staging and redemption loads use idempotent `MERGE` patterns.
- Reconciliation and cross-country latest-record tests were added.
- Generated cache folders are excluded/removed.
