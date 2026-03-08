import json
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

# Initialize the Tree-sitter Java Language and Parser
JAVA_LANGUAGE = Language(tsjava.language())
parser = Parser(JAVA_LANGUAGE)

def count_branching_nodes(node) -> int:
    """
    Recursively traverses the Tree-sitter AST to count Java control-flow branches.
    """
    complexity_addition = 0
    
    # Standard Java branching statements
    branch_node_types = {
        'if_statement', 
        'for_statement', 
        'enhanced_for_statement', 
        'while_statement', 
        'do_statement', 
        'catch_clause', 
        'switch_label',      # Represents 'case' or 'default' in a switch
        'ternary_expression' # e.g., (a > b) ? a : b
    }
    
    if node.type in branch_node_types:
        complexity_addition += 1
        
    # Hidden branches: Logical AND (&&) / OR (||) introduce short-circuit paths
    elif node.type == 'binary_expression':
        operator_node = node.child_by_field_name('operator')
        if operator_node and operator_node.type in {'&&', '||'}:
            complexity_addition += 1

    # Recursively check all children
    for child in node.children:
        complexity_addition += count_branching_nodes(child)
        
    return complexity_addition

def calculate_snippet_complexity(source_code: str) -> int:
    """
    Parses the Java source code into a Tree-sitter AST and computes its cyclomatic complexity.
    Base complexity is 1. We add 1 for every control flow branch found.
    """
    try:
        # Tree-sitter requires byte strings
        tree = parser.parse(bytes(source_code, "utf8"))
        
        # Check for catastrophic parsing failures (though Tree-sitter is highly fault-tolerant)
        if tree.root_node.has_error and len(tree.root_node.children) == 0:
            return -1
            
        # Base complexity of 1 + all discovered branches
        return 1 + count_branching_nodes(tree.root_node)
    except Exception:
        return -1

def evaluate_pair_complexity(clone_1_code: str, clone_2_code: str) -> dict:
    """
    Evaluates the control-flow complexity for a pair of Java clone candidates.
    Returns the individual complexities and the aggregate 'pair_score'.
    """
    c1_score = calculate_snippet_complexity(clone_1_code)
    c2_score = calculate_snippet_complexity(clone_2_code)
    
    if c1_score == -1 or c2_score == -1:
        pair_score = -1 
    else:
        # Taking the maximum complexity ensures the LLM curriculum tier accurately 
        # reflects the hardest refactoring boundary in the pair.
        pair_score = max(c1_score, c2_score)

    return {
        "clone_1_complexity": c1_score,
        "clone_2_complexity": c2_score,
        "pair_complexity_score": pair_score
    }

# ==========================================
# Example Usage (Using the ActiveMQ JSONL)
# ==========================================
if __name__ == "__main__":
    
    # Instance: activemq_17_0
    clone_a = """    public MessageProducer getMessageProducer(Destination destination) throws JMSException {
        MessageProducer result = null;

        if (useAnonymousProducers) {
            result = safeGetSessionHolder().getOrCreateProducer();
        } else {
            result = getInternalSession().createProducer(destination);
        }

        return result;
    }"""

    # Instance: activemq_17_1
    clone_b = """    public TopicPublisher getTopicPublisher(Topic destination) throws JMSException {
        TopicPublisher result = null;

        if (useAnonymousProducers) {
            result = safeGetSessionHolder().getOrCreatePublisher();
        } else {
            result = ((TopicSession) getInternalSession()).createPublisher(destination);
        }

        return result;
    }"""
    
    # High-complexity fallback example (Nested logic & Catch blocks)
    clone_c = """    public void processMessage(Message msg) {
        if (msg != null && msg.isValid()) {
            try {
                for (Header h : msg.getHeaders()) {
                    if (h.isImportant()) {
                        process(h);
                    }
                }
            } catch (JMSException e) {
                log.error(e);
            } catch (Exception e) {
                log.fatal(e);
            }
        }
    }"""

    print("--- Evaluating activemq_17_0 vs activemq_17_1 (Tier 1 / Low Complexity) ---")
    result_ab = evaluate_pair_complexity(clone_a, clone_b)
    print(json.dumps(result_ab, indent=4))
    
    print("\n--- Evaluating activemq_17_0 vs Complex Snippet (Tier 3/4 / High Asymmetry) ---")
    result_ac = evaluate_pair_complexity(clone_a, clone_c)
    print(json.dumps(result_ac, indent=4))