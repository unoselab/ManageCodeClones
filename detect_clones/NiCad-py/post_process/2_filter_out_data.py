#!/usr/bin/env python3
import json
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from collections import Counter
import io
import tokenize
import textwrap

# --- Use Tree-sitter based cleaner ---
try:
    from remove_python_comments import remove_python_comments
except ImportError:
    print("[ERROR] Could not import 'remove_python_comments_ts'.", file=sys.stderr)
    sys.exit(1)

EXCLUSION_CODE_TEST_FUNC = "TEST_FUNC"

# -----------------------------
# Metrics & Heuristics
# -----------------------------
_SKIP_TOKEN_TYPES_FOR_COUNT = {
    tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE,
    tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.COMMENT
}

def nonempty_loc(code: str) -> int:
    if not code:
        return 0
    return sum(1 for line in code.splitlines() if line.strip())

def python_token_count(code: str) -> int:
    if not code:
        return 0
    src = code if code.endswith("\n") else (code + "\n")
    try:
        n = 0
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type in _SKIP_TOKEN_TYPES_FOR_COUNT:
                continue
            n += 1
        return n
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return len(code.split())

def is_test_filename(file_path: str) -> bool:
    if not file_path:
        return False
    p = file_path.lower()
    name = Path(p).name

    # Updated filter logic - or "testutils" in p
    if "/test/" in p or "/tests/" in p or "/testing/" in p:
        return True
    if "/eng/" in p or p.startswith("eng/"):
        return True
    return name.startswith("test_") or name.endswith("_test.py")

def is_test_function_name(code: str) -> bool:
    if not code:
        return False
    for line in code.splitlines():
        if line.strip().startswith("def test_"):
            return True
    return False

def has_assertions_tokenwise(code: str) -> bool:
    if not code:
        return False
    if "assert" not in code:
        return False
    src = code if code.endswith("\n") else (code + "\n")
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.NAME and tok.string == "assert":
                return True
        return False
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return "assert " in code

def has_test_framework_imports_tokenwise(code: str) -> bool:
    if not code:
        return False
    lowered = code.lower()
    if "pytest" not in lowered and "unittest" not in lowered:
        return False

    src = code if code.endswith("\n") else (code + "\n")
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return (
            "import pytest" in lowered or "from pytest" in lowered or
            "import unittest" in lowered or "from unittest" in lowered
        )

    n = len(toks)
    for i in range(n):
        t = toks[i]
        if t.type != tokenize.NAME:
            continue
        if t.string in ("import", "from"):
            j = i + 1
            while j < n and toks[j].type in (
                tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT
            ):
                j += 1
            if j < n and toks[j].type == tokenize.NAME and toks[j].string in ("pytest", "unittest"):
                return True
    return False

def extract_first_def_name(code: str) -> Optional[str]:
    if not code:
        return None
    for line in code.splitlines():
        s = line.strip()
        if s.startswith("def ") and "(" in s:
            rest = s[4:]
            name = rest.split("(", 1)[0].strip()
            return name or None
    return None

def test_reasons(file_path: str, code_clean: str) -> List[str]:
    reasons: List[str] = []
    if is_test_filename(file_path):
        reasons.append("FILENAME")
    if is_test_function_name(code_clean):
        reasons.append("FUNCNAME")
    if has_assertions_tokenwise(code_clean):
        reasons.append("ASSERT")
    if has_test_framework_imports_tokenwise(code_clean):
        reasons.append("IMPORT")
    return reasons

