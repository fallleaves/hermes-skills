---
name: auto-devops
description: "Ops worker skill — respond to kanban tasks: incident response, add monitoring, deploy projects."
version: 3.3.0
author: Hermes Agent
tags: [ops, automation, monitoring, kanban, incident-response, onboarding, deploy]
---

# Auto DevOps — Ops Worker Skill

> Load this when responding to ops kanban tasks. The dispatch table below routes each task to the right workflow.

## Dispatch — What to Run

| If the kanban task title starts with… | Then do this |
|---------------------------------------|--------------|
| `🛑` / `HTTP endpoint returned` / `Disk usage at` / `Memory at` / `Backup` | **Incident Response** — diagnose, fix, verify, close |
| `📦 New service:` | **Add to Monitoring** — `ops check new`, backup, wiki |
| `🗑 Remove:` | **Remove from Monitoring** — delete checks, config, and wiki references |
| `🚀 Deploy:` | **Deploy Project** — read `dev-ops.md`, build, deploy, monitor, wiki |
| `🚀 Deploy:` | **Deploy Project** — read `dev-ops.md`, build, deploy, monitor, wiki |
| `🔧 Config audit` / `cfg audit` / `清理配置` | **Configuration Audit** — audit .env vs config.yaml across all Hermes profiles |

If there's no task context (user just asks about ops) — point them to `~/projects/auto-devops/`.

---

## Incident Response

Triggered by: any health-monitoring failure (service down, HTTP 5xx, disk/memory threshold exceeded, backup stale).

### 1. Identify the Project

Parse the task title and body to determine which project is affected. The task body now includes context references:

```
Service: wiki-webui.service
Status: inactive
📖 Wiki: entities/wiki-webui.md
📄 dev-ops: ~/projects/wiki-webui/dev-ops.md
```

Extract the project name (e.g., `wiki-webui`) — this is the key to everything that follows.

### 2. Load Project Context

Read two sources to build a project-specific runbook:

**Wiki entity page** — metadata and system context:
```bash
cat ~/projects/wiki/entities/<project>.md
```
Contains: purpose, port, systemd unit, log location, backup paths, dependencies.

**dev-ops.md** — the project's own troubleshooting contract:
```bash
cat ~/projects/<project>/dev-ops.md
```
Focus on the **Troubleshooting** section which lists known failure modes and fixes.

If either file is missing, fall back to generic steps (systemd status → journal → curl) and consider filing a wiki update.

### 3. Assess Using Runbook

Follow the dev-ops.md Troubleshooting guide. If it prescribes specific diagnostics, use those. If not, use the generic checklist:

```bash
# systemd status
systemctl --user status <unit> -n 30 --no-pager
journalctl --user -u <unit> -n 50 --no-pager --since "10 min ago"

# HTTP (if applicable)
curl -sv http://127.0.0.1:<port>/ 2>&1 | tail -20

# Dependencies listed in dev-ops.md
# e.g., check DB, check API, check upstream services
```

### 4. Fix Using Runbook

The dev-ops.md **Troubleshooting** section may prescribe project-specific fixes (e.g., "restart in this order", "run migration", "clear cache"). Follow those first.

Generic fallback:

| Type | Diagnose | Fix | Verify |
|------|----------|-----|--------|
| systemd | (none) | `systemctl --user restart <unit>` | `is-active` after 5s |
| docker | `docker ps \| grep <name>` | `docker restart <name>` | `docker ps` |
| disk | `df -h /` | `journalctl --vacuum-size=500M` | `df -h /` |
| backup | `systemctl --user status daily-backup.timer daily-backup.service` | `~/projects/auto-devops/scripts/backup.sh` | `./bin/ops run --service <extracted_service>` |
|        | `journalctl --user -u daily-backup -n 50 --since "24h ago"` | If backup script fails: check `df -h /` (disk full), check script stderr, fix root cause and retry | |

> **Backup failures:** These indicate the daily backup cron (`daily-backup.timer`) didn't run or failed. Multiple backup checks may fire simultaneously for the same root cause (e.g., cron failed entirely → both `backup-amhousing` and `backup-wiki-webui` alarm). Fix the cron/service first, then re-run `scripts/backup.sh` — it handles all services in one pass. Then verify each affected service independently with `./bin/ops run --service <name>`.

