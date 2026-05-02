# wiki-webui Tab Types Pattern

How to implement a persistent view that fills the center tab area — behaves like the graph view.

---

## The Two Patterns

### Pattern A: Overlay Modal (transient)
Use for: QuickSwitcher, FullTextSearch, TagsBrowser, Settings.

- Controlled by `ui.*Open: boolean` in Zustand store
- Rendered conditionally in `page.tsx` outside the layout
- `position: fixed; inset: 0` covering the viewport
- Close via Escape key or explicit close button
- Does NOT appear in tab history
- No tab bar representation

### Pattern B: Tab Type (persistent)
Use for: Graph view, and any view that should "fill the tab" and support back/forward navigation.

- Defined as a `type` value in `HistoryEntry.type` and `Tab.type`
- Rendered inside `MarkdownEditor` based on `activeTab.type`
- Appears in tab history — supports back/forward navigation
- Tab bar shows an icon + label
- Sidebars and status bar remain visible

---

## Example: Adding a `requests` tab type

### 1. Store — `useWikiStore.ts`

**Interface changes:**
```ts
interface HistoryEntry {
  type: 'file' | 'graph' | 'requests'  // add 'requests'
  path?: string
}

interface Tab {
  id: string
  type: 'file' | 'graph' | 'requests'  // add 'requests'
  // ...
}
```

**New action in WikiStore interface:**
```ts
openRequestsTab: () => void
```

**Implementation:**
```ts
openRequestsTab: () => {
  const { tabs, activeTabId } = get()
  const currentTab = tabs.find((t) => t.id === activeTabId) ?? tabs[0]
  if (!currentTab) return
  set((state) => ({
    tabs: state.tabs.map((t) => {
      if (t.id !== currentTab.id) return t
      const newHistory = t.history.slice(0, t.historyIndex + 1)
      const filtered = newHistory.filter((e) => e.type !== 'requests')
      filtered.push({ type: 'requests' })
      return {
        ...t,
        type: 'requests' as const,
        path: null,
        content: '',
        etag: '',
        isDirty: false,
        history: filtered,
        historyIndex: filtered.length - 1,
      }
    }),
    activeFile: null,
  }))
},
```

**goBack/goForward — add 'requests' to the graph branch:**
```ts
if (entry.type === 'graph' || entry.type === 'requests') {
  set((state) => ({
    tabs: state.tabs.map((t) =>
      t.id === activeTabId
        ? { ...t, type: t.type === 'graph' ? 'graph' as const : 'requests' as const,
            path: null, content: '', etag: '', isDirty: false, historyIndex: newIndex }
        : t
    ),
    activeFile: null,
  }))
}
```

### 2. TabBar — `components/TabBar/TabBar.tsx`

```tsx
import { Network, Inbox } from 'lucide-react'  // add Inbox

// In the tab rendering:
const isGraph = tab.type === 'graph'
const isRequests = tab.type === 'requests'
const label = isGraph ? 'Graph' : isRequests ? 'Request Box'
  : tab.path ? tab.path.split('/').pop()?.replace(/\.md$/, '') ?? 'Untitled' : 'Empty'

// Icon:
{isGraph && <Network size={12} style={{ flexShrink: 0 }} />}
{isRequests && <Inbox size={12} style={{ flexShrink: 0 }} />}

// MinWidth adjustment:
minWidth: isGraph || isRequests ? '70px' : '80px'
```

### 3. MarkdownEditor — `components/Editor/MarkdownEditor.tsx`

Import the panel component:
```tsx
import RequestsPanel from '@/components/Requests/RequestsPanel'
```

Add tab-type check (before the `!activeTab || !activeTab.path` empty state check):
```tsx
if (activeTab.type === 'requests') {
  return (
    <div style={{ height: '100%', width: '100%', overflow: 'hidden' }}>
      <RequestsPanel />
    </div>
  )
}
```

### 4. LeftVerticalBar — `components/LeftVerticalBar/LeftVerticalBar.tsx`

```tsx
<button
  className="vertical-icon-btn"
  onClick={() => useWikiStore.getState().openRequestsTab()}
  title="Request Box"
>
  <Inbox size={18} />
</button>
```

### 5. RequestsPanel — `components/Requests/RequestsPanel.tsx`

Make `onClose` optional since it's no longer always an overlay:
```tsx
export default function RequestsPanel({ onClose }: { onClose?: () => void }) {
```

---

## Key Files Reference

| File | Role |
|------|------|
| `store/useWikiStore.ts` | Tab type definitions + `openRequestsTab()` action |
| `components/TabBar/TabBar.tsx` | Tab label + icon rendering |
| `components/Editor/MarkdownEditor.tsx` | Panel rendering based on `activeTab.type` |
| `components/LeftVerticalBar/LeftVerticalBar.tsx` | Button that opens the tab |
| `app/page.tsx` | Layout shell (no changes needed for tab types) |
