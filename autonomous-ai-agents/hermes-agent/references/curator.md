# Hermes Curator — Technical Reference

## Files

| File | Purpose |
|------|---------|
| `~/.hermes/skills/.bundled_manifest` | Tracks every bundled skill: `name:MD5_hash` |
| `~/.hermes/skills/.usage.json` | Per-agent skill usage: use/view/patch counts, last-used, state |
| `~/.hermes/skills/.curator_state` | Curator run history: last run, duration, summary |
| `~/.hermes/skills/.archive/` | Archived agent-created skills (tar.gz before each LLM run) |
| `~/.hermes/hermes-agent/tools/skill_usage.py` | Provenance tracking + lifecycle state machine |
| `~/.hermes/hermes-agent/tools/skills_sync.py` | Manifest-based bundled skill sync + `reset_bundled_skill()` |

## Provenance Classification

Curator determines skill origin via `is_agent_created()`:

```python
is_agent_created(skill_name):
    not in .bundled_manifest  →  agent-created
    not in .hub/lock.json     →  agent-created
    else                       →  bundled or hub-installed
```

The curator does NOT distinguish "user wrote" vs "agent generated" — both are agent-created from its perspective.

## Lifecycle States

```
active (new) → stale (>30 days unused) → archived (>90 days unused)
     ↑_________ (any use/view resets to active) _________↑
pinned skills skip all transitions.
```

## The Manifest Incompleteness Bug

**Symptom:** Curator archives bundled skills that were never modified.

**Cause:** `.bundled_manifest` was only a partial snapshot (~29 of 89 skills). The hermes-agent package ships 89 bundled skills in `/home/jfeng/.hermes/hermes-agent/skills/`, but the manifest captured only a subset. Missing skills are treated as agent-created → eligible for archival.

**Fix:** Re-sync the manifest with all bundled skills (see SKILL.md procedure).

## The Three-Hash Problem

Every bundled skill has three relevant hashes:

| Hash | What it is | Changes when |
|------|-----------|--------------|
| `bundled_hash` | MD5 of upstream bundled source | Upstream publishes an update |
| `manifest_hash` | MD5 recorded in `.bundled_manifest` at install/sync | Agent runs `sync_skills` |
| `disk_hash` | MD5 of what's actually on disk | User edits the skill |

`sync_skills()` uses this logic:

```
if manifest_hash == disk_hash:
    # User hasn't modified — safe to update from source
    if bundled_hash != manifest_hash:
        update from bundled  # brings user up to upstream
    else:
        skip (already current)
elif disk_hash != manifest_hash:
    # User modified — SKIP, never overwrite
    skip
```

**Key insight:** If you update `manifest_hash` to match `disk_hash` (to align the manifest), you lose the "user modified" skip protection. The next `sync_skills` run will see `bundled_hash != manifest_hash` and try to update, overwriting user changes.

## When a Skill Is Modified AND Source Updates

Hermes's answer: **user wins.** The skill is permanently skipped from future updates until `hermes skills reset <name> --restore` is run (which deletes the user's copy and re-copies from bundled source — user patches are **gone**).

There is no three-way merge or diff preview. To get upstream changes into a modified skill, you must:
1. `hermes skills reset <name> --restore` (back up your copy first)
2. Manually re-apply your patches to the freshly-copied source

## Resetting a Bundled Skill

```bash
# Just clear the manifest entry (keep user's copy, resume update tracking)
hermes skills reset <name>

# Delete user's copy and re-copy from bundled source
hermes skills reset <name> --restore
```

`reset_bundled_skill()` in `tools/skills_sync.py` (line 321):
1. Removes manifest entry
2. Optionally deletes user copy
3. Runs `sync_skills()` to re-baseline

## Manifest Entry Format

v2 format (current): `skill_name:MD5_hash`
- MD5 is `_dir_hash()` — MD5 of all files in the skill directory, sorted by relative path
- Old v1 format (plain names) auto-migrates to v2 on first sync

## The `sync_skills()` Return Structure

```python
{
    "copied":        [...],  # new skills copied to user dir
    "updated":       [...],  # existing skills updated from bundled
    "skipped":       N,      # unchanged (already current)
    "user_modified": [...],  # skipped because user modified
    "cleaned":       [...],  # removed from manifest (upstream removed)
    "total_bundled": N,
}
```

## Verifying Alignment

After any curator run or manifest update, always verify:

```python
# All 89 bundled skills in manifest?
# No extra entries?
# Archive empty?
# Curator state reflects expected run?
```
