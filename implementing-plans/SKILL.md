---
name: implementing-plans
description: "End-to-end implementation workflow — writing plans, executing via subagents, two-stage review, verification pipeline, TDD, and systematic debugging. Use when building software from a spec, executing multi-step tasks, or doing pre-commit verification."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Implementation, Planning, Subagent, TDD, Debugging, Code-Review, Verification, Execution]
    umbrella: true
---

# Implementing Plans — End-to-End Software Development Workflow

This umbrella covers the full implementation lifecycle: **planning → subagent execution → review → verification → debugging → commit**.

## Quick Decision Tree

| Phase | § to use |
|-------|----------|
| Write/create an implementation plan from requirements | § Writing-Plans |
| Execute a plan by dispatching subagents per task | § Subagent-Driven-Development |
| Pre-commit verification: security scan + tests + independent reviewer | § Requesting-Code-Review |
| Write a plan summary document | § Plan |
| Test-driven development cycle | § Test-Driven-Development |
| Debug a failing system systematically | § Systematic-Debugging |
| Quick feasibility experiment before committing to build | § Spike (references/spike.md) |

---

## § Writing-Plans

**Use for:** Write a structured implementation plan from user requirements. Converts vague requirements into a detailed, actionable, sequenced task list.

**Prerequisites:** Understand the full scope of what needs to be built before writing the plan.

**Full skill:** `software-development/writing-plans/SKILL.md`

**Core method:** User requirements → decompose into tasks → sequence tasks → identify risks → write the plan file.

**Key rules:**
- Write the plan BEFORE implementing
- One task = 2-5 minutes of focused work
- Identify what must be true before each task (dependencies)
- Risk-first: the hardest/riskiest task goes first

## § Subagent-Driven-Development

**Use for:** Execute an implementation plan by dispatching fresh subagents per task with systematic two-stage review.

**Core principle:** Fresh subagent per task + two-stage review (spec compliance then code quality) = high quality, fast iteration.

**Full skill:** `software-development/subagent-driven-development/SKILL.md`

**The per-task workflow:**
1. Dispatch implementer subagent with complete task context
2. Dispatch spec compliance reviewer → fix gaps if needed
3. Dispatch code quality reviewer → fix issues if needed
4. Mark task complete → proceed to next

**Key rules:**
- Fresh subagent per task (prevents context pollution)
- Spec compliance review FIRST, code quality SECOND (wrong order = compounding issues)
- Never skip reviews
- Two-stage review catches issues before they compound

**Integration with requesting-code-review:** The two-stage review IS the code review. The `requesting-code-review` pipeline provides the pre-commit verification layer applied to your own changes before committing.

## § Requesting-Code-Review

**Use for:** Pre-commit verification pipeline — static security scan, baseline-aware quality gates, independent reviewer subagent, and auto-fix loop. Run after implementing a feature or bug fix, before `git commit` or `git push`.

**Full skill:** `software-development/requesting-code-review/SKILL.md`

**Core principle:** No agent should verify its own work. Fresh context finds what you miss.

**The pipeline:**
1. Get the diff (`git diff --cached`)
2. Static security scan (hardcoded secrets, shell injection, SQL injection, dangerous eval/exec, unsafe deserialization)
3. Baseline tests and linting (stash → run baseline → pop → compare)
4. Self-review checklist
5. Independent reviewer subagent (FAIL-CLOSED: unparseable response = fail)
6. Auto-fix loop (max 2 cycles, third agent fixes only the reported issues)
7. Commit with `[verified]` prefix

**This vs github-code-review:** This skill verifies YOUR changes before committing. `github-code-review` reviews OTHER people's PRs on GitHub.

## § Plan

**Use for:** Plan mode for Hermes — inspect context, write a markdown plan, execute via subagent-driven-development.

**Full skill:** `software-development/plan/SKILL.md`

## § Test-Driven-Development

**Use for:** Red/Green/Refactor cycle — write failing test first, implement minimal code, verify pass, refactor.

**Full skill:** `software-development/test-driven-development/SKILL.md`

**Integration:** TDD is the discipline that `subagent-driven-development` implementers should follow. Include TDD instructions in every implementer context.

## § Systematic-Debugging

## § Systematic-Debugging

**Use for:** Debug failing systems methodically — reproduce, hypothesize, isolate, verify fixes.

