import re
import argparse
import json
import sys
import html
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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

def _range_or_none(start: int, end: int) -> Optional[str]:
    """Return 'start-end' if non-empty, else None (for empty regions)."""
    return f"{start}-{end}" if start <= end else None

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


def fmt_math_set_for_html(s):
    return "{" + html.escape(", ".join(sorted(s))) + "}" if s else "{}"


def _split_var_and_line(s: str) -> Tuple[str, Optional[int]]:
    """
    Input example: "roles (Line 186)" or "roles"
    Returns: ("roles", 186) or ("roles", None)
    """
    m = re.match(r"^(.*?)\s*\(Line\s+(\d+)\)\s*$", s.strip())
    if not m:
        return s.strip(), None
    return m.group(1).strip(), int(m.group(2))


def _base_names_from_with_line(items) -> List[str]:
    """
    Convert iterable of "x (Line N)" to sorted unique base names.
    """
    bases = set()
    for it in items or []:
        b, _ = _split_var_and_line(str(it))
        if b:
            bases.add(b)
    return sorted(bases)


def _sorted_list(items) -> List[str]:
    """
    Stable ordering for JSONL output.
    Prefer sorting by (base_name, line_no) when line exists.
    """
    parsed = []
    for it in items or []:
        s = str(it)
        b, ln = _split_var_and_line(s)
        parsed.append((b, ln if ln is not None else 10**9, s))
    parsed.sort(key=lambda t: (t[0], t[1], t[2]))
    return [t[2] for t in parsed]


def _build_type_map(m_info: Dict[str, Any]) -> Dict[str, str]:
    """
    Build var_name -> var_type from parameters + local variables.
    """
    type_map: Dict[str, str] = {}

    # Parse original method parameters (e.g., "Set<String> roles" -> {"roles": "Set<String>"})
    for param_str in m_info.get("parameters", []) or []:
        parts = str(param_str).strip().rsplit(" ", 1)
        if len(parts) == 2:
            type_map[parts[1]] = parts[0]

    # Parse local variables list: (var_type, var_name, line_num)
    for var_type, var_name, _ in m_info.get("local_variables", []) or []:
        type_map[str(var_name)] = str(var_type)

    return type_map


def _derive_def_before(m_info: Dict[str, Any], clone_start: int) -> List[str]:
    """
    Def_before(i) = method parameters + locals declared before clone.
    Returns sorted unique base names.
    """
    s = set()

    for param_str in m_info.get("parameters", []) or []:
        parts = str(param_str).strip().rsplit(" ", 1)
        if len(parts) == 2:
            s.add(parts[1])

    for var_type, var_name, line_num in m_info.get("local_variables", []) or []:
        try:
            ln = int(line_num)
        except Exception:
            continue
        if ln < clone_start:
            s.add(str(var_name))

    return sorted(s)


def _derive_def_within(rw_regions) -> List[str]:
    """
    Def_within(i) = variables written within clone (base names).
    """
    return _base_names_from_with_line(rw_regions.vw.get(REG_WITHIN, set()))


def _derive_use_after(rw_regions) -> List[str]:
    """
    Use_after(i) = variables read after clone (base names).
    """
    return _base_names_from_with_line(rw_regions.vr.get(REG_POST, set()))


def _derive_use_within(rw_regions) -> List[str]:
    """
    Use(i) = variables read within clone (base names).
    """
    return _base_names_from_with_line(rw_regions.vr.get(REG_WITHIN, set()))


def _infer_signature(
    in_vars: List[str],
    out_vars: List[str],
    type_map: Dict[str, str],
) -> Tuple[str, str, List[str], List[str]]:
    """
    Returns:
      return_type_str,
      extracted_signature_str,
      in_types,
      out_types
    """
    in_types = [type_map.get(v, "Object") for v in in_vars]

    if len(out_vars) == 0:
        return_type_str = "void"
        out_types: List[str] = []
    elif len(out_vars) == 1:
        t = type_map.get(out_vars[0], "Object")
        return_type_str = t
        out_types = [t]
    else:
        out_types = [type_map.get(v, "Object") for v in out_vars]
        return_type_str = "Tuple<" + ", ".join(out_types) + ">"

    extracted_param_list = [f"{type_map.get(v, 'Object')} {v}" for v in in_vars]
    params_str = ", ".join(extracted_param_list)

    extracted_signature_str = f"public {return_type_str} extractedClone({params_str})"
    return return_type_str, extracted_signature_str, in_types, out_types


