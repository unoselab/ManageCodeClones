from __future__ import annotations

import argparse
import json
import keyword
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from python_treesitter_parser import PythonTreeSitterParser
from util_ast_python import enclosing_class_node, iter_descendants


# ============================================================
# Data model
# ============================================================


@dataclass(frozen=True)
class CloneVariable:
    name: str
    type_name: str


@dataclass(frozen=True)
class EnclosingFunction:
    qualified_name: str
    fun_range: str
    fun_nlines: int
    func_code: str


@dataclass(frozen=True)
class CloneSource:
    file: str
    clone_range: str
    nlines: int
    code: str
    func_id: str
    in_vars: List[CloneVariable]
    out_vars: List[CloneVariable]
    defbefore_vars: List[str]
    enclosing_function: EnclosingFunction
    extracted_signature_hint: Optional[str] = None
    return_type_hint: Optional[str] = None
    ground_truth_after_vscode_ref: Optional[dict] = None


@dataclass(frozen=True)
class CloneClassCase:
    classid: str
    nclones: int
    #similarity: float
    project: str
    same_file: int
    actual_label: int
    clone_predict: int
    clone_predict_after_adapt: int
    refactorable: int
    inspection_case: str
    sources: List[CloneSource]


@dataclass(frozen=True)
class LineSpan:
    start_line: int
    end_line: int


@dataclass(frozen=True)
class ExtractionSignature:
    method_name: str
    is_static: bool
    parameters: List[Tuple[str, str]]  # (type_name, param_name)


@dataclass(frozen=True)
class CloneRewrite:
    func_id: str
    file: str
    clone_range: str
    replacement_code: str


@dataclass(frozen=True)
class RewriteArtifact:
    file: str
    output_path: str
    inserted_extracted_method: bool
    rewritten_source: str


@dataclass(frozen=True)
class RefactorResult:
    extracted_method_code: str
    extracted_signature: ExtractionSignature
    replacements: List[CloneRewrite]
    updated_files: List[RewriteArtifact]
    diagnostics: List[str]


# ============================================================
# Generic helpers
# ============================================================


RANGE_RE = re.compile(r"^(\d+)-(\d+)$")

PYTHON_KEYWORDS = set(keyword.kwlist) | {"True", "False", "None"}

METHOD_NODE_TYPES = {"function_definition"}
CLASS_NODE_TYPES = {"class_definition"}
IF_NODE_TYPES = {"if_statement"}


def parse_range(range_text: str) -> LineSpan:
    m = RANGE_RE.match(range_text.strip())
    if not m:
        raise ValueError(f"Invalid range: {range_text}")
    start_line, end_line = int(m.group(1)), int(m.group(2))
    if start_line > end_line:
        raise ValueError(f"Invalid line range order: {range_text}")
    return LineSpan(start_line, end_line)


def line_offsets(text: str) -> List[int]:
    offsets = [0]
    running = 0
    for line in text.splitlines(keepends=True):
        running += len(line)
        offsets.append(running)
    return offsets


def line_span_to_offsets(text: str, span: LineSpan) -> Tuple[int, int]:
    offsets = line_offsets(text)
    if span.end_line > len(offsets) - 1:
        raise ValueError(f"Range {span.start_line}-{span.end_line} exceeds file length")
    return offsets[span.start_line - 1], offsets[span.end_line]


def common_indent(lines: Sequence[str]) -> str:
    indents: List[str] = []
    for line in lines:
        if line.strip():
            indents.append(re.match(r"[ \t]*", line).group(0))
    if not indents:
        return ""
    prefix = indents[0]
    for indent in indents[1:]:
        while not indent.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                return ""
    return prefix


def dedent_block(text: str) -> str:
    lines = text.splitlines()
    prefix = common_indent(lines)
    if not prefix:
        return text
    return "\n".join(line[len(prefix):] if line.startswith(prefix) else line for line in lines)


def indent_block(text: str, indent: str) -> str:
    return "\n".join((indent + line if line.strip() else line) for line in text.splitlines())


