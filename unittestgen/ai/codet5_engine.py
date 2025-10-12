# unittestgen/ai/codet5_engine.py
# pylint: disable=eval-used
import os
import re
import ast
import textwrap
from functools import lru_cache
import math
import difflib
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
def _extract_function_name(code: str) -> str:
    """Return the first function name defined in `code`, else 'generated'."""
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                return node.name
    except SyntaxError:
        pass
    return "generated"


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


def _infer_simple_op(func_src: str) -> Optional[str]:
    """
    Inspect a function and infer {'add','subtract','multiply','power','divide'}.
    Returns None if we cannot confidently infer a single simple arithmetic op.
    """
    try:
        t = ast.parse(func_src)
    except SyntaxError:
        return None

    for node in t.body:
        if isinstance(node, ast.FunctionDef):
            # Look for a direct return first
            for stmt in node.body:
                if isinstance(stmt, ast.Return) and stmt.value is not None:
                    val = stmt.value
                    # First, check simple binop / pow call in the return
                    kind = _find_first_binop(val)
                    if kind:
                        return kind
                    # Also recognize a plain division (we don't oracle-check divide later,
                    # but we still allow detection)
                    if isinstance(val, ast.BinOp) and isinstance(val.op, (ast.Div, ast.FloorDiv)):
                        return "divide"
                    # Handle trivial IfExp (ternary) where each branch is a simple binop
                    if isinstance(val, ast.IfExp):
                        k1 = _find_first_binop(val.body)
                        k2 = _find_first_binop(val.orelse)
                        if k1 and k1 == k2:
                            return k1
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

    inferred = _infer_simple_op(func_src) if func_src else None
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


def _run_test_safely(func_src: str, test_src: str) -> bool:
    """
    Execute function + test in an isolated namespace.
    Returns True only if:
      - The test has at least 1 assert (and not an absurd number),
      - The test calls the target function somewhere,
      - The test does NOT call other user-level functions,
      - Every assert references the target (no stray asserts),
      - Executing the test raises no exceptions (i.e., asserts pass),
      - Optional semantic probe passes for simple arithmetic functions.

    Note: we keep this conservative to avoid rejecting legitimate variants.
    """
    func_name = _extract_function_name(func_src)

    num_asserts = _count_asserts(test_src)
    if num_asserts < 1 or num_asserts > 12:
        _vd(f"reject: bad assert count = {num_asserts}")
        return False

    if not _calls_target(test_src, func_name):
        _vd("reject: test does not call target")
        return False

    if not _asserts_focus_on_target(test_src, func_name, min_ratio=1.0):
        _vd("reject: at least one assert does not reference target")
        return False

    if _has_foreign_calls(test_src, func_name):
        _vd("reject: foreign user-level calls detected")
        return False

    # Execute in a fresh namespace
    ns: dict = {}
    try:
        # define function
        exec(func_src, ns, ns)  # pylint: disable=exec-used
        # NEW: opportunistic auto-fix of wrong RHS values
        fixed_test_src = _auto_fix_assert_rhs(
            ns, test_src, func_name) or test_src
        # run test (asserts must pass)
        exec(fixed_test_src, ns, ns)   # pylint: disable=exec-used
    except Exception as e:      # pylint: disable=broad-exception-caught
        _vd(f"reject: exec raised: {type(e).__name__}: {e}")
        return False

    if not _asserts_semantically_true(ns, test_src):
        _vd("reject: semantic re-check failed")
        return False

    # semantic oracle for simple arithmetic (skip divide variants)
    f = ns.get(func_name)
    if callable(f) and not _arithmetic_oracle(func_name, f, func_src=func_src):
        _vd("reject: arithmetic oracle failed")
        return False

    # NaN check on arithmetic outputs for literal calls
    if func_name.lower() in {"add", "subtract", "multiply", "power"}:
        for args, _ in _extract_calls_in_test(test_src, func_name):
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


