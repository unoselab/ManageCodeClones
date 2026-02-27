INPUT_DIR="./data"
OUTPUT_DIR="./output"
MODELS="codegpt,codebert,codet5,graphcodebert"

echo " "
echo "========================================="
echo "== Generating Delta Charts"
echo "========================================="

# 2. Convert comma-separated string to an array and loop to generate charts
IFS=',' read -ra MODEL_ARRAY <<< "$MODELS"

for MODEL in "${MODEL_ARRAY[@]}"; do
    JSONL_FILE="${OUTPUT_DIR}/${MODEL}/rcp_scores.jsonl"
    CHART_FILE="./rcp_delta_chart_${MODEL}.png"
    
    if [ -f "$JSONL_FILE" ]; then
        echo "Generating chart for $MODEL..."
        python 2_plot_delta.py --rcp "$JSONL_FILE" --output "$CHART_FILE"
    fi
done

echo " "
echo "** Pipeline finished! All reports and charts are in $OUTPUT_DIR"