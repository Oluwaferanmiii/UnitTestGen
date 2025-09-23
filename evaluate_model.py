# evaluate_model.py
import json
from pathlib import Path
from tqdm import tqdm
from unittestgen.ai.codet5_engine import generate_test_from_code, _run_test_safely

# Paths
DATASET_PATH = Path("dataset.cleaned.jsonl")   # adjust if needed
REPORT_PATH = Path("evaluation_report.jsonl")  # will store results


def load_dataset(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def evaluate():
    dataset = list(load_dataset(DATASET_PATH))
    results = []
    success_count = 0

    print(f"[eval] Loaded {len(dataset)} function-test pairs")

    for i, sample in enumerate(tqdm(dataset, desc="Evaluating")):
        func_src = sample["input"]      # your function
        gold_test = sample["output"]    # reference test

        # Generate candidate test
        generated = generate_test_from_code(func_src)

        # Validate: does it pass?
        passed = _run_test_safely(func_src, generated)

        if passed:
            success_count += 1

        # Save results for inspection
        results.append({
            "id": i,
            "function": func_src,
            "reference_test": gold_test,
            "generated_test": generated,
            "passed": passed,
        })

    # Summary
    accuracy = success_count / len(dataset)
    print(f"[eval] Accuracy: {accuracy:.2%} ({success_count}/{len(dataset)})")

    # Write full report
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")

    print(f"[eval] Report saved → {REPORT_PATH}")


if __name__ == "__main__":
    evaluate()
