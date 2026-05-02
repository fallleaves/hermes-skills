---
name: request-processor
description: Process user requests from the Request Box file system — autonomous research, wiki edits, bug fixes, feedback. Manages the full request lifecycle in isolated per-request folders.
triggers:
  - cron job (hourly)
  - manual trigger
input:
  requests_from: /home/jfeng/projects/wiki/requests/INBOX/
output:
  completed_requests: /home/jfeng/projects/wiki/requests/DONE/
  declined_requests: /home/jfeng/projects/wiki/requests/DECLINED/
---

# Request Box Processor

Processes user requests from the Request Box file system. Creates isolated per-request folders throughout the entire lifecycle. Produces wiki-ready output for human review — **no git commits**.

## Folder Structure (Per-Request Isolation)

```
~/projects/wiki/requests/
├── INBOX/
│   └── req-20260502--xxxx.md           ← original submission
├── IN_PROGRESS/
│   └── req-20260502--xxxx/            ← own folder, entire lifecycle
│       ├── request.md                   ← copy of original submission
│       ├── raw/                         ← raw source files (wiki-ready)
│       │   └── {slug}-*.md
│       ├── entities/  OR  concepts/    ← synthesized pages
│       │   └── {slug}.md
│       └── NOTE.md                     ← required: status + guidance
└── DONE/
    └── req-20260502--xxxx/            ← archived (same structure)
```

**DECLINED requests:**
```
DECLINED/
└── req-20260502--xxxx/
    ├── request.md
    └── NOTE.md        ← required: decline reason
```

## Processing Steps

### Phase 1: Setup
1. List all `.md` files in `/home/jfeng/projects/wiki/requests/INBOX/`
2. For each request:
   a. Create `/home/jfeng/projects/wiki/requests/IN_PROGRESS/{req-id}/`
   b. Create subfolders: `raw/`, `entities/`, `concepts/`
   c. Copy the original file as `request.md` inside the folder
   d. Parse the request: extract `type`, `body`, `author`, `contact`

### Phase 2: Implement
3. **For `feature` type requests:** load the `wiki-structured-entity-ingest` skill and delegate the research work. The research skill will output directly into the request folder.
4. **For `bug` type requests:** fix the bug in the wiki or webui, output the fix files into the request folder.
5. **For `question` / `feedback` type requests:** answer or consider the feedback, output any wiki content into the request folder.

### Phase 3: Document
6. Write `NOTE.md` at the root of the request folder (required for ALL requests, even declined):
   ```markdown
   # Research Summary: {Topic}

   ## Status
   - [x] Completed / [ ] Declined / [ ] Partial

   ## Files Produced
   | File | Type | Wiki-Ready | Notes |
   |------|------|-------------|-------|
   | raw/bupt-overview.md | source | ✓ | ... |

   ## Readiness for Wiki Ingest
   - **Ready to commit**: Yes / No
   - **Requires review**: ...
   - **Suggested wiki slug**: ...

   ## Open Questions for Human
   - ...

   ## Decline Reason (if applicable)
   - ...
   ```

### Phase 4: Archive
7. Move the entire request folder from `IN_PROGRESS/` to `DONE/` (or `DECLINED/`)
   - Use `terminal(command="mv ...")` to move the folder
   - Do NOT delete any files
8. Delete the original `.md` file from `INBOX/`

### Phase 5: Report
9. Produce a clear final report as your final output text.
   - The cron job system auto-delivers this report to the user's Telegram home channel.
   - Do NOT call `send_message` yourself.
   - If INBOX was empty, respond with exactly `No pending requests.` and nothing else.

## Request Types

| Type | Behavior |
|------|----------|
| `bug` | Fix bug in wiki or webui. Output fix files + NOTE.md. |
| `feature` | Treat as research request. Load `wiki-structured-entity-ingest` skill. Output raw files + entity/concept + NOTE.md. |
| `question` | Answer question. Add to wiki if appropriate. Output files + NOTE.md. |
| `feedback` | Consider feedback. Reply via NOTE.md. No wiki output needed usually. |

## Research Output Rules (for `feature` type)

When the research skill produces output:

1. **Raw files** (`raw/`): Follow existing wiki conventions exactly:
   - Frontmatter: `title`, `created`, `updated`, `type: source`, `tags`, `sources`
   - Naming: `{slug}-{source-type}.md`
   - Language: source copy if direct extract, English/Chinese (agent judgment) if synthesized
2. **Entity/Concept files** (`entities/` or `concepts/`): Follow existing conventions
   - Frontmatter: `title`, `created`, `updated`, `type: entity|concept`, `tags`, `sources`
   - Language: English or Chinese (agent judgment)
3. **Slug collision prevention**: During processing, files stay inside the request folder — no naming conflicts possible since all paths are scoped to `{req-id}/`
4. **Max output cap**: If research produces more than 20 raw files, stop at 20 and note the remainder in NOTE.md as open questions.

## Implementation Rules

- **No git commits** — output stays in the request folder for human review
- **Absolute paths only** — never use `~`, always use `/home/jfeng/projects/wiki/...`
- **Per-request isolation** — every request's files stay in its own folder throughout lifecycle
- **NOTE.md required** — every request (including DECLINED) must produce this
- **No deletion** — never delete files, only move them

## Pitfalls

### Cron Job `deliver` Setting
**Critical:** The cron job that triggers this skill MUST have `deliver: "origin"` — NOT `"local"`. If set to `"local"`, output is saved to `~/.hermes/cron/output/` only and nothing reaches Telegram. Check with `cronjob(action="list")` and update with `cronjob(action="update", deliver="origin", job_id="...")` if needed.

### Path Resolution
- `~` is NOT expanded by file tools — always use **absolute paths** like `/home/jfeng/projects/wiki/requests/INBOX/`

### File Move Sequence
1. **Write** the NOTE.md and all output files to the destination folder first
2. **Move** the entire folder from `IN_PROGRESS/` to `DONE/` using `terminal(command="mv ...")`
3. **Delete** the original `.md` file from `INBOX/` using `terminal(command="rm ...")`

Do NOT use `rm -r` — move the folder first, then remove it if needed.

### Cron Job Telegram Delivery
- The cron job system auto-delivers the final response to Telegram — do NOT call `send_message`
- If INBOX is empty, respond with `No pending requests.` and nothing else.

### Empty INBOX
- If no requests found, respond with `No pending requests.` exactly.

### Bug Fixes vs Research
- Bug fixes go directly to the webui repo — edit the source, write a NOTE.md, move folder to DONE
- Research (feature) goes to the request folder and delegates to wiki-structured-entity-ingest skill
