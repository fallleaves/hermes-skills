# Which model actually serves vision/video (Hermes, opencode-go)

Verified 2026-09 by reading `tools/vision_tools.py` + provider plugins and by live provider probes.

## Routing on opencode-go

- **Images always go through the aux vision model.** The `opencode-go` `ProviderProfile` sets
  `supports_vision_tool_messages=False` because the Go relay validates tool content as a strict
  string: native image embeds 422 (`messages.N.tool.content.str Input should be a valid string`)
  or 400 (`text is not set`), and the rejected row stays in history so every later call fails too.
  `tools/vision_tools.py:_should_use_native_vision_fast_path()` therefore always returns False here.
- An explicitly configured `auxiliary.vision` also forces `decide_image_input_mode()` to `text`
  (`_explicit_aux_vision_override`), independent of the provider profile.
- Handler chain: `_handle_vision_analyze` → `_configured_aux_model(("vision",), ...)` →
  `async_call_llm(task="vision", temperature=0.1, timeout=auxiliary.vision.timeout)`;
  video the same but `_configured_aux_model(("video","vision"), ...)` with `timeout max(120, 180)`.
- Config keys that matter: `auxiliary.vision.{provider,model}` and `auxiliary.video.model`
  (video has no provider key; it falls back to the main provider). Current: vision =
  `opencode-go/deepseek-v4.1-flash`, video = `qwen3.8-flash`.

## Capability facts (measured, not documentation)

- `deepseek-v4.1-flash` + `video_url` → **HTTP 400** `unknown variant 'video_url', expected one of
  'text', 'image_url', 'file'`. Image parts work (HTTP 200). So the video slot must stay on a
  video-capable model — writing DeepSeek there kills `video_analyze` outright.
- The `file` part variant is for PDFs (needs `file_id`/`file_data` from an upload, and qwen rejects
  PDFs with "does not support PDF file input") — not a video bypass.
- `qwen3.8-flash` + `video_url` → HTTP 200 on a 3 s clip; a 0.8 s clip 400s "video file is too short".
- opencode-go models declaring `video` input in the catalog: qwen3.5-plus, qwen3.6-plus, qwen3.7-plus,
  qwen3.8-flash, qwen3.8-max, minimax-m3, kimi-k2.5/k2.6/k2.7-code/k3, mimo-v2.5, ox-alpha-free,
  muse-spark-1.2/1.3-contributor, glm-5.3-flash (declared, but observed to reject video),
  deepseek-v4-flash-vision-exp is image-only.

## Probes

Provider requests need `Authorization: Bearer $OPENCODE_GO_API_KEY` (read it from the profile `.env`,
never print it) **and** an `x-opencode-session` header — without it every request 400s with
`MissingSessionID` regardless of payload validity.
