# unittestgen/ai/codet5_engine.py
# pylint: disable=eval-used
import os
import re
import ast
import textwrap
from functools import lru_cache
import math
import difflib
import unicodedata
from typing import Any, Tuple, List, Optional

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM


# -----------------------------
# Device selection
# -----------------------------
DEVICE = (
    torch.device("cuda") if torch.cuda.is_available()
    else torch.device("mps") if torch.backends.mps.is_available()
    else torch.device("cpu")
)
print(f"[codet5_engine] Using device: {DEVICE}")

# -----------------------------
# Debug / validator logging
# -----------------------------
_VALIDATOR_DEBUG = os.environ.get("VALIDATOR_DEBUG", "0") not in {
    "", "0", "false", "False"}
_BYPASS_VALIDATOR = os.environ.get("BYPASS_VALIDATOR", "0") not in {
    "", "0", "false", "False"}


def _vd(msg: str) -> None:
    if _VALIDATOR_DEBUG:
        print(f"[validator] {msg}")


# -----------------------------
# Model path (from env)
# -----------------------------
MODEL_DIR = os.environ.get(
    "MODEL_PATH",
    "/Users/oluwaferanmiii/Python/Thesis/fine_tuned_codet5p"
)

if not os.path.exists(MODEL_DIR):
    raise FileNotFoundError(
        f"[codet5_engine] Directory {MODEL_DIR} does not exist!"
    )

print(f"[codet5_engine] Loading model from: {MODEL_DIR}")


# -----------------------------
# Lazy single-load (cached)
# -----------------------------
@lru_cache(maxsize=1)
def _load_model_and_tokenizer():
    tok = AutoTokenizer.from_pretrained(MODEL_DIR)
    mdl = AutoModelForSeq2SeqLM.from_pretrained(MODEL_DIR)
    mdl.to(DEVICE)
    mdl.eval()
    torch.set_grad_enabled(False)
    print("[codet5_engine] Model & tokenizer loaded (cached)")
    return tok, mdl


# -----------------------------
# Small helpers
# -----------------------------
def _extract_function_defs(code_snippet: str) -> list[tuple[str, str]]:
    """
    Return a list of (func_name, source_segment) for all top-level
    non-test functions in the snippet.
    """
    try:
        tree = ast.parse(code_snippet)
    except SyntaxError:
        return []

    fn_defs: list[tuple[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("test_"):
            src = ast.get_source_segment(code_snippet, node) or ""
            fn_defs.append((node.name, src))
    return fn_defs


def _extract_function_name(code_snippet: str) -> str:
    """
    Extract a function name from the snippet.
    New logic: if multiple top-level defs exist, return the *first*.
    Preserves ALL old fallback behaviors.
    """
    if not code_snippet:
        return "generated"

    # NEW: use top-level defs first
    defs = _extract_function_defs(code_snippet)
    if defs:
        return defs[0][0]   # first function in the file

    match = re.search(r"\bdef\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(", code_snippet)
    if match:
        return match.group(1).strip()

    alt = re.search(r"([A-Za-z_][A-Za-z_0-9]*)\s*=", code_snippet)
    if alt:
        return alt.group(1).strip()

    return "generated"


def _ensure_pytest_import(txt: str) -> str:
    if "import pytest" not in txt:
        return "import pytest\n\n" + txt
    return txt


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _isclose(a: Any, b: Any, *, rtol: float = 1e-9, atol: float = 1e-9) -> bool:
    # exact types: use ==
    if isinstance(a, (int, bool)) and isinstance(b, (int, bool)):
        return a == b
    # floats: be tolerant
    try:
        return math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=atol)
    except Exception:       # pylint: disable=broad-exception-caught
        return a == b


def _count_asserts(src: str) -> int:
    try:
        t = ast.parse(src)
    except SyntaxError:
        return 0
    return sum(isinstance(n, ast.Assert) for n in ast.walk(t))


def _extract_calls_in_test(test_src: str, func_name: str) -> List[Tuple[List[Any], dict]]:
    """
    Find calls to `func_name` in the test and try to evaluate their arguments
    (only simple literals like ints/floats/tuples/lists of numbers).
    Returns list of (args_list, kwargs_dict) pairs we can try to re-evaluate.
    """
    try:
        t = ast.parse(test_src)
    except SyntaxError:
        return []

    calls: List[Tuple[List[Any], dict]] = []

    class EvalArg(ast.NodeVisitor):
        def _eval_node(self, node):
            # only allow simple numeric literals and containers thereof
            if isinstance(node, ast.Constant) and _is_number(node.value):
                return node.value
            if (
                isinstance(node, ast.UnaryOp)
                and isinstance(node.op, (ast.UAdd, ast.USub))
                and isinstance(node.operand, ast.Constant)
                and _is_number(node.operand.value)
            ):
                return +node.operand.value if isinstance(node.op, ast.UAdd) else -node.operand.value
            if isinstance(node, ast.Tuple):
                vals = [self._eval_node(e) for e in node.elts]
                return None if any(v is None for v in vals) else tuple(vals)
            if isinstance(node, ast.List):
                vals = [self._eval_node(e) for e in node.elts]
                return None if any(v is None for v in vals) else list(vals)
            # fallback: unsupported
            return None

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == func_name:
                args = [self._eval_node(a) for a in node.args]
                kwargs = {kw.arg: self._eval_node(
                    kw.value) for kw in node.keywords if kw.arg}
                if all(a is not None for a in args) and all(v is not None for v in kwargs.values()):
                    calls.append((args, kwargs))
            self.generic_visit(node)

    EvalArg().visit(t)
    return calls

# ---- helpers for tolerant numeric validation ----


def _is_seq(x):
    return isinstance(x, (list, tuple))


def _num_equal(a, b, *, rtol=1e-9, atol=1e-9):
    # scalar vs scalar
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=rtol, abs_tol=atol)
    # sequence vs sequence (same type/len), element-wise tolerant
    if _is_seq(a) and _is_seq(b) and len(a) == len(b) and type(a) is type(b):
        return all(_num_equal(x, y, rtol=rtol, atol=atol) for x, y in zip(a, b))
    # fallback to python equality
    return a == b


def _cmp_numeric(a, b, op, *, rtol=1e-9, atol=1e-9):
    """
    Tolerant comparisons for floats and simple numeric types.
    - '==' / '!=': tolerant numeric equality, element-wise for same-type sequences.
    - '<', '<=', '>', '>=': only if BOTH sides are numeric scalars; otherwise skip (return True).
      We skip because the test already passed under exec(); this re-check is conservative.
    """
    # tolerant equality (supports same-type sequences too)
    close = _num_equal(a, b, rtol=rtol, atol=atol)
    if op == "==":
        return close
    if op == "!=":
        return not close

    # For ordering, require plain numeric scalars on both sides
    if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        # Can't safely re-validate ordering of non-numerics — trust the exec() pass.
        return True

    af, bf = float(a), float(b)
    if op == "<":
        return (af < bf) and not math.isclose(af, bf, rel_tol=rtol, abs_tol=atol)
    if op == "<=":
        return (af <= bf) or math.isclose(af, bf, rel_tol=rtol, abs_tol=atol)
    if op == ">":
        return (af > bf) and not math.isclose(af, bf, rel_tol=rtol, abs_tol=atol)
    if op == ">=":
        return (af >= bf) or math.isclose(af, bf, rel_tol=rtol, abs_tol=atol)

    # Unknown operator tag (shouldn't happen here) — don't block a passing test.
    return True


def _cmp_bool_identity(left, right, tag):
    # Strict identity when RHS is a boolean; otherwise compare truthiness identity.
    if tag == "is":
        return (left is right) if isinstance(right, bool) else (bool(left) is bool(right))
    if tag == "is not":
        return (left is not right) if isinstance(right, bool) else (bool(left) is not bool(right))
    return False


