#!/usr/bin/env python3
import pandas as pd
import argparse

def main():
    parser = argparse.ArgumentParser(description="Sample 100 clone pairs for manual inspection.")
    parser.add_argument("--csv", required=True, help="Path to the refactor clone eval CSV")
    parser.add_argument("--out", required=True, help="Path to save the sampled dataset")
    args = parser.parse_args()

    # Load the evaluation dataset
    df = pd.read_csv(args.csv)

    # 1. Ensure the pair is from the SAME Java file
    # e.g., camel_3492_3312 -> left_file_id is 3492
    def is_same_file(row):
        try:
            left_file_id = str(row['pair_left_func']).split('_')[1]
            right_file_id = str(row['pair_right_func']).split('_')[1]
            return left_file_id == right_file_id
        except IndexError:
            return False

    df['same_file'] = df.apply(is_same_file, axis=1)
    df = df[df['same_file'] == True]

    # 2. Enforce the strict Refactorability requirement
    df = df[df['Refactorable'] == 1]

    # 3. Define the masks for the 3 Cases
    mask_case1 = (df['actual_label'] == 1) & (df['clone_predict'] == 0) & (df['clone_predict_after_adapt'] == 1)
    mask_case2 = (df['actual_label'] == 0) & (df['clone_predict'] == 1) & (df['clone_predict_after_adapt'] == 0)
    mask_case3 = (df['actual_label'] == 1) & (df['clone_predict'] == 1) & (df['clone_predict_after_adapt'] == 1)

    df_case1 = df[mask_case1].copy()
    df_case2 = df[mask_case2].copy()
    df_case3 = df[mask_case3].copy()

    # Label them to make your manual inspection easier
    df_case1['inspection_case'] = 'Case 1 (False Negative Fixed)'
    df_case2['inspection_case'] = 'Case 2 (False Positive Fixed)'
    df_case3['inspection_case'] = 'Case 3 (True Positive Maintained)'

    # 4. Sample the requested amounts 
    # (Uses min() to gracefully handle datasets that don't have enough matching pairs)
    sample_case1 = df_case1.sample(n=min(45, len(df_case1)), random_state=42)
    sample_case2 = df_case2.sample(n=min(40, len(df_case2)), random_state=42)
    sample_case3 = df_case3.sample(n=min(15, len(df_case3)), random_state=42)

    # Combine the samples
    final_sample = pd.concat([sample_case1, sample_case2, sample_case3])

    # 5. Clean up the output CSV specifically for your Eclipse/VS Code work
    columns_to_keep = [
        'inspection_case', 'pair_left_func', 'pair_right_func', 
        'actual_label', 'clone_predict', 'clone_predict_after_adapt',
        'InCount_L', 'OutCount_L', 'InType_L', 'OutType_L'
    ]
    
    final_sample[columns_to_keep].to_csv(args.out, index=False)

    # Print Summary to terminal
    print(f"\n[SUCCESS] Manual Inspection dataset created: {args.out}")
    print("=== SAMPLING BREAKDOWN ===")
    print(f"Case 1 (Requested 45): Found {len(sample_case1)}")
    print(f"Case 2 (Requested 40): Found {len(sample_case2)}")
    print(f"Case 3 (Requested 15): Found {len(sample_case3)}")
    print(f"Total pairs extracted: {len(final_sample)}\n")

if __name__ == "__main__":
    main()