# -----------------------------
# Main Processing
# -----------------------------
def process_stream(fin, fout, log_exclusions: bool = True):
    total_lines = 0
    remaining_lines = 0
    excluded_lines = 0

    loc_all, loc_kept, loc_excluded = [], [], []
    tok_all, tok_kept, tok_excluded = [], [], []

    group_sizes_all: List[int] = []
    group_sizes_kept: List[int] = []
    group_sizes_excluded: List[int] = []

    for line in fin:
        line = line.strip()
        if not line:
            continue

        total_lines += 1
        obj = json.loads(line)
        sources = obj.get("sources")

        if not isinstance(sources, list):
            # Legacy/Flat format
            raw = obj.get("code", "") or obj.get("func", "")
            code_clean = remove_python_comments(textwrap.dedent(raw))

            # UPDATE THE OBJECT (fix: don't overwrite both if both exist)
            if "code" in obj:
                obj["code"] = code_clean
            elif "func" in obj:
                obj["func"] = code_clean

            loc = nonempty_loc(code_clean)
            tok = python_token_count(code_clean)
            loc_all.append(loc)
            loc_kept.append(loc)
            tok_all.append(tok)
            tok_kept.append(tok)

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            remaining_lines += 1
            continue

        # --- Process Group ---
        processed_sources = []
        group_locs = []
        group_toks = []

        group_sizes_all.append(len(sources))

        for src in sources:
            raw = src.get("code", "") or src.get("func", "")
            file_path = src.get("file", "") or src.get("file_path", "")

            # 1) Dedent & Clean with Tree-sitter
            dedented_code = textwrap.dedent(raw)
            code_clean = remove_python_comments(dedented_code)

            # [FIX] UPDATE THE SOURCE OBJECT WITH CLEANED CODE
            if "code" in src:
                src["code"] = code_clean
            elif "func" in src:
                src["func"] = code_clean

            loc = nonempty_loc(code_clean)
            tok = python_token_count(code_clean)

            group_locs.append(loc)
            group_toks.append(tok)
            processed_sources.append(
                {"loc": loc, "tok": tok, "code": code_clean, "file": file_path}
            )

        loc_all.extend(group_locs)
        tok_all.extend(group_toks)

        # Check exclusion (Priority 1: Test Code Checks)
        exclude_reason_data = None
        for p_src in processed_sources:
            reasons = test_reasons(p_src["file"], p_src["code"])
            if reasons:
                func_name = extract_first_def_name(p_src["code"])
                exclude_reason_data = (p_src["file"], func_name, reasons, p_src["loc"], p_src["tok"])
                break

        if exclude_reason_data:
            excluded_lines += 1
            group_sizes_excluded.append(len(sources))
            loc_excluded.extend(group_locs)
            tok_excluded.extend(group_toks)

            if log_exclusions:
                file_path, func_name, reasons, loc, tok = exclude_reason_data
                func_display = func_name if func_name else "<unknown>"
                print(
                    f"[EXCLUDE] code={EXCLUSION_CODE_TEST_FUNC} file={file_path} "
                    f"func={func_display} loc={loc} tok={tok} why={','.join(reasons)}",
                    file=sys.stderr,
                )
        else:
            remaining_lines += 1
            group_sizes_kept.append(len(sources))
            loc_kept.extend(group_locs)
            tok_kept.extend(group_toks)
            # Now writing the 'obj' which contains the updated 'src["code"]'
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    return (
        total_lines,
        remaining_lines,
        excluded_lines,
        loc_all,
        loc_kept,
        loc_excluded,
        tok_all,
        tok_kept,
        tok_excluded,
        group_sizes_all,
        group_sizes_kept,
        group_sizes_excluded,
    )

# -----------------------------
# Reporting Helpers
# -----------------------------
def _median(sorted_vals: List[int]) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2 == 1:
        return float(sorted_vals[mid])
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0

