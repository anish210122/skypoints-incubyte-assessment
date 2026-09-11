from datetime import date

import pandas as pd

from src.transformations import compute_age, compute_stale_flag, latest_record_wins, parse_flexible_date


def test_parse_flexible_date_variants():
    assert parse_flexible_date("20240115") == "2024-01-15"
    assert parse_flexible_date(6152022) == "2022-06-15"
    assert parse_flexible_date("1/5/2022") == "2022-01-05"
    assert parse_flexible_date("2021-13-13") is None
    assert parse_flexible_date(None) is None


def test_compute_age_including_before_birthday():
    ref = date(2024, 1, 1)
    assert compute_age("1990-01-01", ref) == 34
    assert compute_age("1990-06-01", ref) == 33
    assert compute_age(None, ref) is None


def test_stale_boundary():
    ref = date(2024, 4, 1)
    assert compute_stale_flag("2024-01-02", ref) == 0  # exactly 90 days
    assert compute_stale_flag("2024-01-01", ref) == 1  # 91 days
    assert compute_stale_flag(None, ref) is None


def test_latest_record_wins_uses_flight_date_then_tiebreakers():
    df = pd.DataFrame(
        [
            {"member_key": "M1", "flight_date": "2024-01-01", "enrollment_date": "2020-01-01", "ingested_at": "2024-02-01T00:00:00+00:00", "source_row_number": 2, "country": "IND"},
            {"member_key": "M1", "flight_date": "2024-02-01", "enrollment_date": "2020-01-01", "ingested_at": "2024-02-02T00:00:00+00:00", "source_row_number": 3, "country": "USA"},
        ]
    )
    result = latest_record_wins(df)
    assert len(result) == 1
    assert result.iloc[0]["country"] == "USA"


def test_latest_record_wins_can_route_a_global_member_after_country_move():
    # Production assumption: once MEMBER_KEY is a globally unique membership ID,
    # records from different countries are versions of the same logical member.
    df = pd.DataFrame(
        [
            {
                "member_key": "GLOBAL-42",
                "member_id": "42",
                "flight_date": "2024-01-10",
                "enrollment_date": "2020-01-01",
                "ingested_at": "2024-01-11T00:00:00+00:00",
                "source_row_number": 1,
                "country": "IND",
            },
            {
                "member_key": "GLOBAL-42",
                "member_id": "42",
                "flight_date": "2024-05-10",
                "enrollment_date": "2020-01-01",
                "ingested_at": "2024-05-11T00:00:00+00:00",
                "source_row_number": 1,
                "country": "USA",
            },
        ]
    )

    result = latest_record_wins(df)
    assert len(result) == 1
    assert result.iloc[0]["country"] == "USA"
