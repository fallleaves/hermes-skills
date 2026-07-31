# Kanban Notification Pipeline — Truncation Chain

When a kanban notification arrives truncated, the bottleneck is rarely the
event watcher's display limit. The truncation happens earlier in the pipeline.

## Pipeline Flow

```
Worker → kanban_complete(summary="...")
    ↓
complete_task()  [kanban_db.py]
    ├── task_runs.summary = full text          ← UNLIMITED
    └── task_events.payload.summary = first line, 400 chars  ← HARDCODED
              ↓
    orchestrator task creation [orchestrator_daemon.py]
        ├── Design: title = user_request[:1000]
        └── Fix: title = user_request[:1000]
              ↓
        kanban_create → tasks.title = text     ← DB TEXT COLUMN (unlimited)
              ↓
    event_watcher [kanban-event-watcher.py]
        ├── title: 1000 chars
        ├── summary: 2000 chars
        ├── reason: 2000 chars
        └── error: 2000 chars
              ↓
    Telegram API max: 4096 chars total
```

## Truncation Points

| Stage | Location | Limit | What to change |
|-------|----------|-------|---------------|
| Event payload summary | `kanban_db.py:4105` | **400** chars (first line only) | Change `[:400]` to desired limit |
| Design task title | `orchestrator_daemon.py:356` | **1000** chars | Change `[:1000]` |
| Fix task title | `orchestrator_daemon.py:384` | **1000** chars | Change `[:1000]` |
| Block reason (JSON parse fallback) | `orchestrator_daemon.py:1271` | **2000** chars | Change `[:2000]` |
| Event watcher title | `kanban-event-watcher.py:168` | **1000** chars | Change `truncate(title, 1000)` |
| Event watcher summary | `kanban-event-watcher.py:186` | **2000** chars | Change `truncate(summary, 2000)` |
| Event watcher reason | `kanban-event-watcher.py:191` | **2000** chars | Change `truncate(reason, 2000)` |
| Event watcher error | `kanban-event-watcher.py:194` | **2000** chars | Change `truncate(error, 2000)` |

## Key Insight

The **400-char summary cap in `kanban_db.py:4105`** is the most common
bottleneck — the event watcher's 2000-char limit never fires because the
data is already truncated before it reaches the event table. The task_runs
table stores the full summary; only the event payload is capped.

## Service Restart

After changing any of these limits, restart the relevant service:
- `kanban-event-watcher.service` (standalone event watcher)
- `auto-development.service` (orchestrator daemon)
- `hermes-gateway.service` (for kanban_db.py changes in core Hermes)
