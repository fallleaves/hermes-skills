---
name: amhousing
description: AM Housing property management — process messages, query houses, recommend replacements
triggers:
  - Agent needs to process unified conversation messages
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
- `process_unified_message.py` / `message_watchdog.py` — RETIRED and DELETED (2026-09-11). The app chat is served by the gateway adapter; use the `amhousing` tool (see the runtime block in the Unified conversation section). The deeper lookups below stay for the owner/operator plane.
- `upsert_fixture.py` — deduplicate + write RoomFixture with version history (stdin-JSON kwargs interface — see Rules; does NOT write the HouseEvent)
- `query_house.py` — search across Room, RoomFixture, RoomFurniture, HouseSystem (also `--scan-warranties`)
- `write_pending.py` — park a low-confidence/conflicting update as PendingConfirmation + SSE-notify the owner
- `export_house.py` — export house details (note: events/ledger/leases/files are NOT included)
- `recommend_replacement.py` — compare a fixture's specs against current market options

## Unified conversation (agent chat)

⚠️ RUNTIME (2026-09-10 cutover): the app chat is served by the gateway PLATFORM
ADAPTER in the dedicated `amhousing-app` profile (systemd
`hermes-gateway-amhousing-app.service`); the old daemon pipeline
(`amhousing-message-agent` + `hermes -z` + `process_unified_message.py`) is
STOPPED and disabled. In that profile the agent has NO shell — no terminal, no
file, no code execution, no session_search, no memory — and reaches business
data ONLY through the `amhousing` tool, which calls the app's scoped agent API
with a per-conversation token injected from an in-process registry (never from
the model). Wherever this skill says "run python3 scripts/..." or "INSERT/
UPDATE the DB", the app-chat agent must use the tool instead:
`op: "house"` (per-house context) · `op: "write"` (flat: `{writeOp, ...fields}` — `event.create`, `maintenance.create/update`, `ledger.create`, `fixture.upsert`, `furniture.upsert`, `system.upsert`, `item.upsert`, `window.upsert`, `outdoor.upsert`, `house.update`, `lease.update`; a write without `writeOp` is refused, never guessed) · `op: "pending"` (low confidence / conflict) · `op: "reply"`
(THE completion marker: `{content, scopeHouseIds, eventId?, fileUrls?}` — the
message is bound server-side) · `op: "search"` (that user's own history) ·
`op: "file"` (archive a staged upload) · `op: "notify"` (after a successful
reply). **Pass the fields FLAT at the top level of the arguments** (the nested
`payload` shape also still resolves); identity fields are never sent — the
adapter injects them. `scripts/turn_metrics.py` prints per-turn api calls, tool
calls, tokens and the slowest call — run it before optimising latency (real
turns: latency tracks input tokens + provider variance, NOT tool discovery). The business rules below (inference checklist, decision ladder, safety
boundaries, warranty/rent math, scope resolution) remain CANONICAL for both
planes; the maintenance/cron scripts remain valid for the owner's own
Telegram/CLI/operator sessions.

The owner's unified chat (`/my-houses/chat`, `AgentConversation` +
`AgentConversationMessage` tables) is an explicitly authorized CROSS-HOUSE
channel — one conversation per owner covering ALL of their houses.

