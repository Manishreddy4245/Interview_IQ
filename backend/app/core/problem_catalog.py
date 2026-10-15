"""
Authoritative Problem Catalog and Canonical Question Type Resolver for InterviewIQ.
Provides standardized benchmark definitions for CODING (LeetCode-style) and SQL problems,
along with trustworthy metadata resolution and compatibility handling.
"""

from typing import Any, Dict, List, Optional, Tuple
import re


def is_genuine_verbal_prompt(text: str) -> bool:
    """
    Determines if a prompt is a genuine verbal/discussion question rather than an implementation task,
    even if it references a known DSA or technical problem name.
    """
    if not text:
        return False
    t_lower = text.strip().lower()

    # If the prompt explicitly commands writing code/functions or returns output, it is an implementation task
    if any(cmd in t_lower for cmd in [
        "write a function", "implement a function", "write an algorithm",
        "return an integer", "return the indices", "return the length",
        "return true", "return false", "return a boolean", "return an array",
        "input format", "output format", "example 1:", "constraints:"
    ]):
        return False

    # Verbal inquiry indicators
    verbal_triggers = [
        "explain", "describe", "discuss", "walk through how you would explain",
        "what are the trade-offs", "compare the theoretical", "what is the difference between",
        "how does the runtime complexity differ", "how would you justify",
        "tell me about a time", "what pros and cons"
    ]
    return any(t_lower.startswith(trigger) or f" {trigger} " in f" {t_lower} " for trigger in verbal_triggers)


