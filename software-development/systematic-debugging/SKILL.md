---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior. 4-phase root cause investigation — NO fixes without understanding the problem first.
version: 1.2.0
author: Hermes Agent (adapted from obra/superpowers)
license: MIT
metadata:
  hermes:
    tags: [debugging, troubleshooting, problem-solving, root-cause, investigation]
    related_skills: [test-driven-development, writing-plans, subagent-driven-development]
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

---

## Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

### 1. Read Error Messages Carefully

- Don't skip past errors or warnings
- They often contain the exact solution
- Read stack traces completely
- Note line numbers, file paths, error codes

**Action:** Use `read_file` on the relevant source files. Use `search_files` to find the error string in the codebase.

### 2. Reproduce Consistently

- Can you trigger it reliably?
- What are the exact steps?
- Does it happen every time?
- If not reproducible → gather more data, don't guess

**Action:** Use the `terminal` tool to run the failing test or trigger the bug:

```bash
# Run specific failing test
pytest tests/test_module.py::test_name -v

# Run with verbose output
pytest tests/test_module.py -v --tb=long
```

### 3. Check Recent Changes

- What changed that could cause this?
- Git diff, recent commits
- New dependencies, config changes

**Action:**

```bash
# Recent commits
git log --oneline -10

# Uncommitted changes
git diff

# Changes in specific file
git log -p --follow src/problematic_file.py | head -100
```

### 4. Gather Evidence in Multi-Component Systems

**WHEN system has multiple components (API → service → database, CI → build → deploy):**

**BEFORE proposing fixes, add diagnostic instrumentation:**

For EACH component boundary:
- Log what data enters the component
- Log what data exits the component
- Verify environment/config propagation
- Check state at each layer

Run once to gather evidence showing WHERE it breaks.
THEN analyze evidence to identify the failing component.
THEN investigate that specific component.

### 5. Trace Data Flow

**WHEN error is deep in the call stack:**

- Where does the bad value originate?
- What called this function with the bad value?
- Keep tracing upstream until you find the source
- Fix at the source, not at the symptom

**Action:** Use `search_files` to trace references:

```python
# Find where the function is called
search_files("function_name(", path="src/", file_glob="*.py")

# Find where the variable is set
search_files("variable_name\\s*=", path="src/", file_glob="*.py")
```

### Phase 1 Completion Checklist

- [ ] Error messages fully read and understood
- [ ] Issue reproduced consistently
- [ ] Recent changes identified and reviewed
- [ ] Evidence gathered (logs, state, data flow)
- [ ] Problem isolated to specific component/code
- [ ] Root cause hypothesis formed

**STOP:** Do not proceed to Phase 2 until you understand WHY it's happening.

---

## Phase 2: Pattern Analysis

**Find the pattern before fixing:**

### 1. Find Working Examples

- Locate similar working code in the same codebase
- What works that's similar to what's broken?

**Action:** Use `search_files` to find comparable patterns:

```python
search_files("similar_pattern", path="src/", file_glob="*.py")
```

### 2. Compare Against References

- If implementing a pattern, read the reference implementation COMPLETELY
- Don't skim — read every line
- Understand the pattern fully before applying

### 3. Identify Differences

- What's different between working and broken?
- List every difference, however small
- Don't assume "that can't matter"

### 4. Understand Dependencies

- What other components does this need?
- What settings, config, environment?
- What assumptions does it make?

---

## Phase 3: Hypothesis and Testing

**Scientific method:**

### 1. Form a Single Hypothesis

- State clearly: "I think X is the root cause because Y"
- Write it down
- Be specific, not vague

### 2. Test Minimally

- Make the SMALLEST possible change to test the hypothesis
- One variable at a time
- Don't fix multiple things at once

### 3. Verify Before Continuing

- Did it work? → Phase 4
- Didn't work? → Form NEW hypothesis
- DON'T add more fixes on top

### 4. When You Don't Know