If restart fails: check port conflict (`ss -tlnp | grep <port>`), check `.env`, rebuild if code changed.

### 5. Full Service Verification

Run all checks for this service to confirm everything is healthy — including related checks that were suppressed by service-group dedup:

```bash
cd ~/projects/auto-devops
./bin/ops run --service <project>
```

All checks should pass. If any fail, go back to step 3.

### 6. Re-Verify After Fix

After applying a fix, confirm the service is healthy by running:

```bash
cd ~/projects/auto-devops
./bin/ops run --service <project>
```

All checks should pass.

### 7. Close or Escalate

```python
kanban_complete(summary="<project> recovered — followed dev-ops.md runbook, all checks green",
    metadata={"action": "<specific action taken>", "project": "<project>"})
```

If it can't be fixed → `kanban_block(reason="<what you found — e.g., dev-ops.md missing, unknown failure>")`.

### Dedup Limitation

The dedup system (`engine/lib.sh` `ops_task_exists_for`) prevents duplicate alerts
for the same check within a service-group while the alert kanban task remains
active (not done/archived). However, there is a known gap:

**If the alert kanban task is archived/resolved while the underlying issue
persists, dedup will NOT re-alert.** The dedup entry stays in the cache file
but the task-status check (`_ops_task_active` in `engine/lib.sh`) sees the
task as done and returns "not active", which should allow a new alert. If
you observe this not working in practice, check the dedup cache file at
`config.yaml -> dedup.file` and manually remove stale entries, or check if
the check script was already removed from `checks/`.

To mitigate, after any fix that involves resolving a prior alert task:
1. Re-run `./bin/ops run --service <project>` to confirm all checks pass
2. If checks still fail despite the alert task being resolved, clear the
   relevant entry from the dedup cache file so a fresh alert fires

---

## Add a Service to Monitoring

Triggered by: `📦 New service: <name>` — a service exists but isn't covered by the health-check system.

### 1. Figure Out What It Is

```bash
systemctl --user cat <name>.service 2>/dev/null && TYPE=user
systemctl cat <name>.service 2>/dev/null && TYPE=system
docker ps 2>/dev/null | grep <name> && TYPE=docker
```

Check if a check already exists:

```bash
cd ~/projects/auto-devops && ./bin/ops check list | grep <name>
```

If already monitored — close the task as duplicate.

### 2. Add Checks

**IMPORTANT — check naming convention:** Always use the **service ID** as the
check name, not the domain name. For example, if `wiki-webui` serves
`noelias.com`, name the check `http-wiki-webui` (not `http-noelias`) and
`ssl-wiki-webui` (not `ssl-noelias`). This keeps naming consistent with the
svc check and the config.yaml service entry, avoiding alias mappings.

```bash
cd ~/projects/auto-devops
./bin/ops check new svc:<name> --unit <name>.service \
  [--http /:<port>] \
  [--backup "~/projects/<name>/backups/*.gz"]
```

**Naming rule**: All checks for a service MUST use the **service ID** as the name component — not the domain name, not a nickname. For example, a service with id `wiki-webui` that happens to serve `noelias.com` should have checks named `http-wiki-webui` and `ssl-wiki-webui`, NOT `http-noelias` + `@meta service_group: wiki-webui`. Naming by service ID means `_ops_service_group()` resolves correctly via prefix stripping, and no `service_group` override is needed. This keeps dedup and `--service` filtering working without extra metadata.

If it's a system-level service, also add it to `config.yaml` under `infra_services`.

Verify:

```bash
./bin/ops run --service <name>
```

### 3. Add Backup (if it has persistent data)

Create a modular backup execution script at `scripts/backups/backup-<name>.sh`:

