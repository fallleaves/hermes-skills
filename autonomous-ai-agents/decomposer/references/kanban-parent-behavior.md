# Kanban Parent-Child Behavior

## Creation

- `kanban create --parent <parent_id>` → child status = **`todo`**
- `kanban create` without `--parent` → child status = **`ready`**

## Lifecycle

```
Parent created → ready
                   ↓
Child created with --parent → todo (dispatcher will NOT claim)
                   ↓
Parent completed → parent done
                   ↓
Child auto-promotes: todo → ready (dispatcher CAN claim)
```

## Why Single-Pass Creation Matters

The orchestrator daemon's `handle_decomp_callback` creates child tasks after
decomposition. It must create them in topological order (decomposer guarantees
this via array ordering) and pass `--parent` at creation time.

Two-pass approach (create all, then link) is **broken** because:
1. Tasks are created as `ready` before parent links are set — dispatcher can
   claim a child prematurely
2. The old `kanban_cli("task", "parent", ...)` used a **non-existent subcommand**
   (`task` is not valid; the correct command is `kanban link`). Parent
   dependencies were never actually created.

## Pitfalls

- **Cyclic dependencies**: If a cycle somehow exists, the backward reference
  (higher index not yet created) is silently dropped — the task becomes `ready`
  when it should be `todo`. The dependency graph is silently corrupted, not
  gracefully degraded. The decomposer's cycle check is the proper guard.
- **String-type parent_ids** (by `idempotency_key`): MUST also respect
  topological order (reference only earlier tasks), otherwise silently dropped.
- **Deduplication**: If `parent_ids` contains the same reference twice,
  deduplicate before passing to `kanban_create_task`.