def apply_replacements(source: str, replacements: Sequence[Tuple[Tuple[int, int], str]]) -> str:
    out = source
    for (start_offset, end_offset), replacement in sorted(replacements, key=lambda x: x[0][0], reverse=True):
        out = out[:start_offset] + replacement + out[end_offset:]
    return out


def sanitize_identifier(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned:
        cleaned = "extracted"
    if cleaned[0].isdigit():
        cleaned = f"extracted_{cleaned}"
    if keyword.iskeyword(cleaned):
        cleaned += "_"
    return cleaned


def choose_unique_method_name(classid: str) -> str:
    return "extracted"


def normalize_type(type_name: str) -> str:
    t = (type_name or "Any").strip()
    return t if t else "Any"


def trim_selected_range(file_text: str, start_offset: int, end_offset: int) -> Tuple[int, int]:
    while start_offset < end_offset and file_text[start_offset].isspace():
        start_offset += 1
    while end_offset > start_offset and file_text[end_offset - 1].isspace():
        end_offset -= 1
    return start_offset, end_offset


def range_matches_node(node, selected_start: int, selected_end: int) -> bool:
    return node is not None and node.start_byte == selected_start and node.end_byte == selected_end


def method_header_from_code(func_code: str) -> str:
    for line in func_code.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def infer_is_static(func_code: str) -> bool:
    lines = [line.strip() for line in func_code.splitlines() if line.strip()]
    for i, line in enumerate(lines[:3]):
        if line.startswith("@staticmethod"):
            return True
        if line.startswith("def "):
            break
    return False


def has_self_parameter(func_code: str) -> bool:
    m = re.search(r"def\s+\w+\s*\((.*?)\)\s*:", func_code, flags=re.DOTALL)
    if not m:
        return False
    params_blob = m.group(1).strip()
    if not params_blob:
        return False
    first = params_blob.split(",")[0].strip()
    first = first.split(":")[0].split("=")[0].strip()
    return first == "self"


def strip_comments_and_strings(code: str) -> str:
    code = re.sub(r'"""[\s\S]*?"""', '""', code)
    code = re.sub(r"'''[\s\S]*?'''", "''", code)
    code = re.sub(r"#.*", "", code)
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
    code = re.sub(r"'(?:\\.|[^'\\])*'", "''", code)
    return code


def extract_identifier_tokens(code: str) -> List[str]:
    return re.findall(r"\b[A-Za-z_]\w*\b", code)


def likely_type_name(name: str) -> bool:
    return bool(name and name[0].isupper())


def extract_declared_locals_python(code: str) -> set[str]:
    declared = set()

    patterns = [
        r"^\s*([A-Za-z_]\w*)\s*=",
        r"^\s*([A-Za-z_]\w*)\s*:\s*[^=]+(?:=.+)?$",
        r"^\s*for\s+([A-Za-z_]\w*)\s+in\b",
        r"^\s*except\b.*\bas\s+([A-Za-z_]\w*)\s*:",
        r"^\s*with\b.*\bas\s+([A-Za-z_]\w*)\s*:",
    ]

    for line in code.splitlines():
        for pat in patterns:
            m = re.match(pat, line)
            if m:
                declared.add(m.group(1))
    return declared


def extract_method_local_declarations(code: str) -> set[str]:
    return extract_declared_locals_python(code)


def infer_variable_types_from_function(func_code: str) -> Dict[str, str]:
    code = strip_comments_and_strings(func_code)
    result: Dict[str, str] = {}

    # parameters
    m = re.search(r"def\s+\w+\s*\((.*?)\)\s*(?:->\s*([A-Za-z_][\w\[\], .]*)\s*)?:", code, flags=re.DOTALL)
    if m:
        params_blob = m.group(1).strip()
        if params_blob:
            parts = [p.strip() for p in params_blob.split(",")]
            for part in parts:
                part = part.lstrip("*")
                pm = re.match(r"([A-Za-z_]\w*)(?:\s*:\s*([^=]+))?(?:\s*=.*)?$", part)
                if pm:
                    name = pm.group(1)
                    type_name = pm.group(2).strip() if pm.group(2) else "Any"
                    result[name] = type_name

    # local typed assignments
    for line in code.splitlines():
        m1 = re.match(r"^\s*([A-Za-z_]\w*)\s*:\s*([^=]+)(?:=.*)?$", line)
        if m1:
            result.setdefault(m1.group(1), m1.group(2).strip())
            continue
        m2 = re.match(r"^\s*([A-Za-z_]\w*)\s*=", line)
        if m2:
            result.setdefault(m2.group(1), "Any")

    return result


def basic_free_variable_check(body: str, parameter_names: set[str], local_declared: set[str]) -> List[str]:
    scan_body = strip_comments_and_strings(body)
    tokens = extract_identifier_tokens(scan_body)

    ignore = set(PYTHON_KEYWORDS) | {"self", "cls"}

    free: List[str] = []
    seen = set()

    for token in tokens:
        if token in ignore:
            continue
        if token in parameter_names:
            continue
        if token in local_declared:
            continue
        if likely_type_name(token):
            continue

        if re.search(rf"\b{re.escape(token)}\s*\(", scan_body):
            continue

        if re.search(rf"\.\s*{re.escape(token)}\b", scan_body):
            continue

        if token in seen:
            continue
        seen.add(token)
        free.append(token)

    return free


def infer_extra_vars_for_source(body: str, src: CloneSource, existing_param_names: set[str]) -> List[str]:
    local_declared = extract_method_local_declarations(body)
    free_vars = basic_free_variable_check(body, existing_param_names, local_declared)
    type_env = infer_variable_types_from_function(src.enclosing_function.func_code)

    result: List[str] = []
    for name in free_vars:
        if src.defbefore_vars and name not in src.defbefore_vars and name not in type_env:
            continue
        result.append(name)
    return result


# ============================================================
# Input loading
# ============================================================


class CloneCaseLoader:
    @staticmethod
    def _parse_variables(entry: dict, key_name: str) -> List[CloneVariable]:
        names = entry.get(key_name, [])
        if key_name == "In(i)":
            types = entry.get("InType", {}).get("InType", [])
        else:
            types = entry.get("OutType", [])
        result = []
        for idx, name in enumerate(names):
            type_name = types[idx] if idx < len(types) else "Any"
            result.append(CloneVariable(name=name, type_name=normalize_type(type_name)))
        return result

    @classmethod
    def from_json(cls, payload: dict) -> CloneClassCase:
        sources: List[CloneSource] = []
        for source in payload["sources"]:
            enclosing = source["enclosing_function"]
            sources.append(
                CloneSource(
                    file=source["file"],
                    clone_range=source["range"],
                    nlines=int(source.get("nlines", 0)),
                    code=source["code"],
                    func_id=source["func_id"],
                    in_vars=cls._parse_variables(source.get("In", {}), "In(i)"),
                    out_vars=cls._parse_variables(source.get("Out", {}), "Out(i)"),
                    defbefore_vars=source.get("In", {}).get("InType", {}).get("Defbefore(i)", []),
                    enclosing_function=EnclosingFunction(
                        qualified_name=enclosing["qualified_name"],
                        fun_range=enclosing["fun_range"],
                        fun_nlines=int(enclosing.get("fun_nlines", 0)),
                        func_code=enclosing["func_code"],
                    ),
                    extracted_signature_hint=source.get("Extracted Signature"),
                    return_type_hint=source.get("ReturnType"),
                    ground_truth_after_vscode_ref=source.get("ground_truth_after_VSCode_ref"),
                )
            )
        return CloneClassCase(
            classid=payload["classid"],
            nclones=int(payload["nclones"]),
            #similarity=float(payload.get("similarity", 0.0)),
            project=payload.get("project", ""),
            same_file=int(payload.get("same_file", 0)),
            actual_label=int(payload.get("actual_label", 0)),
            clone_predict=int(payload.get("clone_predict", 0)),
            clone_predict_after_adapt=int(payload.get("clone_predict_after_adapt", 0)),
            refactorable=int(payload.get("Refactorable", 0)),
            inspection_case=payload.get("inspection_case", ""),
            sources=sources,
        )


# ============================================================
# AST location services
# ============================================================


class CloneLocator:
    def __init__(self, source_root: Path):
        self.source_root = source_root

    def absolute_file(self, relative_file: str) -> Path:
        return self.source_root / relative_file

    def load_source(self, relative_file: str) -> str:
        return self.absolute_file(relative_file).read_text(encoding="utf-8", errors="replace")

    def find_method_node(self, source: CloneSource):
        file_path = self.absolute_file(source.file)
        parser = PythonTreeSitterParser(file_path.read_text(encoding="utf-8", errors="replace"))
        method_span = parse_range(source.enclosing_function.fun_range)

        for node in iter_descendants(parser.root):
            if node.type not in METHOD_NODE_TYPES:
                continue
            start_line = node.start_point[0] + 1
            if start_line != method_span.start_line:
                continue

            name_node = node.child_by_field_name("name")
            qname = parser.text_of(name_node) if name_node else ""
            if source.enclosing_function.qualified_name.endswith(qname):
                return parser, node

        raise KeyError(f"Method not found for {source.enclosing_function.qualified_name} @ line {method_span.start_line}")

    def find_enclosing_class_node(self, source: CloneSource):
        parser, method_node = self.find_method_node(source)
        class_node = enclosing_class_node(method_node)
        return parser, class_node

    def clone_offsets(self, file_text: str, clone_range: str) -> Tuple[int, int]:
        return line_span_to_offsets(file_text, parse_range(clone_range))


# ============================================================
# Signature synthesis
# ============================================================


class SignatureSynthesizer:
    def __init__(self, case: CloneClassCase):
        self.case = case

    def _base_parameters(self) -> Tuple[List[Tuple[str, str]], bool]:
        first_src = self.case.sources[0]
        is_static = infer_is_static(first_src.enclosing_function.func_code)

        common_names = {v.name for v in first_src.in_vars}
        per_clone_types: Dict[str, str] = {v.name: normalize_type(v.type_name) for v in first_src.in_vars}

        for src in self.case.sources[1:]:
            src_names = {v.name for v in src.in_vars}
            common_names &= src_names

        parameters: List[Tuple[str, str]] = []
        used_names: set[str] = set()

        for var in first_src.in_vars:
            if var.name not in common_names:
                continue
            if not is_static and var.name == "self":
                continue
            param_name = sanitize_identifier(var.name)
            if param_name in used_names:
                suffix = 2
                base = param_name
                while f"{base}{suffix}" in used_names:
                    suffix += 1
                param_name = f"{base}{suffix}"
            used_names.add(param_name)
            parameters.append((normalize_type(per_clone_types[var.name]), param_name))

        return parameters, is_static

    def _infer_extra_parameters(self, body: str, existing_params: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        first_src = self.case.sources[0]

        param_names = {name for _, name in existing_params}
        local_declared = extract_method_local_declarations(body)
        free_vars = basic_free_variable_check(body, param_names, local_declared)
        type_env = infer_variable_types_from_function(first_src.enclosing_function.func_code)

        existing_param_names = {name for _, name in existing_params}
        extra: List[Tuple[str, str]] = []

        for name in free_vars:
            sanitized = sanitize_identifier(name)
            if sanitized in existing_param_names:
                continue
            if name == "self":
                continue
            if first_src.defbefore_vars and name not in first_src.defbefore_vars and name not in type_env:
                continue
            type_name = normalize_type(type_env.get(name, "Any"))
            extra.append((type_name, sanitized))
            existing_param_names.add(sanitized)

        return extra

    def synthesize(self, normalized_body: str) -> ExtractionSignature:
        if not self.case.sources:
            raise ValueError("Empty clone class")

        parameters, is_static = self._base_parameters()
        parameters += self._infer_extra_parameters(normalized_body, parameters)

        return ExtractionSignature(
            method_name=choose_unique_method_name(self.case.classid),
            is_static=is_static,
            parameters=parameters,
        )


# ============================================================
# Clone normalization and method generation
# ============================================================


class CloneNormalizer:
    def __init__(self, signature: ExtractionSignature, case: CloneClassCase, locator: CloneLocator, source_root: Path):
        self.signature = signature
        self.case = case
        self.locator = locator
        self.source_root = source_root

    def _find_covering_node(self, node, start_offset: int, end_offset: int):
        if not (node.start_byte <= start_offset and end_offset <= node.end_byte):
            return None
        for child in getattr(node, "children", []):
            hit = self._find_covering_node(child, start_offset, end_offset)
            if hit is not None:
                return hit
        return node

    def _node_text(self, file_text: str, node) -> str:
        return file_text[node.start_byte:node.end_byte]

    def _unwrap_block_or_statement(self, text: str) -> str:
        return dedent_block(text).strip("\n")

    def normalized_body(self) -> str:
        first = self.case.sources[0]
        file_text = self.locator.load_source(first.file)
        raw_start, raw_end = self.locator.clone_offsets(file_text, first.clone_range)
        start_offset, end_offset = trim_selected_range(file_text, raw_start, raw_end)

        _parser, method_node = self.locator.find_method_node(first)
        target = self._find_covering_node(method_node, start_offset, end_offset)

        if target is None:
            return dedent_block(first.code).strip("\n")

        original_fragment = file_text[raw_start:raw_end]

        cur = target
        while cur is not None:
            if cur.type in IF_NODE_TYPES:
                consequence = cur.child_by_field_name("consequence")
                alternative = cur.child_by_field_name("alternative")

                if range_matches_node(consequence, start_offset, end_offset):
                    return self._unwrap_block_or_statement(self._node_text(file_text, consequence))

                if range_matches_node(alternative, start_offset, end_offset):
                    return self._unwrap_block_or_statement(self._node_text(file_text, alternative))

                if (
                    alternative is not None
                    and consequence is not None
                    and cur.start_byte == start_offset
                    and consequence.end_byte == end_offset
                ):
                    return self._unwrap_block_or_statement(self._node_text(file_text, consequence))

            cur = cur.parent

        return dedent_block(original_fragment).strip("\n")


class PythonMethodRenderer:
    def __init__(self, signature: ExtractionSignature, normalized_body: str, in_class_scope: bool):
        self.signature = signature
        self.normalized_body = normalized_body
        self.in_class_scope = in_class_scope

    def render(self) -> str:
        lines: List[str] = []

        if self.in_class_scope and self.signature.is_static:
            lines.append("@staticmethod")

        params = [n for _, n in self.signature.parameters]
        if self.in_class_scope and not self.signature.is_static:
            params = ["self"] + params

        header = f"def {self.signature.method_name}({', '.join(params)}):"
        lines.append(header)

        body = self.normalized_body.strip()
        if body:
            lines.append(indent_block(body, "    "))
        else:
            lines.append("    pass")

        return "\n".join(lines)


# ============================================================
# Rewriting engine
# ============================================================


class Rewriter:
    def __init__(
        self,
        source_root: Path,
        case: CloneClassCase,
        signature: ExtractionSignature,
        normalized_bodies: Dict[str, str],
    ):
        self.source_root = source_root
        self.case = case
        self.signature = signature
        self.normalized_bodies = normalized_bodies
        self.locator = CloneLocator(source_root)

    def _call_args_for_source(self, source: CloneSource) -> List[str]:
        source_arg_map = {sanitize_identifier(v.name): v.name for v in source.in_vars}

        common_names = {v.name for v in self.case.sources[0].in_vars}
        for src in self.case.sources[1:]:
            common_names &= {v.name for v in src.in_vars}

        common_param_names = [
            sanitize_identifier(v.name)
            for v in self.case.sources[0].in_vars
            if v.name in common_names and v.name != "self"
        ]
        common_param_count = len(common_param_names)

        existing_param_names = set(common_param_names)
        body = self.normalized_bodies[source.func_id]
        extra_vars = infer_extra_vars_for_source(body, source, existing_param_names)

        args: List[str] = []
        extra_index = 0

        for idx, (_type_name, param_name) in enumerate(self.signature.parameters):
            if idx < common_param_count:
                actual = source_arg_map.get(param_name, param_name)
                args.append(actual)
            else:
                if extra_index < len(extra_vars):
                    args.append(extra_vars[extra_index])
                    extra_index += 1
                else:
                    args.append(param_name)

        return args

    def _find_covering_node(self, node, start_offset: int, end_offset: int):
        if not (node.start_byte <= start_offset and end_offset <= node.end_byte):
            return None
        for child in getattr(node, "children", []):
            hit = self._find_covering_node(child, start_offset, end_offset)
            if hit is not None:
                return hit
        return node

    def _find_smallest_enclosing_if(self, node):
        cur = node
        while cur is not None:
            if cur.type in IF_NODE_TYPES:
                return cur
            cur = cur.parent
        return None

    def _render_if_with_extracted_call(self, original_fragment: str, call_line: str) -> str:
        lines = original_fragment.splitlines()
        if not lines:
            return call_line + "\n"

        first_line = lines[0]
        # Identify the indentation of the original first line (the 'if' or 'else')
        first_indent = re.match(r"[ \t]*", first_line).group(0)

        # Use 4 spaces as a default if we can't find the body indent
        body_indent = first_indent + "    "
        for line in lines[1:]:
            if line.strip():
                body_indent = re.match(r"[ \t]*", line).group(0)
                break

        # Ensure the call_line is indented and followed by a newline
        return f"{first_line.rstrip()}\n{body_indent}{call_line.strip()}\n"

    def _build_callsite(self, source: CloneSource, file_text: str) -> str:
        args = ", ".join(self._call_args_for_source(source))
        call_line = f"{self.signature.method_name}({args})"

        raw_start, raw_end = self.locator.clone_offsets(file_text, source.clone_range)
        start_offset, end_offset = trim_selected_range(file_text, raw_start, raw_end)
        original_fragment = file_text[raw_start:raw_end]

        _parser, method_node = self.locator.find_method_node(source)
        target = self._find_covering_node(method_node, start_offset, end_offset)

        if target is not None:
            enclosing_if = self._find_smallest_enclosing_if(target)
            if enclosing_if is not None:
                consequence = enclosing_if.child_by_field_name("consequence")
                alternative = enclosing_if.child_by_field_name("alternative")

                if range_matches_node(consequence, start_offset, end_offset):
                    return self._render_if_with_extracted_call(original_fragment, call_line)

                if range_matches_node(alternative, start_offset, end_offset):
                    return self._render_if_with_extracted_call(original_fragment, call_line)

                if (
                    consequence is not None
                    and alternative is not None
                    and enclosing_if.start_byte == start_offset
                    and consequence.end_byte == end_offset
                ):
                    return self._render_if_with_extracted_call(original_fragment, call_line)

        lines = original_fragment.splitlines()
        indent = common_indent(lines) or ""
        return f"{indent}{call_line}\n"

    def _insert_method(self, file_text: str, relative_file: str, extracted_method_code: str) -> str:
        first_source_in_file = next(src for src in self.case.sources if src.file == relative_file)
        parser, class_node = self.locator.find_enclosing_class_node(first_source_in_file)

        if class_node is not None:
            body = class_node.child_by_field_name("body")
            insert_at = body.end_byte if body is not None else class_node.end_byte
            class_indent = re.match(
                r"[ \t]*",
                file_text[file_text.rfind("\n", 0, class_node.start_byte) + 1: class_node.start_byte]
            ).group(0)
            method_indent = class_indent + "    "
            indented_method = indent_block(extracted_method_code, method_indent)
            insertion = "\n\n" + indented_method
            return file_text[:insert_at] + insertion + file_text[insert_at:]

        # module-level insertion after enclosing function
        _, func_node = self.locator.find_method_node(first_source_in_file)
        insert_at = func_node.end_byte
        insertion = "\n\n" + extracted_method_code
        return file_text[:insert_at] + insertion + file_text[insert_at:]

    def rewrite(self, extracted_method_code: str) -> Tuple[List[CloneRewrite], List[RewriteArtifact]]:
        by_file: Dict[str, List[CloneSource]] = {}
        for src in self.case.sources:
            by_file.setdefault(src.file, []).append(src)

        replacements_out: List[CloneRewrite] = []
        artifacts: List[RewriteArtifact] = []
        first_file = self.case.sources[0].file if self.case.sources else None

        for relative_file, clone_sources in by_file.items():
            file_text = self.locator.load_source(relative_file)
            replacements: List[Tuple[Tuple[int, int], str]] = []

            for src in clone_sources:
                start_offset, end_offset = self.locator.clone_offsets(file_text, src.clone_range)
                replacement = self._build_callsite(src, file_text)
                replacements_out.append(
                    CloneRewrite(
                        func_id=src.func_id,
                        file=src.file,
                        clone_range=src.clone_range,
                        replacement_code=replacement,
                    )
                )
                replacements.append(((start_offset, end_offset), replacement))

            rewritten = apply_replacements(file_text, replacements)
            inserted = False
            if relative_file == first_file:
                rewritten = self._insert_method(rewritten, relative_file, extracted_method_code)
                inserted = True

            artifacts.append(
                RewriteArtifact(
                    file=relative_file,
                    output_path="",
                    inserted_extracted_method=inserted,
                    rewritten_source=rewritten,
                )
            )

        return replacements_out, artifacts


# ============================================================
# Orchestrator
# ============================================================


class ExtractMethodRefactorer:
    def __init__(self, source_root: Path):
        self.source_root = source_root
        self.locator = CloneLocator(source_root)

    def refactor(self, case: CloneClassCase) -> RefactorResult:
        first_func_code = case.sources[0].enclosing_function.func_code
        is_static = infer_is_static(first_func_code)

        base_signature = ExtractionSignature(
            method_name=choose_unique_method_name(case.classid),
            is_static=is_static,
            parameters=[
                (normalize_type(v.type_name), sanitize_identifier(v.name))
                for v in case.sources[0].in_vars
                if not (v.name == "self" and not is_static)
            ],
        )

        normalized_bodies: Dict[str, str] = {}
        for src in case.sources:
            single_case = CloneClassCase(
                classid=case.classid,
                nclones=1,
                #similarity=case.similarity,
                project=case.project,
                same_file=case.same_file,
                actual_label=case.actual_label,
                clone_predict=case.clone_predict,
                clone_predict_after_adapt=case.clone_predict_after_adapt,
                refactorable=case.refactorable,
                inspection_case=case.inspection_case,
                sources=[src],
            )
            normalized_bodies[src.func_id] = CloneNormalizer(
                base_signature, single_case, self.locator, self.source_root
            ).normalized_body()

        normalized_body = normalized_bodies[case.sources[0].func_id]
        signature = SignatureSynthesizer(case).synthesize(normalized_body)

        param_names = {name for _, name in signature.parameters}
        declared_local_names = extract_method_local_declarations(normalized_body)
        free_vars = basic_free_variable_check(normalized_body, param_names, declared_local_names)

        diagnostics: List[str] = []
        if free_vars:
            diagnostics.append(
                "Potential missing parameters or unresolved names in extracted body: "
                + ", ".join(free_vars)
            )

        in_class_scope = has_self_parameter(first_func_code) or ("." in case.sources[0].enclosing_function.qualified_name)

        extracted_method_code = PythonMethodRenderer(
            signature, normalized_body, in_class_scope=in_class_scope
        ).render()

        replacements, updated_files = Rewriter(
            self.source_root, case, signature, normalized_bodies
        ).rewrite(extracted_method_code)

        return RefactorResult(
            extracted_method_code=extracted_method_code,
            extracted_signature=signature,
            replacements=replacements,
            updated_files=updated_files,
            diagnostics=diagnostics,
        )


# ============================================================
# Output formatting
# ============================================================


class ResultFormatter:
    @staticmethod
    def to_json(case: CloneClassCase, result: RefactorResult, concise: bool = True) -> dict:
        payload = {
            "classid": case.classid,
            "extracted_method": {
                "method_name": result.extracted_signature.method_name,
                "is_static": result.extracted_signature.is_static,
                "parameters": [f"{t} {n}" for t, n in result.extracted_signature.parameters],
                "code": result.extracted_method_code,
            },
            "sources": [
                {
                    "func_id": src.func_id,
                    "file": src.file,
                    "range": src.clone_range,
                    "nlines": src.nlines,
                    "code": src.code,
                    "enclosing_function": {
                        "qualified_name": src.enclosing_function.qualified_name,
                        "fun_range": src.enclosing_function.fun_range,
                        "fun_nlines": src.enclosing_function.fun_nlines,
                        "func_code": src.enclosing_function.func_code,
                    },
                    "replacement_code": next(
                        (repl.replacement_code for repl in result.replacements if repl.func_id == src.func_id),
                        "",
                    ),
                    "ground_truth_after_VSCode_ref": src.ground_truth_after_vscode_ref,
                }
                for src in case.sources
            ],
            "updated_files": [
                {
                    "file": artifact.file,
                    "inserted_extracted_method": artifact.inserted_extracted_method,
                    "rewritten_file_path": artifact.output_path,
                }
                for artifact in result.updated_files
            ],
        }

        if not concise:
            payload.update(
                {
                    "project": case.project,
                    "inspection_case": case.inspection_case,
                    "refactoring_type": "extract_method",
                    "nclones": case.nclones,
                    "same_file": case.same_file,
                    "clone_predict": case.clone_predict,
                    "clone_predict_after_adapt": case.clone_predict_after_adapt,
                    "Refactorable": case.refactorable,
                    "diagnostics": result.diagnostics,
                }
            )

        return payload


# ============================================================
# CLI
# ============================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Method refactoring for Python clone classes.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("refactor_out"))
    parser.add_argument("--full-report", action="store_true")
    parser.add_argument("--merged-report-name", type=str, default="all_refactor_results.json")
    args = parser.parse_args()

    # Load the text content
    text = args.input.read_text(encoding="utf-8").strip()

    # Determine if it's JSONL or standard JSON
    if text.startswith("[") and text.endswith("]"):
        # It's a standard JSON array
        try:
            payloads = json.loads(text)
        except json.JSONDecodeError:
            # Fallback for messy JSONL that happens to start/end with brackets
            payloads = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        # It's either JSONL or a single JSON object
        try:
            # Try parsing as a single object first
            payload = json.loads(text)
            payloads = [payload] if isinstance(payload, dict) else payload
        except json.JSONDecodeError:
            # Process as JSONL
            payloads = [
                json.loads(line)
                for line in text.splitlines()
                if line.strip()
            ]

    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary_reports = []
    merged_reports = []

    for idx, case_payload in enumerate(payloads, start=1):
        case = CloneCaseLoader.from_json(case_payload)
        refactorer = ExtractMethodRefactorer(args.source_root)
        result = refactorer.refactor(case)

        case_output_dir = args.output_dir / case.classid
        case_output_dir.mkdir(parents=True, exist_ok=True)

        materialized_artifacts: List[RewriteArtifact] = []
        for artifact in result.updated_files:
            relative_path = Path(artifact.file)
            out_path = case_output_dir / relative_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(artifact.rewritten_source, encoding="utf-8")

            materialized_artifacts.append(
                RewriteArtifact(
                    file=artifact.file,
                    output_path=str(out_path),
                    inserted_extracted_method=artifact.inserted_extracted_method,
                    rewritten_source=artifact.rewritten_source,
                )
            )

        final_result = RefactorResult(
            extracted_method_code=result.extracted_method_code,
            extracted_signature=result.extracted_signature,
            replacements=result.replacements,
            updated_files=materialized_artifacts,
            diagnostics=result.diagnostics,
        )

        report = ResultFormatter.to_json(case, final_result, concise=not args.full_report)
        merged_reports.append(report)

        summary_reports.append(
            {
                "classid": case.classid,
                "rewritten_files": [a.output_path for a in materialized_artifacts],
                "diagnostics": final_result.diagnostics,
            }
        )

        print(f"[{idx}/{len(payloads)}] Finished: {case.classid}")
        for artifact in materialized_artifacts:
            print(f"Rewritten file written to: {artifact.output_path}")
        if final_result.diagnostics:
            print("Diagnostics:")
            for diag in final_result.diagnostics:
                print(f"  - {diag}")

    merged_report_path = args.output_dir / args.merged_report_name
    merged_report_path.write_text(json.dumps(merged_reports, indent=2), encoding="utf-8")

    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary_reports, indent=2), encoding="utf-8")

    print(f"Merged report written to: {merged_report_path}")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()