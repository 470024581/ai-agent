import os
from typing import Dict, Any

from datasets import load_dataset


def load_finetune_dataset(data_dir: str) -> Any:
    """Load fine-tuning dataset (JSON). Expect keys: prompt, completion.

    Example path:
    server/data/fine_tuning/train_data.json
    """
    train_path = os.path.join(data_dir, "train_data.json")
    if not os.path.exists(train_path):
        raise FileNotFoundError(f"Training data not found: {train_path}")

    dataset_dict = load_dataset("json", data_files={"train": train_path})
    return dataset_dict["train"]


def build_tokenize_fn(tokenizer, max_length: int = 128):
    """Build tokenize function that concatenates prompt + completion."""
    def _fn(examples: Dict[str, Any]):
        prompts = examples.get("prompt")
        completions = examples.get("completion")
        if prompts is None or completions is None:
            raise ValueError("Samples must contain 'prompt' and 'completion' fields")
        # Concatenate prompt and completion into a single sequence for causal LM learning
        texts = [f"{p}\n{c}" for p, c in zip(prompts, completions)]
        tokenized = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )
        # Provide labels so Trainer can compute loss (learn to predict next tokens)
        # labels == input_ids (standard causal LM training)
        tokenized["labels"] = list(tokenized["input_ids"])  # copy list of lists
        return tokenized

    return _fn


