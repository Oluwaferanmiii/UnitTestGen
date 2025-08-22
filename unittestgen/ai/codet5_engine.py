import os
import re
import torch
from functools import lru_cache
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# ---------- Device selection ----------
DEVICE = (
    torch.device("cuda") if torch.cuda.is_available()
    else torch.device("mps") if torch.backends.mps.is_available()
    else torch.device("cpu")
)
print(f"[codet5_engine] Using device: {DEVICE}")

# ---------- Model path (env) ----------
MODEL_DIR = os.environ.get(
    "MODEL_PATH",
    "/Users/oluwaferanmiii/Python/Thesis/fine_tuned_codet5p"
)
if not os.path.exists(MODEL_DIR):
    raise FileNotFoundError(
        f"[codet5_engine] Directory {MODEL_DIR} does not exist!")
print(f"[codet5_engine] Loading model from: {MODEL_DIR}")

# ---------- Lazy single-load (cached) ----------


@lru_cache(maxsize=1)
def _load_model_and_tokenizer():
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR)
    mdl.to(DEVICE)
    mdl.eval()                      # inference mode
    torch.set_grad_enabled(False)   # safety
    print("[codet5_engine] Model & tokenizer loaded (cached)")
    return tok, mdl


def _standardize_test_name(generated: str, function_name: str) -> str:
    """
    Force the first test function name to be test_<function_name>(...).
    Also normalizes some minor artifacts (spacing, repeated newlines).
    """
    text = generated.strip().replace("  ", " ").replace("\n\n", "\n")

    # Standardize the first 'def test_XXX(' occurrence
    text = re.sub(r"def\s+test_\w+\(",
                  f"def test_{function_name}(",
                  text, count=1)

    # Replace weird capitalizations of the function
    text = re.sub(
        rf"\b{re.escape(function_name.capitalize())}\b", function_name, text)
    text = re.sub(rf"\b{re.escape(function_name.upper())}\b",
                  function_name, text)
    text = re.sub(
        rf"\b{re.escape(function_name)}(?=\s*\()", function_name, text)

    # Remove dots within names (e.g., obj.method -> objmethod) to avoid invalid identifiers
    text = re.sub(r"\.(\w+)", r"\1", text)

    # Normalize assert spacing
    text = re.sub(r"assert\s+(\S)", r"assert \1", text)
    text = re.sub(r"assert\s+([^\s=]+)\s*==", r"assert \1 ==", text)

    return text.strip()


def generate_test_from_code(
    code_snippet: str,
    max_length: int = 150,
    min_length: int = 30,
    *,
    deterministic: bool = True,
    num_beams: int = 4,
    temperature: float = 0.6,
    top_k: int = 50,
) -> str:
    """
    Generate a PyTest-style unit test for a Python function.

    Args:
        code_snippet: The function code as a string.
        max_length/min_length: decoding limits.
        deterministic: True -> beam search (stable), False -> sampling (creative).
        num_beams: used when deterministic=True.
        temperature/top_k: used when deterministic=False.
    """
    tokenizer, model = _load_model_and_tokenizer()

    # Build prompt (your original prompt kept)
    prompt = (
        "Given this Python function:\n```python\n"
        f"{code_snippet}\n"
        "```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior."
    )

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,          # allow longer prompt safely
        padding=True,
        return_attention_mask=True,
    ).to(DEVICE)

    gen_kwargs = dict(
        max_length=max_length,
        min_length=min_length,
        no_repeat_ngram_size=3,
        early_stopping=True,
        num_return_sequences=1,
    )

    if deterministic:
        # Deterministic, stable for demos/eval
        gen_kwargs.update(dict(
            num_beams=max(1, int(num_beams)),
            do_sample=False,
        ))
    else:
        # Creative sampling
        gen_kwargs.update(dict(
            do_sample=True,
            temperature=max(0.1, float(temperature)),
            top_k=max(0, int(top_k)),
            num_beams=1,
        ))

    with torch.inference_mode():
        outputs = model.generate(
            inputs["input_ids"],
            attention_mask=inputs["attention_mask"],
            **gen_kwargs
        )

    test_code = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()

    # Try to infer function name from the snippet
    function_match = re.search(r"def\s+([A-Za-z_]\w*)\s*\(", code_snippet)
    function_name = function_match.group(
        1).lower() if function_match else "generated"

    # If the model returned a body only, wrap it into a test function
    if not re.search(r"^\s*def\s+\w+\s*\(", test_code):
        test_code = f"def test_{function_name}():\n    {test_code}"

    # Standardize/cleanup
    test_code = _standardize_test_name(test_code, function_name)

    return test_code


if __name__ == "__main__":
    sample = "def divide(a, b): return a / b"
    print(generate_test_from_code(sample))