def _asserts_semantically_true(ns: dict, test_src: str) -> bool:
    """
    Re-validate every `assert ...` in the generated test using the already-executed
    namespace `ns`. Supports ==, !=, <, <=, >, >= with float tolerance, and
    allows safe wrappers like round()/abs()/min()/max()/sum()/len() and math.*.

    We still rely on the prior exec() pass to catch exceptions side-effects.
    """
    try:
        tree = ast.parse(test_src)
    except SyntaxError:
        _vd("semantic: SyntaxError parsing test")
        return False

    # Minimal, safe evaluation environment (no builtins, tiny allowlist)
    SAFE_GLOBALS = {
        "__builtins__": {},
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
        "min": min,
        "max": max,
        "sum": sum,
        "len": len,
        "math": math,
        "True": True,      # harmless convenience
        "False": False,
    }

    def _eval(node):
        code = compile(ast.Expression(node), "<ast>", "eval")
        # ns shadows SAFE_GLOBALS so user function names resolve
        globs = {**SAFE_GLOBALS, **ns}
        return eval(code, globs, {})  # pylint: disable=eval-used

    # Map AST compare ops to string tags our comparator understands
    OP_TAG = {
        ast.Eq: "==",
        ast.NotEq: "!=",
        ast.Lt: "<",
        ast.LtE: "<=",
        ast.Gt: ">",
        ast.GtE: ">=",
        ast.Is: "is",           # NEW
        ast.IsNot: "is not",    # NEW
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue

        test = node.test
        # Handle chained or single comparisons: a < b < c … → all must hold.
        if isinstance(test, ast.Compare) and len(test.ops) >= 1 and len(test.comparators) >= 1:
            try:
                left_val = _eval(test.left)
            except Exception:   # pylint: disable=broad-exception-caught
                _vd("semantic: left side eval failed")
                return False

            values = [left_val]
            for comp in test.comparators:
                try:
                    values.append(_eval(comp))
                except Exception:   # pylint: disable=broad-exception-caught
                    _vd("semantic: comparator eval failed")
                    return False

            # pairwise compare with tolerance / identity
            left = values[0]
            for op_node, right in zip(test.ops, values[1:]):
                tag = OP_TAG.get(type(op_node))
                if tag is None:
                    # unsupported comparator like `in`, etc: trust exec() result
                    try:
                        ok = bool(_eval(test))
                    except Exception:   # pylint: disable=broad-exception-caught
                        _vd("semantic: unsupported comparator re-eval failed")
                        return False
                    if not ok:
                        _vd("semantic: unsupported comparator truthiness False")
                        return False
                    break
                if tag in {"is", "is not"}:
                    if not _cmp_bool_identity(left, right, tag):
                        _vd(
                            f"semantic: bool-identity compare failed: {left} {tag} {right}")
                        return False
                else:
                    if not _cmp_numeric(left, right, tag):
                        _vd(
                            f"semantic: numeric compare failed: {left} {tag} {right}")
                        return False
                left = right
            continue

        # Non-Compare: treat as truthiness check
        try:
            ok = bool(_eval(test))
        except Exception:   # pylint: disable=broad-exception-caught
            _vd("semantic: non-compare truthiness eval failed")
            return False
        if not ok:
            _vd("semantic: non-compare truthiness False")
            return False

    return True


def _normalize_test_for_similarity(txt: str) -> str:
    """
    Normalize test code so we can compare structure instead of exact formatting:
    - drop comments and blank lines
    - lowercase
    - collapse whitespace
    """
    lines = []
    for line in txt.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        lines.append(stripped)

    joined = " ".join(lines)
    # collapse multiple spaces
    joined = re.sub(r"\s+", " ", joined)
    return joined.lower().strip()


def _too_similar(a: str, b: str, *, threshold: float = 0.88) -> bool:
    """
    Return True if two tests are "too similar" to be considered a regeneration.
    Uses:
      - normalized text similarity
      - argument patterns of calls to the target function
    """
    na = _normalize_test_for_similarity(a)
    nb = _normalize_test_for_similarity(b)

    if not na or not nb:
        return False

    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    if ratio >= threshold:
        return True

    # Optional: compare literal call argument patterns if same target used.
    # We don't know func_name here, so this part will be done in the regen helper
    # where func_name is known.
    return False

# ---------- NEW: stronger AST-based operation inference ----------


def _detect_power_call(node: ast.AST) -> bool:
    """Return True if node is a pow(...) or math.pow(...)."""
    if isinstance(node, ast.Call):
        # pow(x, y)
        if isinstance(node.func, ast.Name) and node.func.id == "pow":
            return True
        # math.pow(x, y)
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.attr == "pow" and node.func.value.id == "math":
                return True
    return False


def _find_first_binop(node: ast.AST) -> Optional[str]:
    """
    Walk a subtree and return one of {'add','subtract','multiply','power'} if found.
    Recognizes:
      - a + b, a - b, a * b, a ** b
      - nested parentheses / unary ops around the binop
      - pow(a, b) or math.pow(a, b)
    """
    for n in ast.walk(node):
        # direct binary operations
        if isinstance(n, ast.BinOp):
            op = n.op
            if isinstance(op, ast.Add):
                return "add"
            if isinstance(op, ast.Sub):
                return "subtract"
            if isinstance(op, ast.Mult):
                return "multiply"
            if isinstance(op, ast.Pow):
                return "power"
        # power as a function call
        if _detect_power_call(n):
            return "power"
    return None


def _infer_simple_op(func_src: str, *, target_name: str | None = None) -> Optional[str]:
    """
    Inspect source and infer {'add','subtract','multiply','power','divide'}.

    If target_name is given, we only analyse the FunctionDef whose name matches
    target_name. If target_name is None, we fall back to the old behaviour:
    look at the first function in the module.
    """
    try:
        t = ast.parse(func_src)
    except SyntaxError:
        return None

    for node in t.body:
        if not isinstance(node, ast.FunctionDef):
            continue

        # In multi-function files, skip other functions
        if target_name is not None and node.name != target_name:
            continue

        # Look for a direct return first
        for stmt in node.body:
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                val = stmt.value
                # First, check simple binop / pow call in the return
                kind = _find_first_binop(val)
                if kind:
                    return kind
                # Also recognize a plain division
                if isinstance(val, ast.BinOp) and isinstance(
                    val.op, (ast.Div, ast.FloorDiv)
                ):
                    return "divide"
                # Handle trivial IfExp (ternary) where each branch is a simple binop
                if isinstance(val, ast.IfExp):
                    k1 = _find_first_binop(val.body)
                    k2 = _find_first_binop(val.orelse)
                    if k1 and k1 == k2:
                        return k1

        # If we were targeting a specific name, don't look further
        if target_name is not None:
            break

    return None
# ---------- END: stronger AST-based operation inference ----------


def _arithmetic_oracle(func_name: str, f, *, func_src: Optional[str] = None) -> bool:
    """
    Semantic probe for add/subtract/multiply/power (skip divide variants).
    If func_src is provided, infer the op from code so it works for renamed functions.
    """
    table = {
        "add": [
            ((3, 4), 7),
            ((-2, 5), 3),
            ((0.5, 0.25), 0.75),
        ],
        "subtract": [
            ((5, 3), 2),
            ((-2, -3), 1),
            ((0.5, 0.25), 0.25),
        ],
        "multiply": [
            ((2, 3), 6),
            ((-1, 5), -5),
            ((2.5, 4), 10.0),
        ],
        "power": [
            ((2, 3), 8),
            ((3, 0), 1),
            ((9, -1), 1/9),
        ],
    }

    inferred = _infer_simple_op(
        func_src, target_name=func_name) if func_src else None
    key = inferred or func_name.lower()
    if key not in table:   # e.g., divide or other custom behavior
        return True

    for (args, expected) in table[key]:
        try:
            got = f(*args)
        except Exception:   # pylint: disable=broad-exception-caught
            _vd(f"oracle: function raised on args={args}")
            return False
        if not _isclose(got, expected):
            _vd(f"oracle: mismatch on {key}{args} -> {got} != {expected}")
            return False
    return True


def _calls_target(test_src: str, func_name: str) -> bool:
    """Does the generated test call the function `func_name` at least once?"""
    try:
        t = ast.parse(test_src)
    except SyntaxError:
        return False

    class Finder(ast.NodeVisitor):
        def __init__(self):
            self.found = False

        def visit_Call(self, node):  # pylint: disable=invalid-name
            # direct calls: func_name(...)
            if isinstance(node.func, ast.Name) and node.func.id == func_name:
                self.found = True
            self.generic_visit(node)

    f = Finder()
    f.visit(t)
    return f.found


def _has_foreign_calls(test_src: str, target: str) -> bool:
    """
    Return True if the test calls any *user-level* function name other than `target`.
    Allow a small safe-list of builtins and a few library namespaces.
    """
    allow_names = {
        "round", "abs", "int", "float", "len", "sum", "max", "min",
        "set", "sorted", "any", "all", "enumerate", "range",
        "list", "tuple", "dict", "str", "reversed"
    }
    try:
        t = ast.parse(test_src)
    except SyntaxError:
        return True  # treat as foreign / invalid

    class Finder(ast.NodeVisitor):
        def __init__(self):
            self.bad = False

        def visit_Call(self, node):  # pylint: disable=invalid-name
            # direct name calls: foo(...)
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name != target and name not in allow_names:
                    self.bad = True
            # attribute calls: module.func(...). Allow common libs used in tests.
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                mod = node.func.value.id
                if mod in {"pytest", "math", "decimal", "fractions"}:
                    pass
                else:
                    # attribute call from unknown module – treat as foreign user call
                    self.bad = True
            self.generic_visit(node)

    f = Finder()
    f.visit(t)
    return f.bad


def _asserts_focus_on_target(test_src: str, func_name: str, *, min_ratio: float = 1.0) -> bool:
    """
    Return True iff at least `min_ratio` fraction of asserts reference a call to `func_name`.
    Default min_ratio=1.0 means *every* assert must reference the target.
    """
    try:
        t = ast.parse(test_src)
    except SyntaxError:
        return False

    total = 0
    hits = 0

    class CallFinder(ast.NodeVisitor):
        def __init__(self):
            self.seen = False

        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id == func_name:
                self.seen = True
            self.generic_visit(node)

    for node in ast.walk(t):
        if isinstance(node, ast.Assert):
            total += 1
            finder = CallFinder()
            finder.visit(node)
            if finder.seen:
                hits += 1

    if total == 0:
        return False
    return (hits / total) >= min_ratio


def _run_test_safely(func_src: str, test_src: str, *, func_name: str | None = None,) -> bool:
    """
    Execute function + test in an isolated namespace.
    Returns True only if:
      - The test has at least 1 assert (and not an absurd number),
      - The test calls the target function somewhere,
      - The test does NOT call other user-level functions,
      - Every assert references the target (no stray asserts),
      - Executing the test raises no exceptions (i.e., asserts pass),
      - Optional semantic probe passes for simple arithmetic functions.
    """

    # --- Minimal hardening: normalize and remove invisible/control chars ---
    def _clean_code(s: str) -> str:
        if not s:
            return ""
        # Normalize newlines
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        # Strip a run of BOM/ZW/RTL/NBSP at the very start (common cause of "line 1" SyntaxError)
        s = re.sub(
            r"^[\ufeff\u200b\u200c\u200d\u202a-\u202e\u2060-\u2063\u00a0]+", "", s)
        # Remove other control characters globally (keep newline and tab)
        s = "".join(ch for ch in s if (
            unicodedata.category(ch)[0] != "C" or ch in "\n\t"))
        return s

    func_src = _clean_code(func_src)
    test_src = _clean_code(test_src)

    target_name = func_name or _extract_function_name(func_src)

    # strip import pytest from the test body
    lines = test_src.splitlines()
    lines = [ln for ln in lines if not ln.strip().startswith("import pytest")]
    test_src = "\n".join(lines)

    # --- Structural pre-checks (unchanged behavior) ---
    num_asserts = _count_asserts(test_src)
    if num_asserts < 1 or num_asserts > 12:
        _vd(f"reject: bad assert count = {num_asserts}")
        return False

    if not _calls_target(test_src, target_name):
        _vd("reject: test does not call target")
        return False

    if not _asserts_focus_on_target(test_src, target_name, min_ratio=1.0):
        _vd("reject: at least one assert does not reference target")
        return False

    if _has_foreign_calls(test_src, target_name):
        _vd("reject: foreign user-level calls detected")
        return False

    # --- Syntax precheck ---
    try:
        ast.parse(func_src)
        ast.parse(test_src)
    except SyntaxError as e:
        _vd(f"reject: syntax precheck failed: {e}")
        return False

    # --- Execute in a fresh namespace ---
    ns: dict = {}
    try:
        exec(func_src, ns, ns)   # pylint: disable=exec-used
        exec(test_src, ns, ns)   # pylint: disable=exec-used
    except Exception as e:       # pylint: disable=broad-exception-caught
        _vd(f"reject: exec raised: {type(e).__name__}: {e}")
        return False

    # --- Post-exec semantic checks ---
    if not _asserts_semantically_true(ns, test_src):
        _vd("reject: semantic re-check failed")
        return False

    f = ns.get(target_name)
    if callable(f) and not _arithmetic_oracle(target_name, f, func_src=func_src):
        _vd("reject: arithmetic oracle failed")
        return False

    if target_name.lower() in {"add", "subtract", "multiply", "power"}:
        for args, _ in _extract_calls_in_test(test_src, target_name):
            try:
                out = f(*args)
            except Exception:   # pylint: disable=broad-exception-caught
                _vd("reject: arithmetic target raised on literal replay")
                return False
            if isinstance(out, float) and math.isnan(out):
                _vd("reject: arithmetic returned NaN")
                return False

    return True


def _standardize_test_name(generated: str, function_name: str) -> str:
    """
    Force the first test function name to be test_<function_name>(...).
    Normalize minor artifacts ONLY (no destructive transformations).
    """
    text = generated.strip()
    # Collapse repeated blank lines and excessive spaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Standardize the first 'def test_XXX(' occurrence
    text = re.sub(
        r"(?m)^\s*def\s+test_\w+\s*\(",
        f"def test_{function_name}(",
        text,
        count=1,
    )

    # Replace weird capitalizations of the function within identifiers
    text = re.sub(
        rf"\b{re.escape(function_name.capitalize())}\b", function_name, text)
    text = re.sub(rf"\b{re.escape(function_name.upper())}\b",
                  function_name, text)
    # Normalize `<FunctionName>(` → `function_name(`
    text = re.sub(
        rf"\b{re.escape(function_name)}\s*(?=\()", function_name, text)

    # Normalize assert spacing (avoid turning 'assert a == b' invalid)
    text = re.sub(r"assert\s+(\S)", r"assert \1", text)
    text = re.sub(r"assert\s+([^\s=]+)\s*==", r"assert \1 ==", text)

    return text.strip()


def _normalize_calls_to_target(test_src: str, function_name: str) -> str:
    """
    If the test calls a prefix variant of the target (e.g., 'subtract(') while
    the function is 'subtract_num', rewrite those calls to the exact target.

    Only rewrites Name calls where the callee is a strict prefix of the target
    and the next char in the target is an underscore, to avoid over-matching.
    """
    # base = function_name.replace("_", "")
    # Simple regex normalizations first
    test_src = re.sub(
        rf"\b{re.escape(function_name.replace('_', ''))}\b", function_name, test_src)
    test_src = re.sub(
        rf"\b{re.escape(function_name)}\s*(?=\()", function_name, test_src)

    # AST-based rename
    try:
        t = ast.parse(test_src)
    except SyntaxError:
        return test_src

    target_is_pred = function_name.startswith("is_")
    lower_target = function_name.lower()

    SAFE_EXCLUDED_IS_NAMES = {"isinstance",
                              "issubclass", "isfinite", "isnan", "isinf"}

    class Renamer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name):
                name = node.func.id
                lname = name.lower()

                # already correct
                if name == function_name:
                    return node

                # For predicate targets, rewrite *any* is_* style user call to the target,
                # except a few well-known builtins.
                if target_is_pred and lname.startswith("is") and lname not in SAFE_EXCLUDED_IS_NAMES:
                    node.func.id = function_name
                    return node

                # Otherwise, allow fuzzy rename when very close (lowered threshold)
                sim = difflib.SequenceMatcher(
                    None, lname, lower_target).ratio()
                if sim >= 0.58:
                    node.func.id = function_name
            return node

    try:
        fixed_tree = Renamer().visit(t)
        ast.fix_missing_locations(fixed_tree)
        return ast.unparse(fixed_tree)
    except Exception:   # pylint: disable=broad-exception-caught
        return test_src