Pipeline — RETIRED (2026-09-11): the claim/dump script no longer exists; the
app-profile gateway adapter claims messages and injects the same context. Kept
below only to document the shape of that context dump: it CLAIMED the oldest
eligible user message + dumped the conversation tail + the owner's HOUSE CATALOG (`{id, displayName, address, city, postcode,
propertyType, energyLabel, archived, isRental}` per house; displayName from the
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
   mention(s) → match (address/city/postcode, exact then fuzzy).
   USER-SELECTED SCOPE (D4, tier 2): when the claimed message carries a
   non-null `userScopeHouseIds` AND names no house explicitly, resolve to
   the selected house(s) WITHOUT asking — state it in the reply ("As you
   selected, …"); explicit mentions and management commands ("all
   houses"/"summarize") OUTRANK the selection; a selection id NOT in the
   catalog → REFUSE and explain, never guess, never fall back to context.
   A selection id whose house has `archived=true` (an archived owned
   house — a persisted pin can outlive an archiving) → REFUSE and
   explain, same as a stale id.
   Then multi-house → process each house, one combined plain-language
   reply — NEVER internal paths (/my-houses/..., /api/...) in reply text
   (dead, non-clickable on external channels; point to records in words:
   "recorded in the house timeline");
   concrete info but NO house mentioned → ask, don't guess, don't write —
   EXCEPT the conversational fallback: if the conversation context
   establishes a current house (the most recent resolved agent message
   resolved exactly one house, no newer mention switched it) follow-ups
   inherit that scope ONLY IF the reply states the assumption explicitly
   ("About the fridge at <displayName / address>…"). Two+ plausible matches
   → pick list, never process both. OWNERSHIP PRONOUNS are resolvable via
   the catalog's `isRental` flag: "出租房"/"the rental(s)" → the isRental=true
   houses; "我家"/"自住房"/"my own home" → the isRental=false house(s).
   Other nicknames/pronouns ("my house") are unresolvable (no nickname field)
   → ask. Explicit management command
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
   REPLY ATTACHMENTS: to send an archived file, the reply row's fileUrls
   column MUST be a JSON array string — `[{"id": "<HouseFile.id>", "url":
   "/api/files/<HouseFile.id>"}]` — ids from the per-house context's files
   list (id/originalName/mimeType) or a HouseFile lookup; image mimeTypes
   render inline. NEVER claim a file was attached when fileUrls is unset —
   a bare `/api/files/<id>` text link is NOT an attachment (INSTRUCTION §9).
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
  HouseEvent; compute & record the warranty (warranty.py, see the Warranty
  section below); check whether it covers an open MaintenanceRecord (see r113
  status-linkage below).
- **Photo / image** → archive as HouseFile, link to room / asset / event.
- **Status statement** ("fixed", "delivered", "broken") → update the matching
  fixture/furniture state; "fixed" may close an open work order (r113); "broken"
  / "damaged" → create an open MaintenanceRecord.
- **New problem report** ("water dripping", "noise from the floor") → create an
  open MaintenanceRecord for the room/item, even if the user only described it.
- **Amount / price** → ledger entry or asset purchase-price update.
- **Date / time info** → lastServiceDate, warranty (warrantyExpiry +
  warrantyBasis), lease, service schedule.
- **Contact / address / contract** → House, Lease, or tenant fields.
- **Asset retirement/removal** ("sold the old sofa", "removed the old boiler")
  → reflect the decommissioning on the asset record (notes/condition, or the
  model's status field if it has one) + HouseEvent; never hard-delete an asset
  the owner described — history matters.
- **Lease lifecycle** (renewal, rent increase, move-out, deposit return) →
  update Lease (status/endDate/monthlyRent; **deposit** — the agreed whole-EUR
  amount from the contract wording, r162); a returned deposit is an
  EXPENSE ledger entry (category 'deposit'); a rent increase also updates
  monthlyRent + HouseEvent.
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
1. **Process messages** (unified chat — the per-house HouseMessage chat was removed 2026-08-25, commit 2e06e59, tables dropped 2026-09-09; the AgentTask queue was removed 2026-09-09 with its last UI entry): the APP chat runs through the gateway adapter in the `amhousing-app` profile — the agent claims nothing itself and uses the `amhousing` tool for every read/write (runtime block above). Claim/retry semantics are unchanged and server-side: eligible = processed=0, OR claimed >30 min ago with no agent reply (the marker is processed=1 + claimedAt); the agent's reply row (written by the adaptor's `op: "reply"`) IS the completion marker. Run the status-linkage check (Safety boundary 3) before finalizing ANY write.
2. **Query**: `python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<terms>"`
3. **Maintenance scan**: `scripts/maintenance_scan.py` is a READ-ONLY deterministic report (warranty expiries, service overdue, poor-condition rooms) — cron job 15fbedd17b3f runs it Mondays 09:00 and the watchdog alerts on non-empty output; the agent never writes scan alerts as chat messages.
4. **Recommend replacement**: Read current specs + web_search → compare → recommend