**Core loop:** Reproduce → Hypothesize → Isolate → Verify → Fix → Confirm

**Full skill:** `software-development/systematic-debugging/SKILL.md`

**Core principle:** NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST. Symptom fixes are failure. Always find the root cause before attempting any fix.

**The Four Phases:**
1. **Phase 1: Root Cause Investigation** — Read error messages carefully, reproduce consistently, check recent changes, trace data flow, gather evidence at component boundaries
2. **Phase 2: Pattern Analysis** — Find working examples, compare against references, identify differences, understand dependencies
3. **Phase 3: Hypothesis and Testing** — Form single hypothesis, test minimally, verify before continuing. After 3 failed fixes: question architecture
4. **Phase 4: Implementation** — Create failing test case first, implement single fix, verify fix, if 3+ fixes failed → question architecture with user

**Bug patterns captured:**
- Stale closure with Zustand store state (captured values at mount time)
- `proper-lockfile` throws ENOENT on non-existent paths
- `fs.unlink`/`fs.readFile` on directory throws EISDIR
- ETag mtime instability causing 409 conflicts
- Lazy tree `loadedChildren` cache + `expandedSet` inconsistency
- Manual button for auto-detectable system condition
- Wikilink `.md` extension not stripped before node ID lookup

**Integration:** If a subagent encounters bugs during implementation, follow `systematic-debugging` to find root cause before fixing. Write regression test, then resume.

## § Test-Driven-Development

**Use for:** Red/Green/Refactor cycle — write failing test first, implement minimal code, verify pass, refactor.

**Full skill:** `software-development/test-driven-development/SKILL.md`

**The Iron Law:** NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.

**Cycle:**
1. **RED** — Write failing test. Watch it fail. Verify failure is for the right reason.
2. **GREEN** — Minimal code to pass. Nothing extra. Hardcoding is OK.
3. **REFACTOR** — Clean up. Keep tests green. Don't add behavior.

**Key rules:**
- Don't keep code "as reference" — delete and implement fresh
- If you didn't watch the test fail, you don't know if it tests the right thing
- If ≥ 3 fixes failed: question architecture, don't continue guessing
- Every bug found → write failing test reproducing it before fixing

**Integration:** TDD is the discipline that `subagent-driven-development` implementers should follow. Include TDD instructions in every implementer context.

## § Writing-Plans

**Use for:** Write a structured implementation plan from user requirements. Converts vague requirements into a detailed, actionable, sequenced task list.

**Full skill:** `software-development/writing-plans/SKILL.md`

**Core principle:** A good plan makes implementation obvious. If someone has to guess, the plan is incomplete.

**Prerequisites:** Understand the full scope of what needs to be built before writing the plan.

**Key rules:**
- Write the plan BEFORE implementing
- One task = 2-5 minutes of focused work
- Identify what must be true before each task (dependencies)
- Risk-first: the hardest/riskiest task goes first
- Include exact file paths, complete code examples, exact commands with expected output
- Apply DRY, YAGNI, TDD principles

**Execution:** After writing the plan, offer to execute using `subagent-driven-development`.

## § Plan

**Use for:** Plan mode for Hermes — inspect context, write a markdown plan into the active workspace's `.hermes/plans/` directory, and do not execute the work.

**Full skill:** `software-development/plan/SKILL.md`

**Core behavior:**
- Planning only for this turn — no implementation, no mutations
- Inspect repo with read-only tools when needed
- Deliverable: markdown plan saved under `.hermes/plans/YYYY-MM-DD_HHMMSS-<slug>.md`
- If task is underspecified, ask a clarifying question

### Pitfall: Tab-Type vs. Overlay Modal in wiki-webui

When implementing a view that should "fill the center tab area and behave like the graph view," implement it as a **tab type** (like `graph`), NOT as a Zustand `*Open` overlay state.

**The distinction:**
- **Tab type** (`type: 'graph' | 'requests'`): Rendered inside `MarkdownEditor` via a `type` check. Sits in the tab history. Supports back/forward navigation. The tab bar shows an icon and label. Full access to sidebars and status bar.
- **Overlay modal** (`quickSwitcherOpen`, `fullSearchOpen`, etc.): Rendered in `page.tsx` outside the center area with `position: fixed`. Acts as a transient interruption. Does not appear in tab history.