- Say "I don't understand X"
- Don't pretend to know
- Ask the user for help
- Research more

---

## Phase 4: Implementation

**Fix the root cause, not the symptom:**

### 1. Create Failing Test Case

- Simplest possible reproduction
- Automated test if possible
- MUST have before fixing
- Use the `test-driven-development` skill

### 2. Implement Single Fix

- Address the root cause identified
- ONE change at a time
- No "while I'm here" improvements
- No bundled refactoring

### 3. Verify Fix

```bash
# Run the specific regression test
pytest tests/test_module.py::test_regression -v

# Run full suite — no regressions
pytest tests/ -q
```

### 4. If Fix Doesn't Work — The Rule of Three

- **STOP.**
- Count: How many fixes have you tried?
- If < 3: Return to Phase 1, re-analyze with new information
- **If ≥ 3: STOP and question the architecture (step 5 below)**
- DON'T attempt Fix #4 without architectural discussion

### 5. If 3+ Fixes Failed: Question Architecture

**Pattern indicating an architectural problem:**
- Each fix reveals new shared state/coupling in a different place
- Fixes require "massive refactoring" to implement
- Each fix creates new symptoms elsewhere

**STOP and question fundamentals:**
- Is this pattern fundamentally sound?
- Are we "sticking with it through sheer inertia"?
- Should we refactor the architecture vs. continue fixing symptoms?

**Discuss with the user before attempting more fixes.**

This is NOT a failed hypothesis — this is a wrong architecture.

---

## Common Bug Patterns

### Pattern: Stale Closure with Zustand Store State

**Symptom:** A callback (e.g., `useCallback`) works correctly when first used but stops working after navigating/changing files. The behavior is tied to the old state value, not the current one.

**Root Cause:** React's `useCallback` captures values from when the component mounted. If `activeFile` is read from the Zustand store via destructuring at render time (`const { activeFile } = useWikiStore()`), the `useCallback` dependency array captures that initial value. When the store's `activeFile` changes (e.g., after `openFile`), the callback still uses the old value.

**Example of broken code:**
```tsx
// ❌ BROKEN: activeFile captured at mount time
const handleCursorChange = useCallback((lineNumber: number) => {
  const lines = activeFile.content.split('\n') // always uses first file's content!
  // ...
}, [activeFile?.content]) // stale dep

// ❌ BROKEN: autoSave closure has stale activeFile reference
const handleChange = useCallback((value: string) => {
  updateActiveFileContent(value)
  if (settings.autoSave) {
    saveTimeout.current = setTimeout(() => saveFile(value), 1000) // path lost!
  }
}, [updateActiveFileContent, settings.autoSave])
```

**Correct fix — read from store at call time:**
```tsx
// ✅ CORRECT: read from store at call time, not closure time
const handleCursorChange = useCallback((lineNumber: number) => {
  const { activeFile: af } = useWikiStore.getState() // always fresh
  if (!af) return
  const lines = af.content.split('\n') // uses CURRENT file's content
  // ...
}, []) // empty deps — no stale closure risk

// ✅ CORRECT: inline the store read at call time
const handleChange = useCallback((value: string) => {
  updateActiveFileContent(value)
  if (settings.autoSave) {
    if (saveTimeout.current) clearTimeout(saveTimeout.current)
    saveTimeout.current = setTimeout(async () => {
      const { activeFile: af } = useWikiStore.getState()
      if (af) await saveFile(af.path, value) // always has current path
    }, 1000)
  }
}, [updateActiveFileContent, settings.autoSave])
```

**When to apply:** Any `useCallback` or event handler that reads from a Zustand store AND is used after a navigation/state-change operation. Key tell: the bug manifests after the first file navigation or state change, not on initial load.

---

### Pattern: Synchronous Zustand `set()` Fails for Tab-Type Navigation (graph/requests)

**Symptom:** History navigation via `goBack()` works for file→back (async fetch) but not for graph→back or requests→back (synchronous local set). The back button is enabled, clicking it does nothing visible — no error, no flash, no navigation. Forward navigation from requests→graph also fails. Going back from a file to graph/requests works fine.

