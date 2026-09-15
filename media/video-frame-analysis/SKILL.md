---
name: video-frame-analysis
description: Use when deeply analyzing a video's content and motion.
---

# Deep video analysis (video model + frame montages)

Use when a user sends a video and wants real content analysis (sports technique, incidents, screen recordings, event timelines) — not just "what is this". The video model gives motion/timeline; self-built frame montages give the fine detail it cannot.

## Pipeline

1. **Measure the file first** — never guess size/format:
   `ffprobe -v error -show_entries format=duration,size,bit_rate -show_entries stream=codec_type,codec_name,width,height,avg_frame_rate,nb_frames -of default=noprint_wrappers=1 FILE`
2. **Whole-clip pass, twice, with different prompts** (they produce different structures):
   - pass 1: "describe second by second with timestamps, what happens, who/what/where"
   - pass 2: "from the perspective of an expert in <domain>, analyze <the specific dimensions the user asked about>; cite the timestamp/visual evidence for each claim and say explicitly what you cannot tell"
   Run them as separate `video_analyze` calls — local tools cannot be batched in one `tool_call`, so they are always serial.
3. **Build frame montages with ffmpeg + PIL** (`scripts/frame_montage.py`): extract single frames at chosen timestamps, crop to the region of interest, upscale, label each cell with its timestamp, tile into one image. One image per question = one vision call covering many moments.
   - Crop for the subject, not the whole frame: a player/panel/counter region zooms far more than a full frame.
   - **Verify the crop on the first grid** (ask the vision model "is a complete person visible in each cell, and if not say so") before building more grids from the same coordinates.
   - Dense sequences (3–6 consecutive frames ~0.3 s apart) are what settle motion questions: swing arc, follow-through end position, contact point.
4. **Cross-check, then adjudicate conflicts yourself**:
   - Treat repeated agreement across the two routes as fact.
   - Static-posture conflicts (paddle angle, follow-through end position) → trust the frame montage, and say in the answer that the two passes disagreed.
   - Timeline conflicts → trust the whole-clip pass, but verify 2–3 key moments by extracting a frame at that timestamp.
   - Discard claims the medium cannot carry (see pitfalls).
5. **Answer with evidence + an explicit uncertainty section**: which conclusions rest on which timestamps, and what the sample cannot support (a 15 s clip cannot yield a level assessment).

## Pitfalls (all verified)

- **No audio is sent.** Code builds one `{type: video_url}` part; a video model that says "no audio track" is right about its input even when the file has an AAC stream. Measure audio yourself with `ffmpeg -i F -af volumedetect -f null - 2>&1 | grep -E 'mean_volume|max_volume'` and never report model-invented sound descriptions.
- **A model may narrate sounds it never received** ("ball hitting the paddle", "crowd noise") — treat any unmeasured audio claim as fabrication.
- **Video models self-estimate timestamps** and can be off; verify key moments with a frame.
- **Very short clips (<~1 s) are rejected** by at least one provider ("The video file is too short"), which reads as a capability failure but is not one. A 3 s test clip is the safe smoke test.
- **An image-only model cannot take a video**: deepseek-v4.1-flash 400s with `unknown variant 'video_url'`. Check `modalities.input` for `video` in the provider/model catalog before assuming.
- **Frame montages are snapshots**: motion, momentum and "airborne" claims are inferences — label them.
- Prefer JPEG (~90) for montages; keep each image well under the 20 MB base64 image cap. Video tool cap is 50 MB base64 (~37 MB real file) with a warning past 20 MB.
- Leave the montages somewhere durable (e.g. `$HERMES_HOME/cache/<topic>/`) and attach one to the answer — the user can check the evidence themselves.

## References

- `references/vision-routing.md` — which model actually serves images/video, and why images cannot be attached natively.
- `scripts/frame_montage.py` — parameterized montage builder (timestamps, crop boxes, labels, grid size).
