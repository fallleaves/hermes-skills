---
name: wiki-structured-entity-ingest
description: "End-to-end wiki research pipeline: user gives a topic → systematic web research → produce raw + entity/concept pages → inject into wiki with logging → commit to git → send time report to Notifications bot (@AmHousingBot)."
version: 3.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wiki, research, ingest, entity, concept, git, notifications]
    category: research
---

# Wiki Structured Ingest — End-to-End Pipeline

End-to-end autonomous research pipeline: user gives a topic → systematic web research →
produce structured raw files + synthesized wiki pages → inject directly into the wiki
with logging → commit to git → send time report via @AmHousingBot.

**Every output is committed to git. Every step is logged. Every ingest is traceable.**

## When This Skill Activates

Activated directly by the user saying something like "research X and add it to the wiki"
or when a kanban task with the relevant description is picked up by a worker.

## Pipeline Overview

```
User gives topic
     ↓
Phase 0: Orient — read SCHEMA, index, log; check for duplicates; start timer
     ↓
Phase 1: Research — parallel web search + extract across dimensions
     ↓
Phase 2: Produce — write raw/ files + entity/concept page directly into wiki
     ↓
Phase 3: Integrate — update index.md, log.md, bump frontmatter
     ↓
Phase 4: Git — git add, commit (descriptive msg), push to origin
     ↓
Phase 5: Report — time report via @AmHousingBot to Notifications chat
```

## Configuration

- **Wiki root:** `WIKI_PATH` env var or `/home/jfeng/projects/wiki`
- **Repo:** `origin` at `github.com/fallleaves/wiki.git`
- **Notifications bot:** @AmHousingBot via `HEALTH_ALERT_BOT_TOKEN` + `HEALTH_ALERT_CHAT_ID` from `~/.hermes/profiles/jf/.env`
- **Date format:** `YYYY-MM-DD`

## Phase 0 — Orient

**Always start here. Never skip.**

1. Read `SCHEMA.md` — understand conventions, tag taxonomy, language policy
2. Read `index.md` — see existing pages, get current page count
3. Read recent `log.md` (last 20 lines) — understand recent activity
4. **Dedup check:** Search by topic name across all wiki pages. If the entity/concept already exists, ask the user whether to update or skip — do NOT create duplicates.
5. Generate the canonical slug (lowercase, hyphens, e.g. `beijing-university-of-posts-and-telecommunications`)
6. Record start time for the time report

## Phase 1 — Research

### Topic Type Detection

| Type | Indicators | Output location |
|------|-----------|-----------------|
| **Entity** | Specific named thing: university, person, company, product, organization | `entities/{slug}.md` |
| **Concept** | General subject: ML, climate change, a technique | `concepts/{slug}.md` |

If ambiguous, default to **entity** (more precise).

### Parallel Web Search

Run 3–6 `web_search` calls simultaneously. Pick dimensions based on topic type:

**For an entity (university, company, person):**
- Overview / history / basic facts
- Admission / enrollment data (if school)
- Employment / graduate outcomes
- Faculty / notable people
- Research / labs / achievements
- International programs / partnerships

**For a concept:**
- Definition / overview
- History / key milestones
- Key techniques / approaches
- Applications / use cases
- Notable researchers / institutions
- Related concepts

**For any topic:** If the user specified focus areas, prioritise those dimensions.

### Parallel Web Extract

Run `web_extract` on the 5–10 most promising URLs. Extract structured data into tables wherever possible.

**Max output:** Stop at **15 raw files** total. If more dimensions remain, note them in the git commit message as "uncovered dimensions."

### Language Decision (per raw file)

| Case | Language |
|------|----------|
| Direct copy / scrape from source | Preserve source language |
| Synthesized / extracted / translated info | English or Chinese (agent judgment) |
| Tables and structured data | English preferred for cross-language usability |
| Chinese source about Chinese topic | Chinese (keep source language) |
| Mixed sources | One language per file, note in commit msg |

## Phase 2 — Produce

All files go directly into the wiki tree — no request folder staging.

### Raw Files

Create one file per sub-topic in `wiki/raw/{type}/`:

**Path:** `raw/{type}/{slug}-{source-type}.md` where `{type}` = `articles`, `papers`, or `notes`

**Frontmatter:**
```yaml
---
title: {Descriptive Title}
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
type: source
tags: [{comma-separated tags}]
sources: [{url}]
---
```

**Rules:**
- One raw file per distinct source or sub-topic
- Tables for structured data (scores, rankings, comparisons, timelines)
- Source URL near the top
- **No raw→raw wikilinks** — raw files are leaf nodes (only linked from entity/concept pages)
- Language per the decision in Phase 1

**Common raw slugs:**

| Suffix | When to use |
|--------|-------------|
| `-overview` | General info, history, basic attributes |
| `-admission-scores` | Test scores, enrollment data by year/province |
| `-employment` | Graduate outcomes, statistics, placement |
| `-research` | Labs, platforms, key achievements |
| `-faculty-alumni` | Notable faculty and alumni |
| `-international` | Exchanges, joint programs, global partnerships |
| `-competitions` | Competition achievements (universities) |
| `-applications` | Use cases, real-world applications |
| `-techniques` | Methods, algorithms, approaches (concepts) |
| `-comparison` | Comparisons with similar entities/concepts |

### Entity / Concept Page

Write to `entities/{slug}.md` or `concepts/{slug}.md`.