**Root Cause:** The synchronous `set()` state update appears to complete without error, but React re-renders with the previous state. The function IS called (logs fire), `entry.type` IS correct, and the `set()` callback IS returning new state. The state appears correct inside the `set()` callback but doesn't propagate to the rendered UI.

**Key diagnostic:** File→back uses async `fetch()` with `.then()` chaining — the second `set()` fires after the fetch resolves. Graph→back uses synchronous `set()` directly. The timing difference between synchronous and asynchronous state updates in React may be relevant — the async path benefits from React's scheduling while the sync path may batch differently.

**Debugging approach:**
```typescript
// Add console.log BEFORE set (verifies function called) and INSIDE set callback (verifies state transformation)
if (entry.type === 'graph' || entry.type === 'requests') {
  console.log('[goBack] graph/requests path — entry.type:', entry.type, 'newIndex:', newIndex, 'activeTabId:', activeTabId)
  set((state) => {
    const newTabs = state.tabs.map((t) =>
      t.id === activeTabId
        ? { ...t, type: entry.type === 'graph' ? 'graph' as const : 'requests' as const, path: null, content: '', etag: '', isDirty: false, historyIndex: newIndex }
        : t
    )
    console.log('[goBack] set callback — new tab type:', newTabs.find(t => t.id === activeTabId)?.type, 'new historyIndex:', newTabs.find(t => t.id === activeTabId)?.historyIndex)
    return { tabs: newTabs, activeFile: null }
  })
}
```

**Hypothesis to test:** Force the set into a microtask to let React's batching settle:
```typescript
// Test: wrap in Promise.resolve().then() to defer
if (entry.type === 'graph' || entry.type === 'requests') {
  Promise.resolve().then(() => {
    set((state) => ({
      tabs: state.tabs.map((t) =>
        t.id === activeTabId
          ? { ...t, type: entry.type === 'graph' ? 'graph' as const : 'requests' as const, path: null, content: '', etag: '', isDirty: false, historyIndex: newIndex }
          : t
      ),
      activeFile: null,
    }))
  })
}
```

If the microtask version works, the issue is React's automatic batching behavior with synchronous state updates. If it still fails, the issue is deeper (store selector staleness, component re-render blocking, etc.).

**Apply when:** `goBack()`/`goForward()` work for file tabs but not for graph/requests tabs. The only difference in the code path is synchronous `set()` vs async `fetch().then(set)`.

---

### Pattern: `proper-lockfile` Throws ENOENT on Non-Existent Paths

**Symptom:** Creating a new file or renaming to a new path fails with "File is being accessed. Try again." (WRITE_FAILED). The file/folder does not exist yet.

**Root Cause:** `proper-lockfile`'s `lock()` internally calls `fs.lstat()` on the target path to check if it exists before creating the lockfile. For non-existent paths, `lstat` throws `ENOENT`, which is re-thrown as the generic "being accessed" error.

```ts
// ❌ BROKEN: lock() throws ENOENT for new files
unlock = await lock(fullPath, { retries: { retries: 3, minTimeout: 100 }, stale: 15000 })
```

**Correct fix — check existence before locking:**
```ts
// For new files (write route): check if file exists first
const fileExists = await fs.access(fullPath).then(() => true).catch(() => false)
if (fileExists) {
  unlock = await lock(fullPath, { retries: { retries: 3, minTimeout: 100 }, stale: 15000 })
}

// For rename to new path: only lock target if it already exists
if (newExists) {
  unlockNew = await lock(fullNewPath, { retries: { retries: 3, minTimeout: 100 }, stale: 15000 })
}
```

**Apply to:** Any route using `proper-lockfile` where the target path may not exist (create, rename-to-new-path).

---

### Pattern: `fs.unlink`/`fs.readFile` on Directory Throws EISDIR

