#!/usr/bin/env python3
"""
process_message.py — Read one unread HouseMessage, process it, write reply.

The Agent loads this script and reads its output to understand what happened.
"""
import sqlite3, json, sys, os, urllib.request
from datetime import datetime

DB = "/home/jfeng/projects/amhousing/prisma/dev.db"
# Internal API endpoint for SSE notification (amhousing runs on port 3001, localhost only)
INTERNAL_API = "http://127.0.0.1:3001/api/events/publish"

def get_db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def get_pending_message():
    """Get the oldest unprocessed message, or None."""
    con = get_db()
    msg = con.execute(
        "SELECT hm.*, ht.houseId, ht.userId FROM HouseMessage hm "
        "JOIN HouseThread ht ON hm.threadId = ht.id "
        "WHERE hm.processed = 0 AND hm.senderType = 'user' "
        "ORDER BY hm.createdAt ASC LIMIT 1"
    ).fetchone()
    con.close()
    return dict(msg) if msg else None

def get_house_context(house_id):
    """Get basic house info for context."""
    con = get_db()
    house = con.execute("SELECT id, address, city, postcode, bedrooms, bathrooms, area FROM House WHERE id = ?", (house_id,)).fetchone()
    rooms = con.execute("SELECT id, name, type FROM Room WHERE houseId = ?", (house_id,)).fetchall()
    fixtures = con.execute(
        "SELECT rf.type, rf.name, rf.brand, rf.model, r.name as room FROM RoomFixture rf JOIN Room r ON rf.roomId = r.id WHERE r.houseId = ?",
        (house_id,)
    ).fetchall()
    con.close()
    return {
        "house": dict(house) if house else None,
        "rooms": [dict(r) for r in rooms],
        "fixtures": [dict(r) for r in fixtures],
    }

def mark_processed(message_id):
    con = get_db()
    con.execute("UPDATE HouseMessage SET processed = 1 WHERE id = ?", (message_id,))
    con.commit()
    con.close()

