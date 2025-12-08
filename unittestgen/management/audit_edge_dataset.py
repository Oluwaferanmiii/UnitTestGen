"""
Audit and normalize *edge-case* function-test pairs.

- Reads dataset.edge.jsonl ({"input": <func>, "output": <pytest-style tests>})
- Performs light static checks:

  * function source parses and contains at least one FunctionDef
  * test source parses and contains at least one 'test_*' function
  * test file contains at least one 'assert' or 'pytest.raises(...)'
  * at least one test references one of the function names from the input

- Writes:
    dataset.edge.cleaned.jsonl
    dataset.edge.rejected.audit.jsonl
"""

from __future__ import annotations

import ast
import json
from typing import List, Set

SRC = "dataset.edge.jsonl"
OUT_CLEAN = "dataset.edge.cleaned.jsonl"
OUT_REJECT = "dataset.edge.rejected.audit.jsonl"

# ----------------- helpers -----------------


def get_function_names_from_src(src: str) -> List[str]:
    """
    Return list of top-level function names defined in `src`.
    If parsing fails, returns [].
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    names: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            names.append(node.name)
    return names


def test_module_has_test_functions(tree: ast.AST) -> bool:
    """True if there is at least one function whose name starts with 'test_'."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            return True
    return False


def test_module_has_assert_or_raises(tree: ast.AST) -> bool:
    """
    True if there is at least one Assert node OR a Call to pytest.raises().
    """
    has_assert = any(isinstance(n, ast.Assert) for n in ast.walk(tree))
    if has_assert:
        return True

    # look for pytest.raises(...) calls
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            # pytest.raises(...)
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "raises"
                and isinstance(func.value, ast.Name)
                and func.value.id == "pytest"
            ):
                return True
    return False


def test_module_references_funcs(tree: ast.AST, func_names: List[str]) -> bool:
    """
    True if at least one Name node in the test module matches a function name
    from the function source (e.g., 'is_palindrome', 'divide', etc.).
    """
    if not func_names:
        return False

    name_set: Set[str] = set(func_names)

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in name_set:
            return True
    return False

# ----------------- main audit -----------------


def main() -> None:
    kept, rej = 0, 0

    with open(SRC, "r", encoding="utf-8") as fi, \
            open(OUT_CLEAN, "w", encoding="utf-8") as fo, \
            open(OUT_REJECT, "w", encoding="utf-8") as fr:

        for line in fi:
            raw = line.rstrip("\n")

            if not raw.strip():
                rej += 1
                fr.write(raw + "\n")
                continue

            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                rej += 1
                fr.write(raw + "\n")
                continue

            func_src = (obj.get("input") or "").strip()
            test_src = (obj.get("output") or "").strip()

            if not func_src or not test_src:
                rej += 1
                fr.write(raw + "\n")
                continue

            # 1) Parse function source & collect function names
            func_names = get_function_names_from_src(func_src)
            if not func_names:
                # either parse failed or no functions present
                rej += 1
                fr.write(raw + "\n")
                continue

            # 2) Parse test source
            try:
                test_tree = ast.parse(test_src)
            except SyntaxError:
                rej += 1
                fr.write(raw + "\n")
                continue

            # 3) At least one test_* function
            if not test_module_has_test_functions(test_tree):
                rej += 1
                fr.write(raw + "\n")
                continue

            # 4) At least one assert or pytest.raises
            if not test_module_has_assert_or_raises(test_tree):
                rej += 1
                fr.write(raw + "\n")
                continue

            # 5) Test references at least one of the functions
            if not test_module_references_funcs(test_tree, func_names):
                rej += 1
                fr.write(raw + "\n")
                continue

            # If we got here, we keep it
            fo.write(json.dumps(obj, ensure_ascii=False) + "\n")
            kept += 1

    print(
        f"[edge-audit] kept={kept} rejected={rej} -> {OUT_CLEAN} / {OUT_REJECT}")


if __name__ == "__main__":
    main()
