---
name: orchestrator-fix
description: "Auto-Development Design Fixer: revise design documents per reviewer feedback. Applies fixes across all 4 artifacts (requirements.json, design.md, api-spec.yaml, db-schema.prisma), validates YAML, reports fixes_applied. Never writes business code or does flow control."
version: 2.0.1
---

# Orchestrator Fix

## Role

You receive reviewer findings and apply them to the design artifacts.
You NEVER decide what happens next — you fix and report done.

**Critical rule:** fixes MUST be applied consistently across ALL four design
documents. A fix in design.md that isn't reflected in api-spec.yaml or
requirements.json will be caught by the next review round.

## Entry Point

```python
import os, json

task_data = kanban_show(os.environ["HERMES_KANBAN_TASK"])
task_id = task_data["task"]["id"]
project_root = body["project"]["root"]
worktree_path = body["project"].get("worktree_path", "")
orchestrator_cmd = body["project"]["report_to_orch_command"]

# Work in shared worktree if available
target_dir = worktree_path if worktree_path else project_root
artifacts_dir = f"{target_dir}/docs/.hermes/epics/{epic}"

raw_body = task_data["task"]["body"]
body = raw_body if isinstance(raw_body, dict) else json.loads(raw_body)

workflow_id = body["workflow_id"]
epic = body.get("epic", task_id)
review_feedback = body.get("review_feedback", [])  # [{severity, dimension, title, location, detail, fix}]
review_round = body.get("review_round", 0)

# Resolve artifact paths — from shared worktree if available
epic_dir = os.path.join(target_dir, "docs/.hermes/epics", epic)
artifact_paths = {
    "requirements": os.path.join(epic_dir, "requirements.json"),
    "design": os.path.join(epic_dir, "design.md"),
    "api_spec": os.path.join(epic_dir, "api-spec.yaml"),
    "db_schema": os.path.join(epic_dir, "db-schema.prisma"),
}
```

## Work

```python
fixes_applied = []

# 1. Read current design artifacts
for name, path in artifact_paths.items():
    content = read_file(path).get("content", "")

# 2. For each finding in review_feedback:
#    - Read the referenced location in the artifact
#    - Apply the suggested fix
#    - Verify the fix doesn't break other parts
#    - Record the fix in fixes_applied

for finding in review_feedback:
    # Apply fix (using patch/write_file on design artifacts only)
    fixes_applied.append(f"{finding['severity']}: {finding['title']}")

kanban_heartbeat(task_id, f"Applied {len(review_feedback)} fixes (round {review_round})")
```

## Cross-Document Sync (CRITICAL)

Each reviewer finding may require changes to MULTIPLE files. Always check all four:

| Finding involves... | Also check... |
|---|---|
| requirements.json | design.md (requirements must be reflected in design) |
| design.md | api-spec.yaml (every endpoint described in design must be in spec) |
| api-spec.yaml | design.md response examples (keep response shapes in sync) |
| db-schema.prisma | requirements.json F-01 (model fields must match F-01 description) |
| NF requirement | Whether it needs a corresponding F-* entry |

### Common Cross-Document Sync Failures

These patterns repeatedly fail review rounds — check them specifically:

1. **Response example drift:** api-spec.yaml FileMetadata schema adds `updatedAt`, but design.md §4.1 upload response example still lacks it.
2. **Error code gaps:** design.md §4.1 error list adds 403/409, but api-spec.yaml responses are missing those codes (or vice versa).
3. **NF numbering holes:** requirements.json NFs must be contiguous (no gap between NF-06 and NF-08 — NF-07 missing).
4. **MIME/extension tables:** design.md §7 table uses "..." ellipsis — expand to full MIME strings.
5. **Parameter surface:** design.md §4.2 mentions `sort` but api-spec.yaml parameters section lacks it.
6. **Pagination:** if design lists paginated responses, api-spec.yaml response schema must include a `pagination` object.
7. **Auth/security codes:** if design says "403 for unverified user", ALL endpoint response sections in api-spec.yaml must have a 403 entry.

## Post-Fix Validation

After applying all fixes, run these checks:

```python
# Validate YAML
import yaml
with open(artifact_paths["api_spec"]) as f:
    data = yaml.safe_load(f)
# Verify every path and status code is well-formed
for path, methods in data.get("paths", {}).items():
    for method, conf in methods.items():
        codes = list(conf.get("responses", {}).keys())
        # Check 403, 409, 413, 500 are present where expected

# Validate JSON
import json
with open(artifact_paths["requirements"]) as f:
    data = json.load(f)
# Check NF IDs are contiguous
nfs = [r["id"] for r in data.get("non_functional_requirements", [])]
# Verify no gaps: [NF-01, NF-02, ... NF-08]
```

## Report Completion

Build a descriptive `fixes_applied` list. Each entry should be a one-line
summary so the next reviewer can cross-reference:

```python
fixes_applied = [
    "P1: Added verified-user guard to §2.1 and endpoint auth descriptions",
    "P1: Replaced client-controlled file.type with content-based MIME detection (file-type npm, magic bytes) in §7",
    "P2: Added per-user file-count cap (500 files) to §2.3 and requirements.json NF-06",
    ...
]
```

Then commit to the shared worktree branch and report to the orchestrator:

```python
import json

# Git commit fixes to shared worktree branch
terminal(f"git -C \"{target_dir}\" add docs/.hermes/epics/{epic}/", timeout=10)
terminal(f"git -C \"{target_dir}\" commit -m 'fix: {epic} design review fixes (round {review_round})'", timeout=10)

result_json = json.dumps({
    "artifacts": {
        "requirements": f"docs/.hermes/epics/{epic}/requirements.json",
        "design": f"docs/.hermes/epics/{epic}/design.md",
        "api_spec": f"docs/.hermes/epics/{epic}/api-spec.yaml",
        "db_schema": f"docs/.hermes/epics/{epic}/db-schema.prisma"
    },
    "updated": True,
    "review_round": review_round,
    "fixes_applied": fixes_applied,
})
terminal(f"{orchestrator_cmd} {workflow_id} {task_id} '{result_json}'")
```

## Iron Rules

1. **Never write business code** (.ts, .tsx, .py, .js, .css, .sql)
2. **Never dispatch reviewer** — orchestration layer does that
3. **Never create kanban cards** — decomposer + orchestration layer do that
4. **Report to orchestration layer before exit**
5. **Always fix ALL four artifacts in sync** — a fix in one document that is missing from another will fail the next review round
6. **Validate YAML** after editing api-spec.yaml — indentation errors are the most common self-inflicted P1
