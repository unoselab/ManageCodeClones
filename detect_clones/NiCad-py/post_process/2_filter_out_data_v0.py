#!/usr/bin/env python3
import json
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from collections import Counter
import io
import tokenize

from remove_python_comments import remove_python_comments

EXCLUSION_CODE_TEST_FUNC = "TEST_FUNC"

# -----------------------------
# LOC (non-empty lines)
#   - remove_python_comments() already post-cleans whitespace-only lines,
#     but keep this robust.
# -----------------------------
def nonempty_loc(code: str) -> int:
    if not code:
        return 0
    return sum(1 for line in code.splitlines() if line.strip())

# -----------------------------
# Token count (Python lexical tokens, not Transformer tokens)
# -----------------------------
_SKIP_TOKEN_TYPES_FOR_COUNT = {
    tokenize.ENCODING,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENDMARKER,
    tokenize.COMMENT,  # should not exist after remove_python_comments(), but keep robust
}

def python_token_count(code: str) -> int:
    """
    Count Python lexical tokens using tokenize (standard tokens).
    Assumes docstrings+comments already removed, but still robust if not.
    Falls back to whitespace split if tokenize fails.
    """
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

# -----------------------------
# Heuristic checks (4)
#   1) file name/path
#   2) function name
#   3) assertions (token-based)
#   4) framework imports (token-based)
#   NOTE: these checks run on code already cleaned by remove_python_comments()
# -----------------------------
def is_test_filename(file_path: str) -> bool:
    if not file_path:
        return False
    p = file_path.lower()
    name = Path(p).name
    return (
        "/test/" in p
        or "/tests/" in p
        or name.startswith("test_")
        or name.endswith("_test.py")
    )

def is_test_function_name(code: str) -> bool:
    if not code:
        return False
    for line in code.splitlines():
        if line.strip().startswith("def test_"):
            return True
    return False

def has_assertions_tokenwise(code: str) -> bool:
    """
    True if token NAME 'assert' appears (not inside strings/comments).
    """
    if not code:
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
    """
    Detect pytest/unittest imports using tokens.
    Matches:
      import pytest
      from pytest import ...
      import unittest
      from unittest import ...
    """
    if not code:
        return False
    src = code if code.endswith("\n") else (code + "\n")
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        lowered = code.lower()
        return (
            "import pytest" in lowered
            or "from pytest" in lowered
            or "import unittest" in lowered
            or "from unittest" in lowered
        )

    n = len(toks)
    for i in range(n):
        t = toks[i]
        if t.type != tokenize.NAME:
            continue

        if t.string == "import":
            j = i + 1
            while j < n and toks[j].type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                j += 1
            if j < n and toks[j].type == tokenize.NAME and toks[j].string in ("pytest", "unittest"):
                return True

        if t.string == "from":
            j = i + 1
            while j < n and toks[j].type in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                j += 1
            if j < n and toks[j].type == tokenize.NAME and toks[j].string in ("pytest", "unittest"):
                return True

    return False

# -----------------------------
# Extractors for logging
# -----------------------------
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

def is_test_source_with_reason(src: Dict[str, Any]) -> Tuple[bool, List[str], str, Optional[str], int, int]:
    file_path = src.get("file", "") or src.get("file_path", "")
    code_raw = src.get("code", "") or src.get("func", "")
    code_clean = remove_python_comments(code_raw)  # docstrings + comments removed

    reasons = test_reasons(file_path, code_clean)
    func_name = extract_first_def_name(code_clean)

    loc = nonempty_loc(code_clean)
    tok = python_token_count(code_clean)
    return (len(reasons) > 0, reasons, file_path, func_name, loc, tok)

