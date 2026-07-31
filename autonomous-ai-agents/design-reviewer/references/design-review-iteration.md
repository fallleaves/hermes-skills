# Iterative Design Review with Sub-Agents

Use this when you (as the assistant) need to validate a complex design
document by dispatching sub-agent review rounds. Extends the reviewer
skill's P0/P1/P2 scoring into an automated iteration loop.

## When to Use

- The design involves nontrivial state machine, concurrency, or data flow
- Multiple components interact and must be self-consistent
- Edge cases, failure modes, or recovery paths need thorough verification
- The user explicitly asks for review iteration (
  "让sub agent review，重复直到零问题")
- The document will serve as a specification for implementation

Do NOT use for: simple one-page plans, routine tasks, or quick designs
where sub-agent overhead outweighs review value.

## Workflow

```
Step 1: Write the design document to a project path
     |
Step 2: Dispatch a sub-agent as reviewer
     |   delegate_task(goal="Review this design document")
     |   with structured criteria + scoring rubric
     |
Step 3: Read the review report from sub-agent
     |   → Zero findings? → Present to user, done.
     |   → Has findings? → Fix each finding in the document
     |       |  (do NOT ask user for permission between rounds)
     |       |  (if user said "repeat until zero", just iterate)
     |       ▼
     Step 4: Re-dispatch sub-agent with:
     |       - Updated document (already saved to disk)
     |       - Context: what was fixed from previous round
     |       - Same criteria + scoring rubric
     |       → Go to Step 3
     |
     (Repeat until zero issues or P0/P1=0, P2<3)
```

## Review Prompt Structure

### Context Section

Provide enough context so the sub-agent knows what changed:

```text
## 设计文档路径
`<path/to/design-doc.md>`

## 背景
这是第 N 轮审阅。上一轮发现了以下问题，现在应已全部修复：

### P0 (已修复)
- **P0-1**: <what was fixed>

### P1 (已修复)
- **P1-1**: <what was fixed>

...

## 审阅要求
请从以下维度审阅：
1. **完整性**：方案描述是否完整？有无遗漏的关键场景？
2. **正确性**：状态机转换逻辑是否正确？有没有状态/事件组合的漏处理？
3. **一致性**：与现有代码的风格、命名、接口是否兼容？
4. **可行性**：每项变更是否可实施？有没有实现上的坑？
5. **安全性**：幂等问题？死循环风险？竞态条件？
6. **边界情况**：重启恢复、并发、超时、降级路径？

## 评分标准
- **P0**: 逻辑错误，会导致系统故障或数据丢失
- **P1**: 重要遗漏，会影响系统健壮性
- **P2**: 次要问题，建议改进

## 输出格式
```markdown
## 审阅报告

### P0 问题
...

### P1 问题
...

### P2 问题
...

### 总结
通过/不通过
```
```

### Review Dimensions

Adapt the 5 standard review dimensions as needed:

| Dimension | What to check |
|-----------|---------------|
| **Completeness** | All scenarios covered? Any missing states/transitions? |
| **Correctness** | State machine transitions valid? Logic flows correctly? |
| **Consistency** | Same concepts named consistently across doc? Compatible with existing system? |
| **Feasibility** | Can every described change be implemented? Hidden dependencies? |
| **Safety** | Idempotency? Race conditions? Deadlock? Recovery paths? |

## Pass Criteria

Same as the reviewer skill:
- **P0 = 0** (no blockers)
- **P1 = 0** (no high-severity issues)
- **P2 < 3** (fewer than 3 minor issues)

## Pitfalls

- **Callback routing**: When the design involves multiple state-dependent
  callback handlers (like the Phase 5 redesign), ensure the reviewer checks
  that callbacks are routed by both `current_state` AND `task_type`, not
  by state alone. Pure state-based routing causes cross-timing bugs.
- **Recovery paths**: Any design relying on HTTP callbacks must also
  specify a recovery/fallback path for callback loss (polling, persistence).
- **sub-agent can't see memory**: The sub-agent gets zero session context.
  Put everything in the `context` field — file path, prior findings, fix
  summary, language preference.
- **Don't ask between rounds**: When the user says "repeat until zero",
  dispatch each round automatically. Only escalate if the same finding
  persists for 3+ rounds (impasse signal).
- **Results must be verifiable**: If the sub-agent claims the design fails
  review but doesn't cite specific locations, re-dispatch with stricter
  instructions about evidence requirements.
