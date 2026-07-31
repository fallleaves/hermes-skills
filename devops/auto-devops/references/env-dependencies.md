# Auto-Devops Shared `.env` Dependencies

**Last updated:** 2026-07-05

## The Shared Env File

Path: `~/projects/auto-devops/.env`

This file is a shared credential hub consumed by multiple services across different projects. Not all consumers are systemd services — some are CLI scripts or cron jobs.

## Variable → Consumer Map

| Variable | Consumer(s) | Type |
|----------|-------------|------|
| `HEALTH_ALERT_BOT_TOKEN` | `kanban-event-watcher.service` (systemd user), `auto-devops` notification scripts | Telegram bot token for @AmHousingBot |
| `HEALTH_ALERT_CHAT_ID` | `kanban-event-watcher.service`, `auto-devops` notification scripts | Telegram chat ID for alerts |
| `IMAP_TELEGRAM_BOT_TOKEN` | `imap-telegram.service` (systemd user) | Telegram bot token for IMAP→Telegram forwarder |
| `IMAP_TELEGRAM_CHAT_ID` | `imap-telegram.service` | Telegram chat ID for email forwarder |
| `EMAIL_ADDRESS` | `imap-telegram.service` (IMAP login), various scripts | Gmail address |
| `EMAIL_PASSWORD` | `imap-telegram.service` (IMAP app password), various scripts | Gmail app password |
| ~~`EMAIL_SMTP_USER`~~ | ~~`utilities/email-sender/send_email.py`~~ | **Removed 2026-07-05** — moved to `utilities/email-sender/.env` (self-contained) |
| ~~`EMAIL_SMTP_PASSWORD`~~ | ~~`utilities/email-sender/send_email.py`~~ | **Removed 2026-07-05** — moved to `utilities/email-sender/.env` |

## Service Details

### kanban-event-watcher.service

- **Unit:** `~/.config/systemd/user/kanban-event-watcher.service`
- **Script:** `~/.hermes/profiles/jf/scripts/kanban-event-watcher.py`
- **Purpose:** Polls all kanban boards' `task_events` table, sends Telegram notifications for meaningful events (created, completed, blocked, crashed, etc.)
- **Credentials used:** `HEALTH_ALERT_BOT_TOKEN`, `HEALTH_ALERT_CHAT_ID`
- **Restart:** `systemctl --user restart kanban-event-watcher.service`
- **Truncation limits** (in the Python script):
  - Title: 1000 chars
  - Summary (completed): 2000 chars
  - Reason (blocked): 2000 chars
  - Error (crashed): 2000 chars

### imap-telegram.service

- **Unit:** `~/.config/systemd/user/imap-telegram.service`
- **Script:** `~/projects/microservices/imap-telegram/imap_to_telegram.py`
- **Purpose:** Monitors `firstseptember2021@gmail.com` inbox via IMAP, forwards new emails to Telegram chat
- **Credentials used:** `IMAP_TELEGRAM_BOT_TOKEN`, `IMAP_TELEGRAM_CHAT_ID`, `EMAIL_ADDRESS`, `EMAIL_PASSWORD`

## Making a Script Self-Contained

When extracting a script from the shared credential hub, follow this pattern (used for `utilities/email-sender/send_email.py` on 2026-07-05):

1. Create `<script-dir>/.env` with the credential(s)
2. Create `<script-dir>/.env.example` with placeholder values (safe to commit)
3. Create `<script-dir>/.gitignore` adding `.env`
4. Change the script's fallback path from `~/.config/auto-devops/env` to `os.path.join(os.path.dirname(__file__), ".env")`
5. Remove the variables from `~/projects/auto-devops/.env`
6. Commit all changes, verify consumers still work
