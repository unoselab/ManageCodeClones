import argparse
import json
import sys
import html
from pathlib import Path

# Import the indexer from your existing code
from index_methods import FileMethodIndex
from util_ast import extract_rw_by_region, REG_PRE, REG_WITHIN, REG_POST

def find_enclosing_method(methods, clone_start: int, clone_end: int):
    """
    Searches through the indexed methods to find the one that completely
    encloses the clone block's line range.
    """
    for qualified_name, record in methods.items():
        m_info = record.method_info
        m_start = m_info.get("start_line")
        m_end = m_info.get("end_line")

        if m_start and m_end:
            if m_start <= clone_start and m_end >= clone_end:
                return record
    return None

def load_template(template_name: str) -> str:
    """Helper function to load HTML templates from the templates directory."""
    path = Path("templates") / template_name
    if not path.is_file():
        print(f"Error: Required template file '{path}' is missing.")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


# Helper function to format sets safely for HTML
def fmt_set(var_set):
    return html.escape(", ".join(sorted(var_set))) if var_set else "<span style='color:#aaa'>None</span>"

def fmt_math_set(s):
    return "{" + html.escape(", ".join(sorted(s))) + "}" if s else "{}"

def process_clone_jsonl(jsonl_path: str, base_dir: str, output_html: str):
    """
    Reads a JSONL file, identifies enclosing methods, and writes an HTML visualization.
    """
    jsonl_file = Path(jsonl_path)
    base_path = Path(base_dir)

    if not jsonl_file.is_file():
        print(f"Error: The file '{jsonl_path}' does not exist.")
        sys.exit(1)

    # Load HTML templates
    tmpl_header = load_template("header.html")
    tmpl_footer = load_template("footer.html")
    tmpl_class_start = load_template("class_start.html")
    tmpl_instance_meta = load_template("instance_meta.html")
    tmpl_instance_error = load_template("instance_error.html")

    indexer = FileMethodIndex()
    html_content = [tmpl_header]
    
    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
                
            try:
                clone_class = json.loads(line)
            except json.JSONDecodeError:
                continue

            class_id = clone_class.get("classid")
            sources = clone_class.get("sources", [])
            
            print(f"--- Processing Clone Class ID: {class_id} ---")
            
            # Start a new Clone Class block using the template
            html_content.append(tmpl_class_start.format(
                class_id=class_id, 
                instance_count=len(sources)
            ))

            for source in sources:
                rel_file = source.get("file")
                range_str = source.get("range")
                func_id = source.get("func_id")
                
                if not rel_file or not range_str:
                    continue

                try:
                    c_start_str, c_end_str = range_str.split('-')
                    clone_start, clone_end = int(c_start_str), int(c_end_str)
                except ValueError:
                    continue

                full_file_path = base_path / rel_file
                
                if full_file_path.is_file():
                    try:
                        parser, methods = indexer.get(str(full_file_path))
                        enclosing_record = find_enclosing_method(methods, clone_start, clone_end)
                        
                        if enclosing_record:
                            m_info = enclosing_record.method_info
                            m_start = m_info.get("start_line")
                            m_end = m_info.get("end_line")

                            # Extract and categorize local variables
                            raw_locals = m_info.get("local_variables", [])
                            pre_locals, clone_locals, post_locals = [], [], []
                            
                            for var_type, var_name, line_num in raw_locals:
                                # Add the line number to the formatted string!
                                formatted_var = f"{var_type} {var_name} (Line {line_num})"
                                
                                if line_num < clone_start:
                                    pre_locals.append(formatted_var)
                                elif clone_start <= line_num <= clone_end:
                                    clone_locals.append(formatted_var)
                                else:
                                    post_locals.append(formatted_var)


                            # --- Run Data-Flow Analysis ---
                            rw_regions = extract_rw_by_region(
                                parser, 
                                enclosing_record.node, 
                                clone_start, 
                                clone_end, 
                                only_method_scope=True
                            )
                            
                            # --- 1. Build a Type Lookup Dictionary ---
                            type_map = {}
                            
                            # Parse original method parameters (e.g., "String name" -> {"name": "String"})
                            for param_str in m_info.get("parameters", []):
                                parts = param_str.strip().rsplit(" ", 1)
                                if len(parts) == 2:
                                    type_map[parts[1]] = parts[0]
                                    
                            # Parse local variables
                            for var_type, var_name, _ in m_info.get("local_variables", []):
                                type_map[var_name] = var_type


                            # --- 2. Synthesize the Extracted Parameters ---
                            extracted_param_list = []
                            seen_params = set()
                            
                            for var_with_line in sorted(rw_regions.vr[REG_WITHIN]):
                                base_name = var_with_line.split(" (Line")[0].strip()
                                
                                # Deduplicate: Only add it to the signature if we haven't seen it yet
                                if base_name not in seen_params:
                                    var_type = type_map.get(base_name, "Object")
                                    extracted_param_list.append(f"{var_type} {base_name}")
                                    seen_params.add(base_name)

                            extracted_params_str = html.escape(", ".join(extracted_param_list))

                            # --- 3. Synthesize the Math Derivation ---
                            # Def_before(i) = Method parameters + Local variables declared before the clone
                            # Use type_map keys that came from parameters to get just the base names
                            def_before_set = set()
                            for param_str in m_info.get("parameters", []):
                                parts = param_str.strip().rsplit(" ", 1)
                                if len(parts) == 2:
                                    def_before_set.add(parts[1]) # Add just the variable name

                            for var_type, var_name, line_num in m_info.get("local_variables", []):
                                if line_num < clone_start:
                                    def_before_set.add(var_name)
                                    
                            # Use(i) = The base names of variables read in the clone
                            use_set = seen_params 
                            
                            # In(i) = Use(i) ∩ Def_before(i)
                            in_set = use_set.intersection(def_before_set)

                            # Add instance metadata using the template
                            html_content.append(tmpl_instance_meta.format(
                                func_id=func_id,
                                rel_file=rel_file,
                                range_str=range_str,
                                method_qualified=m_info.get("qualified"),
                                m_start=m_start,
                                m_end=m_end,
                                extracted_params=extracted_params_str,
                                use_set_str=fmt_math_set(use_set),          # NEW
                                def_set_str=fmt_math_set(def_before_set),   # NEW
                                in_set_str=fmt_math_set(in_set),            # NEW
                                vr_pre=fmt_set(rw_regions.vr[REG_PRE]),
                                vr_within=fmt_set(rw_regions.vr[REG_WITHIN]),
                                vr_post=fmt_set(rw_regions.vr[REG_POST]),
                                vw_pre=fmt_set(rw_regions.vw[REG_PRE]),
                                vw_within=fmt_set(rw_regions.vw[REG_WITHIN]),
                                vw_post=fmt_set(rw_regions.vw[REG_POST])
                            ))


                            # Extract source and color it
                            method_source = parser.text_of(enclosing_record.node)
                            source_lines = method_source.split('\n')
                            
                            in_signature = True
                            
                            for i, raw_line in enumerate(source_lines):
                                current_line_num = m_start + i
                                escaped_line = html.escape(raw_line)
                                
                                # Determine the section of the code
                                if clone_start <= current_line_num <= clone_end:
                                    line_class = "in-clone"
                                    in_signature = False # Safety catch: clones are in the body
                                elif current_line_num < clone_start:
                                    if in_signature:
                                        line_class = "method-signature"
                                        # The signature usually ends at the first opening brace
                                        if '{' in raw_line:
                                            in_signature = False
                                    else:
                                        line_class = "before-clone"
                                else:
                                    line_class = "after-clone"

                                # Inject the line number span right before the code span
                                html_content.append(
                                    f'<span class="line-number">{current_line_num}</span>'
                                    f'<span class="{line_class}">{escaped_line}</span>\n'
                                )

                            # Close the tags opened in tmpl_instance_meta
                            html_content.append('</code></pre>\n</div>\n')
                            print(f"  > Generated HTML for {func_id} in {m_info.get('qualified')}")
                        else:
                            html_content.append(tmpl_instance_error.format(
                                func_id=func_id, rel_file=rel_file, range_str=range_str,
                                error_msg="No enclosing method found bounds."
                            ))
                    except Exception as e:
                        html_content.append(tmpl_instance_error.format(
                            func_id=func_id, rel_file=rel_file, range_str=range_str,
                            error_msg=f"Error parsing Java file: {e}"
                        ))
                else:
                    html_content.append(tmpl_instance_error.format(
                        func_id=func_id, rel_file=rel_file, range_str=range_str,
                        error_msg="File not found on disk."
                    ))
                
            # Close the Clone Class block
            html_content.append('</div>\n') 

    html_content.append(tmpl_footer)

    # Write the output file
    output_path = Path(output_html)
    output_path.write_text("".join(html_content), encoding="utf-8")
    print(f"\nSuccessfully wrote visualization to: {output_path.absolute()}")

def main():
    parser = argparse.ArgumentParser(
        description="Find enclosing Java methods for clone blocks and visualize them in HTML."
    )
    parser.add_argument("--jsonl", type=str, required=True, help="Path to the JSONL file.")
    parser.add_argument("--base-dir", type=str, default=".", help="Base directory to resolve the relative file paths.")
    parser.add_argument("--output", type=str, default="camel_clone.html", help="Output HTML file name.")

    args = parser.parse_args()
    process_clone_jsonl(args.jsonl, args.base_dir, args.output)

if __name__ == "__main__":
    main()