from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os
import re

# Determine device (CUDA for Lightning AI, MPS locally, CPU fallback)
device = torch.device("cuda" if torch.cuda.is_available(
) else "mps" if torch.backends.mps.is_available() else "cpu")
print(f"Using device: {device}")

# Load fine-tuned model and tokenizer with environment variable
MODEL_DIR = os.environ.get(
    "MODEL_PATH", "/Users/oluwaferanmiii/Python/Thesis/fine_tuned_codet5p")
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
    prompt = f"Given this Python function:\n```python\n{code_snippet}\n```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior."
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=128,
        padding=True,
        return_attention_mask=True
    ).to(device)
    attention_mask = inputs["attention_mask"]
    outputs = model.generate(
        inputs["input_ids"],
        attention_mask=attention_mask,
        max_length=max_length,
        min_length=min_length,
        num_beams=4,
        early_stopping=True,
        no_repeat_ngram_size=3,
        temperature=0.6,
        top_k=50,
        do_sample=True,
        num_return_sequences=1,
    )
    test_code = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Remove leading/trailing whitespace and fix basic syntax
    test_code = test_code.strip().replace("  ", " ").replace("\n\n", "\n")
    function_match = re.search(r"def (\w+)\(", code_snippet)
    if function_match:
        function_name = function_match.group(1).lower()
        # Standardize test function name
        test_code = re.sub(r'def test_\w+\(',
                           f'def test_{function_name}(', test_code, 1)
        # Replace function calls with correct case
        test_code = re.sub(
            r'\b' + re.escape(function_name.capitalize()) + r'\b', function_name, test_code)
        test_code = re.sub(
            r'\b' + re.escape(function_name.upper()) + r'\b', function_name, test_code)
        test_code = re.sub(r'\b' + re.escape(function_name) +
                           r'(?=\s*\()', function_name, test_code)
        # Handle dot notation and invalid separators
        # Remove dots (e.g., get.abs -> get_abs)
        test_code = re.sub(r'\.(\w+)', r'\1', test_code)
        # Replace hyphens with underscores
        test_code = test_code.replace("-", "_")
        # Ensure proper assert syntax
        test_code = re.sub(r'assert\s+(\w+)', r'assert \1',
                           test_code)  # Normalize assert spacing
        # Fix assert format
        test_code = re.sub(
            r'assert\s+([^\s=]+)\s*==', r'assert \1 ==', test_code)
    return test_code


if __name__ == "__main__":
    generated_test = generate_test_from_code(
        "def subtract(a, b): return a - b")
    print(generated_test)
