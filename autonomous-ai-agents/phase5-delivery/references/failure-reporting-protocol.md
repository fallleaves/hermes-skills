# Phase 5 Failure Reporting Protocol

## Context

Starting July 2026, Phase 5 no longer creates fix tasks itself. The orchestration layer handles all fix creation and re-verification.

## New Behavior on Failure

When Phase 5 detects a build/test/merge failure:

1. **Do NOT** call kanban_create or kanban_link
2. **Do NOT** call kanban_block
3. **Report** failure to orchestrator via POST /api/v1/task/done:
   ```
   POST /api/v1/task/done
   {
     "workflow_id": "...",
     "task_id": "...",
     "task_type": "phase5_delivery",
     "status": "done",
     "result": {
       "merged": false,
       "failure": {
         "item": "npm run build fails -- ...",
         "description": "Type error in download route...",
         "design_ref": "design.md@abc123"
       }
     },
     "idempotency_key": "...",
     "source": "worker"
   }
   ```
4. Call kanban_comment with failure summary
5. Call kanban_complete with failure summary
6. Exit

## Why

- Eliminates the crash-recovery deadloop (Phase 5 tasks have no parent dependencies, so they don't block on dependency)
- Orchestrator tracks fix attempts (max 3) and creates fresh Phase 5 tasks
- Avoids polluting the kanban board with fix-link parent relationships
