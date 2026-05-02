# MiniMax Provider Internals

Three MiniMax provider variants exist in Hermes, all using `anthropic_messages` transport:

| Provider | Auth | Base URL env | Default aux model |
|---|---|---|---|
| `minimax` | `api_key` | `MINIMAX_BASE_URL` | `MiniMax-M2.7` |
| `minimax-oauth` | `oauth_external` | — (hardcoded to `api.minimax.io/anthropic`) | `MiniMax-M2.7-highspeed` |
| `minimax-cn` | `api_key` | `MINIMAX_CN_BASE_URL` | `MiniMax-M2.7` |

All three are in `_ANTHROPIC_COMPAT_PROVIDERS` and `_MATCHING_PREFIX_STRIP_PROVIDERS`.

## Dot Preservation

Model names like `MiniMax-M2.7` keep their dots — they are NOT converted to `MiniMax-M2-7`. This is because `minimax` is in `_MATCHING_PREFIX_STRIP_PROVIDERS` in `model_normalize.py`, which skips the dot→hyphen normalization that applies to native Anthropic models.

## Beta Header Rules

In `build_anthropic_client()` → `_common_betas_for_base_url()`:
- `fine-grained-tool-streaming-2025-05-14` is **excluded** for MiniMax global (`api.minimax.io`) and China (`api.minimaxi.com`) endpoints
- `interleaved-thinking-2025-05-14` is **included** for both

This was issue #6510/#6555 — MiniMax's endpoint rejects the tool-streaming beta.

## Title Generation Routing

When `title_generation` auxiliary task runs with `provider: auto` (default):

```
call_llm(task="title_generation", main_runtime={...})
  → _resolve_auto(main_runtime)
    → Step 1: main_provider + main_model
      → If main_provider = "minimax" and main_model = "MiniMax-M2.7"
      → resolve_provider_client("minimax", "MiniMax-M2.7")
        → pool lookup for MINIMAX_API_KEY
        → _maybe_wrap_anthropic() → AnthropicAuxiliaryClient
      → returns (client, "MiniMax-M2.7")  ← uses YOUR MiniMax key
```

If Step 1 fails (no main runtime, no MiniMax credentials), the fallback chain at `_resolve_auto()` tries OpenRouter → Nous → API-key providers. For `minimax` in that chain, it uses `MINIMAX_API_KEY` env var and `MiniMax-M2.7` as aux model.

## Credential Guard (Critical)

Both `AIAgent.__init__` (line ~1330) and `AIAgent.switch_model()` (line ~2246) have an explicit guard:

```python
_is_native_anthropic = self.provider == "anthropic"
effective_key = (api_key or resolve_anthropic_token() or "") if _is_native_anthropic else (api_key or self.api_key or "")
```

For any `minimax` variant, `resolve_anthropic_token()` is **never called**. Your MiniMax API key cannot accidentally fall through to an Anthropic credential lookup.

## Max Output Tokens

All MiniMax models: 131,072 tokens (hardcoded in `_get_anthropic_max_output`).

## Thinking Config

MiniMax gets **manual thinking** (`type: "enabled"`, `budget_tokens`), NOT adaptive thinking. Adaptive thinking is Claude 4.6+ only.
