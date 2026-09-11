from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .transformations import parse_flexible_date

VALID_REDEMPTION_STATUSES = {"COMPLETED", "PENDING", "CANCELLED", "FAILED"}


def flatten_redemptions(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = [payload]

    rows: list[dict] = []
    rejects: list[dict] = []
    seen_txn_ids: set[str] = set()

    for entry in payload:
        member_id = str(entry.get("member_id", "")).strip() or None
        feed_date = parse_flexible_date(entry.get("feed_date"))
        for txn in entry.get("redemptions", []):
            txn_id = str(txn.get("txn_id", "")).strip() or None
            txn_date = parse_flexible_date(txn.get("txn_date"))
            miles = txn.get("miles_redeemed")
            status = str(txn.get("status", "")).strip().upper()

            errors: list[str] = []
            if not txn_id:
                errors.append("MISSING_TXN_ID")
            if txn_id and txn_id in seen_txn_ids:
                errors.append("DUPLICATE_TXN_ID")
            if not member_id:
                errors.append("MISSING_MEMBER_ID")
            if txn_date is None:
                errors.append("INVALID_TXN_DATE")
            if miles is None or pd.isna(miles) or float(miles) < 0:
                errors.append("INVALID_MILES_REDEEMED")
            if status not in VALID_REDEMPTION_STATUSES:
                errors.append("INVALID_STATUS")

            record = {
                "txn_id": txn_id,
                "member_id": member_id,
                "feed_date": feed_date,
                "txn_date": txn_date,
                "partner": txn.get("partner"),
                "miles_redeemed": miles,
                "status": status,
            }
            if errors:
                rejects.append({**record, "rejection_reason": "|".join(errors)})
            else:
                rows.append(record)
                seen_txn_ids.add(txn_id)

    return pd.DataFrame(rows), pd.DataFrame(rejects)
