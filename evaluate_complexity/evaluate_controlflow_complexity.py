import ast
import json

class ControlFlowComplexityVisitor(ast.NodeVisitor):
    """
    An AST visitor that calculates the cyclomatic complexity of a Python code snippet.
    Base complexity is 1. We add 1 for every control flow branch.
    """
    def __init__(self):
        self.complexity = 1

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Try(self, node):
        # Each except block adds a branching path
        self.complexity += len(node.handlers)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Logical operators like 'and', 'or' introduce hidden branches
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_ListComp(self, node):
        self.complexity += len(node.generators)
        self.generic_visit(node)
        
    def visit_SetComp(self, node):
        self.complexity += len(node.generators)
        self.generic_visit(node)
        
    def visit_DictComp(self, node):
        self.complexity += len(node.generators)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node):
        self.complexity += len(node.generators)
        self.generic_visit(node)


def calculate_snippet_complexity(source_code: str) -> int:
    """
    Parses the source code into an AST and computes its cyclomatic complexity.
    Returns -1 if the code has syntax errors (cannot be parsed).
    """
    try:
        tree = ast.parse(source_code)
        visitor = ControlFlowComplexityVisitor()
        visitor.visit(tree)
        return visitor.complexity
    except SyntaxError:
        # Fallback for unparseable snippets
        return -1


def evaluate_pair_complexity(clone_1_code: str, clone_2_code: str) -> dict:
    """
    Evaluates the control-flow complexity for a pair of clone candidates.
    Returns the individual complexities and the aggregate 'pair_score'.
    """
    c1_score = calculate_snippet_complexity(clone_1_code)
    c2_score = calculate_snippet_complexity(clone_2_code)
    
    # If either snippet fails to parse, flag the pair
    if c1_score == -1 or c2_score == -1:
        pair_score = -1 
    else:
        # The complexity of the pair is defined by the most complex snippet within it.
        # This ensures the LLM curriculum respects the hardest part of the alignment.
        pair_score = max(c1_score, c2_score)

    return {
        "clone_1_complexity": c1_score,
        "clone_2_complexity": c2_score,
        "pair_complexity_score": pair_score
    }

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    
    # A simple Type-1/Type-2 clone (Low Complexity)
    clone_a = """
def calculate_total(prices):
    total = 0
    for p in prices:
        total += p
    return total
"""

    # A more complex Type-3/Type-4 clone with heavy control flow (High Complexity)
    clone_b = """
def get_valid_total(prices, discount=None):
    total = 0
    for p in prices:
        if p > 0 and type(p) == int:
            total += p
        elif p == -1:
            continue
        else:
            try:
                total += int(p)
            except ValueError:
                pass
    if discount:
        total = total * (1 - discount)
    return total
"""

    result = evaluate_pair_complexity(clone_a, clone_b)
    print(json.dumps(result, indent=4))