def _strip_non_target_asserts(test_src: str, func_name: str) -> str:
    """
    Keep only assert statements that reference the target function. If that removes all asserts,
    return the original (so the pre-check will reject it cleanly).
    """
    try:
        tree = ast.parse(test_src)
    except SyntaxError:
        return test_src

    class Hits(ast.NodeVisitor):
        def __init__(self):
            self.hit = False

        def visit_Call(self, n):
            if isinstance(n.func, ast.Name) and n.func.id == func_name:
                self.hit = True
            self.generic_visit(n)

    new_body = []
    for node in tree.body:
        if isinstance(node, ast.Assert):
            h = Hits()
            h.visit(node)
            if h.hit:
                new_body.append(node)
        else:
            new_body.append(node)

    if not any(isinstance(n, ast.Assert) for n in new_body):
        return test_src

    tree.body = new_body
    try:
        ast.fix_missing_locations(tree)
        return ast.unparse(tree)
    except Exception:   # pylint: disable=broad-exception-caught
        return test_src


def _format_literal(v: Any) -> str:
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, float):
        if math.isnan(v):
            return "float('nan')"
        if math.isinf(v):
            return "float('inf')" if v > 0 else "float('-inf')"
        s = f"{v:.10f}".rstrip("0").rstrip(".")
        try:
            if float(s).is_integer():
                return str(int(round(float(s))))
        except Exception:   # pylint: disable=broad-exception-caught
            pass
        return s
    return repr(v)

