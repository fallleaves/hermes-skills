# Plan-Review-Iterate Workflow

A pre-implementation quality gate for any refactoring or architecture change affecting auto-devops-monitored services.

## Workflow

Repeat until zero issues found:

1. **Write the plan** — comprehensive change plan document (config, scripts, systemd units all covered)
2. **Dispatch sub-agent review** — `delegate_task()` with the full plan as context. Ask the sub-agent to find ALL issues, edge cases, gaps, and inconsistencies. Be specific about what to check: dependency analysis, backward compatibility, credential migration, monitoring impact, error handling, pre-existing bugs.
3. **Fix all findings** — address every issue found. Update the plan document. Critical and moderate first, then minor/trivial.
4. **Re-dispatch** — repeat from step 2. The sub-agent re-reviews to confirm previous issues are resolved and checks for new ones.
5. **Stop when PASS** — only proceed to implementation when the sub-agent explicitly says "zero issues" or "PASS — ready for implementation".

## Key Rules

- **Do NOT ask the user for permission between rounds.** Fix and re-dispatch silently. The user has explicitly requested this workflow (see memory: "不要再问了，自己去迭代直到零问题").
- **Each round must re-check ALL previous issues** to ensure no regression.
- If the same issue persists for 3+ rounds, stop and escalate to the user — something is fundamentally underspecified.
- If the user says "这个不需要review了，直接做" (skip review), skip directly to implementation.

## Why This Works

- Catches design flaws before any code is written
- Prevents wasted implementation effort on wrong approaches
- Distributed review catches blind spots the author missed
- Automated iteration avoids human bottleneck between rounds
