#!/usr/bin/env python3
"""
Test script for tokenize-based Python comment removal.
Prints BEFORE / AFTER for visual inspection.
"""

import io
import tokenize
import argparse


def strip_python_comments(code: str) -> str:
    if not code:
        return ""

    src = code if code.endswith("\n") else (code + "\n")

    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
        kept = []
        for tok in toks:
            if tok.type == tokenize.COMMENT:
                continue
            kept.append(tok)
        return tokenize.untokenize(kept)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        lines = code.splitlines()
        kept_lines = []
        for line in lines:
            if line.lstrip().startswith("#"):
                continue
            kept_lines.append(line)
        return "\n".join(kept_lines)


def _run_case(name: str, code: str, must_contain=(), must_not_contain=(), verbose=True):
    cleaned = strip_python_comments(code)

    if verbose:
        print(f"\n[CASE] {name}")
        print("--- BEFORE ---")
        print(code.rstrip())
        print("\n--- AFTER ---")
        print(cleaned.rstrip())
        print()

    for s in must_contain:
        assert s in cleaned, (
            f"[{name}] expected to contain: {s!r}\n---cleaned---\n{cleaned}"
        )
    for s in must_not_contain:
        assert s not in cleaned, (
            f"[{name}] expected NOT to contain: {s!r}\n---cleaned---\n{cleaned}"
        )

    print(f"[PASS] {name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true", help="Do not print before/after")
    args = parser.parse_args()

    verbose = not args.quiet

    # 1) Full-line comment removal
    _run_case(
        "full_line_comments",
        code=(
            "# comment 1\n"
            "x = 1\n"
            "   # comment 2 with indent\n"
            "y = 2\n"
        ),
        must_contain=("x = 1", "y = 2"),
        must_not_contain=("comment 1", "comment 2"),
        verbose=verbose,
    )

    # 2) Inline comments
    _run_case(
        "inline_comments",
        code=(
            "x = 1  # inline comment\n"
            "y = x + 2  # another one\n"
        ),
        must_contain=("x = 1", "y = x + 2"),
        must_not_contain=("inline comment", "another one"),
        verbose=verbose,
    )

    # 3) URL fragment in string
    _run_case(
        "url_fragment_in_string",
        code=(
            "url = \"https://example.com/path#section-2\"  # trailing comment\n"
            "print(url)\n"
        ),
        must_contain=("https://example.com/path#section-2", "print(url)"),
        must_not_contain=("trailing comment",),
        verbose=verbose,
    )

    # 4) Hash inside strings
    _run_case(
        "hash_in_strings",
        code=(
            "a = '#not_a_comment'\n"
            "b = \"#still_not_a_comment\"  # remove me\n"
            "print(a, b)\n"
        ),
        must_contain=("#not_a_comment", "#still_not_a_comment", "print(a, b)"),
        must_not_contain=("remove me",),
        verbose=verbose,
    )

    # 5) f-string
    _run_case(
        "fstring_hash",
        code=(
            "name = 'abc'\n"
            "s = f\"value=#{name}\"  # remove\n"
            "print(s)\n"
        ),
        must_contain=("value=#{name}", "print(s)"),
        must_not_contain=("remove",),
        verbose=verbose,
    )

    # 6) raw string
    _run_case(
        "raw_string_hash",
        code=(
            "pat = r\"C:\\\\tmp\\\\file#1\"  # comment\n"
            "print(pat)\n"
        ),
        must_contain=("file#1", "print(pat)"),
        must_not_contain=("comment",),
        verbose=verbose,
    )

    # 7) triple-quoted string
    _run_case(
        "triple_quoted_string_with_hash",
        code=(
            "doc = '''This is not a comment: # stays here.\n"
            "And \"nested quotes\" should stay.\n"
            "'''\n"
            "x = 1  # remove\n"
        ),
        must_contain=("This is not a comment: # stays here.", "nested quotes", "x = 1"),
        must_not_contain=("remove",),
        verbose=verbose,
    )

    # 8) docstring preserved
    _run_case(
        "docstring_preserved",
        code=(
            "def f():\n"
            "    \"\"\"Docstring with # is fine.\n"
            "    It should remain.\n"
            "    \"\"\"\n"
            "    return 1  # remove\n"
        ),
        must_contain=("Docstring with # is fine.", "return 1"),
        must_not_contain=("remove",),
        verbose=verbose,
    )

    # 9) shebang / encoding
    _run_case(
        "shebang_and_encoding_removed",
        code=(
            "#!/usr/bin/env python3\n"
            "# -*- coding: utf-8 -*-\n"
            "print('hi')\n"
        ),
        must_contain=("print('hi')",),
        must_not_contain=("coding:", "/usr/bin/env"),
        verbose=verbose,
    )

    # 10) import-like text in string
    _run_case(
        "import_like_text_in_string",
        code=(
            "s = \"import pytest  # not real\"  # remove this comment\n"
            "print(s)\n"
        ),
        must_contain=("import pytest  # not real", "print(s)"),
        must_not_contain=("remove this comment",),
        verbose=verbose,
    )

    print("\nAll comment-removal test cases passed.")


if __name__ == "__main__":
    main()