## Warranty recording & queries (2026-09, warrantyBasis migration)

Every asset table (RoomFixture / RoomFurniture / HouseSystem / Item) carries
`warrantyExpiry` + `warrantyBasis` ('legal' | 'commercial' | 'none'). The
deterministic helper `/home/jfeng/projects/amhousing/scripts/warranty.py` does
ALL date arithmetic — the agent never hand-computes dates:

- **Recording** (invoice/receipt/purchase message, any channel): extract
  delivery date, stated commercial term, new/used, business/private from the
  invoice; run
  `python3 /home/jfeng/projects/amhousing/scripts/warranty.py compute --delivery-date <YYYY-MM-DD> [--term-years N] [--term-months N] [--used] [--private]`
  → JSON {expiry, expiry_epoch_ms, basis, ...} (exit 2 on bad input). Rules
  (NL art. 7:17 / 7:18a BW): new goods from a business → legal floor 2 years;
  second-hand/private → no floor, basis 'none' unless a term is stated; a
  stated term is additive (expiry = LONGER of floor and term), basis
  'commercial' only when it exceeds the floor. WRITE warrantyExpiry
  (expiry_epoch_ms, INTEGER ms) + warrantyBasis in the same asset update,
  mention both in the HouseEvent and the reply. Ambiguity → write_pending /
  ask, never guess. Never fill from a guess — a stated term never shortens
  the floor.
- **Querying** ("still under warranty?", "it broke"): read warrantyExpiry +
  warrantyBasis, run
  `python3 /home/jfeng/projects/amhousing/scripts/warranty.py status --expiry <YYYY-MM-DD> [--delivery <YYYY-MM-DD>]`
  → {status: covered|expired|unknown, days_left, advice}; paraphrase 'advice'
  in the message's language (seller-burden note only within year 1 of
  delivery). Reply: status + expiry date + basis + what the owner can do
  (year 1 → demand repair from the seller; later → commercial/manufacturer;
  expired → own cost). Expiry unknown → ask for the invoice/purchase date.
- `backfill_warranties.py` (repo scripts) retroactively fills assets that
  predate the rule: anchor date (purchaseDate/installationDate) or structured
  notes-JSON dates → legal 2y, one linked HouseEvent each, non-destructive
  (never touches an existing warrantyExpiry); conflicting note dates are
  reported AMBIGUOUS and left untouched. Run with `--dry-run` first.

## Schema migrations (live DB) — the proven path

`prisma migrate dev` refuses non-interactive terminals, and the live DB is held
by the running next-server, so ANY engine write step fails with
`database is locked` (its first write ignores busy_timeout). Do this instead:

1. Hand-write `prisma/migrations/<YYYYMMDDHHMMSS>_<name>/migration.sql`.
2. Verify the SQL really equals the schema:
   `npx prisma migrate diff --from-migrations prisma/migrations --to-schema-datamodel prisma/schema.prisma --shadow-database-url file:/tmp/shadow.db --script`
   → must print "This is an empty migration."
3. Rehearse the deploy on a COPY: `cp prisma/amhousing.db /tmp/t.db` then
   `DATABASE_URL=file:/tmp/t.db npx prisma migrate deploy`.
4. Apply to the LIVE db without stopping the app: exec the migration.sql
   verbatim in one transaction and INSERT the `_prisma_migrations` row
   (`checksum` = sha256 of the file's RAW BYTES, `applied_steps_count`=1,
   `started_at`/`finished_at` as ISO `YYYY-MM-DDTHH:MM:SS.000Z`). Then
   `npx prisma migrate status` must say "Database schema is up to date!" —
   that is the check that the row is right.
5. `npx prisma generate`.

⚠️ The GHA deploy will NOT apply your migration when you push from the deploy
host itself: `PREV_HEAD` is captured in the same working copy, so
`git diff PREV_HEAD HEAD` is empty → `HAS_NEW_MIGRATIONS=no` → migrate is
skipped. Always confirm the row landed (`migrate status`), never assume the
green deploy applied it.

