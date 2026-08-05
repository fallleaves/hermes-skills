#!/usr/bin/env python3
"""upsert_fixture.py — Deduplicate and write RoomFixture with version tracking."""
import sqlite3, json, sys
from datetime import datetime, timezone

DB = "/home/jfeng/projects/amhousing/prisma/amhousing.db"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def now_iso():
    # m-C6: INTEGER Unix-ms — Prisma's native DateTime format (M-A2).
    # TEXT ISO dates reintroduce mixed storage classes that break Prisma
    # cursor comparisons and ordering on Prisma-read tables.
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def cuid():
    import random, string
    return 'c' + ''.join(random.choices(string.ascii_letters + string.digits, k=24))

def normalize_datetime(value):
    """n-D6: DateTime params must land as INTEGER Unix-ms (M-A2) — a TEXT
    ISO value from the agent would reintroduce mixed storage classes on
    Prisma-read columns (breaking ordering/pagination, the original
    M-A2 bug class). Integers pass through; ISO-8601 strings convert."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(dt.timestamp() * 1000)
    return None

def upsert(room_id, fixture_type, name, category=None, brand=None, model=None,
           serial_number=None, material=None, color=None, dimensions=None,
           mount_specs=None, purchase_price=None, supplier=None,
           warranty_expiry=None, condition=None, notes=None, images=None,
           confidence=None):
    """Find existing fixture or create new. Returns (action, fixture_dict)."""
    warranty_expiry = normalize_datetime(warranty_expiry)
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
        # m4: purchasePrice/supplier/warrantyExpiry were missing here — the
        # agent's price/warranty edits were reported as 'updated' but never
        # landed on existing fixtures
        for field in ['brand', 'model', 'serialNumber', 'material', 'color',
                       'dimensions', 'mountSpecs', 'condition', 'notes', 'images',
                       'purchasePrice', 'supplier', 'warrantyExpiry']:
            val = locals().get(field.replace('serialNumber', 'serial_number')
                               .replace('mountSpecs', 'mount_specs'))
            if val is not None:
                # n7-2: sqlite3 cannot bind a list/dict — serialize objects
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                updates[field] = val
        if updates:
            # n7-1: raw SQL bypasses Prisma's @updatedAt — keep the column
            # honest for agent-touched rows
            updates['updatedAt'] = now_iso()
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
        # n7-2: serialize list/dict values (images, mountSpecs, notes, ...)
        # before binding — sqlite3 raises InterfaceError otherwise
        def _bind(v):
            return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v
        con.execute("""
            INSERT INTO RoomFixture (id, roomId, category, type, name, brand, model,
                serialNumber, material, color, dimensions, mountSpecs, condition,
                notes, images, purchasePrice, supplier, warrantyExpiry, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fid, room_id, category or "unknown", fixture_type, name or fixture_type,
              brand, model, serial_number, _bind(material), _bind(color), _bind(dimensions),
              _bind(mount_specs), condition, _bind(notes), _bind(images),
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
