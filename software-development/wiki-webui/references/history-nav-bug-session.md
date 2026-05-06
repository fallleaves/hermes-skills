# History Navigation Bug — Debugging Session Notes

# History Navigation Bugs — Debugging Session Notes

There are **two distinct** history navigation bugs in wiki-webui. This doc covers them separately.

---

## Bug 1: Back Button Unresponsive (Graph/Requests Tab)

**Bug**: Open Request Box → open Graph View → click Back → stays on Graph. Back button remains enabled but clicking it has no effect. Closing/reopening browser tab "resets" the bug.

**User's key clue**: "If I click 'Add a new tab,' then switch to the previous tab, clicking the 'go backwards' button will work. It feels like it really has to lose focus somehow until the button can work."

### What Was Ruled Out

| Attempt | Result |
|---------|--------|
| `e.stopPropagation()` on NavButtons onClick | Did NOT fix |
| `setTimeout(goBack, 0)` — defer outside React batching | Did NOT fix |
| Zustand `renderCount` field incremented on goBack/goForward | Did NOT fix |
| React `useEffect` + local state tick to force re-render | Did NOT fix |
| `pointerEvents: 'none'` on `#graph-container` div | **Did NOT fix** (confirmed by user) |
| `flushSync` from React | Not available in React 19.2.4 |

**Root cause**: Not conclusively identified. The "losing focus" reset pattern is the best remaining lead.

### What Was Cleaned Up

After the debugging session, all artifacts were removed:
- `clickCount` state and debug label from NavButtons.tsx
- `renderCount` from useWikiStore.ts
- `debugHistory()` from useWikiStore.ts
- `Cmd+Shift+D` keyboard shortcut from page.tsx
- `pointerEvents: 'none'` from GraphView.tsx graph-container div
- `setTimeout` wrappers from NavButtons onClick handlers

### Debug Techniques Used (for future sessions)

Since user has no browser console access (mobile, no keyboard):
1. **Visible click counter** — `useState` on NavButtons to confirm onClick fires
2. **`alert()` via keyboard shortcut** — `Cmd+Shift+D` calls `useWikiStore.getState().debugHistory()` showing tab history state as JSON
3. **Store `debugHistory()` method** — returns `{tabId, type, historyIndex, history}` for active tab

### Zustand/React Debug Pattern

```typescript
// In the store — add temporarily for debugging
debugHistory: () => {
  const { tabs, activeTabId } = get()
  const tab = tabs.find((t) => t.id === activeTabId) ?? tabs[0]
  return JSON.stringify({ tabId: tab?.id, type: tab?.type, historyIndex: tab?.historyIndex, history: tab?.history }, null, 2)
}

// In page.tsx useEffect — add temporarily
else if (meta && e.shiftKey && e.key.toLowerCase() === 'd') {
  e.preventDefault()
  alert(useWikiStore.getState().debugHistory())
}
```

Remove all debug artifacts after debugging is complete (see cleanup list above).

---

## Bug 2: Tab Sub-State Lost on Back Navigation (Request Box)

**Bug**: User was on Dashboard sub-tab, opened Graph, clicked Back — returned to Request Box but on Submit sub-tab instead of Dashboard. The tab type restored correctly but the internal sub-tab state did not.

**Root cause**: `requestsActiveTab` was stored as React `useState` inside `RequestsPanel`. Back/forward navigation restored the tab type from history but had no way to know which sub-tab was active.

**Fix applied (2026-05-02)**:
- Added `requestsActiveTab: 'submit' | 'dashboard'` to Zustand WikiStore
- Added `setRequestsActiveTab` action
- Extended `HistoryEntry` with `requestsActiveTab?: 'submit' | 'dashboard'`
- `openGraphTab` saves current `requestsActiveTab` to history before switching to graph
- `openRequestsTab` pushes `requestsActiveTab` to history
- `goBack`/`goForward` restore `requestsActiveTab` when navigating to a requests entry
- `RequestsPanel` reads `activeTab` from Zustand instead of local `useState`

**Files changed**:
- `store/useWikiStore.ts` — added state field, setter, history integration
- `components/Requests/RequestsPanel.tsx` — migrated from local `useState` to Zustand