# --- [LEGACY / UNUSED] ---
# def _auto_fix_assert_rhs(ns: dict, test_src: str, func_name: str) -> str:
#     """
#     For asserts like: <expr> == <literal>, if <expr> contains a call to func_name,
#     evaluate <expr> in ns and rewrite the RHS literal to the true value (bool/int/float).
#     """
#     try:
#         tree = ast.parse(test_src)
#     except SyntaxError:
#         return test_src

#     SAFE_GLOBALS = {
#         "__builtins__": {},
#         "math": math, "abs": abs, "round": round,
#         "int": int, "float": float, "min": min, "max": max, "sum": sum, "len": len,
#         **ns
#     }
#     changed = False

#     class Fixer(ast.NodeTransformer):
#         def visit_Assert(self, node):
#             nonlocal changed
#             test = node.test
#             if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
#                 # Only fix when LHS calls our target
#                 called = [False]

#                 class Finder(ast.NodeVisitor):
#                     def visit_Call(self, n):
#                         if isinstance(n.func, ast.Name) and n.func.id == func_name:
#                             called[0] = True
#                         self.generic_visit(n)
#                 Finder().visit(test.left)
#                 if not called[0]:
#                     return node

#                 # Evaluate left expression
#                 try:
#                     left_val = eval(compile(ast.Expression(
#                         test.left), "<ast>", "eval"), SAFE_GLOBALS, {})
#                 except Exception:   # pylint: disable=broad-exception-caught
#                     return node

#                 if isinstance(left_val, (bool, int, float)):
#                     new_rhs_code = _format_literal(left_val)
#                     try:
#                         new_rhs_ast = ast.parse(new_rhs_code, mode="eval").body
#                     except Exception:   # pylint: disable=broad-exception-caught
#                         return node
#                     test.comparators[0] = new_rhs_ast
#                     changed = True
#             return node

#     fixed = Fixer().visit(tree)
#     if not changed:
#         return test_src
#     try:
#         ast.fix_missing_locations(fixed)
#         return ast.unparse(fixed)
#     except Exception:   # pylint: disable=broad-exception-caught
#         return test_src


def _wrap_as_test_if_needed(body_or_test: str, func_name: str) -> str:
    """
    If the model returns only a body with asserts, wrap it into:
        def test_<func_name>():
            <body>
    """
    src = body_or_test.strip()
    if re.search(r"(?m)^\s*def\s+\w+\s*\(", src):
        return src
    indented = textwrap.indent(src, "    ")
    return f"def test_{func_name}():\n{indented}\n"


def _sanitize_test_src(txt: str, func_name: str) -> str:
    """
    Super-hardened sanitizer for model-generated test code.
    Removes invisible/bidi/control chars, ensures valid Python syntax,
    and rebuilds header if necessary.
    """

    # import unicodedata

    if not txt:
        txt = ""

    # --- DEBUG: Reveal invisible characters in the first 50 chars ---
    visible_repr = []
    for ch in txt[:80]:
        code = ord(ch)
        # Show printable chars normally, others as Unicode codepoints
        if 32 <= code <= 126:
            visible_repr.append(ch)
        elif ch == "\n":
            visible_repr.append("\\n")
        elif ch == "\t":
            visible_repr.append("\\t")
        else:
            visible_repr.append(f"\\u{code:04x}")

    # --- Normalize line endings ---
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")

    # --- Remove any leading junk before 'def' ---
    def_index = txt.find("def test_")
    if def_index > 0:
        txt = txt[def_index:]

    # --- Remove invisible and control characters (broad range) ---
    cleaned = []
    for ch in txt:
        cat = unicodedata.category(ch)
        # Keep only printable (L, N, P, S, Zs, etc.) or newline
        if cat[0] in {"C"} and ch != "\n":
            continue
        if ord(ch) < 32 and ch not in ("\n", "\t"):
            continue
        cleaned.append(ch)
    txt = "".join(cleaned)

    # --- Remove directionality / BOM / non-breaking spaces / zero-width ---
    txt = re.sub(
        r"[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF\u00A0\u00AD\uE000-\uF8FF]",
        "",
        txt,
    )

    # --- Normalize smart quotes and weird apostrophes ---
    txt = txt.replace("‘", "'").replace(
        "’", "'").replace("“", '"').replace("”", '"')

    # --- Standardize indentation ---
    txt = txt.replace("\t", "    ").strip()

    # --- Fix header if malformed ---
    if not re.match(r"^def\s+test_", txt):
        txt = f"def test_{func_name}():\n    pass"

    # --- Collapse duplicate test headers ---
    lines = txt.splitlines()
    cleaned_lines, seen = [], False
    for line in lines:
        if line.strip().startswith("def test_"):
            if seen:
                continue
            seen = True
        cleaned_lines.append(line)
    txt = "\n".join(cleaned_lines)

    # Fix invalid escape sequences like \C, \. by escaping raw backslashes
    txt = re.sub(r"(?<!\\)\\([^\\nrtbf'\"\\])", r"\\\\\1", txt)
    # --- Ensure it's syntactically valid ---
    try:
        ast.parse(txt)
    except SyntaxError:
        txt = f"def test_{func_name}():\n    # fallback: safe template\n    assert {func_name}('') is not None"

    return txt


def _decode_and_clean(tokenizer, seq_ids, func_name: str, *, func_src: str = "") -> str:
    txt = tokenizer.decode(seq_ids, skip_special_tokens=True).strip()

    # --- FIX: unwrap any accidental outer quotes, even escaped ones ---
    if (
        (txt.startswith('"') and txt.endswith('"')) or
        (txt.startswith("'") and txt.endswith("'"))
    ):
        txt = txt[1:-1]

    # Handle case where quotes are escaped (e.g., output starts with \" or \')
    if (
        (txt.startswith('\\"') and txt.endswith('\\"')) or
        (txt.startswith("\\'") and txt.endswith("\\'"))
    ):
        txt = txt[2:-2]

    txt = txt.replace("\\n", "\n").replace("\\t", "\t")

    txt = _wrap_as_test_if_needed(txt, func_name)
    txt = _standardize_test_name(txt, func_name)
    txt = _normalize_calls_to_target(txt, func_name)

    if _function_expects_strings(func_src) or _is_anagram_like(func_src):
        txt = _coerce_string_args_in_test(txt, func_name)

    # Final safety cleanup
    txt = _sanitize_test_src(txt, func_name)
    txt = _ensure_pytest_import(txt)
    return txt


def _function_expects_strings(code: str) -> bool:
    try:
        t = ast.parse(code)
    except SyntaxError:
        return False
    STR_METHODS = {
        "lower", "upper", "replace", "strip", "lstrip", "rstrip", "split", "join",
        "islower", "isupper", "isalpha", "isdigit", "isalnum", "isspace", "startswith", "endswith"
    }
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            if isinstance(n.func.value, ast.Name) and n.func.attr in STR_METHODS:
                return True
    return False


