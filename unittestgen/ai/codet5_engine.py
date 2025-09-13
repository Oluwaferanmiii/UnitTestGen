# unittestgen/ai/codet5_engine.py
import os
import re
import ast
import textwrap
from functools import lru_cache
import math
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


def _asserts_semantically_true(ns: dict, test_src: str) -> bool:
    """
    Re-validate every `assert ...` in the generated test using the already-executed
    namespace `ns`. Handles `==` / `!=` with float tolerance; falls back to truthiness.
    """
    try:
        tree = ast.parse(test_src)
    except SyntaxError:
        return False

    def _eval(node):
        # Evaluate an AST node with the user namespace but *no* builtins.
        code = compile(ast.Expression(node), "<ast>", "eval")
        return eval(code, {"__builtins__": {}}, ns)     # pylint: disable=eval-used

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        test = node.test

        # Compare: left == right / left != right (single comparator only)
        if isinstance(test, ast.Compare) and len(test.ops) == 1 and len(test.comparators) == 1:
            op = test.ops[0]
            left_node = test.left
            right_node = test.comparators[0]
            try:
                left = _eval(left_node)
                right = _eval(right_node)
            except Exception:   # pylint: disable=broad-exception-caught
                return False

            # numeric-friendly equality with tolerance
            if isinstance(op, ast.Eq):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if not math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9):
                        return False
                else:
                    if left != right:
                        return False
            elif isinstance(op, ast.NotEq):
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9):
                        return False
                else:
                    if left == right:
                        return False
            else:
                # other comparison ops: rely on the prior exec() pass
                pass
        else:
            # Non-compare asserts → assert bool(expr) is True
            try:
                ok = bool(_eval(test))
            except Exception:   # pylint: disable=broad-exception-caught
                return False
            if not ok:
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
        except Exception:  # pylint: disable=broad-exception-caught
            return False
        if not _isclose(got, expected):
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
    allow_names = {"round", "abs", "int", "float", "len", "sum", "max", "min"}
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


def _run_test_safely(func_src: str, test_src: str) -> bool:
    """
    Execute function + test in an isolated namespace.
    Returns True only if:
      - The test has at least 1 assert (and not an absurd number),
      - The test calls the target function somewhere,
      - The test does NOT call other user-level functions,
      - Executing the test raises no exceptions (i.e., asserts pass),
      - Optional semantic probe passes for simple arithmetic functions.

    Note: we keep this conservative to avoid rejecting legitimate variants.
    """
    # Identify target function name from the function source
    func_name = _extract_function_name(func_src)

    # Sanity: at least one assert, but not, say, 100 in one line
    num_asserts = _count_asserts(test_src)
    if num_asserts < 1 or num_asserts > 12:
        return False

    if not _calls_target(test_src, func_name):
        return False

    # NEW: reject tests that call any non-target user function
    if _has_foreign_calls(test_src, func_name):
        return False

    # Execute in a fresh namespace
    ns: dict = {}
    try:
        # define the function
        exec(func_src, ns, ns)  # pylint: disable=exec-used
        # run the test (asserts must pass)
        exec(test_src, ns, ns)  # pylint: disable=exec-used
    except Exception:       # pylint: disable=broad-exception-caught
        return False

    # Optional: semantic probe for simple arithmetic (skip divide variants)
    f = ns.get(func_name)
    if callable(f) and not _arithmetic_oracle(func_name, f, func_src=func_src):
        return False

    if not _asserts_semantically_true(ns, test_src):
        return False

    # Optional: sanity – if the test called the function with simple literal args,
    # recompute expected via the test's own asserts implicitly (already done by exec),
    # but we can also ensure outputs are not NaN for add/sub/mul/power cases.
    if func_name.lower() in {"add", "subtract", "multiply", "power"}:
        for args, _ in _extract_calls_in_test(test_src, func_name):
            try:
                out = f(*args)
            except Exception:       # pylint: disable=broad-exception-caught
                return False
            if isinstance(out, float) and math.isnan(out):
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
    parts = function_name.split("_")
    if len(parts) < 2:
        return test_src  # nothing to normalize

    prefix = parts[0]
    if prefix and prefix != function_name:
        pattern = rf"\b{re.escape(prefix)}\s*\("
        replacement = f"{function_name}("
        test_src = re.sub(pattern, replacement, test_src)

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


def _decode_and_clean(tokenizer, seq_ids, func_name: str) -> str:
    """Decode one sequence, ensure it's a test def, and standardize the name."""
    txt = tokenizer.decode(seq_ids, skip_special_tokens=True).strip()
    txt = _wrap_as_test_if_needed(txt, func_name)
    txt = _standardize_test_name(txt, func_name)
    txt = _normalize_calls_to_target(txt, func_name)
    return txt


def _prompt_for(code_snippet: str) -> str:
    return (
        "Given this Python function:\n```python\n"
        f"{code_snippet}\n"
        "```, write a PyTest unit test function in Python with at least one assert statement to verify its behavior."
    )


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
    """Generate `num_return` candidates with specified strategy and return the first passing one, else None."""
    with torch.inference_mode():
        outs = model.generate(
            enc_inputs["input_ids"],
            attention_mask=enc_inputs["attention_mask"],
            max_new_tokens=max_new_tokens,
            min_length=24,
            no_repeat_ngram_size=3,
            early_stopping=True,
            do_sample=do_sample,
            temperature=max(0.1, float(temperature)) if do_sample else None,
            top_k=max(0, int(top_k)) if do_sample else None,
            num_beams=max(1, int(num_beams)),
            num_return_sequences=max(1, int(num_return)),
        )

    for i in range(outs.shape[0]):
        candidate = _decode_and_clean(tokenizer, outs[i], func_name)
        # Must call the target *and* pass its asserts & validation
        if _calls_target(candidate, func_name) and _run_test_safely(code_snippet, candidate):
            return candidate
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
        return passing

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
        return passing

    # 3) Fallbacks for common arithmetic names (always coherent)
    op = _infer_simple_op(code_snippet) or func_name.lower()
    fn = func_name
    if fn == "add":
        return "def test_add(): assert add(3, 4) == 7; assert add(-2, 5) == 3"
    if fn == "subtract":
        return "def test_subtract(): assert subtract(5, 3) == 2; assert subtract(-2, -3) == 1"
    if fn == "multiply":
        return "def test_multiply(): assert multiply(2, 3) == 6; assert multiply(-1, 5) == -5"
    if fn == "divide":
        return "def test_divide(): assert divide(6, 3) == 2; assert divide(-8, 4) == -2"
    if fn == "power":
        return "def test_power(): assert power(2, 3) == 8; assert power(3, 0) == 1"

    if op == "add":
        return f"def test_{fn}(): assert {fn}(3, 4) == 7; assert {fn}(-2, 5) == 3"
    if op == "subtract":
        return f"def test_{fn}(): assert {fn}(5, 3) == 2; assert {fn}(-2, -3) == 1"
    if op == "multiply":
        return f"def test_{fn}(): assert {fn}(2, 3) == 6; assert {fn}(-1, 5) == -5"
    # still keep divide simple (too many variants in your dataset)
    if op == "divide" or fn == "divide":
        return f"def test_{fn}(): assert {fn}(6, 3) == 2; assert {fn}(-8, 4) == -2"
    if op == "power":
        return f"def test_{fn}(): assert {fn}(2, 3) == 8; assert {fn}(3, 0) == 1"

    # Worst-case: valid test shell (avoid wrong asserts)
    return f"def test_{fn}():\n    # model could not produce a valid passing test yet\n    assert callable({fn})\n"


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
