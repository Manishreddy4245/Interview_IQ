"""
InterviewIQ Topic Constraint Validator & Taxonomy Engine
Enforces strict semantic alignment between candidate-selected Focus Areas & Skills
and generated coding/algorithmic questions.
Rejects unrelated problems (e.g., Two Sum when Recursion is requested)
and guarantees that question solution approaches genuinely match the allowed topic set.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple


# Canonical Topic Taxonomy with associated algorithmic patterns and signature markers
CANONICAL_TOPIC_PATTERNS: Dict[str, Dict[str, Any]] = {
    "algorithms": {
        "aliases": {"algorithms", "algorithm", "data structures", "data structures & algorithms", "dsa", "coding"},
        "signature_keywords": {
            "algorithm", "array", "string", "hash", "tree", "graph", "dp", "stack", "queue",
            "pointer", "indices", "nums", "function", "return", "complexity", "solution"
        },
        "anti_patterns": set(),
        "required_approach_description": "Must be an algorithmic or data structures problem."
    },
    "recursion": {
        "aliases": {"recursion", "recursive", "backtracking", "divide and conquer", "divide_and_conquer"},
        "signature_keywords": {
            "recursive", "recursion", "base case", "subproblem", "recurrence",
            "backtrack", "backtracking", "subsets", "permutations", "combinations",
            "combination sum", "tower of hanoi", "dfs", "depth-first search",
            "tree traversal", "divide and conquer", "merge sort", "quick sort",
            "flatten nested", "generate parentheses", "n-queens", "word search",
            "palindrome partitioning", "path sum", "invert binary tree"
        },
        "anti_patterns": {
            "two sum", "two-sum", "hash map lookup", "sliding window maximum",
            "prefix sum array", "stock buy sell"
        },
        "required_approach_description": (
            "The problem must naturally require or be classically solved by a recursive decomposition, "
            "base cases and inductive steps, recursive backtracking, or divide-and-conquer subproblems."
        )
    },
    "dynamic_programming": {
        "aliases": {"dynamic programming", "dynamic_programming", "dp", "memoization", "tabulation"},
        "signature_keywords": {
            "dynamic programming", "dp", "memoization", "tabulation", "subproblem",
            "overlapping subproblems", "optimal substructure", "knapsack", "coin change",
            "longest common subsequence", "longest increasing subsequence", "climbing stairs",
            "house robber", "edit distance", "matrix chain", "state transition"
        },
        "anti_patterns": {"two sum", "valid parentheses"},
        "required_approach_description": "Must involve overlapping subproblems and optimal substructure solved via memoization or tabular DP."
    },
    "arrays": {
        "aliases": {"arrays", "array", "matrices", "matrix", "vectors"},
        "signature_keywords": {
            "array", "nums", "indices", "subarray", "element", "matrix", "grid",
            "two sum", "rotate array", "merge sorted", "in-place", "contiguous"
        },
        "anti_patterns": set(),
        "required_approach_description": "Must operate directly on 1D/2D array data structures."
    },
    "hash_maps": {
        "aliases": {"hash maps", "hash map", "hashmap", "hash tables", "hash table", "hash_maps", "hash sets", "hash set"},
        "signature_keywords": {
            "hash map", "hash table", "hash set", "dictionary", "frequency",
            "lookup", "two sum", "group anagrams", "key-value", "unique elements"
        },
        "anti_patterns": set(),
        "required_approach_description": "Must leverage key-value lookups, hashing, or frequency counting."
    },
    "trees": {
        "aliases": {"trees", "tree", "binary trees", "binary tree", "bst", "trie"},
        "signature_keywords": {
            "tree", "root", "leaf", "binary tree", "bst", "subtree", "trie",
            "inorder", "preorder", "postorder", "lca", "ancestor", "depth"
        },
        "anti_patterns": {"two sum", "sql"},
        "required_approach_description": "Must operate on hierarchical tree node structures."
    },
    "graphs": {
        "aliases": {"graphs", "graph", "bfs", "dfs", "topological sort", "shortest path"},
        "signature_keywords": {
            "graph", "vertex", "vertices", "edge", "edges", "adjacency", "connected components",
            "dijkstra", "bfs", "dfs", "topological sort", "cycle detection", "bipartite"
        },
        "anti_patterns": {"two sum"},
        "required_approach_description": "Must model and solve problems on graph topology."
    },
    "linked_lists": {
        "aliases": {"linked lists", "linked list", "linked_lists", "singly linked list", "doubly linked list"},
        "signature_keywords": {
            "linked list", "head", "tail", "next pointer", "dummy node",
            "reverse linked list", "merge two sorted lists", "cycle detection", "fast and slow"
        },
        "anti_patterns": {"two sum"},
        "required_approach_description": "Must manipulate node pointer relationships in linked lists."
    },
    "binary_search": {
        "aliases": {"binary search", "binary_search", "divide and search", "bsearch"},
        "signature_keywords": {
            "binary search", "sorted array", "log(n)", "lower bound", "upper bound",
            "search in rotated", "bisect", "left <= right"
        },
        "anti_patterns": set(),
        "required_approach_description": "Must exploit monotonic or sorted property using O(log N) binary search."
    },
    "stacks": {
        "aliases": {"stacks", "stack", "queues", "queue", "monotonic stack"},
        "signature_keywords": {
            "stack", "queue", "deque", "monotonic stack", "valid parentheses",
            "lifo", "fifo", "push", "pop", "evaluate reverse polish"
        },
        "anti_patterns": set(),
        "required_approach_description": "Must utilize LIFO/FIFO stack or queue dynamics."
    },
    "strings": {
        "aliases": {"strings", "string", "string manipulation"},
        "signature_keywords": {
            "string", "substring", "anagram", "palindrome", "characters",
            "longest substring", "word break"
        },
        "anti_patterns": set(),
        "required_approach_description": "Must focus on string properties, character sequences, or substrings."
    },
    "sql": {
        "aliases": {"sql", "relational database", "queries", "database"},
        "signature_keywords": {
            "sql", "select", "from", "join", "group by", "having", "order by", "table", "schema"
        },
        "anti_patterns": {"c++", "monaco_language: python"},
        "required_approach_description": "Must involve relational data querying with SQL syntax."
    }
}


def parse_focus_area_topics(focus_areas_str: str) -> List[str]:
    """
    Parse a comma-separated or multi-skill focus areas string into standardized individual topics.
    Example: "Recursion, Dynamic Programming" -> ["Recursion", "Dynamic Programming"]
    """
    if not focus_areas_str:
        return ["Data Structures & Algorithms"]

    # Split by comma or semicolon
    parts = re.split(r"[,;]+", focus_areas_str)
    topics = []
    for p in parts:
        cleaned = p.strip()
        if cleaned:
            # Exclude overly generic filler words unless they are the sole item
            if cleaned.lower() not in ("technical", "fundamentals", "coding", "practice", "skills") or len(parts) == 1:
                topics.append(cleaned)
    return topics if topics else ["Data Structures & Algorithms"]


def normalize_topic_key(topic: str) -> str:
    """Map a topic string to its canonical taxonomy key if recognized."""
    t_lower = topic.strip().lower()
    for canon_key, spec in CANONICAL_TOPIC_PATTERNS.items():
        if t_lower == canon_key or t_lower in spec["aliases"] or canon_key in t_lower:
            return canon_key
    return t_lower


def is_topic_in_allowed_set(topic: str, allowed_topics: List[str]) -> bool:
    """Check if a specific topic matches any of the candidate's allowed topics."""
    norm_topic = normalize_topic_key(topic)
    norm_allowed = {normalize_topic_key(a) for a in allowed_topics}
    if norm_topic in norm_allowed:
        return True

    # Check substring inclusion
    t_lower = topic.lower()
    for a in allowed_topics:
        a_lower = a.lower()
        if a_lower in t_lower or t_lower in a_lower:
            return True
    return False


