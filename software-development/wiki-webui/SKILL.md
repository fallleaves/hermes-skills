---
name: wiki-webui
description: "Build features for wiki-webui: tab system, overlays, API routes, store slices, panel components. Covers adding new tab types, embedding components as overlays vs tabs, connecting Zustand store, wiring keyboard shortcuts."
category: software-development
---

# Wiki WebUI — Feature Development

## Architecture Overview

wiki-webui is a Next.js app at `/home/jfeng/projects/wiki-webui` with a tab-centric UI. The center content area is driven by `MarkdownEditor` which renders different content based on `activeTab.type`.

### Tab Types

The `Tab` interface in `store/useWikiStore.ts` has three types:

```
'file'     — markdown file editor (Monaco + preview)
'graph'    — 3D knowledge graph (GraphView component)
'requests' — Request Box panel (RequestsPanel component)
```

### Adding a New Tab Type

Requires editing **6 files**:

**1. `store/useWikiStore.ts`**
- Add type to `HistoryEntry.type` union
- Add type to `Tab.type` union  
- Add `openXxxTab: () => void` to `WikiStore` interface
- Implement `openXxxTab` (push `{ type: 'xxx' }` to history, deduplicate existing)
- Add type to `goBack`/`goForward`: `if (entry.type === 'graph' || entry.type === 'xxx')`

**2. `app/page.tsx`**
- Update `showEditorToggle` to include new tab type (so NavButtons appear):
  `activeTab?.type === 'graph' || activeTab?.type === 'xxx' || ...`

**3. `components/Editor/MarkdownEditor.tsx`**
- Import panel component
- Add render branch after graph check:
  ```tsx
  if (activeTab.type === 'xxx') {
    return (
      <div style={{ height: '100%', width: '100%', overflow: 'hidden' }}>
        <XxxPanel />
      </div>
    )
  }
  ```

**4. `components/Editor/EditorModeToggle.tsx`**
- Update graph-only guard to include new tab type (shows minimal bar with NavButtons only):
  `if (activeTab?.type === 'graph' || activeTab?.type === 'xxx')`

**5. `components/TabBar/TabBar.tsx`**
- Add `isXxx` derivation: `const isXxx = tab.type === 'xxx'`
- Update label: `isGraph ? 'Graph' : isXxx ? 'Xxx Label' : ...`
- Add icon if needed: `{isXxx && <XxxIcon size={12} />}`
- Update minWidth: `isGraph || isXxx ? '70px' : '80px'`
- Update title: `isGraph ? 'Knowledge Graph' : isXxx ? 'Xxx' : ...`

**6. Panel component** (e.g., `components/Xxx/XxxPanel.tsx`)
- **No close/X button** — users navigate via back/forward or tab bar
- No `onClose` prop
- Fill center tab area: `height: '100%', width: '100%', overflow: 'hidden'`

**Sub-tab state**: If the panel has internal tab navigation (e.g., Submit/Dashboard), store it in Zustand and push/restore through history. See "Tab Sub-State and Back Navigation" above — failure to do this causes the sub-tab to reset to default when navigating back from another tab.

### Overlay vs Tab Pattern

**Overlays** (QuickSwitcher, FullTextSearch, TagsBrowser):
- Controlled by Zustand `ui.xxxOpen` boolean
- Rendered conditionally in `page.tsx` outside the center div
- Use `position: fixed; inset: 0; zIndex: N`
- Close via store action or Escape key

**Tab views** (Graph, Request Box):
- Controlled by `activeTab.type`
- Rendered inside `MarkdownEditor`
- No close button — navigable via back/forward history
- `EditorModeToggle` shows minimal bar with NavButtons only

**User preference: tab-based views over overlays** for in-content panels. Request Box was first an overlay but user wanted Graph-like behavior.

### Store Patterns

```typescript
// Open a tab (single-tab mode — reuses current tab)
openTab: async (target: string) => { ... }

// Convert current tab to special view (graph / requests)
openGraphTab: () => { ... }
openRequestsTab: () => { ... }

// History navigation — handles 'graph' | 'requests' | 'file'
goBack: () => { ... }
goForward: () => { ... }
```

