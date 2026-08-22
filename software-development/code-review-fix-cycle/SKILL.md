---
name: code-review-fix-cycle
description: "Sub-agent review + TDD fix cycles, repeated until clean."
version: 2.4.0
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
  ask the user whether to `git init` or run DEGRADED MODE: no commits, no
  git checks; the fix-status table records reasons instead of hashes;
  everything else (review, fix, append, repeat, stop) proceeds identically.
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
  makes reports lie). In degraded mode, HEAD is omitted.
- `NOTES_FILE` — review sub-agent's working-notes file, default
  `$REVIEWS_DIR/review-notes.md` (≤ 5 KB), committed with the round like the
  report. Cross-round wisdom channel. Optional — its absence never blocks a
  review.

## Round loop (main agent)

### Step 1 — Review sub-agent

`delegate_task` (leaf, background). The prompt MUST include: REPO path, HEAD,
REVIEWS_DIR, TEST_CMD, TYPECHECK_CMD, NOTES_FILE path, SCOPE, the round
number N, the deferred-findings list (if any), the report format verbatim
(below), the final-message contract verbatim (below), and the hard
constraints verbatim (below). Do not rely on the sub-agent reading this
skill — paste the contracts.

MANDATORY first step: if a previous round file exists (highest-numbered in
REVIEWS_DIR), read it: it holds the report format, prior findings to
re-verify at their sites, and the fix-status table (fixed / skipped /
deferred). Do NOT re-report verified fixes unless regressed; do NOT
re-report deferred findings (exclude from count). Round-1 bootstrap: no
previous file — use the format from the prompt, skip re-verification, header
says "first round — none".

Also read NOTES_FILE if it exists (accumulated review wisdom); MAY maintain
it: add useful insights, remove obsolete ones, keep ≤ 5 KB (run `wc -c`
after any write; creation is a permitted write). Reading the round files and
NOTES_FILE is allowed; they are never review TARGETS.

HARD constraints: READ-ONLY except writing round-<N>.md and maintaining
NOTES_FILE; no git commits/pushes, no service restarts, no DB writes; run
each discovered test/typecheck command once (environmental failure → retry
once, report both attempts; never report a run you did not complete); report
REAL pass counts; record baseline failures explicitly in the test-state
header; never fix anything. Zero findings is a VALID, EXPECTED outcome — say
so plainly instead of inventing findings. In rounds ≥ 2, do not report pure
style nits unless they mask a real defect.

REPORT FORMAT (follow exactly): header (date, commit reviewed = HEAD at
dispatch, scope, relationship to previous round, test state incl. baseline
failures) → findings summary table (Severity | Count rows: CRITICAL/MAJOR/
MINOR/NIT/Total) → per finding `### n<M>. <title>` with **File:**,
**Description:** (evidence), **Suggested fix:**, and — for any finding
re-reported from an earlier round — a provenance line `(reported from
round-<K> n<J>: skipped/regressed/unfixed)` where K is the IMMEDIATELY
preceding round that reported it → method section (commands run, files
inspected — written last, just above the marker) →
`<!-- APPEND FINDINGS ABOVE THIS LINE -->`. M = finding index within the
round, from 1; commit suffix uses the same M.

Write incrementally: header, table and marker FIRST; then insert each
finding above the marker as found, and UPDATE the table's counts every time
you insert a finding (the table Total must always equal the number of
`### n<M>.` headers). Final file layout for a non-zero round:
`header → table → findings → method → marker`. Zero-findings round:
`header → table (Total: 0) → method → marker` (method BEFORE the marker so
the file ends with the marker).

FINAL-MESSAGE contract (verbatim in prompt): state the findings count
explicitly ("0 findings" when none — the count of `### n<M>.` headers, which
equals the table Total), and whether NOTES_FILE was created/modified.

### Step 2 — Fix sub-agent

`delegate_task` (leaf, background). The prompt MUST include: REPO path, the
round-<N>.md path, TEST_CMD, TYPECHECK_CMD, the deferred-findings list, and
the behavioral contract verbatim (below). Do not rely on the sub-agent
reading this skill — paste the contract.

BEHAVIORAL CONTRACT (verbatim in prompt):
- First check `git -C "$REPO" status`; IGNORE changes under REVIEWS_DIR
  (round-<N>.md and review-notes.md are expected uncommitted here). If any
  OTHER uncommitted changes exist, stop and report "ABORTED: dirty tree" to
  the main agent.
