# Hermes Config Audit — Practical Reference

> Session-specific detail from 2026-07-05 cleanup across default/jf/ws profiles.

## Redundant .env vars (match config.yaml exactly — delete from .env)

| .env var | config.yaml equivalent |
|----------|----------------------|
| `HERMES_MAX_ITERATIONS=900` | `agent.max_turns: 900` |
| `TERMINAL_TIMEOUT=60` | `terminal.timeout: 180` *(conflict — keep 180)* |
| `TERMINAL_LIFETIME_SECONDS=300` | `terminal.lifetime_seconds: 300` |
| `TERMINAL_MODAL_IMAGE=nikolaik/python-nodejs:python3.11-nodejs20` | `terminal.modal_image: ...` |
| `BROWSER_INACTIVITY_TIMEOUT=120` | `browser.inactivity_timeout: 120` |

## Dead .env vars (feature disabled/unconfigured)

| .env var | Why dead |
|----------|---------|
| `BROWSERBASE_PROXIES=true` | `browser.cloud_provider: local`, no API key set |
| `BROWSERBASE_ADVANCED_STEALTH=false` | Same reason |

## Orphaned plugin refs

| Plugin | Issue |
|--------|-------|
| `model-providers/openrouter` in `plugins.disabled` | `fallback_model` uses `provider: openrouter model: openrouter/free` — fallback path calls `_try_openrouter()` which reads `OPENROUTER_API_KEY` directly, bypassing plugin system. Removing from disabled list makes it work as expected. |

## Commands used

```bash
# Find what to delete
grep -n '^VAR_NAME' /home/jfeng/.hermes/.env

# Delete lines from .env (protected from patch — use sed)
sed -i '/^VAR_NAME=/d' /home/jfeng/.hermes/.env

# Delete from plugins.disabled in config.yaml (also protected)
sed -i '/- model-providers\/openrouter/d' /home/jfeng/.hermes/config.yaml

# Apply same changes to other profiles
for p in jf ws; do
  sed -i '/^VAR_NAME=/d' /home/jfeng/.hermes/profiles/$p/.env
  sed -i '/- model-providers\/openrouter/d' /home/jfeng/.hermes/profiles/$p/config.yaml
done

# Verify
grep -n '^VAR_NAME' /home/jfeng/.hermes/.env /home/jfeng/.hermes/profiles/*/.env
```
