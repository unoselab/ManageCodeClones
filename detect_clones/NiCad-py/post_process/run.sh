python 1_nicad_xml_to_jsonl.py \
    --xml ./input/azure-sdk-for-python_functions-clones-0.30-classes-withsource.xml \
    --out ./data/step1_nicad_azure_sim0.7.jsonl \
    --mode class \
    > ./data/step1_nicad_azure_sim0.7.log 2>&1

# python 1_nicad_xml_to_jsonl.py \
#     --xml ./input-bck/azure-sdk-for-python_functions-clones-0.30-classes-withsource.xml \
#     --out ./data-bck/step1_nicad_azure_sim0.7.jsonl \
#     --mode class \
#     > ./data-bck/step1_nicad_azure_sim0.7.log 2>&1

python 2_filter_out_data.py \
    --input ./data/step1_nicad_azure_sim0.7.jsonl \
    --output ./data/step2_nicad_azure_sim0.7.jsonl \
    > ./data/step2_nicad_azure_sim0.7.log 2>&1
