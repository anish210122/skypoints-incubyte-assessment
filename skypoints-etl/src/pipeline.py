from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from src.ingestion import ingest_member_files
from src.redemption_parser import flatten_redemptions
from src.transformations import compute_age, compute_stale_flag, latest_record_wins, parse_flexible_date
from src.validations import duplicate_member_keys, split_valid_and_rejected

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "input"
DEFAULT_DB = ROOT / "data" / "output" / "skypoints_demo.db"


def transform_members(raw: pd.DataFrame, ref_date: date) -> pd.DataFrame:
    staged = raw.copy()
    staged["enrollment_date"] = staged["enrollment_date_raw"].map(parse_flexible_date)
    staged["flight_date"] = staged["flight_date_raw"].map(parse_flexible_date)
    staged["dob"] = staged["dob_raw"].map(parse_flexible_date)
    staged["age"] = staged["dob"].map(lambda x: compute_age(x, ref_date))
    staged["stale_member"] = staged["flight_date"].map(lambda x: compute_stale_flag(x, ref_date))
    staged["processed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return staged


def _write_table(conn: sqlite3.Connection, name: str, df: pd.DataFrame) -> None:
    conn.execute(f"DELETE FROM {name}")
    if df.empty:
        return
    df.to_sql(name, conn, if_exists="append", index=False)


def run_pipeline(data_dir: Path, db_path: Path, ref_date: date) -> dict:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    ddl_path = ROOT / "sql" / "00_sqlite_demo_schema.sql"
    conn.executescript(ddl_path.read_text(encoding="utf-8"))

    # Bronze: actual assignment input files, preserved before normalization.
    raw = ingest_member_files(data_dir)
    _write_table(conn, "raw_member_landing", raw)

    # Silver: normalize types and derive age + 90-day stale flag.
    staged = transform_members(raw, ref_date)
    valid, rejected = split_valid_and_rejected(staged, ref_date)
    _write_table(conn, "stg_member_profiles", valid)
    _write_table(conn, "rejected_member_records", rejected)

    # Latest-record-wins is intentionally applied *after* staging so staging can
    # retain multiple versions of one logical member.
    latest = latest_record_wins(valid)
    target_cols = [
        "member_key", "member_id", "member_name", "enrollment_date", "flight_date",
        "tier_code", "country", "dob", "age", "stale_member", "is_active",
        "source_file", "source_row_number", "ingested_at",
    ]
    for country, table in {"USA": "table_usa", "IND": "table_ind", "AUS": "table_aus"}.items():
        _write_table(conn, table, latest.loc[latest["country"] == country, target_cols])

    # Semi-structured redemption feed -> queryable fact rows.
    redemption_path = data_dir / "redemptions.json"
    redemptions, redemption_rejects = flatten_redemptions(redemption_path)
    _write_table(conn, "fct_member_redemptions", redemptions)
    _write_table(conn, "rejected_redemptions", redemption_rejects)

    conn.commit()

    summary = {
        "raw_member_rows": len(raw),
        "valid_staging_rows": len(valid),
        "rejected_member_rows": len(rejected),
        "duplicate_member_keys_in_staging": len(duplicate_member_keys(valid)),
        "latest_member_rows": len(latest),
        "redemption_rows": len(redemptions),
        "rejected_redemption_rows": len(redemption_rejects),
        "database": str(db_path),
        "reference_date": ref_date.isoformat(),
    }
    conn.close()
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SkyPoints local ETL demonstration")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="Processing date used for age and stale-member derivation (YYYY-MM-DD)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    summary = run_pipeline(args.data_dir, args.db, date.fromisoformat(args.as_of_date))
    print(json.dumps(summary, indent=2))