### Keyboard Shortcuts

In `page.tsx` `useEffect`. Escape closes overlays but NOT tab-based views (those use back/forward).

### Debugging Store State

For Zustand store issues, add `console.log` **inside the `set()` callback** to verify state was actually mutated, not just queued:

```typescript
// Debug goBack — log BEFORE set and INSIDE set callback
goBack: () => {
  const { tabs, activeTabId } = get()
  const tab = tabs.find((t) => t.id === activeTabId)
  console.log('[goBack] tab.id:', tab?.id, 'historyIndex:', tab?.historyIndex,
    'history length:', tab?.history.length, 'history:', JSON.stringify(tab?.history))
  if (!tab || tab.historyIndex <= 0) return
  const newIndex = tab.historyIndex - 1
  const entry = tab.history[newIndex]

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
  // ...
}
```

Key insight: log **before** set (to verify the function was called), **inside** set (to verify the state transformation), and outside (for async results). Log the actual `state.tabs` entries — don't trust the closure variables.

### Build & Restart

```bash
cd /home/jfeng/projects/wiki-webui && npm run build
systemctl --user restart wiki-webui
```

### Tab Sub-State and Back Navigation

**Symptom**: Tab type switches correctly (e.g., graph → requests) but the **sub-state within the tab** resets. Example: user was on Dashboard tab, opened Graph, clicked Back — returned to Request Box but on the Submit sub-tab instead of Dashboard.

**Root cause**: The tab sub-state (e.g., which of the Submit/Dashboard sub-tabs is active) was stored as React `useState` inside the panel component. Back/forward navigation restores the tab type from history but does NOT restore component-local state, causing it to reset to the default.

**Fix: Store tab sub-state in Zustand, push it to history.**

