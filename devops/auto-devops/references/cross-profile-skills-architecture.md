# Cross-Profile Skills Architecture

**Decision date:** 2026-06-18
**Status:** Active

## Architecture

All Hermes profiles share a single canonical skills directory via symlinks:

```
~/.hermes/skills/                          ← canonical (default profile)
~/.hermes/profiles/jf/skills/  → symlink → ~/.hermes/skills/
~/.hermes/profiles/ws/skills/  → symlink → ~/.hermes/skills/
```

This replaces the previous approach of three independent copies with a daily rsync cron.

## Rationale

- **Zero sync overhead** — modification in any profile is instantly visible in all profiles
- **Single source of truth** — no drift between profiles
- **Curator runs once** — shared `.curator_state` via symlink means only the first profile to reach the 7-day interval actually runs curator; others skip

## Curator Config

| Profile | curator.enabled | Reason |
|---------|:---------------:|--------|
| jf      | true            | Main profile — runs periodic skill maintenance |
| ws      | false           | Disabled — all profiles share skills now |
| default | false           | Disabled — all profiles share skills now |

## Implications

| Aspect | Effect |
|--------|--------|
| **Skill content** | One copy, byte-identical across all profiles |
| **Linked files** | (scripts/ references/ templates/) — shared |
| **`.usage.json`** | Merged (kept max last_used_at, summed use_count from all 3 profiles) — canonical at `~/.hermes/skills/.usage.json` |
| **`.curator_state`** | Shared — kept root's last_run_at (2026-06-16, run_count=5) |
| **`.curator_backups/`** | Shared — canonical at `~/.hermes/skills/.curator_backups/` |
| **`.hub/`** | Shared — all profiles use same hub index cache |
| **`.archive/`** | Shared — archived skills visible to all profiles |
| **Pending skills** | Unaffected — stored at `~/.hermes/profiles/<name>/pending/skills/` (outside skills symlink) |
| **Cross-profile write guard** | `write_file`/`patch` to skills from ws or default profile triggers guard (canonical path resolves to root skills which belongs to "default" profile) — use `cross_profile=True` or work from jf profile |
| **`skill_manage` → approve** | Unaffected — pending JSON → `hermes skills approve` writes via terminal() → works correctly |

## Migration Backup

Full backups of all three skills directories before symlink conversion:
```
~/.hermes/skills-migration-backup/
  root-skills-20260618-*.tar.gz  (35M)
  jf-skills-20260618-*.tar.gz    (12M)
  ws-skills-20260618-*.tar.gz    (12M)
```

## Rollback Procedure

If symlinks need to be undone:

```bash
# 1. Remove symlinks
rm -rf ~/.hermes/profiles/jf/skills
rm -rf ~/.hermes/profiles/ws/skills

# 2. Restore from backup
tar xzf ~/.hermes/skills-migration-backup/jf-skills-20260618-*.tar.gz \
  -C ~/.hermes/profiles/jf/
tar xzf ~/.hermes/skills-migration-backup/ws-skills-20260618-*.tar.gz \
  -C ~/.hermes/profiles/ws/

# 3. Restore curator config
# Set curator.enabled = true in ~/.hermes/config.yaml and ~/.hermes/profiles/ws/config.yaml
```
