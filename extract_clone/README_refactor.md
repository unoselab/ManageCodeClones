# AST Clone Extractability Dashboard

This project provides a robust, HTML-based visualization dashboard for analyzing the **extractability** of code clones in Java. By parsing the Abstract Syntax Tree (AST) and performing localized Data-Flow Analysis, the tool mathematically proves whether a code clone can be safely refactored using the **Extract Method** technique.

## Overview

Given a JSONL file of clone classes and their line ranges, this tool uses `tree-sitter-java` to locate the enclosing methods, track variable reads/writes, and dynamically synthesize the exact method signature required to extract the clone.

## Key Features

### 1. Granular Data-Flow Analysis ($V_r$ and $V_w$)
The tool performs compiler-level data-flow analysis to track variable state across three distinct regions of the enclosing method:
* **Pre-Region:** Code executing before the clone.
* **Within-Region (The Clone):** Code inside the clone boundary.
* **Post-Region:** Code executing after the clone.

For each variable, it records exact line numbers for **Reads ($V_r$)** and **Writes ($V_w$)**, providing a transparent view of the clone's environmental dependencies.

### 2. Automated Signature Synthesis
Instead of guessing parameters, the dashboard acts as a visual compiler. It auto-generates the target method signature (e.g., `public void extractedClone(Map<String, Object> realmAccess, Set<String> roles)`) based on the data-flow intersection. It successfully handles:
* Single return types vs. `void`.
* Parameter deduplication.
* Type resolution from original local/parameter declarations.

### 3. Mathematical Derivation Proofs
The dashboard displays the formal mathematical formulas used to derive the signature, bridging academic theory with practical code structure:
* **Parameters Derivation:** $\mathsf{In}(i) = \mathsf{Use}(i) \cap \mathsf{Def}_{\text{before}}(i)$
* **Return Type Derivation:** $\mathsf{Out}(i) = \mathsf{Def}_{\text{within}}(i) \cap \mathsf{Use}_{\text{after}}(i)$

It shows the exact variable sets being intersected so users can verify the logic at a glance.

### 4. Rich Code Visualization
The tool generates a highly readable, IDE-like code viewer directly in the browser:
* **Line Numbers:** Non-selectable gutter for easy cross-referencing with the metadata.
* **Region-Based Syntax Coloring:** * Purple: Method Signatures
  * Blue: Pre-clone code
  * **Red (Bold): The Clone Block**
  * Black: Post-clone code
* **Input Highlighting:** Variables that are mathematically required as parameters ($\mathsf{In}(i)$) are dynamically highlighted with a yellow background inside the clone block, utilizing regex word boundaries (`\b`) for precise targeting.

## Technical Stack
* **Python 3**
* **Tree-sitter (Java):** For robust AST parsing, scope boundary detection, and node-level Read/Write classification.
* **HTML/CSS:** Zero-dependency template generation for instantaneous browser rendering.

## How it Works
1. **Index Methods:** Scans the Java files and indexes all method boundaries.
2. **Match Clones:** Finds the enclosing method for a given clone's line range.
3. **Traverse AST:** Walks the method's AST to catalog parameters, local variable declarations (ignoring inner-class scope bleed), and identifier interactions.
4. **Compute Regions:** Classifies interactions into Pre/Within/Post sets using "Paper Logic" (e.g., ignoring variables read in the clone if they were also locally defined in the clone).
5. **Render:** Formats the sets and dynamically injects them into HTML templates.

## Usage

Run the main Python script, passing in your JSONL clone data and the base directory of the target repository:

```bash
python main.py --jsonl clones.jsonl --base-dir /path/to/java/repo --output clone_visualization.html
