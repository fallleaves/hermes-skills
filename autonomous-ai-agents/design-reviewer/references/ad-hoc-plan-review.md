# Ad-Hoc Plan / Design Document Review

Use this pattern when the user asks you to review a refactor plan, design
document, or proposal during a Hermes conversation (as opposed to running
as an automated kanban worker — see the main SKILL.md for that workflow).

## Process

1. **Read the document** — `read_file` with the full content.

2. **Find prior review context** — Search session history with
   `session_search(query="<doc-name> review")` to find previous review
   rounds. Also check for separate review/issue-tracking files in the
   project directory with `search_files`.

3. **Verify every claim against the live codebase** — Plans can be wrong.
   For each claim in the document:
   - Function signatures → `search_files` for the `def`, then `read_file`
     to confirm parameters match what the plan says.
   - State enums / constants → verify they exist and are spelled correctly.
   - Subcommand names → read the CLI wrapper to confirm the subcommand
     is valid (`kanban_cli` → `hermes kanban <subcommand>`).
   - Bug descriptions → read the actual old code to confirm the bug
     really exists the way the plan describes it.

4. **Compare old code vs proposed new code line by line** — Read the
   existing function in full, then side-by-side with the proposed code
   in the plan. Ensure:
   - All old code cases are covered in the new code.
   - No guards or edge cases from the old code were silently dropped.
   - The new code adds strict improvements (bounds checks, dedup, etc.).

5. **Check disposition of every prior-review issue** — If the context
   mentions previous rounds, enumerate each issue and verify it is
   actually fixed in the current revision of the document.

6. **Look for issues the plan itself misses** — Read as if you're about
   to implement from the plan. Ask:
   - Are there edge cases not covered?
   - Version numbers in headers consistent with the review round?
   - Code blocks match real code style / function signatures?
   - Any side effects on shared input data (mutation)?
   - Gaps between what the plan says and what the code does?

7. **Report concisely** — State which issues are fixed, list any
   remaining issues with exact line locations, and give the final
   verdict. Keep the format consistent so it's easy to scan.

## Pitfalls

- **Don't trust the plan's claims** — always verify against actual
  code. Plan authors make mistakes about function signatures,
  subcommand names, enum values, etc.
- **Version drift** — Check that the document's stated version
  (e.g., "v2" in the title) matches the review context. A document
  at v3 that still says v2 has an inconsistent title.
- **Empty session_search results** — Don't stop; also check git log
  (`git log --oneline -- <file>`), review notes, and issue files in
  the project directory.
- **Stale code blocks** — Verify code blocks in the plan match the
  actual codebase. Plans get edited without updating embedded code.
- **Old-code edge cases the plan silently drops** — Example: the old
  code had a `parent_id != child_id` self-link guard that the new
  code doesn't replicate. Each such omission needs justification.
