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
]

edge_tests = [
    "def test_add(): assert add(0,0)==0; assert add(-1,1)==0; assert add(10**9,-10**9)==0",
    "def test_add(): assert add(-5,-5)==-10; assert add(-1,0)==-1; assert add(1,-2)==-1",
    "def test_add(): assert add(999999999,1)==1000000000; assert add(-999999999,-1)==-1000000000; assert add(0,-999)==-999",
    "def test_add(): assert add(0.1,0.2)==0.30000000000000004; assert add(-0.5,0.5)==0.0; assert add(1.5,-0.5)==1.0",
    "def test_add(): assert add('', '')==''; assert add('a','b')=='ab'; assert add('😀','😁')=='😀😁'",
    "def test_add(): assert add([],[])==[]; assert add([1],[2])==[1,2]; assert add(['x'],[])==['x']",
    "def test_add(): assert add({},{} )=={}; assert add({'a':1},{'b':2})=={'a':1,'b':2}; assert add({'x':1},{} )=={'x':1}",
    "def test_add(): assert add(() ,() )==(); assert add((1,), (2,))==(1,2); assert add((),(3,4))==(3,4)",
    "def test_add(): assert add('','abc')=='abc'; assert add('abc','')=='abc'; assert add(' ',' ')==' '",
    "def test_add(): assert add(True,True)==2; assert add(True,False)==1; assert add(False,False)==0",
    "def test_add(): assert add(-1,-999999999)==-1000000000; assert add(500,-500)==0; assert add(3,-7)==-4",
    "def test_add(): assert add(1e308,1e308)==float('inf'); assert add(-1e308,-1e308)==-float('inf'); assert add(1e308,-1e308)==0.0",
    "def test_add(): assert add('a','😊')=='a😊'; assert add('á','é')=='áé'; assert add('🐍','code')=='🐍code'",
    "def test_add(): assert add([[],[]],[1])==[[],[],1]; assert add([1,[2]],[3])==[1,[2],3]; assert add([0],[[]])==[0,[]]",
    "def test_add(): assert add('', '🙂')=='🙂'; assert add('🙂','')=='🙂'; assert add('👍','👎')=='👍👎'",
    "def test_add(): assert add(0,-0)==0; assert add(-0.0,0.0)==0.0; assert add(0.0,0.0)==0.0",
    "def test_add(): assert add(-1000000000,999999999)==-1; assert add(250000000,-250000000)==0; assert add(42,-42)==0",
    "def test_add(): assert add('abc','123')=='abc123'; assert add('','123')=='123'; assert add('abc','')=='abc'",
    "def test_add(): assert add([],[1,2,3])==[1,2,3]; assert add([1,2],[])==[1,2]; assert add([0],[0])==[0,0]",
    "def test_add(): assert add((-1,),(-2,))==(-1,-2); assert add((),(1,))==(1,); assert add((0,),())==(0,)",
    "def test_add(): assert add(True,5)==6; assert add(False,5)==5; assert add(-1,True)==0",
    "def test_add(): assert add(1e-12,1e-12)==2e-12; assert add(-1e-12,1e-12)==0.0; assert add(3.14,-3.14)==0.0",
    "def test_add(): assert add('🔥','🔥')=='🔥🔥'; assert add('☺️','☹️')=='☺️☹️'; assert add('✨','')=='✨'",
    "def test_add(): assert add({'a':1},{})=={'a':1}; assert add({}, {'b':2})=={'b':2}; assert add({'x':1},{'x':2})=={'x':2}",
    "def test_add(): assert add([1],[[]])==[1,[]]; assert add([[]],[])==[[]]; assert add([],['a'])==['a']",
    "def test_subtract(): assert subtract(0,0)==0; assert subtract(1,1)==0; assert subtract(-1,-1)==0",
    "def test_subtract(): assert subtract(0,5)==-5; assert subtract(5,0)==5; assert subtract(0,-5)==5",
    "def test_subtract(): assert subtract(-5,-10)==5; assert subtract(-10,-5)==-5; assert subtract(-1,-2)==1",
    "def test_subtract(): assert subtract(10**9,10**9)==0; assert subtract(10**9,10**9-1)==1; assert subtract(-(10**9),10**9)==-2*10**9",
    "def test_subtract(): assert subtract(1,-1)==2; assert subtract(-1,1)==-2; assert subtract(-3,-5)==2",
    "def test_subtract(): assert subtract(0.0,0.0)==0.0; assert subtract(0.3,0.1)==0.19999999999999998; assert subtract(-0.5,-0.25)==-0.25",
    "def test_subtract(): assert subtract(1.5,1.5)==0.0; assert subtract(-1.5,1.5)==-3.0; assert subtract(1.5,-1.5)==3.0",
    "def test_subtract(): assert subtract(True,True)==0; assert subtract(True,False)==1; assert subtract(False,True)==-1",
    "def test_subtract(): assert subtract(0,True)==-1; assert subtract(True,0)==1; assert subtract(5,True)==4",
    "def test_subtract(): assert subtract(1e308,1e308)==0.0; assert subtract(1e308,-1e308)==float('inf'); assert subtract(-1e308,1e308)==-float('inf')",
    "def test_subtract(): assert subtract(-1e-12,1e-12)==-2e-12; assert subtract(1e-12,-1e-12)==2e-12; assert subtract(0.0,1e-12)==-1e-12",
    "def test_subtract(): assert subtract(2**63-1,2**63-1)==0; assert subtract(-(2**63-1),2**63-1)==-2*(2**63-1); assert subtract(2**63-1,0)==2**63-1",
    "def test_subtract(): assert subtract(-1000000000,0)==-1000000000; assert subtract(0,-1000000000)==1000000000; assert subtract(-1000000000,1)==-1000000001",
    "def test_subtract(): assert subtract(5,10)==-5; assert subtract(10,5)==5; assert subtract(5,5)==0",
    "def test_subtract(): assert subtract(1,-0)==1; assert subtract(-0,1)==-1; assert subtract(-0,-0)==0",
    "def test_subtract(): assert subtract(-2,-0)==-2; assert subtract(-2,0)==-2; assert subtract(0,-2)==2",
    "def test_subtract(): assert subtract(999999999,1000000000)==-1; assert subtract(1000000000,999999999)==1; assert subtract(-999999999,-1000000000)==1",
    "def test_subtract(): assert subtract(3.14,3.14)==0.0; assert subtract(3.14,0.0)==3.14; assert subtract(0.0,3.14)==-3.14",
    "def test_subtract(): assert subtract(-3.14,-3.14)==0.0; assert subtract(-3.14,3.14)==-6.28; assert subtract(3.14,-3.14)==6.28",
    "def test_subtract(): assert subtract(100,-1)==101; assert subtract(-1,100)==-101; assert subtract(-100,-1)==-99",
    "def test_subtract(): assert subtract(1,2)==-1; assert subtract(2,1)==1; assert subtract(-1,2)==-3",
    "def test_subtract(): assert subtract(50,49)==1; assert subtract(49,50)==-1; assert subtract(50,51)==-1",
    "def test_subtract(): assert subtract(10**5,10**5-1)==1; assert subtract(10**5-1,10**5)==-1; assert subtract(-10**5,10**5-1)==-2*10**5+1",
    "def test_subtract(): assert subtract(7,-7)==14; assert subtract(-7,7)==-14; assert subtract(-7,-7)==0",
    "def test_subtract(): assert subtract(True,2)==-1; assert subtract(2,True)==1; assert subtract(False,-2)==2",
    "def test_rotate_right(): assert rotate_right('')==''; assert rotate_right('a')=='a'; assert rotate_right('aa')=='aa'",
    "def test_rotate_right(): assert rotate_right('ab')=='ba'; assert rotate_right('abc')=='cab'; assert rotate_right('abcd')=='dabc'",
    "def test_rotate_right(): assert rotate_right('hello')=='ohell'; assert rotate_right('world')=='dworl'; assert rotate_right('test')=='ttes'",
    "def test_rotate_right(): assert rotate_right('😊a')=='a😊'; assert rotate_right('a😊')=='😊a'; assert rotate_right('🙂🙂')=='🙂🙂'",
    "def test_rotate_right(): assert rotate_right(' Café')=='é Caf'; assert rotate_right('café')=='écaf'; assert rotate_right('ño')=='oñ'",
    "def test_rotate_right(): assert rotate_right('   ')=='   '; assert rotate_right(' a ')==' a '; assert rotate_right('  a')=='a  '",
    "def test_rotate_right(): assert rotate_right('a b')=='b a'; assert rotate_right(' hi')=='ihi'; assert rotate_right('hi ')==' hi'",
    "def test_rotate_right(): assert rotate_right('123')=='312'; assert rotate_right('001')=='100'; assert rotate_right('10')=='01'",
    "def test_rotate_right(): assert rotate_right('!@#')=='#@!'; assert rotate_right('?.')=='.?'; assert rotate_right('---')=='---'",
    "def test_rotate_right(): assert rotate_right('A')=='A'; assert rotate_right('Aa')=='aA'; assert rotate_right('ABc')=='cAB'",
    "def test_rotate_right(): assert rotate_right('mixedCASE')=='EmixedCAS'; assert rotate_right('TestIng')=='gTestIn'; assert rotate_right('CamelCase')=='eCamelCas'",
    "def test_rotate_right(): assert rotate_right('0')=='0'; assert rotate_right('01')=='10'; assert rotate_right('010')=='001'",
    "def test_rotate_right(): assert rotate_right(' spaced')=='d space'; assert rotate_right('spaced ')==' spaced'; assert rotate_right('  spaced')=='d  space'",
    "def test_rotate_right(): assert rotate_right('longstring')=='glongstrin'; assert rotate_right('rotate')=='erotat'; assert rotate_right('python')=='npytho'",
    "def test_rotate_right(): assert rotate_right('abcabc')=='cabcab'; assert rotate_right('aaaaab')=='baaaaa'; assert rotate_right('ababab')=='babaab'",
    "def test_rotate_right(): assert rotate_right('#tag')=='g#ta'; assert rotate_right('##tag')=='g##ta'; assert rotate_right('tag#')=='#tag'",
    "def test_rotate_right(): assert rotate_right('_hidden')=='n_hidde'; assert rotate_right('__x')=='x__'; assert rotate_right('_')=='_'",
    "def test_rotate_right(): assert rotate_right('日本語')=='語日本'; assert rotate_right('語日')=='日語'; assert rotate_right('語')=='語'",
    "def test_rotate_right(): assert rotate_right('😊😊a')=='a😊😊'; assert rotate_right('a😊😊')=='😊a😊'; assert rotate_right('😊a😊')=='😊😊a'",
    "def test_rotate_right(): assert rotate_right('tab\t')=='\ttab'; assert rotate_right('\ttab')=='b\tta'; assert rotate_right('a\tb')=='ba\t'",
    "def test_rotate_right(): assert rotate_right('abc')=='cab'; assert rotate_right('ab')=='ba'; assert rotate_right('ab')=='ba'",
    "def test_rotate_right(): assert rotate_right(' ')==' '; assert rotate_right('  a')=='a  '; assert rotate_right('a  ')=='  a'",
    "def test_rotate_right(): assert rotate_right('ab cd')=='dab c'; assert rotate_right(' cdab')=='b cda'; assert rotate_right('abcd ')==' abcd'",
    "def test_rotate_right(): assert rotate_right('0a0')=='00a'; assert rotate_right('a0a')=='aa0'; assert rotate_right('00a')=='a00'",
    "def test_rotate_right(): assert rotate_right('END!')=='!END'; assert rotate_right('YES?')=='?YES'; assert rotate_right('ok!')=='!ok'",
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
