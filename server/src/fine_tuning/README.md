# LoRA Fine-tuning and Inference Guide

This module provides LoRA fine-tuning and inference for a base model (default `EleutherAI/gpt-neo-125M`) on CPU.

- Code: `server/src/fine_tuning/`
- Data & outputs: recommended `server/data/fine_tuning/`
- If your data is under `server/data/fine_tuning/` (with hyphen), set `--data_dir` accordingly when running.

## Train
Run from the `server` directory:
```bash
python -m src.fine_tuning.train \
  --data_dir ./data/fine_tuning \
  --output_dir ./data/fine_tuning \
  --model_name EleutherAI/gpt-neo-125M \
  --max_length 128 \
  --batch_size 1 \
  --grad_accum_steps 4 \
  --learning_rate 1e-4 \
  --num_train_epochs 3 \
  --save_steps 50 \
  --logging_steps 1 \
  --lora_r 4 \
  --lora_alpha 16 \
  --lora_dropout 0.05
```
If your data is under `server/data/fine_tuning/` (hyphen):
```bash
python -m src.fine_tuning.train --data_dir ./data/fine_tuning --output_dir ./data/fine_tuning
```

### Key arguments
- `--model_name`: base model (default `EleutherAI/gpt-neo-125M`)
- `--data_dir`: data directory containing `train_data.json` with keys `prompt`, `completion`
- `--output_dir`: output directory (will create `gptneo_lora/` and `gptneo_lora_weights/`)
- `--max_length`: max sequence length (default 128)
- `--batch_size`: per-device batch size (CPU recommended 1)
- `--grad_accum_steps`: gradient accumulation steps (helps simulate larger batch on CPU)
- `--learning_rate`: default 1e-4
- `--num_train_epochs`: default 3
- `--save_steps`: default 50
- `--logging_steps`: default 1
- `--lora_r` / `--lora_alpha` / `--lora_dropout`: LoRA configuration

## Inference
Run from the `server` directory:
```bash
python -m src.fine_tuning.infer \
  --base_model EleutherAI/gpt-neo-125M \
  --weights_dir ./data/fine_tuning/gptneo_lora_weights \
  --prompt "Write a Python function to compute factorial" \
  --max_length 128
```
Adjust `--weights_dir` if your weights are stored elsewhere.

## Data format
`train_data.json` is a JSON array. Each item must include:
```json
{
  "prompt": "instruction or context",
  "completion": "expected output"
}
```

## Notes
- If GPT‑Neo has no `pad_token`, the script will use `eos_token` as padding.
- LoRA saves only delta weights (small size). Inference requires base model + LoRA weights.
- On CPU, training time depends on dataset size and epochs. Reduce `num_train_epochs` or `max_length` to speed up.
