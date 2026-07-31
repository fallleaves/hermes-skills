# Kanban `--parent` Dependency Behavior

> Discovered 2026-07-06 during orchestration race-condition analysis.
> Applies to any skill that creates kanban tasks with dependencies.

## Core Behavior

When a kanban task is created with `--parent <task_id>`:

| Creation mode | Initial status | Claimable? |
|---------------|----------------|------------|
| No `--parent` | `ready` | Yes — dispatcher can pick it up immediately |
| With `--parent` | `todo` | **No** — dispatcher skips `todo` tasks |

## Auto-Promotion

When the **last parent task** completes (marked Done), kanban automatically
promotes the child from `todo` to `ready` — the child becomes claimable
without any explicit action.

```
Parent created   → ready
Child (--parent) → todo      ← not claimable yet
Parent completed
Child            → ready     ← auto-promoted by kanban
```

## Race Condition Avoidance

This behavior eliminates a subtle race condition:

**Bad (two-pass):** Create all tasks (no parents), then link parents via
`kanban parent --add`. Between the two passes, a child task sits in `ready`
without its dependency being recorded. If the dispatcher ticks in the gap,
the child is claimed prematurely.

**Good (one-pass):** Create tasks in topological order, passing `--parent` at
creation time. Each child is born in `todo` — impossible for the dispatcher
to claim, regardless of timing. No second pass needed.

## Verified By Test (2026-07-06)

```python
# Test: create parent (ready), child with --parent (todo),
# complete parent, observe child auto-promotes to ready
p = kanban_create("parent")        # status: ready
c = kanban_create("child", parent=p)  # status: todo
kanban_complete(p)                 # parent done
kanban_show(c)["status"]          # → "ready" (auto-promoted)
```

## Implications for Orchestrator Daemon

- `handle_decomp_callback` must create tasks in array order, resolving
  `parent_ids` to already-created kanban IDs on the fly
- No need for a second pass to set parent links
- No race condition between creation and linking
- If a task's parent_ids reference a task that hasn't been created yet
  (violates topological order), the child is created without that parent
  link and enters `ready` prematurely — this is a bug in the decomposer

## Related

- Decomposer skill: must output task_specs array in topological order
- Developer skill: receives tasks with parents already set at create time
- Orchestrator daemon: `handle_decomp_callback` creation logic