# -----------------------------
# Distribution reporting (shared)
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
    minv, maxv = vals[0], vals[-1]
    meanv = sum(vals) / n
    medv = _median(vals)

    print(f"[DIST] count    : {n}", file=sys.stderr)
    print(f"[DIST] min/max  : {minv} / {maxv}", file=sys.stderr)
    print(f"[DIST] mean     : {meanv:.2f}", file=sys.stderr)
    print(f"[DIST] median   : {medv:.1f}", file=sys.stderr)

    buckets = Counter()
    for v in vals:
        if v <= 0:
            key = "0"
        else:
            start = ((v - 1) // bucket_size) * bucket_size + 1
            end = start + bucket_size - 1
            key = f"{start:>4}-{end:<4}"
        buckets[key] += 1

    print(f"[DIST] bucket_size: {bucket_size}", file=sys.stderr)
    if "0" in buckets:
        print(f"[DIST]    0      : {buckets['0']}", file=sys.stderr)

    range_keys = [k for k in buckets.keys() if k != "0"]
    def _range_start(k: str) -> int:
        return int(k.split("-", 1)[0].strip())
    for k in sorted(range_keys, key=_range_start):
        print(f"[DIST] {k} : {buckets[k]}", file=sys.stderr)

    if topk_exact > 0:
        exact = Counter(vals)
        print(f"[DIST] top exact (top {topk_exact}):", file=sys.stderr)
        for v, cnt in exact.most_common(topk_exact):
            print(f"[DIST]   {v}: {cnt}", file=sys.stderr)

# -----------------------------
# Main filtering logic
# -----------------------------
def process_stream(fin, fout, log_exclusions: bool = True):
    total_lines = 0
    remaining_lines = 0
    excluded_lines = 0

    # per-function distributions (after docstrings+comments removal)
    loc_all: List[int] = []
    loc_kept: List[int] = []
    loc_excluded: List[int] = []

    tok_all: List[int] = []
    tok_kept: List[int] = []
    tok_excluded: List[int] = []

    for line in fin:
        line = line.strip()
        if not line:
            continue

        total_lines += 1
        obj = json.loads(line)

        sources = obj.get("sources")
        if not isinstance(sources, list):
            # Non clone-group: keep; still collect LOC/TOK if code present
            code_raw = obj.get("code", "") or obj.get("func", "")
            code_clean = remove_python_comments(code_raw)

            loc = nonempty_loc(code_clean)
            tok = python_token_count(code_clean)

            loc_all.append(loc); loc_kept.append(loc)
            tok_all.append(tok); tok_kept.append(tok)

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            remaining_lines += 1
            continue

        # Collect LOC/TOK for ALL sources in this group (after docstrings+comments removal)
        group_locs: List[int] = []
        group_toks: List[int] = []
        for src in sources:
            code_raw = src.get("code", "") or src.get("func", "")
            code_clean = remove_python_comments(code_raw)
            group_locs.append(nonempty_loc(code_clean))
            group_toks.append(python_token_count(code_clean))

        loc_all.extend(group_locs)
        tok_all.extend(group_toks)

        # Decide exclusion: drop entire group if ANY source is a test
        exclude_reason = None  # (file_path, func_name, reasons, loc, tok)
        for src in sources:
            is_test, reasons, file_path, func_name, loc, tok = is_test_source_with_reason(src)
            if is_test:
                exclude_reason = (file_path, func_name, reasons, loc, tok)
                break

        if exclude_reason is not None:
            excluded_lines += 1
            loc_excluded.extend(group_locs)
            tok_excluded.extend(group_toks)

            if log_exclusions:
                file_path, func_name, reasons, loc, tok = exclude_reason
                func_display = func_name if func_name else "<unknown>"
                reason_str = ",".join(reasons) if reasons else "UNKNOWN"
                print(
                    f"[EXCLUDE] code={EXCLUSION_CODE_TEST_FUNC} "
                    f"file={file_path} func={func_display} loc={loc} tok={tok} why={reason_str}",
                    file=sys.stderr,
                )
            continue

        # keep group
        remaining_lines += 1
        loc_kept.extend(group_locs)
        tok_kept.extend(group_toks)
        fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    return (
        total_lines, remaining_lines, excluded_lines,
        loc_all, loc_kept, loc_excluded,
        tok_all, tok_kept, tok_excluded
    )

# -----------------------------
# Entry point
# -----------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Filter out clone groups that contain Python test functions; report LOC and token distributions (docstrings+comments removed)."
    )
    parser.add_argument("--input", default="./data/step1_nicad_azure_sim0.7.jsonl")
    parser.add_argument("--output", default="./data/step2_nicad_azure_sim0.7.jsonl")
    parser.add_argument("--quiet-exclusions", action="store_true")

    parser.add_argument("--loc-bucket-size", type=int, default=5)
    parser.add_argument("--loc-topk", type=int, default=15)

    parser.add_argument("--tok-bucket-size", type=int, default=50)
    parser.add_argument("--tok-topk", type=int, default=15)

    args = parser.parse_args()

    start_wall = datetime.now()
    start_time = time.time()
    print(f"[TIME] start time : {start_wall.isoformat(sep=' ', timespec='seconds')}", file=sys.stderr)

    fin = open(args.input, "r", encoding="utf-8")
    fout = open(args.output, "w", encoding="utf-8")
    try:
        (total, remaining, excluded,
         loc_all, loc_kept, loc_excluded,
         tok_all, tok_kept, tok_excluded) = process_stream(fin, fout, log_exclusions=not args.quiet_exclusions)
    finally:
        fin.close()
        fout.close()

    end_wall = datetime.now()
    elapsed = time.time() - start_time

    # ---- line stats ----
    print(f"[STATS] total input lines   : {total}", file=sys.stderr)
    print(f"[STATS] remaining lines     : {remaining}", file=sys.stderr)
    print(f"[STATS] excluded lines      : {excluded}", file=sys.stderr)

    # ---- LOC distributions ----
    print_dist_report("LOC: ALL functions (input, docstrings+comments removed)", loc_all, args.loc_bucket_size, args.loc_topk)
    print_dist_report("LOC: REMAINING functions (output, docstrings+comments removed)", loc_kept, args.loc_bucket_size, args.loc_topk)
    print_dist_report("LOC: EXCLUDED functions (dropped groups, docstrings+comments removed)", loc_excluded, args.loc_bucket_size, args.loc_topk)

    # ---- Token distributions ----
    print_dist_report("TOKENS: ALL functions (input, docstrings+comments removed)", tok_all, args.tok_bucket_size, args.tok_topk)
    print_dist_report("TOKENS: REMAINING functions (output, docstrings+comments removed)", tok_kept, args.tok_bucket_size, args.tok_topk)
    print_dist_report("TOKENS: EXCLUDED functions (dropped groups, docstrings+comments removed)", tok_excluded, args.tok_bucket_size, args.tok_topk)

    # ---- timing ----
    print(f"[TIME] end time   : {end_wall.isoformat(sep=' ', timespec='seconds')}", file=sys.stderr)
    print(f"[TIME] elapsed    : {elapsed:.3f} seconds", file=sys.stderr)

if __name__ == "__main__":
    main()