def add_reply(thread_id, content, msg_type="text", event_id=None, confidence=None):
    con = get_db()
    now = datetime.utcnow()
    created_at = now.strftime('%Y-%m-%dT%H:%M:%S.') + f"{now.microsecond // 1000:03d}Z"
    con.execute(
        "INSERT INTO HouseMessage (id, threadId, senderType, type, content, eventId, confidence, processed, createdAt) "
        "VALUES (?, ?, 'agent', ?, ?, ?, ?, 1, ?)",
        (cuid(), thread_id, msg_type, content, event_id, confidence, created_at)
    )
    con.commit()

    # Notify user via SSE
    try:
        user = con.execute(
            "SELECT userId FROM HouseThread WHERE id = ?", (thread_id,)
        ).fetchone()
        if user:
            payload = json.dumps({
                "userId": user[0],
                "event": "house_thread_message",
                "data": {"threadId": thread_id}
            }).encode()
            req = urllib.request.Request(
                INTERNAL_API, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            urllib.request.urlopen(req, timeout=2)
    except Exception as e:
        print(f"[notify] SSE notification failed: {e}", file=sys.stderr)

    con.close()

def cuid():
    """Generate a simple unique ID."""
    import random, string
    return 'c' + ''.join(random.choices(string.ascii_letters + string.digits, k=24))

def backfill_file_user_ids(thread_id, user_id, file_ids):
    """Attribution fix: ensure HouseFile records linked to this message carry the
    thread user's userId (chat-channel uploads used to leave userId NULL, which
    surfaced as 'unattributed/system uploads' in the admin storage panel)."""
    if not file_ids:
        return 0
    con = get_db()
    ids = [fid for fid in file_ids if fid]
    if not ids:
        con.close()
        return 0
    placeholders = ",".join("?" * len(ids))
    con.execute(
        f"UPDATE HouseFile SET userId = COALESCE(userId, ?) WHERE id IN ({placeholders})",
        [user_id, *ids]
    )
    con.commit()
    n = con.total_changes
    con.close()
    return n

def extract_file_ids(msg):
    """Parse fileUrls JSON into a list of file IDs, if any."""
    try:
        urls = json.loads(msg.get("fileUrls") or "[]")
        return [u.get("id") for u in urls if isinstance(u, dict) and u.get("id")]
    except Exception:
        return []

def main():
    msg = get_pending_message()
    if not msg:
        json.dump({"status": "no_pending_messages"}, sys.stdout, indent=2)
        return
    
    context = get_house_context(msg["houseId"])
    
    # Attribution fix: backfill userId on any HouseFile linked to this message
    # (chat uploads used to leave userId NULL → showed as "system uploads")
    file_ids = extract_file_ids(msg)
    if file_ids and msg.get("userId"):
        try:
            n = backfill_file_user_ids(msg["threadId"], msg["userId"], file_ids)
            if n:
                print(f"[attribution] backfilled userId on {n} HouseFile(s)", file=sys.stderr)
        except Exception as e:
            print(f"[attribution] backfill failed: {e}", file=sys.stderr)
    
    # Return everything the Agent needs to analyze
    output = {
        "status": "message_found",
        "message": {
            "id": msg["id"],
            "content": msg["content"],
            "type": msg["type"],
            "createdAt": msg["createdAt"],
            "fileUrls": msg["fileUrls"],
        },
        "house": context["house"],
        "rooms": context["rooms"],
        "existing_fixtures": context["fixtures"],
        "instruction": """Analyze the message content against the house context above.
Determine the user's intent:
- extract: receipt/photo → write to RoomFixture/Furniture/System/Item
- update: replacement/repair → update existing fixture (dedup by room+type)
- query: asking for info → search DB and reply
- recommend: asking for replacement → search specs + web_search

IMPORTANT — amount unit: 
  - **HouseLedgerEntry.amount** is stored in **cents** (分). 
    e.g. €3300 → amount=330000, €69.50 → amount=6950
    The frontend divides by 100 when displaying.
  - **Listing.price** and **Lease.monthlyRent** are stored in **euros** (元).
    e.g. €3450 → price=3450 (NOT 345000).
    Do NOT multiply these by 100.

IMPORTANT — ledger entry type: use **"INCOME"** for money received,
  **"EXPENSE"** for money paid. Do NOT use values like "rent_income"
  or "payment" — the API only recognizes these two exact uppercase
  values. Wrong type causes the entry to appear as a negative expense
  instead of positive income.

IMPORTANT — file linking: the message may include fileUrls with file IDs.
  fileUrls format: [{"id":"file_xxx","url":"/api/files/xxx"}, ...]
  The file is already saved to disk and a HouseFile record created.
  
  To make it traceable, create a HouseEvent and link the file:
  1. Parse file IDs from message.fileUrls
  2. INSERT INTO HouseEvent (id, houseId, type, title, occurredAt, createdAt)
     VALUES (cuid(), houseId, 'NOTE', '上传平面图', datetime('now'), datetime('now'))
  3. UPDATE HouseFile SET eventId = ? WHERE id IN (fileId1, fileId2, ...)
  4. If it belongs to a specific room, also set roomId on HouseFile:
     UPDATE HouseFile SET roomId = ? WHERE id = ?

  This ensures every uploaded file is linked to a traceable event.

IMPORTANT — NEVER delete old files or old records when user replaces an image.
  Old files are historical records and must be preserved.
  When the user says "用新图片替换旧图片" or similar:
  1. Upload the new file (already done by the client)
  2. Create a NEW event for the replacement: "更新照片 — 次卧窗帘"
  3. Link the new file to the new event via eventId
  4. Reply confirming the update
  5. Do NOT delete the old file, old event, or old HouseFile record

Reply with JSON: {intent, target_model, fields: {...}, confidence: 0-1, reply_message: "..."}

Then use upsert_fixture.py to write, and INSERT HouseMessage for reply."""
    }
    
    # Mark as processed (even though the agent hasn't replied yet — 
    # the reply will be a separate message)
    mark_processed(msg["id"])
    
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2, default=str)

if __name__ == "__main__":
    main()
