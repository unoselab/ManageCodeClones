import argparse
import pandas as pd
import json
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def generate_delta_chart(jsonl_path: str, output_path: str):
    # 1. Read the JSONL data
    data = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
                
    df = pd.DataFrame(data)

    # 2. Pivot the data to get 'before' and 'after' averages side-by-side for each subject
    # We filter by a specific model (e.g., codegpt) if there are multiple
    df_pivot = df.pivot(index='subject', columns='adapt', values='avg').reset_index()

    # Drop any subjects that don't have BOTH before and after data yet
    df_pivot = df_pivot.dropna(subset=['before', 'after'])

    # 3. Calculate the Delta (Improvement)
    # Since penalties are negative, improvement is After - Before
    # Example: -0.40 (After) - (-2.49) (Before) = +2.09 improvement
    df_pivot['delta'] = df_pivot['after'] - df_pivot['before']

    # 4. Sort from highest improvement to lowest
    df_pivot = df_pivot.sort_values(by='delta', ascending=False)

    # 5. Plotting configurations for academic style
    plt.figure(figsize=(14, 6))
    sns.set_theme(style="whitegrid")
    
    # Create the bar plot
    ax = sns.barplot(
        x='subject', 
        y='delta', 
        data=df_pivot, 
        palette="viridis"
    )

    # Add labels and title
    plt.title('Improvement in Refactoring Compatibility Penalty (RCP) via Domain Adaptation', fontsize=16, pad=15)
    plt.xlabel('Subject Projects', fontsize=12, labelpad=10)
    plt.ylabel('RCP Improvement (Reduction in Errors / Clone)', fontsize=12, labelpad=10)

    # Rotate x-axis labels to 90 degrees to prevent overlapping text
    plt.xticks(rotation=90, ha='center', fontsize=10)
    plt.yticks(fontsize=10)
    
    # Add a horizontal line at Y=0 for baseline reference
    plt.axhline(0, color='black', linewidth=1)

    # Adjust layout to prevent cutting off the rotated x-labels
    plt.tight_layout()

    # 6. Save the figure (300 DPI is standard for IEEE/ACM paper submissions)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"--> Successfully saved Delta Bar Chart to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a Delta Bar Chart for RCP scores.")
    parser.add_argument("--rcp", type=str, required=True, help="Path to the input JSONL file (e.g., output/codegpt/rcp_scores.jsonl)")
    parser.add_argument("--output", type=str, required=True, help="Path to save the output chart (e.g., rcp_delta_chart.png)")
    
    args = parser.parse_args()
    
    input_file = args.rcp
    output_image = args.output
    
    # Check if file exists before running
    if Path(input_file).exists():
        # Ensure the parent directory for the output image exists
        Path(output_image).parent.mkdir(parents=True, exist_ok=True)
        generate_delta_chart(input_file, output_image)
    else:
        print(f"Error: Could not find '{input_file}'. Please check the path.")