import json
from pathlib import Path

from src.redemption_parser import flatten_redemptions

ROOT = Path(__file__).resolve().parents[1]


def test_redemption_feed_flattens_array():
    good, rejected = flatten_redemptions(ROOT / "data" / "input" / "redemptions.json")
    assert len(good) == 2
    assert rejected.empty
    assert set(good["txn_id"]) == {"RX10091", "RX10092"}


def test_duplicate_and_negative_redemption_are_rejected(tmp_path):
    payload = [
        {
            "member_id": "1",
            "feed_date": "20240115",
            "redemptions": [
                {"txn_id": "T1", "txn_date": "20240110", "partner": "A", "miles_redeemed": 10, "status": "COMPLETED"},
                {"txn_id": "T1", "txn_date": "20240111", "partner": "A", "miles_redeemed": -1, "status": "COMPLETED"},
            ],
        }
    ]
    path = tmp_path / "r.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    good, rejected = flatten_redemptions(path)
    assert len(good) == 1
    assert len(rejected) == 1
    assert "DUPLICATE_TXN_ID" in rejected.iloc[0]["rejection_reason"]
    assert "INVALID_MILES_REDEEMED" in rejected.iloc[0]["rejection_reason"]