def print_dist_report(label: str, values: List[int], bucket_size: int, topk_exact: int) -> None:
    print(f"[DIST] ===== {label} =====", file=sys.stderr)
    if not values:
        print("[DIST] (empty)", file=sys.stderr)
        return
    vals = sorted(values)
    n = len(vals)
    print(f"[DIST] count    : {n}", file=sys.stderr)
    print(f"[DIST] min/max  : {vals[0]} / {vals[-1]}", file=sys.stderr)
    print(f"[DIST] mean     : {sum(vals)/n:.2f}", file=sys.stderr)
    print(f"[DIST] median   : {_median(vals):.1f}", file=sys.stderr)

    buckets = Counter()
    for v in vals:
        if v <= 0:
            key = "0"
        else:
            start = ((v - 1) // bucket_size) * bucket_size + 1
            key = f"{start:>4}-{start + bucket_size - 1:<4}"
        buckets[key] += 1

    print(f"[DIST] bucket_size: {bucket_size}", file=sys.stderr)
    if "0" in buckets:
        print(f"[DIST]     0      : {buckets['0']}", file=sys.stderr)

    def _range_start(k: str) -> int:
        return int(k.split("-")[0]) if "-" in k else -1

    for k in sorted([k for k in buckets if k != "0"], key=_range_start):
        print(f"[DIST] {k} : {buckets[k]}", file=sys.stderr)

    if topk_exact > 0:
        print(f"[DIST] top exact (top {topk_exact}):", file=sys.stderr)
        for v, cnt in Counter(vals).most_common(topk_exact):
            print(f"[DIST]   {v}: {cnt}", file=sys.stderr)

def print_group_size_dist(label: str, sizes: List[int]) -> None:
    print(f"[GROUP] ===== {label} =====", file=sys.stderr)
    if not sizes:
        print("[GROUP] (empty)", file=sys.stderr)
        return
    cnt = Counter(sizes)
    total = sum(cnt.values())
    print(f"[GROUP] total groups: {total}", file=sys.stderr)
    try:
        print(f"[GROUP] min/max size: {min(cnt)} / {max(cnt)}", file=sys.stderr)
    except ValueError:
        pass
    for k in sorted(cnt):
        print(f"[GROUP] size={k:<3} : {cnt[k]}", file=sys.stderr)

# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Filter Python test functions & report stats.")
    parser.add_argument("--input", default="./data/step1_nicad_azure_sim0.7.jsonl")
    parser.add_argument("--output", default="./data/step2_nicad_azure_sim0.7.jsonl")
    parser.add_argument("--quiet-exclusions", action="store_true")
    parser.add_argument("--loc-bucket-size", type=int, default=5)
    parser.add_argument("--loc-topk", type=int, default=15)
    parser.add_argument("--tok-bucket-size", type=int, default=50)
    parser.add_argument("--tok-topk", type=int, default=15)
    args = parser.parse_args()

    start_time = time.time()
    print(f"[TIME] start: {datetime.now().isoformat(sep=' ', timespec='seconds')}", file=sys.stderr)

    with open(args.input, "r", encoding="utf-8") as fin, open(args.output, "w", encoding="utf-8") as fout:
        (
            total,
            remaining,
            excluded,
            loc_all,
            loc_kept,
            loc_excluded,
            tok_all,
            tok_kept,
            tok_excluded,
            group_sizes_all,
            group_sizes_kept,
            group_sizes_excluded,
        ) = process_stream(fin, fout, log_exclusions=not args.quiet_exclusions)

    elapsed = time.time() - start_time
    print(f"[STATS] total lines : {total}", file=sys.stderr)
    print(f"[STATS] remaining   : {remaining}", file=sys.stderr)
    print(f"[STATS] excluded    : {excluded}", file=sys.stderr)

    print_dist_report("LOC: ALL", loc_all, args.loc_bucket_size, args.loc_topk)
    print_dist_report("LOC: EXCLUDED", loc_excluded, args.loc_bucket_size, args.loc_topk)

    print_dist_report("TOK: ALL", tok_all, args.tok_bucket_size, args.tok_topk)
    print_dist_report("TOK: EXCLUDED", tok_excluded, args.tok_bucket_size, args.tok_topk)

    print_group_size_dist("ALL clone groups (input)", group_sizes_all)
    print_group_size_dist("EXCLUDED clone groups", group_sizes_excluded)

    print_dist_report("LOC: KEPT", loc_kept, args.loc_bucket_size, args.loc_topk)
    print_dist_report("TOK: KEPT", tok_kept, args.tok_bucket_size, args.tok_topk)
    print_group_size_dist("REMAINING clone groups (output)", group_sizes_kept)

    print(f"[TIME] elapsed: {elapsed:.3f}s", file=sys.stderr)

if __name__ == "__main__":
    main()
