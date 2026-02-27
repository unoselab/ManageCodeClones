python 2_plot_delta.py --rcp "output/codebert/rcp_scores.jsonl" \
                     --output "rcp_delta_codebert.png"

python 2_plot_delta.py --rcp "output/codegpt/rcp_scores.jsonl" \
                     --output "rcp_delta_codegpt.png"

python 2_plot_delta.py --rcp "output/codet5/rcp_scores.jsonl" \
                     --output "rcp_delta_codet5.png"

python 2_plot_delta.py --rcp "output/graphcodebert/rcp_scores.jsonl" \
                     --output "rcp_delta_graphcodebert.png"
