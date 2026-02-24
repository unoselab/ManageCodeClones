#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# func_id -> (in_count, out_count, extractable)
FuncMeta = Tuple[int, int, Optional[bool]]


def build_func_map(jsonl_path: Path) -> Dict[str, FuncMeta]:
    func_map: Dict[str, FuncMeta] = {}

    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            obj = json.loads(line)
            for s in obj.get("sources", []):
                fid = s.get("func_id")
                if not fid:
                    continue

                ins = s.get("In", [])
                outs = s.get("Out", [])
                ext = s.get("Extractable", None)

                in_count = len(ins) if isinstance(ins, list) else 0
                out_count = len(outs) if isinstance(outs, list) else 0

                func_map[fid] = (in_count, out_count, ext)

    return func_map


def parse_pred_line(line: str):
    line = line.strip()
    if not line:
        return None

    parts = line.split()
    if len(parts) < 3:
        return None

    return parts[0], parts[1], parts[2]


def bool_to_str(x: Optional[bool]) -> str:
    if x is True:
        return "True"
    if x is False:
        return "False"
    return ""


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Join clone predictions with function-level refactorability metadata."
    )
    ap.add_argument("--jsonl", required=True, type=Path, help="Path to step4_*.jsonl")
    ap.add_argument("--pred", required=True, type=Path, help="Prediction file (txt)")
    ap.add_argument("--out", required=True, type=Path, help="Output CSV file")

    args = ap.parse_args()

    if not args.jsonl.exists():
        print(f"ERROR: --jsonl not found: {args.jsonl}", file=sys.stderr)
        return 2
    if not args.pred.exists():
        print(f"ERROR: --pred not found: {args.pred}", file=sys.stderr)
        return 2

    func_map = build_func_map(args.jsonl)

    total_pairs = 0
    clone_ones = 0
    pair_refactorable_true = 0

    ensure_parent(args.out)

    with args.pred.open("r", encoding="utf-8") as fin, \
         args.out.open("w", encoding="utf-8", newline="") as fout:

        writer = csv.writer(fout)

        writer.writerow([
            "pair_left_func",
            "pair_right_func",
            "clone_predict",
            "pair_left_in",
            "pair_right_in",
            "pair_left_out",
            "pair_right_out",
            "pair_left_extractable",
            "pair_right_extractable",
            "pair_refactorable",
        ])

        for line in fin:
            parsed = parse_pred_line(line)
            if parsed is None:
                continue

            left, right, pred = parsed
            total_pairs += 1

            if pred == "1":
                clone_ones += 1

            lm = func_map.get(left)
            rm = func_map.get(right)

            if lm:
                left_in, left_out, left_ext = lm
            else:
                left_in = left_out = ""
                left_ext = None

            if rm:
                right_in, right_out, right_ext = rm
            else:
                right_in = right_out = ""
                right_ext = None

            if left_ext is None or right_ext is None:
                pair_ref = ""
            else:
                pair_ref_bool = (left_ext is True) and (right_ext is True)
                pair_ref = "True" if pair_ref_bool else "False"
                if pair_ref_bool:
                    pair_refactorable_true += 1

            writer.writerow([
                left,
                right,
                pred,
                left_in,
                right_in,
                left_out,
                right_out,
                bool_to_str(left_ext),
                bool_to_str(right_ext),
                pair_ref,
            ])

    print("\n===== STATISTICS =====")
    print(f"JSONL : {args.jsonl}")
    print(f"PRED  : {args.pred}")
    print(f"OUT   : {args.out}")
    print(f"Loaded func_ids           : {len(func_map)}")
    print(f"Total parsed pairs        : {total_pairs}")
    print(f"clone_predict == 1        : {clone_ones}")
    print(f"pair_refactorable == True : {pair_refactorable_true}")

    if total_pairs > 0:
        print("\nRates:")
        print(f"  Clone positive rate: {clone_ones / total_pairs:.6f}")
        print(f"  Refactorable rate  : {pair_refactorable_true / total_pairs:.6f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())