**Symptom:** Renaming or deleting a directory fails with "Internal error" (EISDIR: illegal operation on a directory, read).

**Root Cause:** `fs.unlink()` only works on files — on directories it throws `EISDIR`. Similarly, `fs.readFile()` on a directory throws `EISDIR`. The code path doesn't distinguish between files and directories.

```ts
// ❌ BROKEN: unlink fails on directories
await fs.unlink(fullPath) // EISDIR for directories

// ❌ BROKEN: readFile fails on directories
content = await fs.readFile(fullPath, 'utf-8') // EISDIR for directories
```

**Correct fix — check type before operation:**
```ts
// For delete: use fs.rm with recursive for directories
const stat = await fs.stat(fullPath)
if (stat.isDirectory()) {
  await fs.rm(fullPath, { recursive: true, force: true })
} else {
  await fs.unlink(fullPath)
}

// For rename: use fs.rename for directories (atomic, preserves nested content)
if (oldIsDir) {
  await fs.rename(fullOldPath, fullNewPath)
} else {
  // file logic: read, rewrite wikilinks, write, unlink old
}
```

**Apply to:** Any file operation route that handles both files and directories. Always check `stat.isDirectory()` before choosing the fs method.

**Symptom:** Auto-save or Cmd+S triggers a "file was modified" alert even when the file wasn't modified externally. It fires on every save attempt after the first one.

**Root Cause:** Server computes ETag as `MD5(content + mtime)`. After writing a file, the server returns `MD5(content + mtime_after_write)`. The client stores this new ETag and sends it in `If-Match` on the next save. But the server reads the file and gets `mtime` which may differ slightly from the one used post-write, causing a hash mismatch → 409 conflict.

```ts
// ❌ BROKEN: mtime changes between write and subsequent read
const etag = createHash('md5')
  .update(content + stat.mtimeMs) // mtime is unstable across operations
  .digest('hex')
```

**Correct fix — content-only hash:**
```ts
// ✅ CORRECT: stable hash from content only
const etag = createHash('md5')
  .update(content)
  .digest('hex')
```

**Apply to:** Both `/api/files/read` (ETag generation) and `/api/files/write` (ETag comparison). The client should also store the returned ETag from each successful write, since that is the authoritative hash for the content that was just saved.

---

### Pattern: Lazy Tree `loadedChildren` Cache + `expandedSet` Inconsistency

**Symptom:** After creating/rename/delete a file inside an expanded folder, the tree shows stale content or the expand arrow becomes inconsistent with what's rendered (e.g., arrow points down but no children shown; or folder auto-collapses unexpectedly on certain browsers).

**Root Cause:** The file tree uses two separate state structures:
- `expandedSet: Set<string>` — which folders are currently expanded (controls arrow direction and whether children render)
- `loadedChildren: Map<string, TreeEntry[]>` — cached child entries per expanded folder

When a file operation happens inside an expanded folder, the operation may invalidate `loadedChildren` (delete cache entry) but leave `expandedSet` unchanged, OR may call `loadRoot()` (which sets `loading=true`) and reset `entries` at the root level, causing the whole tree to briefly re-render and lose context.

**Correct fix — re-fetch children immediately on mutation:**

When a file is created/renamed/deleted in a nested folder, do NOT just `delete` the cache entry (causes flash of empty) and do NOT just call `loadRoot()` (causes unnecessary full reload + potential state loss). Instead, immediately re-fetch the folder's children and update `loadedChildren` with the new sorted entries:

```tsx
// ✅ CORRECT: re-fetch immediately so folder stays open with correct content
const res = await fetch(`/api/files/list?path=${encodeURIComponent(dirPath)}`)
const data = await res.json()
if (data.entries) {
  const sorted = data.entries
    .filter((e: TreeEntry) => e.name !== '.git')
    .sort((a: TreeEntry, b: TreeEntry) => {
      if (a.type !== b.type) return a.type === 'directory' ? -1 : 1
      return a.name.localeCompare(b.name)
    })
  setLoadedChildren((prev) => {
    const next = new Map(prev)
    next.set(dirPath, sorted)
    return next
  })
}
```

