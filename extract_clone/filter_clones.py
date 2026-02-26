import argparse
import json
import sys
from pathlib import Path

def filter_clones_in_file(in_file: Path, out_file: Path):
    kept_classes = 0
    dropped_classes = 0
    total_sources_removed = 0

    with open(in_file, "r", encoding="utf-8") as f_in, open(out_file, "w", encoding="utf-8") as f_out:
        for line_num, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                clone_class = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Could not parse JSON in {in_file.name} on line {line_num}: {e}")
                continue

            original_sources = clone_class.get("sources", [])
            
            # 1. Filter out the source records where is_full_function_clone is True
            filtered_sources = [
                src for src in original_sources 
                if not src.get("is_full_function_clone", False)
            ]

            sources_removed_count = len(original_sources) - len(filtered_sources)
            total_sources_removed += sources_removed_count

            # Update the nclones count and the sources list
            clone_class["sources"] = filtered_sources
            clone_class["nclones"] = len(filtered_sources)

            # 2. Drop the classid record if "nclones" < 2
            if clone_class["nclones"] < 2:
                dropped_classes += 1
                continue

            # Write the surviving records to the output
            f_out.write(json.dumps(clone_class, ensure_ascii=False) + "\n")
            kept_classes += 1

    return total_sources_removed, dropped_classes, kept_classes

def process_directory(input_dir: str, output_dir: str):
    in_path = Path(input_dir)
    out_path = Path(output_dir)

    if not in_path.is_dir():
        print(f"Error: The input directory '{input_dir}' does not exist.")
        sys.exit(1)

    out_path.mkdir(parents=True, exist_ok=True)

    jsonl_files = list(in_path.glob("*.jsonl"))
    if not jsonl_files:
        print(f"No .jsonl files found in {input_dir}")
        return

    print(f"Found {len(jsonl_files)} JSONL files to process.\n")

    grand_total_removed = 0
    grand_total_dropped = 0
    grand_total_kept = 0

    for in_file in jsonl_files:
        # Prefix the output file so it doesn't overwrite original data if paths overlap
        out_file = out_path / f"filtered_{in_file.name}"
        
        print(f"Processing: {in_file.name} ...")
        removed, dropped, kept = filter_clones_in_file(in_file, out_file)
        
        grand_total_removed += removed
        grand_total_dropped += dropped
        grand_total_kept += kept

    print("\n--- Final Batch Summary ---")
    print(f"Total instances removed (is_full_function_clone=true): {grand_total_removed}")
    print(f"Total clone classes dropped (nclones < 2):             {grand_total_dropped}")
    print(f"Total clone classes kept:                              {grand_total_kept}")
    print(f"\nFiltered files saved to: {out_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="Batch filter clone JSONL files: remove full-function clones, and drop classes with < 2 clones remaining."
    )
    
    parser.add_argument(
        "--input-dir", "-i", 
        type=str, 
        required=True, 
        help="Path to the directory containing input JSONL files."
    )
    
    parser.add_argument(
        "--output-dir", "-o", 
        type=str, 
        required=True, 
        help="Path to the directory where filtered JSONL files will be saved."
    )

    args = parser.parse_args()

    process_directory(args.input_dir, args.output_dir)

if __name__ == "__main__":
    main()