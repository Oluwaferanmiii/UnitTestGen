# THESIS/unittestgen/management/tools/generate_edge_dataset.py
"""
Build / update the *edge-case* training dataset.

- Reads / appends to `dataset.edge.jsonl`
- Validates that both function & test are valid Python
- Does exact pair-level dedupe (and optional per-input caps)
- Writes:
    - dataset.edge.jsonl                (raw but deduped)
    - dataset.edge.rejected.gen.jsonl   (rejected at generation stage)
- Then calls `audit_edge_dataset.main()` to produce:
    - dataset.edge.cleaned.jsonl
    - dataset.edge.rejected.audit.jsonl
    - dataset.edge.rejected.jsonl       (merged view of all rejects)
"""
import ast
import json
import os
from collections import defaultdict

# ----------------------------
# Config (edge-specific paths)
# ----------------------------
DATASET_FILE = "dataset.edge.jsonl"
REJECTED_FILE = "dataset.edge.rejected.gen.jsonl"

# To limit how many test variants one input function can have:
PER_INPUT_CAP = None  # None == no cap

# ----------------------------
# Edge-case seeds
# ----------------------------
# IMPORTANT:
# - `edge_functions[i]` pairs with `edge_tests[i]`
# - Keep them 1:1 and same length
# - These should be *edge-focused* tests, not the “normal” ones used for the base model.

edge_functions = [
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def add(a,b): return a+b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def subtract(a, b): return a - b",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def rotate_right(s):\n    return s[-1:] + s[:-1]",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
    "def divide(a, b): return a / b if b != 0 else 0",
]