**When `loadRoot()` IS needed:** Only when the root-level entries themselves may have changed (creating/renaming/deleting a root-level file).

**When to invalidate without re-fetch:** When creating a new folder — just delete the parent's cache entry so it re-fetches naturally on next expand. No need to force a re-fetch since the new folder isn't visible until expansion anyway.

**Cross-browser timing differences:** React's state batching can cause `expandedSet` and `loadedChildren` to update in slightly different orders on different browsers. Always ensure both are updated together atomically — don't rely on one to compensate for the other.

**Apply to:** Any lazy-loaded tree component that caches children in a Map separate from the expansion state.

---

### Pattern: Manual Button for a Problem the System Can Detect Automatically

**Context:** User proposes a feature with a manual action (button, shortcut) to solve a problem. Upon analysis, the system can detect the condition automatically without user intervention.

**Symptom:** The feature "works" technically, but users won't use it because they don't know *when* to trigger it. The button/shortcut gets ignored and the original problem (external file changes going unnoticed) persists.

**Root Cause:** The design asks users to do work that computers are better at — continuously monitoring a condition. Users can't know when an external change occurred without checking, so they never check.

**Examples from real implementations:**
- ❌ "Add a refresh button to detect external file changes" → users never know when to click it
- ❌ "Press Ctrl+R to sync" → users forget, or don't know sync failed
- ❌ "Click to update the cache" → stale data persists until user action

**Correct approach — auto-detect + notify:**
```
User goal: "Be warned when a file changes externally"

Design: System detects automatically (on focus, on event, via watcher)
        → User is notified only when there's actually something to act on
        → Manual action becomes "reload on demand" not "reload to find out"
```

**Key distinction:** Replace "user polls system" with "system notifies user". The trigger changes from user-initiated to event-initiated.

