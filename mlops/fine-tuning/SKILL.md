---
name: fine-tuning
description: Unified fine-tuning skill for LLMs — covers axolotl, unsloth, GRPO/RL training, PEFT (LoRA/QLoRA), PyTorch FSDP, and TRL (SFT/DPO/PPO). Use when fine-tuning large models, optimizing training pipelines, or implementing RLHF/DPO workflows.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [Fine-Tuning, LLM, LoRA, QLoRA, RLHF, DPO, GRPO, Axolotl, Unsloth, TRL, FSDP, PEFT, Training]
    category: mlops/training
---

# Fine-Tuning LLM Skill

Comprehensive guide for fine-tuning large language models. This is an **umbrella skill** that consolidates six specialized fine-tuning approaches. Choose the right approach for your hardware and goal.

## Six Fine-Tuning Approaches

| Approach | Best For | Hardware | Key Benefit |
|---------|----------|----------|-------------|
| **Axolotl** (§axolotl) | General fine-tuning, 100+ model support | Multi-GPU, H100/A100 | YAML-driven, battle-tested |
| **Unsloth** (§unsloth) | Fast iteration, consumer GPUs | Mac M-series, RTX 3090/4090 | 2-5x faster, 50-80% less memory |
| **GRPO/RL Training** (§grpo) | Structured outputs, reasoning | Any GPU with 8GB+ | RL-based format/correctness enforcement |
| **PEFT (LoRA/QLoRA)** §peft | Memory-constrained fine-tuning | Single GPU, 6-24GB VRAM | <1% params, minimal accuracy loss |
| **PyTorch FSDP** §fsdp | Distributed large-model training | Multi-node H100/A100 | Full parameter sharding |
| **TRL (SFT/DPO/PPO)** §trl | RLHF pipelines, preference alignment | Any GPU | End-to-end RLHF, DPO, ORPO |

## §axolotl — Axolotl

Expert guidance for fine-tuning LLMs with Axolotl — YAML configs, 100+ models, LoRA/QLoRA, DPO/KTO/ORPO/GRPO, multimodal support.

**Skill:** `axolotl`
**Path:** `mlops/training/axolotl/SKILL.md`

### Quick Start

```bash
# Install
pip install axolotl

# Key config pattern for FSDP
fsdp_version: 2
fsdp_config:
  offload_params: true
  state_dict_type: FULL_STATE_DICT
  transformer_layer_cls_to_wrap: LlamaDecoderLayer
  reshard_after_forward: true

# Context parallel (divisor of total GPUs)
context_parallel_size: 4  # 8 GPUs → 2 batches per step

# Save compressed for vLLM compatibility
save_compressed: true
```

### Common Patterns

```yaml
# Example: Llama 3.1 8B QLoRA
base_model: meta-llama/Llama-3.1-8B
model_type: LlamaForCausalLM
load_in_4bit: true
bf16: true
gradient_accumulation_steps: 4
quant_method: bnb

# NCCL test for networking validation
./build/all_reduce_perf -b 8 -e 128M -f 2 -g 3
```

## §unsloth — Unsloth

Expert guidance for fast fine-tuning with Unsloth — 2-5x faster training, 50-80% less memory, LoRA/QLoRA optimization.

**Skill:** `unsloth`
**Path:** `mlops/training/unsloth/SKILL.md`

### Quick Start

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="google/gemma-3-1b-it",
    max_seq_length=1024,
    load_in_4bit=True,
    fast_inference=True,
    max_lora_rank=32,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"],
    lora_alpha=32,
    use_gradient_checkpointing="unsloth",
)
```

## §grpo — GRPO/RL Training with TRL

Expert guidance for Group Relative Policy Optimization using the TRL library. Use for structured output enforcement, verifiable task training (math, code), and reward-based fine-tuning.

**Skill:** `grpo-rl-training`
**Path:** `mlops/training/grpo-rl-training/SKILL.md`

### Key Insight: Loss Increases — That's Normal

GRPO loss starts near 0 and **increases** during training. This is correct — loss measures KL divergence from the initial policy. **Monitor reward metrics, not loss.**

### Healthy Training Pattern

```
Step   Reward    Reward_Std   KL
100    0.5       0.3          0.02
300    1.2       0.2          0.08  ← Good progression
400    1.5       0.15         0.12
```

### Reward Function Design

Use 3-5 reward functions compositionally:

```python
def format_reward(completions, **kwargs):
    """Award XML-like structured format."""
    import re
    pattern = r'<reasoning>.*?</reasoning>\s*<answer>.*?</answer>'
    responses = [comp[0]['content'] for comp in completions]
    return [1.0 if re.search(pattern, r, re.DOTALL) else 0.0 for r in responses]