BENCHMARK_PROBLEMS: Dict[str, Dict[str, Any]] = {
    "two_sum": {
        "id": "two_sum",
        "title": "Two Sum",
        "text": "Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.",
        "assessed_skill": "Arrays & Hash Maps",
        "difficulty": "Easy",
        "question_type": "coding",
        "response_mode": "coding_ide",
        "function_name": "twoSum",
        "input_format": "`nums`: integer array, `target`: integer",
        "output_format": "Return an array of two integers `[index1, index2]`",
        "constraints": [
            "2 <= nums.length <= 10^4",
            "-10^9 <= nums[i] <= 10^9",
            "-10^9 <= target <= 10^9",
            "Exactly one valid solution exists.",
            "The same element cannot be used twice.",
        ],
        "examples": [
            {
                "example_number": 1,
                "input": "nums = [2,7,11,15]\ntarget = 9",
                "output": "[0,1]",
                "explanation": "Because nums[0] + nums[1] == 2 + 7 == 9, we return [0, 1].",
            },
            {
                "example_number": 2,
                "input": "nums = [3,2,4]\ntarget = 6",
                "output": "[1,2]",
                "explanation": "Because nums[1] + nums[2] == 2 + 4 == 6, we return [1, 2].",
            },
            {
                "example_number": 3,
                "input": "nums = [3,3]\ntarget = 6",
                "output": "[0,1]",
                "explanation": "Because nums[0] + nums[1] == 3 + 3 == 6, we return [0, 1].",
            },
        ],
        "test_cases": [
            {
                "id": "tc_1",
                "input": "[2,7,11,15]\n9",
                "expected_output": "[0,1]",
                "is_hidden": False,
                "explanation": "Standard positive integer array test",
            },
            {
                "id": "tc_2",
                "input": "[3,2,4]\n6",
                "expected_output": "[1,2]",
                "is_hidden": False,
                "explanation": "Unsorted array pair test",
            },
            {
                "id": "tc_3",
                "input": "[3,3]\n6",
                "expected_output": "[0,1]",
                "is_hidden": False,
                "explanation": "Duplicate value pair test",
            },
            {
                "id": "tc_4",
                "input": "[-1,-2,-3,-4,-5]\n-8",
                "expected_output": "[2,4]",
                "is_hidden": True,
                "explanation": "Negative integer values hidden benchmark case",
            },
        ],
        "reference_solution": (
            "from typing import List\n\n"
            "class Solution:\n"
            "    def twoSum(self, nums: List[int], target: int) -> List[int]:\n"
            "        seen = {}\n"
            "        for i, num in enumerate(nums):\n"
            "            diff = target - num\n"
            "            if diff in seen:\n"
            "                return [seen[diff], i]\n"
            "            seen[num] = i\n"
            "        return []\n"
        ),
        "comparison_policy": "strict_structural",
        "oracle_verified": True,
        "oracle_provenance": "benchmark_catalog",
        "code_template": {
            "python": "from typing import List\n\nclass Solution:\n    def twoSum(self, nums: List[int], target: int) -> List[int]:\n        # Implement your O(N) solution here\n        pass\n",
            "javascript": "/**\n * @param {number[]} nums\n * @param {number} target\n * @return {number[]}\n */\nfunction twoSum(nums, target) {\n    // Implement your solution here\n}\n",
            "typescript": "function twoSum(nums: number[], target: number): number[] {\n    // Implement your solution here\n    return [];\n}\n",
            "cpp": "#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        return {};\n    }\n};\n",
            "java": "import java.util.*;\n\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n        return new int[]{};\n    }\n}\n",
        },
    },

    "valid_parentheses": {
        "id": "valid_parentheses",
        "title": "Valid Parentheses",
        "text": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.\n\nAn input string is valid if:\n1. Open brackets must be closed by the same type of brackets.\n2. Open brackets must be closed in the correct order.\n3. Every close bracket has a corresponding open bracket of the same type.",
        "assessed_skill": "Stacks & String Parsing",
        "difficulty": "Easy",
        "question_type": "coding",
        "response_mode": "coding_ide",
        "function_name": "isValid",
        "input_format": "`s`: string containing only brackets `()[]{}`",
        "output_format": "Return a boolean (`true` or `false`) indicating bracket validity.",
        "constraints": [
            "1 <= s.length <= 10^4",
            "s consists of parentheses only: ()[]{}",
        ],
        "examples": [
            {
                "example_number": 1,
                "input": 's = "()"',
                "output": "true",
                "explanation": "Simple matched parentheses pair.",
            },
            {
                "example_number": 2,
                "input": 's = "()[]{}"',
                "output": "true",
                "explanation": "Multiple matched consecutive pairs.",
            },
            {
                "example_number": 3,
                "input": 's = "(]"',
                "output": "false",
                "explanation": "Mismatched closing bracket type.",
            },
        ],
        "test_cases": [
            {"id": "tc_1", "input": "()", "expected_output": "true", "is_hidden": False},
            {"id": "tc_2", "input": "()[]{}", "expected_output": "true", "is_hidden": False},
            {"id": "tc_3", "input": "(]", "expected_output": "false", "is_hidden": False},
            {"id": "tc_4", "input": "([)]", "expected_output": "false", "is_hidden": True},
            {"id": "tc_5", "input": "{[]}", "expected_output": "true", "is_hidden": True},
        ],
        "reference_solution": (
            "class Solution:\n"
            "    def isValid(self, s: str) -> bool:\n"
            "        stack = []\n"
            "        mapping = {')': '(', '}': '{', ']': '['}\n"
            "        for char in s:\n"
            "            if char in mapping:\n"
            "                top = stack.pop() if stack else '#'\n"
            "                if mapping[char] != top:\n"
            "                    return False\n"
            "            else:\n"
            "                stack.append(char)\n"
            "        return not stack\n"
        ),
        "comparison_policy": "strict_structural",
        "oracle_verified": True,
        "oracle_provenance": "benchmark_catalog",
        "code_template": {
            "python": "class Solution:\n    def isValid(self, s: str) -> bool:\n        # Implement stack-based validation\n        pass\n",
            "javascript": "/**\n * @param {string} s\n * @return {boolean}\n */\nfunction isValid(s) {\n    // Implement stack-based validation\n}\n",
            "typescript": "function isValid(s: string): boolean {\n    return false;\n}\n",
            "cpp": "#include <string>\n#include <stack>\nusing namespace std;\n\nclass Solution {\npublic:\n    bool isValid(string s) {\n        return false;\n    }\n};\n",
            "java": "import java.util.*;\n\nclass Solution {\n    public boolean isValid(String s) {\n        return false;\n    }\n}\n",
        },
    },

    "longest_substring": {
        "id": "longest_substring",
        "title": "Longest Substring Without Repeating Characters",
        "text": "Given a string s, find the length of the longest substring without repeating characters.",
        "assessed_skill": "Sliding Window & Hash Sets",
        "difficulty": "Medium",
        "question_type": "coding",
        "response_mode": "coding_ide",
        "function_name": "lengthOfLongestSubstring",
        "input_format": "`s`: string",
        "output_format": "Return an integer representing the length of the longest substring without repeating characters.",
        "constraints": [
            "0 <= s.length <= 5 * 10^4",
            "s consists of English letters, digits, symbols and spaces.",
        ],
        "examples": [
            {
                "example_number": 1,
                "input": 's = "abcabcbb"',
                "output": "3",
                "explanation": 'The answer is "abc", with the length of 3.',
            },
            {
                "example_number": 2,
                "input": 's = "bbbbb"',
                "output": "1",
                "explanation": 'The answer is "b", with the length of 1.',
            },
            {
                "example_number": 3,
                "input": 's = "pwwkew"',
                "output": "3",
                "explanation": 'The answer is "wke", with the length of 3 (note that "pwke" is a subsequence, not a substring).',
            },
        ],
        "test_cases": [
            {"id": "tc_1", "input": "abcabcbb", "expected_output": "3", "is_hidden": False, "explanation": "Mixed repeating characters"},
            {"id": "tc_2", "input": "bbbbb", "expected_output": "1", "is_hidden": False, "explanation": "All identical characters"},
            {"id": "tc_3", "input": "pwwkew", "expected_output": "3", "is_hidden": False, "explanation": "Overlapping window"},
            {"id": "tc_4", "input": "", "expected_output": "0", "is_hidden": True, "explanation": "Empty string boundary"},
            {"id": "tc_5", "input": "au", "expected_output": "2", "is_hidden": True, "explanation": "Two distinct characters"},
            {"id": "tc_6", "input": "dvdf", "expected_output": "3", "is_hidden": True, "explanation": "Non-adjacent duplicates"},
        ],
        "reference_solution": (
            "class Solution:\n"
            "    def lengthOfLongestSubstring(self, s: str) -> int:\n"
            "        char_set = set()\n"
            "        left = 0\n"
            "        max_len = 0\n"
            "        for right in range(len(s)):\n"
            "            while s[right] in char_set:\n"
            "                char_set.remove(s[left])\n"
            "                left += 1\n"
            "            char_set.add(s[right])\n"
            "            max_len = max(max_len, right - left + 1)\n"
            "        return max_len\n"
        ),
        "comparison_policy": "strict_structural",
        "oracle_verified": True,
        "oracle_provenance": "benchmark_catalog",
        "code_template": {
            "python": "class Solution:\n    def lengthOfLongestSubstring(self, s: str) -> int:\n        # Implement your O(N) sliding window solution here\n        pass\n",
            "javascript": "/**\n * @param {string} s\n * @return {number}\n */\nfunction lengthOfLongestSubstring(s) {\n    // Implement your sliding window solution here\n}\n",
            "typescript": "function lengthOfLongestSubstring(s: string): number {\n    // Implement your sliding window solution here\n    return 0;\n}\n",
            "cpp": "#include <string>\n#include <unordered_set>\n#include <algorithm>\nusing namespace std;\n\nclass Solution {\npublic:\n    int lengthOfLongestSubstring(string s) {\n        return 0;\n    }\n};\n",
            "java": "import java.util.*;\n\nclass Solution {\n    public int lengthOfLongestSubstring(String s) {\n        return 0;\n    }\n}\n",
        },
    },

    "max_sum_non_overlapping_subarrays": {
        "id": "max_sum_non_overlapping_subarrays",
        "title": "Maximum Sum of Two Non-Overlapping Subarrays",
        "text": "Given an integer array nums and two integers firstLen and secondLen, return the maximum sum of elements in two non-overlapping subarrays of lengths firstLen and secondLen.\n\nThe array with length firstLen could occur before or after the array with length secondLen, but they must not overlap.",
        "assessed_skill": "Dynamic Programming & Prefix Sums",
        "difficulty": "Medium",
        "question_type": "coding",
        "response_mode": "coding_ide",
        "function_name": "maxSumTwoNoOverlap",
        "input_format": "`nums`: integer array, `firstLen`: integer, `secondLen`: integer",
        "output_format": "Return an integer representing the maximum sum of two non-overlapping subarrays.",
        "constraints": [
            "firstLen + secondLen <= nums.length <= 1000",
            "1 <= firstLen, secondLen <= 1000",
            "0 <= nums[i] <= 1000",
        ],
        "examples": [
            {
                "example_number": 1,
                "input": "nums = [0,6,5,2,2,5,1,9,4]\nfirstLen = 1\nsecondLen = 2",
                "output": "20",
                "explanation": "One choice of subarrays is [9] with length 1, and [6,5] with length 2.",
            },
            {
                "example_number": 2,
                "input": "nums = [3,8,1,3,2,1,8,9,0]\nfirstLen = 3\nsecondLen = 2",
                "output": "29",
                "explanation": "One choice of subarrays is [3,8,1] with length 3, and [8,9] with length 2.",
            },
            {
                "example_number": 3,
                "input": "nums = [2,1,5,6,0,9,5,0,3,8]\nfirstLen = 4\nsecondLen = 3",
                "output": "31",
                "explanation": "One choice of subarrays is [5,6,0,9] with length 4, and [0,3,8] with length 3.",
            },
        ],
        "test_cases": [
            {
                "id": "tc_1",
                "input": "[0,6,5,2,2,5,1,9,4]\n1\n2",
                "expected_output": "20",
                "is_hidden": False,
                "explanation": "Standard case with mixed element values",
            },
            {
                "id": "tc_2",
                "input": "[3,8,1,3,2,1,8,9,0]\n3\n2",
                "expected_output": "29",
                "is_hidden": False,
                "explanation": "Subarrays near boundaries",
            },
            {
                "id": "tc_3",
                "input": "[2,1,5,6,0,9,5,0,3,8]\n4\n3",
                "expected_output": "31",
                "is_hidden": False,
                "explanation": "Longer length constraints",
            },
            {
                "id": "tc_4",
                "input": "[1,0,1]\n1\n1",
                "expected_output": "2",
                "is_hidden": True,
                "explanation": "Minimal length singleton subarrays boundary case",
            },
            {
                "id": "tc_5",
                "input": "[0,0,0,0,0]\n2\n2",
                "expected_output": "0",
                "is_hidden": True,
                "explanation": "All zeroes edge case",
            },
        ],
        "reference_solution": (
            "from typing import List\n\n"
            "class Solution:\n"
            "    def maxSumTwoNoOverlap(self, nums: List[int], firstLen: int, secondLen: int) -> int:\n"
            "        prefix = [0] * (len(nums) + 1)\n"
            "        for i, x in enumerate(nums):\n"
            "            prefix[i + 1] = prefix[i] + x\n\n"
            "        def helper(l1: int, l2: int) -> int:\n"
            "            max_l1 = 0\n"
            "            ans = 0\n"
            "            for i in range(l1 + l2, len(nums) + 1):\n"
            "                cur_l1 = prefix[i - l2] - prefix[i - l2 - l1]\n"
            "                if cur_l1 > max_l1:\n"
            "                    max_l1 = cur_l1\n"
            "                cur_l2 = prefix[i] - prefix[i - l2]\n"
            "                if max_l1 + cur_l2 > ans:\n"
            "                    ans = max_l1 + cur_l2\n"
            "            return ans\n\n"
            "        return max(helper(firstLen, secondLen), helper(secondLen, firstLen))\n"
        ),
        "comparison_policy": "strict_structural",
        "oracle_verified": True,
        "oracle_provenance": "benchmark_catalog",
        "code_template": {
            "python": "from typing import List\n\nclass Solution:\n    def maxSumTwoNoOverlap(self, nums: List[int], firstLen: int, secondLen: int) -> int:\n        # Implement your O(N) dynamic programming / prefix sum solution here\n        pass\n",
            "javascript": "/**\n * @param {number[]} nums\n * @param {number} firstLen\n * @param {number} secondLen\n * @return {number}\n */\nfunction maxSumTwoNoOverlap(nums, firstLen, secondLen) {\n    // Implement your solution here\n}\n",
            "typescript": "function maxSumTwoNoOverlap(nums: number[], firstLen: number, secondLen: number): number {\n    // Implement your solution here\n    return 0;\n}\n",
            "cpp": "#include <vector>\n#include <numeric>\n#include <algorithm>\nusing namespace std;\n\nclass Solution {\npublic:\n    int maxSumTwoNoOverlap(vector<int>& nums, int firstLen, int secondLen) {\n        return 0;\n    }\n};\n",
            "java": "import java.util.*;\n\nclass Solution {\n    public int maxSumTwoNoOverlap(int[] nums, int firstLen, int secondLen) {\n        return 0;\n    }\n}\n",
        },
    },

    "maximum_length_subarray": {
        "id": "maximum_length_subarray",
        "title": "Maximum Length of Repeated Subarray",
        "text": "Given two integer arrays nums1 and nums2, return the maximum length of a subarray that appears in both arrays.",
        "assessed_skill": "Arrays & Dynamic Programming",
        "difficulty": "Medium",
        "question_type": "coding",
        "response_mode": "coding_ide",
        "function_name": "findLength",
        "input_format": "`nums1`: integer array, `nums2`: integer array",
        "output_format": "Return an integer representing the maximum length of a common contiguous subarray.",
        "constraints": [
            "1 <= nums1.length, nums2.length <= 1000",
            "0 <= nums1[i], nums2[i] <= 100",
        ],
        "examples": [
            {
                "example_number": 1,
                "input": "nums1 = [1,2,3,2,1]\nnums2 = [3,2,1,4,7]",
                "output": "3",
                "explanation": "The repeated subarray with maximum length is [3,2,1].",
            },
            {
                "example_number": 2,
                "input": "nums1 = [0,0,0,0,0]\nnums2 = [0,0,0,0,0]",
                "output": "5",
                "explanation": "The repeated subarray with maximum length is [0,0,0,0,0].",
            },
            {
                "example_number": 3,
                "input": "nums1 = [1,2,3]\nnums2 = [4,5,6]",
                "output": "0",
                "explanation": "There are no common subarrays, so return 0.",
            },
        ],
        "test_cases": [
            {
                "id": "tc_1",
                "input": "[1,2,3,2,1]\n[3,2,1,4,7]",
                "expected_output": "3",
                "is_hidden": False,
                "explanation": "Standard repeated subarray [3,2,1] test",
            },
            {
                "id": "tc_2",
                "input": "[0,0,0,0,0]\n[0,0,0,0,0]",
                "expected_output": "5",
                "is_hidden": False,
                "explanation": "Identical arrays test",
            },
            {
                "id": "tc_3",
                "input": "[1,2,3]\n[4,5,6]",
                "expected_output": "0",
                "is_hidden": False,
                "explanation": "Disjoint arrays test",
            },
            {
                "id": "tc_4",
                "input": "[1,0,0,0,1]\n[1,0,0,1,1]",
                "expected_output": "3",
                "is_hidden": True,
                "explanation": "Repeated zeroes hidden test case",
            },
            {
                "id": "tc_5",
                "input": "[70,39,25,40,7]\n[52,20,67,5,31]",
                "expected_output": "0",
                "is_hidden": True,
                "explanation": "No common elements boundary test",
            },
        ],
        "reference_solution": (
            "from typing import List\n\n"
            "class Solution:\n"
            "    def findLength(self, nums1: List[int], nums2: List[int]) -> int:\n"
            "        m, n = len(nums1), len(nums2)\n"
            "        dp = [0] * (n + 1)\n"
            "        ans = 0\n"
            "        for i in range(1, m + 1):\n"
            "            prev = 0\n"
            "            for j in range(1, n + 1):\n"
            "                temp = dp[j]\n"
            "                if nums1[i - 1] == nums2[j - 1]:\n"
            "                    dp[j] = prev + 1\n"
            "                    if dp[j] > ans:\n"
            "                        ans = dp[j]\n"
            "                else:\n"
            "                    dp[j] = 0\n"
            "                prev = temp\n"
            "        return ans\n"
        ),
        "comparison_policy": "strict_structural",
        "oracle_verified": True,
        "oracle_provenance": "benchmark_catalog",
        "code_template": {
            "python": "from typing import List\n\nclass Solution:\n    def findLength(self, nums1: List[int], nums2: List[int]) -> int:\n        # Implement your O(M*N) dynamic programming solution here\n        pass\n",
            "javascript": "/**\n * @param {number[]} nums1\n * @param {number[]} nums2\n * @return {number}\n */\nfunction findLength(nums1, nums2) {\n    // Implement your solution here\n}\n",
            "typescript": "function findLength(nums1: number[], nums2: number[]): number {\n    // Implement your solution here\n    return 0;\n}\n",
            "cpp": "#include <vector>\n#include <algorithm>\nusing namespace std;\n\nclass Solution {\npublic:\n    int findLength(vector<int>& nums1, vector<int>& nums2) {\n        return 0;\n    }\n};\n",
            "java": "import java.util.*;\n\nclass Solution {\n    public int findLength(int[] nums1, int[] nums2) {\n        return 0;\n    }\n}\n",
        },
    },

    "sql_department_salaries": {
        "id": "sql_department_salaries",
        "title": "Department Salary Aggregation & High Earners",
        "text": "Write an SQL query to find the number of employees in each department. Return the department name (`dept_name`) and the employee count (`emp_count`).",
        "assessed_skill": "SQL Joins, Aggregation & Grouping",
        "difficulty": "Medium",
        "question_type": "sql",
        "response_mode": "sql_sandbox",
        "sql_fixture": "employees_departments",
        "input_format": "Tables: `departments` (dept_id, dept_name), `employees` (emp_id, emp_name, dept_id, salary, role)",
        "output_format": "Columns: `dept_name` (TEXT), `emp_count` (INTEGER)",
        "constraints": [
            "Query must run cleanly in isolated SQLite in-memory sandbox.",
            "Only aggregate departments present in the sample fixture.",
        ],
        "examples": [
            {
                "example_number": 1,
                "input": "Fixture: employees_departments",
                "output": "dept_name | emp_count\nEngineering | 4\nDesign | 2\nProduct | 2",
                "explanation": "Aggregates employee count grouped by department.",
            },
        ],
        "test_cases": [
            {
                "id": "tc_1",
                "input": "SELECT dept_name, count(*) as emp_count FROM departments d JOIN employees e ON d.dept_id = e.dept_id GROUP BY dept_name;",
                "expected_output": "3 rows (Engineering, Design, Product)",
                "is_hidden": False,
            },
        ],
        "code_template": {
            "sql": "-- Write your SQL query here\nSELECT dept_name, COUNT(*) AS emp_count\nFROM departments d\nJOIN employees e ON d.dept_id = e.dept_id\nGROUP BY dept_name;\n",
        },
    },
}


