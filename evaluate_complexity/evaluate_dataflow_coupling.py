import ast
import builtins
import json

class DataFlowCouplingVisitor(ast.NodeVisitor):
    """
    An AST visitor that tracks variable declarations and usages to calculate
    how many external variables a snippet depends on.
    """
    def __init__(self):
        self.local_defs = set()
        self.external_refs = set()
        # We ignore Python built-ins (e.g., print, len, range, str) 
        # because they are globally available and do not impede refactoring.
        self.builtin_names = set(dir(builtins))

    def visit_Assign(self, node):
        # Track variables defined locally via standard assignment (e.g., x = 5)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.local_defs.add(target.id)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        # Track variables defined with type hints (e.g., x: int = 5)
        if isinstance(node.target, ast.Name):
            self.local_defs.add(node.target.id)
        self.generic_visit(node)

    def visit_For(self, node):
        # Track loop variables (e.g., 'i' in 'for i in range(10)')
        if isinstance(node.target, ast.Name):
            self.local_defs.add(node.target.id)
        self.generic_visit(node)

    def visit_Name(self, node):
        """
        Every time a variable name is encountered, we check its context.
        If it is being read (ast.Load) or modified (ast.Store) and was NOT 
        defined inside this snippet, it is an external coupling dependency.
        """
        is_read_or_write = isinstance(node.ctx, (ast.Load, ast.Store))
        is_not_builtin = node.id not in self.builtin_names
        is_not_local = node.id not in self.local_defs

        if is_read_or_write and is_not_builtin and is_not_local:
            self.external_refs.add(node.id)
            
        self.generic_visit(node)


def calculate_coupling_density(source_code: str) -> dict:
    """
    Parses the snippet and returns the count and names of external variables.
    Returns a score of -1 if the code cannot be parsed.
    """
    try:
        # Wrap the snippet in a function if it's a raw block of statements 
        # to ensure it parses as a valid AST block.
        tree = ast.parse(source_code)
        visitor = DataFlowCouplingVisitor()
        visitor.visit(tree)
        
        return {
            "density_score": len(visitor.external_refs),
            "external_variables": list(visitor.external_refs)
        }
    except SyntaxError:
        return {
            "density_score": -1,
            "external_variables": []
        }

def evaluate_dataflow_coupling(clone_1_code: str, clone_2_code: str) -> dict:
    """
    Evaluates the data-flow coupling density for a pair of clone candidates.
    The curriculum relies on the maximum density of the pair to ensure 
    the LLM respects the hardest refactoring boundaries.
    """
    c1_metrics = calculate_coupling_density(clone_1_code)
    c2_metrics = calculate_coupling_density(clone_2_code)
    
    # If either fails to parse, flag the pair for manual review / highest tier
    if c1_metrics["density_score"] == -1 or c2_metrics["density_score"] == -1:
        pair_score = -1
    else:
        # We take the maximum coupling. If Clone A has 0 external vars but 
        # Clone B has 4, the pair is fundamentally complex to align and refactor.
        pair_score = max(c1_metrics["density_score"], c2_metrics["density_score"])

    return {
        "clone_1_coupling": c1_metrics,
        "clone_2_coupling": c2_metrics,
        "pair_coupling_score": pair_score,
        "description": f"Maximum of {pair_score} external variables must be managed across the extraction boundary."
    }

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    
    # Snippet A: Fully self-contained clone (Low Coupling = 0)
    # If we extract this, it needs 0 parameters.
    clone_a = """
total_sum = 0
for i in range(10):
    total_sum += i
print(total_sum)
"""

    # Snippet B: Highly entangled clone (High Coupling = 3)
    # It relies on 'user_id', 'db_connection', and 'logger' which are not defined here.
    # If we extract this, we must pass 3 parameters.
    clone_b = """
query = f"SELECT * FROM users WHERE id = {user_id}"
result = db_connection.execute(query)
if result:
    logger.info("User found.")
    active_status = result['is_active']
"""

    print("--- Evaluating Data-Flow Coupling Density ---")
    result = evaluate_dataflow_coupling(clone_a, clone_b)
    print(json.dumps(result, indent=4))