def correctness_reward(prompts, completions, answer, **kwargs):
    """Reward correct answers."""
    responses = [comp[0]['content'] for comp in completions]
    extracted = [extract_final_answer(r) for r in responses]
    return [2.0 if ans == gt else 0.0 for ans, gt in zip(extracted, answer)]
```

### Training Config

```python
from trl import GRPOConfig

training_args = GRPOConfig(
    learning_rate=5e-6,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=4,
    num_generations=8,           # Group size: 8-16
    max_prompt_length=256,
    max_completion_length=512,
    bf16=True,
    use_vllm=True,               # Fast generation
    report_to="wandb",
)
```

## §peft — PEFT (LoRA / QLoRA)

Parameter-efficient fine-tuning for LLMs using LoRA, QLoRA, and 25+ methods. Use when fine-tuning 7B-70B models with limited GPU memory.

**Skill:** `peft-fine-tuning`
**Path:** `mlops/training/peft/SKILL.md`

### Core LoRA Pattern

```python
from peft import LoraConfig, get_peft_model

peft_config = LoraConfig(
    r=16,                         # Rank
    lora_alpha=32,                # Scaling factor (typically 2*r)
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                   "gate_proj", "up_proj", "down_proj"],
    task_type="CAUSAL_LM",
    lora_dropout=0.05,
)

model = get_peft_model(base_model, peft_config)
model.print_trainable_parameters()
# trainable params: 4,194,304 || all params: 6,738,415,616 || trainable%: 0.062
```

## §fsdp — PyTorch FSDP

Expert guidance for Fully Sharded Data Parallel training with PyTorch FSDP — parameter sharding, mixed precision, CPU offloading, FSDP2.

**Skill:** `pytorch-fsdp`
**Path:** `mlops/training/pytorch-fsdp/SKILL.md`

### FSDP2 Config Pattern

```yaml
fsdp_version: 2
fsdp_config:
  offload_params: true           # CPU offload for large models
  state_dict_type: FULL_STATE_DICT
  auto_wrap_policy: TRANSFORMER_BASED_WRAP
  transformer_layer_cls_to_wrap: LlamaDecoderLayer
  reshard_after_forward: true
```

## §trl — TRL (SFT / DPO / PPO)

Fine-tune LLMs using reinforcement learning with TRL — SFT for instruction tuning, DPO for preference alignment, PPO/GRPO for reward optimization.

**Skill:** `trl-fine-tuning`
**Path:** `mlops/training/trl-fine-tuning/SKILL.md`

### DPO Training Pattern

```python
from trl import DPOConfig, DPOTrainer

training_args = DPOConfig(
    learning_rate=1e-5,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    num_train_epochs=1,
    bf16=True,
    report_to="wandb",
)

trainer = DPOTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    tokenizer=tokenizer,
)
trainer.train()
```

### SFT Pattern

```python
from trl import SFTTrainer, SFTConfig

training_args = SFTConfig(
    dataset_text_field="text",
    max_seq_length=4096,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=2,
    bf16=True,
    report_to="wandb",
)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    processing_class=tokenizer,
)
trainer.train()
```

## Decision Guide

**Start here:**

| Scenario | Recommendation |
|----------|----------------|
| Fast prototyping on Mac/consumer GPU | Unsloth |
| Large-scale multi-GPU training | Axolotl or FSDP |
| Need structured outputs / reasoning | GRPO |
| Single GPU with limited VRAM (6-24GB) | PEFT (QLoRA) |
| Full RLHF pipeline (SFT + DPO + PPO) | TRL |
| Don't know where to start | Unsloth (fastest iteration) |

## Sub-Skill Reference

| Sub-skill | Location |
|-----------|----------|
| axolotl | `mlops/training/axolotl/SKILL.md` |
| unsloth | `mlops/training/unsloth/SKILL.md` |
| grpo-rl-training | `mlops/training/grpo-rl-training/SKILL.md` |
| peft-fine-tuning | `mlops/training/peft/SKILL.md` |
| pytorch-fsdp | `mlops/training/pytorch-fsdp/SKILL.md` |
| trl-fine-tuning | `mlops/training/trl-fine-tuning/SKILL.md` |
