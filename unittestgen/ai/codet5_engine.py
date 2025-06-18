from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# Determine device (MPS if available, else CPU)
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")

# Load CodeT5 model and tokenizer (using codet5p-220m for better capacity)
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5p-220m")
model = AutoModelForSeq2SeqLM.from_pretrained(
    "Salesforce/codet5p-220m").to(device)


def generate_test_from_code(code_snippet, max_length=150, min_length=30):
    """
    Generate PyTest-style unit test for a Python code snippet.
    """
    # Enhanced prompt with specific instructions for assertions
    prompt = f"Generate a PyTest unit test with assertions for this Python function:\n```python\n{code_snippet}\n``` The test should include at least one assert statement to verify the function's output."

    # Tokenize input with attention mask
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True,
                       max_length=100, padding=True, return_attention_mask=True).to(device)
    attention_mask = inputs["attention_mask"]

    # Generate test using model with sampling
    outputs = model.generate(
        inputs["input_ids"],
        attention_mask=attention_mask,
        max_length=max_length,
        min_length=min_length,
        do_sample=True,  # Enable sampling to use temperature
        temperature=0.7,
        top_k=50,  # Limit to top 50 tokens for better focus
        top_p=0.95,  # Nucleus sampling for coherence
        num_return_sequences=1,  # Single output
    )

    # Decode and return result
    test_code = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    print(f"Generated test code: {test_code}")  # Debug output
    return test_code
