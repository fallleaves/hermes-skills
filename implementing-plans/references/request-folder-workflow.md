# Request-Folder-Workflow: Autonomous Agent with Human-in-the-Loop

A pattern for building LLM-powered automation that runs on a schedule, produces wiki-ready output for human review, and delivers Telegram summaries. NOT git-commit automation — output is staged for human decision.

## When to Use This Pattern

Use when:
- User is often away (no mid-flight interaction possible)
- Output needs human review before wiki commit
- Multiple simultaneous requests can arrive (per-request isolation prevents collisions)
- Telegram delivery for completed/partial work is desired

Do NOT use when:
- User wants immediate git-commit on completion (use `wiki-structured-entity-ingest` directly)
- Real-time user feedback is needed mid-task

## Architecture

```
Trigger (cron) → Agent picks up from INBOX
                      ↓
              Create IN_PROGRESS/{req-id}/
                      ↓
              Research / Implement
                      ↓
              Write NOTE.md + output files
                      ↓
              Move to DONE/{req-id}/
                      ↓
              Deliver summary to origin (Telegram)
```

## Key Invariants

1. **Per-request folder isolation** — all files for a request live in `{req-id}/` from pickup to archive
2. **NOTE.md is required** — even empty, even for declined requests
3. **No git commits** — output is for human review; wiki commit is a separate human decision
4. **Absolute paths** — `~` is NOT expanded by file tools; always use `/home/jfeng/...`
5. **No mid-flight questions** — agent does its best, notes open questions in NOTE.md, moves on

## Request Types and Routing

| Type | Behavior |
|------|----------|
| `bug` | Fix bug, output to request folder, NOTE.md with fix summary |
| `feature` | Treat as research topic; delegate to `wiki-structured-entity-ingest` |
| `question` | Answer, optionally add to wiki, NOTE.md with answer summary |
| `feedback` | Consider, NOTE.md with response |

## Cron Job Configuration

```json
{
  "skill": "request-processor",
  "schedule": "every 60m",
  "deliver": "origin",
  "repeat": "forever"
}
```

**Critical: `deliver: "origin"`** — this delivers the final output to the user's home channel (Telegram). `deliver: "local"` saves only to `~/.hermes/cron/output/` and nothing reaches the user.

**Skill drives behavior** — the skill content is what the agent reads; cron job config just triggers it.

## Telegram Delivery Rules

- Cron system auto-delivers the final response — do NOT call `send_message` in the skill
- If INBOX empty: respond with exactly `No pending requests.` (triggers silent delivery suppression)
- If task is truly done with nothing to report: respond with `[SILENT]` (nothing else)

## File Move Sequence

When archiving:

1. Write NOTE.md and all output files to `DONE/{req-id}/` first
2. `terminal(command="mv /path/IN_PROGRESS/{req-id} /path/DONE/{req-id}")` — move the whole folder
3. `terminal(command="rm /path/INBOX/{req-id}.md")` — delete original submission

Do NOT use `fs.unlink` or `rm -r`; use `mv` for folder moves.

## NOTE.md Format

```markdown
# Research Summary: {Topic}

## Status
- [x] Completed / [ ] Declined / [ ] Partial

## Files Produced
| File | Type | Wiki-Ready | Notes |
|------|------|------------|-------|
| raw/bupt-overview.md | source | ✓ | Direct copy, Chinese |

## Readiness for Wiki Ingest
- **Ready to commit**: Yes/No
- **Requires review**: ...
- **Suggested slug**: `bupt`

## Open Questions
- ...

## Decline Reason (if applicable)
- ...
```

## Wiki-Ready Output Conventions

When the research engine outputs files:

- **Raw files**: `type: source`, proper frontmatter (`title`, `created`, `updated`, `tags`, `sources`)
- **Entity files**: `type: entity`, `sources:` lists raw slugs, content in English or Chinese
- **Concept files**: `type: concept`, same structure as entity
- **Language**: source copy → original language; synthesized → English or Chinese (agent judgment)
- **No raw→raw links** — only entity/concept → raw links

## Slug Collision Prevention

All files during processing are inside `{req-id}/` — collisions are impossible at this stage. The NOTE.md contains the suggested canonical slug for human reference at wiki-ingest time.

If max output cap reached (20 raw files), note in NOTE.md under "Open Questions".

## Testing the Workflow

1. Submit a test request via wiki-webui
2. Wait for cron (or trigger manually)
3. Verify:
   - `IN_PROGRESS/` folder created with correct subfolder structure
   - `NOTE.md` has correct format
   - Raw files are wiki-formatted
   - Entity/concept file is well-structured
   - Folder moved to `DONE/` after completion
   - Telegram message delivered to home channel

## Common Failure Modes

1. **`deliver: "local"`** — output saved locally but never reaches Telegram. Fix: update cron job to `deliver: "origin"`.
2. **`~` in paths** — file tools don't expand `~`. Always use absolute `/home/jfeng/...`.
3. **Missing NOTE.md** — every request must produce one. A declined request with no NOTE.md is an incomplete workflow.
4. **Calling `send_message`** — cron system auto-delivers; manual `send_message` in skill causes duplicate delivery.
5. **git commits in skill** — this pattern deliberately skips git commits; if skill tries to commit, it's using the wrong pattern.
