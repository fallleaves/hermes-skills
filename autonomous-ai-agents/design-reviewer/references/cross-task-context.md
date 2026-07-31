# Cross-Task Context Discovery

> How a Reviewer agent discovers what happened in previous review rounds.

## Problem

The orchestration layer creates each reviewer task independently. When the
reviewer runs on round 2 (or later), its task body contains only:

- `artifacts` — file paths to the updated design documents
- `review_round` — the current round number (2, 3, …)
- `max_review_rounds`

It does NOT receive:
- Previous round's findings
- What fixes were applied

However, the reviewer must verify that previous-round issues were addressed.
Without that context, it can only re-review the current state — it cannot
confirm "fixes verified".

## Solution: Kanban CLI Lookup

The reviewer has `terminal` access and can query the kanban board for related
tasks. The discovery flow is:

```
1. Get workflow_id from own task body
2. terminal("hermes kanban list --json") → find sibling tasks
3. terminal("hermes kanban show <fix_task_id> --json") → get fix task data
4. Fix task body contains "review_feedback" (previous findings)
5. Fix task result contains "fixes_applied" (what was changed)
6. read_file on updated artifacts → verify each fix is present
```

### Step-by-step

```python
import os, json, subprocess

# 1. Get workflow_id from own task
task_data = kanban_show(os.environ["HERMES_KANBAN_TASK"])
body = json.loads(task_data["task"]["body"])
workflow_id = body["workflow_id"]
review_round = body.get("review_round", 1)

if review_round > 1:
    # 2. List all tasks and find fix tasks for this workflow
    result = terminal("hermes kanban list --json")
    all_tasks = json.loads(result["output"])

    # 3. Find tasks belonging to this workflow
    fix_tasks = []
    for t in all_tasks:
        t_body = json.loads(t.get("body", "{}"))
        if t_body.get("workflow_id") == workflow_id and "fix" in t.get("title", "").lower():
            fix_tasks.append(t)

    # 4. Read fix task body for review_feedback
    for ft in fix_tasks:
        ft_data = terminal(f"hermes kanban show {ft['id']} --json")
        ft_body = json.loads(json.loads(ft_data["output"])["task"]["body"])
        previous_findings = ft_body.get("review_feedback", [])

        # 5. Each finding has severity, title, location, detail, fix
        for finding in previous_findings:
            # 6. Read the artifact at the specified location
            artifact_content = read_file(finding["location"].split("#")[0])
            # Verify fix is applied in the current document
            # ...
```

## Important Notes

- The fix task's **body** contains `review_feedback` (the findings from the
  previous round that triggered the fix).
- The fix task's **result** (from kanban_show's task result field, or via the
  orchestrator API) contains `fixes_applied` — a human-readable list of changes.
- The orchestrator's workflow state is also available via
  `curl http://localhost:9876/api/v1/workflows/{workflow_id}` — this returns
  the full history including all task results.
- Never assume the fix task exists. It may have timed out or been garbage
  collected. Check before accessing.
- The fix task may not exist on round 1 — only round 2+ reviewers need this.