```bash
cat > ~/projects/auto-devops/scripts/backups/backup-<name>.sh << "EOF"
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$HOME/projects/<name>"
cd "$PROJECT_DIR"

if ! scripts/backup.sh; then
  echo '{"status":"fail","project":"<name>","summary":"Backup script failed"}'
  exit 1
fi

git add <backup-path-glob> 2>/dev/null || true
if git diff --cached --quiet; then
  echo '{"status":"ok","project":"<name>","summary":"No new files to commit"}'
  exit 0
fi
git commit -m "Daily backup: <name> $(date '+%Y-%m-%d')"
git push origin main 2>&1 || true
echo '{"status":"ok","project":"<name>","summary":"Backup pushed to GitHub"}'
EOF
chmod +x ~/projects/auto-devops/scripts/backups/backup-<name>.sh
```

Then register it in `config.yaml` — add `backup_script: scripts/backups/backup-<name>.sh` to the service entry (above the `# @@OPS-SERVICES@@` marker).

The backup runner (`scripts/backup.sh`) is now a config-driven thin wrapper that discovers all registered backups automatically — no need to edit it. See `engine/lib.sh` functions `ops_backup_run_all()` and `ops_backup_send_report()` for the runner implementation.

### 4. Commit Changes

Commit **auto-devops** (check scripts from step 2) and **wiki** (new docs):

```bash
cd ~/projects/auto-devops
git add -A && git commit -m "ops: add checks for <name>" && git push origin main

ops wiki commit "ops: onboarded <name> — wiki"
```

Wiki files changed:
- `entities/<name>.md` — new entity page
- `concepts/server-infrastructure.md` — add row
- `index.md` — add link
- `log.md` — record addition

### 5. Close

```python
kanban_complete(summary="onboarded <name> — svc/http/backup checks created, wiki updated",
    metadata={"checks": ["svc:<name>", ...], "wiki_updated": True})
```

---

## Watchdog Script Service

Triggered by: `🐕 Watchdog: <name>` — a daemon script that should run continuously under systemd supervision and be monitored by auto-devops.

Pattern: kanban-blocked-bridge.py, imap-telegram.py, and any other Python script that needs to run in a loop with auto-restart on failure.

### 1. Script Requirements

The script must support daemon mode with `--daemon` and `--interval N` flags:

```python
# In the script:
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    if args.daemon:
        run_daemon(interval=args.interval)  # loop: main() + sleep
    else:
        sys.exit(main())  # one-shot mode (backward compatible)
```

The daemon loop should:
- Catch exceptions per tick (single failure does not kill the daemon)
- Handle SIGTERM gracefully (systemd stop)
- Sleep in 1-second increments for responsive shutdown

### 2. Create systemd Unit

Unit file at `~/.config/systemd/user/<name>.service`:

```ini
[Unit]
Description=<Name> Watchdog
After=network.target

[Service]
Type=simple
Environment=PATH=/home/<user>/.local/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 %h/path/to/script.py --daemon --interval 60
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=<name>

# Allow the script to access its state directory
ReadWritePaths=%h/.hermes/kanban %h/.hermes/config.yaml

[Install]
WantedBy=default.target
```

Key points:
- `PATH` must include `~/.local/bin` if the script calls `hermes` CLI
- `Restart=on-failure` + `RestartSec=10`: crash → restart after 10s
- `ReadWritePaths`: list only directories/files the script actually writes to

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable <name>.service
systemctl --user start <name>.service
systemctl --user status <name>.service -n 5 --no-pager
```

### 3. Register in Monitoring

```bash
cd ~/projects/auto-devops
./bin/ops check new svc:<name> --unit <name>.service
./bin/ops run --service <name>  # verify it passes
```

### 4. Verify the Three-Layer Safety Net

| Layer | Mechanism | What it protects against |
|-------|-----------|-------------------------|
| In-script | `try/except` per tick | Single tick failure does not kill daemon |
| systemd | `Restart=on-failure` | Process crash → auto-restart |
| auto-devops | `svc:<name>` health check | systemd restart loop → alert human |

### 5. Commit and Close

```bash
cd ~/projects/auto-devops
git add -A && git commit -m "ops: add <name> watchdog check" && git push origin master
```

```python
kanban_complete(summary="<name> watchdog deployed — systemd + auto-devops monitoring active",
    metadata={"checks": ["svc:<name>"], "unit": "<name>.service"})
