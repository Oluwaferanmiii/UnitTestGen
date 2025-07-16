from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
import os
import re

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
        temperature=0.6,  # Lowered from 0.7 to reduce variability
        top_k=50,        # Add top-k sampling to constrain outputs
        do_sample=True,
        num_return_sequences=1,
    )

    # Decode and return result
    test_code = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # Ensure proper spacing in assertions for any function name
    test_code = test_code.replace(
        "assert", "assert ")  # Add space after assert
    # Extract the function name from the input code_snippet
    function_match = re.search(r"def (\w+)\(", code_snippet)
    if function_match:
        function_name = function_match.group(
            1).lower()  # Force lowercase for consistency
        # Fix cases where the function name might be concatenated or capitalized
        test_code = test_code.replace(
            f"assert{function_name.capitalize()}", f"assert {function_name}")
        test_code = test_code.replace(
            f"assert{function_name}", f"assert {function_name}")
        # Replace any uppercase version of the function with lowercase
        test_code = re.sub(r'\b' + function_name.capitalize() +
                           r'\b', function_name, test_code)
    return test_code


if __name__ == "__main__":
    generated_test = generate_test_from_code(
        "def multiply(a, b): return a * b")
    print(generated_test)
