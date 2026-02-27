#!/bin/bash

ADAPT_STAGE="after"
REPO="camel"
MODEL="codegpt"

INPUT_PATH="./data/pred_${ADAPT_STAGE}_adapt_refactorability/${MODEL}/pred_${REPO}_with_refactorability.csv"
# INPUT_PATH="./data/pred_${ADAPT_STAGE}_adapt_refactorability/${MODEL}/pred_${REPO}_with_refactorability_sample.csv"

python evaluate_clones.py \
    --input "$INPUT_PATH"

echo ' ';echo '-----------------------------';echo ' '

ADAPT_STAGE="before"
REPO="camel"
MODEL="codegpt"

INPUT_PATH="./data/pred_${ADAPT_STAGE}_adapt_refactorability/${MODEL}/pred_${REPO}_with_refactorability.csv"
# INPUT_PATH="./data/pred_${ADAPT_STAGE}_adapt_refactorability/${MODEL}/pred_${REPO}_with_refactorability_sample.csv"

python evaluate_clones.py \
    --input "$INPUT_PATH"