def _is_anagram_like(code: str) -> bool:
    # very lightweight detection: sorted(a) == sorted(b)
    try:
        t = ast.parse(code)
    except SyntaxError:
        return False
    for n in ast.walk(t):
        if isinstance(n, ast.Compare) and len(n.comparators) == 1:
            left, right = n.left, n.comparators[0]
            if all(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "sorted"
                   for x in (left, right)):
                return True
    return False


def _coerce_string_args_in_test(test_src: str, func_name: str) -> str:
    try:
        t = ast.parse(test_src)
    except SyntaxError:
        return test_src

    class Coercer(ast.NodeTransformer):
        def visit_Call(self, node):
            node = self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == func_name:
                new_args = []
                for a in node.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, (int, float)):
                        new_args.append(ast.Constant(value=str(a.value)))
                    else:
                        new_args.append(a)
                node.args = new_args
            return node

    try:
        new_t = Coercer().visit(t)
        ast.fix_missing_locations(new_t)
        return ast.unparse(new_t)
    except Exception:   # pylint: disable=broad-exception-caught
        return test_src


# ---------- NEW: predicate few-shot prompt helpers ----------


def _looks_like_predicate(code: str) -> bool:
    """Return True only for boolean-returning functions, not counters."""
    try:
        t = ast.parse(code)
    except SyntaxError:
        return False

    lowered = code.lower()

    # Early exclude: counters / length / numeric aggregations
    if any(k in lowered for k in [
        "def count_", "def num_", "def len_",
        "return len(", "collections.counter(",
        "sum(", "+= 1", "total +=", "counter(",
    ]):
        return False

    for node in ast.walk(t):
        if isinstance(node, ast.Return) and isinstance(getattr(node, "value", None), ast.Constant):
            if isinstance(node.value.value, bool):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr.startswith("is"):
                # skip if inside an aggregation context
                if "sum(" in lowered or "len(" in lowered or "+= 1" in lowered:
                    continue
                return True

    return any(k in lowered for k in [" is_", " return true", " return false"])


def looks_like_is_anagram(fn: str, code: str) -> bool:
    name = fn.lower()
    return (
        "is_anagram" in name
        or ("sorted(" in code and "==" in code and "(" in code and "," in code)
    )


def looks_like_is_palindrome(fn: str, code: str) -> bool:
    name = fn.lower()
    return (
        "is_palindrome" in name
        or ("return" in code and "==" in code and "s[::-1]" in code)
    )


_PREDICATE_FEWSHOT = (
    "### Example A\n"
    "Given this Python function:\n"
    "```python\n"
    "def is_even(n):\n"
    "    return n % 2 == 0\n"
    "```\n"
    "Correct style:\n"
    "```python\n"
    "def test_is_even():\n"
    "    assert is_even(4) == True\n"
    "    assert is_even(9) == False\n"
    "```\n\n"
    "### Example B\n"
    "Given this Python function:\n"
    "```python\n"
    "def is_prime(n):\n"
    "    if n <= 1: return False\n"
    "    if n <= 3: return True\n"
    "    if n % 2 == 0 or n % 3 == 0: return False\n"
    "    i = 5\n"
    "    while i * i <= n:\n"
    "        if n % i == 0 or n % (i+2) == 0: return False\n"
    "        i += 6\n"
    "    return True\n"
    "```\n"
    "Correct style (note both asserts call `is_prime`):\n"
    "```python\n"
    "def test_is_prime():\n"
    "    assert is_prime(7) == True\n"
    "    assert is_prime(32) == False\n"
    "```\n\n"
)

_STRING_PREDICATE_FEWSHOT = (
    "### String predicate examples\n"
    "# Always pass alphabetic strings; digits like '4' are not uppercase letters.\n"
    "```python\n"
    "def test_is_upper_basic():\n"
    "    assert is_upper('HELLO') == True\n"
    "    assert is_upper('Hello') == False\n"
    "    assert is_upper('hello') == False\n"
    "    assert is_upper('123') == False\n"
    "```\n"
    "```python\n"
    "def test_is_lower_basic():\n"
    "    assert is_lower('hello') == True\n"
    "    assert is_lower('Hello') == False\n"
    "    assert is_lower('HELLO') == False\n"
    "    assert is_lower('abc123') == False\n"
    "```\n"
)

_STRING_PREDICATE_FEWSHOT_UPPER = (
    "### String predicate examples (UPPER)\n"
    "Given this function:\n"
    "```python\n"
    "def is_upper(s: str) -> bool:\n"
    "    return s.isupper()\n"
    "```\n"
    "Correct truth pattern:\n"
    "- 'HELLO' -> True\n"
    "- 'Hello' -> False\n"
    "- 'hello' -> False\n"
    "- '123'   -> False (no cased letters)\n"
    "Tests:\n"
    "```python\n"
    "def test_is_upper():\n"
    "    assert is_upper('HELLO') == True\n"
    "    assert is_upper('Hello') == False\n"
    "    assert is_upper('123') == False\n"
    "```\n\n"
)

_STRING_PREDICATE_FEWSHOT_LOWER = (
    "### String predicate examples (LOWER)\n"
    "Given this function:\n"
    "```python\n"
    "def is_lower(s: str) -> bool:\n"
    "    return s.islower()\n"
    "```\n"
    "Correct truth pattern:\n"
    "- 'hello' -> True\n"
    "- 'Hello' -> False\n"
    "- 'HELLO' -> False\n"
    "- '123'   -> False (no cased letters)\n"
    "Tests:\n"
    "```python\n"
    "def test_is_lower():\n"
    "    assert is_lower('hello') == True\n"
    "    assert is_lower('Hello') == False\n"
    "    assert is_lower('123') == False\n"
    "```\n\n"
)

_STRING_COUNTER_FEWSHOT = (
    "### String counter examples\n"
    "# Use short literals; include empty string and mixed cases.\n"
    "```python\n"
    "def test_count_uppercase_small():\n"
    "    assert count_uppercase('Hello World') == 2\n"
    "    assert count_uppercase('no caps') == 0\n"
    "    assert count_uppercase('ABCdef') == 3\n"
    "    assert count_uppercase('') == 0\n"
    "```\n"
    "RULE: For counter functions returning integers, compare with numeric values (0, 1, 2...), never booleans.\n"
)


