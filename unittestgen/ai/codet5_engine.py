from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# Determine device (MPS if available, else CPU)
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

# Load CodeT5 model and tokenizer (using codet5p-220m)
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-large")
model = AutoModelForSeq2SeqLM.from_pretrained(
    "Salesforce/codet5-large").to(device)


def generate_test_from_code(code_snippet, max_length=120, min_length=30):
    """
    Generate PyTest-style unit test for a Python code snippet.
    """
    # Reframed prompt to encourage test generation
    prompt = f"Given this Python function:\n```python\n{code_snippet}\n```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior."

    # Tokenize input with attention mask
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True,
                       max_length=80, padding=True, return_attention_mask=True).to(device)
    attention_mask = inputs["attention_mask"]

    # Generate test using model with adjusted parameters
    outputs = model.generate(
        inputs["input_ids"],
        attention_mask=attention_mask,
        max_length=max_length,
        min_length=min_length,
        num_beams=4,  # Increased beams for better exploration
        early_stopping=True,
        no_repeat_ngram_size=2,
        temperature=0.6,  # Slight randomness to avoid strict repetition
        do_sample=False,  # Stick to beam search for now
    )

    # Decode and return result
    test_code = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    print(f"Generated test code: {test_code}")  # Debug output
    return test_code
