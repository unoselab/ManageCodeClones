# AST Clone Extractability Dashboard & Pipeline

This project provides a robust pipeline and HTML-based visualization dashboard for analyzing the **extractability** of code clones in Java. By parsing the Abstract Syntax Tree (AST) and performing localized Data-Flow Analysis, the tool mathematically proves whether a code clone can be safely refactored using the **Extract Method** technique, generating a highly accurate, augmented JSONL dataset ready for LLM training.

## Overview

Given a JSONL file of clone classes and their line ranges, this tool uses `tree-sitter-java` to locate the enclosing methods, track variable reads/writes, and dynamically synthesize the exact method signature required to extract the clone. It outputs both a visual HTML proof of the refactoring and a data-rich JSONL file for downstream machine learning tasks.

## Key Features

### 1. Granular Data-Flow Analysis ($V_r$ and $V_w$)

The tool performs compiler-level data-flow analysis to track variable state across three distinct regions of the enclosing method:

* **Pre-Region:** Code executing before the clone.
* **Within-Region (The Clone):** Code inside the clone boundary.
* **Post-Region:** Code executing after the clone.

Standard AST tools struggle with deep mutations, but this pipeline traverses *upward* through the AST to accurately classify complex interactions:

* **Array Mutations:** Accurately flags `arr` as both Read (to resolve reference) and Written in statements like `arr[i] = 10;`.
* **Object Field Mutations:** Recognizes when an object's properties are mutated (e.g., `config.timeout = 5000;`), correctly capturing `config` as an input.
* **Self (`this`) References:** Parses `field_identifier` nodes to ensure assignments like `this.count = 1;` are recorded as writes.

### 2. Intelligent Scope & Boundary Detection

* **Constructor Support:** Captures `constructor_declaration` nodes, allowing the analysis of object initialization refactoring patterns.
* **Overloaded Methods:** Dynamically keys methods by qualified name and line number (`Class.Method_LineNo`) to prevent method overloading bugs during AST indexing.
* **Class Field Injection:** Extracts instance and static variables from the enclosing class. If a clone relies on class-level state (e.g., `cache.put()`), the tool injects the field into the $\mathsf{In}(i)$ set as an explicit input parameter.
* **Logger & Constant Exclusion:** Heuristic regex filters automatically drop common static utilities (e.g., `LOG`) and `ALL_CAPS` constants from the field definitions, preventing hallucinated parameters.

### 3. Automated Signature Synthesis & Type Mapping

Instead of guessing parameters, the pipeline acts as a visual compiler. It auto-generates the target method signature based on the data-flow intersection:

* **Rich Generics Extraction:** Class field types are dynamically extracted from the AST (e.g., `Map<String, DefaultExchangeHolder>`) to yield strictly-typed native Java signatures rather than defaulting to `Object`.
* **Modifier Preservation:** Modifiers on local parameters (e.g., `final Message`) are tracked and preserved.
* **The "Return" Trap:** If a clone block contains an explicit `return;` statement (causing an empty $\mathsf{Use}_{\text{after}}$ set), the script intelligently falls back to the enclosing method's original return type instead of incorrectly assigning `void`.
* **Multi-Variable Returns:** If a clone block modifies multiple variables used *after* the block executes, it calculates an advanced signature utilizing Tuples (e.g., `Tuple<boolean, String>`).

### 4. Mathematical Derivation Proofs

The dashboard displays the formal mathematical formulas used to derive the signature, bridging academic theory with practical code structure:

* **Parameters Derivation:** $\mathsf{In}(i) = \mathsf{Use}(i) \cap \mathsf{Def}_{\text{before}}(i)$
* **Return Type Derivation:** $\mathsf{Out}(i) = \mathsf{Def}_{\text{within}}(i) \cap \mathsf{Use}_{\text{after}}(i)$

It shows the exact variable sets being intersected so users can verify the logic at a glance.

### 5. Rich Code Visualization

The tool generates a highly readable, IDE-like code viewer directly in the browser:

* **Line Numbers:** Non-selectable gutter for easy cross-referencing.
* **Region-Based Syntax Coloring:** * Purple: Method Signatures
* Blue: Pre-clone code
* **Red (Bold): The Clone Block**
* Black: Post-clone code


* **Input Highlighting:** Variables mathematically required as parameters ($\mathsf{In}(i)$) are dynamically highlighted with a yellow background inside the clone block utilizing regex word boundaries.

## Technical Stack

* **Python 3**
* **Tree-sitter (Java):** For robust AST parsing, scope boundary detection, and node-level Read/Write classification.
* **HTML/CSS:** Zero-dependency template generation for instantaneous browser rendering.

## Output Schema

The resulting augmented JSONL appends critical data to each clone instance for LLM training:

* `is_full_function_clone`: Boolean flag indicating if the clone spans the entire method.
* `Variables Read (V_r)` / `Variables Written (V_w)`: Categorized by Pre, Within, and Post regions.
* `In`: The exact variables and mapped types required to be passed into the extracted method.
* `Out`: The variables modified within the block that must be returned.
* `Extracted Signature`: A fully compilable, strictly-typed Java method signature.
* `ReturnType`: The inferred return type (Void, Single Type, or Tuple).

## How it Works

1. **Index Methods:** Scans the Java files and indexes all method and constructor boundaries.
2. **Match Clones:** Finds the enclosing method for a given clone's line range.
3. **Traverse AST:** Walks the method's AST to catalog parameters, local variables, and class-level fields (stripping generic constants).
4. **Compute Regions:** Classifies identifier interactions into Pre/Within/Post sets using precise data-flow logic.
5. **Render & Export:** Formats the sets, dynamically injects them into HTML templates, and writes the mathematically proven signatures to the JSONL dataset.

## Usage

Run the main Python script, passing in your JSONL clone data and the base directory of the target repository:

```bash
python main.py \
  --jsonl ./data/input_clones.jsonl \
  --base-dir /path/to/java/repo \
  --output ./output/visualization.html \
  --out-jsonl ./output/augmented_clones.jsonl \
  --apply-drop-filters

```

*Note: Omit the `--apply-drop-filters` flag if you want to keep full-function clones and single-instance classes in your dataset (they will be tagged but not removed).*