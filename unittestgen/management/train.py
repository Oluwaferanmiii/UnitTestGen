import torch    # pylint: disable=unused-import
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, Trainer, TrainingArguments
from datasets import load_dataset

# Load dataset
dataset = load_dataset("json", data_files="dataset.jsonl")["train"]

# Load tokenizer and model
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5p-220m")
model = AutoModelForSeq2SeqLM.from_pretrained("Salesforce/codet5p-220m")

# Tokenize dataset


def tokenize_function(examples):
    inputs = [
        f"Given this Python function:\n```python\n{func}\n```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior." for func in examples["input"]]
    targets = [test for test in examples["output"]]
    model_inputs = tokenizer(inputs, padding="max_length",
                             max_length=128, truncation=True, return_tensors="pt")
    with tokenizer.as_target_tokenizer():
        labels = tokenizer(targets, padding="max_length", max_length=128,
                           truncation=True, return_tensors="pt")["input_ids"]
    model_inputs["labels"] = labels
    return model_inputs


tokenized_dataset = dataset.map(tokenize_function, batched=True)

# Define training arguments
training_args = TrainingArguments(
    output_dir="../results",
    num_train_epochs=20,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,  # Effective batch size of 16
    warmup_steps=300,
    weight_decay=0.01,
    logging_dir="/Users/oluwaferanmiii/Python/Thesis/logs",
    logging_steps=1,
    save_steps=10,
    save_total_limit=3,
    push_to_hub=False,
    report_to="tensorboard",
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
model.save_pretrained("./fine_tuned_codet5p")
tokenizer.save_pretrained("./fine_tuned_codet5p")
