import os
from typing import Optional

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
import torch.nn as nn
from torch.quantization import quantize_dynamic


def load_lora_model(base_model: str, weights_dir: str, quantize: str = "none"):
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Optional quantized loading for inference
    model = None
    if quantize in ("bnb_int8", "bnb_int4") and torch.cuda.is_available():
        try:
            from transformers import BitsAndBytesConfig
            if quantize == "bnb_int8":
                bnb_config = BitsAndBytesConfig(load_in_8bit=True)
            else:
                bnb_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                )
            model = AutoModelForCausalLM.from_pretrained(
                base_model,
                quantization_config=bnb_config,
                device_map="auto",
            )
        except Exception:
            model = AutoModelForCausalLM.from_pretrained(base_model)
    else:
        model = AutoModelForCausalLM.from_pretrained(base_model)
    model = PeftModel.from_pretrained(model, weights_dir)
    model.eval()

    # Optional CPU dynamic int8 quantization after merging LoRA
    if quantize == "cpu_int8_dynamic":
        try:
            # Merge LoRA weights into base for better quantization effect
            if hasattr(model, "merge_and_unload"):
                model = model.merge_and_unload()
            model = model.to("cpu")
            model.eval()
            model = quantize_dynamic(model, {nn.Linear}, dtype=torch.qint8)
        except Exception:
            # If anything fails, keep the original FP32 model
            pass
    return tokenizer, model


def generate_text(
    tokenizer,
    model,
    prompt: str,
    max_length: int = 128,
    do_sample: bool = False,
    temperature: float = 0.7,
    top_p: float = 0.9,
    repetition_penalty: float = 1.05,
    num_beams: int = 1,
):
    # Use same QA template as training
    # Match training template for Mistral Instruct
    templated = f"<s>[INST] {prompt} [/INST] "
    inputs = tokenizer(templated, return_tensors="pt")
    # Move inputs to model device
    try:
        device = next(model.parameters()).device
    except StopIteration:
        device = torch.device("cpu")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    gen_ids = model.generate(
        **inputs,
        max_new_tokens=max_length,
        min_new_tokens=1,
        do_sample=do_sample,
        temperature=temperature,
        top_p=top_p,
        repetition_penalty=repetition_penalty,
        num_beams=num_beams,
        no_repeat_ngram_size=3,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.eos_token_id,
        use_cache=True,
    )
    text = tokenizer.decode(gen_ids[0], skip_special_tokens=True)
    # Strip the template prefix to return only the answer part when possible
    if "Answer:" in text:
        return text.split("Answer:", 1)[1].strip()
    return text


def run_cli():
    import argparse
    parser = argparse.ArgumentParser(description="LoRA inference CLI")
    parser.add_argument("--base_model", default="EleutherAI/gpt-neo-125M")
    parser.add_argument("--weights_dir", default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fine_tuning", "gptneo_lora_weights"))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max_length", type=int, default=128)
    parser.add_argument("--quantize", type=str, default="none", choices=["none", "cpu_int8_dynamic", "bnb_int8", "bnb_int4"], help="Quantization: cpu_int8_dynamic (CPU), or bnb_* (CUDA only)")
    # decoding controls
    parser.add_argument("--do_sample", action="store_true", help="Enable sampling (default off)")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--repetition_penalty", type=float, default=1.05)
    parser.add_argument("--num_beams", type=int, default=1)
    args = parser.parse_args()

    tokenizer, model = load_lora_model(args.base_model, args.weights_dir, args.quantize)
    print(
        generate_text(
            tokenizer,
            model,
            args.prompt,
            args.max_length,
            do_sample=args.do_sample,
            temperature=args.temperature,
            top_p=args.top_p,
            repetition_penalty=args.repetition_penalty,
            num_beams=args.num_beams,
        )
    )


if __name__ == "__main__":
    run_cli()


