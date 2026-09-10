from datetime import date
from src.pipeline import parse_flexible_date, compute_age, compute_stale_flag

def test_parse_flexible_date():
    assert parse_flexible_date("20240115") == "2024-01-15"
    assert parse_flexible_date(6152022) == "2022-06-15"
    assert parse_flexible_date("2021-13-13") is None
    assert parse_flexible_date(None) is None

def test_compute_age():
    ref = date(2024, 1, 1)
    assert compute_age("1990-01-01", ref_date=ref) == 34
    assert compute_age("1990-06-01", ref_date=ref) == 33
    assert compute_age(None, ref_date=ref) is None

def test_compute_stale_flag():
    ref = date(2024, 4, 1)
    assert compute_stale_flag("2024-02-01", ref_date=ref) == 0
    assert compute_stale_flag("2023-11-01", ref_date=ref) == 1
    assert compute_stale_flag(None, ref_date=ref) == 1