**Frontmatter:**
```yaml
---
title: {Entity Name}         # Display name (may include Chinese)
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
type: entity                # or concept
tags: [{comma-separated, from SCHEMA taxonomy}]
sources:
  - raw/{type}/{slug}-overview
  - raw/{type}/{slug}-admission-scores
  - ...
---
```

**Content rules:**
- Synthesize all raw sources into a coherent page
- Level-2 headings for each major section
- "Key Facts" table near the top (for entities) — name, type, founded, location, key stats
- Tables for comparisons, scores, timelines
- At least 2 `[[wikilinks]]` to other wiki pages (Related Entities / Related Concepts sections)
- End with a summary / key takeaways section
- Sources section: `[[raw/{type}/{slug}|Display Title]]` bullet list
- Language: English or Chinese (agent judgment per SCHEMA language policy)

## Phase 3 — Integrate

### Update index.md

1. Add the new page to the correct section (Entities / Concepts / Comparisons / Queries)
2. Keep alphabetical order within the section
3. Format: `- [[path/to/page]] — one-line summary`
4. Bump the "Total pages" count and "Last updated" date in the index header

### Update log.md

Append a new entry:
```
## [YYYY-MM-DD] ingest | {Topic Title}
- Research dimensions: {overview, admission, employment, ...}
- Sources scraped: {N} URLs
- Raw files created: {N}
- Entity/concept page: [[path/to/page]]
- Git commit: {short SHA}
```

### Bump Frontmatter

The entity/concept page and raw files already have today's date from creation. No additional bump needed for fresh pages.

## Phase 4 — Git

```bash
cd "$WIKI_ROOT"
git add -A
git commit -m "ingest: {Topic Title}

- Type: entity|concept
- Slug: {slug}
- Raw files: {list}
- Dimensions covered: {overview, admission, ...}
- Sources scraped: {N} URLs
- Language(s): {primary language(s)}

{Optional: uncovered dimensions, notes}"

git push origin main
```

**Commit message rules:**
- First line: `ingest: {topic}` — short, descriptive
- Body: list what was produced (raw files, page type), dimensions covered, source count
- If any dimensions were intentionally skipped (content not found), note them
- If the research was partial, mark with `Status: partial` at the end

## Phase 5 — Report

```bash
# Calculate duration from start time to now
# Send via @AmHousingBot Telegram Bot API
WIKI_ROOT="${WIKI_PATH:-$HOME/projects/wiki}"
SHORT_SHA=$(cd "$WIKI_ROOT" && git rev-parse --short HEAD)

source "$HOME/.hermes/profiles/jf/.env" 2>/dev/null

REPORT="📚 *Wiki Ingest Report*

*Topic:* {Topic Title}
*Type:* Entity / Concept
*Slug:* \`{slug}\`

*Research:*
· Sources scraped: {N} URLs
· Raw files created: {N}
· Page: {path}

*Time:* {duration}
*Git:* \`$SHORT_SHA\`
*Repo:* github.com/fallleaves/wiki"

curl -s -X POST "https://api.telegram.org/bot${HEALTH_ALERT_BOT_TOKEN}/sendMessage" \
  -H "Content-Type: application/json" \
  -d "{\"chat_id\":\"${HEALTH_ALERT_CHAT_ID}\",\"text\":\"$REPORT\",\"parse_mode\":\"Markdown\"}"
```

## Tag Conventions

From the SCHEMA taxonomy — add new tags to SCHEMA.md first:

- **Type:** `university`, `company`, `organization`, `person`, `school`, `product`
- **Location:** `beijing`, `china`, `amsterdam`, `netherlands`, `oud-zuid`
- **Subject:** `telecommunications`, `law`, `education`, `machine-learning`, `architecture`
- **Status:** `211`, `double-first-class`, `985` (Chinese unis); `active-project`, `completed-project`
- **Topic:** `admission`, `employment`, `research`, `international`, `competition`

## Slug Generation

| What | Rule | Examples |
|------|------|----------|
| Entity slug | English name, lowercase, hyphens | `beijing-university-of-posts-and-telecommunications` |
| Concept slug | English name, lowercase, hyphens | `machine-learning` |
| Raw file slug | `{entity-slug}-{suffix}` | `bupt-overview`, `bupt-admission-scores` |
| Raw file path | `raw/{type}/{slug}.md` | `raw/articles/bupt-overview.md` |

## Pitfalls

### Duplicate Prevention
Always search existing wiki before creating. If the topic exists, ask to update — never silently duplicate.

### Max Raw Files
Stop at **15 raw files**. If more dimensions exist, list them in the git commit message as uncovered.

### No raw→raw Links
Raw files are leaf nodes — they link to nothing. Only entity/concept pages link to raw files and to other wiki pages.

### Language Consistency Per File
One language per file. Mixed-language raw files are OK (different source languages), but a single file should not mix.

### Empty Search Results
If web search returns nothing useful, report to the user with explanation. Do NOT create placeholder pages.

### Git Auth
The wiki repo uses `https://github.com/fallleaves/wiki.git` origin. Git auth relies on `gh auth git-credential` helper (configured globally). If push fails, check `gh auth status`.

### Tables for Structured Data
Always use markdown tables for: scores, statistics, rankings, timelines, comparisons. Never dump unstructured prose where a table would be clearer.

### Notification Reliability
The Telegram notification via @AmHousingBot is best-effort. If the bot token or chat ID is missing, skip notification but still complete the git commit.
