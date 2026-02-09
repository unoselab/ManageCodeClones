#!/usr/bin/env python3
import io
import tokenize


def remove_python_comments(code: str) -> str:
    """
    Remove Python comments + docstrings (module/class/function) using tokenize.
    Keeps '#' inside strings and keeps non-docstring triple-quoted strings (e.g., assigned data).
    Also post-cleans:
      - standalone "\" artifact lines
      - trailing whitespace
      - whitespace-only lines
    """
    if not code:
        return ""

    src = code if code.endswith("\n") else code + "\n"

    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Conservative fallback: remove full-line comments only; do not attempt docstring removal
        lines = code.splitlines()
        kept_lines = [ln for ln in lines if not ln.lstrip().startswith("#")]
        return "\n".join(kept_lines)

    kept = []
    at_module_start = True     # first statement at module level
    at_suite_start = False     # first statement after INDENT (def/class body)

    i = 0
    n = len(toks)
    while i < n:
        tok = toks[i]

        # 1) remove comments
        if tok.type == tokenize.COMMENT:
            i += 1
            continue

        # track suite starts
        if tok.type == tokenize.INDENT:
            at_suite_start = True
            kept.append(tok)
            i += 1
            continue

        if tok.type == tokenize.DEDENT:
            at_suite_start = False
            kept.append(tok)
            i += 1
            continue

        # keep NL (layout), but don't let it close "first statement"
        if tok.type == tokenize.NL:
            kept.append(tok)
            i += 1
            continue

        # 2) remove docstring if STRING appears as first statement (module or suite)
        if tok.type == tokenize.STRING and (at_module_start or at_suite_start):
            i += 1
            # swallow immediate NEWLINE (if any) to avoid blank statement line
            if i < n and toks[i].type == tokenize.NEWLINE:
                i += 1
            at_module_start = False
            at_suite_start = False
            continue

        # close docstring windows on first real statement token
        if tok.type not in (tokenize.ENCODING, tokenize.NL, tokenize.NEWLINE):
            at_module_start = False
            at_suite_start = False

        kept.append(tok)
        i += 1

    out = tokenize.untokenize(kept)

    # Post-clean:
    # 1) remove standalone "\" artifact lines
    # 2) strip trailing whitespace
    # 3) drop whitespace-only lines
    lines = out.splitlines()
    cleaned_lines = []
    for ln in lines:
        if ln.strip() in ("\\", "\\\\"):
            continue
        ln = ln.rstrip()
        if ln.strip() == "":
            continue
        cleaned_lines.append(ln)

    return "\n".join(cleaned_lines)