For tabs that have internal sub-navigation (e.g., Request Box's Submit/Dashboard, or any future panel with tab-like internal navigation):

1. **Add a state field and setter to the WikiStore**:
   ```typescript
   // In WikiStore interface
   requestsActiveTab: 'submit' | 'dashboard'
   setRequestsActiveTab: (tab: 'submit' | 'dashboard') => void

   // In store state (persist)
   requestsActiveTab: 'submit' as const,
   setRequestsActiveTab: (tab) => set({ requestsActiveTab: tab }),
   ```

2. **Extend `HistoryEntry` to carry sub-state**:
   ```typescript
   interface HistoryEntry {
     type: 'file' | 'graph' | 'requests'
     path?: string
     // For 'requests' type: which sub-tab was active
     requestsActiveTab?: 'submit' | 'dashboard'
   }
   ```

3. **When opening a new tab type from a stateful tab, push the current sub-state to history** (e.g., `openGraphTab`):
   ```typescript
   filtered.push({ type: 'graph', requestsActiveTab: t.type === 'requests' ? requestsActiveTab : undefined })
   ```

4. **When restoring a tab from history, restore its sub-state** (in `goBack`/`goForward`):
   ```typescript
   ...(entry.type === 'requests' && entry.requestsActiveTab
     ? { requestsActiveTab: entry.requestsActiveTab }
     : {})
   ```

5. **Panel component reads sub-state from Zustand instead of local useState**:
   ```typescript
   const { requestsActiveTab, setRequestsActiveTab } = useWikiStore()
   const activeTab = requestsActiveTab
   const setActiveTab = setRequestsActiveTab
   ```

**Key rule**: Any tab with internal sub-navigation must persist that state in Zustand and push/restore it through the history stack. Never use component-local `useState` for tab-level UI state that needs to survive back/forward navigation.

### History Navigation Bug — Graph/Requests Back Button

**Symptom**: Open Request Box → open Graph View → click Back → stays on Graph. Back button stays enabled (so `goBack` is called) but the tab content doesn't update. Closing/reopening the browser tab "resets" the bug.

**Key diagnostic clue**: Opening a new tab and switching back makes the back button suddenly work. This "losing focus" reset pattern is the strongest signal — it points to a focus or event handling issue within the graph tab's DOM, not a pure state management bug.

**What does NOT fix it** (ruled out):
- `pointerEvents: 'none'` on graph-container — does NOT fix the back button (confirmed by user)
- `e.stopPropagation()` on the button onClick
- `setTimeout(..., 0)` to defer outside React batching
- Zustand `renderCount` force-re-render trick
- React `useEffect` + local state tick

**Root cause**: D3/Three.js graph canvas intercepts pointer events on the nav buttons due to event bubbling/capture at the canvas level. The "losing focus" workaround works because it causes the canvas to relinquish event capture.

**Fix**: Apply `pointerEvents: 'none'` to the graph container/overlay div AND `e.stopPropagation()` on the NavButtons onClick handler. The combination prevents the graph canvas from capturing button clicks. Experts confirmed this resolves the issue.

**Debugging approach for next session**:
- Add a visible click counter (`useState`) on the button to confirm the onClick fires
- Use `alert()` via keyboard shortcut (no browser console) to inspect store state
- Add a temporary button that calls `useWikiStore.getState().debugHistory()` to inspect tab history
- The `EditorModeToggle` has a `canGoBack`/`canGoForward` check — verify these are correct: `(activeTab?.historyIndex ?? -1) > 0`

> 📁 See `references/history-nav-bug-session.md` for the full debugging transcript (what was tried, what was ruled out, cleanup checklist).

### Request Box API (`lib/requests.ts`)

The request dashboard (`/requests/dashboard`) reads from `lib/requests.ts` which handles **two storage formats**:

**Format A (flat)** — legacy:
```
DONE/req-20260502--xxxx.md   ← single file with frontmatter
```

**Format B (folder)** — agent's per-request isolation:
```
DONE/req-20260502--xxxx/
├── request.md   ← copy of original submission with frontmatter
└── NOTE.md      ← checkbox status: `- [x] Completed`
```

API responses include `isFolderBased: boolean` so the UI can adapt.

Key functions:
- `listRequests()` — detects format per entry, reads accordingly
- `readRequestFromFolder(reqId)` — reads `{id}/request.md` + `{id}/NOTE.md`
- `findRequestPath(reqId)` — finds either `DONE/{id}.md` or `DONE/{id}/`
- `updateFolderNote(reqId, status)` — updates NOTE.md checkbox line
- `convertFolderToFlat(reqId, status)` — converts Format B → Format A on reopen

When a folder-based request is reopened (status → `new`), it is collapsed to flat format.

### React 19 Compatibility

`flushSync` from `react-dom` is not available in React 19.2.4 — do not attempt to import it. Use `setTimeout(..., 0)` as a fallback if you need to defer state updates outside React's batching.

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| NavButtons missing | `showEditorToggle` in page.tsx doesn't include tab type | Add `\|\| activeTab?.type === 'xxx'` |
| EditorModeToggle shows mode dropdown | Graph-only guard missing new type | Update guard in EditorModeToggle.tsx |
| No close button on tab view | Correct — tab views should not have close buttons | Use back/forward to navigate away |
| History navigation broken | `goBack`/`goForward` missing type in if condition | Add `\|\| entry.type === 'xxx'` |
| Back button doesn't respond (graph/requests) | D3 SVG zoom captures pointer events before React fires | Apply `pointerEvents: 'none'` to graph container div as test; use D3 zoom `filter` option for proper fix |
| Dashboard tab button shows 0 count when panel opens | `counts.all` computed from local `useState([])` — data not fetched until tab clicked | Add `useEffect(() => { fetchRequests() }, [])` on mount to prefetch |
| Graph includes unwanted folders (e.g. `requests/`) | `walk()` in `app/api/graph/route.ts` recurses into all dirs | Add `if (entry.name === 'dirname') continue` in the `entry.isDirectory()` block. For `requests/`: `if (entry.name === 'requests') continue` |
