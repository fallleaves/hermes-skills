---
name: code-review-fix-cycle
description: "Sub-agent review + TDD fix cycles, repeated until clean."
version: 2.1.1
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [code-review, tdd, sub-agent, iterative-review]
    related_skills: [test-driven-development, requesting-code-review]
triggers:
  - User asks to run the review-fix cycle / iterative code review on a project
  - User says "review round" or references a round-N.md findings file
  - User wants the codebase driven to a clean review state
---

# Code Review-Fix Cycle

## When to Use

Use when the user wants the codebase driven to a clean review state via
iterative rounds: review → fix → repeat. Also triggered by "review round",
"review-fix cycle", or an existing round-N.md findings file. One-shot
pre-commit reviews belong to `requesting-code-review`; this skill is the
multi-round loop.

Drive a codebase to a clean review state by repeating rounds until a review
sub-agent returns zero findings. Each round: ONE review sub-agent writes
findings to a file; ONE fix sub-agent reads that file and fixes everything
TDD-style; the main agent verifies, records fix status, and commits the round
report.

## Setup (determine once, pass into every prompt)

- `REPO` — project root (user-specified, else current directory). All other
  paths are relative to it.
- `REVIEWS_DIR` — default `$REPO/docs/reviews`; create if missing. Round
  files: `round-<N>.md`, where N = 1 + the highest existing round number in
  REVIEWS_DIR (else 1). Do not run concurrent review-fix cycles on the same
  REPO.
