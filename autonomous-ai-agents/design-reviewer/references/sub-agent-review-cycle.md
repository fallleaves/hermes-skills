# Sub-Agent Review Cycle

## When to Use

Use this pattern when you produce a design document, implementation plan,
or specification and need a thorough review before presenting it to the user.

## The Pattern

### Step 1: Write the document

Write a complete, self-contained document. Include:
- Problem statement (context for the reviewer)
- Proposed solution design
- Code snippets or pseudo-code where relevant
- Risk analysis

### Step 2: Dispatch a sub-agent review

Use `delegate_task` with a detailed review brief. Include:

```
DELEGATE BRIEF MUST INCLUDE:
- File path to the document being reviewed
- Review dimensions (see Step 3)
- Severity classification (P0/P1/P2)
- What changed since last round (for iterative reviews)
- Output format specification
- Language: match the user's language (e.g., Chinese)
```

### Step 3: Review dimensions

Apply the same 7 dimensions as the reviewer skill:
1. Completeness — any missing scenarios?
2. Correctness — state transitions, logic?
3. Consistency — naming, conventions?
4. Feasibility — implementable?
5. Security — idempotency, isolation?
6. Code Consistency — aligns with existing codebase?
7. Safety & Resilience — timeout, recovery, persistence?

### Step 4: Iterate

After receiving review results:
1. Fix ALL findings (P0, P1, and P2)
2. Re-dispatch WITHOUT asking the user for permission
3. In the next round's context, list what was fixed so the reviewer can verify

### Step 5: Converge to zero

Keep the cycle running until the sub-agent reports zero issues (PASS).
Only then present the final result to the user.

## DO NOT

- Ask the user "shall I dispatch another round" — just do it
- Stop after fixing only P0 issues — fix P1 and P2 too
- Present intermediate results — only present when zero issues
- Repeat the same round context without noting what changed
