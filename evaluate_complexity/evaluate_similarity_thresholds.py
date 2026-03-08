import ast
import tokenize
import io
import difflib
import json

def get_lexical_tokens(source_code: str) -> list:
    """
    Extracts a list of meaningful lexical tokens from the source code.
    We strip out whitespace, formatting, and comments to ensure the LLM
    curriculum evaluates actual semantic code content, not formatting artifacts.
    """
    tokens = []
    try:
        # Convert string to byte stream for the tokenizer
        byte_stream = io.BytesIO(source_code.encode('utf-8'))
        for tok in tokenize.tokenize(byte_stream.readline):
            # Ignore encoding markers, whitespace, newlines, and comments
            if tok.type not in (tokenize.ENCODING, tokenize.NEWLINE, 
                                tokenize.INDENT, tokenize.DEDENT, 
                                tokenize.NL, tokenize.COMMENT):
                tokens.append(tok.string)
    except Exception:
        # Fallback if tokenization fails (e.g., invalid syntax)
        pass
    return tokens

def get_ast_node_sequence(source_code: str) -> list:
    """
    Extracts a flattened sequence of AST node types (e.g., 'FunctionDef', 'If', 'Return').
    This strips away all variable names and literals, leaving only the pure 
    structural skeleton of the code snippet.
    """
    node_sequence = []
    try:
        tree = ast.parse(source_code)
        # ast.walk visits nodes in no guaranteed order, but it is consistent 
        # for identical structures. For strict sequence alignment, visiting 
        # via a custom ast.NodeVisitor is generally preferred, but walk() 
        # suffices for structural set/sequence approximation.
        for node in ast.walk(tree):
            node_sequence.append(type(node).__name__)
    except SyntaxError:
        pass
    return node_sequence

def calculate_jaccard_similarity(list1: list, list2: list) -> float:
    """
    Calculates the Jaccard similarity index between two lists (used for sets of tokens).
    Formula: Intersection size / Union size
    Returns a float between 0.0 (no overlap) and 1.0 (exact match).
    """
    set1, set2 = set(list1), set(list2)
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    if union == 0:
        return 0.0
    return intersection / union

def calculate_sequence_similarity(seq1: list, seq2: list) -> float:
    """
    Calculates the Ratcliff/Obershelp sequence similarity (used for structural order).
    This ensures that the order of the AST nodes matters, not just their presence.
    Returns a float between 0.0 and 1.0.
    """
    if not seq1 or not seq2:
        return 0.0
    matcher = difflib.SequenceMatcher(None, seq1, seq2)
    return matcher.ratio()

def evaluate_similarity_thresholds(clone_1_code: str, clone_2_code: str) -> dict:
    """
    Evaluates both the lexical (surface text) and structural (AST skeleton) 
    similarity between two clone candidates.
    """
    # 1. Lexical Evaluation (Surface-level token similarity)
    tokens_1 = get_lexical_tokens(clone_1_code)
    tokens_2 = get_lexical_tokens(clone_2_code)
    lexical_sim = calculate_jaccard_similarity(tokens_1, tokens_2)
    
    # 2. Structural Evaluation (Deep AST skeleton similarity)
    ast_seq_1 = get_ast_node_sequence(clone_1_code)
    ast_seq_2 = get_ast_node_sequence(clone_2_code)
    structural_sim = calculate_sequence_similarity(ast_seq_1, ast_seq_2)
    
    # 3. Composite Score
    # The curriculum matrix balances both to place the pair in the right tier.
    # E.g., High Lexical + High Structural = Tier 1 (Easy)
    # E.g., Low Lexical + High Structural = Tier 3 (Harder - variable renaming / Type-2/3)
    composite_score = (lexical_sim + structural_sim) / 2.0

    return {
        "lexical_similarity": round(lexical_sim, 4),
        "structural_similarity": round(structural_sim, 4),
        "composite_similarity_score": round(composite_score, 4)
    }

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    
    # Snippet A: Original function
    clone_a = """
def calculate_discount(price, discount_rate):
    if price > 100:
        return price - (price * discount_rate)
    return price
"""

    # Snippet B: Type-2 Clone (Identifiers changed, logic identical)
    # Lexical similarity will drop slightly, but structural similarity remains 1.0
    clone_b = """
def apply_promo(cost, rate):
    if cost > 100:
        return cost - (cost * rate)
    return cost
"""

    # Snippet C: Type-3 Clone (Statements added/modified)
    # Both lexical and structural similarity will drop
    clone_c = """
def apply_promo_with_tax(cost, rate, tax=0.05):
    if cost > 100:
        discounted = cost - (cost * rate)
        return discounted + (discounted * tax)
    return cost + (cost * tax)
"""

    print("--- Comparing Snippet A to Snippet B (Type-2 Clone) ---")
    result_ab = evaluate_similarity_thresholds(clone_a, clone_b)
    print(json.dumps(result_ab, indent=4))
    
    print("\n--- Comparing Snippet A to Snippet C (Type-3 Clone) ---")
    result_ac = evaluate_similarity_thresholds(clone_a, clone_c)
    print(json.dumps(result_ac, indent=4))