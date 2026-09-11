from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%Y%m%d",
    "%m%d%Y",
)

VALID_TIERS = {"SLV", "GLD", "PLT"}
VALID_COUNTRIES = {"USA", "IND", "AUS"}
VALID_ACTIVE_FLAGS = {"A", "I"}


def parse_flexible_date(value: Any) -> str | None:
    """Parse known source date variants and return ISO YYYY-MM-DD.

    Invalid dates are intentionally returned as None so they can be quarantined by
    the validation layer instead of silently corrected.
    """
    if value is None or pd.isna(value):
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    raw = str(value).strip()
    if not raw or raw.upper() in {"NAT", "NONE", "NULL", "NAN"}:
        return None

    # Excel / pandas often surfaces timestamps as strings.
    raw = raw.split()[0]

    # Source USA uses numeric MMDDYYYY; some values lose the leading zero.
    if raw.isdigit() and len(raw) in {7, 8}:
        raw = raw.zfill(8)
        try:
            return datetime.strptime(raw, "%m%d%Y").date().isoformat()
        except ValueError:
            pass

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def compute_age(dob_iso: str | None, ref_date: date | None = None) -> int | None:
    if not dob_iso:
        return None
    ref_date = ref_date or date.today()
    try:
        born = datetime.strptime(dob_iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    return ref_date.year - born.year - (
        (ref_date.month, ref_date.day) < (born.month, born.day)
    )


def compute_stale_flag(
    flight_date_iso: str | None,
    ref_date: date | None = None,
) -> int | None:
    """Return 1 when days since last flight > 90, else 0.

    Missing/invalid flight dates return None because the assessment only defines
    staleness when a flight date is present. This makes the missing-data state
    explicit rather than conflating it with stale.
    """
    if not flight_date_iso:
        return None
    ref_date = ref_date or date.today()
    try:
        flight_date = datetime.strptime(flight_date_iso, "%Y-%m-%d").date()
    except ValueError:
        return None
    return int((ref_date - flight_date).days > 90)


def latest_record_wins(df: pd.DataFrame) -> pd.DataFrame:
    """Return one deterministic latest row per logical member key.

    Order of precedence:
      1. flight_date descending
      2. enrollment_date descending
      3. ingested_at descending
      4. source_row_number descending
    """
    if df.empty:
        return df.copy()

    result = df.copy()
    for col in ("flight_date", "enrollment_date", "ingested_at"):
        result[col] = pd.to_datetime(result[col], errors="coerce")

    result = result.sort_values(
        ["member_key", "flight_date", "enrollment_date", "ingested_at", "source_row_number"],
        ascending=[True, False, False, False, False],
        na_position="last",
    )
    return result.drop_duplicates(subset=["member_key"], keep="first").reset_index(drop=True)
