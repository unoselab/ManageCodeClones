#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# USER CONFIG
# -----------------------------
PY_SCRIPT="/home/user1-system11/research_dream/llm-clone/AST_Clone_Extractability/join_pred_refactorability.py"

PRED_DIR="/home/user1-system11/research_dream/llm-clone/AST_Clone_Extractability/input/prediction_before_adapt/codebert/predictions_prefixed"

JSONL_ROOT="/home/user1-system11/research_dream/llm-clone/AST_Clone_Extractability/output/java-functions"

OUT_DIR="/home/user1-system11/research_dream/llm-clone/AST_Clone_Extractability/output/pred_before_adapt_refactorability"

# -----------------------------
# PREP
# -----------------------------
mkdir -p "$OUT_DIR"

echo "Starting batch processing..."
echo

shopt -s nullglob

for pred in "$PRED_DIR"/predictions_*_test.txt; do
    base="$(basename "$pred")"              # predictions_camel_test.txt
    system="${base#predictions_}"           # camel_test.txt
    system="${system%_test.txt}"            # camel

    echo "Processing system: $system"

    # Find matching JSONL
    mapfile -t jsonls < <(
        find "$JSONL_ROOT" -type f -name "step4_*${system}*.jsonl"
    )

    if [[ "${#jsonls[@]}" -eq 0 ]]; then
        echo "  ERROR: No JSONL found for $system"
        continue
    fi

    if [[ "${#jsonls[@]}" -gt 1 ]]; then
        echo "  ERROR: Multiple JSONLs found for $system"
        printf '    %s\n' "${jsonls[@]}"
        continue
    fi

    jsonl="${jsonls[0]}"
    out_csv="$OUT_DIR/pred_${system}_with_refactorability.csv"

    python3 "$PY_SCRIPT" \
        --jsonl "$jsonl" \
        --pred "$pred" \
        --out "$out_csv"

    echo "  Done -> $out_csv"
    echo
done

echo "All systems processed."