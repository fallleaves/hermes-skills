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
Database: prisma/dev.db (SQLite)

## Scripts
All DB access through Python scripts in this skill's own `scripts/` directory.
⚠️ Skills are SHARED across profiles (jf/ws are hardlinked clones of the same repo) —
NEVER hardcode a profile path like `~/.hermes/profiles/<name>/skills/...`.
Resolve the skill dir at runtime: call `skill_view(name='amhousing')` and use the
returned `skill_dir` field, then run `<skill_dir>/scripts/<script>.py`.
- `process_message.py` — read unread HouseMessage, analyze intent, execute action, write reply
- `upsert_fixture.py` — deduplicate + write RoomFixture with version history
- `query_house.py` — search across Room, RoomFixture, RoomFurniture, HouseSystem

## Workflows
1. **Process messages**: `cd /home/jfeng/projects/amhousing && python3 <skill_dir>/scripts/process_message.py` (skill_dir from skill_view)
2. **Query**: `python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<terms>"`
3. **Maintenance scan**: Check warrantyExpiry, lastServiceDate, condition → write alerts to HouseThread
4. **Recommend replacement**: Read current specs + web_search → compare → recommend

## Rules
- Dedup before write (same roomId+type → update, not duplicate)
- Low confidence → PendingConfirmation
- Unsure → ask user, don't guess
- Every data change → write HouseEvent

## Advanced Workflows

### Export house details
`python3 <skill_dir>/scripts/export_house.py --house-id <id> --format text`

### Cross-house search  
`python3 <skill_dir>/scripts/query_house.py --house-id <id> --query "<search terms>"`

### Multi-house comparison
Query both houses and compare by field.