edge_tests = [
    "def test_add():\n"
    "    assert add(0, 0) == 0\n"
    "    assert add(-1, 1) == 0\n"
    "    assert add(1, -1) == 0",

    "def test_add():\n"
    "    assert add(10**12, 1) == 10**12 + 1\n"
    "    assert add(-10**12, -1) == -(10**12 + 1)\n"
    "    assert add(10**12, -10**12) == 0",

    "def test_add():\n"
    "    assert add(1e308, 1e308) == float('inf')\n"
    "    assert add(-1e308, -1e308) == -float('inf')\n"
    "    assert add(1e308, -1e308) == 0.0",

    "def test_add():\n"
    "    assert add(0.1, 0.2) == 0.30000000000000004\n"
    "    assert add(-0.5, 0.5) == 0.0\n"
    "    assert add(1.5, -1.5) == 0.0",

    "def test_add():\n"
    "    assert add(True, True) == 2\n"
    "    assert add(True, False) == 1\n"
    "    assert add(False, False) == 0",

    "def test_add():\n"
    "    assert add('', '') == ''\n"
    "    assert add('', 'abc') == 'abc'\n"
    "    assert add('abc', '') == 'abc'",

    "def test_add():\n"
    "    assert add('🔥', '🔥') == '🔥🔥'\n"
    "    assert add('🙂', '🙃') == '🙂🙃'\n"
    "    assert add('á', 'é') == 'áé'",

    "def test_add():\n"
    "    assert add([], []) == []\n"
    "    assert add([1], []) == [1]\n"
    "    assert add([], [1, 2, 3]) == [1, 2, 3]",

    "def test_add():\n"
    "    assert add([1], [2]) == [1, 2]\n"
    "    assert add([[], []], [1]) == [[], [], 1]\n"
    "    assert add([0], [[]]) == [0, []]",

    "def test_add():\n"
    "    assert add((), ()) == ()\n"
    "    assert add((1,), (2,)) == (1, 2)\n"
    "    assert add((), (3, 4)) == (3, 4)",

    "def test_add():\n"
    "    assert add((-1,), (-2,)) == (-1, -2)\n"
    "    assert add((), (1,)) == (1,)\n"
    "    assert add((0,), ()) == (0,)",

    "def test_add():\n"
    "    assert add(0.0, -0.0) == 0.0\n"
    "    assert add(-0.0, -0.0) == 0.0\n"
    "    assert add(0, -0) == 0",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add('1', 2)\n"
    "    with pytest.raises(TypeError):\n"
    "        add(2, '1')",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add([1, 2], (3, 4))\n"
    "    with pytest.raises(TypeError):\n"
    "        add((1, 2), [3, 4])",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add({'a': 1}, {'b': 2})\n"
    "    with pytest.raises(TypeError):\n"
    "        add({'x': 1}, {})",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add(None, 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        add(1, None)\n"
    "    with pytest.raises(TypeError):\n"
    "        add(None, None)",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add('abc', ['d'])\n"
    "    with pytest.raises(TypeError):\n"
    "        add({'k': 'v'}, ['list'])",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add({'k': 'v'}, ('tuple',))\n"
    "    with pytest.raises(TypeError):\n"
    "        add({1, 2}, {3, 4})",

    "def test_add():\n"
    "    large_list = list(range(1000))\n"
    "    result = add(large_list, [])\n"
    "    assert len(result) == 1000\n"
    "    assert result[0] == 0\n"
    "    assert result[-1] == 999",

    "def test_add():\n"
    "    large_list = list(range(500))\n"
    "    result = add([], large_list)\n"
    "    assert len(result) == 500\n"
    "    assert result[0] == 0\n"
    "    assert result[-1] == 499",

    "def test_add():\n"
    "    assert add(1e-12, 1e-12) == 2e-12\n"
    "    assert add(-1e-12, 1e-12) == 0.0\n"
    "    assert add(3.14, -3.14) == 0.0",

    "def test_add():\n"
    "    assert add(1 + 2j, 3 + 4j) == 4 + 6j\n"
    "    assert add(1 + 0j, 0) == 1 + 0j\n"
    "    assert add(0, 1 + 0j) == 1 + 0j",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add('bytes', b'bytes')\n"
    "    with pytest.raises(TypeError):\n"
    "        add(b'bytes', 'bytes')",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add(object(), 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        add(1, object())",

    "def test_add():\n"
    "    with pytest.raises(TypeError):\n"
    "        add(add, 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        add(1, add)",

    "def test_subtract():\n"
    "    assert subtract(0, 0) == 0\n"
    "    assert subtract(-1, 0) == -1\n"
    "    assert subtract(0, -1) == 1",

    "def test_subtract():\n"
    "    assert subtract(10**12, 10**12) == 0\n"
    "    assert subtract(10**12, -10**12) == 2 * 10**12\n"
    "    assert subtract(-10**12, 10**12) == -2 * 10**12",

    "def test_subtract():\n"
    "    assert subtract(1e308, 1e308) == 0.0\n"
    "    assert subtract(1e308, -1e308) == float('inf')\n"
    "    assert subtract(-1e308, 1e308) == -float('inf')",

    "def test_subtract():\n"
    "    assert subtract(1e-12, 1e-12) == 0.0\n"
    "    assert subtract(-1e-12, 1e-12) == -2e-12\n"
    "    assert subtract(1e-12, -1e-12) == 2e-12",

    "def test_subtract():\n"
    "    assert subtract(0.1, 0.2) == -0.1\n"
    "    assert subtract(-0.5, -0.25) == -0.25\n"
    "    assert subtract(1.5, -1.5) == 3.0",

    "def test_subtract():\n"
    "    assert subtract(True, True) == 0\n"
    "    assert subtract(True, False) == 1\n"
    "    assert subtract(False, True) == -1",

    "def test_subtract():\n"
    "    assert subtract(0, True) == -1\n"
    "    assert subtract(True, 0) == 1\n"
    "    assert subtract(False, False) == 0",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract('abc', 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(1, 'abc')",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract([], {})\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract({}, [])",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract('🔥', '🔥')\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract('🙂', '🙃')",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract([1, 2, 3], [1])\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract([], [1])",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract((1,), (1,))\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract((), (1,))",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract({'a': 1}, {'b': 2})\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract({'x': 1}, {})",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(None, 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(1, None)",

    "def test_subtract():\n"
    "    large_list = list(range(500))\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(large_list, [])",

    "def test_subtract():\n"
    "    tiny = [1e-12] * 3\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(tiny, tiny)",

    "def test_subtract():\n"
    "    assert subtract(0.0, -0.0) == 0.0\n"
    "    assert subtract(-0.0, 0.0) == -0.0\n"
    "    assert subtract(-0.0, -0.0) == 0.0",

    "def test_subtract():\n"
    "    assert subtract(2**63 - 1, 0) == 2**63 - 1\n"
    "    assert subtract(-(2**63 - 1), 0) == -(2**63 - 1)\n"
    "    assert subtract(2**63 - 1, -(2**63 - 1)) == 2 * (2**63 - 1)",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract({'k': 'v'}, ['list'])\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(['list'], {'k': 'v'})",

    "def test_subtract():\n"
    "    assert subtract(3.14, 3.14) == 0.0\n"
    "    assert subtract(3.14, 0.0) == 3.14\n"
    "    assert subtract(0.0, 3.14) == -3.14",

    "def test_subtract():\n"
    "    assert subtract(-3.14, -3.14) == 0.0\n"
    "    assert subtract(-3.14, 3.14) == -6.28\n"
    "    assert subtract(3.14, -3.14) == 6.28",

    "def test_subtract():\n"
    "    assert subtract(1e5, 1e5 - 1) == 1.0\n"
    "    assert subtract(1e5 - 1, 1e5) == -1.0\n"
    "    assert subtract(-1e5, 1e5 - 1) == -2e5 + 1",

    "def test_subtract():\n"
    "    assert subtract(1 + 2j, 3 + 4j) == (-2 - 2j)\n"
    "    assert subtract(1 + 0j, 0) == 1 + 0j\n"
    "    assert subtract(0, 1 + 0j) == -1 - 0j",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(b'bytes', 'str')\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract('str', b'bytes')",

    "def test_subtract():\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(object(), 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        subtract(1, object())",

    "def test_rotate_right():\n"
    "    assert rotate_right('') == ''\n"
    "    assert rotate_right('a') == 'a'\n"
    "    assert rotate_right('aa') == 'aa'",

    "def test_rotate_right():\n"
    "    assert rotate_right('ab') == 'ba'\n"
    "    assert rotate_right('abc') == 'cab'\n"
    "    assert rotate_right('abcd') == 'dabc'",

    "def test_rotate_right():\n"
    "    assert rotate_right('aaa') == 'aaa'\n"
    "    assert rotate_right('bbbb') == 'bbbb'\n"
    "    assert rotate_right('aba') == 'aab'",

    "def test_rotate_right():\n"
    "    assert rotate_right('   ') == '   '\n"
    "    assert rotate_right(' a ') == ' a '\n"
    "    assert rotate_right('  a') == 'a  '",

    "def test_rotate_right():\n"
    "    assert rotate_right('a b') == 'b a'\n"
    "    assert rotate_right(' hi') == 'ihi'\n"
    "    assert rotate_right('hi ') == ' hi'",

    "def test_rotate_right():\n"
    "    assert rotate_right('café') == 'écaf'\n"
    "    assert rotate_right(' Café') == 'é Caf'\n"
    "    assert rotate_right('ño') == 'oñ'",

    "def test_rotate_right():\n"
    "    assert rotate_right('😊a') == 'a😊'\n"
    "    assert rotate_right('a😊') == '😊a'\n"
    "    assert rotate_right('😊😊') == '😊😊'",

    "def test_rotate_right():\n"
    "    assert rotate_right('😊😊a') == 'a😊😊'\n"
    "    assert rotate_right('a😊😊') == '😊a😊'\n"
    "    assert rotate_right('😊a😊') == '😊😊a'",

    "def test_rotate_right():\n"
    "    assert rotate_right('日本語') == '語日本'\n"
    "    assert rotate_right('語日') == '日語'\n"
    "    assert rotate_right('語') == '語'",

    "def test_rotate_right():\n"
    "    assert rotate_right('0') == '0'\n"
    "    assert rotate_right('01') == '10'\n"
    "    assert rotate_right('010') == '001'",

    "def test_rotate_right():\n"
    "    assert rotate_right('0a0') == '00a'\n"
    "    assert rotate_right('a0a') == 'aa0'\n"
    "    assert rotate_right('00a') == 'a00'",

    "def test_rotate_right():\n"
    "    assert rotate_right('123') == '312'\n"
    "    assert rotate_right('001') == '100'\n"
    "    assert rotate_right('10') == '01'",

    "def test_rotate_right():\n"
    "    assert rotate_right('!@#') == '#@!'\n"
    "    assert rotate_right('?.') == '.?'\n"
    "    assert rotate_right('---') == '---'",

    "def test_rotate_right():\n"
    "    assert rotate_right('#tag') == 'g#ta'\n"
    "    assert rotate_right('##tag') == 'g##ta'\n"
    "    assert rotate_right('tag#') == '#tag'",

    "def test_rotate_right():\n"
    "    assert rotate_right('A') == 'A'\n"
    "    assert rotate_right('Aa') == 'aA'\n"
    "    assert rotate_right('ABc') == 'cAB'",

    "def test_rotate_right():\n"
    "    assert rotate_right('mixedCASE') == 'EmixedCAS'\n"
    "    assert rotate_right('TestIng') == 'gTestIn'\n"
    "    assert rotate_right('CamelCase') == 'eCamelCas'",

    "def test_rotate_right():\n"
    "    assert rotate_right('_hidden') == 'n_hidde'\n"
    "    assert rotate_right('__x') == 'x__'\n"
    "    assert rotate_right('_') == '_'",

    "def test_rotate_right():\n"
    "    assert rotate_right('ab cd') == 'dab c'\n"
    "    assert rotate_right(' cdab') == 'b cda'\n"
    "    assert rotate_right('abcd ') == ' abcd'",

    "def test_rotate_right():\n"
    "    assert rotate_right('longstring') == 'glongstrin'\n"
    "    assert rotate_right('rotate') == 'erotat'\n"
    "    assert rotate_right('python') == 'npytho'",

    "def test_rotate_right():\n"
    "    s = 'abcabc'\n"
    "    r1 = rotate_right(s)\n"
    "    r2 = rotate_right(r1)\n"
    "    assert r1 == 'cabcab'\n"
    "    assert r2 == 'bcabca'",

    "def test_rotate_right():\n"
    "    s = 'abc'\n"
    "    t = s\n"
    "    for _ in range(len(s)):\n"
    "        t = rotate_right(t)\n"
    "    assert t == s\n"
    "    assert len(t) == len(s)",

    "def test_rotate_right():\n"
    "    s = 'a' * 1000\n"
    "    r = rotate_right(s)\n"
    "    assert len(r) == 1000\n"
    "    assert r[0] == 'a'\n"
    "    assert r[-1] == 'a'",

    "def test_rotate_right():\n"
    "    s = ' ' * 100\n"
    "    r = rotate_right(s)\n"
    "    assert r == s\n"
    "    assert len(r) == len(s)",

    "def test_rotate_right():\n"
    "    assert rotate_right('tab\\t') == '\\ttab'\n"
    "    assert rotate_right('\\ttab') == 'b\\tta'\n"
    "    assert rotate_right('a\\tb') == 'ba\\t'",

    "def test_rotate_right():\n"
    "    assert rotate_right('line\\n') == '\\nline'\n"
    "    assert rotate_right('\\nline') == 'eline\\n'\n"
    "    assert rotate_right('a\\nb') == 'ba\\n'",

    "def test_divide():\n"
    "    assert divide(0, 1) == 0\n"
    "    assert divide(0, -5) == 0\n"
    "    assert divide(1, 0) == 0",

    "def test_divide():\n"
    "    assert divide(10**12, 1) == 10**12\n"
    "    assert divide(10**12, -1) == -10**12\n"
    "    assert divide(-10**12, 1) == -10**12",

    "def test_divide():\n"
    "    assert divide(1e308, 1e308) == 1.0\n"
    "    assert divide(1e308, -1e308) == -1.0\n"
    "    assert divide(-1e308, 1e308) == -1.0",

    "def test_divide():\n"
    "    assert divide(1e308, 1e-308) == float('inf')\n"
    "    assert divide(-1e308, 1e-308) == -float('inf')\n"
    "    assert divide(1e-308, 1e308) == 0.0",

    "def test_divide():\n"
    "    assert divide(1e-12, 1) == 1e-12\n"
    "    assert divide(1, 1e-12) == 1e12\n"
    "    assert divide(-1, 1e-12) == -1e12",

    "def test_divide():\n"
    "    assert divide(0.5, 0.25) == 2.0\n"
    "    assert divide(-0.5, 0.25) == -2.0\n"
    "    assert divide(0.5, -0.25) == -2.0",

    "def test_divide():\n"
    "    assert divide(2.5, 0.5) == 5.0\n"
    "    assert divide(2.5, -0.5) == -5.0\n"
    "    assert divide(-2.5, 0.5) == -5.0",

    "def test_divide():\n"
    "    assert divide(0.0001, 0.0002) == 0.5\n"
    "    assert divide(0.0002, 0.0001) == 2.0\n"
    "    assert divide(-0.0002, 0.0001) == -2.0",

    "def test_divide():\n"
    "    assert divide(3.14159, 1) == 3.14159\n"
    "    assert divide(3.14159, 2) == 3.14159 / 2\n"
    "    assert divide(-3.14159, 2) == -3.14159 / 2",

    "def test_divide():\n"
    "    assert divide(0, 0.1) == 0\n"
    "    assert divide(0, -0.1) == 0\n"
    "    assert divide(0, 100) == 0",

    "def test_divide():\n"
    "    assert divide(999999999, 3) == 333333333\n"
    "    assert divide(3, 999999999) == 3 / 999999999\n"
    "    assert divide(-3, 999999999) == -3 / 999999999",

    "def test_divide():\n"
    "    assert divide(123456789, 1) == 123456789\n"
    "    assert divide(123456789, 9) == 13717421\n"
    "    assert divide(9, 123456789) == 9 / 123456789",

    "def test_divide():\n"
    "    assert divide(2**20, 2) == 2**19\n"
    "    assert divide(2**10, 2) == 512\n"
    "    assert divide(2**10, -2) == -512",

    "def test_divide():\n"
    "    assert divide(8, 4) == 2\n"
    "    assert divide(8, 3) == 8 / 3\n"
    "    assert divide(8, -3) == -8 / 3",

    "def test_divide():\n"
    "    assert divide(-8, 4) == -2\n"
    "    assert divide(-8, -4) == 2\n"
    "    assert divide(-8, 3) == -8 / 3",

    "def test_divide():\n"
    "    assert divide(7, 7) == 1\n"
    "    assert divide(-7, 7) == -1\n"
    "    assert divide(7, -7) == -1",

    "def test_divide():\n"
    "    assert divide(-100, -1) == 100\n"
    "    assert divide(-100, 1) == -100\n"
    "    assert divide(100, -1) == -100",

    "def test_divide():\n"
    "    assert divide(1, 0.1) == 10\n"
    "    assert divide(1, -0.1) == -10\n"
    "    assert divide(-1, 0.1) == -10",

    "def test_divide():\n"
    "    assert divide(3, 1) == 3\n"
    "    assert divide(3, -1) == -3\n"
    "    assert divide(-3, -1) == 3",

    "def test_divide():\n"
    "    assert divide(10, 3) == 10 / 3\n"
    "    assert divide(10, 5) == 2\n"
    "    assert divide(10, 10) == 1",

    "def test_divide():\n"
    "    with pytest.raises(TypeError):\n"
    "        divide('a', 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(1, 'a')",

    "def test_divide():\n"
    "    with pytest.raises(TypeError):\n"
    "        divide([], 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(1, [])",

    "def test_divide():\n"
    "    with pytest.raises(TypeError):\n"
    "        divide({}, 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(1, {})",

    "def test_divide():\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(None, 1)\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(1, None)",

    "def test_divide():\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(object(), 2)\n"
    "    with pytest.raises(TypeError):\n"
    "        divide(2, object())",

]

# ----------------------------
# Helpers (same style as base)
# ----------------------------


def is_valid_python(code_src: str) -> bool:
    try:
        ast.parse(code_src)
        return True
    except SyntaxError:
        return False


def load_jsonl(path: str):
    """Load existing edge dataset in the same shape: [{'input': ..., 'output': ...}, ...]."""
    items = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                inp = (obj.get("input") or "").strip()
                out = (obj.get("output") or "").strip()
                if inp and out:
                    items.append({"input": inp, "output": out})
    return items


# ----------------------------
# Main
# ----------------------------

def main() -> None:
    # 1) Load existing edge dataset (if any)
    existing = load_jsonl(DATASET_FILE)

    # 2) Build incoming examples from your seed lists
    incoming_raw = [
        {"input": f.strip(), "output": t.strip()}
        for f, t in zip(edge_functions, edge_tests)
    ]

    # Guard: if accidentally mismatch lengths
    if len(edge_functions) != len(edge_tests):
        raise ValueError(
            f"edge_functions ({len(edge_functions)}) and edge_tests "
            f"({len(edge_tests)}) must have the same length"
        )

    items_in = existing + incoming_raw

    seen_pairs = set()
    per_input_counts = defaultdict(int)
    clean = []
    rejected = []

    for ex in items_in:
        in_src = ex["input"].strip()
        tgt = ex["output"].strip()
        key = (in_src, tgt)

        # Exact pair dedupe
        if key in seen_pairs:
            continue

        # Basic Python validity check
        if not (is_valid_python(in_src) and is_valid_python(tgt)):
            rejected.append(ex)
            continue

        if PER_INPUT_CAP is not None and per_input_counts[in_src] >= PER_INPUT_CAP:
            continue

        clean.append({"input": in_src, "output": tgt})
        seen_pairs.add(key)
        per_input_counts[in_src] += 1

    # 3) Write back the updated edge dataset
    with open(DATASET_FILE, "w", encoding="utf-8") as f:
        for ex in clean:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    # 4) Save generation-time rejects
    if rejected:
        with open(REJECTED_FILE, "w", encoding="utf-8") as f:
            for ex in rejected:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"[edge-dataset] Existing loaded: {len(existing)}")
    print(f"[edge-dataset] Incoming seeds: {len(incoming_raw)}")
    print(f"[edge-dataset] Unique kept:    {len(clean)}")
    print(f"[edge-dataset] Rejected saved: {len(rejected)} -> {REJECTED_FILE}")
    print(f"[edge-dataset] Updated in-place: {DATASET_FILE}")

    # 5) Run edge-audit to produce dataset.edge.cleaned.jsonl
    try:
        from unittestgen.management.audit_edge_dataset import (  # adjust path if needed
            main as audit_main,
        )

        print("[edge-generate] Running audit on dataset.edge.jsonl ...")
        audit_main()
        print("[edge-generate] Audit done. Train on dataset.edge.cleaned.jsonl")
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"[edge-generate] Audit failed: {e}")

    # 6) Build merged rejects snapshot (gen + audit)
    _merge_rejects()


def _merge_rejects() -> None:
    paths = [
        "dataset.edge.rejected.gen.jsonl",
        "dataset.edge.rejected.audit.jsonl",
    ]
    merged = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Tag source if missing
                    if "source" not in obj:
                        obj["source"] = (
                            "generate-edge" if p.endswith(
                                ".gen.jsonl") else "audit-edge"
                        )
                    merged.append(obj)
        except FileNotFoundError:
            continue

    if not merged:
        print("[edge-generate] No rejects to merge.")
        return

    out_path = "dataset.edge.rejected.jsonl"
    with open(out_path, "w", encoding="utf-8") as fo:
        for obj in merged:
            fo.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(
        f"[edge-generate] Combined rejects -> {out_path} ({len(merged)})"
    )


if __name__ == "__main__":
    main()
