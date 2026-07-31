# Iterative Design Review by Sub-agent

When reviewing a design document (architecture plan, design doc, API spec),
use this iterative sub-agent pattern to reach zero findings.

## Process

1. **Initial review**: Dispatch a reviewer sub-agent with full context
   (design doc + all related files + user requirements).

2. **Fix findings**: Review the structured report, address each P0/P1/F
   finding by updating the design document.

3. **Re-dispatch**: Dispatch a NEW reviewer sub-agent with the updated
   doc. Do NOT ask the user for permission — just iterate.

4. **Repeat** until the reviewer reports zero P0, zero P1, zero format
   issues. The dispatch should include all prior findings so the reviewer
   can verify they were resolved.

5. **Final sign-off**: Only when zero findings, present to user.

## Key rules

- Each round gets its OWN sub-agent (fresh context, no bias from previous
  rounds). Include the fix log so the new reviewer knows what was done.
- The reviewer follows 5 dimensions: Completeness, Correctness, Consistency,
  Feasibility, Robustness.
- "Zero P0, zero P1, zero format issues" is the pass criterion.
- NEVER ask the user "should I dispatch another round". Just do it.
  The user has explicitly stated this preference across multiple sessions.

## Example dispatch context for round N+1

Include:
- Full updated design doc
- List of all prior findings and how each was fixed
- Any specific areas the user wants re-checked
- Review dimensions to evaluate