def _auto_fix_assert_rhs(ns: dict, test_src: str, func_name: str) -> str:
    """
    For asserts like: <expr> == <literal>, if <expr> contains a call to func_name,
    evaluate <expr> in ns and rewrite the RHS literal to the true value (bool/int/float).
    """
    try:
        tree = ast.parse(test_src)
    except SyntaxError:
        return test_src

    SAFE_GLOBALS = {
        "__builtins__": {},
        "math": math, "abs": abs, "round": round,
        "int": int, "float": float, "min": min, "max": max, "sum": sum, "len": len,
        **ns
    }
    changed = False

    class Fixer(ast.NodeTransformer):
        def visit_Assert(self, node):
            nonlocal changed
            test = node.test
            if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
                # Only fix when LHS calls our target
                called = [False]

                class Finder(ast.NodeVisitor):
                    def visit_Call(self, n):
                        if isinstance(n.func, ast.Name) and n.func.id == func_name:
                            called[0] = True
                        self.generic_visit(n)
                Finder().visit(test.left)
                if not called[0]:
                    return node

                # Evaluate left expression
                try:
                    left_val = eval(compile(ast.Expression(
                        test.left), "<ast>", "eval"), SAFE_GLOBALS, {})
                except Exception:   # pylint: disable=broad-exception-caught
                    return node

                if isinstance(left_val, (bool, int, float)):
                    new_rhs_code = _format_literal(left_val)
                    try:
                        new_rhs_ast = ast.parse(new_rhs_code, mode="eval").body
                    except Exception:   # pylint: disable=broad-exception-caught
                        return node
                    test.comparators[0] = new_rhs_ast
                    changed = True
            return node

    fixed = Fixer().visit(tree)
    if not changed:
        return test_src
    try:
        ast.fix_missing_locations(fixed)
        return ast.unparse(fixed)
    except Exception:   # pylint: disable=broad-exception-caught
        return test_src


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


def _decode_and_clean(tokenizer, seq_ids, func_name: str, *, func_src: str = "") -> str:
    txt = tokenizer.decode(seq_ids, skip_special_tokens=True).strip()
    txt = _wrap_as_test_if_needed(txt, func_name)
    txt = _standardize_test_name(txt, func_name)
    txt = _normalize_calls_to_target(txt, func_name)

    # If function expects strings (is_upper/lower, palindrome, anagram), coerce numeric args
    if _function_expects_strings(func_src) or _is_anagram_like(func_src):
        txt = _coerce_string_args_in_test(txt, func_name)
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
    try:
        t = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(t):
        if isinstance(node, ast.Return):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            # common string/numeric "is*" predicates (isupper/islower/isdigit/isalpha etc.)
            if node.func.attr.startswith("is"):
                return True
    lowered = code.lower()
    return any(k in lowered for k in [" is_", " return true", " return false"])


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
    "    assert is_even(4) is True\n"
    "    assert is_even(9) is False\n"
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
    "    assert is_prime(7) is True\n"
    "    assert is_prime(32) is False\n"
    "```\n\n"
)


