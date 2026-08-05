#!/usr/bin/env python3
"""
export_house.py — Export all details for a house as structured JSON.
Usage: python3 export_house.py --house-id <id> [--format json|text]
"""
import sqlite3, json, sys, argparse

DB = "/home/jfeng/projects/amhousing/prisma/amhousing.db"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def export(house_id):
    con = get_db()
    
    # House basic info
    row = con.execute("SELECT * FROM House WHERE id = ?", (house_id,)).fetchone()
    if row is None:
        # m5: a nonexistent house-id used to crash with dict(None) — a
        # clean error is far more useful for the agent
        return {"error": f"House {house_id} not found"}
    house = dict(row)
    del house['images']
    del house['ownerId']
    
    # Rooms with details
    rooms = []
    for room in con.execute("SELECT * FROM Room WHERE houseId = ? ORDER BY floor, name", (house_id,)).fetchall():
        r = dict(room)
        
        # Windows
        r['windows'] = [dict(w) for w in con.execute(
            "SELECT * FROM RoomWindow WHERE roomId = ?", (r['id'],)).fetchall()]
        
        # Fixtures
        r['fixtures'] = [dict(f) for f in con.execute(
            "SELECT * FROM RoomFixture WHERE roomId = ? ORDER BY category, type", (r['id'],)).fetchall()]
        
        # Furniture
        r['furniture'] = [dict(f) for f in con.execute(
            "SELECT * FROM RoomFurniture WHERE roomId = ? ORDER BY type", (r['id'],)).fetchall()]
        
        rooms.append(r)
    
    # Systems
    systems = [dict(s) for s in con.execute(
        "SELECT * FROM HouseSystem WHERE houseId = ? ORDER BY type", (house_id,)).fetchall()]
    
    # Outdoor spaces
    outdoor = [dict(o) for o in con.execute(
        "SELECT * FROM OutdoorSpace WHERE houseId = ?", (house_id,)).fetchall()]
    
    # Items (catch-all)
    items = [dict(i) for i in con.execute(
        "SELECT * FROM Item WHERE houseId = ? ORDER BY category", (house_id,)).fetchall()]
    
    # Stats
    stats = {
        "total_rooms": len(rooms),
        "total_fixtures": sum(len(r['fixtures']) for r in rooms),
        "total_furniture": sum(len(r['furniture']) for r in rooms),
        "total_windows": sum(len(r['windows']) for r in rooms),
        "total_systems": len(systems),
        "total_outdoor_spaces": len(outdoor),
        "total_items": len(items),
    }
    
    con.close()
    
    return {
        "house": house,
        "rooms": rooms,
        "systems": systems,
        "outdoor_spaces": outdoor,
        "items": items,
        "stats": stats,
    }

def format_text(data):
    """Format as readable text for Agent to display."""
    lines = []
    h = data['house']
    lines.append(f"🏠 {h['address']}, {h['postcode']} {h['city']}")
    lines.append(f"   {h['bedrooms']} 卧室 | {h['bathrooms']} 浴室 | {h['area']}m²")
    if h.get('buildingType'): lines.append(f"   类型: {h['buildingType']} | 建造: {h.get('yearBuilt', '?')}")
    lines.append("")
    
    lines.append(f"📊 统计: {data['stats']['total_rooms']} 房间, {data['stats']['total_fixtures']} 装置, {data['stats']['total_furniture']} 家具, {data['stats']['total_systems']} 设备系统")
    lines.append("")
    
    for room in data['rooms']:
        lines.append(f"📍 {room['name']} ({room['type']}) — {room.get('area', '?')}m²")
        if room.get('floorType'): lines.append(f"   地面: {room['floorType']} {room.get('floorMaterial','')} {room.get('floorColorCode','')}".rstrip())
        if room.get('wallPaintColor'): lines.append(f"   墙面: {room['wallPaintColor']} ({room.get('wallPaintCode','')})")
        for f in room['fixtures']:
            lines.append(f"   🔧 {f['name']}: {f.get('brand','')} {f.get('model','')}".rstrip())
        for f in room['furniture']:
            lines.append(f"   🪑 {f['name']}: {f.get('brand','')} {f.get('model','')}".rstrip())
        lines.append("")
    
    for s in data['systems']:
        lines.append(f"⚙️ {s['name']} ({s['type']}): {s.get('brand','')} {s.get('model','')}".rstrip())
    
    return "\n".join(lines)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--house-id", required=True)
    p.add_argument("--format", default="json")
    args = p.parse_args()
    
    data = export(args.house_id)
    if isinstance(data, dict) and "error" in data:
        # m5: one clean JSON document for the agent
        json.dump(data, sys.stdout, ensure_ascii=False)
        return
    
    if args.format == "text":
        print(format_text(data))
    else:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2, default=str)

if __name__ == "__main__":
    main()