**When a manual mechanism is appropriate instead:**
- The check is expensive (must not run automatically)
- User needs control over timing (e.g., before a critical operation)
- The condition is user-specific (can't be auto-detected reliably)

**Apply when:** User proposes a button, keyboard shortcut, or manual refresh for a condition that could be detected automatically by the system. Always ask: "could the system detect this and notify the user only when relevant?"

---

### Pattern: Wikilink `.md` Extension Not Stripped Before Node ID Lookup

**Symptom:** Wikilinks in a page resolve correctly in the preview (clickable, navigate to right file), but the corresponding graph edges are missing. Nodes appear isolated despite having wikilinks to each other.

**Root Cause:** In `app/api/graph/route.ts`, node IDs are stored WITHOUT the `.md` extension (the `.md` is stripped at node creation time via `replace(/\.md$/, '')`). However, when parsing wikilinks in the second pass, the target path still contains `.md` (e.g., `[[raw/articles/hildebrand-van-loonschool-official-website.md|...]]`). The `nodes.has(target)` lookup always returns `false` for targets with `.md`, so edges are silently dropped.

Links without `.md` (e.g., `[[entities/cornelis-vrijschool]]`) work correctly.

**Correct fix:**
```ts
// Before lookup, strip .md from target
const targetNoMd = target.replace(/\.md$/, '')
if (targetNoMd && nodes.has(targetNoMd)) {
  const linkKey = `${sourceName}→${targetNoMd}`
  if (!linkSet.has(linkKey)) {
    linkSet.add(linkKey)
    links.push({ source: sourceName, target: targetNoMd }) // use targetNoMd consistently
  }
}
```

**When to apply:** Any graph/link-building API that stores node IDs without file extensions but parses wikilinks that may include them. Test by adding a wikilink with `.md` extension and verifying the graph edge appears.

---

### Pattern: Wiki Path Resolution Inconsistency

**Symptom:** Clicking a wikilink in preview navigates correctly, but clicking a tag-browser item does not. Graph node clicks may also fail to open files.

**Root Cause:** `openFile` receives paths in different formats depending on the source:
- From wikilinks: relative like `concepts/rag` (needs `WIKI_ROOT/wiki/concepts/rag`)
- From tag-pages API: already has `wiki/` prefix like `wiki/concepts/rag` (needs `WIKI_ROOT/concepts/rag`)
- From graph: `concepts/rag` (same as wikilinks)

```
// ❌ BROKEN: doubles 'wiki/' prefix from tag-pages API
if (!target.startsWith('/')) {
  filePath = join(WIKI_ROOT, 'wiki', target) // 'wiki/concepts/rag' → 'WIKI/wiki/wiki/concepts/rag'
}

// ✅ CORRECT: detect pre-existing 'wiki/' prefix
if (!target.startsWith('/')) {
  if (target.startsWith('wiki/')) {
    filePath = join(WIKI_ROOT, target)
  } else {
    filePath = join(WIKI_ROOT, 'wiki', target)
  }
}
```

**Apply to:** Any function that receives paths from multiple external sources (APIs, store, event handlers). Always test with representative inputs from each source.

---

### Pattern: `isRootLevel` Check Fails for Absolute Paths

**Symptom:** Deleting/renaming a root-level file in a file tree does NOT update the UI immediately. The file still appears until user manually refreshes. Creating files works fine.

**Root Cause:** A common anti-pattern for checking if a path is at the root level uses substring searching:

```ts
// ❌ BROKEN: `isRootLevel` check for absolute paths like /home/jfeng/wiki/file.md
const isRootLevel = !path.includes('/', path.indexOf('/') + 1)
// For /home/jfeng/wiki/file.md:
//   path.indexOf('/') = 5  (first / in /home/)
//   path.includes('/', 6) = true  (finds / in /feng/ or /wiki/)
//   isRootLevel = false  ← WRONG! File IS at wiki root.
```

The logic checks "does this string have a second `/` somewhere after the first one?" — which is always true for absolute paths, even when the file is at the wiki root.

**Correct fix — compare parent directory to wiki root:**

```tsx
// ✅ CORRECT: compare actual parent directory to wiki root
const wikiRoot = process.env.WIKI_ROOT || '/home/jfeng/projects/wiki'
const isRootLevel = dirPath === wikiRoot || path === wikiRoot

// For deletions: ALWAYS filter from `entries` since it holds all root-level items.
// `loadedChildren` only holds children of EXPANDED folders — if parent wasn't expanded,
// the file won't be there anyway. So filtering `entries` alone catches all root files.
setEntries((prev) => prev.filter((e) => e.path !== path))

// For nested items: also filter from `loadedChildren` of the parent folder
const dirPath = isRootLevel ? wikiRoot : path.substring(0, path.lastIndexOf('/'))
setLoadedChildren((prev) => {
  const children = prev.get(dirPath) ?? []
  return new Map(prev).set(dirPath, children.filter((e) => e.path !== path))
})
```

**Why always filtering `entries` works:** `entries` is the source of truth for root-level files. If you only filter `loadedChildren` and the parent folder was never expanded, the file stays in `entries` and reappears on refresh. Always updating `entries` ensures the file disappears regardless of expansion state.

**Debugging tip:** When optimistic updates seem to not fire, add `console.log` directly inside the setState callbacks in the browser DevTools console to trace whether React is actually receiving the updates. For Next.js production builds, inject debug logs temporarily into the source, rebuild, redeploy, then remove them after testing.

**Apply to:** Any tree component that manages root-level items separately from nested/expanded items, especially those using absolute paths. The `path.includes('/', path.indexOf('/') + 1)` pattern is a reliable sign of this bug.

---

### Pattern: Hermes Auxiliary Client — Transient API 404 with Correct Code Path

**Symptom:** Background title generation fails with `HTTP 404: 404 page not found`, but main chat works fine. The 404 appears as an HTML error page from a load balancer or nginx, not a JSON API error.

**Root Cause:** Can be a transient upstream outage (MiniMax, OpenAI, etc.) — not a Hermes configuration error. The "page not found" is the load balancer reporting upstream unavailability.

**Diagnosis approach:**

1. **Check the log line** — the INFO log before the failure shows exactly what endpoint Hermes hit:
```
Auxiliary title_generation: using auto (MiniMax-M2.7) at https://api.minimax.io/v1
Title generation failed: 404 page not found
```
This tells you: provider, model, and URL. In this case, the URL was already rewritten from `/anthropic` → `/v1`.

2. **Trace the URL rewriting** — Hermes rewrites Anthropic-style base URLs for OpenAI SDK compatibility:
```
Original:  https://api.minimax.io/anthropic  (Anthropic Messages API)
Rewritten: https://api.minimax.io/v1          (OpenAI Chat Completions)
```
Key functions:
- `_to_openai_base_url()` in `agent/auxiliary_client.py` — rewrites `/anthropic` suffix to `/v1`
- `_endpoint_speaks_anthropic_messages()` — detects which endpoints need Anthropic wire format
- `_requires_bearer_auth()` — for MiniMax endpoints, ensures Bearer auth (not x-api-key)
- `_is_third_party_anthropic_endpoint()` — for third-party proxies (not direct Anthropic)

3. **Verify auth type** — MiniMax uses Bearer auth on `/anthropic`:
```python
# In build_anthropic_client():
elif _requires_bearer_auth(normalized_base_url):
    kwargs["auth_token"] = api_key  # Bearer auth, not x-api-key
```

4. **Check if it's actually transient** — retry manually:
```bash
curl -X POST "https://api.minimax.io/v1/chat/completions" \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-M2.7","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}'
```

5. **Key code locations**:
- Title generation: `agent/title_generator.py` → `generate_title()` → `call_llm(task="title_generation")`
- Provider resolution: `agent/auxiliary_client.py` → `_resolve_task_provider_model()` → `_resolve_auto()` → `resolve_provider_client()`
- URL rewriting: `agent/auxiliary_client.py` `_to_openai_base_url()` and `agent/anthropic_adapter.py` `_requires_bearer_auth()`
- main_runtime propagation: gateway passes agent's `{model, provider, base_url, api_key, api_mode}` to title generation

**Apply when:** Auxiliary background tasks (title generation, compression, vision, session search) fail with 404/502/503 but main agent chat works. First check if the upstream API is experiencing a transient outage before assuming Hermes configuration is wrong.

---

### Pattern: D3 SVG Drawn with Stale Container Dimensions on Resize

**Symptom:** A D3 force-directed graph (or any D3 visualization) renders correctly on initial mount. When the browser window resizes, device rotates (Portrait ↔ Landscape), or a sidebar collapses/expands — the graph appears clipped, offset, or continues drawing in the old area. An "invisible pane" from the old size covers part of the graph.

**Root Cause:** The D3 setup reads `container.clientWidth` and `container.clientHeight` once inside a `useEffect`, captures them in local constants (`width`/`height`), and uses those for the SVG and simulation for the entire lifetime of the component. When the container's actual size changes (via CSS flexbox, window resize, or orientation change), neither the SVG dimensions nor the D3 simulation's `forceCenter` are updated. The flexbox layout gives the container a new size, but D3 continues drawing in the old coordinate space.

```tsx
// ❌ BROKEN: width/height captured once at mount, never updated on resize
useEffect(() => {
  const container = document.getElementById('graph-container')
  const width = container.clientWidth   // ← captured once
  const height = container.clientHeight // ← captured once
  const svg = d3.select(container).append('svg')
    .attr('width', width).attr('height', height)
  const simulation = d3.forceSimulation(nodes)
    .force('center', d3.forceCenter(width / 2, height / 2))
  // ...
}, [data, theme]) // container size changes don't trigger re-run
```

**Correct fix — ResizeObserver + containerSize state:**

```tsx
// 1. Add reactive state for container dimensions
const [containerSize, setContainerSize] = useState({ width: 0, height: 0 })

// 2. ResizeObserver tracks actual DOM dimensions
useEffect(() => {
  const el = document.getElementById('graph-container')
  if (!el) return
  const ro = new ResizeObserver((entries) => {
    for (const entry of entries) {
      setContainerSize({ width: entry.contentRect.width, height: entry.contentRect.height })
    }
  })
  ro.observe(el)
  return () => ro.disconnect()
}, [])

// 3. D3 effect re-runs when containerSize changes
useEffect(() => {
  const container = document.getElementById('graph-container')
  if (!container) return
  const width = container.clientWidth || 0
  const height = container.clientHeight || 0
  // ... full D3 setup, simulation, rendering ...
}, [data, theme, containerSize]) // ← containerSize in deps
```

**Key points:**
- `ResizeObserver` fires on every size change (window resize, orientation, CSS transitions)
- `containerSize` state change triggers the D3 effect to re-run with fresh dimensions
- Include `containerSize` (not just `data`/`theme`) in the effect dependency array
- Use `|| 0` fallback to handle `display:none` or `clientWidth = 0` during CSS transitions
- The cleanup function (`return () => ro.disconnect()`) prevents memory leaks

**Apply to:** Any D3/visualization component inside a React `useEffect` that reads DOM dimensions at mount time. Signs: renders fine on load but clips/resizes incorrectly on orientation change or sidebar toggle. Also applies to Canvas-based visualizations, not just SVG.

---

## Red Flags — STOP and Follow Process

If you catch yourself thinking:
- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "Pattern says X but I'll adapt it differently"
- "Here are the main problems: [lists fixes without investigation]"
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when already tried 2+)**
- **Each fix reveals a new problem in a different place**

