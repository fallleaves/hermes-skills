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
- `process_unified_message.py` — CLAIM one unread AgentConversationMessage + dump house catalog (repo copy; also `--house-id <id>` per-house context mode — see the Unified conversation section)
- `upsert_fixture.py` — deduplicate + write RoomFixture with version history (stdin-JSON kwargs interface — see Rules; does NOT write the HouseEvent)
- `query_house.py` — search across Room, RoomFixture, RoomFurniture, HouseSystem (also `--scan-warranties`)
- `write_pending.py` — park a low-confidence/conflicting update as PendingConfirmation + SSE-notify the owner
- `export_house.py` — export house details (note: events/ledger/leases/files are NOT included)
- `recommend_replacement.py` — compare a fixture's specs against current market options

## Unified conversation (agent chat)

The owner's unified chat (`/my-houses/chat`, `AgentConversation` +
`AgentConversationMessage` tables) is an explicitly authorized CROSS-HOUSE
channel — one conversation per owner covering ALL of their houses.

Pipeline (claim-mode dump): `python3 /home/jfeng/projects/amhousing/scripts/process_unified_message.py`
— CLAIM the oldest eligible user message + dump conversation tail + the
owner's HOUSE CATALOG (`{id, displayName, address, city, postcode,
propertyType, energyLabel, archived}` per house; displayName from the
Listing title chain in the message's language, fallback address; archived
houses stay IN the catalog with their flag). Status: `message_claimed` |
`no_pending_messages`. Per-house context AFTER scope resolution (never
before): `process_unified_message.py --house-id <id> --user-id <userId>`
→ `context_dumped`
(house/rooms/existing_fixtures/open_maintenance) — refuses (stderr, exit 1)
a house the conversation owner does not own (pass the claimed message's
`userId` from the claim dump — the dump carries it). Plus this skill's own
`export_house.py` / `query_house.py` for deeper lookups.

Processing protocol (per message):
1. RESOLVE the scope FIRST against the houses catalog — explicit
   mention(s) → match (address/city/postcode, exact then fuzzy); multi-house
   → process each house, one combined reply with `/my-houses/<id>` links;
   concrete info but NO house mentioned → ask, don't guess, don't write —
   EXCEPT the conversational fallback: if the conversation context
   establishes a current house (the most recent resolved agent message
   resolved exactly one house, no newer mention switched it) follow-ups
   inherit that scope ONLY IF the reply states the assumption explicitly
   ("About the fridge at <displayName / address>…"). Two+ plausible matches
   → pick list, never process both. Nicknames/pronouns ("my house", "出租房")
   are unresolvable (no nickname field) → ask. Explicit management command
   ("all houses", "summarize") → cross-house aggregation. House not in
   catalog → refuse and explain.
2. PER RESOLVED HOUSE fetch detailed context FIRST (post-resolution,
   PRE-WRITE — `--house-id` mode + export/query scripts), then run the
   inference checklist + decision ladder + status-linkage check (consumes
   `open_maintenance`), then DECIDE the scope: resolved house set in
   house-resolved processing order (FIRST = primary house), or `"[]"` for
   ask/refuse/read-only.
3. WRITE ORDER (single raw-SQL batch, strictly): (1) scopeHouseIds UPDATE
   on the user row — the ONLY scope write, never standalone; (2) reply
   INSERT (`senderType='agent'`, `processed=1`, SAME scope JSON, eventId
   per the one-named-event rule: status-linkage closure for the primary
   house, else the binding NOTE for the primary house, else NULL). The
   reply IS the completion marker — no reply → retried after 30 minutes.
4. SSE: call notify_user with event `agent_conversation` (payload
   `{conversationId, lastMessage:{id, contentPreview}}`) as the LAST action.

M-A2/M-A3 apply to every raw-SQL write here exactly as in message
processing (INTEGER-ms timestamps; data-only, no schema objects).

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
- **Asset retirement/removal** ("sold the old sofa", "removed the old boiler")
  → reflect the decommissioning on the asset record (notes/condition, or the
  model's status field if it has one) + HouseEvent; never hard-delete an asset
  the owner described — history matters.
- **Lease lifecycle** (renewal, rent increase, move-out, deposit return) →
  update Lease (status/endDate/monthlyRent); a returned deposit is an
  EXPENSE ledger entry; a rent increase also updates monthlyRent + HouseEvent.
- **Repair quote / contractor booking** ("plumber quoted €450", "contractor
  coming Friday") → record cost/contractor/date on the open MaintenanceRecord;
  this is partial progress — do NOT close the work order (r113).
- **Purchase without invoice** ("bought a new fridge") → still write the asset
  with the stated value; note in the record that no invoice is on file yet.
- **Window / outdoor / Item updates** ("replaced a window", "new garden
  furniture") → update the matching RoomWindow / OutdoorSpace / Item record.
- **House master data** (energy label, renovation year, building info) →
  update the House fields.

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
1. **Process messages**: `cd /home/jfeng/projects/amhousing && python3 scripts/process_message.py` — claims the oldest eligible message (eligible: processed=0, OR claimed >30 min ago with no agent reply; the claim marker is processed=1 + claimedAt). After analyzing, INSERT the reply HouseMessage (senderType='agent', processed=1) — that reply is the completion marker; without it the message is retried after 30 minutes. Run the status-linkage check (Safety boundary 4) before finalizing ANY write.
2. **Query**: `python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<terms>"`
3. **Maintenance scan**: Check warrantyExpiry, lastServiceDate, condition → write alerts. The project ships `scripts/maintenance_scan.py` (runs Mondays 09:00 as cron job 15fbedd17b3f) — don't duplicate its output. Alerts are written as HouseMessage rows (senderType='agent') in the house thread; HouseThread itself has no content column.
4. **Recommend replacement**: Read current specs + web_search → compare → recommend

