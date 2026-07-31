# Design Review Iteration Protocol

## Flow

```
Round 1 Review FAIL
  → Fixer applies fixes across all 4 artifacts
  → Sub-agent review (with updated pass criteria)
  → If FAIL: fix again → re-dispatch review
  → Repeat until PASS
  → Human approval gate
```

## Pass Criteria (user preference, hard requirement)

**PASS only when: P0=0 AND P1=0 AND P2<3**

All three conditions must be met. Any P1 or P2 >= 3 means FAIL.

## Escalating Strictness

- Round 1: obvious correctness gaps (P0/P1)
- Round 2: subtle inconsistencies, edge cases
- Round 3: maximum scrutiny — any imprecision

## Common Iteration Traps

1. **Cross-document sync failure** — fixing design.md but forgetting api-spec.yaml generates a guaranteed P1 in the next round.
2. **YAML indentation** — the most common self-inflicted P1. Always validate `yaml.safe_load()` after patching api-spec.yaml.
3. **NF numbering gaps** — deleting or inserting NFs without renumbering creates a consistency finding.
4. **Response example drift** — schema has field but response example in design.md doesn't show it.
5. **Fixing the symptom, not the root** — a finding about "missing 403 on upload" means check ALL four endpoints, not just upload.

## Sub-Agent Dispatch Template

When dispatching a review sub-agent outside the daemon workflow:

```
delegate_task(
    goal="Review the updated design documents for <feature>",
    context="Pass criteria: P0=0, P1=0, P2<3. Read these 4 files: ..."
)
```

Do NOT ask the user "shall I dispatch another round" — just do it. Iterate until zero findings, then present the final result.
