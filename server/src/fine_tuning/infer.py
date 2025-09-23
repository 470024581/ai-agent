import os
from typing import Optional

from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel


def load_lora_model(base_model: str, weights_dir: str):
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model)
    model = PeftModel.from_pretrained(model, weights_dir)
    return tokenizer, model


def generate_text(tokenizer, model, prompt: str, max_length: int = 128) -> str:
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_length=max_length)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def run_cli():
    import argparse
    parser = argparse.ArgumentParser(description="LoRA inference CLI")
    parser.add_argument("--base_model", default="EleutherAI/gpt-neo-125M")
    parser.add_argument("--weights_dir", default=os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fine_tuning", "gptneo_lora_weights"))
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--max_length", type=int, default=128)
    args = parser.parse_args()

    tokenizer, model = load_lora_model(args.base_model, args.weights_dir)
    print(generate_text(tokenizer, model, args.prompt, args.max_length))


if __name__ == "__main__":
    run_cli()