```

---

## Service Lifecycle Management

> **Related reference:** `references/plan-review-iterate-workflow.md` describes the iterative sub-agent review cycle used to validate the decoupling plan before implementation. Use this pattern for any planned change to auto-devops-monitored services.

### Decouple a Service from Auto-Devops Dependencies

Triggered by: a service monitored by auto-devops has hardcoded references to auto-devops `.env`, config, or paths, and needs to become self-contained.

**Principle:** Auto-devops monitoring checks `systemctl --user is-active <unit>` — it only cares that the **unit name** stays the same. As long as the unit name is unchanged, you can freely relocate `EnvironmentFile`, credentials, and configuration to the service's own project directory without touching any auto-devops check scripts or `config.yaml` entries.

#### 1. Identify Dependencies on Auto-Devops

Check what the service currently pulls from auto-devops:

```bash
systemctl --user cat <unit> | grep EnvironmentFile
cat ~/projects/<service>/imap_to_telegram.py | grep -n 'auto-devops\|HERMES_HOME'
```

Common dependency types:

| Dependency | How it shows up | How to decouple |
|-----------|-----------------|-----------------|
| `EnvironmentFile=%h/projects/auto-devops/.env` | systemd unit | Move to project-local `.env`; update `EnvironmentFile` |
| Hardcoded `~/projects/auto-devops/.env` path | Python `load_env()` fallback | Change to `__file__`-relative `.env` resolution |
| Hardcoded `$HERMES_HOME` fallback | Python `load_env()` fallback | Remove — project `.env` is the single source |
| Hardcoded constants (host, port, interval, etc.) | Python global variables | Move to `config.yaml` (YAML) in project dir |

#### 2. Create Project-Local Configuration

```bash
# 1. Create config.yaml with all operational parameters
cat > ~/projects/<service>/config.yaml << 'EOF'
# example structure:
imap:
  host: imap.gmail.com
  port: 993
  timeout: 30
polling:
  interval: 10
  max_per_poll: 10
EOF

# 2. Create .env with secrets (chmod 600)
cp /dev/null ~/projects/<service>/env
chmod 600 ~/projects/<service>/.env
# Populate manually from the original credential source

# 3. Update systemd unit
systemctl --user edit --full <unit>
# Change EnvironmentFile to project-local path:
# EnvironmentFile=%h/projects/<service>/.env
```

#### 3. Update the Script

- Add `load_config(path)` that reads `config.yaml` via yaml.safe_load()
- Remove hardcoded constants; read from config dict
- Change `load_env()` to derive `.env` path from `__file__` (not a hardcoded auto-devops path)
- Use exception-based error handling (raise ValueError), not sys.exit(), in library functions — let `main()` handle exit
- Fix any stale error messages referencing `auto-devops` paths

#### 4. Verify Monitoring Still Works

```bash
cd ~/projects/auto-devops
./bin/ops run --service <service>
```

Expected: `svc:<service>` check passes (systemd unit is active with same name).

Also verify the service starts correctly:

```bash
systemctl --user daemon-reload
systemctl --user restart <unit>
systemctl --user status <unit>
journalctl --user -u <unit> -n 20
```

#### 5. Clean Up Old References

- Remove any leftover `HERMES_HOME` / `auto-devops` fallback code from the script
- Remove the old `EnvironmentFile` reference to auto-devops from the systemd unit
- The auto-devops `config.yaml` entry and check script need **zero changes** (unit name unchanged)

**Key rule:** If all you changed is `EnvironmentFile` path and config source, auto-devops monitoring is unaffected. The check script only checks `systemctl --user is-active <unit>`, and the unit name didn't change.

---

## Deploy a Project

Triggered by: `🚀 Deploy: <name>`.

**Prerequisite:** the project repo must have a `dev-ops.md` at its root. If it doesn't → `kanban_block` with a link to `~/projects/auto-devops/templates/dev-ops.md`.

### 1. Read the Contract

Open `~/projects/<name>/dev-ops.md` and extract what you need:

| dev-ops.md section | What it's for |
|--------------------|--------------|
| Project Identity | name, purpose, tech stack |
| Service Dependencies | other services this needs → **auto-discover and add monitoring** |
| Build/Runtime Dependencies | system packages, runtimes, env vars |
| Build Guide | exact commands to build |
| Deploy Guide | service type, unit file, ports |
| Backup Guide | data location (if stateful) |
| Deployment Checklist | items to verify after deploy |
| Troubleshooting | likely problems and fixes |

### 2. Auto-Discover Service Dependencies

For each dependency in the **Service Dependencies** table:

```bash
# Is it monitored already?
cd ~/projects/auto-devops
./bin/ops check list 2>/dev/null | grep -q "<dep>" && echo "already covered"
```

If not monitored, probe to decide what kind of check to create:

```bash
ACTIVE=$(systemctl --user is-active <dep>.service 2>/dev/null && echo user \
      || (systemctl is-active <dep>.service 2>/dev/null && echo system) \
      || echo "")
