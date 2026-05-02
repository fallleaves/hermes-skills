---
name: wiki-structured-entity-ingest
description: "Autonomous research agent: takes a topic (entity or concept), researches it across the web, and outputs wiki-ready raw files + synthesized pages into the current request folder. No git commits — output is for human review."
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wiki, research, ingest, entity, concept, raw-sources]
    category: research
---

# Wiki Topic Research Agent

Autonomously researches a topic (entity or concept) from web sources and outputs structured, wiki-ready files into the current request folder. Designed to be called by the `request-processor` skill for feature-type requests.

**No git commits. No user interaction. Output to request folder for human review.**

## When This Skill Activates

Called by `request-processor` when processing a `feature`-type request. The request text contains the topic to research.

## Input

The skill receives:
- **Topic**: the research question/topic from the request body
- **Request ID**: the folder name (e.g. `req-20260502--xxxx`) — used for slug collision safety
- **Output folder**: the current request's folder path (e.g. `/home/jfeng/projects/wiki/requests/IN_PROGRESS/req-20260502--xxxx/`)

## Wiki Structure (Output Target)

```
{request_folder}/
├── request.md          ← already present
├── raw/               ← raw source files
│   └── {slug}-*.md    ← one per source/topic
├── entities/  OR  concepts/   ← synthesized page(s)
│   └── {slug}.md
└── NOTE.md            ← required: agent's summary + guidance
```

**The request-processor skill creates the folder structure before calling this skill.**

## Topic Type Detection

Read the request body and decide:

| Type | Indicators | Output folder |
|------|-----------|---------------|
| **Entity** | Specific named thing: university, person, company, product, organization | `entities/` |
| **Concept** | General subject: machine learning, climate change, urban planning, a technique | `concepts/` |

If ambiguous, default to **concept** (more general). Log your reasoning in NOTE.md.

## Research Workflow

### Step 0: Parse Request
1. Read the original request body from `{request_folder}/request.md`
2. Extract: topic, any user hints (depth preferences, language, focus areas)
3. Decide: entity vs concept
4. Generate slug candidates

### Step 1: Parallel Web Search
Run multiple `web_search` calls simultaneously across dimensions relevant to the topic.

**For an entity (e.g., university):**
- Overview / history / basic facts
- Admission scores / enrollment
- Employment / graduate outcomes
- Faculty / notable alumni
- Research platforms / labs
- International programs

**For a concept (e.g., machine learning):**
- Definition / overview
- History / key milestones
- Key techniques / approaches
- Applications / use cases
- Notable researchers / institutions
- Related concepts

**For open-ended topics:** agent judges which dimensions are most relevant.

### Step 2: Parallel Web Extract
Run `web_extract` on the most promising URLs from search results. Extract structured data.

### Step 3: Language Decision (per raw file)
- **Direct copy / scrape from source** → preserve source language
- **Synthesized / extracted / translated info** → English or Chinese (agent judges which is more suitable for the content)
- **Tables and structured data** → English is preferred for cross-language usability
- Log the language decision per file in NOTE.md

### Step 4: Create Raw Files

For each distinct source or sub-topic, create one raw file:

**Naming:** `{slug}-{source-type}.md`
**Frontmatter:**
```yaml
---
title: {Descriptive Title}
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
type: source
tags: [{comma, separated, tags}]
sources: [{url or "original content" if self-generated}]
---
```

**Rules:**
- One raw file per source or sub-topic — never combine unrelated sources
- Max 20 raw files total — if exceeded, note remaining dimensions in NOTE.md
- Tables for structured data (scores, statistics, comparisons)
- Source URL at top of file
- **No Related Pages / cross-links in raw files** — raw→raw links are forbidden
- Language as determined in Step 3

**Common raw file types:**
| Suffix | Use for |
|--------|---------|
| `-overview` | General info, history, attributes |
| `-schools-majors` | Schools, departments, programs (universities) |
| `-admission-scores` | Admission data, scores by province/year |
| `-employment` | Graduate employment, statistics |
| `-research` | Labs, platforms, achievements |
| `-international` | Exchanges, joint programs |
| `-applications` | Use cases, real-world applications (concepts) |
| `-techniques` | Methods, algorithms, approaches (concepts) |
| `-history` | Historical development |
| `-comparison` | Comparisons with similar entities/concepts |

