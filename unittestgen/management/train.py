import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, Trainer, TrainingArguments
from datasets import load_dataset
import os

# Set device explicitly
device = torch.device("cuda" if torch.cuda.is_available(
) else "mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {device}")

# Load dataset
dataset_path = os.environ.get("DATASET_PATH", "dataset.jsonl")
dataset = load_dataset("json", data_files=dataset_path)["train"]

# Load tokenizer and model
model_path = os.environ.get("MODEL_PATH", "Salesforce/codet5p-220m")
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(device)

# Tokenize dataset


def tokenize_function(examples):
    inputs = [
        f"Given this Python function:\n```python\n{func}\n```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior."
        for func in examples["input"]
    ]
    targets = [test for test in examples["output"]]
    model_inputs = tokenizer(
        inputs,
        padding="max_length",
        max_length=256,
        truncation=True,
        return_tensors="pt"
    )
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(
            targets,
            padding="max_length",
            max_length=128,
            truncation=True,
            return_tensors="pt"
        )["input_ids"]
    model_inputs["labels"] = labels
    return model_inputs


tokenized_dataset = dataset.map(tokenize_function, batched=True)

# Define training arguments
training_args = TrainingArguments(
    output_dir=os.environ.get("OUTPUT_DIR", "../results"),
    num_train_epochs=20,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,  # Effective batch size of 16
    warmup_steps=300,
    weight_decay=0.01,
    logging_dir=os.environ.get("LOGGING_DIR", "./logs"),
    logging_steps=1,
    save_steps=10,
    save_total_limit=3,
    push_to_hub=False,
    report_to="tensorboard",
    fp16=torch.cuda.is_available(),  # Use fp16 only for CUDA (Lightning AI)
)

# Initialize Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
)

# Train the model
trainer.train()

# Save the fine-tuned model
save_path = os.environ.get("SAVE_PATH", "./results/fine_tuned_codet5p_updated")
model.save_pretrained(save_path)
tokenizer.save_pretrained(save_path)
