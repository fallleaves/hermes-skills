# Providers & Model Aliases

Set via `hermes model` (picker) or `hermes setup`. 35+ provider profiles ship as
plugins under `plugins/model-providers/`; user plugins of the same name override.
Full docs: https://hermes-agent.nousresearch.com/docs/integrations/providers

### Providers

| Provider | Auth | Key env var(s) |
|----------|------|----------------|
| openrouter | API key | `OPENROUTER_API_KEY` |
| anthropic | API key | `ANTHROPIC_API_KEY` (also `CLAUDE_CODE_OAUTH_TOKEN`) |
| nous | OAuth device code | `hermes auth add nous` (or `NOUS_API_KEY`) |
| openai-codex | OAuth | `hermes auth add openai-codex` |
| qwen-oauth | OAuth | `hermes auth add qwen-oauth` |
| minimax-oauth | OAuth | `hermes auth add minimax-oauth` |
| copilot | Token | `COPILOT_GITHUB_TOKEN` / `GH_TOKEN` (Copilot device flow — `gh auth login` tokens do NOT work) |
| copilot-acp | External CLI | Copilot CLI on PATH or `COPILOT_CLI_PATH` |
| gemini | API key | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| xai | API key | `XAI_API_KEY` (SuperGrok OAuth also supported) |
| deepseek | API key | `DEEPSEEK_API_KEY` |
| zai (GLM) | API key | `GLM_API_KEY` / `ZAI_API_KEY` |
| minimax / minimax-cn | API key | `MINIMAX_API_KEY` / `MINIMAX_CN_API_KEY` |
| kimi-coding / -cn | API key | `KIMI_API_KEY` / `KIMI_CN_API_KEY` |
| alibaba (+coding-plan) | API key | `DASHSCOPE_API_KEY` / `ALIBABA_CODING_PLAN_API_KEY` |
| xiaomi | API key | `XIAOMI_API_KEY` |
| huggingface | Token | `HF_TOKEN` |
| fireworks / novita / nvidia / deepinfra / gmi / arcee / stepfun / upstage / kilocode / ai-gateway / opencode-zen / opencode-go / ollama-cloud | API key | `<NAME>_API_KEY` |
| bedrock / vertex / azure-foundry | Cloud SDK / key | AWS SDK creds / Vertex ADC / `AZURE_FOUNDRY_API_KEY` |
| custom | Config | `model.base_url` + `model.api_key` in config.yaml |

Multiple credentials per provider pool and rotate automatically (`hermes auth`).
Fallback chain when the primary fails: `hermes fallback add|remove|list`.

### User-defined model aliases

Work with `/model <name>` in CLI and every gateway platform. Resolved by
`hermes_cli/model_switch.py::resolve_alias()`; user aliases are checked BEFORE
the built-in table, so a user `sonnet`/`grok` shadows the built-in.

```yaml
# Full form
model_aliases:
  fav:
    model: claude-sonnet-4.6
    provider: anthropic
  local-qwen:
    model: qwen3.5:397b
    provider: custom
    base_url: "https://ollama.com/v1"
  theta:
    model: theta-1
    provider: custom
    base_url: "https://theta.example.com/v1"
    key_env: THETA_API_KEY        # or: api_key: "${THETA_API_KEY}"

# Short form ("provider/model"), also via CLI:
#   hermes config set model.aliases.fav openrouter/anthropic/claude-sonnet-4.6
model:
  aliases:
    fav: openrouter/anthropic/claude-sonnet-4.6
```

`/model fav` — session-scoped; add `--global` to persist as default.

An alias with its own `base_url` authenticates with its own credential
(`api_key`, which also accepts a `"${VAR}"` reference, or `key_env`). With
neither set the key is resolved from the alias HOST, never carried over from
the provider that was active before the switch.

Built-in aliases (catalog-resolved against the active provider): `sonnet`,
`opus`, `haiku`, `claude`, `gpt5`, `gpt`, `codex`, `o3`, `o4`, `gemini`,
`deepseek`, `grok`, `llama`, `qwen`, `minimax`, `nemotron`, `kimi`, `glm`,
`step`, `mimo`, `trinity`.

### Multimodal input on OpenCode Zen/Go — test it, don't trust the catalog

`opencode-go` / `opencode-zen` (`https://opencode.ai/zen/go|/v1`) require an opaque
`x-opencode-session` header on EVERY request, main turns and aux calls alike
(`agent/opencode_affinity.py`, derived from the Hermes session id; documented in
`website/docs/integrations/providers.md`). A bare request without it fails
`400 MissingSessionID` — that is a missing-header artifact, not a capability verdict,
so reproducing provider behavior outside a real session must set the header itself.

The models.dev catalog overstates video support: it lists 15 of 36 `opencode-go` models
with `video` input, but the relay only accepts an OpenAI-style `video_url` content part
for the Qwen 3.6+/3.7/3.8 line plus `minimax-m3` and `kimi-k2.7-code`. Probed with a real
2 s mp4 as a base64 data URL (`{"type":"video_url","video_url":{"url":"data:video/mp4;base64,…"}}`):

- accepted and actually read the frames: `qwen3.8-flash`, `qwen3.7-plus`, `qwen3.6-plus`,
  `qwen3.8-max`, `minimax-m3`, `kimi-k2.7-code`
- accepted, returned nothing usable: `mimo-v2.5`
- rejected the part (`only text and image_url are …`): `glm-5.3-flash` — the model most
  installs point `auxiliary.vision` at — plus `kimi-k3` and any catalogued image-only
  model (control: `deepseek-v4.1-flash`)
- collapses unrelated to video: `kimi-k2.5` / `qwen3.5-plus` "Model is unavailable",
  `kimi-k2.6` "No endpoints found", `ox-alpha-free` "not supported",
  `muse-spark-1.{2,3}-contributor` 403 DataPolicyError

Consequence for `video_analyze` (opt-in `video` toolset, models.dev independent): the aux
model must accept video. `_configured_aux_model(("video","vision"), …)` resolves
`auxiliary.video.model` first and only then `auxiliary.vision.model`, so point
`auxiliary.video.{provider,model}` at a working pair (e.g. `opencode-go` /
`qwen3.8-flash`) and leave `auxiliary.vision` on the better image model. Enabling the
toolset alone silently keeps video on the image-only aux model, which then fails with a
capability error at call time.