def find_benchmark_problem(text: str, title: Optional[str] = None, q_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Matches a question against known benchmark problems based on text or title,
    provided it is not an explicitly verbal discussion question.
    """
    if is_genuine_verbal_prompt(text):
        return None

    if q_id and q_id in BENCHMARK_PROBLEMS:
        return BENCHMARK_PROBLEMS[q_id]

    combined = f"{title or ''} {text or ''}".lower()

    if "longest substring without repeating characters" in combined or (
        "longest substring" in combined and "without repeating" in combined
    ) or "lengthoflongestsubstring" in combined:
        return BENCHMARK_PROBLEMS["longest_substring"]

    if "two sum" in combined or "indices of the two numbers" in combined or "two numbers that sum" in combined:
        return BENCHMARK_PROBLEMS["two_sum"]

    if "valid parentheses" in combined or ("brackets" in combined and "closed by the same type" in combined):
        return BENCHMARK_PROBLEMS["valid_parentheses"]

    if "department salary" in combined or ("employees_departments" in combined):
        return BENCHMARK_PROBLEMS["sql_department_salaries"]

    if (
        "maximum sum of non-overlapping subarrays" in combined
        or "maxsumtwonooverlap" in combined
        or ("non-overlapping subarrays" in combined and "sum" in combined)
        or ("subarrays" in combined and "minimum length" in combined and "sum" in combined)
    ):
        return BENCHMARK_PROBLEMS["max_sum_non_overlapping_subarrays"]

    if (
        "maximum length of repeated subarray" in combined
        or "maximum length subarray" in combined
        or "max length subarray" in combined
        or "longest repeated subarray" in combined
        or "findlength" in combined
        or ("maximum length" in combined and "subarray" in combined)
        or ("max length" in combined and "subarray" in combined)
    ):
        return BENCHMARK_PROBLEMS["maximum_length_subarray"]

    return None


def resolve_canonical_question_type(data: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    """
    Authoritative resolution of question_type and response_mode.
    Returns (question_type, response_mode, benchmark_match).

    Enforces strict consistency:
    - CODING: coding_ide
    - SQL: sql_sandbox
    - SYSTEM_DESIGN: system_design_text
    - VERBAL: verbal_speech_text
    - MULTIPLE_CHOICE: multiple_choice
    - AMBIGUOUS: None (if unclassifiable)
    """
    raw_type = data.get("question_type")
    raw_mode = data.get("response_mode")
    text = data.get("text") or ""
    title = data.get("title") or ""
    q_id = data.get("id") or ""

    # 1. First check if this is a genuine verbal question
    is_verbal_prompt = is_genuine_verbal_prompt(text)

    # 2. Check for benchmark match if not explicitly verbal
    benchmark = None
    if not is_verbal_prompt:
        benchmark = find_benchmark_problem(text, title, q_id)

    # If it matches a benchmark coding problem, benchmark wins over missing/stale defaults
    if benchmark:
        b_type = benchmark["question_type"]
        b_mode = benchmark["response_mode"]
        return b_type, b_mode, benchmark

    # 3. Check explicit structured artifacts
    has_code_artifacts = bool(
        data.get("test_cases") or data.get("code_template") or data.get("function_name")
    )
    has_sql_artifacts = bool(
        data.get("sql_schema") or data.get("sql_fixture") or data.get("expected_sql_query")
    )
    has_mc_artifacts = bool(data.get("options") and len(data.get("options") or []) >= 2)

    if has_code_artifacts and not has_sql_artifacts:
        return "coding", "coding_ide", None
    if has_sql_artifacts:
        return "sql", "sql_sandbox", None
    if has_mc_artifacts:
        return "multiple_choice", "multiple_choice", None

    # 4. Check explicit response_mode
    if raw_mode:
        m = str(raw_mode).strip().lower()
        if m in ("coding_ide", "code", "ide"):
            return "coding", "coding_ide", None
        if m in ("sql_sandbox", "sql"):
            return "sql", "sql_sandbox", None
        if m in ("system_design_text", "system_design", "design"):
            return "system_design", "system_design_text", None
        if m in ("verbal_speech_text", "verbal", "speech", "text"):
            return "verbal", "verbal_speech_text", None
        if m in ("multiple_choice", "mcq"):
            return "multiple_choice", "multiple_choice", None

    # 5. Check explicit non-verbal question_type
    if raw_type and isinstance(raw_type, str):
        t = raw_type.strip().lower()
        if t in ("coding", "coding_dsa", "dsa", "code"):
            return "coding", "coding_ide", None
        if t in ("sql", "database"):
            return "sql", "sql_sandbox", None
        if t in ("system_design", "sys_design", "architecture", "system-design"):
            return "system_design", "system_design_text", None
        if t in ("multiple_choice", "mcq"):
            return "multiple_choice", "multiple_choice", None

    # 6. Trustworthy textual indicators (takes precedence over stale default 'verbal' labels)
    t_clean = text.strip().lower()

    # SQL indicators:
    if (
        any(phrase in t_clean for phrase in ["write an sql query", "write a sql query", "query the database", "sql fixture"])
        or ("select " in t_clean and " from " in t_clean)
        or ("group by " in t_clean and ("select " in t_clean or "count(" in t_clean))
        or ("insert into " in t_clean)
        or ("create table " in t_clean)
    ):
        return "sql", "sql_sandbox", None

    # System Design indicators:
    if any(phrase in t_clean for phrase in [
        "design a distributed", "architect a high-availability", "system architecture",
        "design a rate limiter", "design a system", "design a url shortening", "architect a distributed",
        "feed architecture", "system design"
    ]):
        return "system_design", "system_design_text", None

    # Coding / DSA indicators:
    if (
        any(phrase in t_clean for phrase in [
            "write a function", "implement a function", "write an algorithm", "given an array",
            "given a string", "return the indices", "return the maximum", "return an integer",
            "time complexity o(", "space complexity o(", "input format:", "output format:",
            "shortest path", "dijkstra", "binary search", "linked list", "binary tree",
            "reverse a linked list", "in c++", "in python", "in java"
        ])
        or (t_clean.startswith("implement ") and any(k in t_clean for k in ["algorithm", "function", "class", "method", "tree", "graph", "search", "sort", "path"]))
    ) and not is_verbal_prompt:
        return "coding", "coding_ide", None

    # 7. Check if explicitly verbal or conceptual
    if raw_type and isinstance(raw_type, str):
        t = raw_type.strip().lower()
        if t in ("verbal", "behavioral", "conceptual", "spoken"):
            return "verbal", "verbal_speech_text", None

    if is_verbal_prompt or any(phrase in t_clean for phrase in ["explain how", "describe your experience", "walk through how you", "what are the differences", "tell me about"]):
        return "verbal", "verbal_speech_text", None

    # 8. Unclassifiable legacy/unknown question -> default safely to verbal
    return "verbal", "verbal_speech_text", None


def resolve_available_and_recommended_modes(
    question_type: str,
    data: Optional[Dict[str, Any]] = None,
    session_mode: Optional[str] = None,
) -> Tuple[List[str], str]:
    """
    Determine compatible answer modes and the default recommended mode.
    Strictly isolated when session_mode is provided:
    - CODING session: ['coding'] exclusively.
    - VERBAL session: ['verbal'] (or ['verbal', 'system_design'] for architecture). Never allows 'coding' or 'sql'.
    Incompatible modes are excluded to prevent submitting invalid answer formats.
    """
    s_mode = (session_mode or "").strip().upper() if session_mode else None
    data = data or {}
    text = (data.get("text") or "").lower()
    skill = (data.get("assessed_skill") or "").lower()

    if s_mode == "CODING":
        return ["coding"], "coding"

    if s_mode == "VERBAL":
        if any(k in text or k in skill for k in ["architecture", "system design", "distributed", "scalability", "infrastructure"]):
            return ["verbal", "system_design"], "verbal"
        return ["verbal"], "verbal"

    if question_type == "coding":
        return ["coding", "verbal"], "coding"
    if question_type == "sql":
        return ["sql", "verbal"], "sql"
    if question_type == "system_design":
        return ["system_design", "verbal"], "system_design"
    if question_type == "multiple_choice":
        return ["multiple_choice"], "multiple_choice"

    # For verbal/conceptual questions:
    if any(k in text or k in skill for k in ["architecture", "system design", "distributed", "scalability", "infrastructure"]):
        return ["verbal", "system_design"], "verbal"

    return ["verbal"], "verbal"


def normalize_and_classify_question(data: Dict[str, Any], session_mode: Optional[str] = None) -> Dict[str, Any]:
    """
    Normalize, validate, and migrate question metadata safely.
    Enforces reliable question_type, response_mode, available_modes, and recommended_mode.
    Strictly isolates CODING vs VERBAL sessions:
    - CODING: guarantees coding_ide response mode and test cases.
    - VERBAL: guarantees natural language verbal mode, stripping code/testcase artifacts.
    Attaches benchmark test cases and templates if matching benchmark problem.
    """
    res = dict(data)
    s_mode = (session_mode or res.get("session_mode") or "").strip().upper()
    if s_mode not in ("CODING", "VERBAL"):
        s_mode = None

    q_type, resp_mode, benchmark = resolve_canonical_question_type(res)

    if s_mode == "CODING":
        # Force strict coding mode
        q_type = "coding"
        resp_mode = "coding_ide"
    elif s_mode == "VERBAL":
        # Force strict verbal mode
        if q_type != "system_design":
            q_type = "verbal"
            resp_mode = "verbal_speech_text"
        else:
            resp_mode = "system_design_text"
        # Strip all code execution artifacts from verbal questions
        res.pop("test_cases", None)
        res.pop("code_template", None)
        res.pop("starter_templates", None)
        res.pop("function_name", None)
        res.pop("sql_fixture", None)
        res.pop("expected_sql_query", None)
        benchmark = None

    res["question_type"] = q_type
    res["response_mode"] = resp_mode

    available_modes, recommended_mode = resolve_available_and_recommended_modes(q_type, res, session_mode=s_mode)
    res["available_modes"] = available_modes
    res["recommended_mode"] = recommended_mode

    if not res.get("question_number"):
        res["question_number"] = res.get("number") or 1
    if not res.get("assessed_skill"):
        res["assessed_skill"] = (benchmark.get("assessed_skill") if benchmark else None) or res.get("skill") or "Technical Competency"
    if not res.get("difficulty"):
        res["difficulty"] = (benchmark.get("difficulty") if benchmark else None) or "Medium"
    if not res.get("rubric") or len(str(res.get("rubric", "")).strip()) < 10:
        res["rubric"] = (benchmark.get("rubric") if benchmark else None) or "Correctness, technical depth, and clear structured reasoning."

    # Normalize any existing test cases so expected_output is populated from output/expected/result
    if res.get("test_cases"):
        for tc in res["test_cases"]:
            if isinstance(tc, dict):
                if not str(tc.get("expected_output", "")).strip():
                    for alt_key in ("output", "expected", "result"):
                        if str(tc.get(alt_key, "")).strip():
                            tc["expected_output"] = str(tc[alt_key]).strip()
                            break

    # If benchmark problem matched, enrich missing fields
    if benchmark:
        if not res.get("text"):
            res["text"] = benchmark.get("text")
        if not res.get("title"):
            res["title"] = benchmark.get("title")

        # Check if existing test cases are missing or have blank expected_output
        has_broken_tests = (
            not res.get("test_cases")
            or any(
                not str(tc.get("expected_output", "") if isinstance(tc, dict) else getattr(tc, "expected_output", "")).strip()
                for tc in res.get("test_cases", [])
            )
        )
        if has_broken_tests and benchmark.get("test_cases"):
            res["test_cases"] = benchmark.get("test_cases")

        if not res.get("function_name"):
            res["function_name"] = benchmark.get("function_name")
        if not res.get("input_format"):
            res["input_format"] = benchmark.get("input_format")
        if not res.get("output_format"):
            res["output_format"] = benchmark.get("output_format")
        if not res.get("constraints"):
            res["constraints"] = benchmark.get("constraints")
        if not res.get("examples"):
            res["examples"] = benchmark.get("examples")
        if not res.get("code_template"):
            res["code_template"] = benchmark.get("code_template") or benchmark.get("starter_templates")
        if not res.get("starter_templates"):
            res["starter_templates"] = benchmark.get("starter_templates") or benchmark.get("code_template")
        if not res.get("reference_solution") and benchmark.get("reference_solution"):
            res["reference_solution"] = benchmark.get("reference_solution")
        if not res.get("comparison_policy"):
            res["comparison_policy"] = benchmark.get("comparison_policy", "strict_structural")
        if benchmark.get("oracle_verified"):
            res["oracle_verified"] = True
            res["oracle_provenance"] = benchmark.get("oracle_provenance", "benchmark_catalog")
        if not res.get("sql_fixture") and benchmark.get("sql_fixture"):
            res["sql_fixture"] = benchmark.get("sql_fixture")
        if not res.get("expected_sql_query") and benchmark.get("expected_sql_query"):
            res["expected_sql_query"] = benchmark.get("expected_sql_query")
    elif s_mode == "CODING" and not res.get("test_cases"):
        # Enrich from benchmark two_sum if code test cases are missing in CODING session
        default_bm = BENCHMARK_PROBLEMS.get("two_sum")
        if default_bm:
            if not res.get("text"):
                res["text"] = default_bm.get("text")
            if not res.get("title"):
                res["title"] = default_bm["title"]
            if not res.get("test_cases"):
                res["test_cases"] = default_bm["test_cases"]
            if not res.get("function_name"):
                res["function_name"] = default_bm["function_name"]
            if not res.get("code_template"):
                res["code_template"] = default_bm["code_template"]
            if not res.get("starter_templates"):
                res["starter_templates"] = default_bm["code_template"]
            if not res.get("constraints"):
                res["constraints"] = default_bm["constraints"]
            if not res.get("examples"):
                res["examples"] = default_bm["examples"]

    return res
