# Request Folder Structure

This document describes the folder structure used by the `request-processor` skill for organizing request processing.

## Top-Level Structure

```
~/projects/wiki/requests/
├── INBOX/                    # New requests submitted via wiki-webui
│   └── req-YYYYMMDD--xxxx.md  # Original submission file
├── IN_PROGRESS/              # Requests currently being processed
│   └── req-YYYYMMDD--xxxx/   # Per-request isolated folder
│       ├── request.md          # Copy of original submission
│       ├── raw/               # Raw source files (wiki-ready)
│       ├── entities/          # Entity pages (if applicable)
│       ├── concepts/          # Concept pages (if applicable)
│       └── NOTE.md            # Required: status + guidance for human
└── DONE/                     # Successfully processed requests
    └── req-YYYYMMDD--xxxx/  # Archived copy (same structure as IN_PROGRESS)

# Declined requests (if applicable)
└── DECLINED/
    └── req-YYYYMMDD--xxxx/
        ├── request.md
        └── NOTE.md            # Required: decline reason
```

## Per-Request Folder Contents

### `request.md` (required)
Copy of the original submission file. Contains:
- Frontmatter: `id`, `type`, `status`, `submitted`, `author`, `contact`
- Body: the original request text

### `raw/` (optional, for research requests)
Raw source files following wiki conventions:
- Frontmatter: `title`, `created`, `updated`, `type: source`, `tags`, `sources`
- Naming: `{slug}-{source-type}.md`
- One file per source or sub-topic
- Language: source language for direct copies, English/Chinese for synthesized

### `entities/` (optional, for entity-type topics)
Synthesized entity pages:
- Frontmatter: `title`, `created`, `updated`, `type: entity`, `tags`, `sources`
- Sources field lists raw file slugs
- Content in English or Chinese (agent judgment)

### `concepts/` (optional, for concept-type topics)
Synthesized concept pages:
- Frontmatter: `title`, `created`, `updated`, `type: concept`, `tags`, `sources`
- Sources field lists raw file slugs
- Content in English or Chinese (agent judgment)

### `NOTE.md` (required for every request)
Agent's summary and guidance for human review:
- Status: Completed / Declined / Partial
- Files produced table
- Readiness assessment
- Open questions
- Decline reason (if applicable)

## Request Lifecycle

1. **Submit**: User submits via wiki-webui → file saved to `INBOX/`
2. **Pickup**: Cron job picks up request → creates `IN_PROGRESS/{req-id}/` folder
3. **Process**: Research/implementation happens inside the folder
4. **Document**: `NOTE.md` written with status and guidance
5. **Archive**: Folder moved to `DONE/` (or `DECLINED/`)
6. **Deliver**: Telegram summary sent to user

## Key Principles

- **Isolation**: Each request lives in its own folder throughout its entire lifecycle
- **No collision**: Files never mix between requests
- **Human review**: Output is NOT committed to wiki git — human decides
- **Completeness**: `NOTE.md` is required even for declined requests