**ALL of these mean: STOP. Return to Phase 1.**

**If 3+ fixes failed:** Question the architecture (Phase 4 step 5).

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | First fix sets the pattern. Do it right from the start. |
| "I'll write test after confirming fix works" | Untested fixes don't stick. Test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, check changes, gather evidence, trace data flow | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare, identify differences | Know what's different |
| **3. Hypothesis** | Form theory, test minimally, one variable at a time | Confirmed or new hypothesis |
| **4. Implementation** | Create regression test, fix root cause, verify | Bug resolved, all tests pass |

## Hermes Agent Integration

### Investigation Tools

Use these Hermes tools during Phase 1:

- **`search_files`** — Find error strings, trace function calls, locate patterns
- **`read_file`** — Read source code with line numbers for precise analysis
- **`terminal`** — Run tests, check git history, reproduce bugs
- **`web_search`/`web_extract`** — Research error messages, library docs

### Hermes Auxiliary Failure Diagnostics

For background task failures (title generation, compression, vision), see:
- `references/hermes-auxiliary-debugging.md` — log patterns, endpoint tests, URL rewriting rules

### With delegate_task

For complex multi-component debugging, dispatch investigation subagents:

```python
delegate_task(
    goal="Investigate why [specific test/behavior] fails",
    context="""
    Follow systematic-debugging skill:
    1. Read the error message carefully
    2. Reproduce the issue
    3. Trace the data flow to find root cause
    4. Report findings — do NOT fix yet

    Error: [paste full error]
    File: [path to failing code]
    Test command: [exact command]
    """,
    toolsets=['terminal', 'file']
)
```

### With test-driven-development

When fixing bugs:
1. Write a test that reproduces the bug (RED)
2. Debug systematically to find root cause
3. Fix the root cause (GREEN)
4. The test proves the fix and prevents regression

## Real-World Impact

From debugging sessions:
- Systematic approach: 15-30 minutes to fix
- Random fixes approach: 2-3 hours of thrashing
- First-time fix rate: 95% vs 40%
- New bugs introduced: Near zero vs common

**No shortcuts. No guessing. Systematic always wins.**
