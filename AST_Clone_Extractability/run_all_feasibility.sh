#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/user1-system11/research_dream/llm-clone/AST_Clone_Extractability"
IN_BASE="$ROOT/input/java-functions"
OUT_BASE="$ROOT/output/java-functions"

P=7
R=1

LOG_FILE="$ROOT/output/java-functions/ALL_repos_feasibility.log"

mkdir -p "$OUT_BASE"

echo "==============================================================" > "$LOG_FILE"
echo "Batch Feasibility Run Started: $(date)" >> "$LOG_FILE"
echo "==============================================================" >> "$LOG_FILE"

for repo_dir in "$IN_BASE"/*-sim0.7; do
  [[ -d "$repo_dir" ]] || continue
  repo="$(basename "$repo_dir")"

  in_file="$(ls "$repo_dir"/step4_nicad_*_filtered_with_func_id.jsonl 2>/dev/null | head -n 1 || true)"

  if [[ -z "${in_file}" ]]; then
    echo "[SKIP] $repo (no matching input file)" | tee -a "$LOG_FILE"
    continue
  fi

  repo_out_dir="$OUT_BASE/$repo"
  mkdir -p "$repo_out_dir"

  base="$(basename "$in_file" .jsonl)"
  out_file="$repo_out_dir/${base}_feasibility_P${P}_R${R}.jsonl"

  echo "" | tee -a "$LOG_FILE"
  echo "==============================================================" | tee -a "$LOG_FILE"
  echo "[RUN ] Repo: $repo" | tee -a "$LOG_FILE"
  echo "Input : $in_file" | tee -a "$LOG_FILE"
  echo "Output: $out_file" | tee -a "$LOG_FILE"
  echo "Time  : $(date)" | tee -a "$LOG_FILE"
  echo "==============================================================" | tee -a "$LOG_FILE"

  (
    cd "$ROOT"
    PYTHONPATH=.. python main.py \
      --input "$in_file" \
      --output "$out_file" \
      --P "$P" --R "$R" \
      --jsonl
  ) 2>&1 | tee -a "$LOG_FILE"

done

echo "" | tee -a "$LOG_FILE"
echo "Batch Finished: $(date)" | tee -a "$LOG_FILE"
echo "==============================================================" | tee -a "$LOG_FILE"