# Orchestrator Daemon Callback Contract

All worker skills report completion to the daemon via `POST /api/v1/task/done`.
The daemon reads specific keys from `result` depending on `task_type`.
Wrong keys are silently ignored -- workflow stalls.

## Common Payload

```json
{
  "workflow_id": "wf-<8hex>",
  "task_id": "t_<8hex>",
  "task_type": "orchestrator_design|reviewer|orchestrator_fix|decomposer|developer_code|qa_test|phase5_delivery",
  "status": "done",
  "result": { "...": "task-type-specific keys" },
  "idempotency_key": "<wf_id>-<task_id>",
  "source": "worker"
}
```

## Per-task-type `result` Keys

| task_type | Daemon reads from `result` | Behaviour |
|-----------|---------------------------|-----------|
| `orchestrator_design` | `epic` (str), `artifacts` (dict with `requirements`, `design`, `api_spec` keys) | Empty/falsy `artifacts` = retry (up to 3). Valid = create reviewer task. |
| `reviewer` | `passed` (bool), `findings` (list), `review_round` (int) | `passed=true` = block for human approval. `passed=false` = create fix task. |
| `orchestrator_fix` | `review_round` (int), `artifacts` (dict) | Creates a new reviewer task with incremented round. |
| `decomposer` | **`tasks`** (list) -- NOT `task_specs` / `task_list` | Each task spec: `{title, skill, body, parent_ids, idempotency_key}`. |
| `developer_code` | None (pass-through) | Passed to child callback handler. |
| `qa_test` | `passed` (bool), `bug_report` (dict with `description`) | `passed=false` + bug_fix workflow = create fix. |
| `phase5_delivery` | None (pass-through) | Triggers completion check. |

## Idempotency

Every callback must include a unique `idempotency_key`. The daemon stores
processed keys in the workflow JSON (`callback_idempotency_keys`). If the
same key arrives again (due to network retry or daemon restart), the
callback is silently dropped. Use `{wf_id}-{task_id}` as the base and
append a discriminator for retries: `{wf_id}-{task_id}-{round}`.

## Known Pitfall: Approval Gate

When the reviewer passes, the daemon calls
`kanban_block_task(wf.task_ids[0])` to block the design task for human
approval. However, the design task is already `done` -- kanban cannot
block a completed task. The workflow enters `waiting_approval` but
nothing blocks the user from the kanban side.

To proceed past `waiting_approval`, the user must call:
```
POST /api/v1/task/unblocked
{ "workflow_id": "wf-...", "task_id": "t_...", "task_type": "orchestrator_design",
  "idempotency_key": "wf-...-approval", "source": "human" }
```

Or the daemon's internal poller detects the unblock event if a task is
actually blocked and later unblocked.
