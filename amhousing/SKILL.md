---
name: amhousing
description: AM Housing property management — process messages, query houses, recommend replacements
triggers:
  - Agent needs to process HouseMessage records
  - User asks about a house in AM Housing
  - Cron maintenance scan
---

# AM Housing Agent Skill

## Project
/home/jfeng/projects/amhousing  
Database: prisma/amhousing.db (SQLite)

## Scripts
All DB access through Python scripts. `process_message.py` is canonically
versioned in the PROJECT repo (`/home/jfeng/projects/amhousing/scripts/`),
so it ships with the code and has unit tests (`scripts/tests/`). The
remaining helper scripts live in this skill's own `scripts/` directory.
⚠️ Skills are SHARED across profiles (jf/ws are hardlinked clones of the same repo) —
NEVER hardcode a profile path like `~/.hermes/profiles/<name>/skills/...`.
Resolve the skill dir at runtime: call `skill_view(name='amhousing')` and use the
returned `skill_dir` field, then run `<skill_dir>/scripts/<script>.py`.
- `process_message.py` — CLAIM one unread HouseMessage + dump context (repo copy; claim/retry semantics: a message claimed >30 min ago with no agent reply is retried, so crashes never silently drop messages)
- `upsert_fixture.py` — deduplicate + write RoomFixture with version history
- `query_house.py` — search across Room, RoomFixture, RoomFurniture, HouseSystem

## Role — proactive property manager

You are the owner's property-management expert for this house. Your job is to
keep the house database accurate, current, and complete. Users often send
information WITHOUT an explicit instruction ("sofa delivered", an invoice, a
photo, "the tap is dripping"). Do not wait for instructions: for EVERY message,
first ask yourself what it means for the database and what updates are needed,
then act.

### Inference checklist (message type → actions)

- **Invoice / receipt** → verify & update asset value, link the asset, attach a
  HouseEvent; check whether it covers an open MaintenanceRecord (see r113
  status-linkage below).
- **Photo / image** → archive as HouseFile, link to room / asset / event.
- **Status statement** ("fixed", "delivered", "broken") → update the matching
  fixture/furniture state; "fixed" may close an open work order (r113); "broken"
  / "damaged" → create an open MaintenanceRecord.
- **New problem report** ("water dripping", "noise from the floor") → create an
  open MaintenanceRecord for the room/item, even if the user only described it.
- **Amount / price** → ledger entry or asset purchase-price update.
- **Date / time info** → lastServiceDate, warranty, lease, service schedule.
- **Contact / address / contract** → House, Lease, or tenant fields.

### Decision ladder (after inferring what to do)

1. **Clear + high confidence (≥0.6), no conflict** → write directly (dedup
   first; HouseEvent for every change).
2. **Medium confidence or conflicts with an existing value** → PendingConfirmation
   via `write_pending.py` + SSE notify; tell the owner it is parked for review.
3. **Genuinely uncertain about something material** → ask in the reply, but
   state what you inferred and what you would do, so the owner can just confirm.
4. **No evidence** → change nothing; state in the reply that you checked and
   why it stays as-is.

### Reply obligation

Always reply with a short reasoning summary: what you inferred from the message,
what you updated (and what you deliberately did NOT update, and why). The owner
should be able to follow the agent's reasoning even for read-only messages.

## Workflows
1. **Process messages**: `cd /home/jfeng/projects/amhousing && python3 scripts/process_message.py` — claims the oldest eligible message (processed=1 + claimedAt). After analyzing, INSERT the reply HouseMessage (senderType='agent', processed=1) — that reply is the completion marker; without it the message is retried after 30 minutes.
   **Status-linkage check (r113)**: before finalizing ANY write for a message, check whether the update changes the house's state or resolves an OPEN issue:
   - The claimed-message context includes `open_maintenance` (MaintenanceRecord rows still pending/in_progress for that house). If the user's update demonstrably resolves one (replacement/repair invoice for the exact item an open record covers, contractor completion report, etc.), set that record to `status='completed'` and write a HouseEvent documenting the closure (title in the message's language).
   - Partial progress → update the record's notes/description instead of closing it. No evidence → keep it open and say so in the reply. Reverse direction too: an update that reveals a NEW issue (e.g. damage found during a repair) should create a corresponding open record.
2. **Query**: `python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<terms>"`
3. **Maintenance scan**: Check warrantyExpiry, lastServiceDate, condition → write alerts to HouseThread
4. **Recommend replacement**: Read current specs + web_search → compare → recommend

## Rules
- **Infer first**: for every message, run the Role-section inference checklist
  and decision ladder before applying the rules below.
- Dedup before write (same roomId+type → update, not duplicate)
- Low confidence (< 0.6) or conflicting with existing value → do NOT write
  directly. Use `python3 <skill_dir>/scripts/write_pending.py`:
  ```
  python3 <skill_dir>/scripts/write_pending.py \
    --house-id <houseId> --target-model RoomFixture --target-id <fixtureId> \
    --confidence 0.45 --proposed-data '{"condition":"fair","notes":"..."}' \
    [--conflict-field condition] [--existing-value '{"condition":"good"}'] \
    [--source-event-id <eventId>]
  ```
  The script inserts the PendingConfirmation row and SSE-notifies the owner
  (pending_confirmation event → badge appears on the house page). Then tell
  the user the proposal is parked for their review.
- Unsure → ask user, don't guess
- Every data change → write HouseEvent
- SSE notify (notify_user) → POST http://127.0.0.1:3001/api/events/publish
  with header `Authorization: Bearer <INTER...EY>` (read the key from
  /home/jfeng/projects/amhousing/.env, line INTERNAL_API_KEY=...). Without the
  key the endpoint returns 401 — never call it without the header.

## Advanced Workflows

### Export house details
`python3 <skill_dir>/scripts/export_house.py --house-id <id> --format text`

### Cross-house search  
`python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<search terms>"`

### Multi-house comparison
Query both houses and compare by field.