- `TEST_CMD`, `TYPECHECK_CMD` — discover in order: package.json / Makefile /
  pyproject / scripts manifests, then CI config (.github/workflows/*.yml,
  .gitlab-ci.yml), then README. If none exist: record "no automated tests
  exist" in the round report rather than inventing counts. Monorepo: one
  test command per package, run for packages in the reviewed scope. If a
  command cannot be made concrete, ask the user before dispatching — never
  guess. If the project has resource constraints (e.g. parallel tests OOM),
  bake the safe invocation into every prompt.
- `HEAD` — `git -C "$REPO" log -1 --format=%H`.
- `NOTES_FILE` — review sub-agent's working-notes file, default
  `$REVIEWS_DIR/review-notes.md` (≤ 5 KB), committed with the round like
  the report. Cross-round wisdom channel: add insights that help future
  reviews, remove obsolete entries. Optional — its absence never blocks
  a review. NOTE: do NOT name it agents.md — that basename is protected
  by Hermes (prompt-injection gate, always-ask approval) and a sub-agent
  cannot write it.

## Round loop (main agent)

1. **Review sub-agent** — `delegate_task` (leaf, background). Context MUST
   include: REPO path, HEAD, REVIEWS_DIR, TEST_CMD, TYPECHECK_CMD, NOTES_FILE
   path, the report format (verbatim, below), and the round number N.
   - MANDATORY first step: if a previous round file exists (the highest-
     numbered one in REVIEWS_DIR — usually round-<N-1>.md), read it: it holds
     the report format and the prior findings to re-verify at their sites (do
     NOT re-report verified fixes unless regressed — the fix-status table the
     main agent appended tells you which were fixed/skipped/deferred).
     Round-1 bootstrap: no previous file exists — use the format from the
     prompt verbatim, skip re-verification, set the header's "relationship
     to previous round" to "first round — none".
   - Also read NOTES_FILE if it exists (accumulated review wisdom); MAY
     maintain it: add useful insights (project-specific bug patterns,
     recurring classes, probe techniques, pitfalls), remove obsolete ones,
     keep ≤ 5 KB — run `wc -c` after any write and trim if needed. Creation
     is a permitted write. Do NOT review the round files, NOTES_FILE, or
     your own artifacts.
   - Scope: the explicit file tree to review (all source, tests, configs),
     excluding .git, dependency dirs (node_modules, vendor, .venv), build/
     dist artifacts, and REVIEWS_DIR itself.
   - HARD constraints: READ-ONLY except writing round-<N>.md and maintaining
     NOTES_FILE; no git commits/pushes, no service restarts, no DB writes;
     run the test and typecheck commands once (if a run fails for an
     environmental reason — not a code failure — retry once and report both
     attempts; never report a run you did not complete) and report REAL pass
     counts; never fix anything.
   - Zero findings is a VALID, EXPECTED outcome — if the codebase is clean,
     say so plainly instead of inventing findings. In rounds ≥ 2, do not
     report pure style nits unless they mask a real defect.
   - Report format (follow exactly): header (date, commit reviewed, scope,
     relationship to previous round, test state) → findings summary table
     (CRITICAL/MAJOR/MINOR/NIT/Total) → per finding `### n<M>. <title>` with
     **File:**, **Description:** (evidence), **Suggested fix:** → method
     section → `<!-- APPEND FINDINGS ABOVE THIS LINE -->`. M is the finding's
     index within the round, numbered from 1 — it matches the fixer's commit
     suffix. Write incrementally: header, summary table and the APPEND marker
     FIRST, then insert each finding above the marker as found. A zero-
     findings round still writes the header + table (Total: 0) + marker.
   - Final message MUST state the findings count explicitly ("0 findings"
     when none).

2. **Fix sub-agent** — `delegate_task` (leaf, background). Context MUST
   include: REPO path, the round-<N>.md path, TEST_CMD, TYPECHECK_CMD, and
   the deferred-findings list from previous rounds (if any).
   - First: check `git -C "$REPO" status` is clean; if there are uncommitted
     changes, stop and report to the main agent rather than committing over
     them.
   - MANDATORY: read the findings file fully; fix findings ONE at a time with
     strict TDD — failing test FIRST (watch red), minimal fix (watch green),
     run the touched suites. Load the `test-driven-development` skill if
     available.
   - Each fix = ONE independent commit on the CURRENT branch; message names
     the round+item (`r<N>-n<M>`, M matching the finding header). Never mix
     fixes in one commit. Never create branches, never push, never
     force-push. Stage only files touched by the current fix.
   - Regression rule: if the full suite fails after a fix, the batch is not
     done — fix the regression as part of the same finding's commit (or an
     additional r<N>-n<M>-named commit) and re-run until green. Never leave
     the suite red; never report a round as complete with failing tests.
   - Unfixable / external-dependency findings: skip with explicit
     justification, and report them in your final message (by n<M> id +
     reason). Do NOT modify the findings file — report per-finding outcomes
     in your final message instead.
   - Do NOT touch NOTES_FILE.

3. **Main agent verifies + records + commits the round**:
   - Before dispatching the fixer, validate round-<N>.md exists, contains a
     findings summary table, and ends with the APPEND marker. If not,
     re-dispatch the review sub-agent once, then surface to the user.
   - Confirm the fixer's commits exist (`git -C "$REPO" log`) — match
     r<N>-n<M> names. If the fixer produced zero commits, re-dispatch once
     with the error, then report to the user; never commit a round report
     that claims fixes that do not exist.
   - Append a fix-status table to round-<N>.md (main agent owns this — the
     fixer never modifies the file): finding id → fixed / skipped / deferred
     → commit hash (or reason). This makes "do NOT re-report verified fixes"
     mechanically actionable for the next round.
   - Commit round-<N>.md (and review-notes.md if the reviewer
     created/updated it this round) on the SAME branch the fixer committed
     to as docs commits. Record the deferred list for the next review
     prompt.
   - Summarize the round (findings count, commits, fixer-reported test state
     — unverified by the main agent; the next round's review confirms).

4. **Repeat** with fresh-context sub-agents. **STOP when a round returns
   zero findings** — state it explicitly and stop. There is NO round cap:
   as long as the review sub-agent keeps finding real issues, keep the loop
   going.

## Pitfalls

- Fresh context every round — never reuse an earlier sub-agent's assumptions.
- The findings file + the main agent's fix-status table are the contract
  between the two sub-agents; the review sub-agent must write it
  incrementally.
- Real numbers only: report actual test/typecheck output, never fabricated
  counts; never report a run you did not complete.
- Stage only intended files — never commit build artifacts, logs, or
  untracked junk; review-notes.md is committed with the round like the
  report.
- Keep the review sub-agent read-only except the two allowed files (the
  round report and NOTES_FILE); any other write invalidates the round's
  independence. NOTES_FILE is bounded at 5 KB — run `wc -c` after any write,
  trim or consolidate when near the limit.
- If `delegate_task` is unavailable, perform the review/fix steps inline with
  equivalent separation (read-only review pass, then fix pass), preserving
  the file contract.