- Read the findings file fully; fix findings ONE at a time with strict TDD —
  failing test FIRST (watch red), minimal fix (watch green), run the touched
  suites AND TYPECHECK_CMD after each fix. Load the
  `test-driven-development` skill if available. Run the full suite once
  BEFORE fixing to establish the baseline; "green" = baseline failures plus
  no new failures, unless a finding covers a baseline failure.
- Non-testable findings (config/docs/dependency pins, or code with NO test
  harness available): still one independent commit each; verification is by
  the next round's review; add a regression test only where a harness exists
  cheaply; state "no harness" as the verification method.
- Each fix = ONE independent commit on the CURRENT branch; commit subject
  MUST start with `r<N>-n<M>` (M matching the finding header). Never mix
  fixes in one commit. Never create branches, never push, never force-push.
  Stage only files touched by the current fix.
- Regression rule: if the full suite fails after a fix, fix the regression
  as part of the same finding's commit (or an additional r<N>-n<M>-named
  commit) and re-run until green; run the full suite after the final fix and
  once more after any regression fix. Never leave the suite red.
- Unfixable / external-dependency findings: skip with explicit
  justification. The deferred list is context only — deferred findings never
  appear in the file and you must not touch them.
- Do NOT modify the findings file.
- FINAL-MESSAGE contract: per-finding outcome list (r<N>-n<M> → fixed /
  skipped, with commit hash or reason) and the final test/typecheck state.

### Step 3 — Main agent verifies + records + commits

- If the reviewer's final message is missing or unparsable, re-dispatch the
  review sub-agent once, then surface to the user (if the file's table Total
  is 0 and no count is available, treat it as a zero-findings round after
  one re-dispatch).
- If the reviewer's count is 0 (zero findings): SKIP validation and the
  fixer. Commit round-<N>.md and review-notes.md (if modified) on the same
  branch, state convergence, and stop — do NOT start another round. A
  zero-findings round gets NO fix-status table (no fixer ran) and NO
  commits; the file is committed exactly as the reviewer wrote it (this
  signature is the convergence marker — see Resume in Pitfalls).
- Otherwise, before dispatching the fixer, validate round-<N>.md exists,
  contains a findings summary table, ends with the APPEND marker, and the
  count of `### n<M>.` headers equals the table's Total. On any failure,
  re-dispatch the review sub-agent once, then surface to the user.
- After the fixer returns, confirm its commits exist. Verify by hash when
  the final message provides one (`git cat-file -e "<hash>"`); otherwise
  fall back to `git -C "$REPO" log --grep='^r<N>-n'` for findings without
  a stated hash. Content correctness is confirmed by the next round's
  review. Decision tree:
  - All findings have matching commits → proceed.
  - Zero commits AND no skips reported → re-dispatch once; if the re-dispatch
    also produces zero commits with no skips, report to the user.
  - Zero commits AND skips reported → record the skips, proceed.
  - Some fixed + some skipped, outcomes present → record fixed rows with
    their hashes, skipped rows with reasons; apply the deferral rule per
    skipped row; proceed.
  - Some findings have no matching commit AND no outcome in the final message
    → record them as UNFIXED (reason: "no commit"), commit the round, let
    the next round re-report them.
  - Outcome says "fixed" but no matching commit exists → record UNFIXED
    (reason: "no commit").
  - Fixer reported "ABORTED: dirty tree" → do NOT re-dispatch; surface the
    dirty-tree state to the user and wait.
  - Final message missing or unparsable → re-dispatch the fixer once with
    the previous final message text plus "resume: findings already committed
    this round (check git log --grep r<N>-n<M>) are done — report them with
    their existing hash; fix only the remainder"; if the re-dispatch also
    fails, surface to the user.
  Never commit a round report that claims fixes that do not exist.
- Append a fix-status table BELOW the APPEND marker (the marker stays the
  boundary between findings and fix-status):
  `| id | status | commit/reason |` with rows like `| n1 | fixed | r2-n1 abc1234 |`.
  The main agent may edit the status column of its own appended rows (e.g.
  change "skipped" to "deferred") before committing.
