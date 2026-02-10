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

python display_clone_group_sizes.py \
    --input ./data/step2_nicad_azure_sim0.7.jsonl \
    > ./data/display_clone_group_sizes1.log 2>&1

python 3_filter_out_group.py \
    --input ./data/step2_nicad_azure_sim0.7.jsonl \
    --output ./data/step3_nicad_azure_sim0.7.jsonl \
    --min-size 1 --max-size 20 \
    > ./data/step3_nicad_azure_sim0.7.log 2>&1

python display_clone_group_sizes.py \
    --input ./data/step3_nicad_azure_sim0.7.jsonl \
    > ./data/display_clone_group_sizes2.log 2>&1

python 4_gen_init_train_sample.py \
    --input ./data/step3_nicad_azure_sim0.7.jsonl \
    --output ./data/step4_nicad_azure_sim0.7.jsonl \

python 5_gen_neg_clone_sample.py \
  --input ./data/step4_nicad_azure_sim0.7.jsonl \
  --out_txt ./data/step5_nicad_azure_sim0.7_neg_pairs.txt \
  --out_jsonl ./data/step5_nicad_azure_sim0.7_neg_pairs.jsonl \
  --out_html ./data/step5_nicad_azure_sim0.7_neg_pairs.html \
  --out_md ./data/step5_nicad_azure_sim0.7_neg_pairs.md \
  --seed 42 --verify --cleanup
