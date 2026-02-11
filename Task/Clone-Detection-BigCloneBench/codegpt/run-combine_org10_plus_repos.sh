BASE=/home/user1-system11/research_dream/llm-clone/Task/Clone-Detection-BigCloneBench/dataset
OUT=$BASE/combined_org10_plus_repos
python combine_org10_plus_repos.py \
  --base_dir "$BASE" \
  --out_dir  "$OUT" \
  --seed 3
  