```

| Probe result | Checks to create |
|-------------|-----------------|
| systemd user | `ops check new svc:<dep> --unit <dep>.service` |
| systemd system | `ops check new svc:<dep> --unit <dep>.service` + register in `config.yaml` infra_services |
| Not found | log a warning but don't block — it may be external |
| Has HTTP port | add `--http /:<port>` to the check above |

Create the checks, verify them.

**Record Dependency Relationships in Wiki (always):**

Regardless of whether the dependency already had monitoring, record the **dependency relationship** so incident response can trace the full chain:

```bash
# Add dependencies section to project entity page
cat >> ~/projects/wiki/entities/<project>.md << EOF

## Dependencies

| Service | Purpose | Monitored |
|---------|---------|-----------|
| <dep>   | <purpose from dev-ops.md> | ✅ / ❌ |
EOF

# Update infrastructure table
# Edit: ~/projects/wiki/concepts/server-infrastructure.md
# | <project> | <port> | <unit> | depends on: <dep> | <backup> |
```

### 2.5. Commit Dependency Checks

```bash
cd ~/projects/auto-devops
git add -A && git commit -m "ops: add dep checks for <name>" && git push origin main
```

Then move on to the build.

### 3. Install Dependencies & Build

Follow the Build/Runtime Dependencies and Build Guide from `dev-ops.md`. If the build fails → consult Troubleshooting, then retry. If it still fails → `kanban_block`.

### 4. Deploy

If it's a `systemd (user)` service, the unit file lives at `~/.config/systemd/user/<name>.service` with:

```
WorkingDirectory=~/projects/<name>
ExecStart=<from the build guide>
Restart=on-failure
RestartSec=5
```

Set up `.env` based on the vars listed in dev-ops.md (never copy `.env.example` directly — it's all commented out). Then enable and start.

### 5. Run the Deployment Checklist

Execute every item from dev-ops.md's checklist. Common items:

- Service started without errors
- HTTP endpoint returns 200
- `.env` has the right values
- Logs show clean startup

If anything fails → use Troubleshooting to recover. If persistent → `kanban_block`.

### 6. Add to Monitoring

Same as **Add a Service to Monitoring** (above):

```bash
cd ~/projects/auto-devops
./bin/ops check new svc:<name> --unit <name>.service \
  [--http /:<port>] [--backup "~/projects/<name>/<glob>"]
```

Also add backup orchestration if the project is stateful — create `scripts/backups/backup-<name>.sh` and register in `config.yaml` (see **Add a Service to Monitoring > step 3** above).

### 7. Commit Changes

Commit **auto-devops** (service checks from step 6) and **wiki** (new docs):

```bash
cd ~/projects/auto-devops
git add -A && git commit -m "ops: add checks for <name>" && git push origin main

ops wiki commit "ops: deployed <name> — wiki"
```

Wiki files changed:
- `entities/<name>.md` — new entity page
- `concepts/server-infrastructure.md` — add row
- `index.md` — add link
- `log.md` — record deployment

### 8. Close

```python
kanban_complete(summary="deployed <name> — <N> deps auto-monitored, <M> checks created, wiki updated",
    metadata={"checks_created": ["svc:<name>", ...], "deps_monitored": ["<dep1>", ...]})
