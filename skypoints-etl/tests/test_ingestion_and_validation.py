from datetime import date
from pathlib import Path

from src.ingestion import ingest_member_files
from src.pipeline import transform_members
from src.validations import split_valid_and_rejected

ROOT = Path(__file__).resolve().parents[1]


def test_actual_files_are_ingested():
    raw = ingest_member_files(ROOT / "data" / "input")
    assert len(raw) == 9
    assert set(raw["country"]) == {"USA", "IND", "AUS"}
    assert set(raw["source_file"]) == {"USA.csv", "IND.csv", "AUS.xlsx"}


def test_bad_australian_date_is_quarantined():
    raw = ingest_member_files(ROOT / "data" / "input")
    staged = transform_members(raw, date(2026, 9, 11))
    valid, rejected = split_valid_and_rejected(staged, date(2026, 9, 11))

    assert len(valid) == 8
    assert len(rejected) == 1
    assert rejected.iloc[0]["member_name"] == "Jonnathan"
    assert "INVALID_OR_MISSING_ENROLLMENT_DATE" in rejected.iloc[0]["rejection_reason"]


def test_overlapping_country_ids_are_not_accidentally_merged():
    raw = ingest_member_files(ROOT / "data" / "input")
    assert raw["member_id"].duplicated().any()
    assert raw["member_key"].is_unique