⚠️ Drift blocks ALL future migrations: if `_prisma_migrations` holds a row whose
directory no longer exists in `prisma/migrations`, `migrate deploy` refuses
("migration history differs"). Check with
`comm -23 <(db names) <(repo dirs)`; if `migrate diff` above is empty (recorded
history == schema), the orphan rows are bookkeeping leftovers and can be
deleted in a transaction — after a backup.

## Rent window (UI recorded receipts)

The owner can record rent receipts from the overview rent tab
(`/overview/rent/[houseId]`, POST `/api/overview/rent/[houseId]`). The
UI writes: HouseLedgerEntry (type='INCOME', category='rent', amount CENTS,
date) + a linked HouseEvent (type='INCOME', createdByType='owner',
createdByModel='rent-window', structured {type:'rent_receipt', amountCents,
date}). When the owner says they recorded a payment in the app, do NOT
double-write — the ledger entry already exists; answer from it. Rent math
stays in rent_calc.py (shared via src/lib/rentView.ts).

## Test pitfalls (vitest)

- jsdom `fireEvent.click` never submits forms — use `userEvent`.
- Mock `next/navigation` with STABLE objects: `useRouter: () => mockRouter` /
  `useParams: () => mockParams` (module-level consts). A fresh object per
  call re-triggers every effect that depends on `router`/`params.id` on each
  render → infinite fetch loop that silently resets form state (r152 lesson:
  a select's state kept reverting until the mocks were made stable).
- Populate ALL required form fields before submitting a form in tests —
  native constraint validation blocks the submit event in jsdom.

## Rules
- **Infer first**: for every message, run the Role-section inference checklist
  and decision ladder before applying the rules below.
- **Reading image content**: the host has NO local OCR (no tesseract) — that
  absence alone NEVER means an image is unreadable. Visible text in uploaded
  photos (invoice/receipt/label) is read with a VISION MODEL: `hermes chat
  --image <ABSOLUTE path of the stored file> -q "<extract all visible text
  verbatim>" -Q` (relative paths FAIL — always pass the absolute path), or the
  vision_analyze tool when available. EXIF/PIL metadata is a hint, not a read.
  A run that skips vision and replies "no OCR / cannot read" is WRONG: it must
  archive/register the file and ASK the owner for the text, stating what a
  record would need. NEVER fabricate brand/model/price from a photo you did
  not actually read.
- Dedup before write (same roomId+type → update, not duplicate)
- HouseFile.storagePath is STORAGE-ROOT-RELATIVE (`houses/<houseId>/<file>`). NEVER write `private/uploads/houses/...` (root-prefixed) or an absolute path — the app joins relative paths under its root, so a root-prefixed value double-prefixes and every attached file 404s in the GUI (r143-n2).
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

These apply to EVERY use of this skill (message processing, cron
scans, interactive chat, unified conversation) — not just the cron pipeline.
Canonical 5-item list, lockstepped with docs/unified-house-chat.md §8:

1. **AgentConversationMessage scope**: the unified conversation is an
   explicitly authorized cross-house channel, but per-message house
   resolution is MANDATORY (the Unified conversation protocol above) —
   including via a user-selected scope (D4, tier 2): the picker only
   ever offers the owner's own non-archived houses, so a selection
   introduces no cross-house surface (a selection id whose house is
   archived is refused — 400 server-side and agent-side REFUSE, same as
   a stale id); a message that cannot be resolved is NOT written — ask
   instead.
2. **Cross-house exception**: cross-house aggregation responds only to
   explicit management commands ("summarize all houses", "maintenance due
   reminders for all houses"), including inside the unified conversation;
   everything else is a single-house request.
3. **Status-linkage check**: every processed update is checked against the
   house's open maintenance records (`open_maintenance` from the claimed
   context / per-house dump). An update that demonstrably resolves an open
   work order closes it (status='completed') with a documenting HouseEvent;
   partial progress updates the record's notes/description; no evidence →
   keep it open and say so in the reply; a newly revealed issue opens a new
   record.
4. **Sensitive data**: tenant personal information (name/phone/email) and
   account credentials must NEVER be written to reply content,
   or PendingConfirmation.proposedData (proposedData is shown in the owner's
   UI when they review a proposal).
5. **Decision ladder**: low confidence (< 0.6) or conflicting with an
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

## Rent payment plans & status (2026-09, rent_calc.py)

- **Plan changes (r163)**: the payment plan of the ACTIVE lease can be
  changed ONLY before the first rent payment arrives (rent income entry
  with date >= lease.startDate locks it; deposits never lock). The rent
  window exposes the selector (PATCH /api/overview/rent/[houseId]); a
  plan the agent would also update (contract renegotiation) follows the
  same rule — never change paymentPlan/annualRent in the DB once rent
  was received for the contract window.

- `Lease.paymentPlan` ∈ {'monthly', 'yearly', 'hybrid_last6'} (default
  'monthly'); `Lease.annualRent` = the agreed PAY-IN-FULL amount in whole
  EUR (NULL → monthlyRent × leaseMonths); `Lease.firstMonthRent` (r175) = a
  promotional first-month whole EUR (NULL = same as monthlyRent — rent_calc
  --first-month); `Lease.serviceCosts`/`Lease.furnitureCosts` (r177/r178) =
  recurring monthly service/furniture fees in whole EUR (NULL = none), billed
  TOGETHER WITH the rent as one combined payment — record from the contract
  wording ("服务费", "servicekosten", "家具费") and pass the matching
  rent_calc flags. yearly = 整付 / pay in full: the
  WHOLE contract rent is due at contract start (fixed-term leases only —
  open-ended is rejected by the lease API). hybrid_last6 (半年付) = any lease
  LONGER than 6 months: the FIRST N-6 months paid monthly, the LAST 6 months
  prepaid as ONE block due when the block's window starts (dueDate = start of
  month N-5, due = 6×monthly). Never offer hybrid for a lease of 6 months or less (the
  lease API rejects it).