**Wrong approach (overlay):**
```tsx
// page.tsx — WRONG for tab-like behavior
{ui.requestsOpen && <RequestsPanel onClose={() => setRequestsOpen(false)} />}
```

**Correct approach (tab type) — 4 files to touch:**
1. **Store** (`useWikiStore.ts`): Add `'requests'` to `HistoryEntry.type`, `Tab.type`, and `UIState`. Add `openRequestsTab()` action that sets `type: 'requests'` on the current tab, deduplicates history.
2. **TabBar** (`components/TabBar/TabBar.tsx`): Add `isRequests` check and icon for `type === 'requests'` tabs.
3. **MarkdownEditor** (`components/Editor/MarkdownEditor.tsx`): Add `if (activeTab.type === 'requests')` check rendering the panel inline (before the file/empty-state checks).
4. **LeftVerticalBar** (`components/LeftVerticalBar/LeftVerticalBar.tsx`): Button calls `openRequestsTab()` not `setRequestsOpen(true)`.

**Pattern reference:** See `implementing-plans/references/wiki-webui-tab-types.md`

---

## § Request-Folder-Workflow (Autonomous Agent with Human-in-the-Loop)

**Use for:** Building autonomous agents that run on a schedule (cron), produce output files for human review, and deliver summaries via Telegram (or other channels). Not git-commit-then-push — output stays in a request folder for human decision.

**Core pattern:**
1. Cron fires → agent picks up work from INBOX
2. Creates per-request isolated folder (IN_PROGRESS/{req-id}/)
3. Does research or implementation inside the folder
4. Writes required NOTE.md summary + readiness assessment
5. Moves folder to DONE/ or DECLINED/
6. Output delivered to origin (Telegram, etc.)

**Key design decisions for this pattern:**
- **Per-request folder isolation** — every request stays in its own `{req-id}/` folder throughout lifecycle; avoids collisions and makes batch review easy
- **Required NOTE.md** — even declined requests get one; contains status, file inventory, readiness, open questions
- **Wiki-ready output** — files follow wiki conventions but are NOT committed; human reviews and decides
- **No git commits** — output is staged for human review, not auto-committed
- **Zero mid-flight interaction** — agent does its best, notes open questions in NOTE.md, moves on

**Related skill:** `wiki-structured-entity-ingest` implements the research engine for this pattern when the request is a feature/topic-research type.

**Full reference:** `implementing-plans/references/request-folder-workflow.md`

---

## § Spike (Reference: `references/spike.md`)

**Use for:** Throwaway experiments to validate an idea before committing to a real build. Spikes are disposable — throw them away once they've paid their debt.

**Trigger phrases:** "let me try this", "I want to see if X works", "spike this out", "quick prototype of Z", "is this even possible?", "compare A vs B".

**NOT for:** The answer is knowable from docs (just research), the work is production path (use `writing-plans`), the idea is already validated (jump to implementation).

**Core method:** Decompose → Research → Build → Verdict

**Full reference:** `implementing-plans/references/spike.md`

---

## Sub-Skill Reference

| Sub-skill | Location | Status |
|-----------|----------|--------|
| subagent-driven-development | `software-development/subagent-driven-development/SKILL.md` | Absorbed → § Subagent-Driven-Development |
| requesting-code-review | `software-development/requesting-code-review/SKILL.md` | Absorbed → § Requesting-Code-Review |
| writing-plans | `software-development/writing-plans/SKILL.md` | Absorbed → § Writing-Plans |
| plan | `software-development/plan/SKILL.md` | Absorbed → § Plan |
| test-driven-development | `software-development/test-driven-development/SKILL.md` | Absorbed → § Test-Driven-Development |
| systematic-debugging | `software-development/systematic-debugging/SKILL.md` | Absorbed → § Systematic-Debugging |
| spike | Moved to `references/spike.md` | Demoted → § Spike (reference) |
| debugging-hermes-tui-commands | `software-development/debugging-hermes-tui-commands/SKILL.md` | Standalone — Hermes-specific debugging |
| hermes-agent-skill-authoring | `software-development/hermes-agent-skill-authoring/SKILL.md` | Standalone — Hermes-specific authoring |
| node-inspect-debugger | `software-development/node-inspect-debugger/SKILL.md` | Standalone — Node.js debugging |
| python-debugpy | `software-development/python-debugpy/SKILL.md` | Standalone — Python debugging |
