import sqlite3
from datetime import date
from pathlib import Path

from src.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[1]


def test_end_to_end_pipeline(tmp_path):
    db = tmp_path / "demo.db"
    summary = run_pipeline(ROOT / "data" / "input", db, date(2026, 9, 11))

    assert summary["raw_member_rows"] == 9
    assert summary["valid_staging_rows"] == 8
    assert summary["rejected_member_rows"] == 1
    assert summary["redemption_rows"] == 2

    with sqlite3.connect(db) as conn:
        raw_count = conn.execute("SELECT COUNT(*) FROM raw_member_landing").fetchone()[0]
        target_count = sum(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("table_usa", "table_ind", "table_aus")
        )
        assert raw_count == 9
        assert target_count == 8


def test_reconciliation_invariants(tmp_path):
    db = tmp_path / "reconcile.db"
    summary = run_pipeline(ROOT / "data" / "input", db, date(2026, 9, 11))

    assert summary["raw_member_rows"] == (
        summary["valid_staging_rows"] + summary["rejected_member_rows"]
    )
    assert summary["latest_member_rows"] == 8

    with sqlite3.connect(db) as conn:
        target_count = sum(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("table_usa", "table_ind", "table_aus")
        )
        assert target_count == summary["latest_member_rows"]
