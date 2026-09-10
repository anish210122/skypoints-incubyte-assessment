# SkyPoints Data Platform - Incubyte Assessment

A production-grade ELT data pipeline implementing a Medallion Architecture for the SkyPoints loyalty program.

## Architecture Overview
- **Landing (Bronze)**: Raw ingestion preserving source payloads for both flat profile files and partner redemptions JSON.
- **Staging (Silver)**: Normalizes diverse date formats, derives customer Age dynamically, and calculates the 90-day inactivity flag (is_stale_member).
- **Country Targets (Gold)**: Enforces "Latest Record Wins" deduplication windowing to partition members cleanly across table_usa, table_ind, and table_aus.
- **Redemption Facts (Gold)**: Flattens semi-structured JSON redemption arrays into fct_member_redemptions and exposes unified analytical joins against country profiles.

## Edge Cases Handled
- **Corrupt Calendar Inputs**: Non-existent dates (such as 2021-13-13) are safely parsed to NULL.
- **Unpadded Numeric Dates**: MMDDYYYY integer formats (such as 6152022) are padded with leading zeros and parsed to standard ISO dates.
- **Cross-Border Relocation**: Members moving between countries are routed strictly to their most recent active country table.

## Quickstart
1. Activate virtual environment:
   .\venv\Scripts\Activate.ps1
2. Run the pipeline:
   python src\pipeline.py
3. Run automated tests:
   python -m pytest
