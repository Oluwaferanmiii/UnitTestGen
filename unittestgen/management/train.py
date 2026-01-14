# unittestgen/management/train.py

import os
import torch
from datasets import load_dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    DataCollatorForSeq2Seq,
    Trainer,
    TrainingArguments,
)
from dotenv import load_dotenv

load_dotenv()

# ---------- Device ----------
device = torch.device(
    "cuda" if torch.cuda.is_available()
    else "mps" if torch.backends.mps.is_available()
    else "cpu"
)
print(f"Using device: {device}")

# ---------- Paths / Model names from env ----------
DATASET_PATH = os.environ.get("DATASET_PATH", "dataset.cleaned.jsonl")
BASE_MODEL = os.environ.get("MODEL_PATH", "Salesforce/codet5p-220m")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "../results")
LOGGING_DIR = os.environ.get("LOGGING_DIR", "./logs")
SAVE_PATH = os.environ.get("SAVE_PATH", "./results/fine_tuned_codet5p_updated")

# ---------- Load dataset and make an eval split ----------
raw = load_dataset("json", data_files=DATASET_PATH)["train"]
split = raw.train_test_split(test_size=0.1, seed=42)
train_ds, eval_ds = split["train"], split["test"]

# ---------- Tokenizer / Model ----------
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModelForSeq2SeqLM.from_pretrained(BASE_MODEL).to(device)

# Ensure model embeddings match tokenizer vocab (prevents missing-keys weirdness)
model.resize_token_embeddings(len(tokenizer))
model.config.tie_word_embeddings = True
model.tie_weights()

# ---------- Preprocessing ----------
MAX_SRC_LEN = 512
MAX_TGT_LEN = 256


def build_prompt(func: str) -> str:
    """Builds the natural-language prompt for the model."""
    return (
        "Given this Python function:\n```python\n"
        f"{func}\n"
        "```, write a PyTest unit test function in Python with at least one assert "
        "statement to verify its behavior."
    )


def preprocess(batch, tokenizer_name: str):
    """Pure function suitable for hashing by Datasets."""
    tok = AutoTokenizer.from_pretrained(tokenizer_name)
    inputs = [build_prompt(func) for func in batch["input"]]
    model_inputs = tok(inputs, max_length=MAX_SRC_LEN, truncation=True)
    labels = tok(text_target=batch["output"],
                 max_length=MAX_TGT_LEN, truncation=True)
    model_inputs["labels"] = labels["input_ids"]
    return model_inputs


# Call map with a serializable function (passing model name as primitive)
train_ds = train_ds.map(
    preprocess,
    fn_kwargs={"tokenizer_name": BASE_MODEL},
    batched=True,
    remove_columns=train_ds.column_names,
    new_fingerprint="preprocess_v1_train",
)

eval_ds = eval_ds.map(
    preprocess,
    fn_kwargs={"tokenizer_name": BASE_MODEL},
    batched=True,
    remove_columns=eval_ds.column_names,
    new_fingerprint="preprocess_v1_eval",
)

# ---------- Data Collator ----------
data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)

# ---------- Training args ----------
args = TrainingArguments(
    output_dir=SAVE_PATH,
    num_train_epochs=6,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,   # effective batch size = 16
    learning_rate=5e-5,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    weight_decay=0.01,
    label_smoothing_factor=0.1,

    # Logging / eval / saving
    logging_dir=LOGGING_DIR,
    logging_steps=50,
    evaluation_strategy="epoch",  # <-- fixed name
    save_strategy="epoch",
    save_total_limit=3,
    load_best_model_at_end=True,
    metric_for_best_model="eval_loss",
    greater_is_better=False,

    # Misc
    push_to_hub=False,
    report_to=["tensorboard"],
    dataloader_pin_memory=False,
    fp16=torch.cuda.is_available(),
)

# ---------- Trainer ----------
trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_ds,
    eval_dataset=eval_ds,
    tokenizer=tokenizer,
    data_collator=data_collator,
)

# ---------- Train ----------
trainer.train()

# ---------- Save ----------
model.tie_weights()
trainer.save_model(SAVE_PATH)
tokenizer.save_pretrained(SAVE_PATH)
print(f"Model + tokenizer saved to: {SAVE_PATH}")
