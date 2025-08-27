"""
Audit and normalize arithmetic function-test pairs.

- Reads dataset.jsonl ({"input": <func>, "output": <one-line pytest test>})
- For add/subtract/multiply/divide/power:
  * validates the function is a single safe def (no imports/dunders/semicolons)
  * executes the function in a restricted env to compute true RHS values
  * rewrites assert RHS if wrong; rejects suspicious lines
- Writes dataset.cleaned.jsonl and dataset.rejected.jsonl
"""

from __future__ import annotations

import ast
import json
import math
import re
from typing import Tuple, Dict, Any

SRC = "dataset.jsonl"
OUT_CLEAN = "dataset.cleaned.jsonl"
OUT_REJECT = "dataset.rejected.audit.jsonl"

ARITH_FAMILIES = {"add", "subtract", "multiply", "divide", "power"}

# --- sandbox helpers ---------------------------------------------------------


def _is_safe_single_func(tree: ast.AST) -> bool:
    """Allow exactly one top-level FunctionDef and no other statements."""
    if not isinstance(tree, ast.Module):
        return False
    if len(tree.body) != 1 or not isinstance(tree.body[0], ast.FunctionDef):
        return False
    return True


def _has_forbidden_tokens(src: str) -> bool:
    """Block obvious dangerous patterns."""
    if "__" in src:
        return True
    if "import " in src:
        return True
    if ";" in src:
        return True
    return False


def safe_exec_func(func_src: str, call_src: str) -> Tuple[str, Any]:
    """
    Execute a single user function and evaluate a call expression.

    Returns:
        ("ok", value) on success,
        ("raises", ExceptionClassName) if the call raises,
        ("blocked", None) if the function source is not accepted.
    """
    if _has_forbidden_tokens(func_src):
        return ("blocked", None)

    try:
        tree = ast.parse(func_src)
    except (SyntaxError, ValueError):
        return ("blocked", None)

    if not _is_safe_single_func(tree):
        return ("blocked", None)

    # Ultra-minimal safe builtins
    safe_builtins: Dict[str, Any] = {
        "abs": abs,
        "round": round,
        "float": float,
        "int": int,
        "len": len,
        "sum": sum,
        "max": max,
        "min": min,
        "pow": pow,
    }
    g = {"__builtins__": safe_builtins}
    l: Dict[str, Any] = {}

    try:
        code = compile(tree, "<func>", "exec")
        exec(code, g, l)  # pylint: disable=exec-used
    except (TypeError, ValueError, SyntaxError):
        return ("blocked", None)

    try:
        # Evaluate the call expression (e.g., "divide(6,3)")
        val = eval(call_src, g, l)  # pylint: disable=eval-used
        return ("ok", val)
    except (ArithmeticError, TypeError, ValueError, NameError, ZeroDivisionError) as err:
        return ("raises", type(err).__name__)


def format_num(x: Any) -> str:
    """Format ints/floats nicely and deterministically for RHS literals."""
    if isinstance(x, float):
        if math.isnan(x):
            return "float('nan')"
        if math.isinf(x):
            return "float('inf')" if x > 0 else "float('-inf')"
        if x == 0.0:
            return "0.0"  # normalize -0.0
        s = f"{x:.10f}".rstrip("0").rstrip(".")
        # Make "2.0" → "2"
        try:
            if float(s).is_integer():
                return str(int(round(float(s))))
        except (TypeError, ValueError):
            pass
        return s
    return repr(x)


LEADING_ZERO_PATTERN = re.compile(r"(^|[^\d])0\d+")  # matches 05, 025, etc.


def correct_asserts(func_src: str, test_src: str, fname: str) -> Tuple[bool, str]:
    """
    Parse a one-line pytest test and correct RHS numbers by executing the function.

    Returns:
        (True, corrected_test_src) if the test is acceptable (possibly corrected),
        (False, original_test_src) to reject this pair.
    """
    if "\n" in test_src:
        test_src = test_src.replace("\n", " ")

    if not test_src.strip().startswith("def "):
        return (False, test_src)

    # Extract (args, rhs) pairs for patterns like  func(args) == rhs
    pairs = re.findall(rf"{fname}\(([^)]*)\)\s*==\s*([^\s;]+)", test_src)

    # Reject suspicious RHS: identifiers (except float('inf'/'-inf'/'nan')), or leading-zero ints
    def _rhs_suspicious(rhs: str) -> bool:
        if rhs.startswith("float('"):
            return False
        if re.search(r"[A-Za-z_]", rhs):
            return True
        if LEADING_ZERO_PATTERN.search(rhs):
            return True
        return False

    for args, rhs in pairs:
        if _rhs_suspicious(rhs):
            return (False, test_src)

        status, out = safe_exec_func(func_src, f"{fname}({args})")
        if status == "ok":
            fixed_rhs = format_num(out)
            if fixed_rhs != rhs:
                test_src = test_src.replace(
                    f"{fname}({args})=={rhs}", f"{fname}({args})=={fixed_rhs}"
                )
        elif status == "raises":
            # We don’t rewrite to pytest.raises here; reject so you can curate.
            return (False, test_src)
        else:
            return (False, test_src)

    # Final guard for any stray leading-zero literals anywhere in the test
    if LEADING_ZERO_PATTERN.search(test_src):
        return (False, test_src)

    return (True, test_src)


# --- main --------------------------------------------------------------------


def main() -> None:
    kept, rej = 0, 0
    with open(SRC, "r", encoding="utf-8") as fi, \
            open(OUT_CLEAN, "w", encoding="utf-8") as fo, \
            open(OUT_REJECT, "w", encoding="utf-8") as fr:

        for line in fi:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                rej += 1
                fr.write(line)
                continue

            func = obj.get("input", "")
            test = obj.get("output", "")

            m = re.search(r"def\s+([a-zA-Z_]\w*)\s*\(", func)
            if not m:
                rej += 1
                fr.write(line)
                continue

            fname = m.group(1)
            family = fname.split("_")[0]

            if family in ARITH_FAMILIES:
                ok, fixed = correct_asserts(func, test, fname)
                if ok:
                    obj["output"] = fixed
                    fo.write(json.dumps(obj, ensure_ascii=False) + "\n")
                    kept += 1
                else:
                    fr.write(line)
                    rej += 1
            else:
                fo.write(json.dumps(obj, ensure_ascii=False) + "\n")
                kept += 1

    print(f"[audit] kept={kept} rejected={rej} -> {OUT_CLEAN} / {OUT_REJECT}")


if __name__ == "__main__":
    main()
