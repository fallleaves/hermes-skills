---
name: telegram-messaging
description: Hermes Agent Telegram channel — markdown, media, workflow, and user-preference conventions for this messaging platform.
version: 1.0.0
owner: jfeng
triggers:
  - "telegram"
  - "send to telegram"
  - "format message"
  - "telegram output"
  - "telegram markdown"
---

# Telegram Messaging Skill

## Platform Notes

Telegram auto-converts standard markdown with some important quirks:
- ✅ **`**bold**`**, `*italic*`, `~~strikethrough~~`, `||spoiler||`, `` `inline code` ``, `[link](url)`
- ✅ ``` ```code blocks``` ``` — but keep them SHORT (see below)
- ✅ `## Headers` and `- bullet lists`
- ✅ Key: Value pairs — preferred over tables (Telegram rewrites tables to row-bullet groups anyway)
- ❌ Tables (pipe syntax) — auto-rewritten into unreadable row-group bullets — use bullet lists or key:value pairs instead

## Content Rules

**Keep it short and scannable.** This is a messaging app, not a document.

- No deeply nested bullet indentations
- No large code blocks (> ~15 lines rendered inline gets cut off)
- No markdown tables — use `Label: value` pairs or simple bullets
- One idea per message if possible

## Long Output Strategy

When content is necessarily long (code, file dumps, structured reports):

1. **Code files / file content** → Use `terminal` to `cat` or `head` the file, then paste a **relevant excerpt** (5–15 lines, not the whole file). If the full file matters, send it as a media file or direct the user to `terminal` to view it.
2. **Multi-part explanations** → Split into 2–3 messages rather than one mega-message.
3. **Background jobs** → Run with `background=true`, check `logs/backfill.log` for status, report back with a clean summary. Never block the conversation waiting for a long-running job.
4. **Data/query results** → Summarize the key numbers. Don't dump raw SQL output.

## Workflow Conventions

- `target="telegram"` on every `send_message` call
- Use `send_messages` (plural, batched) to send multiple parts of a split message
- After sending, describe what was sent in plain text so the user knows what to look for
- Background processes: start with `background=true`, check logs via `terminal`, report status cleanly

## User Preferences (from session 2026-05-05)

- User corrects verbose output: "you don't need to explain" tone — give direct answers, minimal preamble
- User dislikes long code blocks in chat — always prefer short excerpts or terminal cat + pointed description
- User prefers key:value pairs over tables
- User says "formatting was strange" for long nested explanations — keep it flat and short
- When running long CLI jobs → always background, check logs, summarize from log output