```

---

## Remove a Service from Monitoring

Triggered by: `🗑 Remove: <name>` — a service is being decommissioned or should no longer be monitored.

Removal spans **two repos** (auto-devops + wiki). Search both for all references before acting.

### 1. Remove from auto-devops

**config.yaml** — delete the service's entry block from `services:` (or `infra_services:`):
```bash
# Show the block to delete
grep -n -A 4 "id: <name>" ~/projects/auto-devops/config.yaml
```

**Check script** — delete the file:
```bash
rm ~/projects/auto-devops/checks/svc-<name>.sh
# system-level: rm ~/projects/auto-devops/checks/sys-svc-<name>.sh
```

**README.md** — remove the directory listing line (under `checks/`).

### 2. Remove from wiki

Search for all references:
```bash
grep -rn "<name>" ~/projects/wiki/ --include="*.md"
```

Common locations to clean up:

| File | What to remove |
|------|---------------|
| `entities/<related-project>.md` | Row from Dependencies table |
| `concepts/server-infrastructure.md` | Row from services table, dedicated section (if any), status/restart batch commands, known-issues row |

## Pitfalls

### 1. Dedup 不意味着"忽略到永远"

去重机制只在**已有活跃告警任务**时静默跳过。如果告警任务被人为 done/archived（如清理测试任务时顺手 archive）但底层服务仍然挂著，去重检查发现任务已 done/archived → 返回"不活跃" → **应该重新报警**。

`_ops_task_active` 的逻辑是正确的（done/archived → 放行），但要注意：
- 不要同时 close 告警和移除 check——确认服务已恢复再移出监控
- 如果服务挂了超过 N 小时，应有升级机制（更高频率、更高级别），而非仅靠每 5 分钟一次的去重检查
- **Re-number tables** after removing rows (services table, known issues table).
- **Update batch commands** that compose the service name (e.g. `systemctl --user status X Y Z`).
- **Known issues** — if the issue is closed by the removal itself, delete the row; if it's a separate bug, keep it but note "service decommissioned".
- **Dedicated subsections** (e.g. `### 2.3 hermes-gateway-*`) — if you're removing the last instance of a category, collapse the section title from plural to singular.

### 3. Verify

```bash
# No references remain in auto-devops
grep -rn "<name>" ~/projects/auto-devops/ --include="*.yaml" --include="*.md" --include="*.sh"

# No references remain in wiki
grep -rn "<name>" ~/projects/wiki/ --include="*.md"
```

Zero matches = complete.

### 4. Commit

```bash
cd ~/projects/auto-devops
git add -A && git commit -m "ops: remove <name> from monitoring" && git push origin main

ops wiki commit "ops: removed <name> from monitoring — wiki cleanup"
```

### 5. Close

```python
kanban_complete(summary="removed <name> from monitoring — config/check/wiki cleaned",
    metadata={"project": "<name>", "files_deleted": "svc-<name>.sh", "wiki_updated": True})
```

---

---

## Constraints & Pitfalls

### Gateway Process Constraint

You **cannot** run `systemctl --user stop/restart` against the Hermes gateway from within a gateway session — the SIGTERM propagates to all child processes including the current session, killing the command before it completes.

**Workaround:** use `delegate_task` to a subagent (which gets its own terminal session) or run `hermes gateway restart` / `systemctl --user restart hermes-gateway-*.service` from a separate terminal outside the running gateway.

This applies to ALL Hermes gateway services (`hermes-gateway-default`, `hermes-gateway-jf`, etc.). The `hermes gateway restart` CLI command has built-in safe-handling for this.

---

## Config & Environment Auditing

When tasked with reviewing Hermes config/environment files for issues:

