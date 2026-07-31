# Kanban Event Watcher Architecture

**Last updated:** 2026-07-05

## Overview

The kanban event watcher is a standalone daemon that polls `task_events` SQLite tables across all kanban boards and sends notifications to a Telegram channel via a dedicated bot (@AmHousingBot). It is independent of Hermes' built-in notifier (which uses `kanban_notify_subs` for task-specific subscriptions).

## Script Location

```
~/.hermes/profiles/jf/scripts/kanban-event-watcher.py
```

## Systemd Service

```
~/.config/systemd/user/kanban-event-watcher.service
kanban-event-watcher.service (user service)
```

### Restart

```bash
systemctl --user restart kanban-event-watcher.service
```

### Credentials

From `~/projects/auto-devops/.env` (via `EnvironmentFile` in systemd unit):
- `HEALTH_ALERT_BOT_TOKEN` — @AmHousingBot token
- `HEALTH_ALERT_CHAT_ID` — Telegram chat ID (5684104233)

## Boards Watched

Hardcoded in `BOARDS` dict at top of script:

| Board | DB Path |
|-------|---------|
| amhousing | `~/.hermes/kanban/boards/amhousing/kanban.db` |
| wiki-webui | `~/.hermes/kanban/boards/wiki-webui/kanban.db` |
| ops | `~/.hermes/kanban/boards/ops/kanban.db` |

## Event Types Forwarded

Events marked as `MEANINGFUL_EVENTS`: created, decomposed, promoted, spawned, claimed, completed, blocked, unblocked, crashed, gave_up, commented, archived.

## Truncation Limits (per-field)

Updated 2026-07-05 to match orchestrator:

| Field | Limit | Code Line |
|-------|-------|-----------|
| Title | 1000 chars | `truncate(title, 1000)` |
| Summary (completed) | 2000 chars | `truncate(data["summary"], 2000)` |
| Reason (blocked) | 2000 chars | `truncate(data["reason"], 2000)` |
| Error (crashed) | 2000 chars | `truncate(data["error"], 2000)` |

**Note:** The full message has no explicit total limit. Telegram API hard limit is 4096 chars per message.

## Summary Truncation Workaround

### The Problem

Hermes core (`kanban_db.py:complete_task`) caps the event payload summary at **400 chars** (first line only):

```python
# hermes_cli/kanban_db.py line 4105 — DO NOT MODIFY (core code)
ev_summary = ev_summary.strip().splitlines()[0][:400]
```

The full summary is preserved in `task_runs.summary` but the `task_events.payload` contains only the truncated version. The event watcher was previously reading the truncated payload.

### The Fix

The event watcher bypasses the truncated payload for completed events by reading the full summary directly from `task_runs`:

```python
# In poll_once(), for each completed event with a non-null run_id:
cur = conn.execute("SELECT summary FROM task_runs WHERE id = ?", (ev[2],))
row = cur.fetchone()
if row and row[0]:
    payload["summary"] = row[0]  # inject full summary
```

This requires no Hermes core changes — only the event watcher script is modified.

### Data Flow

```
Worker → kanban_complete(summary="...") 
  → task_runs.summary         = FULL (no truncation) ✅  
  → task_events.payload.summary = 400 chars (core limit) ⚠  
  → event watcher reads task_runs → gets FULL summary ✅  
```

## Related: Orchestrator Truncation Limits

The orchestrator (`~/projects/auto-development/orchestrator_daemon.py`) independently truncates text when creating tasks. These should be kept in sync with the event watcher:

| Orchestrator Usage | Limit |
|-------------------|-------|
| `Design: {wf.user_request[:1000]}` | 1000 chars |
| `Fix: {wf.user_request[:1000]}` | 1000 chars |
| `reason = str(payload_raw)[:2000]` | 2000 chars |

## Batch Size

The event watcher sends at most **10 messages per tick** (`messages[:10]`), dropping any overflow. The polling interval is 10 seconds in daemon mode.
