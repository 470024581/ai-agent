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
    """Tokenize with QA template and label masking so only the answer is supervised.

    Format:
    Question: {prompt}\nAnswer: {completion}
    """
    def _fn(examples: Dict[str, Any]):
        prompts = examples.get("prompt")
        completions = examples.get("completion")
        if prompts is None or completions is None:
            raise ValueError("Samples must contain 'prompt' and 'completion' fields")

        # Use chat-style template to align with instruction-tuned models like Mistral Instruct
        # <s>[INST] {prompt} [/INST] {completion}</s>
        questions = [f"<s>[INST] {p} [/INST] " for p in prompts]
        full_texts = [q + c + "</s>" for q, c in zip(questions, completions)]

        tokenized = tokenizer(
            full_texts,
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )

        # Build labels: mask question part (set to -100), supervise only the answer tokens
        labels = []
        for q_text, input_ids in zip(questions, tokenized["input_ids"]):
            q_ids = tokenizer(q_text, add_special_tokens=False)["input_ids"]
            q_len = len(q_ids)
            # Copy and mask
            lbl = input_ids.copy()
            for i in range(min(q_len, len(lbl))):
                lbl[i] = -100
            # Also mask padding tokens
            pad_id = tokenizer.pad_token_id
            lbl = [(-100 if tok_id == pad_id else tok_id) for tok_id in lbl]
            labels.append(lbl)

        tokenized["labels"] = labels
        return tokenized

    return _fn


