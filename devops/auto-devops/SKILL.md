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
- **False-positive restarts**: on this box, other agent sessions (e.g. the `ws` gateway doing amhousing feature work) routinely run `npm run build && systemctl --user restart amhousing.service` — a <1s restart window colliding with a tick produces an `HTTP endpoint returned 000` alert for a service that never went down. Before treating a 000/svc alert as an outage, diff `journalctl --user -u <unit> --since` stop/start times against deploys (`gh run list`) AND check the ws session history (`session_search(profile='ws', query='restart <unit>', sort='newest')`). Restarts are an expected alert source — verify and close, don't "fix".
- **amhousing deploy-gate failures (recurring)**: any `amhousing.nl HTTP endpoint returned 000` lately likely = a FAILED deploy, not a false positive: the workflow's `prisma migrate deploy` gate (deploy.yml ~L96) takes a write lock even when there are NO pending migrations (SQLite busy_timeout=0, WAL) and can lose the race to the message-agent daemon's 5s polls/hermes workers (and to ws-gateway sessions doing direct sqlite3 on amhousing.db during deploys), so `restore_previous_build` runs: service down ~36s, then healthy. Diagnosis: `gh run list` conclusions (failure) + journal stop/start vs run `createdAt`; service is usually ALREADY healthy — verify (curl + `ops run --service amhousing`) and close, then check whether a follow-up task exists for the gate fix.
- **hermes-amhousing-app toolset closure (fail-closed)**: the tenant gateway's profile (`~/.hermes/profiles/amhousing-app/config.yaml`) must keep `platform_toolsets.amhousing` EXACTLY `[amhousing, web, vision]` — the adapter asserts it at start and otherwise exits `78/CONFIG`, and `RestartPreventExitStatus=78` leaves the unit `failed` instead of looping (so this alert means config drift, not a crash). `hermes update` config migrations widen saved toolset lists (44→45 appended `connections`), so expect this alert right after an update: fix = restore the exact list, keep `agent.disabled_toolsets: [connections]` (that decline marker makes the migration skip), then start the unit. Pre-write copies live in `~/.hermes/profiles/amhousing-app/backups/config/`.
- **Checks**: one script per check in `checks/`, named by **service ID** — `svc-<id>`, `http-<id>`, `ssl-<id>`, `backup-<id>`; never by domain. Each prints one line of JSON: `{"status":"ok"}` or `{"status":"fail","title","body","priority"}` (priority ≥100 → Telegram+kanban, ≥50 → kanban only).
- **User vs system**: `svc-*` checks use `systemctl --user`; system-level infra uses hand-written `sys-svc-<id>.sh` (plain `systemctl`) + `infra_services` entry with `type: system`.
- **Backups**: the scaffold generates the wrapper — it runs the project's `scripts/backup.sh`, then pushes the backup dir to a dedicated **private** GitHub repo `<account>/<id>-backups` (HTTPS + gh auth). The project's `dev-ops.md` states only *how* + *where*; the framework owns schedule, storage, and push.
- **Maintenance**: `ops pause <svc>|--all [--reason]` / `ops resume` — paused services show `[PAUSED]` in `ops check list`; do NOT "fix" a paused service during incidents.
- **Git**: auto-devops repo branch is `main` (push `origin main`); the wiki repo is separate, pushed via `ops wiki commit`.
- **Gateway**: ONE `hermes-gateway.service` process serves EVERY profile (multiplexed — `gateway.multiplex_profiles: true` in the DEFAULT profile's config; the per-profile `hermes-gateway-<profile>.service` units are retired). Restarting it drops every profile's adapters, including the session you are running in — never `systemctl --user stop/restart` a hermes-gateway from inside a gateway session; use `hermes gateway restart` from outside, or `delegate_task`. In a headless `-q` kanban worker (`approvals.single_query_mode: deny`), ANY `systemctl` lifecycle verb on a hermes-gateway unit AND `hermes gateway stop|restart` / `hermes update` are approval-blocked — the sanctioned recovery there is `hermes -p <profile> gateway start` (starts the unit, kills nothing).
- **Multiplexed gateway health (`svc-hermes-gateway`)**: the check is not just `systemctl is-active` — it reads the multiplexer's own `~/.hermes/gateway_state.json` (DEFAULT profile home) and fails when (a) a platform the process started is not `connected` (a revoked bot token shows up as `fatal` / `telegram_auth_error`), or (b) a served profile has NO connected platform at all (its adapter failed to build — grep the log for `[MULTIPLEX] Profile '<p>': skipping platform`). Secondaries appear as `<profile>:<platform>`; the default profile's keys are unscoped. A platform with no credential in that profile's own `.env` is skipped ON PURPOSE — not an outage. Ground truth: `hermes gateway status`, `~/.hermes/gateway_state.json`, `journalctl --user -u hermes-gateway`.
- **Plugin adapters must read env scope-aware**: under multiplexing a profile's credentials live only in its secret scope — `os.environ` carries the DEFAULT profile's values, and a scoped miss returns the default rather than borrowing. A plugin that probes credentials with a raw `os.getenv` (the amhousing adapter's `check_requirements`, `_setting`, `tool.py`) fails closed at adapter creation for every secondary profile, so the platform is skipped and its users silently get nothing. Fix = `gateway.platforms._shared.get_scoped_secret` for credentials and `get_hermes_home()` for paths, never `os.getenv`.
- **Alert tasks that end as "Agent crash x2 — protocol violation" are usually a DEAD PROVIDER, not a hard fix**: a worker that dies before its first tool call (e.g. `HTTP 401: Insufficient balance` from opencode.ai) exits rc=0 without calling `kanban_complete`/`kanban_block`, so the board only shows the protocol violation. Run `hermes kanban runs <task>` / `hermes kanban log <task>` and read the transcript before concluding anything about the service. Under the multiplexed gateway the dispatcher runs in the DEFAULT profile and reads `kanban.default_assignee` / `kanban.orchestrator_profile` from it, so every task is spawned with THAT profile's credentials — whose provider key answers 401. Both values now point at `jf` (2026-09-14): never route kanban work back to `default` while its key is unfunded, and check the assignee profile's provider before concluding a service is unfixable.
- **`hermes-gateway` alert naming `jf:discord` (`discord_connect_error`) — check the vendor before the box**: a Discord "Session Unavailability" incident (discordstatus.com) makes the gateway WS handshake return `503` (`Retry-After: 5`) and the authenticated REST endpoints (`/users/@me`, `/gateway/bot`) return `500`, so no session can be established; the network path (ping ≈1.4 ms, 0 % loss), the gateway process and every other platform stay fine, and the multiplexer's secondary reconnect loop self-heals (backoff 30s→300s, `✓ discord reconnected (profile: jf)` in the profile's own log). Multiplexed profiles' adapter lines land in `profiles/<p>/logs/agent.log` (plus the journal at WARNING+), NOT in `~/.hermes/logs/gateway.log` — read there before concluding anything.
- **After such a reconnect the platform stays `fatal` in `gateway_state.json` — a stale-state false positive, not an outage**: the Discord plugin never called the base `_mark_connected()` (its `connect()` only set `_running = True`) and the secondary reconnect success path only logs, so the `fatal` entry survives a successful reconnect and `svc-hermes-gateway` keeps alerting. **Root cause fixed upstream in `ec11359b44`** ("fix(discord): clear fatal status on successful reconnect", `Fixes #102554`, landed in upstream `main` 2026-09-15), with the identical hunk applied to this box's install tree as an uncommitted working-tree edit plus a local regression test (`tests/gateway/test_discord_runtime_status_publish.py`) — full write-up in `entities/hermes-gateway.md`. The RUNNING process still carries the pre-fix module, and a profile re-scan cannot rebuild it (`_start_one_profile_adapters` skips platforms already live *or* queued for reconnect, so touching `profiles/<p>/.env` + the `rescan-profiles` control verb is a no-op) — so the stale entry clears at the next gateway restart, which the next `hermes update` performs anyway; a headless worker can only `kanban_block(kind='capability')` for a human to run `hermes gateway restart` (startup clears the profile-scoped keys, which converges the check). Treat a fresh `jf:discord fatal (discord_connect_error)` as REAL until the fixed module is loaded (restart/update), and re-verify with `./bin/ops run --service hermes`.
- **Patching the hermes-agent install tree (out-of-band fixes)**: `~/.hermes/hermes-agent` is a plain git checkout of upstream, so when upstream ALREADY carries the fix, apply it as an **uncommitted working-tree edit byte-identical to the upstream commit** (`git cherry-pick -n <sha>` gives exactly that): never `git commit` it — a local commit makes `hermes update`'s ff-merge diverge and it gets auto-discarded. Add extra regression tests as NEW untracked files (an edit to an upstream test file is fine too, as long as it matches upstream), and verify with `./venv/bin/python -m pytest <file> -q`. `hermes update` autostashes the edit, pulls, and restores cleanly when both sides hold the same change (discard the autostash — upstream's copy is authoritative — if it ever conflicts). Baseline your run: `tests/gateway/*` shows pre-existing per-process failures when many discord files share one pytest process (cross-file pollution) and ambient env (`DISCORD_ALLOW_BOTS=mentions`) — run the fixtures per file and diff the FAILED set with and without the patch, rather than assuming you broke something.
- **Verify everything** with `./bin/ops run --service <id>` (substring match: `hermes` matches `svc-hermes-gateway`) and the suites: `bash tests/test.sh` (integration + Python unit suites for health.py/scaffold.py), `bash tests/test_lib.sh` (engine unit tests: lib/router/runner/backup).
- **`tests/test.sh` must keep running while the fleet is unhealthy — never reintroduce a `set -e` abort**: under `set -euo pipefail` a bare `var=$(...)` capture of `bin/ops` (health exits 1 when ANY check fails; run exits with the failed count; the sandbox runs real units) or of a `grep` whose no-match is legitimate ends the run with rc=1 and no ✗ line. Guard with `|| true` OUTSIDE the substitution — `cmd || true | tail -1` pipes `true`, not `cmd` — and write section summaries as `if [[ $errors -eq 0 ]]; then pass ...; fi`, never as a trailing `[[ $errors -eq 0 ]] && pass ...` (its return status is the function's, so `set -e` aborts the run before the remaining sections and the final summary print). To validate a suite change against a failing check, copy the repo to /tmp and inject a well-formed failing check (`# @meta id: <type>:<name>`, file `checks/<type>-<name>.sh`) into the COPY's `checks/` — injecting into the live `checks/` makes `ops-health.timer` raise a bogus alert task.

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
4. Verify (`ops run --service <id>`), commit auto-devops (`git push origin main`), `ops wiki commit`.
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
