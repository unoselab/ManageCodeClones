# Complexity Matrix Evaluation Suite for Domain-Adaptive Code Clones

This repository contains the evaluation suite used to quantify the structural, semantic, and architectural complexity of code clone pairs. 

In our approach, adapting Large Language Models (LLMs) to project-specific structural idioms requires a mathematically grounded **curriculum learning** pipeline. Rather than using conventional randomized dataset splits, we stratify contrastive clone pairs into progressive learning tiers. This suite evaluates each clone pair across **five orthogonal dimensions** to calculate a composite difficulty score, facilitating a smooth, phase-specific curriculum transition from generalized patterns to complex target-domain idioms.

---

## The 5-Axis Complexity Matrix

The suite is divided into five independent evaluation modules. Each module targets a specific facet of software engineering complexity, directly impacting both the LLM's context-window limitations and the mathematical preconditions required for downstream automated refactoring (e.g., *Extract Method*).

### 1. Internal Control-Flow Complexity
* **Script:** `evaluate_controlflow_complexity.py`
* **Mechanism:** Computes McCabe’s Cyclomatic Complexity by traversing the Abstract Syntax Tree (AST) to count linearly independent control-flow branching paths (`If`, `For`, `While`, `Try`, etc.).
* **Curriculum Impact:** Pairs with highly asymmetric or deeply nested logic are pushed to later training epochs. 

### 2. Lexical and Structural Similarity Thresholds
* **Script:** `evaluate_similarity_thresholds.py`
* **Mechanism:** Calculates surface-level lexical similarity (Jaccard index of normalized token sets) and deep structural similarity (Ratcliff/Obershelp sequence matching on flattened AST node types).
* **Curriculum Impact:** High lexical/structural similarity (easy pattern matching) populates Tier 1. Low lexical but high structural similarity targets Tier 2/3. 

### 3. Semantic Divergence (Clone Taxonomy)
* **Script:** `evaluate_semantic_divergence.py`
* **Mechanism:** Classifies the clone pair into standard taxonomies based on AST sequence thresholds and token normalization.
  * **Tier 1:** Type-1 (Exact textual matches)
  * **Tier 2:** Type-2 (Renamed identifiers, identical AST)
  * **Tier 3:** Type-3 (Modified/added statements, high AST overlap)
  * **Tier 4:** Type-4 (Functional equivalents, divergent syntax)
* **Curriculum Impact:** Forces the LLM to master structural variations before attempting pure semantic reasoning. 

### 4. Data-Flow Coupling Density
* **Script:** `evaluate_dataflow_coupling.py`
* **Mechanism:** Performs a lightweight Def-Use chain analysis via the AST. It counts the number of external variables read/written inside the clone snippet but declared outside its scope.
* **Curriculum Impact:** Critical for safe automated refactoring. Clones with zero external dependencies (0 parameters needed for extraction) are Tier 1. Highly entangled clones are Tier 4. 

### 5. Architectural Distance
* **Script:** `evaluate_architectural_distance.py`
* **Mechanism:** Computes the tree-traversal distance across the target repository's directory structure to find the deepest common ancestor between two clone instances.
* **Curriculum Impact:** Measures contextual isolation. 
  * `Distance 0`: Intra-file proximity (Easy)
  * `Distance 1-2`: Intra-package / Sibling files
  * `Distance 3+`: Inter-package / Globally dispersed (Hard) 

---

## Setup & Dependencies

This suite is designed to be lightweight, deterministic, and natively integrable into larger machine learning data-engineering pipelines. 

**Requirements:**
* Python 3.8+
* Built-in standard libraries strictly utilized (`ast`, `tokenize`, `difflib`, `pathlib`, `json`, `io`, `re`). **No external dependencies are required.**

---

## Usage

Each script can be run standalone to test specific heuristics, or imported as a module into your dataset compilation pipeline.

### Standalone Execution
You can run any of the scripts directly from the command line to view the JSON-formatted evaluation of built-in sample snippets:

```bash
python evaluate_controlflow_complexity.py
python evaluate_similarity_thresholds.py
python evaluate_semantic_divergence.py
python evaluate_dataflow_coupling.py
python evaluate_architectural_distance.py

```

### Pipeline Integration (Curriculum Tier Routing)

To synthesize these 5 dimensions into a unified curriculum buffer, import the evaluators into your main data-shuffling script:

```python
from evaluate_semantic_divergence import evaluate_semantic_divergence
from evaluate_dataflow_coupling import evaluate_dataflow_coupling
# ... import others ...

def compute_curriculum_tier(clone_a, clone_b, path_a, path_b):
    # 1. Gather all 5 orthogonal vectors
    semantic_score = evaluate_semantic_divergence(clone_a, clone_b)['divergence_score']
    coupling_score = evaluate_dataflow_coupling(clone_a, clone_b)['pair_coupling_score']
    arch_distance = evaluate_architectural_distance(path_a, path_b)['architectural_tier']
    # ...
    
    # 2. Compute composite difficulty metric (example weighting)
    # The resulting float/integer determines the dynamic sampling ratio (alpha_e)
    # mapping this pair to a specific training phase.
    composite_difficulty = (semantic_score * 0.4) + (coupling_score * 0.4) + (arch_distance * 0.2)
    
    return composite_difficulty

```

---

## Input Requirements

* **Source Code Sanitization:** The input strings must be valid Python syntax. The AST parsing will fail (`SyntaxError`) if the code is malformed. If the snippet fails to parse, the modules default to the highest difficulty tier (assuming the LLM will have to rely purely on raw semantic embeddings rather than structural heuristics).
* **Metadata:** Dimension 5 requires file paths relative to the repository root.
