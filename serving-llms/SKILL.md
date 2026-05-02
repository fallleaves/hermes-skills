---
name: serving-llms
description: "LLM inference serving skills — vLLM (high-throughput production serving), llama.cpp (CPU/edge/Apple Silicon/GGUF), structured generation (Guidance, Outlines), and model surgery (OBLITERATUS). Use when deploying, running, or modifying LLM inference."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [LLM, Inference, Serving, vLLM, llama.cpp, GGUF, Structured-Generation, Guidance, Outlines, OBLITERATUS, Abliteration]
    umbrella: true
---

# LLM Inference & Serving — Skills

Unified entry point for LLM inference serving, covering production servers, edge deployment, structured output generation, and model modification.

## Quick Decision Tree

| Goal | § to use |
|------|----------|
| High-throughput production API (OpenAI-compatible) | § vLLM |
| CPU/edge/Apple Silicon/Metal inference, GGUF quantization | § llama-cpp |
| Guaranteed valid JSON/JSONSchema/Regex output | § Outlines (Pydantic) or § Guidance (regex/grammar) |
| Constrained generation with chat formats | § Guidance |
| Remove refusal/guardrails from open models | § OBLITERATUS |

---

## § vLLM — Production LLM Serving

**Use for:** High-throughput production LLM serving with OpenAI-compatible endpoints. PagedAttention + continuous batching. NVIDIA GPU-primary.

**Full skill:** `mlops/inference/vllm/SKILL.md`

**Quick reference:**
```bash
# Install
pip install vllm

# Serve (OpenAI-compatible)
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --port 8000

# With quantization
vllm serve TheBloke/Llama-2-70B-AWQ \
  --quantization awq \
  --tensor-parallel-size 4
```

**When to use vs llama.cpp:**
- vLLM: Production, multi-user, NVIDIA GPUs, maximum throughput
- llama.cpp: Edge, CPU, Apple Silicon, single-user, GGUF-native

## § llama-cpp — CPU/Edge/Apple Silicon Inference + GGUF

**Use for:** Running LLMs on CPU, Apple Silicon (Metal), AMD/Intel GPUs, or edge devices. GGUF format conversion and quantization (K-quants, imatrix).

**Full skill:** `mlops/inference/llama-cpp/SKILL.md`

**Quick reference:**
```bash
# Install
brew install llama.cpp  # macOS
# or: git clone https://github.com/ggml-org/llama.cpp && make

# Download pre-quantized
huggingface-cli download TheBloke/Llama-2-7B-Chat-GGUF \
  llama-2-7b-chat.Q4_K_M.gguf --local-dir models/

# Run
./llama-cli -m models/llama-2-7b-chat.Q4_K_M.gguf -ngl 99 -p "Hello"

# OpenAI-compatible server
./llama-server -m models/llama-2-7b-chat.Q4_K_M.gguf --port 8080 -ngl 35
```

**GGUF format:** GGUF (GPT-Generated Unified Format) is llama.cpp's native file format. See `llama-cpp` skill for full quantization reference (Q2_K through Q8_0, K-quants, imatrix calibration).

**Hardware acceleration:**
- Apple Silicon: `make GGML_METAL=1` → `-ngl 99` for full Metal offload
- NVIDIA CUDA: `make GGML_CUDA=1` → `-ngl 35`
- CPU: `-t 8` (match physical cores)

## § Outlines — Structured Generation (Pydantic/JSON Schema)

**Use for:** Guaranteed valid JSON, XML, or code generation using Pydantic models or JSON Schema. Zero-overhead grammar-based constrained generation. Works with Transformers, vLLM, llama.cpp.

**Full skill:** `mlops/inference/outlines/SKILL.md`

**Quick reference:**
```python
from pydantic import BaseModel
import outlines

model = outlines.models.transformers("microsoft/Phi-3-mini-4k-instruct")

class User(BaseModel):
    name: str
    age: int
    email: str

generator = outlines.generate.json(model, User)
user = generator("Extract: John Doe, 30, john@example.com")
```

**vs Guidance:** Outlines uses FSM-based token filtering (fastest, best for vLLM). Guidance uses grammar/regex constraints with broader chat-format support. Both guarantee valid output — choose based on your backend.

## § Guidance — Constrained Generation (Regex/Grammar/Chat)

**Use for:** Controlling LLM output with regex patterns, grammars, and chat-format templates. Token healing, multi-step ReAct agents, and structured generation. Microsoft Research.

**Full skill:** `mlops/inference/guidance/SKILL.md`

**Quick reference:**
```python
from guidance import models, gen, select

lm = models.Anthropic("claude-sonnet-4-5-20250514")

# Constrain to valid email
lm += "Email: " + gen("email", regex=r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

# Multiple choice
lm += "Sentiment: " + select(["positive", "negative", "neutral"], name="sentiment")
```

## § OBLITERATUS — Remove Refusal Behaviors from Models

**Use for:** Surgical removal of refusal/guardrail behaviors from open-weight LLMs using mechanistic interpretability (SVD, LEACE, SAE decomposition). Uncensor, abliterate, or analyze refusal mechanisms.

**Full skill:** `mlops/inference/obliteratus/SKILL.md`

**Quick reference:**
```bash
# Abliterate with recommended settings
obliteratus obliterate <model_name> --method advanced --output-dir ./abliterated-models

# With telemetry-driven recommendation
obliteratus recommend <model_name>
obliteratus obliterate <model_name> --method advanced --n-directions 4
```

**IMPORTANT:** OBLITERATUS is AGPL-3.0. Always invoke via CLI, never `import` as a library.

**Complementary skills:** Use vLLM to serve the abliterated model, or GGUF via llama-cpp to convert and run it.

---

## Sub-Skill Reference

| Sub-skill | Location | Status |
|-----------|----------|--------|
| vllm | `mlops/inference/vllm/SKILL.md` | § vLLM |
| llama-cpp | `mlops/inference/llama-cpp/SKILL.md` | § llama-cpp |
| gguf | Absorbed into llama-cpp | § llama-cpp §GGUF subsection |
| guidance | `mlops/inference/guidance/SKILL.md` | § Guidance |
| outlines | `mlops/inference/outlines/SKILL.md` | § Outlines |
| obliteratus | `mlops/inference/obliteratus/SKILL.md` | § OBLITERATUS |