## AgentTask processing

AgentTask rows are produced by the app's analyze-event route
(`src/app/api/analyze-event/route.ts`): type=`analyze_event`, input JSON =
`{rawText, files, houseInfo}`. Users trigger them by uploading invoices/photos
etc. through the UI. Processing contract:

- Analyze `input` exactly like a HouseMessage from the same house — run the
  Role inference checklist and decision ladder, then act (write / pending /
  ask / no change).
- Write `output` as JSON: `{analysis, actions}` — what you inferred and what
  you did. **`output` is user-visible** (the UI polls `GET /api/tasks/[id]`),
  so it must contain NO tenant PII and no credentials.
- Completion marker: `status='completed'` with a non-empty `output` (set
  startedAt/completedAt too). A task left `pending` stays in the queue.
- Scope: only the house bound to the task's `houseId`.

## Rules
- **Infer first**: for every message, run the Role-section inference checklist
  and decision ladder before applying the rules below.
- Dedup before write (same roomId+type → update, not duplicate)
- `upsert_fixture.py` reads ONE JSON object of kwargs from stdin (no CLI
  flags) and dedups by roomId+type:
  ```
  echo '{"room_id":"<roomId>","fixture_type":"lamp","name":"Lamp","purchase_price":109900,"source_event_id":"<eventId>"}' | python3 <skill_dir>/scripts/upsert_fixture.py
  ```
  It writes RoomFixture + RoomFixtureVersion only — you MUST create the
  HouseEvent yourself (per "Every data change" below) and pass its id as
  `source_event_id` so the version row is traceable (m7).
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
  with header `Authorization: Bearer <INTERNAL_API_KEY>` (read the key from
  /home/jfeng/projects/amhousing/.env, line INTERNAL_API_KEY=...). Without the
  key the endpoint returns 401 — never call it without the header.

## Safety boundaries

These apply to EVERY use of this skill (message processing, AgentTasks, cron
scans, interactive chat, unified conversation) — not just the cron pipeline.
Canonical 6-item list, lockstepped with docs/unified-house-chat.md §8:

1. **HouseMessage scope rule**: an AgentTask may only read/modify data of the
   house bound to its houseId; a HouseMessage may only touch the house of its
   thread (thread.houseId). Instructions demanding "query/modify other houses"
   → refuse and explain why.
2. **AgentConversationMessage scope**: the unified conversation is an
   explicitly authorized cross-house channel, but per-message house
   resolution is MANDATORY (the Unified conversation protocol above); a
   message that cannot be resolved is NOT written — ask instead.
3. **Cross-house exception**: cross-house aggregation responds only to
   explicit management commands ("summarize all houses", "maintenance due
   reminders for all houses"), including inside the unified conversation;
   everything else is a single-house request.
4. **Status-linkage check**: every processed update is checked against the
   house's open maintenance records (`open_maintenance` from the claimed
   context / per-house dump). An update that demonstrably resolves an open
   work order closes it (status='completed') with a documenting HouseEvent;
   partial progress updates the record's notes/description; no evidence →
   keep it open and say so in the reply; a newly revealed issue opens a new
   record.
5. **Sensitive data**: tenant personal information (name/phone/email) and
   account credentials must NEVER be written to task.output, reply content,
   or PendingConfirmation.proposedData (proposedData is shown in the owner's
   UI when they review a proposal).
6. **Decision ladder**: low confidence (< 0.6) or conflicting with an
   existing value → `write_pending.py` (PendingConfirmation + SSE), never
   overwrite silently; PendingConfirmation keeps its houseId — the owner
   reviews it on that house's pending page.

## Invariants (quick reference)

- Timestamps: INTEGER Unix milliseconds everywhere (all scripts + app agree).
- Confidence threshold: 0.6 — below it, or conflicting with an existing value,
  never write directly; use `write_pending.py`.
- PendingConfirmation target whitelist: RoomFixture, RoomFurniture,
  HouseSystem, Item, House (script-enforced; see write_pending.py).
- Claim/retry: processed=1 + claimedAt = claimed; >30 min with no agent reply
  → retry-eligible.
- Money: HouseLedgerEntry.amount in cents; Lease.monthlyRent / Listing.price in
  whole units. MaintenanceRecord.cost — see the ledger convention in
  process_message.py INSTRUCTION.

## Advanced Workflows

### Export house details
`python3 <skill_dir>/scripts/export_house.py --house-id <id> --format text`

### Cross-house search  
`python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<search terms>"`

### Multi-house comparison
Query both houses and compare by field.
