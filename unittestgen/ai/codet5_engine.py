from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# Determine device (MPS if available, else CPU)
device = torch.device(
    "mps" if torch.backends.mps.is_available() else "cpu")

# Load CodeT5 model and tokenizer (only once)
tokenizer = AutoTokenizer.from_pretrained("Salesforce/codet5-base")
model = AutoModelForSeq2SeqLM.from_pretrained(
    "Salesforce/codet5-base").to(device)


def generate_test_from_code(code_snippet, max_length=512, min_length=50):
    """
        Generate PyTest-style unit test for a Python code snippet.
        """
    # Enhanced prompt with an example
    prompt = f"""Generate a PyTest unit test for the following Python function. The test should include assertions to verify the function's behavior, including edge cases where applicable.

   Example:
   For the function:
   ```python
   def multiply(x, y): return x * y
   ```
   Generated test:
   ```python
   def test_multiply():
       assert multiply(2, 3) == 6
       assert multiply(-1, 5) == -5
       assert multiply(0, 10) == 0
   ```

   Function to test:
   ```python
   {code_snippet}
   ```
   """

    # Tokenize input
    inputs = tokenizer(prompt, return_tensors="pt",
                       truncation=True, max_length=256).to(device)

    # Generate test using model
    outputs = model.generate(
        inputs["input_ids"],
        max_length=max_length,
        min_length=min_length,
        num_beams=5,  # Increased beams for better exploration
        early_stopping=False,  # Disable early stopping
        no_repeat_ngram_size=2,  # Prevent repetitive outputs
    )

    # Decode and return result
    test_code = tokenizer.decode(
        outputs[0], skip_special_tokens=True).strip()
    return test_code
