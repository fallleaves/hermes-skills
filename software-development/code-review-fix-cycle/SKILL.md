---
name: code-review-fix-cycle
description: "Sub-agent review + TDD fix cycles, repeated until clean."
version: 2.2.0
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
sub-agent returns zero NEW actionable findings. Each round: ONE review
sub-agent writes findings to a file; ONE fix sub-agent reads that file and
fixes everything TDD-style; the main agent verifies, appends fix status, and
commits the round report. There is NO round cap — as long as the review
sub-agent keeps finding real issues, keep the loop going.

## Setup (determine once, pass into every prompt)

- `REPO` — project root (user-specified, else current directory). All other
  paths are relative to it. If `git -C "$REPO" rev-parse --git-dir` fails,
  ask the user whether to `git init` or run degraded mode (review+fix without
  commits).
- `REVIEWS_DIR` — default `$REPO/docs/reviews`; create if missing. Round
  files: `round-<N>.md`, where N = 1 + the numeric max of existing
  `round-(\d+).md` filenames (parse the integer; ignore non-matching files),
  else 1. Do not run concurrent review-fix cycles on the same REPO.
- `TEST_CMD`, `TYPECHECK_CMD` — discover in order: package.json / Makefile /
  pyproject / scripts manifests, then CI config (.github/workflows/*.yml,
  .gitlab-ci.yml), then README. Record "no automated tests" and "no
  typecheck" INDEPENDENTLY when absent. Monorepo: one command per package,
  run for packages in the reviewed scope. If a command cannot be made
  concrete, ask the user before dispatching — never guess. If the project
  has resource constraints (e.g. parallel tests OOM), bake the safe
  invocation into every prompt.
- `SCOPE` — the file tree to review, fixed for all rounds unless the user
  changes it. Default "all source, tests, configs"; pass verbatim into every
  prompt.
- `HEAD` — `git -C "$REPO" log -1 --format=%H` at EACH round's dispatch
  (recompute every round — the fixer commits each round, so a frozen HEAD
  makes reports lie).
- `NOTES_FILE` — review sub-agent's working-notes file, default
  `$REVIEWS_DIR/review-notes.md` (≤ 5 KB), committed with the round like the
  report. Cross-round wisdom channel. Optional — its absence never blocks a
  review.

## Round loop (main agent)

1. **Review sub-agent** — `delegate_task` (leaf, background). Context MUST
   include: REPO path, HEAD, REVIEWS_DIR, TEST_CMD, TYPECHECK_CMD, NOTES_FILE
   path, SCOPE, the report format (verbatim, below), the round number N, and
   the deferred-findings list from prior rounds (if any).
   - MANDATORY first step: if a previous round file exists (highest-numbered
     in REVIEWS_DIR), read it: it holds the report format, the prior findings
     to re-verify at their sites, and the fix-status table (fixed / skipped /
     deferred). Do NOT re-report verified fixes unless regressed; do NOT
     re-report deferred findings unless their status changed (exclude them
     from the count). Round-1 bootstrap: no previous file — use the format
     from the prompt verbatim, skip re-verification, header says "first round
     — none".
   - Also read NOTES_FILE if it exists (accumulated review wisdom); MAY
     maintain it: add useful insights, remove obsolete ones, keep ≤ 5 KB
     (run `wc -c` after any write; creation is a permitted write). Reading
     the round files and NOTES_FILE is allowed; they are just never review
     TARGETS.
   - HARD constraints: READ-ONLY except writing round-<N>.md and maintaining
     NOTES_FILE; no git commits/pushes, no service restarts, no DB writes;
     run each discovered test/typecheck command once (if a run fails for an
     environmental reason, retry once and report both attempts; never report
     a run you did not complete) and report REAL pass counts; record baseline
     failures explicitly in the test-state header; never fix anything.
   - Zero findings is a VALID, EXPECTED outcome — say so plainly instead of
     inventing findings. In rounds ≥ 2, do not report pure style nits unless
     they mask a real defect.
   - Report format (follow exactly): header (date, commit reviewed = HEAD at
     dispatch, scope, relationship to previous round, test state incl.
     baseline failures) → findings summary table (CRITICAL/MAJOR/MINOR/NIT/
     Total) → per finding `### n<M>. <title>` with **File:**, **Description:**
     (evidence), **Suggested fix:** → method section (commands run, files
     inspected — written last, just above the marker) →
     `<!-- APPEND FINDINGS ABOVE THIS LINE -->`. M = finding index within the
     round, from 1. Write incrementally: header, table and marker FIRST, then
     insert findings above the marker as found. Zero-findings round still
     writes header + table (Total: 0) + marker + method.
   - Final message MUST state: the findings count explicitly ("0 findings"
     when none), and whether NOTES_FILE was created/modified.

2. **Fix sub-agent** — `delegate_task` (leaf, background). Context MUST
   include: REPO path, the round-<N>.md path, TEST_CMD, TYPECHECK_CMD, and
   the deferred-findings list.
   - First: check `git -C "$REPO" status`; IGNORE changes under REVIEWS_DIR
     (round-<N>.md and review-notes.md are expected uncommitted at this
     point). If any OTHER uncommitted changes exist, stop and report to the
     main agent rather than committing over them.
   - MANDATORY: read the findings file fully; fix findings ONE at a time with
     strict TDD — failing test FIRST (watch red), minimal fix (watch green),
     run the touched suites AND TYPECHECK_CMD. Load the
     `test-driven-development` skill if available. Run the full suite once
     BEFORE fixing to establish the baseline; "green" means baseline failures
     plus no new failures, unless a finding covers a baseline failure.
     Non-testable findings (config/docs/dependency pins): still one
     independent commit each; verification is by the next round's review
     rather than a failing test; add a regression test only where a harness
     exists.
   - Each fix = ONE independent commit on the CURRENT branch; commit subject
     MUST start with `r<N>-n<M>` (M matching the finding header). Never mix
     fixes in one commit. Never create branches, never push, never
     force-push. Stage only files touched by the current fix.
   - Regression rule: if the full suite fails after a fix, fix the regression
     as part of the same finding's commit (or an additional r<N>-n<M>-named
     commit) and re-run until green; run the full suite after the final fix
     and once more after any regression fix. Never leave the suite red.
   - Unfixable / external-dependency findings: skip with explicit
     justification. Do NOT modify the findings file — report per-finding
     outcomes in your final message instead.
   - Final message MUST contain: per-finding outcome list (r<N>-n<M> →
     fixed/skipped, with commit hash or reason) and the final test/typecheck
     state.

3. **Main agent verifies + records + commits the round**:
   - Before dispatching the fixer, validate round-<N>.md exists, contains a
     findings summary table, ends with the APPEND marker, and the count of
     `### n<M>.` headers equals the table's Total. On any failure, re-dispatch
     the review sub-agent once, then surface to the user.
   - Confirm the fixer's commits exist (`git -C "$REPO" log --grep='^r<N>-n'`)
     — match r<N>-n<M> names. If the fixer produced zero commits AND reported
     no skipped findings, re-dispatch once with the error, then report to the
     user; if zero commits but skips were reported, record the skips and
     proceed. Never commit a round report that claims fixes that do not
     exist.
   - Append a fix-status table BELOW the APPEND marker (the marker stays the
     boundary between findings and fix-status): finding id → fixed / skipped
     / deferred → commit hash (or reason). The main agent may mark a
     twice-skipped or external-dependency finding as DEFERRED; deferred items
     are recorded here AND in the deferred list for the next review prompt.
     Persist the deferred list inside round-<N>.md (a "Deferred findings"
     section) so a crashed main agent can rebuild it from the file.
   - Commit round-<N>.md and review-notes.md (if modified this round) on the
     SAME branch the fixer committed to (capture `git symbolic-ref --short
     HEAD` before dispatch; if detached, use the raw commit as anchor) as
     docs commits.
   - Summarize the round (findings count, commits, fixer-reported test state
     — unverified by the main agent; the next round's review confirms).

4. **Repeat** with fresh-context sub-agents. **STOP when a round returns
   zero NEW actionable findings** (deferred items are reported separately to
   the user). Commit round-<N>.md and review-notes.md first, then state "the
   loop is converged" and stop. There is NO round cap.

## Pitfalls

- Fresh context every round — never reuse an earlier sub-agent's assumptions.
- Resume: before computing N, check whether the highest round file lacks an
  appended fix-status table or is uncommitted; if so, finish that round
  (verify fixer commits, append table, commit) before starting a new one.
- The findings file + fix-status table + deferred list are the contract
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
