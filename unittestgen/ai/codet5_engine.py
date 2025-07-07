from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os

# Determine device (MPS if available, else CPU)
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

# Load fine-tuned model and tokenizer with absolute path
MODEL_DIR = "/Users/oluwaferanmiii/Python/Thesis/fine_tuned_codet5p"
print(f"Loading model from: {MODEL_DIR}")
if not os.path.exists(MODEL_DIR):
    raise FileNotFoundError(f"Directory {MODEL_DIR} does not exist!")
tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR).to(device)
print(f"Model loaded with config: {model.config}")


def generate_test_from_code(code_snippet, max_length=150, min_length=30):
    """
    Generate PyTest-style unit test for a Python code snippet.
    """
    # Strict prompt enforcing Python PyTest syntax
    prompt = f"Given this Python function:\n```python\n{code_snippet}\n```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior."

    # Tokenize input with attention mask
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True,
                       max_length=128, padding=True, return_attention_mask=True).to(device)
    attention_mask = inputs["attention_mask"]

    # Generate test using model with sampling
    outputs = model.generate(
        inputs["input_ids"],
        attention_mask=attention_mask,
        max_length=max_length,
        min_length=min_length,
        num_beams=4,
        early_stopping=True,
        no_repeat_ngram_size=3,
        temperature=0.7,
        num_return_sequences=1,
    )

    # Decode and return result
    test_code = tokenizer.decode(outputs[0], skip_special_tokens=True)
    return test_code


if __name__ == "__main__":
    test_code = generate_test_from_code("def add(a, b): return a + b")
    print(test_code)
