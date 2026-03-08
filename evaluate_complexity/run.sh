python evaluate_controlflow_complexity.py \
    --input ./data/activemq-sim0.7/step4_nicad_activemq_sim0.7_filtered_with_func_id.jsonl \
    --output ./output/controlflow/step1_nicad_activemq_sim0.7_eval_complexity.jsonl
    
python evaluate_similarity_thresholds.py \
    --input ./data/activemq-sim0.7/step4_nicad_activemq_sim0.7_filtered_with_func_id.jsonl \
    --output ./output/similarity/step1_nicad_activemq_sim0.7_eval_complexity.jsonl

python evaluate_semantic_divergence.py \
    --input ./data/activemq-sim0.7/step4_nicad_activemq_sim0.7_filtered_with_func_id.jsonl \
    --output ./output/semantic/step1_nicad_activemq_sim0.7_eval_complexity.jsonl

python evaluate_dataflow_coupling.py \
    --input ./data/activemq-sim0.7/step4_nicad_activemq_sim0.7_filtered_with_func_id.jsonl \
    --output ./output/dataflow/step1_nicad_activemq_sim0.7_eval_complexity.jsonl

python evaluate_architectural_distance.py \
    --input ./data/activemq-sim0.7/step4_nicad_activemq_sim0.7_filtered_with_func_id.jsonl \
    --output ./output/architecture/step4_nicad_activemq_sim0.7_eval_architecture.jsonl