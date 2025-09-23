import os
from typing import Optional

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model

from .data import load_finetune_dataset, build_tokenize_fn


DEFAULT_MODEL = "EleutherAI/gpt-neo-125M"
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fine_tuning")
OUTPUT_DIR = DATA_DIR  # Save weights to server/data/fine_tuning


def finetune_lora(
    model_name: str = DEFAULT_MODEL,
    data_dir: str = DATA_DIR,
    output_dir: str = OUTPUT_DIR,
    max_length: int = 64,  # Reduce sequence length
    learning_rate: float = 5e-4,  # Increase learning rate
    batch_size: int = 1,
    grad_accum_steps: int = 8,  # Increase gradient accumulation
    num_train_epochs: int = 5,  # Increase training epochs
    save_steps: int = 25,  # Save more frequently
    logging_steps: int = 1,
    lora_r: int = 8,  # Increase LoRA rank
    lora_alpha: int = 32,  # Increase alpha
    lora_dropout: float = 0.1,  # Increase dropout
) -> str:
    """Run LoRA fine-tuning and return weights output directory."""
    os.makedirs(output_dir, exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    # GPT-Neo may need pad_token; use eos_token as pad if missing
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_name)

    # Dataset
    train_ds = load_finetune_dataset(data_dir)
    tokenize_fn = build_tokenize_fn(tokenizer, max_length=max_length)
    tokenized_train = train_ds.map(tokenize_fn, batched=True, remove_columns=train_ds.column_names)

    # LoRA config
    # GPT-Neo does not have "query_key_value"; use proj names instead
    lora_config = LoraConfig(
        r=lora_r,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "out_proj"],
        lora_dropout=lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=os.path.join(output_dir, "gptneo_lora"),
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum_steps,
        learning_rate=learning_rate,
        num_train_epochs=num_train_epochs,
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=2,
        fp16=False,
        report_to=[]
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_train,
    )

    trainer.train()

    weights_dir = os.path.join(output_dir, "gptneo_lora_weights")
    model.save_pretrained(weights_dir)
    return weights_dir


def run_cli():
    """CLI entry point: python -m src.fine_tuning.train --help"""
    import argparse

    parser = argparse.ArgumentParser(description="LoRA Fine-tuning CLI")
    parser.add_argument("--model_name", default=DEFAULT_MODEL)
    parser.add_argument("--data_dir", default=DATA_DIR)
    parser.add_argument("--output_dir", default=OUTPUT_DIR)
    parser.add_argument("--max_length", type=int, default=128)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--grad_accum_steps", type=int, default=4)
    parser.add_argument("--num_train_epochs", type=int, default=3)
    parser.add_argument("--save_steps", type=int, default=50)
    parser.add_argument("--logging_steps", type=int, default=1)
    parser.add_argument("--lora_r", type=int, default=4)
    parser.add_argument("--lora_alpha", type=int, default=16)
    parser.add_argument("--lora_dropout", type=float, default=0.05)

    args = parser.parse_args()

    weights_dir = finetune_lora(
        model_name=args.model_name,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        max_length=args.max_length,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        grad_accum_steps=args.grad_accum_steps,
        num_train_epochs=args.num_train_epochs,
        save_steps=args.save_steps,
        logging_steps=args.logging_steps,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
    )

    print(f"LoRA weights saved to: {weights_dir}")


if __name__ == "__main__":
    run_cli()


