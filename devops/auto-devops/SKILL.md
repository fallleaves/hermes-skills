---
name: auto-devops
description: "Ops worker skill — respond to kanban tasks: incident response, add monitoring, deploy projects."
version: 4.0.0
author: Hermes Agent
tags: [ops, automation, monitoring, kanban, incident-response, onboarding, deploy]
---

# Auto DevOps — Ops Worker Skill

Guidance for operating the Auto DevOps framework at `~/projects/auto-devops/`. This skill routes tasks and gives the non-obvious operating facts. The framework itself (CLI `bin/ops`, `engine/`, `checks/`, `config.yaml`, `tests/`) is the source of truth for details — run `./bin/ops help` for the full CLI surface.

## Dispatch — What to Run

| Kanban task title starts with… | Do this |
|--------------------------------|---------|
| `🛑` / `HTTP endpoint returned` / `Disk usage at` / `Memory at` / `Backup` / `SSL certificate` | **Incident Response** — diagnose, fix, verify, close |
| `📦 New service:` | **Add to Monitoring** |
| `🗑 Remove:` | **Remove from Monitoring** |
| `🚀 Deploy:` | **Deploy Project** |
| `🔧 Config audit` / `cfg audit` / `清理配置` | **Configuration Audit** |

No task context → point to `~/projects/auto-devops/`.

## Core operating facts

- **Scheduling**: `ops-health.timer` (every 5 min → `./bin/ops run --cron`) and `daily-backup.timer` (03:00 → `scripts/backup.sh`) run everything. New services in `config.yaml` are picked up automatically.
- **Alerting**: a check must fail 2 consecutive ticks before an alert task fires (`alert_after_sec` in config.yaml — currently 180s, code default 600s). First failing tick only records `.cache/failstate.json`. Tasks appearing right after a deploy window are expected.
- **Checks**: one script per check in `checks/`, named by **service ID** — `svc-<id>`, `http-<id>`, `ssl-<id>`, `backup-<id>`; never by domain. Each prints one line of JSON: `{"status":"ok"}` or `{"status":"fail","title","body","priority"}` (priority ≥100 → Telegram+kanban, ≥50 → kanban only).
- **User vs system**: `svc-*` checks use `systemctl --user`; system-level infra uses hand-written `sys-svc-<id>.sh` (plain `systemctl`) + `infra_services` entry with `type: system`.
- **Backups**: the scaffold generates the wrapper — it runs the project's `scripts/backup.sh`, then pushes the backup dir to a dedicated **private** GitHub repo `<account>/<id>-backups` (HTTPS + gh auth). The project's `dev-ops.md` states only *how* + *where*; the framework owns schedule, storage, and push.
- **Maintenance**: `ops pause <svc>|--all [--reason]` / `ops resume` — paused services show `[PAUSED]` in `ops check list`; do NOT "fix" a paused service during incidents.
- **Git**: auto-devops repo branch is `master` (push `origin master`); the wiki repo is separate, pushed via `ops wiki commit`.
- **Gateway**: never `systemctl --user stop/restart` a hermes-gateway from inside a gateway session — it kills the session. Use `hermes gateway restart` from outside, or `delegate_task`.
- **Verify everything** with `./bin/ops run --service <id>` (substring match: `hermes` also matches `hermes-jf`/`hermes-ws`) and the suites: `bash tests/test.sh` (integration + Python unit suites for health.py/scaffold.py), `bash tests/test_lib.sh` (engine unit tests: lib/router/runner/backup).

## Workflows

### Incident Response
1. Extract the project from the task body (`📄 dev-ops: <path>` / `📖 Wiki: entities/<id>.md`).
2. Read the project's `dev-ops.md` — the **Troubleshooting** section is the runbook — plus its wiki entity page.
3. Follow the runbook; generic fallback: systemd status + journal → curl the port → fix.
4. Verify all checks pass (`./bin/ops run --service <project>`), then `kanban_complete(...)`; if unfixable → `kanban_block(reason=...)`.

### Add a Service to Monitoring
1. Identify type: `systemctl --user cat <id>.service` / `systemctl cat` / docker.
2. Generate checks:
   ```bash
   ./bin/ops check new svc:<id> --unit <id>.service [--name "..."] \
     [--http /:port] [--backup "~/backups/<id>/<id>.*.gz"]
   ```
   This creates the check scripts, registers the service in `config.yaml`, and (with `--backup`) creates the private backups repo. Backup globs: the scaffold FIRST reads the project's `dev-ops.md` Backup Guide for a `- **Backup files:** \`glob1\`, \`glob2\`` line (comma-separated, multi-artifact) — `--backup` is only a fallback when the contract declares none. The generated freshness check verifies EACH pattern independently (a fresh archive must not mask a stale one), so the contract is the single source of truth for what gets monitored. Add `./bin/ops check new ssl:<id> --domain <domain>` if domain-served.
3. System-level services: hand-write `sys-svc-<id>.sh` (copy `checks/sys-svc-caddy.sh`).
4. Verify (`ops run --service <id>`), commit auto-devops (`git push origin master`), `ops wiki commit`.
5. Note: `--backup` requires the project repo to already exist with a GitHub `origin` (the backups remote is derived from it).

### Deploy a Project
1. `dev-ops.md` at the repo root is the contract — missing → `kanban_block` with `~/projects/auto-devops/templates/dev-ops.md`.
2. Follow its Build/Deploy guides; auto-discover and monitor its Service Dependencies; set up `.env` from the listed vars.
3. Run the deployment checklist, add monitoring (see above), commit + `ops wiki commit`, close.

### Remove a Service
1. Delete: the `config.yaml` entry, `svc-<id>.sh` + companion checks (`http-/ssl-/backup-<id>.sh`), and the wrapper `scripts/backups/backup-<id>.sh`; consciously keep or archive the private `<id>-backups` repo.
2. Clean all wiki references (grep the wiki); verify zero hits in both repos; commit both; close.

### Watchdog Script Service
For daemon scripts needing supervision (e.g. kanban-blocked-bridge): require `--daemon`/`--interval` flags, run under a systemd user unit with `Restart=on-failure`, register with `ops check new svc:`.

### Decouple a Service from Auto-Devops Dependencies
Relocate env/config into the project (project-local `.env`/`config.yaml`, `EnvironmentFile` update). Monitoring is unaffected **as long as the unit name stays the same** — check scripts only test `systemctl --user is-active <unit>`. Verify with `ops run --service <id>`.

### Configuration Audit
Compare `.env` vs `config.yaml` across profiles: flag redundant, conflicting, and dead vars; keep `.env` for secrets only; fix, verify, restart affected services.

## Reference

- `~/projects/auto-devops/` — `bin/ops` (CLI), `engine/` (runner, scaffold, router, backup-runner), `checks/`, `scripts/backups/`, `config.yaml`, `templates/dev-ops.md`, `tests/test.sh`
- Troubleshooting specifics live in each project's `dev-ops.md`; framework internals in the repo + test suite.
