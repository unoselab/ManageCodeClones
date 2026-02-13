#!/usr/bin/env python3
"""
4_gen_init_train_sample.py

Purpose
-------
Assign a stable, unique func_id to every function within each clone group. 
Unlike a global counter, this uses the group's classid and the local index 
of the source to ensure IDs remain consistent regardless of file shuffling.

Input:
  JSONL clone groups with structure:
    {
      "classid": <int|str>,
      "sources": [ { ... }, { ... }, ... ]
    }

Output:
  Same JSONL structure, with a "func_id" added to each source:
    func_id = {classid}_{index_in_group}  (e.g., "9_0", "9_1")
"""

import argparse
import json
import os
import sys

def add_unique_ids(input_file: str, output_file: str) -> None:
    if not os.path.exists(input_file):
        print(f"[ERROR] Input file not found: {input_file}")
        sys.exit(1)

    print(f"--- Step 4: Assigning stable func_ids ---")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    total_groups = 0
    total_funcs = 0

    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:

        for line_no, line in enumerate(fin, 1):
            line = line.strip()
            if not line: continue

            try:
                data = json.loads(line)
                class_id = data.get("classid", "unknown")
                sources = data.get("sources", [])

                # Generate IDs using local index (i) for reproducibility
                # Format: {class_id}_{local_index}
                for i, src in enumerate(sources):
                    src["func_id"] = f"{class_id}_{i}"
                    total_funcs += 1

                fout.write(json.dumps(data, ensure_ascii=False) + "\n")
                total_groups += 1
            except json.JSONDecodeError:
                print(f"[WARN] Skipping invalid JSON at line {line_no}")
                continue

    print(f"Processing complete: {total_groups} groups, {total_funcs} functions.")
    print(f"Saved to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add stable func_id to clone groups.")
    parser.add_argument("--input", required=True, help="Input JSONL file")
    parser.add_argument("--output", required=True, help="Output JSONL file")
    args = parser.parse_args()
    
    add_unique_ids(args.input, args.output)