# Hermes Auxiliary Client Debugging

## Key Logs

```bash
# All auxiliary failures (title generation, compression, vision, etc.)
grep -n "auxiliary\|title_generation\|Title generation" ~/.hermes/logs/errors.log | tail -20
grep -n "auxiliary\|title_generation\|Title generation" ~/.hermes/logs/agent.log | tail -30

# Check what endpoint Hermes actually hit
grep "Auxiliary title_generation" ~/.hermes/logs/agent.log

# Gateway inbound messages (what user saw)
grep "inbound message" ~/.hermes/logs/gateway.log | tail -10
```

## Log Line Patterns

```
# Before failure — shows exact provider/model/URL Hermes resolved to:
INFO agent.auxiliary_client: Auxiliary title_generation: using auto (MiniMax-M2.7) at https://api.minimax.io/v1

# The failure itself:
WARNING agent.title_generator: Title generation failed: 404 page not found
```

## Verify API Keys Are Set

```bash
grep "^MINIMAX_API_KEY=" ~/.hermes/.env | sed 's/=.*/=***/'
# Or for OpenRouter:
grep "^OPENROUTER_API_KEY=" ~/.hermes/.env | sed 's/=.*/=***/'
```

## Quick Endpoint Test

```bash
# MiniMax (Bearer auth on /v1 endpoint)
curl -s -X POST "https://api.minimax.io/v1/chat/completions" \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"MiniMax-M2.7","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}' \
  | jq -r '.choices[0].message.content // .error.message'

# OpenRouter
curl -s -X POST "https://openrouter.ai/api/v1/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"openai/gpt-4o-mini","messages":[{"role":"user","content":"Hi"}],"max_tokens":10}'
```

## Config to Check

```bash
# auxiliary.title_generation config (provider: auto = use main model)
python3 -c "
from hermes_cli.config import load_config
cfg = load_config()
print('auxiliary.title_generation:', cfg.get('auxiliary', {}).get('title_generation'))
print('main model:', cfg.get('model'))
"
```

## URL Rewriting Rules (MiniMax)

```
Provider base_url in config:     https://api.minimax.io/anthropic
Auxiliary client rewrites to:    https://api.minimax.io/v1  (OpenAI SDK compatible)

Provider base_url in config:     https://api.minimaxi.com/anthropic  (China)
Auxiliary client rewrites to:    https://api.minimaxi.com/v1
```

## Python Diagnostic Snippet

```python
from agent.auxiliary_client import (
    _to_openai_base_url,
    _endpoint_speaks_anthropic_messages,
    _requires_bearer_auth,
    _is_third_party_anthropic_endpoint,
)

url = "https://api.minimax.io/anthropic"
print("URL:", url)
print("Rewritten:", _to_openai_base_url(url))
print("Speaks Anthropic:", _endpoint_speaks_anthropic_messages(url))
print("Requires Bearer:", _requires_bearer_auth(url))
print("Is third-party:", _is_third_party_anthropic_endpoint(url))
```
