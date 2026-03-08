# Technical Report: Multi-Dimensional Complexity Evaluation Suite for Dom4LLM

## 1. Overview and Rationale
This repository contains the deterministic evaluation suite utilized in the **Dom4LLM** (Domain-Adaptive Large Language Models for Automated Code Clone Refactoring) pipeline. Adapting Large Language Models (LLMs) to project-specific structural idioms requires a rigorously engineered curriculum learning sequence. Relying on random sampling during fine-tuning often results in catastrophic forgetting or representation collapse due to domain shift.

To facilitate an optimal learning trajectory—from generalized software patterns to highly localized, project-specific idioms—this suite evaluates contrastive code clone pairs across five orthogonal dimensions. The metrics dynamically construct a complexity matrix, generating a composite difficulty score that maps each pair to a specific curriculum tier. 

## 2. The 5-Axis Complexity Matrix

The evaluation suite calculates metrics across five discrete axes. Each dimension is handled by a dedicated Tree-sitter AST parsing script to ensure cross-language compatibility (primarily targeting Java and Python) and fault tolerance against malformed code snippets.

### 2.1. Internal Control-Flow Complexity
**Script:** `evaluate_controlflow_complexity.py`

This module quantifies the cognitive load required to parse the internal logic of the clone snippets using an Asymmetry-Penalized Alignment Gap model. It parses the Abstract Syntax Tree (AST) to count linearly independent paths (McCabe's Cyclomatic Complexity, $c$), capturing explicit branches (`if`, `for`, `while`, `catch`) and implicit short-circuits (`&&`, `||`).



To account for the structural divergence inherent in heavily modified code clones (e.g., mapping a straight-line function to a heavily nested one), the pair's composite score is computed using the following formula:

$$Score_{CF} = \max(c_1, c_2) + \gamma \cdot |c_1 - c_2|$$

Where $\gamma$ is the penalty weight (default $\gamma = 0.5$). This guarantees that structurally asymmetric pairs are ranked as strictly more difficult than symmetric pairs of an equivalent base complexity.

### 2.2. Lexical and Structural Similarity Thresholds
**Script:** `evaluate_similarity_thresholds.py`

This module assesses the surface-level pattern matching required by the LLM. It calculates two distinct metrics:
1.  **Lexical Similarity ($Sim_{lex}$):** The Jaccard index of normalized leaf-node tokens (ignoring comments).
2.  **Structural Similarity ($Sim_{str}$):** The Ratcliff/Obershelp sequence matching ratio computed over the flattened AST node-type sequence.



To prevent a high score in one metric from masking a catastrophic failure in the other (e.g., identical AST but completely divergent variable names), the composite score utilizes an Imbalance-Penalizing Harmonic Mean:

$$Score_{Sim} = \frac{2 \cdot Sim_{lex} \cdot Sim_{str}}{Sim_{lex} + Sim_{str}}$$

This formulation mathematically penalizes structural-lexical asymmetry, pulling the composite score toward the lower boundary, analogous to an F1-score computation.

### 2.3. Semantic Divergence (Clone Taxonomy)
**Script:** `evaluate_semantic_divergence.py`

This dimension maps the clone pair into the standard software engineering taxonomy (Type-1 through Type-4), returning a discrete divergence penalty $\in \{1, 2, 3, 4\}$.



* **Type-1 (Score 1):** Exact textual match (ignoring whitespace and comments).
* **Type-2 (Score 2):** Identical AST structural sequence; divergent literals/identifiers.
* **Type-3 (Score 3):** High structural overlap. The sequence matching ratio ($Ratio \ge 0.70$) indicates statement insertions, deletions, or modifications.
* **Type-4 (Score 4):** Syntactically divergent ($Ratio < 0.70$), forcing the model to rely purely on semantic representation rather than structural alignment.

### 2.4. Data-Flow Coupling Density
**Script:** `evaluate_dataflow_coupling.py`

This is the most critical metric for establishing safe preconditions for automated *Extract Method* refactorings. The module performs a localized def-use chain analysis via the AST. It tracks locally declared variables and identifies all external references (identifiers used inside the clone but declared outside its scope). These external references constitute the mandatory parameter set ($In(i)$) for the target refactored method.



Because resolving multiple external boundaries simultaneously compounds the difficulty exponentially, a simple arithmetic maximum is insufficient. The pair score is calculated using the Euclidean Coupling Magnitude of the external dependency vectors $d_1$ and $d_2$:

$$Score_{DF} = \sqrt{d_1^2 + d_2^2}$$

A pair requiring 4 parameters each ($d_1=4, d_2=4$) yields a magnitude of $5.66$, correctly ranking it as more complex than an asymmetric pair ($d_1=4, d_2=0$, magnitude $4.0$).

### 2.5. Architectural Distance
**Script:** `evaluate_architectural_distance.py`

This module evaluates the contextual isolation of the clone pair by representing the repository directory structure as a mathematical tree. The contextual gap is defined by the number of edge traversals required to navigate from the origin file to the deepest common ancestor, and down to the target file.



$$Score_{Arch} = \text{Steps}_{up} + \text{Steps}_{down}$$

The distances map to discrete architectural tiers:
* **Tier 1 ($Distance = 0$):** Intra-file proximity. Identical namespace and context window.
* **Tier 2 ($Distance \le 2$):** Intra-package proximity.
* **Tier 3 ($Distance \le 4$):** Cross-package proximity.
* **Tier 4 ($Distance > 4$):** Inter-package, globally dispersed clones requiring substantial global context resolution.

## 3. Data Synthesis and Curriculum Routing
**Script:** `merge_evaluations.py`

The final stage of the evaluation pipeline reads the orthogonal outputs, normalizes the unbounded metrics to a $[0.0, 1.0]$ continuous scale, and computes the composite difficulty vector.

For unbounded metrics like Control-Flow ($Score_{CF}$) and Data-Flow ($Score_{DF}$), min-max scaling is applied relative to empirically defined ceilings:

$$Norm(x) = \max\left(0, \min\left(1, \frac{x - \min}{\max - \min}\right)\right)$$

The final Curriculum Difficulty Score is computed via a weighted sum, explicitly prioritizing the Data-Flow Coupling bounds critical for refactoring safety:

$$Tier_{Composite} = (CF_{norm} \cdot 0.15) + ((1 - Sim_{norm}) \cdot 0.20) + (Sem_{norm} \cdot 0.25) + (DF_{norm} \cdot 0.25) + (Arch_{norm} \cdot 0.15)$$

This continuous variable $\in [0.0, 1.0]$ is subsequently quantized into four discrete training batches (Tiers 1-4), dictating the dynamic sampling ratio ($\alpha_e$) during the target-domain adaptation epochs.

## 4. Execution Protocol

The suite includes a fully automated, cross-platform batch processing engine (`run_pipeline.py`). It dynamically utilizes `pathlib.rglob` to discover all target dataset inputs across multiple domain directories and ensures execution isolation.

**Command Line Execution:**
```bash
python run_pipeline.py --input ./data --output ./output/complexity/

---

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
