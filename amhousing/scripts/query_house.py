#!/usr/bin/env python3
"""query_house.py — Query AM Housing DB."""
import sqlite3, json, sys, argparse
from datetime import datetime, timedelta

DB = "/home/jfeng/projects/amhousing/prisma/dev.db"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def search(house_id, query):
    con = get_db(); q = f"%{query}%"; results = []
    for table, cols in [("RoomFixture", "rf.name LIKE ? OR rf.brand LIKE ? OR rf.model LIKE ? OR rf.type LIKE ?"),
                         ("RoomFurniture", "rf.name LIKE ? OR rf.brand LIKE ? OR rf.model LIKE ?")]:
        rows = con.execute(f"SELECT rf.*, r.name as room FROM {table} rf JOIN Room r ON rf.roomId=r.id WHERE r.houseId=? AND ({cols}) LIMIT 20",
                          (house_id, q, q, q, q) if "type" in cols else (house_id, q, q, q)).fetchall()
        results.extend([dict(r) for r in rows])
    rows = con.execute("SELECT * FROM HouseSystem WHERE houseId=? AND (name LIKE ? OR brand LIKE ?) LIMIT 10",
                       (house_id, q, q)).fetchall()
    results.extend([dict(r) for r in rows])
    con.close(); return results

def scan_warranties(house_id):
    con = get_db(); alerts = []
    six_months = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
    rows = con.execute("""SELECT rf.name, rf.type, rf.brand, rf.warrantyExpiry, r.name as room
        FROM RoomFixture rf JOIN Room r ON rf.roomId=r.id
        WHERE r.houseId=? AND rf.warrantyExpiry IS NOT NULL AND rf.warrantyExpiry <= ?""",
        (house_id, six_months)).fetchall()
    for r in rows:
        d = dict(r)
        alerts.append({"item": f"{d['name']} ({d['brand']})", "room": d['room'], "expiry": d['warrantyExpiry']})
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
