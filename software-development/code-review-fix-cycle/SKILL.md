---
name: code-review-fix-cycle
description: "Sub-agent review + TDD fix cycles, repeated until clean."
version: 1.0.0
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
TDD-style; the main agent verifies and commits the round report.

## Setup (determine once, pass into every prompt)

- `REPO` — project root (user-specified, else current directory).
- `REVIEWS_DIR` — default `docs/reviews`; create if missing. Round files:
  `round-<N>.md`, where N = 1 + highest existing number.
- `TEST_CMD`, `TYPECHECK_CMD` — discover from package.json / Makefile /
  pyproject / scripts; must be concrete before dispatching. If the project
  has resource constraints (e.g. parallel tests OOM), bake the safe
  invocation into every prompt.
- `HEAD` — `git -C "$REPO" log -1 --format=%H`.
- `NOTES_FILE` — review sub-agent's working-notes file, default
  `$REVIEWS_DIR/agents.md` (≤ 5 KB). Maintained by the review sub-agent
  itself across rounds: add insights that help future reviews, remove
  entries that are obsolete or wrong. Optional — its absence never blocks
  a review.

## Round loop (main agent)

1. **Review sub-agent** — `delegate_task` (leaf, background). Context MUST include:
   - REPO path, HEAD, REVIEWS_DIR, TEST_CMD, TYPECHECK_CMD.
   - MANDATORY first step: read the previous round file (round-<N-1>.md) —
     it holds the report format and the prior findings to re-verify at their
     sites (do NOT re-report verified fixes unless regressed). Also read
     NOTES_FILE if it exists — it carries accumulated review wisdom from
     earlier rounds.
   - MAY maintain NOTES_FILE (agents.md, ≤ 5 KB): record anything that will
     help future review rounds — project-specific bug patterns, recurring
     classes, useful probe techniques, pitfalls. Maintain it yourself: add
     what is useful, remove what is obsolete or wrong, keep it under 5 KB.
   - Scope: the explicit file tree to review (all source, tests, configs).
   - HARD constraints: READ-ONLY except writing round-<N>.md and
     maintaining NOTES_FILE; no git commits/pushes, no service restarts,
     no DB writes; run the test and typecheck commands once and report REAL
     pass counts; never fix anything.
   - Report format (follow exactly): header (date, commit reviewed, scope,
     relationship to previous round, test state) → findings summary table
     (CRITICAL/MAJOR/MINOR/NIT/Total) → per finding `### n<N>. <title>` with
     **File:**, **Description:** (evidence), **Suggested fix:** → method
     section → `<!-- APPEND FINDINGS ABOVE THIS LINE -->`.
     Write incrementally — a crash mid-review must not lose findings already
     found.

2. **Fix sub-agent** — `delegate_task` (leaf, background). Context MUST include:
   - REPO path, the round-<N>.md path, TEST_CMD, TYPECHECK_CMD.
   - MANDATORY: read the findings file fully; fix findings ONE at a time with
     strict TDD — failing test FIRST (watch red), minimal fix (watch green),
     run the touched suites. Load the `test-driven-development` skill if
     available.
   - Each fix = ONE independent commit on the working branch; message names
     the round+item (`r<N>-n<M>`). Never mix fixes in one commit.
   - After the batch: run TEST_CMD and TYPECHECK_CMD in full — no regressions.
     External-dependency issues: skip with explicit justification.
   - Do NOT modify the findings file.

3. **Main agent verifies + commits the round**: confirm the fixer's commits
   exist (`git -C "$REPO" log`), commit round-<N>.md as a docs commit, then
   summarize the round (findings count, commits, test state).

4. **Repeat** with fresh-context sub-agents. **STOP when a round returns zero
   findings** — state it explicitly and stop.

## Pitfalls

- Fresh context every round — never reuse an earlier sub-agent's assumptions.
- The findings file is the contract between the two sub-agents; the review
  sub-agent must write it incrementally.
- Real numbers only: report actual test/typecheck output, never fabricated
  counts.
- Stage only intended files — never commit build artifacts, logs, or
  untracked junk in the repo.
- Keep the review sub-agent read-only except the two allowed files (the
  round report and NOTES_FILE); any other write invalidates the round's
  independence. NOTES_FILE is bounded at 5 KB — trim or consolidate when
  near the limit.
