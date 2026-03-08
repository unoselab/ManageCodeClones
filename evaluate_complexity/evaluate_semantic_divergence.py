import ast
import re
import difflib
import json

def normalize_text(source_code: str) -> str:
    """
    Strips comments and normalizes whitespace to check for Type-1 clones.
    Type-1 clones are identical except for formatting and comments.
    """
    # Remove single-line comments
    code = re.sub(r'#.*', '', source_code)
    # Remove docstrings / multi-line strings (simplified heuristic)
    code = re.sub(r'("""[\s\S]*?""")|(\'\'\'[\s\S]*?\'\'\')', '', code)
    # Normalize all whitespace to a single space
    code = re.sub(r'\s+', ' ', code).strip()
    return code

def get_ast_skeleton(source_code: str) -> list:
    """
    Extracts an ordered sequence of AST node types.
    Ignores variable names, literals, and operators to isolate pure structure.
    """
    try:
        tree = ast.parse(source_code)
        # Using ast.walk provides a consistent structural footprint
        return [type(node).__name__ for node in ast.walk(tree)]
    except SyntaxError:
        return []

def evaluate_semantic_divergence(clone_1_code: str, clone_2_code: str, type_3_threshold: float = 0.7) -> dict:
    """
    Evaluates the semantic divergence between two clone candidates, 
    classifying them into Type-1, Type-2, Type-3, or Type-4.
    Returns a divergence score (1-4), where 4 is the most complex for the LLM.
    """
    # ---------------------------------------------------------
    # 1. Check for Type-1 (Exact Textual Match)
    # ---------------------------------------------------------
    norm_1 = normalize_text(clone_1_code)
    norm_2 = normalize_text(clone_2_code)
    
    if norm_1 and norm_1 == norm_2:
        return {
            "clone_type": "Type-1",
            "divergence_score": 1,
            "description": "Exact textual match (ignoring whitespace and comments)."
        }

    # ---------------------------------------------------------
    # 2. Check for Type-2 (Structurally Identical, Renamed Identifiers)
    # ---------------------------------------------------------
    ast_1 = get_ast_skeleton(clone_1_code)
    ast_2 = get_ast_skeleton(clone_2_code)
    
    # If unparseable, we default to the highest difficulty (requires raw semantic reasoning)
    if not ast_1 or not ast_2:
        return {
            "clone_type": "Unknown/Unparseable",
            "divergence_score": 4,
            "description": "Syntax errors present; relies entirely on LLM semantic embedding."
        }

    if ast_1 == ast_2:
        return {
            "clone_type": "Type-2",
            "divergence_score": 2,
            "description": "Structurally identical; divergent identifiers or literals."
        }

    # ---------------------------------------------------------
    # 3. Check for Type-3 (Modified Statements / Structural Gaps)
    # ---------------------------------------------------------
    matcher = difflib.SequenceMatcher(None, ast_1, ast_2)
    structural_similarity = matcher.ratio()
    
    if structural_similarity >= type_3_threshold:
        return {
            "clone_type": "Type-3",
            "divergence_score": 3,
            "structural_similarity": round(structural_similarity, 3),
            "description": "High structural overlap, but statements were added, removed, or modified."
        }

    # ---------------------------------------------------------
    # 4. Check for Type-4 (Semantic Equivalents)
    # ---------------------------------------------------------
    # Since these pairs are pre-validated true clones from the dataset, 
    # falling through to this point means they achieve the same logic 
    # using completely different syntactic structures (e.g., 'for' loop vs 'recursion').
    return {
        "clone_type": "Type-4",
        "divergence_score": 4,
        "structural_similarity": round(structural_similarity, 3),
        "description": "Functionally equivalent but syntactically divergent."
    }

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    
    base_snippet = """
def factorial(n):
    if n == 0:
        return 1
    else:
        return n * factorial(n-1)
"""

    type_1_snippet = """
def factorial(n):
    # Base case
    if n == 0:
        return 1
    else:
        return n * factorial(n-1)
"""

    type_2_snippet = """
def get_fact(num):
    if num == 0:
        return 1
    else:
        return num * get_fact(num-1)
"""

    type_3_snippet = """
def factorial(n):
    if n < 0:
        raise ValueError("Negative numbers not allowed")
    if n == 0:
        return 1
    return n * factorial(n-1)
"""

    type_4_snippet = """
def factorial(n):
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result
"""

    print("--- Evaluating Base vs Type-1 ---")
    print(json.dumps(evaluate_semantic_divergence(base_snippet, type_1_snippet), indent=4))
    
    print("\n--- Evaluating Base vs Type-2 ---")
    print(json.dumps(evaluate_semantic_divergence(base_snippet, type_2_snippet), indent=4))

    print("\n--- Evaluating Base vs Type-3 ---")
    print(json.dumps(evaluate_semantic_divergence(base_snippet, type_3_snippet), indent=4))

    print("\n--- Evaluating Base vs Type-4 ---")
    print(json.dumps(evaluate_semantic_divergence(base_snippet, type_4_snippet), indent=4))