1. **Read default profile** — check both `~/.hermes/.env` and `~/.hermes/config.yaml`
2. **Identify issues** — three categories:
   - **Redundant**: env vars that duplicate config.yaml values (`HERMES_MAX_ITERATIONS`, `TERMINAL_LIFETIME_SECONDS`, `TERMINAL_MODAL_IMAGE`, `BROWSER_INACTIVITY_TIMEOUT`, etc.)
   - **Conflicting**: env vars that override config.yaml at different values (`TERMINAL_TIMEOUT` vs `terminal.timeout`)
   - **Dead**: env vars referencing disabled/disconnected features (`BROWSERBASE_PROXIES`/`BROWSERBASE_ADVANCED_STEALTH` without API key, debug flags)
3. **Check all profiles** — apply same review to `~/.hermes/profiles/jf/` and `~/.hermes/profiles/ws/`
4. **Apply fixes** — remove lines from `.env` using `sed -i`, enable/disable plugins in `config.yaml` via `sed -i`
5. **Verify** — confirm with `grep` that lines are gone; check `ops check` if applicable
6. **Restart services** — restart any affected systemd user services

> **Rule of thumb**: keep `.env` for secrets only (API keys, tokens). All behavioral settings belong in `config.yaml`. See `references/kanban-notification-pipeline.md` for the kanban event flow and truncation chain when debugging truncated notification messages.

## Kanban Event Watcher Maintenance

The kanban event watcher is a standalone daemon (`kanban-event-watcher.service`) that polls all boards' `task_events` tables and sends Telegram notifications via @AmHousingBot. It is independent of Hermes' built-in notifier.

### Quick Reference

```bash
# Restart after modifications
systemctl --user restart kanban-event-watcher.service
# Check status
systemctl --user status kanban-event-watcher.service --no-pager -l
```

### Truncation Limits

When modifying the event watcher's truncation limits, also update the orchestrator (`orchestrator_daemon.py`) to keep them in sync:

| Field | Event Watcher | Orchestrator |
|-------|:------------:|:------------:|
| Title | 1000 | 1000 |
| Summary | 2000 | — |
| Reason/Error | 2000 | 2000 |

### Pitfall: Summary Truncation in Hermes Core

Hermes core (`kanban_db.py`) caps the event payload summary at **400 chars**. The full summary is stored in `task_runs.summary`. The event watcher works around this by reading from `task_runs` directly — **do not modify Hermes core code**.

### Related

See `references/kanban-event-watcher.md` for full architecture details (boards, events, data flow, service config).

---

## Reference

### Notification Rules

All workflows output `[SILENT]` and send notifications directly via curl to @AmHousingBot Telegram API — never through cron delivery.

### Known Pitfalls

**Dedup suppresses re-alerts when alert task is resolved but issue persists.**
The dedup mechanism (`engine/lib.sh`, `ops_task_exists_for`) stores the kanban task ID when an alert fires. On subsequent checks, if that task still exists and is not "done" or "archived", it skips. But if the task was archived/resolved without fixing the root cause, the dedup entry still blocks re-alerting.

This means: if someone archives an alert kanban task but the service is still down, auto-devops will NOT re-alert. Fix: when closing an alert task manually, also clear the dedup entry (`~/projects/auto-devops/.cache/dedup.json`), or run `./bin/ops run --service <name>` to force a fresh check.

### File Locations

Adding a service to `config.yaml` and creating a check script in `checks/` is NOT
enough on its own. Auto-devops checks must be **scheduled** to run — the project
has no daemon, no systemd service, no systemd timer, and no cron job by default.

If checks never fire, it's usually because no scheduling mechanism was installed.
To set up periodic execution:

```bash
# Option A: systemd timer (preferred)
# Create ~/.config/systemd/user/auto-devops-check.timer
# that runs ./bin/ops run --all periodically

# Option B: cron
crontab -e
# */5 * * * * cd ~/projects/auto-devops && ./bin/ops run --all
```

Check current scheduling status:

```bash
systemctl --user list-timers 2>/dev/null | grep auto-devops
crontab -l 2>/dev/null | grep auto-devops
```

### File Locations