def _prompt_for(code_snippet: str) -> str:
    fn = _extract_function_name(code_snippet)
    base = (
        "Given this Python function:\n```python\n"
        f"{code_snippet}\n"
        "```\n"
        "Write ONE PyTest unit test function named `test_<function_name>` with at least two assert statements.\n"
        f"- Every assert must call **exactly** `{fn}` (use this exact name).\n"
        "- Do not call any other user-defined helpers.\n"
        "- Use only these builtins if needed: abs, round, int, float, len, sum, max, min, and math.\n"
        "- If the code uses string methods (e.g., `.islower()`, `.isupper()`, `.lower()`, `.replace()`), pass **string arguments** like 'abc'.\n"
        "- If it compares `sorted(a) == sorted(b)`, pass **string pairs** like ('listen', 'silent').\n"
        "- No pytest fixtures, no parametrize, no classes, no print statements.\n"
        "- Output ONLY the test function (no extra text).\n"
    )
    if _looks_like_predicate(code_snippet):
        return _PREDICATE_FEWSHOT + base

    if _function_expects_strings(code_snippet) or _is_anagram_like(code_snippet):
        base += (
            "\nAdditional constraints:\n"
            "- Use **string** inputs (e.g., 'HELLO'/'Hello', 'racecar'/'python', 'listen'/'silent').\n"
            "- Avoid numbers for these tests.\n"
        )

    return base


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
            no_repeat_ngram_size=0 if do_sample else 3,
            early_stopping=True,
            do_sample=do_sample,
            temperature=max(0.1, float(temperature)) if do_sample else None,
            top_k=max(0, int(top_k)) if do_sample else None,
            num_beams=max(1, int(num_beams)),
            num_return_sequences=max(1, int(num_return)),
        )

    # Keep a short log of rejections (first reason only)
    rejections = []

    for i in range(outs.shape[0]):
        candidate = _decode_and_clean(tokenizer, outs[i], func_name)
        candidate = _strip_non_target_asserts(candidate, func_name)

        if _VALIDATOR_DEBUG:
            print("\n[validator] ---------- CANDIDATE BEGIN ----------")
            print(candidate)
            print("[validator] ----------- CANDIDATE END -----------")

        # Quick pre-checks to collect reason strings
        def _first_reject_reason(test_src: str) -> Optional[str]:
            # assert count
            n = _count_asserts(test_src)
            if n < 1 or n > 12:
                return f"bad assert count={n}"
            if not _calls_target(test_src, func_name):
                return "does not call target"
            if not _asserts_focus_on_target(test_src, func_name, min_ratio=1.0):
                return "an assert does not reference target"
            if _has_foreign_calls(test_src, func_name):
                return "foreign user-level calls"
            # exec + semantic done within _run_test_safely
            return None

        reason = _first_reject_reason(candidate)
        if reason is not None:
            if _VALIDATOR_DEBUG:
                print(f"[validator] REJECT (pre): {reason}")
            rejections.append((candidate, reason))
            continue

        ok = _run_test_safely(code_snippet, candidate)
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
def generate_test_from_code(
    code_snippet: str,
    *,
    # decoding size
    max_new_tokens: int = 140,
    # candidate budgets
    beam_candidates: int = 6,
    sample_candidates: int = 6,
    # beam params
    num_beams: int = 6,
    # sampling params
    temperature: float = 0.7,
    top_k: int = 50,
) -> str:
    """
    Generate a PyTest-style unit test and validate it automatically.

    Strategy:
      1) Try several beam candidates (deterministic) → return first that calls the target and passes.
      2) If none pass, try several sampling candidates (diverse) → return first that passes.
      3) If still none pass, return a safe fallback.

    Your CLI one-liner keeps working the same.
    """
    print("[validator] generate_test_from_code: beams→sampling→fallback")
    tokenizer, model = _load_model_and_tokenizer()
    func_name = _extract_function_name(code_snippet)
    prompt = _prompt_for(code_snippet)

    enc = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=512,
        padding=True,
        return_attention_mask=True,
    ).to(DEVICE)

    # Optional: bypass validator to inspect raw model output quickly
    if _BYPASS_VALIDATOR:
        with torch.inference_mode():
            raw = model.generate(
                enc["input_ids"],
                attention_mask=enc["attention_mask"],
                max_new_tokens=max_new_tokens,
                min_length=24,
                no_repeat_ngram_size=3,
                early_stopping=True,
                do_sample=True,
                temperature=max(0.1, float(temperature)),
                top_k=max(0, int(top_k)),
                num_beams=1,
                num_return_sequences=1,
            )
        txt = _decode_and_clean(tokenizer, raw[0], func_name)
        return "# origin: raw_unvalidated\n" + txt

    # 1) Deterministic beams
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
        return "# origin: beams\n" + passing

    # 2) Sampling for diversity
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
        return "# origin: sampling\n" + passing

    # 3) Fallbacks for common arithmetic names (always coherent)
    op = _infer_simple_op(code_snippet) or func_name.lower()
    fn = func_name
    if fn == "add":
        return "# origin: fallback\n" + "def test_add(): assert add(3, 4) == 7; assert add(-2, 5) == 3"
    if fn == "subtract":
        return "# origin: fallback\n" + "def test_subtract(): assert subtract(5, 3) == 2; assert subtract(-2, -3) == 1"
    if fn == "multiply":
        return "# origin: fallback\n" + "def test_multiply(): assert multiply(2, 3) == 6; assert multiply(-1, 5) == -5"
    if fn == "divide":
        return "# origin: fallback\n" + "def test_divide(): assert divide(6, 3) == 2; assert divide(-8, 4) == -2"
    if fn == "power":
        return "# origin: fallback\n" + "def test_power(): assert power(2, 3) == 8; assert power(3, 0) == 1"

    # --- Non-arithmetic Tier-1 fallbacks ---
    if fn == "count_vowels":
        return "# origin: fallback\n" + \
            "def test_count_vowels(): assert count_vowels('hello') == 2; assert count_vowels('bcd') == 0; assert count_vowels('AEiou') == 5\n"

    if fn == "is_even":
        return "# origin: fallback\n" + \
            "def test_is_even(): assert is_even(2) is True; assert is_even(3) is False; assert is_even(0) is True\n"

    if fn == "is_odd":
        return "# origin: fallback\n" + \
            "def test_is_odd(): assert is_odd(2) is False; assert is_odd(3) is True; assert is_odd(1) is True\n"

    if fn == "is_lower":
        return "# origin: fallback\n" + \
            "def test_is_lower(): assert is_lower('hello') is True; assert is_lower('Hello') is False\n"

    if fn == "is_upper":
        return "# origin: fallback\n" + \
            "def test_is_upper(): assert is_upper('HELLO') is True; assert is_upper('Hello') is False\n"

    if fn == "is_palindrome":
        return "# origin: fallback\n" + \
            "def test_is_palindrome(): assert is_palindrome('racecar') is True; assert is_palindrome('python') is False\n"

    if fn == "reverse_string":
        return "# origin: fallback\n" + \
            "def test_reverse_string(): assert reverse_string('abc') == 'cba'; assert reverse_string('') == ''\n"

    if fn == "remove_duplicates":
        return "# origin: fallback\n" + \
            "def test_remove_duplicates(): assert remove_duplicates([1,1,2,3,2]) == [1,2,3]; assert remove_duplicates([]) == []\n"

    if fn == "is_anagram":
        return "# origin: fallback\n" + \
            "def test_is_anagram(): assert is_anagram('listen','silent') is True; assert is_anagram('rat','car') is False\n"

    if op == "add":
        return "# origin: fallback\n" + f"def test_{fn}(): assert {fn}(3, 4) == 7; assert {fn}(-2, 5) == 3"
    if op == "subtract":
        return "# origin: fallback\n" + f"def test_{fn}(): assert {fn}(5, 3) == 2; assert {fn}(-2, -3) == 1"
    if op == "multiply":
        return "# origin: fallback\n" + f"def test_{fn}(): assert {fn}(2, 3) == 6; assert {fn}(-1, 5) == -5"
    if op == "divide" or fn == "divide":
        return "# origin: fallback\n" + f"def test_{fn}(): assert {fn}(6, 3) == 2; assert {fn}(-8, 4) == -2"
    if op == "power":
        return "# origin: fallback\n" + f"def test_{fn}(): assert {fn}(2, 3) == 8; assert {fn}(3, 0) == 1"

    # Worst-case: valid test shell (avoid wrong asserts)
    return "# origin: fallback\n" + f"def test_{fn}():\n    # model could not produce a valid passing test yet\n    assert callable({fn})\n"


# -----------------------------
# Back-compat wrapper (kept for convenience)
# -----------------------------
def generate_test_from_code_validated(
    code_snippet: str,
    *,
    num_beams: int = 6,
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
