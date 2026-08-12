#!/usr/bin/env python3
"""
write_pending.py — Record a low-confidence finding as a PendingConfirmation
and notify the house owner in real time (SSE).

The Agent calls this when it extracted information with confidence < 0.6
(or when the new value conflicts with an existing record): instead of
writing straight to the target model, the proposal is parked for the
landlord to approve/reject in the UI (my-houses/[id]/pending).

Usage:
  python3 write_pending.py \
    --house-id <houseId> \
    --target-model RoomFixture \
    --target-id <fixtureId> \
    --confidence 0.45 \
    --proposed-data '{"condition":"fair","notes":"scratched"}' \
    [--conflict-field condition] [--existing-value '{"condition":"good"}'] \
    [--source-event-id <eventId>]

Exit code 0 on success, 1 on failure. Prints a JSON summary on stdout.
"""
import argparse
import json
import random
import os
import sqlite3
import string
import sys
import urllib.request
from datetime import datetime, timezone

DB = "/home/jfeng/projects/amhousing/prisma/amhousing.db"
INTERNAL_API = "http://127.0.0.1:3001/api/events/publish"


def get_internal_api_key():
    """Read INTERNAL_API_KEY from the amhousing .env file."""
    try:
        with open("/home/jfeng/projects/amhousing/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("INTERNAL_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    return ""


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


def now_iso():
    # m-C6: INTEGER Unix-ms — Prisma's native DateTime format (M-A2).
    # TEXT ISO dates reintroduce mixed storage classes that break Prisma
    # cursor comparisons and ordering on Prisma-read tables.
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def cuid():
    return "c" + "".join(random.choices(string.ascii_letters + string.digits, k=24))


def notify_owner(owner_id, house_id, target_model):
    """Push a real-time pending_confirmation SSE event to the owner."""
    key = get_internal_api_key()
    if not key:
        return False
    payload = json.dumps({
        "userId": owner_id,
        "event": "pending_confirmation",
        "data": {"houseId": house_id, "targetModel": target_model},
    }).encode()
    req = urllib.request.Request(
        INTERNAL_API, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Write a PendingConfirmation + notify owner")
    parser.add_argument("--house-id", required=True)
    parser.add_argument("--target-model", required=True,
                        help="RoomFixture | RoomFurniture | RoomWindow | HouseSystem | Item | OutdoorSpace | MaintenanceRecord | Lease | Room | House")
    parser.add_argument("--target-id", required=True,
                        help="ID of the existing record this proposal modifies "
                             "(REQUIRED — the approval flow can only APPLY updates to an "
                             "existing record; a proposal without a target-id can never be "
                             "approved, only rejected)")
    parser.add_argument("--confidence", required=True, type=float,
                        help="Agent confidence in the proposal (0.0-1.0)")
    parser.add_argument("--proposed-data", required=True,
                        help='JSON object of proposed field changes, e.g. \'{"condition":"fair"}\'')
    parser.add_argument("--conflict-field", default=None,
                        help="Field that conflicts with the existing value (if any)")
    parser.add_argument("--existing-value", default=None,
                        help="Current value of the conflicting field (JSON)")
    parser.add_argument("--source-event-id", default=None)
    args = parser.parse_args()

    # r17-n1: argparse's required=True only guarantees PRESENCE — an empty
    # string is a valid value. The falsy verification gate below would skip
    # the target-existence check and the INSERT would park a pending row
    # with targetId="" that the approval flow can never APPLY (it can only
    # update an existing record) — permanently stuck in the owner's queue.
    if args.target_id == "":
        print(json.dumps({"ok": False, "error": "target-id must not be empty"}))
        sys.exit(1)

    # Validate proposed-data is a JSON object
    try:
        parsed = json.loads(args.proposed_data)
        if not isinstance(parsed, dict):
            raise ValueError("proposed-data must be a JSON object")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"invalid proposed-data: {e}"}))
        sys.exit(1)

    if not 0.0 <= args.confidence <= 1.0:
        print(json.dumps({"ok": False, "error": "confidence must be between 0.0 and 1.0"}))
        sys.exit(1)

    con = get_db()

    # House must exist — we need the owner's userId for the SSE notification
    house = con.execute("SELECT id, ownerId FROM House WHERE id = ?", (args.house_id,)).fetchone()
    if not house:
        con.close()
        print(json.dumps({"ok": False, "error": f"house {args.house_id} not found"}))
        sys.exit(1)

    # Target must exist and belong to this house when an existing record is
    # referenced. m5: the generic path previously checked EXISTENCE only — an
    # agent could park a proposal against ANOTHER house's record, and the
    # owner's approval would then modify the wrong house. Every supported
    # model now gets an explicit ownership path. m7-5: NEVER splice an
    # agent-supplied model name into SQL — the whitelist keeps the
    # interpolation safe even if a future caller passes a crafted value.
    TARGET_MODEL_WHITELIST = {
        # roomId → Room.houseId
        "RoomFixture": "JOIN Room r ON t.roomId = r.id",
        "RoomFurniture": "JOIN Room r ON t.roomId = r.id",
        "RoomWindow": "JOIN Room r ON t.roomId = r.id",
        # direct houseId column
        "HouseSystem": "",
        "Item": "",
        "OutdoorSpace": "",
        "MaintenanceRecord": "",
        "Lease": "",
        "Room": "",
    }
    if args.target_model not in TARGET_MODEL_WHITELIST:
        if args.target_model != "House":
            con.close()
            print(json.dumps({"ok": False, "error": f"unsupported target model {args.target_model!r}"}))
            sys.exit(1)
    if args.target_model == "House":
        # the house itself: target id must equal the house id
        row = con.execute(
            "SELECT id FROM House WHERE id = ? AND id = ?",
            (args.target_id, args.house_id),
        ).fetchone()
    else:
        join = TARGET_MODEL_WHITELIST[args.target_model]
        if join:
            row = con.execute(
                f"SELECT t.id FROM {args.target_model} t {join} WHERE t.id = ? AND r.houseId = ?",
                (args.target_id, args.house_id),
            ).fetchone()
        else:
            row = con.execute(
                f"SELECT id FROM {args.target_model} WHERE id = ? AND houseId = ?",
                (args.target_id, args.house_id),
            ).fetchone()
    if row is None:
        con.close()
        print(json.dumps({"ok": False,
                          "error": f"target {args.target_model}/{args.target_id} not found in house {args.house_id}"}))
        sys.exit(1)

    item_id = cuid()
    ts = now_iso()
    con.execute(
        "INSERT INTO PendingConfirmation (id, houseId, sourceEventId, targetModel, targetId,"
        " proposedData, confidence, status, conflictField, existingValue, createdAt, updatedAt)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)",
        (item_id, args.house_id, args.source_event_id, args.target_model, args.target_id,
         args.proposed_data, args.confidence, args.conflict_field, args.existing_value, ts, ts),
    )
    con.commit()
    con.close()

    notified = notify_owner(house["ownerId"], args.house_id, args.target_model)

    print(json.dumps({
        "ok": True,
        "pendingId": item_id,
        "houseId": args.house_id,
        "targetModel": args.target_model,
        "targetId": args.target_id,
        "confidence": args.confidence,
        "ownerNotified": notified,
    }))


if __name__ == "__main__":
    main()