- Deferral rule: mark a finding DEFERRED when it is skipped in two
  CONSECUTIVE rounds under the same provenance (both re-reports chain to
  the same original round-K n<J>; the status token is ignored for
  matching), or it is an external-dependency item. Deferred items are
  recorded here AND in a "Deferred findings" section (format: `- r<N>-n<M>
  <title> (<file>) — reason`). The deferred list passed to future rounds =
  the UNION of all Deferred sections across prior round files INCLUDING
  the just-written round-N.md. Deferred items stay excluded until the user
  removes them or a fix commit references their r<N>-n<M> id — the main
  agent checks this at each round's dispatch.
- Re-report tracking: persist the consecutive-re-report count in the round
  file so a crash/resume does not reset it. Add a "Re-report tracking"
  section below the Deferred section, e.g. `- r1-n2 → r2-n3 → r3-n1 (3
  consecutive, origin round-1 n2)`. The main agent updates it each round by
  following provenance chains back to the origin. On resume, reconstruct
  the counts from these sections across prior files.
- Commit round-<N>.md and review-notes.md (if modified this round) on the
  SAME branch the fixer committed to (capture `git symbolic-ref --short
  HEAD` before dispatch; if detached, use the raw commit as anchor) as docs
  commits. In degraded mode: skip all git steps; the table records reasons
  instead of hashes; the fixer skips its git-status check and reports
  outcomes as `fixed (no hash) / skipped: reason`; the decision tree
  replaces the commit-existence check with presence of a per-finding
  outcome in the final message.
- Summarize the round (findings count, commits, fixer-reported test state —
  unverified by the main agent; the next round's review confirms).

### Step 4 — Repeat / stop

Repeat with fresh-context sub-agents. STOP when a round's findings count
(table Total) is 0 — re-reported findings count as findings and drive
deferral, never the stop condition. Deferred items are reported separately
to the user: the main agent lists them in the final convergence summary as
`- r<N>-n<M> <title> (<file>) — reason`, noting they were excluded from
review. Commit round-<N>.md and review-notes.md first, then state "the loop
is converged" and stop. There is NO round cap.

Termination guarantee for stubborn findings: track re-report counts by
provenance. If the SAME finding (matched by provenance/title+file) is
re-reported for 3 consecutive rounds, the main agent either marks it
deferred (with user notice) or surfaces it to the user and stops the loop.

## Pitfalls

- Fresh context every round — never reuse an earlier sub-agent's assumptions.
- Resume: before computing N, check whether the highest round file lacks an
  appended fix-status table or is uncommitted. If its summary table shows
  Total: 0, treat the round as CONVERGED: verify the commit exists, do NOT
  re-dispatch the fixer, do NOT append a table, finish. Otherwise, if it
  has no fix-status table AND no r<N>-n commits exist, re-dispatch the
  fixer first; only then append the table and commit. Finish that round
  before starting a new one.
- The findings file + fix-status table + deferred list are the contract
  between the two sub-agents; the review sub-agent must write it
  incrementally and keep the summary table in sync.
- Real numbers only: report actual test/typecheck output, never fabricated
  counts; never report a run you did not complete.
- Stage only intended files — never commit build artifacts, logs, or
  untracked junk; review-notes.md is committed with the round like the
  report.
- Keep the review sub-agent read-only except the two allowed files (the round
  report and NOTES_FILE); any other write invalidates the round's
  independence. NOTES_FILE is bounded at 5 KB — run `wc -c` after any write,
  trim or consolidate when near the limit.
- Round numbering: compute N by PARSING the numeric max of existing
  `round-(\d+).md` filenames (e.g. `ls "$REVIEWS_DIR" | grep -oE
  'round-[0-9]+' | sed 's/round-//' | sort -n | tail -1`) — NEVER by an
  alphabetical `ls | tail`, which sorts round-100 BEFORE round-11 and hides
  high-numbered files mid-list. A new review series started inside an
  existing REVIEWS_DIR (new target, same dir) can silently OVERWRITE legacy
  round files whose reports are still committed: verify the true max first
  and number the new series from max+1; if a legacy file was already
  overwritten, restore it from git history (`git checkout <old-commit> --
  <file>`) and renumber the new reports, adding a renumbering note at the
  top of each (fix-commit subjects keep their original r<N>-n<M> labels for
  traceability).
- If `delegate_task` is unavailable, perform the review/fix steps inline with
  equivalent separation (read-only review pass, then fix pass), preserving
  the file contract.