def process_clone_jsonl(jsonl_path: str, base_dir: str, output_html: str, output_jsonl: str):
    """
    Reads a JSONL file, identifies enclosing methods, writes:
      1) an HTML visualization
      2) an augmented JSONL with analysis fields
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

    out_jsonl_path = Path(output_jsonl)
    out_jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    written_classes = 0
    written_sources = 0

    with open(jsonl_file, "r", encoding="utf-8") as f_in, open(out_jsonl_path, "w", encoding="utf-8") as f_out:
        for line_num, line in enumerate(f_in, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                clone_class = json.loads(line)
            except json.JSONDecodeError:
                continue

            class_id = clone_class.get("classid")
            sources = clone_class.get("sources", []) or []

            print(f"--- Processing Clone Class ID: {class_id} ---")

            # HTML: start class block
            html_content.append(
                tmpl_class_start.format(
                    class_id=class_id,
                    instance_count=len(sources),
                )
            )

            # JSONL: build augmented class record
            augmented_class = dict(clone_class)
            augmented_sources: List[Dict[str, Any]] = []

            for source in sources:
                src_aug = dict(source)  # keep original fields
                rel_file = source.get("file")
                range_str = source.get("range")
                func_id = source.get("func_id")

                if not rel_file or not range_str:
                    augmented_sources.append(src_aug)
                    continue

                try:
                    c_start_str, c_end_str = str(range_str).split("-")
                    clone_start, clone_end = int(c_start_str), int(c_end_str)
                except ValueError:
                    augmented_sources.append(src_aug)
                    continue

                full_file_path = base_path / rel_file

                if not full_file_path.is_file():
                    html_content.append(
                        tmpl_instance_error.format(
                            func_id=func_id,
                            rel_file=rel_file,
                            range_str=range_str,
                            error_msg="File not found on disk.",
                        )
                    )
                    src_aug["analysis_error"] = "File not found on disk."
                    augmented_sources.append(src_aug)
                    continue

                try:
                    parser, methods = indexer.get(str(full_file_path))
                    enclosing_record = find_enclosing_method(methods, clone_start, clone_end)

                    if not enclosing_record:
                        html_content.append(
                            tmpl_instance_error.format(
                                func_id=func_id,
                                rel_file=rel_file,
                                range_str=range_str,
                                error_msg="No enclosing method found bounds.",
                            )
                        )
                        src_aug["analysis_error"] = "No enclosing method found bounds."
                        augmented_sources.append(src_aug)
                        continue

                    m_info = enclosing_record.method_info
                    m_start = int(m_info.get("start_line"))
                    m_end = int(m_info.get("end_line"))

                    # --- Run Data-Flow Analysis ---
                    rw_regions = extract_rw_by_region(
                        parser,
                        enclosing_record.node,
                        clone_start,
                        clone_end,
                        only_method_scope=True,
                    )

                    # --- Build Type Lookup ---
                    type_map = _build_type_map(m_info)

                    # --- Derivation Sets ---
                    use_set = _derive_use_within(rw_regions)  # Use(i)
                    def_before_set = _derive_def_before(m_info, clone_start)  # Defbefore(i)
                    in_set = sorted(set(use_set).intersection(def_before_set))  # In(i)

                    def_within_set = _derive_def_within(rw_regions)  # Defwithin(i)
                    use_after_set = _derive_use_after(rw_regions)  # Useafter(i)
                    out_set = sorted(set(def_within_set).intersection(use_after_set))  # Out(i)

                    # --- Signature & types ---
                    return_type_str, extracted_sig, in_types, out_types = _infer_signature(
                        in_vars=in_set,
                        out_vars=out_set,
                        type_map=type_map,
                    )

                    # --- Region ranges ---
                    pre_rng = _range_or_none(m_start, clone_start - 1)
                    within_rng = _range_or_none(clone_start, clone_end)
                    post_rng = _range_or_none(clone_end + 1, m_end)

                    src_aug["region_ranges"] = {
                        "CloneRegion_pre": pre_rng,
                        "CloneRegion_within": within_rng,
                        "CloneRegion_post": post_rng,
                    }

                    # --- CORRECTED IS_FULL_FUNCTION_CLONE LOGIC ---
                    is_full = (clone_end == m_end) and ((clone_start - m_start) <= 3)
                    src_aug["is_full_function_clone"] = is_full

                    # --- Enclosing function code ---
                    method_source = parser.text_of(enclosing_record.node)

                    # --- Remove annotation lines but do NOT collapse blank lines ---
                    method_source = re.sub(
                        r'^\s*@\w+(?:\([^)]*\))?\s*$',
                        '',
                        method_source,
                        flags=re.MULTILINE
                    )

                    src_aug["enclosing_function"] = {
                        "qualified_name": m_info.get("qualified") or m_info.get("qualified_name") or m_info.get("name"),
                        "fun_range": f"{m_start}-{m_end}",
                        "fun_nlines": int(m_end - m_start + 1),
                        "func_code": method_source,
                    }

                    # --- Variables read/written grouped ---
                    vr_pre = _sorted_list(rw_regions.vr.get(REG_PRE, set()))
                    vr_within = _sorted_list(rw_regions.vr.get(REG_WITHIN, set()))
                    vr_post = _sorted_list(rw_regions.vr.get(REG_POST, set()))
                    vw_pre = _sorted_list(rw_regions.vw.get(REG_PRE, set()))
                    vw_within = _sorted_list(rw_regions.vw.get(REG_WITHIN, set()))
                    vw_post = _sorted_list(rw_regions.vw.get(REG_POST, set()))

                    src_aug["Variables Read (V_r)"] = {
                        "Pre": vr_pre if vr_pre else None,
                        "Within (Inputs!)": vr_within if vr_within else None,
                        "Post": vr_post if vr_post else None,
                    }
                    src_aug["Variables Written (V_w)"] = {
                        "Pre": vw_pre if vw_pre else None,
                        "Within": vw_within if vw_within else None,
                        "Post": vw_post if vw_post else None,
                    }

                    # --- CORRECTED NESTED STRUCTURE ---
                    src_aug["In"] = {
                        "In(i)": in_set,
                        "InType": {
                            "InType": in_types,
                            "Use(i)": use_set,
                            "Defbefore(i)": def_before_set,
                        },
                    }
                    src_aug["Out"] = {
                        "Out(i)": out_set,
                        "OutType": out_types,
                        "Defwithin(i)": def_within_set,
                        "Useafter(i)": use_after_set,
                    }

                    # Remove old keys if present
                    src_aug.pop("InType", None)
                    src_aug.pop("OutType", None)

                    src_aug["Extracted Signature"] = extracted_sig
                    src_aug["ReturnType"] = return_type_str

                    # --------------------------
                    # HTML emission
                    # --------------------------
                    extracted_params_str = html.escape(
                        ", ".join([f"{type_map.get(v, 'Object')} {v}" for v in in_set])
                    )

                    html_content.append(
                        tmpl_instance_meta.format(
                            func_id=func_id,
                            rel_file=rel_file,
                            range_str=range_str,
                            method_qualified=m_info.get("qualified"),
                            m_start=m_start,
                            m_end=m_end,
                            return_type=html.escape(return_type_str),
                            extracted_params=extracted_params_str,
                            use_set_str=fmt_math_set_for_html(set(use_set)),
                            def_set_str=fmt_math_set_for_html(set(def_before_set)),
                            in_set_str=fmt_math_set_for_html(set(in_set)),
                            def_within_str=fmt_math_set_for_html(set(def_within_set)),
                            use_after_str=fmt_math_set_for_html(set(use_after_set)),
                            out_set_str=fmt_math_set_for_html(set(out_set)),
                            vr_pre=fmt_set(set(vr_pre)),
                            vr_within=fmt_set(set(vr_within)),
                            vr_post=fmt_set(set(vr_post)),
                            vw_pre=fmt_set(set(vw_pre)),
                            vw_within=fmt_set(set(vw_within)),
                            vw_post=fmt_set(set(vw_post)),
                        )
                    )

                    # Render and highlight Use(i) within clone
                    source_lines = method_source.split("\n")
                    in_signature = True

                    use_set_for_highlight = set(use_set)

                    for i, raw_line in enumerate(source_lines):
                        current_line_num = m_start + i
                        escaped_line = html.escape(raw_line)

                        if clone_start <= current_line_num <= clone_end:
                            line_class = "in-clone"
                            in_signature = False

                            for var in sorted(use_set_for_highlight, key=len, reverse=True):
                                pattern = rf"\b({re.escape(var)})\b"
                                highlight_tag = (
                                    r'<span style="background-color: #ffeb3b; color: #b30000; '
                                    r'border-radius: 2px; padding: 0 2px;">\1</span>'
                                )
                                escaped_line = re.sub(pattern, highlight_tag, escaped_line)

                        elif current_line_num < clone_start:
                            if in_signature:
                                line_class = "method-signature"
                                if "{" in raw_line:
                                    in_signature = False
                            else:
                                line_class = "before-clone"
                        else:
                            line_class = "after-clone"

                        html_content.append(
                            f'<span class="line-number">{current_line_num}</span>'
                            f'<span class="{line_class}">{escaped_line}</span>\n'
                        )

                    html_content.append("</code></pre>\n</div>\n")

                    print(f"  > Generated HTML + JSONL analysis for {func_id} in {m_info.get('qualified')}")
                    augmented_sources.append(src_aug)
                    written_sources += 1

                except Exception as e:
                    html_content.append(
                        tmpl_instance_error.format(
                            func_id=func_id,
                            rel_file=rel_file,
                            range_str=range_str,
                            error_msg=f"Error parsing Java file: {e}",
                        )
                    )
                    src_aug["analysis_error"] = f"Error parsing Java file: {e}"
                    augmented_sources.append(src_aug)

            # close HTML class block
            html_content.append("</div>\n")

            augmented_class["sources"] = augmented_sources
            f_out.write(json.dumps(augmented_class, ensure_ascii=False) + "\n")
            written_classes += 1

    html_content.append(tmpl_footer)

    # Write HTML output
    output_path = Path(output_html)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(html_content), encoding="utf-8")

    print(f"\nSuccessfully wrote visualization to: {output_path.absolute()}")
    print(f"Successfully wrote augmented JSONL to: {out_jsonl_path.absolute()}")
    print(f"Stats: classes={written_classes}, sources_analyzed={written_sources}")


def main():
    parser = argparse.ArgumentParser(
        description="Find enclosing Java methods for clone blocks, visualize in HTML, and export augmented JSONL."
    )

    parser.add_argument(
        "--jsonl",
        type=str,
        required=True,
        help="Path to the input JSONL file."
    )

    parser.add_argument(
        "--base-dir",
        type=str,
        default=".",
        help="Base directory to resolve the relative file paths."
    )

    parser.add_argument(
        "--output",
        type=str,
        default="clone_visualization.html",
        help="Output HTML file name."
    )

    parser.add_argument(
        "--out-jsonl",
        dest="out_jsonl",
        type=str,
        default=None,
        help="Output augmented JSONL file name (default: derived from --output).",
    )

    args = parser.parse_args()

    out_jsonl = args.out_jsonl
    if not out_jsonl:
        out_jsonl = str(Path(args.output).with_suffix(".jsonl"))

    process_clone_jsonl(args.jsonl, args.base_dir, args.output, out_jsonl)


if __name__ == "__main__":
    main()