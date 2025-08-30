# unittestgen/management/tools/fix_rejected.py
import ast
import json
import os
import re
from typing import Tuple

REJECTED = "dataset.rejected.audit.jsonl"
OUT = "dataset.fixed.candidates.jsonl"
REPORT = "dataset.fix_report.txt"

# Families we allow to auto-rename inside tests when names are close
FAMILIES = ("divide", "add", "subtract", "multiply", "power")

FLOAT_RE = re.compile(r"(-?\d+\.\d+(?:e[+-]?\d+)?)", re.IGNORECASE)


def get_func_name(src: str) -> str:
    try:
        tree = ast.parse(src)
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef):
                return n.name
    except SyntaxError:
        pass
    return ""


def guess_family(name: str) -> str:
    for fam in FAMILIES:
        if name == fam or name.startswith(f"{fam}_"):
            return fam
    return ""


def inject_pytest_if_needed(test: str) -> str:
    return ("import pytest; " + test) if "raises(" in test and "pytest" not in test else test


def wrap_isclose(test: str) -> str:
    # Replace "... == <float>" with math.isclose(..., <float>, rel_tol=1e-9, abs_tol=1e-9)
    if "==" not in test:
        return test
    parts = test.split("assert ")
    rebuilt = []
    added_math = False
    for p in parts:
        if "==" in p:
            left, right = p.split("==", 1)
            right_val = right.strip().rstrip(";")
            # only transform if right side looks like a float literal
            m = FLOAT_RE.match(right_val)
            if m:
                cmp = f"math.isclose({left.strip()}, {right_val}, rel_tol=1e-9, abs_tol=1e-9)"
                p = cmp + ";"
                added_math = True
            else:
                p = left + "==" + right
        rebuilt.append(p)
    out = "assert ".join(rebuilt)
    if added_math and "import math;" not in out:
        out = "import math; " + out
    return out


def normalize_zero_div_behavior(fn_src: str, test: str, fn_name: str) -> str:
    """
    If function clearly returns None when b==0, align tests that compare to 0.
    If function clearly returns 0 when b==0, align tests that expect None.
    Also keep pytest-raises tests if the function raises.
    """
    lower = fn_src.replace(" ", "")
    returns_none_on_zero = (
        "b==0:returnNone" in lower) or ("elseNone" in lower)
    returns_zero_on_zero = ("b==0:return0" in lower) or ("else0" in lower) or (
        "(a-a)" in lower) or ("(0.0ifa==0elseNone)" in lower)
    raises_on_zero = "raiseZeroDivisionError" in lower

    # Adjust expectations only for direct calls with denominator 0
    if raises_on_zero:
        # ensure pytest import is present (handled elsewhere)
        return test

    if returns_none_on_zero:
        # change "...(x,0) == 0" -> "is None"
        test = re.sub(rf"{fn_name}\(([^)]*?),\s*0\)\s*==\s*0",
                      rf"{fn_name}(\1,0) is None", test)
    elif returns_zero_on_zero:
        # change "...(x,0) is None" -> "== 0"
        test = re.sub(
            rf"{fn_name}\(([^)]*?),\s*0\)\s*is\s*None", rf"{fn_name}(\1,0) == 0", test)
    return test


def rename_called_function(test: str, want: str) -> str:
    """
    If test calls a sibling like divide_or_zero while current function is divide_or_zero,
    or vice-versa, swap them so calls match the function under test.
    """
    fam = guess_family(want)
    if not fam:
        return test

    # Find all simple call names in the test
    names = set(re.findall(r"\b([A-Za-z_]\w*)\(", test))
    if want in names:
        return test  # already matched

    # Heuristic: replace any *other* function name from the same family with `want`
    for n in sorted(names, key=len, reverse=True):
        if n == "test":  # def test_xxx(
            continue
        if n.startswith(fam):
            test = re.sub(rf"\b{re.escape(n)}\(", f"{want}(", test)
    return test


def single_line(s: str) -> str:
    return " ".join(s.strip().split())


def valid_python(s: str) -> bool:
    try:
        ast.parse(s)
        return True
    except SyntaxError:
        return False


def process_pair(item) -> Tuple[dict, str]:
    fn, test = item["input"].strip(), item["output"].strip()
    fn_name = get_func_name(fn)
    if not fn_name:
        return None, "bad_function_syntax"

    # 1) make sure tests call the right function in the same family
    test2 = rename_called_function(test, fn_name)
    # 2) float robustness
    test2 = wrap_isclose(test2)
    # 3) zero-division semantics alignment
    test2 = normalize_zero_div_behavior(fn, test2, fn_name)
    # 4) pytest import if needed
    test2 = inject_pytest_if_needed(test2)
    # 5) keep single line
    test2 = single_line(test2)

    # validate
    if not valid_python(test2):
        return None, "bad_test_syntax_after_fix"

    return {"input": single_line(fn), "output": test2}, "fixed"


def main():
    if not os.path.exists(REJECTED):
        print(f"[fix] {REJECTED} not found.")
        return

    fixed, skipped = [], []
    with open(REJECTED, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                skipped.append((i, "json_decode_error"))
                continue
            result, status = process_pair(item)
            if result:
                fixed.append(result)
            else:
                skipped.append((i, status))

    with open(OUT, "w", encoding="utf-8") as f:
        for ex in fixed:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(f"fixed={len(fixed)}\n")
        f.write(f"skipped={len(skipped)}\n")
        for idx, why in skipped[:50]:
            f.write(f"  line {idx}: {why}\n")

    print(f"[fix] wrote {len(fixed)} -> {OUT}")
    print(f"[fix] skipped {len(skipped)} (see {REPORT})")


if __name__ == "__main__":
    main()
