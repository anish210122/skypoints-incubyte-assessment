import sqlite3
import json
from datetime import datetime, date
import pandas as pd

DB_NAME = "skypoints.db"

def parse_flexible_date(val):
    """Parses ambiguous dates (integers, strings, standard ISO, MMDDYYYY). Returns YYYY-MM-DD or None."""
    if pd.isna(val) or val is None or str(val).strip() == "" or str(val).strip().upper() == "NAT":
        return None
    
    val_str = str(val).split()[0].strip()
    
    # Handle numeric MMDDYYYY representations like 6152022 or 1052022
    if val_str.isdigit() and len(val_str) in [7, 8]:
        val_str = val_str.zfill(8)
        try:
            return datetime.strptime(val_str, "%m%d%Y").date().strftime("%Y-%m-%d")
        except ValueError:
            pass

    formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d", "%m%d%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(val_str, fmt).date().strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def compute_age(dob_str, ref_date=None):
    """Calculates integer age accurately from YYYY-MM-DD string."""
    if not dob_str:
        return None
    if ref_date is None:
        ref_date = date.today()
    try:
        born = datetime.strptime(dob_str, "%Y-%m-%d").date()
        return ref_date.year - born.year - ((ref_date.month, ref_date.day) < (born.month, born.day))
    except Exception:
        return None

def compute_stale_flag(flight_date_str, ref_date=None):
    """Returns 1 (stale) if flight date is missing or > 90 days prior, else 0."""
    if not flight_date_str:
        return 1
    if ref_date is None:
        ref_date = date.today()
    try:
        flight_dt = datetime.strptime(flight_date_str, "%Y-%m-%d").date()
        diff_days = (ref_date - flight_dt).days
        return 1 if diff_days > 90 else 0
    except Exception:
        return 1

def run_pipeline():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Execute DDL schemas
    with open("sql/01_ddl_tables.sql", "r", encoding="utf-8-sig") as f:
        cursor.executescript(f.read())

    # 2. Sample records simulating landing feed
    raw_profiles = [
        {"member_id": "223457", "member_name": "Elena", "enrollment_date": "20101012", "flight_date": "20240113", "tier_code": "GLD", "agent_name": "Sam", "state": "CA", "country": "USA", "post_code": "90001", "dob": "03051985", "is_active": "A"},
        {"member_id": "223458", "member_name": "Ravi", "enrollment_date": "20101012", "flight_date": "20121013", "tier_code": "SLV", "agent_name": "Sam", "state": "TN", "country": "IND", "post_code": "60001", "dob": "3051985", "is_active": "A"},
        {"member_id": "2256", "member_name": "Jacob", "enrollment_date": "20101012", "flight_date": "20240210", "tier_code": "SLV", "agent_name": "Sam", "state": "VIC", "country": "AUS", "post_code": "3000", "dob": "03051985", "is_active": "A"},
        # Ravi moves from IND to USA with a more recent flight date
        {"member_id": "223458", "member_name": "Ravi", "enrollment_date": "20101012", "flight_date": "20240215", "tier_code": "GLD", "agent_name": "Sam", "state": "NY", "country": "USA", "post_code": "10001", "dob": "03051985", "is_active": "A"}
    ]

    staged_records = []
    ref_dt = date(2024, 3, 1)

    for r in raw_profiles:
        enroll_dt = parse_flexible_date(r["enrollment_date"])
        flight_dt = parse_flexible_date(r["flight_date"])
        dob_dt = parse_flexible_date(r["dob"])
        age = compute_age(dob_dt, ref_date=ref_dt)
        stale = compute_stale_flag(flight_dt, ref_date=ref_dt)

        staged_records.append({
            "member_id": r["member_id"],
            "member_name": r["member_name"],
            "enrollment_date": enroll_dt,
            "flight_date": flight_dt,
            "tier_code": r["tier_code"],
            "agent_name": r.get("agent_name"),
            "state": r.get("state"),
            "country": r["country"].strip().upper(),
            "post_code": r.get("post_code"),
            "dob": dob_dt,
            "age": age,
            "is_stale_member": stale,
            "is_active": r.get("is_active", "A")
        })

    # Deliverable 3: Apply Latest Record Wins (Order by flight_date desc, deduplicate by member_id)
    df_stg = pd.DataFrame(staged_records)
    df_stg.sort_values(by=["flight_date", "enrollment_date"], ascending=[False, False], inplace=True)
    df_stg.drop_duplicates(subset=["member_id"], keep="first", inplace=True)

    df_stg.to_sql("stg_member_profiles", conn, if_exists="replace", index=False)

    # Route members to country tables
    country_table_map = {
        "USA": "table_usa",
        "IND": "table_ind",
        "AUS": "table_aus"
    }

    for country, tbl_name in country_table_map.items():
        cursor.execute(f"DELETE FROM {tbl_name}")
        country_slice = df_stg[df_stg["country"] == country]
        country_slice.to_sql(tbl_name, conn, if_exists="append", index=False)

    # Deliverable 4: Parse & Flatten JSON Redemptions
    with open("data/redemptions.json", "r") as jf:
        json_data = json.load(jf)

    flattened_txns = []
    for entry in json_data:
        m_id = entry.get("member_id")
        feed_dt = parse_flexible_date(entry.get("feed_date"))
        for txn in entry.get("redemptions", []):
            flattened_txns.append({
                "txn_id": txn.get("txn_id"),
                "member_id": m_id,
                "feed_date": feed_dt,
                "txn_date": parse_flexible_date(txn.get("txn_date")),
                "partner": txn.get("partner"),
                "miles_redeemed": txn.get("miles_redeemed"),
                "status": txn.get("status")
            })

    df_redemptions = pd.DataFrame(flattened_txns)
    df_redemptions.to_sql("fct_member_redemptions", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print("ETL pipeline executed successfully.")

if __name__ == "__main__":
    run_pipeline()