def _prompt_for(code_snippet: str, func_name: str | None = None) -> str:
    """
    Build a prompt for a SINGLE target function.

    - If the file contains multiple functions, we first extract the body of the
      specific `func_name` and show ONLY that in the prompt.
    - We still assume the rest of the file is available at runtime, but the
      tests must not call any other user-defined functions.
    """
    fn = func_name or _extract_function_name(code_snippet)

    # --- Isolate the source for just this function, if possible ---
    func_src = None
    for name, src in _extract_function_defs(code_snippet):
        if name == fn:
            func_src = (src or "").strip()
            break

    # Fallback: if we didn't find a clean def block, use the whole snippet
    if not func_src:
        func_src = code_snippet.strip()

    name_lower = fn.lower()
    code_lower = func_src.lower()

    # --- Shared base instruction (now clearly scoped to a single function) ---
    base = (
        "You are given a Python file that may contain several functions.\n"
        f"Your task is to write tests **only** for the function `{fn}` shown below.\n"
        "Do not test or call any other functions from the file.\n\n"
        "Target function:\n"
        "```python\n"
        f"{func_src}\n"
        "```\n"
        "Write ONE PyTest unit test function named `test_<function_name>` "
        "with at least two assert statements.\n"
        f"- Every assert must call **exactly** `{fn}` (use this exact name).\n"
        "- Do not call any other user-defined helpers.\n"
        "- Use only these builtins if needed: abs, round, int, float, len, sum, max, min, and math.\n"
        "- If the code uses string methods (e.g., `.islower()`, `.isupper()`, `.lower()`, `.replace()`), "
        "pass **string arguments** like 'abc'.\n"
        "- If it compares `sorted(a) == sorted(b)`, pass **string pairs** like ('listen', 'silent').\n"
        "- No pytest fixtures, no parametrize, no classes, no print statements.\n"
        "- Output ONLY the test function (no extra text).\n"
    )

    # --- Helper predicates using ONLY this function's body ---
    def looks_like_is_lower() -> bool:
        return ("is_lower" in name_lower) or (".islower(" in code_lower)

    def looks_like_is_upper() -> bool:
        return ("is_upper" in name_lower) or (".isupper(" in code_lower)

    def looks_like_string_counter() -> bool:
        body = code_lower
        return (
            "count" in name_lower
            or name_lower.startswith(("num_", "len_"))
            or "uppercase" in name_lower
            or "lowercase" in name_lower
            # structural cues (numeric aggregation)
            or ("sum(" in body and ".isupper(" in body)
            or ("sum(" in body and ".islower(" in body)
            or "collections.counter(" in body
            or "return len(" in body
            or " += 1" in body and ".isupper(" in body
            or " += 1" in body and ".islower(" in body
        )

    def looks_like_string_predicate() -> bool:
        return (
            looks_like_is_lower()
            or looks_like_is_upper()
            or any(k in code_lower for k in [".isalpha(", ".isdigit(", ".istitle("])
            or re.search(r"^is_(alpha|digit|title)$", name_lower)
        )

    # --- Special routing for counters / string predicates / anagram / palindrome ---

    if looks_like_string_counter():
        return _STRING_COUNTER_FEWSHOT + base + (
            "\nRULE: Every assert must call EXACTLY "
            f"`{fn}`; do NOT call `is_upper`/`islower` directly.\n"
            "RULE: Compare the result to integers (0, 1, 2, ...), never booleans.\n"
            "RULE: Include examples with mixed case, empty strings, and no uppercase letters."
        )

    elif looks_like_is_lower():
        return _STRING_PREDICATE_FEWSHOT_LOWER + base + (
            "\nRULE: For `is_lower`, 'HELLO' must be False, "
            "'hello' must be True, and '123' must be False.\n"
            "Avoid numeric strings as positives."
        )

    elif looks_like_is_upper():
        return _STRING_PREDICATE_FEWSHOT_UPPER + base + (
            "\nRULE: For `is_upper`, 'HELLO' must be True, "
            "'hello' must be False, and '123' must be False."
        )

    elif looks_like_is_anagram(fn, func_src):
        return (
            "### is_anagram examples\n"
            "Given this function:\n"
            "```python\n"
            "def is_anagram(a: str, b: str) -> bool:\n"
            "    return sorted(a) == sorted(b)\n"
            "```\n"
            "Correct tests:\n"
            "```python\n"
            "def test_is_anagram():\n"
            "    assert is_anagram('listen','silent') == True\n"
            "    assert is_anagram('rat','car') == False\n"
            "```\n\n"
            + base
            + f"\nRULE: Every assert must call `{fn}` with exactly two string arguments."
        )

    elif looks_like_is_palindrome(fn, func_src):
        return (
            "### is_palindrome examples\n"
            "Given this function:\n"
            "```python\n"
            "def is_palindrome(s: str) -> bool:\n"
            "    return s == s[::-1]\n"
            "```\n"
            "Correct tests:\n"
            "```python\n"
            "def test_is_palindrome():\n"
            "    assert is_palindrome('madam') == True\n"
            "    assert is_palindrome('python') == False\n"
            "```\n\n"
            + base
            + "\nRULE: Use alphabetic strings or phrases; avoid numbers unless they form true palindromes."
        )

    elif looks_like_string_predicate():
        prompt = _STRING_PREDICATE_FEWSHOT + base
        prompt += "\nRULE: For string predicates, use alphabetic examples; avoid numeric literals.\n"
        return prompt

    # --- Fallback: general predicate or numeric, still using only this function's code ---
    elif _looks_like_predicate(func_src):
        return _PREDICATE_FEWSHOT + base

    elif _function_expects_strings(func_src) or _is_anagram_like(func_src):
        base_extra = (
            "\nAdditional constraints:\n"
            "- Use **string** inputs (e.g., 'HELLO'/'Hello', 'racecar'/'python', 'listen'/'silent').\n"
            "- Avoid numbers for these tests.\n"
        )
        return base + base_extra

    # Default: plain numeric or general function
    return base


def _regen_prompt_for(
    code_snippet: str,
    func_name: str,
    previous_test: str,
) -> str:
    """
    Prompt variant for regeneration:
    - Reuses the normal few-shot prompt logic.
    - Shows the previously generated test and explicitly asks
      for a different one.
    """
    base = _prompt_for(code_snippet, func_name)

    extra = (
        "\n\nThe following test function was generated earlier:\n"
        "```python\n"
        f"{previous_test.strip()}\n"
        "```\n"
        "Now write a *different* valid PyTest test function for "
        f"`{func_name}`:\n"
        "- Use different input combinations or assertions than the previous test.\n"
        "- You may still test similar behavior, but avoid copying the same literal values.\n"
        "- Follow all previous rules (no fixtures, no classes, focus on this function only).\n"
    )

    return base + extra


def _try_candidates(
    tokenizer,
    model,
    enc_inputs,
    *,
    code_snippet: str,
    func_name: str,
    max_new_tokens: int,
    do_sample: bool,
    num_return: int,
    num_beams: int = 1,
    temperature: float = 0.7,
    top_k: int = 50,
):
    """Generate `num_return` candidates and return the first passing one, else None."""
    with torch.inference_mode():
        outs = model.generate(
            enc_inputs["input_ids"],
            attention_mask=enc_inputs["attention_mask"],
            max_new_tokens=max_new_tokens,
            min_length=0,
            no_repeat_ngram_size=0 if not do_sample else 0,  # keep your behavior
            early_stopping=True,
            do_sample=do_sample,
            temperature=max(0.1, float(temperature)) if do_sample else None,
            top_k=max(0, int(top_k)) if do_sample else None,
            num_beams=max(1, int(num_beams)),
            num_return_sequences=max(1, int(num_return)),
        )

    rejections = []

    for i in range(outs.shape[0]):
        candidate = _decode_and_clean(
            tokenizer, outs[i], func_name, func_src=code_snippet
        )
        # If your _decode_and_clean doesn't call the sanitizer internally,
        # uncomment the next line:
        # candidate = _sanitize_test_src(candidate, func_name)

        candidate = _strip_non_target_asserts(candidate, func_name)

        if _VALIDATOR_DEBUG:
            print("\n[validator] ---------- CANDIDATE BEGIN ----------")
            print(candidate)
            print("[validator] ----------- CANDIDATE END -----------")

        # --- NEW: Fast syntax guard before any execution ---
        try:
            ast.parse(candidate)
        except SyntaxError:
            if _VALIDATOR_DEBUG:
                print("[validator] REJECT (pre): syntax")
            rejections.append((candidate, "syntax"))
            continue

        # Quick pre-checks to collect reason strings
        def _first_reject_reason(test_src: str):
            n = _count_asserts(test_src)
            if n < 1 or n > 12:
                return f"bad assert count={n}"
            if not _calls_target(test_src, func_name):
                return "does not call target"
            if not _asserts_focus_on_target(test_src, func_name, min_ratio=1.0):
                return "an assert does not reference target"
            if _has_foreign_calls(test_src, func_name):
                return "foreign user-level calls"
            return None

        reason = _first_reject_reason(candidate)
        if reason is not None:
            if _VALIDATOR_DEBUG:
                print(f"[validator] REJECT (pre): {reason}")
            rejections.append((candidate, reason))
            continue

        ok = _run_test_safely(code_snippet, candidate, func_name=func_name)
        if ok:
            return candidate
        else:
            if _VALIDATOR_DEBUG:
                print("[validator] REJECT (run): failed in exec/semantic/oracle")
            rejections.append((candidate, "exec/semantic/oracle"))

    if _VALIDATOR_DEBUG and rejections:
        print("\n[validator] SUMMARY: all candidates rejected.")
        for idx, (_cand, why) in enumerate(rejections, 1):
            print(f"[validator]  {idx:02d}. reason: {why}")

    return None

# -----------------------------
# Public API: auto-validated generation (beams → sampling → fallback)
# -----------------------------

# -----------------------------
# Single-function generator helper
# -----------------------------


