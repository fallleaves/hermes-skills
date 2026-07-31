#!/usr/bin/env python3
"""upsert_fixture.py — Deduplicate and write RoomFixture with version tracking."""
import sqlite3, json, sys
from datetime import datetime, timezone

DB = "/home/jfeng/projects/amhousing/prisma/dev.db"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def now_iso():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"

def cuid():
    import random, string
    return 'c' + ''.join(random.choices(string.ascii_letters + string.digits, k=24))

def upsert(room_id, fixture_type, name, category=None, brand=None, model=None,
           serial_number=None, material=None, color=None, dimensions=None,
           mount_specs=None, purchase_price=None, supplier=None,
           warranty_expiry=None, condition=None, notes=None, images=None,
           confidence=None):
    """Find existing fixture or create new. Returns (action, fixture_dict)."""
    con = get_db()
    
    # Look for existing fixture of same type in same room
    existing = con.execute(
        "SELECT * FROM RoomFixture WHERE roomId = ? AND type = ? ORDER BY createdAt DESC LIMIT 1",
        (room_id, fixture_type)
    ).fetchone()
    
    if existing:
        old = dict(existing)
        # Update
        updates = {}
        for field in ['brand', 'model', 'serialNumber', 'material', 'color',
                       'dimensions', 'mountSpecs', 'condition', 'notes', 'images']:
            val = locals().get(field.replace('serialNumber', 'serial_number')
                               .replace('mountSpecs', 'mount_specs'))
            if val is not None:
                updates[field] = val
        if updates:
            updates['previousState'] = json.dumps(old, default=str)
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            con.execute(
                f"UPDATE RoomFixture SET {set_clause} WHERE id = ?",
                list(updates.values()) + [old['id']]
            )
            # Save version snapshot
            ts = now_iso()
            con.execute(
                "INSERT INTO RoomFixtureVersion (id, fixtureId, snapshot, source, createdAt) VALUES (?, ?, ?, 'agent_extraction', ?)",
                (cuid(), old['id'], json.dumps(old, default=str), ts)
            )
            con.commit()
            updated = dict(con.execute("SELECT * FROM RoomFixture WHERE id = ?", (old['id'],)).fetchone())
            con.close()
            return ("updated", updated)
        else:
            con.close()
            return ("unchanged", old)
    else:
        # Create new
        fid = cuid()
        ts = now_iso()
        con.execute("""
            INSERT INTO RoomFixture (id, roomId, category, type, name, brand, model,
                serialNumber, material, color, dimensions, mountSpecs, condition,
                notes, images, purchasePrice, supplier, warrantyExpiry, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fid, room_id, category or "unknown", fixture_type, name or fixture_type,
              brand, model, serial_number, material, color, dimensions,
              mount_specs, condition, notes, images,
              purchase_price, supplier, warranty_expiry, ts, ts))
        # Create initial version
        con.execute(
            "INSERT INTO RoomFixtureVersion (id, fixtureId, snapshot, source, createdAt) VALUES (?, ?, '{}', 'agent_extraction', ?)",
            (cuid(), fid, ts)
        )
        con.commit()
        new_fixture = dict(con.execute("SELECT * FROM RoomFixture WHERE id = ?", (fid,)).fetchone())
        con.close()
        return ("created", new_fixture)

if __name__ == "__main__":
    data = json.load(sys.stdin)
    result = upsert(**data)
    json.dump({"action": result[0], "fixture": result[1]}, sys.stdout, ensure_ascii=False, indent=2, default=str)