- **Recording** (new lease / lease edit, any channel): read the contract
  wording — "一次性付清 / 整付 / pay in full (the whole contract upfront)" →
  plan yearly (+ annualRent when the contract states the agreed full
  amount), "前半年按月付、后半年预付" /
  "half prepaid at the start" → hybrid_last6, plain monthly → monthly.
  Include paymentPlan (+ annualRent if any) in the lease write.
- **Querying rent status** ("收了多少 / 这个月交了吗 / 还欠多少 / 预付到
  什么时候"): run the deterministic calculator —
  `python3 /home/jfeng/projects/amhousing/scripts/rent_calc.py
  --start <YYYY-MM-DD> [--end <YYYY-MM-DD>] --monthly <whole EUR>
  [--plan monthly|yearly|hybrid_last6] [--annual <whole EUR>] [--first-month <whole EUR>]
  --payments '<json [{"date":"YYYY-MM-DD","amountCents":N}]>'
  [--on <YYYY-MM-DD>]` (NO `compute` subcommand — flags go directly on the
  script) — payments = the house's rent-income ledger entries
  (INCOME + rent category; amountCents). Pass --service-costs <EUR> /
  --furniture-costs <EUR> (r177/r178) when the lease carries recurring
  monthly service / furniture fees — every due already combines them. Output JSON, amounts in CENTS:
  {contractTotalCents, receivedTotalCents, outstandingCents, overdueCents,
  prepaidThrough, periods[], current{status,...}, nextDue{...}}; status per
  period: paid | partial | overdue | upcoming. outstandingCents = whole
  remaining contract (NOT debt today); overdueCents = what is actually
  past-due unpaid — the 缺口 the owner sees. NEVER hand-compute rent math.

## Advanced Workflows

### Export house details
`python3 <skill_dir>/scripts/export_house.py --house-id <id> --format text`

### Cross-house search  
`python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<search terms>"`

### Multi-house comparison
Query both houses and compare by field.
