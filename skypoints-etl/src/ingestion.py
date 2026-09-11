from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


def _stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _base_record(
    *,
    source_country: str,
    source_file: str,
    row_number: int,
    member_id: object,
    member_name: object,
    tier_code: object,
    enrollment_raw: object,
    flight_raw: object,
    dob_raw: object = None,
    individual_or_corporate: object = None,
) -> dict:
    member_id_str = None if pd.isna(member_id) else str(member_id).strip()
    return {
        "record_type": "D",
        "member_key": f"{source_country}:{member_id_str}" if member_id_str else None,
        "member_id": member_id_str,
        "member_name": None if pd.isna(member_name) else str(member_name).strip(),
        "enrollment_date_raw": None if pd.isna(enrollment_raw) else str(enrollment_raw),
        "flight_date_raw": None if pd.isna(flight_raw) else str(flight_raw),
        "tier_code": None if pd.isna(tier_code) else str(tier_code).strip().upper(),
        "agent_name": None,
        "state": None,
        "country": source_country,
        "post_code": None,
        "dob_raw": None if dob_raw is None or pd.isna(dob_raw) else str(dob_raw),
        "is_active": "A",
        "individual_or_corporate": None
        if individual_or_corporate is None or pd.isna(individual_or_corporate)
        else str(individual_or_corporate).strip().upper(),
        "source_file": source_file,
        "source_row_number": row_number,
        "ingested_at": _stamp(),
    }


def ingest_usa(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    records = [
        _base_record(
            source_country="USA",
            source_file=path.name,
            row_number=i + 2,
            member_id=row["ID"],
            member_name=row["Name"],
            tier_code=row["TierCode"],
            enrollment_raw=row["EnrollmentDate"],
            flight_raw=row["FlightDate"],
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return pd.DataFrame(records)


def ingest_india(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    records = [
        _base_record(
            source_country="IND",
            source_file=path.name,
            row_number=i + 2,
            member_id=row["ID"],
            member_name=row["Name"],
            tier_code=row["TierCode"],
            enrollment_raw=row["EnrollmentDate"],
            flight_raw=row["Flight Date"],
            dob_raw=row["DOB"],
            individual_or_corporate=row["Individual or Corporate"],
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return pd.DataFrame(records)


def ingest_australia(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    records = [
        _base_record(
            source_country="AUS",
            source_file=path.name,
            row_number=i + 2,
            member_id=row["Unique ID"],
            member_name=row["Member Name"],
            tier_code=row["Tier Type"],
            enrollment_raw=row["Date of Enrollment"],
            flight_raw=row["Date of Flight"],
            dob_raw=row["Date of Birth"],
        )
        for i, (_, row) in enumerate(df.iterrows())
    ]
    return pd.DataFrame(records)


def ingest_member_files(data_dir: Path) -> pd.DataFrame:
    frames: Iterable[pd.DataFrame] = (
        ingest_usa(data_dir / "USA.csv"),
        ingest_india(data_dir / "IND.csv"),
        ingest_australia(data_dir / "AUS.xlsx"),
    )
    return pd.concat(frames, ignore_index=True)