### Step 5: Create Entity or Concept Page

**Entity pages (`entities/{slug}.md`):**
```yaml
---
title: {Entity Name}
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
type: entity
tags: [{comma separated tags}]
sources:
  - {raw-slug-1}
  - {raw-slug-2}
---
```

**Concept pages (`concepts/{slug}.md`):**
```yaml
---
title: {Concept Name}
created: {YYYY-MM-DD}
updated: {YYYY-MM-DD}
type: concept
tags: [{comma separated tags}]
sources:
  - {raw-slug-1}
  - {raw-slug-2}
---
```

**Content rules:**
- Synthesize all raw sources into a coherent page
- Use level-2 headings for sections
- Include a "Key Facts" table near the top (for entities)
- Tables for comparisons, scores, statistics
- End with a summary section
- Sources section at bottom using wiki link syntax: `[[raw/{slug}|{Display Title}]]`
- Language: English or Chinese (agent judgment)

### Step 6: Verify
- All raw files have correct frontmatter (`type: source`)
- Entity/concept page has `type: entity` or `type: concept`
- `sources:` field lists raw slugs (without `.md`)
- No raw→raw links
- All files are within the request folder

### Step 7: Write NOTE.md

The request-processor skill requires NOTE.md. Write it inside the request folder:

```markdown
# Research Summary: {Topic}

## Status
- [x] Completed / [ ] Declined / [ ] Partial

## Topic Classification
- **Type**: Entity / Concept
- **Slug**: `{slug}`
- **Language**: Primary language used in output files

## Files Produced
| File | Type | Wiki-Ready | Language | Notes |
|------|------|-------------|----------|-------|
| raw/bupt-overview.md | source | ✓ | Chinese (source) | Direct copy of official website |
| raw/bupt-admission.md | source | ✓ | English | Synthesized from enrollment data |
| entities/bupt.md | entity | ✓ | English | Full synthesis |

## Research Depth
- **Dimensions covered**: Overview, Admission, Employment, Research, International
- **Sources scraped**: 8 URLs
- **Raw files produced**: 6

## Readiness for Wiki Ingest
- **Ready to commit**: Yes / No
- **Requires human review**: ...
- **Suggested canonical slug**: `bupt` (raw/), `beijing-university-of-posts-and-telecommunications` (entity)

## Open Questions for Human
- Should the admission scores table be split by year?
- ...

## Decline Reason (if applicable)
- ...
```

## Tag Conventions

Use consistent tags:
- `university`, `company`, `organization`, `person` for entity type
- `concept`, `technique`, `technology` for concept type
- Location tags: `beijing`, `china`, `netherlands`
- Subject area tags: `telecommunications`, `machine-learning`
- Status tags: `211`, `double-first-class`, `985` for Chinese universities
- Topic tags: `admission`, `employment`, `research`, `international`

## Slug Generation

For entities: derive from English name + key identifier
- BUPT → `bupt`
- Beijing University of Posts and Telecommunications → `beijing-university-of-posts-and-telecommunications`

For concepts: use the English concept name
- Machine Learning → `machine-learning`
- Transformer model → `transformer-model`

Raw file slugs: `{base-slug}-{source-type}`
- `bupt-overview`, `bupt-admission-scores`, `bupt-research`

## Pitfalls

### Max Output Cap
- Stop at **20 raw files** maximum
- If research generates more, stop at 20, note the remainder in NOTE.md under "Open Questions"

### Slug Collision
- All files live inside `{req-id}/` folder during processing — no collision possible at this stage
- The NOTE.md will contain the suggested canonical slug for human decision at ingest time

### Language Consistency
- Raw files from the same source should use the same language
- The entity/concept page may differ if raw sources are mixed-language (note this in NOTE.md)

### Self-Generated Content
- If content is synthesized from multiple sources (not direct copy), mark `sources: ["synthesized"]` and write in English or Chinese as appropriate

### Empty Research Results
- If web search returns nothing useful, write NOTE.md with `Status: Partial` and explain in "Open Questions" why research was inconclusive

### Tables for Structured Data
- Always use markdown tables for: admission scores, employment statistics, historical timelines, comparisons
- Never dump unstructured prose where a table would be clearer