def _generate_for_single_function(
    code_snippet: str,
    func_name: str,
    *,
    max_new_tokens: int,
    beam_candidates: int,
    sample_candidates: int,
    num_beams: int,
    temperature: float,
    top_k: int,
) -> str:
    """
    Core generation/validation pipeline for a SINGLE function name.

    This is essentially your old generate_test_from_code logic, but
    parameterized by func_name so we can reuse it for multi-function files.
    """
    print(
        f"[validator] generate(single): {func_name} – beams→sampling→fallback")

    tokenizer, model = _load_model_and_tokenizer()
    # NOTE: we now pass func_name into the prompt, instead of re-extracting it
    prompt = _prompt_for(code_snippet, func_name)

    enc = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
        return_attention_mask=True,
    ).to(DEVICE)

    # -------------------------
    # Optional: bypass validator (unchanged)
    # -------------------------
    if _BYPASS_VALIDATOR:
        with torch.inference_mode():
            raw = model.generate(
                enc["input_ids"],
                attention_mask=enc["attention_mask"],
                max_new_tokens=max_new_tokens,
                min_length=24,
                no_repeat_ngram_size=3,
                length_penalty=1.15,                   # helps complete a full test
                repetition_penalty=1.07,              # discourages token loops
                early_stopping=True,
                do_sample=True,
                temperature=max(0.1, float(temperature)),
                top_k=max(0, int(top_k)),
                top_p=(0.92),
                num_beams=4,
                num_return_sequences=1,
            )
        txt = _decode_and_clean(tokenizer, raw[0], func_name)
        return "# origin: raw_unvalidated\n" + txt

    # -------------------------
    # 1) Deterministic beams  (unchanged)
    # -------------------------
    passing = _try_candidates(
        tokenizer,
        model,
        enc,
        code_snippet=code_snippet,
        func_name=func_name,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        num_return=max(1, int(beam_candidates)),
        num_beams=max(1, int(num_beams)),
    )
    if passing:
        return "# Origin: Beams \n" + passing

    # -------------------------
    # 2) Sampling for diversity (unchanged)
    # -------------------------
    passing = _try_candidates(
        tokenizer,
        model,
        enc,
        code_snippet=code_snippet,
        func_name=func_name,
        max_new_tokens=max_new_tokens,
        do_sample=True,
        num_return=max(1, int(sample_candidates)),
        temperature=temperature,
        top_k=top_k,
    )
    if passing:
        return "# Origin : sampling \n" + passing

    # -------------------------
    # 3) Fallbacks (your existing block, using fn = func_name)
    # -------------------------
    fn = func_name
    op = _infer_simple_op(code_snippet, target_name=fn) or fn.lower()

    if fn == "add":
        return _ensure_pytest_import(
            "def test_add():\n"
            "   assert add(3, 4) == 7\n"
            "   assert add(-2, 5) == 3\n"
        )
    if fn == "subtract":
        return _ensure_pytest_import(
            "def test_subtract():\n"
            "   assert subtract(5, 3) == 2\n"
            "   assert subtract(-2, -3) == 1\n"
        )
    if fn == "multiply":
        return _ensure_pytest_import(
            "def test_multiply():\n"
            "   assert multiply(2, 3) == 6\n"
            "   assert multiply(-1, 5) == -5\n"
        )
    if fn == "divide":
        return _ensure_pytest_import(
            "def test_divide():\n"
            "   assert divide(8, 4) == 2\n"
            "   assert divide(-6, 3) == -2"
        )
    if fn == "power":
        return _ensure_pytest_import(
            "def test_power():\n"
            "   assert power(2, 3) == 8\n"
            "   assert power(3, 0) == 1"
        )

    # --- Non-arithmetic Tier-1 fallbacks ---
    if fn == "count_vowels":
        return _ensure_pytest_import(
            "def test_count_vowels():\n"
            "   assert count_vowels('hello') == 2\n"
            "   assert count_vowels('bcd') == 0\n"
            "   assert count_vowels('AEiou') == 5\n"
        )

    if fn == "is_even":
        return _ensure_pytest_import(
            "def test_is_even():\n"
            "   assert is_even(2) == True\n"
            "   assert is_even(3) == False\n"
            "   assert is_even(0) == True\n"
        )

    if fn == "is_odd":
        return _ensure_pytest_import(
            "def test_is_odd():\n"
            "   assert is_odd(2) == False\n"
            "   assert is_odd(3) == True\n"
            "   assert is_odd(1) == True\n"
        )

    if fn == "is_lower":
        return _ensure_pytest_import(
            "def test_is_lower():\n"
            "   assert is_lower('hello') == True\n"
            "   assert is_lower('Hello') == False\n"
            "   assert is_lower('HELLO') == False\n"
        )

    if fn == "is_upper":
        return _ensure_pytest_import(
            "def test_is_upper():\n"
            "   assert is_upper('HELLO') == True\n"
            "   assert is_upper('Hello') == False\n"
            "   assert is_upper('123') == False\n"
        )

    if fn == "is_palindrome":
        return _ensure_pytest_import(
            "def test_is_palindrome():\n"
            "   assert is_palindrome('racecar') == True\n"
            "   assert is_palindrome('python') == False\n"
        )

    if fn == "reverse_string":
        return _ensure_pytest_import(
            "def test_reverse_string():\n"
            "   assert reverse_string('abc') == 'cba'\n"
            "   assert reverse_string('') == ''\n"
        )

    if fn == "repeat_string":
        return _ensure_pytest_import(
            "def test_repeat_string():\n"
            "    assert repeat_string('hi', 3) == 'hihihi'\n"
            "    assert repeat_string('a', 0) == ''\n"
            "    assert repeat_string('', 5) == ''\n"
        )

    if fn == "remove_duplicates":
        return _ensure_pytest_import(
            "def test_remove_duplicates():\n"
            "   assert remove_duplicates([1,1,2,3,2]) == [1,2,3]\n"
            "   assert remove_duplicates([]) == []\n"
        )

    if fn == "is_anagram":
        return _ensure_pytest_import(
            "def test_is_anagram():\n"
            "   assert is_anagram('listen','silent') == True\n"
            "   assert is_anagram('rat','car') == False\n"
        )

    # --- Non-arithmetic Tier-2 fallbacks (string utilities) ---
    if fn == "reverse_words":
        return _ensure_pytest_import(
            "def test_reverse_words():\n"
            "    assert reverse_words('hello world') == 'world hello'\n"
            "    assert reverse_words('a b c') == 'c b a'\n"
            "    assert reverse_words('single') == 'single'\n"
        )

    if fn == "normalize_whitespace":
        return _ensure_pytest_import(
            "def test_normalize_whitespace():\n"
            "    assert normalize_whitespace('  hello   world  ') == 'hello world'\n"
            "    assert normalize_whitespace('\\tfoo  bar\\n') == 'foo bar'\n"
        )

    if fn == "strip_punctuation":
        return _ensure_pytest_import(
            "def test_strip_punctuation():\n"
            "    assert strip_punctuation('Hello, world!') == 'Hello world'\n"
            "    assert strip_punctuation('Good-morning!!!') == 'Goodmorning'\n"
        )

    if fn == "count_uppercase":
        return _ensure_pytest_import(
            "def test_count_uppercase():\n"
            "    assert count_uppercase('Hello World') == 2\n"
            "    assert count_uppercase('no caps') == 0\n"
            "    assert count_uppercase('ABCdef') == 3\n"
            "    assert count_uppercase('123!') == 0\n"
            "    assert count_uppercase('') == 0\n"
        )

    if fn == "strip_numbers":
        return _ensure_pytest_import(
            "def test_strip_numbers():\n"
            "    assert strip_numbers('abc123') == 'abc'\n"
            "    assert strip_numbers('no digits') == 'no digits'\n"
            "    assert strip_numbers('42life') == 'life'\n"
        )

    if fn == "replace_substring":
        return _ensure_pytest_import(
            "def test_replace_substring():\n"
            "    assert replace_substring('hello world', 'world', 'there') == 'hello there'\n"
            "    assert replace_substring('abcabc', 'a', 'x') == 'xbcxbc'\n"
            "    assert replace_substring('nochange', 'z', 'q') == 'nochange'\n"
        )

    if fn == "remove_vowels":
        return _ensure_pytest_import(
            "def test_remove_vowels():\n"
            "    assert remove_vowels('hello') == 'hll'\n"
            "    assert remove_vowels('AEIOU') == ''\n"
            "    assert remove_vowels('xyz') == 'xyz'\n"
        )

    # Worst-case: valid test shell (avoid wrong asserts)
    return _ensure_pytest_import(
        f"def test_{fn}():\n"
        "    # model could not produce a valid passing test yet\n"
        f"    assert callable({fn})\n"
    )

