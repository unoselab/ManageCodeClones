#!/usr/bin/env python3
from pathlib import Path
import argparse
import sys
import random

def read_lines(p: Path):
    if not p.exists():
        print(f"[WARN] missing: {p}", file=sys.stderr)
        return []
    return [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]

def write_lines(p: Path, lines):
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base_dir", required=True, help="dataset directory containing repo subfolders")
    ap.add_argument("--out_dir", required=True, help="output directory")
    ap.add_argument("--org_repo", default="org", help="org repo folder name")
    ap.add_argument("--seed", type=int, default=3, help="shuffle seed")
    ap.add_argument("--exclude", nargs="*", default=[], help="repo folders to exclude")
    args = ap.parse_args()

    rnd = random.Random(args.seed)

    base = Path(args.base_dir)
    out  = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    out_name = Path(args.out_dir).name
    repos = sorted(
        p.name for p in base.iterdir()
        if p.is_dir() and p.name != out_name
    )
    repos = [r for r in repos if r not in set(args.exclude)]


    if args.org_repo not in repos:
        print(f"[ERROR] org repo not found: {args.org_repo}", file=sys.stderr)
        sys.exit(1)

    other_repos = [r for r in repos if r != args.org_repo]

    # -------- train --------
    train_lines = []
    train_lines += read_lines(base / args.org_repo / "train_10percent.txt")
    for r in other_repos:
        train_lines += read_lines(base / r / "train.txt")

    rnd.shuffle(train_lines)
    write_lines(out / "train_mix.txt", train_lines)

    # -------- valid --------
    valid_lines = []
    valid_lines += read_lines(base / args.org_repo / "valid_10percent.txt")
    for r in other_repos:
        valid_lines += read_lines(base / r / "valid.txt")

    rnd.shuffle(valid_lines)
    write_lines(out / "valid_mix.txt", valid_lines)

    # -------- data.jsonl (NO shuffle) --------
    data_lines = []
    for r in repos:
        data_lines += read_lines(base / r / "data.jsonl")

    write_lines(out / "data_mix.jsonl", data_lines)

    print("[OK] Combined + shuffled dataset created")
    print(f"  train_mix.txt lines  : {len(train_lines)}")
    print(f"  valid_mix.txt lines  : {len(valid_lines)}")
    print(f"  data_mix.jsonl lines : {len(data_lines)}")
    print(f"  shuffle seed     : {args.seed}")
    print(f"  repos included   : {len(repos)} (org + {len(other_repos)} others)")

if __name__ == "__main__":
    main()
