# unittestgen/management/tools/check_alignment_generate.py
from pathlib import Path
import ast
import re

GEN_PATH = Path(__file__).resolve().parents[1] / "generate_dataset.py"

FUNC_DEF_RE = re.compile(r'^\s*def\s+([A-Za-z_]\w*)\s*\(', re.M)


def _extract_list_literal(text: str, varname: str):
    # Find "varname = [ ... ]" and return a Python list via ast.literal_eval
    start = text.find(f"{varname} = [")
    if start == -1:
        raise ValueError(f"Couldn't find `{varname} = [` in {GEN_PATH}")
    i = text.find("[", start)
    depth, j = 0, i
    while j < len(text):
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    literal = text[i:j]
    return ast.literal_eval(literal)


def _func_name_from_code(src: str) -> str | None:
    m = FUNC_DEF_RE.search(src or "")
    return m.group(1) if m else None


def _test_calls_function(test_src: str, name: str) -> bool:
    if not name:
        return False
    return re.search(r'\b' + re.escape(name) + r'\s*\(', test_src or "") is not None


def main():
    text = GEN_PATH.read_text(encoding="utf-8")
    functions = _extract_list_literal(text, "functions")
    tests = _extract_list_literal(text, "tests")

    print(f"Loaded functions={len(functions)}, tests={len(tests)}")

    n = min(len(functions), len(tests))
    first_bad = None
    for i in range(n):
        fname = _func_name_from_code(functions[i])
        if not _test_calls_function(tests[i], fname or ""):
            first_bad = i
            break

    if first_bad is not None:
        i = first_bad
        print(f"❌ Mismatch at index {i}")
        # show a small window to help you fix quickly
        for k in range(max(0, i-2), min(n, i+3)):
            fname_k = _func_name_from_code(functions[k]) or "<no def>"
            calls_ok = _test_calls_function(tests[k], fname_k)
            mark = "->" if k == i else "  "
            print(f"{mark} [{k}] func `{fname_k}` | calls_ok={calls_ok}")
    else:
        if len(functions) != len(tests):
            print(
                f"❌ Length mismatch: functions={len(functions)} vs tests={len(tests)}")
        else:
            print("✅ All tests line up with their functions!")


if __name__ == "__main__":
    main()