# -----------------------------
# Merge helper for multi-function tests
# -----------------------------


def _merge_multi_function_tests(snippets: list[str]) -> str:
    """
    Merge several single-function test snippets into one block:
    - keep a single `import pytest` at the top
    - drop per-snippet '# Origin: ...' comments
    """
    bodies: list[str] = []
    saw_import = False

    for snippet in snippets:
        lines_out: list[str] = []
        for line in snippet.splitlines():
            stripped = line.strip()

            if stripped.startswith("# Origin"):
                # we will add one combined origin header at the top
                continue
            if stripped.startswith("import pytest"):
                if not saw_import:
                    lines_out.append("import pytest")
                    saw_import = True
                continue

            lines_out.append(line)

        body = "\n".join(lines_out).strip()
        if body:
            bodies.append(body)

    header = "# Origin: Beams (multi-function)\n"
    return header + "\n\n".join(bodies)


# -----------------------------
# Public API: multi-function aware
# -----------------------------
def generate_test_from_code(
    code_snippet: str,
    *,
    # decoding size
    max_new_tokens: int = 240,
    # candidate budgets
    beam_candidates: int = 4,
    sample_candidates: int = 12,
    # beam params
    num_beams: int = 4,
    # sampling params
    temperature: float = 0.85,
    top_k: int = 100,
) -> str:
    """
    Generate PyTest-style unit tests and validate them automatically.

    - If there is 0 or 1 top-level user function: behave like before,
      but now we pass the *isolated function source* into the generator.
    - If there are 2+ functions: generate tests for each (using each
      function's own source) and merge them.
    """
    fn_defs = _extract_function_defs(code_snippet)

    # 0 or 1 function → single-function path
    if len(fn_defs) <= 1:
        if fn_defs:
            single_name, single_src = fn_defs[0]
        else:
            # fallback: no explicit def found, keep current behaviour
            single_name = _extract_function_name(code_snippet)
            single_src = code_snippet

        return _generate_for_single_function(
            # <- isolated src (or whole snippet if unknown)
            single_src,
            single_name,
            max_new_tokens=max_new_tokens,
            beam_candidates=beam_candidates,
            sample_candidates=sample_candidates,
            num_beams=num_beams,
            temperature=temperature,
            top_k=top_k,
        )

    # Multi-function path
    print(
        f"[multi] Detected {len(fn_defs)} functions: {[n for n, _ in fn_defs]}")
    snippets: list[str] = []

    for func_name, fn_src in fn_defs:
        # IMPORTANT: pass this function's own source, not the whole file
        tests_for_fn = _generate_for_single_function(
            fn_src,
            func_name,
            max_new_tokens=max_new_tokens,
            beam_candidates=beam_candidates,
            sample_candidates=sample_candidates,
            num_beams=num_beams,
            temperature=temperature,
            top_k=top_k,
        )
        snippets.append(tests_for_fn)

    return _merge_multi_function_tests(snippets)

# -----------------------------
# Regeneration helper (NEW)
# -----------------------------


def regenerate_test_for_function(
    code_snippet: str,
    func_name: str,
    previous_test: str,
    *,
    max_new_tokens: int = 240,
    sample_candidates: int = 12,
    temperature: float = 0.95,
    top_k: int = 120,
) -> str:
    """
    Regenerate a *different* test for a single function.

    - Uses sampling-only (no beams) to increase diversity.
    - Uses a regen-specific prompt that shows the previous test.
    - Rejects tests that are too similar to the previous one.
    """
    print(f"[validator] regenerate(single): {func_name} - sampling-only")

    tokenizer, model = _load_model_and_tokenizer()
    prompt = _regen_prompt_for(code_snippet, func_name, previous_test)

    enc = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
        return_attention_mask=True,
    ).to(DEVICE)

    with torch.inference_mode():
        outs = model.generate(
            enc["input_ids"],
            attention_mask=enc["attention_mask"],
            max_new_tokens=max_new_tokens,
            min_length=0,
            no_repeat_ngram_size=0,
            early_stopping=True,
            do_sample=True,
            temperature=max(0.1, float(temperature)),
            top_k=max(0, int(top_k)),
            num_beams=1,
            num_return_sequences=max(1, int(sample_candidates)),
        )

    norm_prev = _normalize_test_for_similarity(previous_test)

    best_candidate: str | None = None
    rejections = []

    for i in range(outs.shape[0]):
        raw_candidate = _decode_and_clean(
            tokenizer,
            outs[i],
            func_name,
            func_src=code_snippet,
        )
        candidate = _strip_non_target_asserts(raw_candidate, func_name)

        if _VALIDATOR_DEBUG:
            print("\n[regen] ---------- CANDIDATE BEGIN ----------")
            print(candidate)
            print("[regen] ----------- CANDIDATE END -----------")

        # --- Fast syntax guard ---
        try:
            ast.parse(candidate)
        except SyntaxError:
            if _VALIDATOR_DEBUG:
                print("[regen] REJECT (pre): syntax")
            rejections.append((candidate, "syntax"))
            continue

        # --- Similarity check vs previous test ---
        norm_cand = _normalize_test_for_similarity(candidate)
        if _too_similar(norm_prev, norm_cand):
            if _VALIDATOR_DEBUG:
                print("[regen] REJECT: too similar (text)")
            rejections.append((candidate, "too similar (text)"))
            continue

        # Extra: compare literal call argument patterns if possible
        prev_calls = _extract_calls_in_test(previous_test, func_name)
        cand_calls = _extract_calls_in_test(candidate, func_name)
        if prev_calls and cand_calls:
            # sort for deterministic comparison
            prev_set = sorted(prev_calls)
            cand_set = sorted(cand_calls)
            if prev_set == cand_set:
                if _VALIDATOR_DEBUG:
                    print("[regen] REJECT: same call argument patterns")
                rejections.append((candidate, "same call args"))
                continue

        # --- Structural checks (reuse normal validator logic) ---
        def _first_reject_reason(test_src: str):
            n = _count_asserts(test_src)
            if n < 1 or n > 12:
                return f"bad assert count={n}"
            if not _calls_target(test_src, func_name):
                return "does not call target"
            if not _asserts_focus_on_target(test_src, func_name, min_ratio=1.0):
                return "an assert does not reference target"
            if _has_foreign_calls(test_src, func_name):
                return "foreign user-level calls"
            return None

        reason = _first_reject_reason(candidate)
        if reason is not None:
            if _VALIDATOR_DEBUG:
                print(f"[regen] REJECT (pre): {reason}")
            rejections.append((candidate, reason))
            continue

        ok = _run_test_safely(code_snippet, candidate, func_name=func_name)
        if ok:
            best_candidate = candidate
            break
        else:
            if _VALIDATOR_DEBUG:
                print("[regen] REJECT (run): failed in exec/semantic/oracle")
            rejections.append((candidate, "exec/semantic/oracle"))

    if best_candidate is not None:
        return "# Origin: Regen (sampling)\n" + best_candidate

    # If everything failed, as a last resort just return the previous test
    # (or you could fall back to _generate_for_single_function)
    if _VALIDATOR_DEBUG and rejections:
        print("\n[regen] SUMMARY: all regen candidates rejected.")
        for idx, (_cand, why) in enumerate(rejections, 1):
            print(f"[regen]  {idx:02d}. reason: {why}")

    return "# Origin: Regen (fallback – reused previous)\n" + previous_test

# -----------------------------
# Back-compat wrapper (kept for convenience)
# -----------------------------


def generate_test_from_code_validated(
    code_snippet: str,
    *,
    num_beams: int = 4,
    max_new_tokens: int = 140,
) -> str:
    """Calls the same validated generator; retained for back-compat."""
    return generate_test_from_code(
        code_snippet,
        num_beams=num_beams,
        max_new_tokens=max_new_tokens,
    )


# -----------------------------
# CLI quick-check
# -----------------------------
if __name__ == "__main__":
    sample = "def divide(a, b): return a / b if b else None"
    print(generate_test_from_code(sample))
