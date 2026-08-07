#!/usr/bin/env python3
"""query_house.py — Query AM Housing DB."""
import os
import sys
import sqlite3, json, sys, argparse
from datetime import datetime, timedelta, timezone

DB = "/home/jfeng/projects/amhousing/prisma/amhousing.db"

def get_db():
    # r76-n4: F-037 parity (process_message.py) — a missing/0-byte path must
    # refuse; sqlite3.connect would CREATE a phantom empty DB and the script
    # would die with a raw "no such table" traceback (or a misleading
    # "not found"), and the phantom would shadow the real DB for later runs
    if not os.path.exists(DB) or os.path.getsize(DB) == 0:
        print(f"[{__file__.split('/')[-1]}] refusing to open missing/0-byte database: {DB}", file=sys.stderr)
        sys.exit(1)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def escape_like(q):
    """r10-n2: a literal %/_/\\ in the agent's query acted as LIKE wildcards
    and matched EVERY row — escape them (the app routes' n7-5 pattern)."""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

def search(house_id, query):
    con = get_db(); q = f"%{escape_like(query)}%"; results = []
    for table, cols in [("RoomFixture", "rf.name LIKE ? ESCAPE '\\' OR rf.brand LIKE ? ESCAPE '\\' OR rf.model LIKE ? ESCAPE '\\' OR rf.type LIKE ? ESCAPE '\\'"),
                         ("RoomFurniture", "rf.name LIKE ? ESCAPE '\\' OR rf.brand LIKE ? ESCAPE '\\' OR rf.model LIKE ? ESCAPE '\\'")]:
        rows = con.execute(f"SELECT rf.*, r.name as room FROM {table} rf JOIN Room r ON rf.roomId=r.id WHERE r.houseId=? AND ({cols}) LIMIT 20",
                          (house_id, q, q, q, q) if "type" in cols else (house_id, q, q, q)).fetchall()
        results.extend([dict(r) for r in rows])
    rows = con.execute("SELECT * FROM HouseSystem WHERE houseId=? AND (name LIKE ? ESCAPE '\\' OR brand LIKE ? ESCAPE '\\') LIMIT 10",
                       (house_id, q, q)).fetchall()
    results.extend([dict(r) for r in rows])
    con.close(); return results

def scan_warranties(house_id):
    con = get_db(); alerts = []
    # r43-n1: the warranty epochs are UTC-normalized (epoch_expr below) —
    # the comparison side must be aware-UTC too; a naive-local now()
    # diverges by the UTC offset on any non-UTC host (r19-n1 class; every
    # sibling script uses datetime.now(timezone.utc))
    six_months_ts = (datetime.now(timezone.utc) + timedelta(days=180)).timestamp()
    # M-A2/m-D3: warrantyExpiry is INTEGER Unix-ms since the backfill —
    # comparing an INTEGER against a TEXT date literal is ALWAYS true in
    # SQLite (storage-class ordering), which flagged EVERY fixture as
    # expiring (even warranties valid until 2040). Normalize both sides to
    # epoch seconds like cleanup_orphan_files.epoch_expr.
    epoch_expr = (
        "CASE WHEN typeof(rf.warrantyExpiry) = 'integer' "
        "THEN rf.warrantyExpiry/1000.0 "
        "ELSE (julianday(rf.warrantyExpiry)-2440587.5)*86400.0 END"
    )
    rows = con.execute(f"""SELECT rf.name, rf.type, rf.brand, rf.warrantyExpiry, r.name as room
        FROM RoomFixture rf JOIN Room r ON rf.roomId=r.id
        WHERE r.houseId=? AND rf.warrantyExpiry IS NOT NULL AND {epoch_expr} <= ?""",
        (house_id, six_months_ts)).fetchall()
    for r in rows:
        d = dict(r)
        raw = d['warrantyExpiry']
        # normalize the reported expiry to a readable date (INTEGER ms or TEXT)
        # r26-m1: an absurd stored ms value (1e18 ≈ year 31M) raised
        # ValueError from fromtimestamp — degrade to the raw digits rather
        # than taking down the agent's warranty query
        if isinstance(raw, (int, float)):
            try:
                # r49-n1: aware-UTC display — naive-local fromtimestamp
                # prints the LOCAL calendar date of a UTC instant (r43-n1
                # fixed the scan boundary; the epoch_expr side is UTC)
                expiry = datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            except (ValueError, OverflowError, OSError):
                expiry = str(raw)[:10]
        else:
            expiry = str(raw)[:10]
        alerts.append({"item": f"{d['name']} ({d['brand']})", "room": d['room'], "expiry": expiry})
    con.close(); return alerts

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--house-id", required=True)
    p.add_argument("--query"); p.add_argument("--scan-warranties", action="store_true")
    args = p.parse_args()
    result = {}
    if args.query: result["search"] = search(args.house_id, args.query)
    if args.scan_warranties: result["alerts"] = scan_warranties(args.house_id)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)

if __name__ == "__main__": main()
