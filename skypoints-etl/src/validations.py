from __future__ import annotations

from datetime import date

import pandas as pd

from .transformations import VALID_ACTIVE_FLAGS, VALID_COUNTRIES, VALID_TIERS


def _is_missing(value) -> bool:
    """Return True for None, NaN/NaT, or blank-like strings."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip().upper() in {"", "NAN", "NAT", "NONE", "NULL"}:
        return True
    return False


def validate_member_row(row: pd.Series, ref_date: date) -> list[str]:
    errors: list[str] = []

    if _is_missing(row.get("member_id")):
        errors.append("MISSING_MEMBER_ID")
    if _is_missing(row.get("member_name")):
        errors.append("MISSING_MEMBER_NAME")
    if _is_missing(row.get("enrollment_date")):
        errors.append("INVALID_OR_MISSING_ENROLLMENT_DATE")

    if row.get("country") not in VALID_COUNTRIES:
        errors.append("INVALID_COUNTRY")
    if row.get("tier_code") not in VALID_TIERS:
        errors.append("INVALID_TIER_CODE")
    if row.get("is_active") not in VALID_ACTIVE_FLAGS:
        errors.append("INVALID_ACTIVE_FLAG")

    dob = pd.to_datetime(row.get("dob"), errors="coerce")
    enrollment = pd.to_datetime(row.get("enrollment_date"), errors="coerce")
    flight = pd.to_datetime(row.get("flight_date"), errors="coerce")

    if pd.notna(dob) and dob.date() > ref_date:
        errors.append("DOB_IN_FUTURE")
    if pd.notna(dob) and pd.notna(enrollment) and enrollment < dob:
        errors.append("ENROLLMENT_BEFORE_DOB")
    if pd.notna(flight) and pd.notna(enrollment) and flight < enrollment:
        errors.append("FLIGHT_BEFORE_ENROLLMENT")

    age = row.get("age")
    if age is not None and not pd.isna(age) and (age < 0 or age > 115):
        errors.append("INVALID_AGE")

    return errors


def split_valid_and_rejected(df: pd.DataFrame, ref_date: date) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid_rows: list[dict] = []
    rejected_rows: list[dict] = []

    for _, row in df.iterrows():
        errors = validate_member_row(row, ref_date)
        record = row.to_dict()
        if errors:
            rejected_rows.append({**record, "rejection_reason": "|".join(errors)})
        else:
            valid_rows.append(record)

    return pd.DataFrame(valid_rows), pd.DataFrame(rejected_rows)


def duplicate_member_keys(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    counts = df.groupby("member_key").size().rename("row_count").reset_index()
    return counts[counts["row_count"] > 1]
