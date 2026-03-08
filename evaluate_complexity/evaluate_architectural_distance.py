import json
from pathlib import Path
import os

def calculate_tree_distance(path1: str, path2: str) -> dict:
    """
    Calculates the structural distance between two files in a repository tree.
    It counts the number of edge traversals (up to a common ancestor, then down)
    required to navigate from path1 to path2.
    """
    p1 = Path(path1).resolve()
    p2 = Path(path2).resolve()
    
    # If they are the exact same file
    if p1 == p2:
        return {
            "distance_metric": 0,
            "common_ancestor": str(p1.parent)
        }
    
    # Find the deepest common ancestor directory
    parts1 = p1.parts
    parts2 = p2.parts
    
    common_prefix_length = 0
    for part1, part2 in zip(parts1, parts2):
        if part1 == part2:
            common_prefix_length += 1
        else:
            break
            
    common_ancestor = Path(*parts1[:common_prefix_length])
    
    # Distance is the number of steps UP from path1 to the common ancestor,
    # plus the number of steps DOWN to path2.
    steps_up = len(parts1) - common_prefix_length
    steps_down = len(parts2) - common_prefix_length
    total_distance = steps_up + steps_down
    
    return {
        "distance_metric": total_distance,
        "common_ancestor": str(common_ancestor)
    }

def evaluate_architectural_distance(clone_1_filepath: str, clone_2_filepath: str) -> dict:
    """
    Evaluates the architectural proximity of two clone candidates and categorizes 
    them into a 1-4 curriculum tier.
    """
    tree_metrics = calculate_tree_distance(clone_1_filepath, clone_2_filepath)
    distance = tree_metrics["distance_metric"]
    
    # ---------------------------------------------------------
    # Tier 1: Intra-file / Intra-class
    # ---------------------------------------------------------
    # The clones live in the exact same file. 
    if distance == 0:
        tier = 1
        description = "Intra-file proximity. Clones share identical namespace and imports."
        
    # ---------------------------------------------------------
    # Tier 2: Intra-package / Sibling files
    # ---------------------------------------------------------
    # distance == 2 means: UP 1 step to parent dir, DOWN 1 step to sibling file.
    elif distance <= 2:
        tier = 2
        description = "Intra-package proximity. Clones reside in the same directory/module."
        
    # ---------------------------------------------------------
    # Tier 3: Cross-package / Neighboring modules
    # ---------------------------------------------------------
    # e.g., src/module_A/file1.py vs src/module_B/file2.py
    # distance == 4 (UP 2, DOWN 2)
    elif distance <= 4:
        tier = 3
        description = "Cross-package proximity. Clones share a recent common ancestor directory."
        
    # ---------------------------------------------------------
    # Tier 4: Globally dispersed / Inter-package
    # ---------------------------------------------------------
    # Clones are in completely disjoint sections of the repository.
    else:
        tier = 4
        description = "Inter-package dispersion. Clones are architecturally isolated from each other."

    return {
        "clone_1_path": clone_1_filepath,
        "clone_2_path": clone_2_filepath,
        "tree_distance": distance,
        "architectural_tier": tier,
        "description": description,
        "common_ancestor": tree_metrics["common_ancestor"]
    }

# ==========================================
# Example Usage
# ==========================================
if __name__ == "__main__":
    
    # Example 1: Clones inside the exact same file (Tier 1)
    # E.g., two overloaded methods in the same class
    path_1a = "project/src/auth/login.py"
    path_1b = "project/src/auth/login.py"

    # Example 2: Clones in the same package/directory (Tier 2)
    path_2a = "project/src/auth/login.py"
    path_2b = "project/src/auth/register.py"

    # Example 3: Clones in different but related packages (Tier 3)
    path_3a = "project/src/auth/login.py"
    path_3b = "project/src/security/crypto.py"

    # Example 4: Clones widely dispersed across the repository (Tier 4)
    path_4a = "project/src/auth/login.py"
    path_4b = "project/tests/legacy/test_helpers.py"

    print("--- Evaluating Tier 1 (Intra-file) ---")
    print(json.dumps(evaluate_architectural_distance(path_1a, path_1b), indent=4))
    
    print("\n--- Evaluating Tier 2 (Intra-package) ---")
    print(json.dumps(evaluate_architectural_distance(path_2a, path_2b), indent=4))

    print("\n--- Evaluating Tier 3 (Cross-package) ---")
    print(json.dumps(evaluate_architectural_distance(path_3a, path_3b), indent=4))

    print("\n--- Evaluating Tier 4 (Globally Dispersed) ---")
    print(json.dumps(evaluate_architectural_distance(path_4a, path_4b), indent=4))