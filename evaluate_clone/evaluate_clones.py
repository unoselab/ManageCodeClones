import argparse
import pandas as pd
import sys
from pathlib import Path
from string import Template

def get_ground_truth(row):
    try:
        left_class = str(row['pair_left_func']).split('_')[1]
        right_class = str(row['pair_right_func']).split('_')[1]
        return 1 if left_class == right_class else 0
    except IndexError:
        return 0

def compute_penalties(row):
    """
    Computes penalty scores matching the Excel sheet logic.
    """
    p_detect = 0
    p_in = 0
    p_out = 0
    p_intype = 0
    p_outtype = 0

    # Rule 1: False Positive or False Negative
    if row['ground_truth'] != row['clone_predict']:
        p_detect = -1
        
    # Rules 2-5: Only evaluate mapping if the model predicted a clone
    if row['clone_predict'] == 1:
        # Cast to string to safely handle potential NaN (empty) values in the CSV
        if str(row['pair_left_in']) != str(row['pair_right_in']):
            p_in = -1
        if str(row['pair_left_out']) != str(row['pair_right_out']):
            p_out = -1
        if str(row['pair_inType_ok']).strip().lower() == 'false':
            p_intype = -1
        if str(row['pair_outType_ok']).strip().lower() == 'false':
            p_outtype = -1
            
    total = p_detect + p_in + p_out + p_intype + p_outtype
    return pd.Series([p_detect, p_in, p_out, p_intype, p_outtype, total])

def load_template(template_name: str) -> str:
    path = Path("template") / template_name
    if not path.is_file():
        print(f"Error: Required template file '{path}' is missing.")
        sys.exit(1)
    return path.read_text(encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Calculate metrics and generate an HTML error report.")
    parser.add_argument("--input", type=str, required=True)
    args = parser.parse_args()
    input_path = Path(args.input)

    try:
        df = pd.read_csv(input_path, sep=None, engine='python')
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    # Calculate GT and Penalties
    df['ground_truth'] = df.apply(get_ground_truth, axis=1)
    
    # Apply individual penalties to distinct columns
    penalty_cols = ['P_Detect', 'P_In', 'P_Out', 'P_InType', 'P_OutType', 'Total_Penalty']
    df[penalty_cols] = df.apply(compute_penalties, axis=1)

    # Standard Metrics
    TP = len(df[(df['ground_truth'] == 1) & (df['clone_predict'] == 1)])
    FP_df = df[(df['ground_truth'] == 0) & (df['clone_predict'] == 1)]
    FN_df = df[(df['ground_truth'] == 1) & (df['clone_predict'] == 0)]
    TN = len(df[(df['ground_truth'] == 0) & (df['clone_predict'] == 0)])

    FP = len(FP_df)
    FN = len(FN_df)

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    overall_penalty = df['Total_Penalty'].sum()
    
    # Calculate average penalty based on ACTUAL clones, avoiding dilution from True Negatives
    actual_clones = len(df[df['ground_truth'] == 1])
    avg_penalty = overall_penalty / actual_clones if actual_clones > 0 else 0.0

    print(f"\n=== Evaluation Results for: {input_path.name} ===")
    print(f"TP: {TP} | FP: {FP} | TN: {TN} | FN: {FN}")
    print(f"Total Penalty: {overall_penalty} (Average per true clone: {avg_penalty:.2f})")

    # Generate HTML
    stage = "unknown"
    if "before" in str(input_path).lower(): stage = "before"
    elif "after" in str(input_path).lower(): stage = "after"
        
    model = input_path.parent.name
    file_stem = input_path.stem[5:] if input_path.stem.startswith("pred_") else input_path.stem
    html_report_path = Path.cwd() / f"report_{stage}_{model}_{file_stem}.html"
    
    # Choose columns to display in the HTML tables
    display_cols = [
        'pair_left_func', 'pair_right_func', 'clone_predict', 'ground_truth', 
        'P_Detect', 'P_In', 'P_Out', 'P_InType', 'P_OutType', 'Total_Penalty'
    ]
    
    fp_html = FP_df[display_cols].to_html(index=False, border=1, classes="data-table") if not FP_df.empty else "<p><i>No False Positives found!</i></p>"
    fn_html = FN_df[display_cols].to_html(index=False, border=1, classes="data-table") if not FN_df.empty else "<p><i>No False Negatives found!</i></p>"
    
    html_template_str = load_template("report_template.html")
    template = Template(html_template_str)
    
    html_content = template.safe_substitute(
        stage=stage.capitalize(),
        model=model,
        input_filename=input_path.name,
        tp=TP, fp=FP, tn=TN, fn=FN,
        precision=f"{precision:.4f}",
        recall=f"{recall:.4f}",
        f1_score=f"{f1_score:.4f}",
        total_penalty=overall_penalty,
        avg_penalty=f"{avg_penalty:.2f}",
        fp_html=fp_html,
        fn_html=fn_html
    )
    
    with open(html_report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"--> Saved Refactoring Compatibility Penalty (RCP) Report to: {html_report_path}\n")

if __name__ == "__main__":
    main()