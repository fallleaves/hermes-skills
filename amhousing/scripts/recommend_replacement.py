#!/usr/bin/env python3
"""
recommend_replacement.py — Query fixture specs for replacement recommendation.
Outputs structured data for the Agent to use with web_search.
"""
import sqlite3, json, sys, argparse

DB = "/home/jfeng/projects/amhousing/prisma/dev.db"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def find_fixture(house_id, query):
    """Find a fixture by search terms and return its full specs + room context."""
    con = get_db()
    q = f"%{query}%"
    row = con.execute("""
        SELECT rf.*, r.name as room_name, r.type as room_type,
               r.doorThickness, r.doorWidth, r.doorHeight, r.doorOpening,
               r.lockType, r.lockBackset, r.wallMaterial, r.ceilingType,
               r.floorType, r.hasFloorHeating
        FROM RoomFixture rf
        JOIN Room r ON rf.roomId = r.id
        WHERE r.houseId = ? AND (rf.name LIKE ? OR rf.type LIKE ? OR rf.brand LIKE ? OR rf.model LIKE ?)
        ORDER BY rf.roomId
        LIMIT 5
    """, (house_id, q, q, q, q)).fetchall()
    con.close()
    return [dict(r) for r in row]

def find_furniture(house_id, query):
    con = get_db(); q = f"%{query}%"
    rows = con.execute("""
        SELECT rf.*, r.name as room_name FROM RoomFurniture rf
        JOIN Room r ON rf.roomId = r.id
        WHERE r.houseId = ? AND (rf.name LIKE ? OR rf.brand LIKE ?)
        LIMIT 5
    """, (house_id, q, q)).fetchall()
    con.close(); return [dict(r) for r in rows]

def find_system(house_id, query):
    con = get_db(); q = f"%{query}%"
    rows = con.execute("""
        SELECT * FROM HouseSystem
        WHERE houseId = ? AND (name LIKE ? OR brand LIKE ? OR type LIKE ?)
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
