#!/bin/bash

MODEL="codegpt"
OUTPUT_PATH="./output"

# Loop through both stages automatically
for ADAPT_STAGE in "before" "after"; do
    INPUT_PATH="./data/pred_${ADAPT_STAGE}_adapt_refactorability/${MODEL}/"

    echo "-----------------------------"
    echo "Processing Directory: $INPUT_PATH"
    echo "-----------------------------"
    
    python evaluate_clones.py --input-dir "$INPUT_PATH" --output "$OUTPUT_PATH"
    echo " "
done