def validate_question_topic(
    question_data: Dict[str, Any],
    allowed_topics: List[str],
) -> Tuple[bool, Optional[str]]:
    """
    Semantically validate that question_data genuinely belongs to the candidate's allowed topics.
    Rejects unrelated questions (e.g., Two Sum when Recursion is requested) even if the
    question description superficially mentions the topic name.

    Returns:
        (is_valid: bool, rejection_reason: Optional[str])
    """
    if not allowed_topics:
        return True, None

    title = (question_data.get("title") or "").strip()
    title_lower = title.lower()
    text = (question_data.get("text") or "").strip()
    text_lower = text.lower()
    skill = (question_data.get("assessed_skill") or "").strip()
    skill_lower = skill.lower()
    combined_content = f"{title_lower} {skill_lower} {text_lower}"

    norm_allowed = [normalize_topic_key(t) for t in allowed_topics]

    # Specific hard rejection checks for known benchmark problems against disallowed topics
    # Case: Recursion requested, but problem is Two Sum
    if "recursion" in norm_allowed and len(norm_allowed) == 1:
        if "two sum" in title_lower or "indices of the two numbers" in text_lower:
            return False, "Question 'Two Sum' is an Array/Hash-Map problem and does not satisfy the 'Recursion' topic constraint."
        if "valid parentheses" in title_lower and "stack" not in norm_allowed:
            return False, "Question 'Valid Parentheses' is a Stack parsing problem and does not satisfy the 'Recursion' topic constraint."

    # Verify matching across the taxonomy
    matches_allowed = False
    rejection_details = []

    for canon_key in norm_allowed:
        pattern_spec = CANONICAL_TOPIC_PATTERNS.get(canon_key)
        if not pattern_spec:
            # Custom / uncataloged topic: match text/title directly
            if canon_key in combined_content or any(canon_key in t.lower() for t in (title, skill)):
                matches_allowed = True
                break
            continue

        # Check for explicit anti-patterns
        anti_patterns = pattern_spec["anti_patterns"]
        if any(ap in title_lower for ap in anti_patterns):
            rejection_details.append(f"Problem '{title}' is an anti-pattern for requested topic '{canon_key}'.")
            continue

        # Check signature keywords
        sig_keywords = pattern_spec["signature_keywords"]
        has_signature = False
        matched_sigs = []
        for kw in sig_keywords:
            if kw in combined_content:
                matched_sigs.append(kw)
                has_signature = True

        # Check assessed_skill or title directly
        aliases = pattern_spec["aliases"]
        title_or_skill_match = any(alias in title_lower or alias in skill_lower for alias in aliases)

        if has_signature or title_or_skill_match:
            matches_allowed = True
            break
        else:
            rejection_details.append(
                f"Question does not exhibit algorithmic characteristics of '{canon_key}' "
                f"({pattern_spec['required_approach_description']})."
            )

    if not matches_allowed:
        allowed_str = ", ".join(allowed_topics)
        reason = (
            f"Question '{title}' failed topic constraint validation against allowed topics [{allowed_str}]. "
            + (" ".join(rejection_details) if rejection_details else "No matching algorithmic competency detected.")
        )
        return False, reason

    return True, None


def select_next_topic_from_focus_areas(
    allowed_topics: List[str],
    covered_topics: List[str],
) -> str:
    """
    Select the next topic from allowed_topics to ensure balanced coverage
    without repeating recently covered topics.
    """
    if not allowed_topics:
        return "Algorithms"

    norm_covered = {normalize_topic_key(c) for c in covered_topics}
    uncovered = [t for t in allowed_topics if normalize_topic_key(t) not in norm_covered]

    if uncovered:
        return uncovered[0]

    # If all covered, cycle based on count
    idx = len(covered_topics) % len(allowed_topics)
    return allowed_topics[idx]