| Path | What it is |
|------|-----------|
| `~/projects/auto-devops/` | The project — `config.yaml` (services), `checks/` (check scripts), `engine/` (runner, backup-runner functions), `bin/ops` (CLI) |
| `~/projects/auto-devops/.env` | Shared credential hub (Telegram bot tokens, SMTP passwords, IMAP credentials) — consumed by kanban-event-watcher, imap-telegram, email-sender, various scripts |
| `~/projects/auto-devops/scripts/backups/` | Modular per-project backup execution scripts (registered via `backup_script` in config.yaml) |
| `~/projects/auto-devops/scripts/backup.sh` | Config-driven thin wrapper (dispatches to all registered backup scripts) |
| `~/projects/auto-devops/engine/lib.sh` | Shared library: `ops_backup_run_all()` + `ops_backup_send_report()` |
| `~/projects/auto-devops/templates/dev-ops.md` | Deployment contract template — every deployable project copies this |
| `~/projects/auto-devops/config.yaml` | Central config: services (with `backup_script`), thresholds, alerting routing |
| `~/.hermes/profiles/jf/scripts/kanban-event-watcher.py` | Kanban event watcher script — polls all boards' `task_events` table, sends Telegram notifications via @AmHousingBot |
| `~/.config/systemd/user/kanban-event-watcher.service` | Its systemd user unit — loads `EnvironmentFile=%h/projects/auto-devops/.env` |
| `~/.hermes/kanban/boards/ops/` | Ops kanban board |
| `~/projects/wiki/concepts/server-infrastructure.md` | Live ops reference — services, ports, backups, runbook |
| `~/projects/wiki/entities/` | Per-service wiki pages |

### User-Level vs System-Level Services

Auto-devops monitors both. The `type` field in `config.yaml` determines the check:
- `systemd` → `systemctl` (system-level, e.g. `caddy.service`)
- `systemd` (default) → `systemctl --user` (user-level, e.g. `kanban-event-watcher.service`)

When doing incident response, always confirm which level the service runs at before running diagnostics:
```bash
# Check user-level
systemctl --user status the-service.service
# Check system-level
systemctl status the-service.service
# List all user services
systemctl --user list-units --type=service
```

The `ops check` commands handle this automatically via the `--user` flag.

### Testing Gotchas

- **Cache test path mismatch**: `tests/test.sh` used to hardcode `/tmp/.auto-devops-cache.json` while `ops run` writes cache to the path in `config.yaml` (`cache_file` field). Always resolve the cache path from `config.yaml` dynamically in tests instead of hardcoding it. The fix is `cache_file=$(python3 -c "import yaml; ... print(cfg.get('cache_file'))")` then expand `~`.
- **Check count snapshot**: Integration tests that assert exact check counts need updating when checks are added or renamed. The rename from `http-noelias` → `http-wiki-webui` did not change the count but renamed checks, which `ops check list` picks up automatically.

> **Path drift warning:** Per-service backup execution scripts (e.g. `scripts/backups/backup-amhousing.sh`) hardcode the project path and git add glob at creation time. If you change the backup location in a project, update both the project's `scripts/backup.sh` AND the corresponding `scripts/backups/backup-<id>.sh`. Also update `backup_path` in `config.yaml` and regenerate the freshness check if needed.

### Kanban Event Watcher

Refer to `references/kanban-event-watcher.md` for maintenance of the kanban notification script (`kanban-event-watcher.py`), including truncation limits, the Hermes-core 400-char payload bypass, service restart, and cross-component sync with the orchestrator.

### Check Naming Convention

All checks MUST be named by **service ID** (e.g. `svc-wiki-webui`, `http-wiki-webui`, `ssl-wiki-webui`), never by domain name or other aliases.

| Correct | Wrong |
|---------|-------|
| `http-wiki-webui` | `http-noelias` (domain) |
| `ssl-wiki-webui` | `ssl-noelias` |

**Why:** Naming by domain forces a `@meta service_group` mapping that is redundant — the naming itself already encodes the relationship. It breaks consistency with all other checks and confuses incident routing.

**If you find a misnamed check:** rename the file, update its `@meta id` to match, remove the `service_group` override, and update all references (README.md, test assertions, comments in engine/lib.sh, engine/runner.sh). Run tests to verify nothing breaks.
