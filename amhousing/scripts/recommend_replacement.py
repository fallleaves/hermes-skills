#!/usr/bin/env python3
"""
recommend_replacement.py — Query fixture specs for replacement recommendation.
Outputs structured data for the Agent to use with web_search.
"""
import os
import sys
import sqlite3, json, sys, argparse

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

def find_fixture(house_id, query):
    """Find a fixture by search terms and return its full specs + room context."""
    con = get_db()
    q = f"%{escape_like(query)}%"
    row = con.execute("""
        SELECT rf.*, r.name as room_name, r.type as room_type,
               r.doorThickness, r.doorWidth, r.doorHeight, r.doorOpening,
               r.lockType, r.lockBackset, r.wallMaterial, r.ceilingType,
               r.floorType, r.hasFloorHeating
        FROM RoomFixture rf
        JOIN Room r ON rf.roomId = r.id
        WHERE r.houseId = ? AND (rf.name LIKE ? ESCAPE '\\' OR rf.type LIKE ? ESCAPE '\\' OR rf.brand LIKE ? ESCAPE '\\' OR rf.model LIKE ? ESCAPE '\\')
        ORDER BY rf.roomId
        LIMIT 5
    """, (house_id, q, q, q, q)).fetchall()
    con.close()
    return [dict(r) for r in row]

def find_furniture(house_id, query):
    con = get_db(); q = f"%{escape_like(query)}%"
    rows = con.execute("""
        SELECT rf.*, r.name as room_name FROM RoomFurniture rf
        JOIN Room r ON rf.roomId = r.id
        WHERE r.houseId = ? AND (rf.name LIKE ? ESCAPE '\\' OR rf.brand LIKE ? ESCAPE '\\')
        LIMIT 5
    """, (house_id, q, q)).fetchall()
    con.close(); return [dict(r) for r in rows]

def find_system(house_id, query):
    con = get_db(); q = f"%{escape_like(query)}%"
    rows = con.execute("""
        SELECT * FROM HouseSystem
        WHERE houseId = ? AND (name LIKE ? ESCAPE '\\' OR brand LIKE ? ESCAPE '\\' OR type LIKE ? ESCAPE '\\')
        LIMIT 5
    """, (house_id, q, q, q)).fetchall()
    con.close(); return [dict(r) for r in rows]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--house-id", required=True)
    p.add_argument("--query", required=True)
    args = p.parse_args()

    fixtures = find_fixture(args.house_id, args.query)
    furniture = find_furniture(args.house_id, args.query)
    systems = find_system(args.house_id, args.query)

    results = {
        "fixtures": fixtures,
        "furniture": furniture,
        "systems": systems,
        "search_instructions": """
For each item found above, the Agent should:
1. Read the 'brand', 'model', 'mountSpecs' (JSON), and 'dimensions' (JSON) fields
2. web_search for: "{brand} {model} replacement compatible"
3. web_search for alternatives if discontinued
4. Compare key compatibility parameters from mountSpecs against candidate specs
5. Present top 3 recommendations with: brand, model, compatibility notes, price estimate, purchase link
"""
    }

    json.dump(results, sys.stdout, ensure_ascii=False, indent=2, default=str)

if __name__ == "__main__":
    main()
