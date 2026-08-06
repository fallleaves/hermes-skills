#!/usr/bin/env python3
"""upsert_fixture.py — Deduplicate and write RoomFixture with version tracking."""
import sqlite3, json, sys, math
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
    M-A2 bug class). Integers pass through; ISO-8601 strings convert.
    r18-n1: unparseable strings return None instead of crashing the whole
    upsert with a ValueError traceback (plausible LLM outputs like
    'January 15, 2026'), mirroring maintenance_scan.parse_dt's graceful
    degradation."""
    if value is None:
        return None
    if isinstance(value, bool):
        # r18-n1: bool is an int subclass — True would become 1ms
        # (1970-01-01T00:00:00.001), a garbage warranty date
        return None
    if isinstance(value, (int, float)):
        # r25-n2: NaN/±Infinity floats reach this branch from crafted
        # stdin (json.loads accepts the NaN/Infinity literals) — int(NaN)
        # raises ValueError and int(inf) OverflowError, crashing the whole
        # upsert with a traceback instead of the graceful-None contract
        if isinstance(value, float) and not math.isfinite(value):
            return None
        # r26-m1: magnitude guard — a finite 1e30 passes int() but crashes
        # the very next sqlite bind (OverflowError: Python int too large
        # to convert to SQLite INTEGER), and bindable-but-absurd values
        # (1e18 ms ≈ year 31M) crash the weekly cron readers
        # (ValueError: year out of range). 8.64e15 ms ≈ year 275760 — a
        # sane DateTime ceiling.
        # r28-n3: the negative end is garbage too — a pre-1970 warranty/
        # purchase date is always a mistake (LLM-computed epochs), and
        # it gets flagged long-expired by the warranty scans
        if not 0 <= value <= 8_640_000_000_000_000:
            return None
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            # r19-n1: a Z-less ISO string yields a NAIVE datetime, and
            # timestamp() would interpret it in LOCAL time — the DB stores
            # UTC ms, so bare strings mean UTC (parse_dt parity)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass
        # r18-n1: parse_dt fallbacks — the DB's TEXT formats still
        # convert; anything else degrades to None (clean no-op, never a
        # traceback, and the agent still gets its JSON summary)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                # strptime always yields naive — same UTC contract
                dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        return None
    return None

def normalize_purchase_price(value):
    """r26-n2: purchasePrice is a Prisma 32-bit Int column — a float,
    numeric string or oversized int bound raw would silently drift the
    column to REAL/TEXT/overflow (SQLite dynamic typing). Accept only
    in-range integers (int, or integer-valued finite floats); anything
    else — fractions, strings, bools, out-of-range — degrades to None,
    honoring the graceful-degradation contract."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 2**31 - 1 else None
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        return int(value) if 0 <= value <= 2**31 - 1 else None
    return None  # strings and anything else are rejected


def upsert(room_id, fixture_type, name, category=None, brand=None, model=None,
           serial_number=None, material=None, color=None, dimensions=None,
           mount_specs=None, purchase_price=None, supplier=None,
           warranty_expiry=None, condition=None, notes=None, images=None,
           confidence=None):
    """Find existing fixture or create new. Returns (action, fixture_dict)."""
    warranty_expiry = normalize_datetime(warranty_expiry)
    purchase_price = normalize_purchase_price(purchase_price)
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
        # M1: the camelCase DB field names are looked up in locals(), but
        # the Python params are snake_case — purchasePrice/warrantyExpiry
        # resolved to None and those edits were STILL silently dropped
        # (only supplier landed). Map every non-identical field explicitly.
        FIELD_TO_PARAM = {
            'serialNumber': 'serial_number',
            'mountSpecs': 'mount_specs',
            'purchasePrice': 'purchase_price',
            'warrantyExpiry': 'warranty_expiry',
        }
        for field in ['name', 'category', 'brand', 'model', 'serialNumber', 'material', 'color',
                       'dimensions', 'mountSpecs', 'condition', 'notes', 'images',
                       'purchasePrice', 'supplier', 'warrantyExpiry']:
            val = locals().get(FIELD_TO_PARAM.get(field, field))
            if val is None:
                continue
            # n7-2: sqlite3 cannot bind a list/dict — serialize objects
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            # r20-m2: only write fields that actually CHANGED. `name` is a
            # REQUIRED upsert() param, so adding it to the loop without
            # this check made every call (even a true no-op) report
            # "updated" — the honest "unchanged" path must survive.
            if old.get(field) == val:
                continue
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
            # r12-n1: confidence on the UPDATE path was silently dropped —
            # record it in the version snapshot like the create path
            snapshot = json.dumps(old, default=str)
            if confidence is not None:
                snapshot = json.dumps({**old, "confidence": confidence}, default=str)
            con.execute(
                "INSERT INTO RoomFixtureVersion (id, fixtureId, snapshot, source, createdAt) VALUES (?, ?, ?, 'agent_extraction', ?)",
                (cuid(), old['id'], snapshot, ts)
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
        # r11-n4: confidence was accepted but silently dropped — record it
        # in the initial version snapshot so the caller's value lands
        initial_snapshot = (
            json.dumps({"confidence": confidence}, default=str)
            if confidence is not None else "{}"
        )
        con.execute(
            "INSERT INTO RoomFixtureVersion (id, fixtureId, snapshot, source, createdAt) VALUES (?, ?, ?, 'agent_extraction', ?)",
            (cuid(), fid, initial_snapshot, ts)
        )
        con.commit()
        new_fixture = dict(con.execute("SELECT * FROM RoomFixture WHERE id = ?", (fid,)).fetchone())
        con.close()
        return ("created", new_fixture)

def main():
    # r26-n1: the stdin entrypoint must never die with a raw traceback —
    # unknown kwargs (TypeError), empty/non-JSON stdin (EOFError/
    # JSONDecodeError) and array stdin (TypeError) all exit cleanly with
    # a structured JSON error, honoring the r18-n1 graceful contract
    # (the argparse siblings already do this).
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError("stdin must be a JSON object of upsert() kwargs")
        result = upsert(**data)
        # r27-n2: the success path carries ok: true — the r26-n1 error
        # shape ({"ok": false, ...}) made a caller that gates on
        # payload.get("ok") misread every success as a failure
        json.dump({"ok": True, "action": result[0], "fixture": result[1]},
                  sys.stdout, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        json.dump({"ok": False, "error": str(e)}, sys.stdout)
        sys.exit(1)

if __name__ == "__main__":
    main()
