---
name: creative
description: "Unified creative content generation — ASCII art, video production, comic creation, infographics, UI prototyping, technical diagrams, generative visuals, and AI-assisted music/songwriting. Use when users request: generate/create/make ASCII art, video, comic, infographic, design mockup, diagram, pixel art, animation, music, or any visual/audio creative output."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Creative, Art, Design, Visual, Audio, Video, Generation, ASCII, UI, Diagrams]
    umbrella: true
---

# Creative Production Library

A unified entry point for all visual and audio creative generation. Each § represents a specialized mode; see the sub-skill for full detail.

## Quick Decision Tree

| User wants | § to use |
|------------|----------|
| Text as large ASCII banner | § ASCII-Art → Tool 1 (pyfiglet) |
| ASCII art from image | § ASCII-Art → Tool 6 (ascii-image-converter) |
| ASCII video / animated ASCII | § ASCII-Video |
| Comic / graphic novel art | § Baoyu-Comic |
| Professional infographic | § Baoyu-Infographic |
| Hand-drawn style diagram | § Excalidraw |
| Dark-themed system architecture diagram | § Architecture-Diagram |
| Pixel art from image | § Pixel-Art |
| HTML prototype / UI mockup | § Sketch or § Claude-Design |
| Design system reference | § Popular-Web-Designs |
| p5.js interactive sketch | § P5JS |
| Manim math animation | § Manim-Video |
| TouchDesigner generative | § TouchDesigner-MCP |
| AI-generated music / song | § Songwriting-and-AI-Music |
| Humanize AI text | § Humanizer |
| Creative brainstorming | § Creative-Ideation |
| Pre-made ASCII art search | § ASCII-Art → Tool 7 (ascii.co.uk) |
| Design doc / DESIGN.md | § Design-MD |

## § ASCII-Art

**Use for:** Static ASCII art — text banners (pyfiglet), message art (cowsay), decorative borders (boxes), image-to-ASCII conversion, QR codes, weather art, pre-made art search.

**Full skill:** `creative/ascii-art/SKILL.md`

**Quick reference:**
```bash
# Text banner
python3 -m pyfiglet "HELLO" -f slant

# Cowsay
cowsay "Hello World"
cowsay -f dragon "Roar!"

# Image to ASCII
ascii-image-converter image.png -C -d 60,30

# Search pre-made art
curl -s 'https://ascii.co.uk/art/cat' | python3 -c "import re,sys; [print(p) for p in re.findall(r'<pre[^>]*>(.*?)</pre>', sys.stdin.read(), re.DOTALL) if len(re.sub(r'<[^>]+>','',p)) > 30]"
```

**Sub-sections absorbed:**
- `ascii-video` (full ASCII video production pipeline) — see § ASCII-Video

## § ASCII-Video

**Use for:** ASCII character video production — converts video/audio/images/generative input into colored ASCII character video output (MP4, GIF, image sequence). Covers: video-to-ASCII, audio-reactive music visualizers, generative ASCII art animations, hybrid video+audio reactive, text/lyrics overlays, real-time terminal rendering.

**Full skill:** `creative/ascii-video/SKILL.md`

**Quick reference:**
```bash
# Production pipeline: INPUT → ANALYZE → SCENE_FN → TONEMAP → SHADE → ENCODE
# Key rules:
# - Use tonemap() NOT canvas * N multipliers (clipping prevention)
# - Never stderr=subprocess.PIPE with ffmpeg (deadlock risk)
# - macOS: use font.getmetrics() not textbbox() for cell height
```

## § Baoyu-Comic

**Use for:** Knowledge comics with multiple art styles (manga, noir, watercolor, etc.). Subject-driven visual storytelling.

**Full skill:** `creative/baoyu-comic/SKILL.md`

## § Baoyu-Infographic

**Use for:** Professional infographics with 21 layout types. Subject-driven informational visual design.

**Full skill:** `creative/baoyu-infographic/SKILL.md`

## § Excalidraw

**Use for:** Hand-drawn style diagrams. Excalidraw JSON format for diagrams that look sketched by hand.

**Full skill:** `creative/excalidraw/SKILL.md`

## § Architecture-Diagram

**Use for:** Dark-themed SVG software architecture diagrams — system topology, data flow, component relationships.

**Full skill:** `creative/architecture-diagram/SKILL.md`

## § Pixel-Art

**Use for:** Retro pixel art from images with hardware-accurate palette conversion.

**Full skill:** `creative/pixel-art/SKILL.md`

## § Sketch

**Use for:** Throwaway HTML mockups — 2-3 design variants to compare. Fast prototyping.

**Full skill:** `creative/sketch/SKILL.md`

## § Claude-Design

**Use for:** One-off HTML artifacts (landing pages, decks, prototypes) via Claude.

**Full skill:** `creative/claude-design/SKILL.md`

## § P5JS

**Use for:** Interactive and generative visual sketches with p5.js.

**Full skill:** `creative/p5js/SKILL.md`

## § Manim-Video

**Use for:** Mathematical and technical animations via Manim (3Blue1Brown's animation engine).

**Full skill:** `creative/manim-video/SKILL.md`

## § TouchDesigner-MCP

**Use for:** Real-time generative visuals via TouchDesigner MCP bridge.

**Full skill:** `creative/touchdesigner-mcp/SKILL.md`

## § Songwriting-and-AI-Music

**Use for:** Songwriting craft + AI music generation (Suno-focused). Lyrics, melody concepts, genre guidance.

**Full skill:** `creative/songwriting-and-ai-music/SKILL.md`

## § Humanizer

**Use for:** Strip AI-isms from text — adds human voice, removes robotic patterns.

**Full skill:** `creative/humanizer/SKILL.md`

## § Creative-Ideation

**Use for:** Generate project ideas through creative constraints.

**Full skill:** `creative/creative-ideation/SKILL.md`

## § Design-MD

**Use for:** Author, validate, diff, and export DESIGN.md files (Google Slides format).

**Full skill:** `creative/design-md/SKILL.md`

## § Popular-Web-Designs

**Use for:** 54 production-quality design systems extracted from real popular websites.

**Full skill:** `creative/popular-web-designs/SKILL.md`

## § ComfyUI

**Use for:** Generate images, video, and audio with ComfyUI.

**Full skill:** `creative/comfyui/SKILL.md`

## § Pretext

**Use for:** Creative browser demos with @chenglou/p/react-motion effects.

**Full skill:** `creative/pretext/SKILL.md`

---

## Umbrella Notes

This is the top-level creative entry point. Each § is a full skill in the `creative/` subdirectory. The sub-skills are kept as separate files (not merged into this file) because each has substantial reference/template/script infrastructure.

The ASCII cluster (`ascii-art` + `ascii-video`) is the one place where the sub-skills have been retained as full separate files because both are large and have distinct toolchains, with ascii-video referencing ascii-art as a component.

**Archived siblings:**
- No siblings archived — all creative skills retained as full sub-skills under `creative/` directory.

**Clusters deliberately NOT merged here (standalone domains):**
- `dogfood/` — exploratory QA testing (not creative production)
- `media/` — audio/video media consumption (youtube, spotify, etc.)
- `social-media/` — posting/monitoring social platforms
