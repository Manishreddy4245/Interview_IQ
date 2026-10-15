import type { QuestionItem, TestCase } from './api.ts'

export interface ProblemExample {
  example_number?: number
  input: string
  output: string
  explanation?: string
}

export interface NormalizedProblem {
  id: string
  title: string
  difficulty: 'Easy' | 'Medium' | 'Hard'
  assessed_skill: string
  description: string
  input_format: string
  output_format: string
  constraints: string[]
  examples: ProblemExample[]
  test_cases: TestCase[]
  starter_templates: Record<string, string>
  is_sql: boolean
  sql_fixture?: string
  test_cases_available: boolean
  execution_contract: 'function' | 'stdio' | 'sql'
  execution_hint: string
  function_name?: string
}

/**
 * Built-in Benchmark DSA & SQL Problem Definitions
 */
export const BENCHMARK_PROBLEMS: Record<string, NormalizedProblem> = {
  two_sum: {
    id: 'two_sum',
    title: 'Two Sum',
    difficulty: 'Easy',
    assessed_skill: 'Arrays & Hash Maps',
    function_name: 'twoSum',
    description:
      'Given an integer array `nums` and an integer `target`, return the indices of the two numbers whose sum equals `target`.\n\nYou may assume that each input would have exactly one valid solution, and you may not use the same element twice.\n\nYou can return the answer in any order.',
    input_format: '`nums`: integer array, `target`: integer (provided as array and integer on standard input or parameters)',
    output_format: 'Return an array of two integers `[index1, index2]` representing the 0-based indices of the matching pair.',
    constraints: [
      '2 <= nums.length <= 10^4',
      '-10^9 <= nums[i] <= 10^9',
      '-10^9 <= target <= 10^9',
      'Exactly one valid solution exists.',
      'The same element cannot be used twice.',
    ],
    examples: [
      {
        example_number: 1,
        input: 'nums = [2,7,11,15]\ntarget = 9',
        output: '[0,1]',
        explanation: 'Because nums[0] + nums[1] == 2 + 7 == 9, we return [0, 1].',
      },
      {
        example_number: 2,
        input: 'nums = [3,2,4]\ntarget = 6',
        output: '[1,2]',
        explanation: 'Because nums[1] + nums[2] == 2 + 4 == 6, we return [1, 2].',
      },
      {
        example_number: 3,
        input: 'nums = [3,3]\ntarget = 6',
        output: '[0,1]',
        explanation: 'Because nums[0] + nums[1] == 3 + 3 == 6, we return [0, 1].',
      },
    ],
    test_cases: [
      {
        id: 'tc_1',
        input: '[2,7,11,15]\n9',
        expected_output: '[0,1]',
        is_hidden: false,
        explanation: 'Standard positive integer array test',
      },
      {
        id: 'tc_2',
        input: '[3,2,4]\n6',
        expected_output: '[1,2]',
        is_hidden: false,
        explanation: 'Unsorted array pair test',
      },
      {
        id: 'tc_3',
        input: '[3,3]\n6',
        expected_output: '[0,1]',
        is_hidden: false,
        explanation: 'Duplicate value pair test',
      },
      {
        id: 'tc_4',
        input: '[-1,-2,-3,-4,-5]\n-8',
        expected_output: '[2,4]',
        is_hidden: true,
        explanation: 'Negative integer values hidden benchmark case',
      },
    ],
    starter_templates: {
      python: `from typing import List

class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        # Implement your O(N) solution here
        pass
`,
      javascript: `/**
 * @param {number[]} nums
 * @param {number} target
 * @return {number[]}
 */
function twoSum(nums, target) {
    // Implement your solution here
}
`,
      typescript: `function twoSum(nums: number[], target: number): number[] {
    // Implement your solution here
    return [];
}
`,
      cpp: `#include <vector>
#include <unordered_map>

using namespace std;

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        // Implement your solution here
        return {};
    }
};
`,
      java: `import java.util.*;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        // Implement your solution here
        return new int[]{};
    }
}
`,
      c: `#include <stdio.h>
#include <stdlib.h>

/**
 * Note: The returned array must be malloced, assume caller calls free().
 */
int* twoSum(int* nums, int numsSize, int target, int* returnSize) {
    // Implement your solution here
    *returnSize = 0;
    return NULL;
}
`,
      csharp: `using System;
using System.Collections.Generic;

public class Solution {
    public int[] TwoSum(int[] nums, int target) {
        // Implement your solution here
        return new int[0];
    }
}
`,
      go: `package main

func twoSum(nums []int, target int) []int {
    // Implement your solution here
    return []int{}
}
`,
      rust: `impl Solution {
    pub fn two_sum(nums: Vec<i32>, target: i32) -> Vec<i32> {
        // Implement your solution here
        vec![]
    }
}
`,
      sql: `-- Write your SQL query here
SELECT * FROM employees LIMIT 10;
`,
    },
    is_sql: false,
    test_cases_available: true,
    execution_contract: 'function',
    execution_hint: 'Your function/method should return the 2-element index array directly (e.g. [0, 1]). Do not print unless debugging.',
  },

  valid_parentheses: {
    id: 'valid_parentheses',
    title: 'Valid Parentheses',
    difficulty: 'Easy',
    assessed_skill: 'Stacks & String Parsing',
    function_name: 'isValid',
    description:
      'Given a string `s` containing just the characters `(`, `)`, `{`, `}`, `[` and `]`, determine if the input string is valid.\n\nAn input string is valid if:\n1. Open brackets must be closed by the same type of brackets.\n2. Open brackets must be closed in the correct order.\n3. Every close bracket has a corresponding open bracket of the same type.',
    input_format: '`s`: string containing only brackets `()[]{}`',
    output_format: 'Return a boolean (`true` or `false`) indicating bracket validity.',
    constraints: [
      '1 <= s.length <= 10^4',
      's consists of parentheses only: ()[]{}',
    ],
    examples: [
      {
        example_number: 1,
        input: 's = "()"',
        output: 'true',
        explanation: 'Simple matched parentheses pair.',
      },
      {
        example_number: 2,
        input: 's = "()[]{}"',
        output: 'true',
        explanation: 'Multiple matched consecutive pairs.',
      },
      {
        example_number: 3,
        input: 's = "(]"',
        output: 'false',
        explanation: 'Mismatched closing bracket type.',
      },
    ],
    test_cases: [
      { id: 'tc_1', input: '()', expected_output: 'true', is_hidden: false },
      { id: 'tc_2', input: '()[]{}', expected_output: 'true', is_hidden: false },
      { id: 'tc_3', input: '(]', expected_output: 'false', is_hidden: false },
      { id: 'tc_4', input: '([)]', expected_output: 'false', is_hidden: true },
      { id: 'tc_5', input: '{[]}', expected_output: 'true', is_hidden: true },
    ],
    starter_templates: {
      python: `class Solution:
    def isValid(self, s: str) -> bool:
        # Implement stack-based validation
        pass
`,
      javascript: `/**
 * @param {string} s
 * @return {boolean}
 */
function isValid(s) {
    // Implement stack-based validation
}
`,
      typescript: `function isValid(s: string): boolean {
    // Implement stack-based validation
    return false;
}
`,
      cpp: `#include <string>
#include <stack>

using namespace std;

class Solution {
public:
    bool isValid(string s) {
        // Implement stack-based validation
        return false;
    }
};
`,
      java: `import java.util.*;

class Solution {
    public boolean isValid(String s) {
        // Implement stack-based validation
        return false;
    }
}
`,
      sql: `-- Write your SQL query here\nSELECT * FROM employees LIMIT 10;\n`,
    },
    is_sql: false,
    test_cases_available: true,
    execution_contract: 'function',
    execution_hint: 'Your function/method should return a boolean (True / False / true / false) directly.',
  },

  sql_department_salaries: {
    id: 'sql_department_salaries',
    title: 'Department Salary Aggregation & High Earners',
    difficulty: 'Medium',
    assessed_skill: 'SQL Joins, Aggregation & Grouping',
    description:
      'Write an SQL query to report the department name (`dept_name`) and the total employee headcount (`emp_count`) for all departments in the organization.\n\nJoin the `departments` table with the `employees` table on `dept_id`, group by `dept_name`, and return departments having employees.',
    input_format: 'Tables: `departments` (dept_id, dept_name), `employees` (emp_id, emp_name, dept_id, salary, role)',
    output_format: 'Columns: `dept_name` (TEXT), `emp_count` (INTEGER)',
    constraints: [
      'Query must run cleanly in isolated SQLite in-memory sandbox.',
      'Only aggregate departments present in the sample fixture.',
    ],
    examples: [
      {
        example_number: 1,
        input: 'Fixture: employees_departments',
        output: 'dept_name | emp_count\nEngineering | 4\nDesign | 2\nProduct | 2',
        explanation: 'Aggregates employee count grouped by department.',
      },
    ],
    test_cases: [
      {
        id: 'tc_1',
        input: 'SELECT dept_name, count(*) as emp_count FROM departments d JOIN employees e ON d.dept_id = e.dept_id GROUP BY dept_name;',
        expected_output: '3 rows (Engineering, Design, Product)',
        is_hidden: false,
      },
    ],
    starter_templates: {
      sql: `-- Write your SQL query here
SELECT dept_name, COUNT(*) AS emp_count
FROM departments d
JOIN employees e ON d.dept_id = e.dept_id
GROUP BY dept_name;
`,
    },
    is_sql: true,
    sql_fixture: 'employees_departments',
    test_cases_available: true,
    execution_contract: 'sql',
    execution_hint: 'Write an SQL query producing columns `dept_name` and `emp_count` from the joined tables.',
  },

  longest_substring: {
    id: 'longest_substring',
    title: 'Longest Substring Without Repeating Characters',
    difficulty: 'Medium',
    assessed_skill: 'Strings & Sliding Window',
    function_name: 'lengthOfLongestSubstring',
    description:
      'Given a string `s`, find the length of the longest substring without repeating characters.\n\nA substring is a contiguous non-empty sequence of characters within a string.',
    input_format: '`s`: string (e.g. "abcabcbb")',
    output_format: 'Return an integer representing the length of the longest substring with unique characters.',
    constraints: [
      '0 <= s.length <= 5 * 10^4',
      's consists of English letters, digits, symbols and spaces.',
    ],
    examples: [
      {
        example_number: 1,
        input: 's = "abcabcbb"',
        output: '3',
        explanation: 'The answer is "abc", with the length of 3.',
      },
      {
        example_number: 2,
        input: 's = "bbbbb"',
        output: '1',
        explanation: 'The answer is "b", with the length of 1.',
      },
      {
        example_number: 3,
        input: 's = "pwwkew"',
        output: '3',
        explanation: 'The answer is "wke", with the length of 3. Note that the answer must be a substring, "pwke" is a subsequence.',
      },
    ],
    test_cases: [
      { id: 'tc_1', input: 'abcabcbb', expected_output: '3', is_hidden: false },
      { id: 'tc_2', input: 'bbbbb', expected_output: '1', is_hidden: false },
      { id: 'tc_3', input: 'pwwkew', expected_output: '3', is_hidden: false },
      { id: 'tc_4', input: '', expected_output: '0', is_hidden: true },
      { id: 'tc_5', input: ' ', expected_output: '1', is_hidden: true },
    ],
    starter_templates: {
      python: `class Solution:
    def lengthOfLongestSubstring(self, s: str) -> int:
        # Implement your solution here
        pass
`,
      javascript: `/**
 * @param {string} s
 * @return {number}
 */
function lengthOfLongestSubstring(s) {
    // Implement your solution here
    return 0;
}
`,
      typescript: `function lengthOfLongestSubstring(s: string): number {
    // Implement your solution here
    return 0;
}
`,
      cpp: `#include <string>
#include <unordered_set>

using namespace std;

class Solution {
public:
    int lengthOfLongestSubstring(string s) {
        // Implement your solution here
        return 0;
    }
};
`,
      java: `import java.util.*;

class Solution {
    public int lengthOfLongestSubstring(String s) {
        // Implement your solution here
        return 0;
    }
}
`,
      csharp: `using System;
using System.Collections.Generic;

public class Solution {
    public int LengthOfLongestSubstring(string s) {
        // Implement your solution here
        return 0;
    }
}
`,
      go: `package main

func lengthOfLongestSubstring(s string) int {
    // Implement your solution here
    return 0
}
`,
      rust: `impl Solution {
    pub fn length_of_longest_substring(s: String) -> i32 {
        // Implement your solution here
        0
    }
}
`,
    },
    is_sql: false,
    test_cases_available: true,
    execution_contract: 'function',
    execution_hint: 'Your function/method should return an integer representing the maximum substring length.',
  },

  maximum_length_subarray: {
    id: 'maximum_length_subarray',
    title: 'Maximum Length of Repeated Subarray',
    difficulty: 'Medium',
    assessed_skill: 'Arrays & Dynamic Programming',
    function_name: 'findLength',
    description:
      'Given two integer arrays `nums1` and `nums2`, return the maximum length of a subarray that appears in both arrays.\n\nA subarray is a contiguous non-empty sequence of elements within an array.',
    input_format: '`nums1`: integer array, `nums2`: integer array',
    output_format: 'Return an integer representing the maximum length of a common contiguous subarray.',
    constraints: [
      '1 <= nums1.length, nums2.length <= 1000',
      '0 <= nums1[i], nums2[i] <= 100',
    ],
    examples: [
      {
        example_number: 1,
        input: 'nums1 = [1,2,3,2,1]\nnums2 = [3,2,1,4,7]',
        output: '3',
        explanation: 'The repeated subarray with maximum length is [3,2,1].',
      },
      {
        example_number: 2,
        input: 'nums1 = [0,0,0,0,0]\nnums2 = [0,0,0,0,0]',
        output: '5',
        explanation: 'The repeated subarray with maximum length is [0,0,0,0,0].',
      },
      {
        example_number: 3,
        input: 'nums1 = [1,2,3]\nnums2 = [4,5,6]',
        output: '0',
        explanation: 'There are no common subarrays, so return 0.',
      },
    ],
    test_cases: [
      { id: 'tc_1', input: '[1,2,3,2,1]\n[3,2,1,4,7]', expected_output: '3', is_hidden: false },
      { id: 'tc_2', input: '[0,0,0,0,0]\n[0,0,0,0,0]', expected_output: '5', is_hidden: false },
      { id: 'tc_3', input: '[1,2,3]\n[4,5,6]', expected_output: '0', is_hidden: false },
      { id: 'tc_4', input: '[1,0,0,0,1]\n[1,0,0,1,1]', expected_output: '3', is_hidden: true },
      { id: 'tc_5', input: '[70,39,25,40,7]\n[52,20,67,5,31]', expected_output: '0', is_hidden: true },
    ],
    starter_templates: {
      python: `from typing import List\n\nclass Solution:\n    def findLength(self, nums1: List[int], nums2: List[int]) -> int:\n        # Implement your O(M*N) dynamic programming solution here\n        pass\n`,
      javascript: `/**\n * @param {number[]} nums1\n * @param {number[]} nums2\n * @return {number}\n */\nfunction findLength(nums1, nums2) {\n    // Implement your solution here\n}\n`,
      typescript: `function findLength(nums1: number[], nums2: number[]): number {\n    // Implement your solution here\n    return 0;\n}\n`,
      cpp: `#include <vector>\n#include <algorithm>\nusing namespace std;\n\nclass Solution {\npublic:\n    int findLength(vector<int>& nums1, vector<int>& nums2) {\n        return 0;\n    }\n};\n`,
      java: `import java.util.*;\n\nclass Solution {\n    public int findLength(int[] nums1, int[] nums2) {\n        return 0;\n    }\n}\n`,
    },
    is_sql: false,
    test_cases_available: true,
    execution_contract: 'function',
    execution_hint: 'Your function/method should return an integer representing the maximum length of a shared subarray.',
  },

  max_sum_non_overlapping_subarrays: {
    id: 'max_sum_non_overlapping_subarrays',
    title: 'Maximum Sum of Two Non-Overlapping Subarrays',
    difficulty: 'Medium',
    assessed_skill: 'Dynamic Programming & Prefix Sums',
    function_name: 'maxSumTwoNoOverlap',
    description:
      'Given an integer array `nums` and two integers `firstLen` and `secondLen`, return the maximum sum of elements in two non-overlapping subarrays of lengths `firstLen` and `secondLen`.\n\nThe subarray with length `firstLen` could occur before or after the subarray with length `secondLen`, but they must not overlap.',
    input_format: '`nums`: integer array, `firstLen`: integer, `secondLen`: integer',
    output_format: 'Return an integer representing the maximum sum of two non-overlapping subarrays.',
    constraints: [
      'firstLen + secondLen <= nums.length <= 1000',
      '1 <= firstLen, secondLen <= 1000',
      '0 <= nums[i] <= 1000',
    ],
    examples: [
      {
        example_number: 1,
        input: 'nums = [0,6,5,2,2,5,1,9,4]\nfirstLen = 1\nsecondLen = 2',
        output: '20',
        explanation: 'One choice of subarrays is [9] with length 1, and [6,5] with length 2.',
      },
      {
        example_number: 2,
        input: 'nums = [3,8,1,3,2,1,8,9,0]\nfirstLen = 3\nsecondLen = 2',
        output: '29',
        explanation: 'One choice of subarrays is [3,8,1] with length 3, and [8,9] with length 2.',
      },
      {
        example_number: 3,
        input: 'nums = [2,1,5,6,0,9,5,0,3,8]\nfirstLen = 4\nsecondLen = 3',
        output: '31',
        explanation: 'One choice of subarrays is [5,6,0,9] with length 4, and [0,3,8] with length 3.',
      },
    ],
    test_cases: [
      { id: 'tc_1', input: '[0,6,5,2,2,5,1,9,4]\n1\n2', expected_output: '20', is_hidden: false },
      { id: 'tc_2', input: '[3,8,1,3,2,1,8,9,0]\n3\n2', expected_output: '29', is_hidden: false },
      { id: 'tc_3', input: '[2,1,5,6,0,9,5,0,3,8]\n4\n3', expected_output: '31', is_hidden: false },
      { id: 'tc_4', input: '[1,0,1]\n1\n1', expected_output: '2', is_hidden: true },
      { id: 'tc_5', input: '[0,0,0,0,0]\n2\n2', expected_output: '0', is_hidden: true },
    ],
    starter_templates: {
      python: `from typing import List\n\nclass Solution:\n    def maxSumTwoNoOverlap(self, nums: List[int], firstLen: int, secondLen: int) -> int:\n        # Implement your O(N) dynamic programming / prefix sum solution here\n        pass\n`,
      javascript: `/**\n * @param {number[]} nums\n * @param {number} firstLen\n * @param {number} secondLen\n * @return {number}\n */\nfunction maxSumTwoNoOverlap(nums, firstLen, secondLen) {\n    // Implement your solution here\n}\n`,
      typescript: `function maxSumTwoNoOverlap(nums: number[], firstLen: number, secondLen: number): number {\n    // Implement your solution here\n    return 0;\n}\n`,
      cpp: `#include <vector>\n#include <numeric>\n#include <algorithm>\nusing namespace std;\n\nclass Solution {\npublic:\n    int maxSumTwoNoOverlap(vector<int>& nums, int firstLen, int secondLen) {\n        return 0;\n    }\n};\n`,
      java: `import java.util.*;\n\nclass Solution {\n    public int maxSumTwoNoOverlap(int[] nums, int firstLen, int secondLen) {\n        return 0;\n    }\n}\n`,
    },
    is_sql: false,
    test_cases_available: true,
    execution_contract: 'function',
    execution_hint: 'Your function/method should return an integer representing the maximum sum of two non-overlapping subarrays.',
  },
}

/**
 * Parses markdown/plain-text example blocks from question descriptions
 */
export function extractExamplesFromText(text: string): ProblemExample[] {
  if (!text) return []
  const results: ProblemExample[] = []

  // Pattern 1: Example N: Input: ... Output: ... (Explanation: ...)
  const exampleRegex = /(?:Example\s*(\d*):?[\r\n]+)([\s\S]*?)(?=(?:Example\s*\d+:|Constraints?:|\n\n#|$))/gi
  let match: RegExpExecArray | null

  while ((match = exampleRegex.exec(text)) !== null) {
    const block = match[2]
    const inMatch = block.match(/Input:?\s*([\s\S]*?)(?=Output:|$)/i)
    const outMatch = block.match(/Output:?\s*([\s\S]*?)(?=Explanation:|$)/i)
    const expMatch = block.match(/Explanation:?\s*([\s\S]*?)$/i)

    if (inMatch && outMatch) {
      const cleanInput = inMatch[1].replace(/```[a-z]*\n?/gi, '').replace(/```/g, '').trim()
      const cleanOutput = outMatch[1].replace(/```[a-z]*\n?/gi, '').replace(/```/g, '').trim()
      const cleanExp = expMatch ? expMatch[1].replace(/```[a-z]*\n?/gi, '').replace(/```/g, '').trim() : ''

      if (cleanInput && cleanOutput) {
        results.push({
          example_number: results.length + 1,
          input: cleanInput,
          output: cleanOutput,
          explanation: cleanExp,
        })
      }
    }
  }

  // Fallback pattern 2: single Input: ... Output: ... block without "Example N:" header
  if (results.length === 0) {
    const inMatch = text.match(/(?:^|\n)Input:?\s*([\s\S]*?)(?=(?:^|\n)Output:)/i)
    const outMatch = text.match(/(?:^|\n)Output:?\s*([\s\S]*?)(?=(?:^|\n)(?:Explanation:|Constraints?:|$))/i)
    const expMatch = text.match(/(?:^|\n)Explanation:?\s*([\s\S]*?)(?=(?:^|\n)(?:Constraints?:|$))/i)

    if (inMatch && outMatch) {
      const cleanInput = inMatch[1].replace(/```[a-z]*\n?/gi, '').replace(/```/g, '').trim()
      const cleanOutput = outMatch[1].replace(/```[a-z]*\n?/gi, '').replace(/```/g, '').trim()
      const cleanExp = expMatch ? expMatch[1].replace(/```[a-z]*\n?/gi, '').replace(/```/g, '').trim() : ''
      if (cleanInput && cleanOutput) {
        results.push({
          example_number: 1,
          input: cleanInput,
          output: cleanOutput,
          explanation: cleanExp,
        })
      }
    }
  }

  return results
}

/**
 * Intelligently extract or normalize any question item into a full LeetCode-style problem definition
 */
export function normalizeProblemData(question: QuestionItem, currentLang: string = 'python'): NormalizedProblem {
  if (!question) {
    return BENCHMARK_PROBLEMS.two_sum
  }

  // 1. Direct match with benchmark problems if id or keywords match
  const textLower = (question.text || '').toLowerCase()
  const titleLower = (question.title || '').toLowerCase()
  const idLower = (question.id || '').toLowerCase()

  if (
    idLower.includes('two_sum') ||
    textLower.includes('two sum') ||
    textLower.includes('indices of the two numbers') ||
    titleLower.includes('two sum')
  ) {
    const base = BENCHMARK_PROBLEMS.two_sum
    return {
      ...base,
      difficulty: (question.difficulty as any) || base.difficulty,
      assessed_skill: question.assessed_skill || base.assessed_skill,
    }
  }

  if (
    idLower.includes('parenthes') ||
    textLower.includes('valid parentheses') ||
    titleLower.includes('valid parentheses')
  ) {
    const base = BENCHMARK_PROBLEMS.valid_parentheses
    return {
      ...base,
      difficulty: (question.difficulty as any) || base.difficulty,
      assessed_skill: question.assessed_skill || base.assessed_skill,
    }
  }

  if (
    idLower.includes('longest_sub') ||
    idLower.includes('longest substring') ||
    textLower.includes('longest substring') ||
    titleLower.includes('longest substring')
  ) {
    const base = BENCHMARK_PROBLEMS.longest_substring
    return {
      ...base,
      difficulty: (question.difficulty as any) || base.difficulty,
      assessed_skill: question.assessed_skill || base.assessed_skill,
    }
  }

  if (
    idLower.includes('repeated_sub') ||
    idLower.includes('maximum_length_sub') ||
    titleLower.includes('maximum length of repeated subarray') ||
    titleLower.includes('maximum length subarray') ||
    textLower.includes('maximum length of a subarray that appears in both arrays') ||
    (titleLower.includes('maximum length') && titleLower.includes('subarray')) ||
    (textLower.includes('maximum length') && textLower.includes('subarray'))
  ) {
    const base = BENCHMARK_PROBLEMS.maximum_length_subarray
    return {
      ...base,
      difficulty: (question.difficulty as any) || base.difficulty,
      assessed_skill: question.assessed_skill || base.assessed_skill,
    }
  }

  if (
    idLower.includes('non_overlapping_sub') ||
    idLower.includes('max_sum_non_overlapping') ||
    titleLower.includes('non-overlapping subarrays') ||
    textLower.includes('non-overlapping subarrays') ||
    (titleLower.includes('subarrays') && titleLower.includes('minimum length') && titleLower.includes('sum')) ||
    (textLower.includes('subarrays') && textLower.includes('minimum length') && textLower.includes('sum'))
  ) {
    const base = BENCHMARK_PROBLEMS.max_sum_non_overlapping_subarrays
    return {
      ...base,
      difficulty: (question.difficulty as any) || base.difficulty,
      assessed_skill: question.assessed_skill || base.assessed_skill,
    }
  }

  const isSql =
    question.question_type === 'sql' ||
    textLower.includes('select ') ||
    textLower.includes('sql query') ||
    Boolean(question.sql_fixture)

  if (isSql && (textLower.includes('department') || textLower.includes('employee'))) {
    const base = BENCHMARK_PROBLEMS.sql_department_salaries
    return {
      ...base,
      title: question.title || base.title,
      difficulty: (question.difficulty as any) || base.difficulty,
      assessed_skill: question.assessed_skill || base.assessed_skill,
      description: question.text || base.description,
    }
  }

  // 2. Parse structured sections from question text
  let extractedTitle = question.title || ''
  if (!extractedTitle) {
    // Attempt extracting from markdown heading or first line
    const firstLine = question.text.split('\n')[0].trim()
    if (firstLine.startsWith('#') || firstLine.startsWith('Problem:')) {
      extractedTitle = firstLine.replace(/^#+\s*/, '').replace(/^Problem:\s*/i, '').trim()
    } else if (question.assessed_skill) {
      extractedTitle = `${question.assessed_skill} Problem`
    } else {
      extractedTitle = `Problem 0${question.question_number}`
    }
  }

  // Parse Constraints from text if question.constraints is empty
  let constraints: string[] = []
  if (Array.isArray(question.constraints) && question.constraints.length > 0) {
    constraints = question.constraints
  } else {
    const constraintMatch = question.text.match(/Constraints:?([\s\S]*?)(?:Examples?:|Input Format:|Output Format:|$)/i)
    if (constraintMatch && constraintMatch[1]) {
      constraints = constraintMatch[1]
        .split('\n')
        .map((l) => l.trim().replace(/^[-*•]\s*/, ''))
        .filter((l) => l.length > 2)
    }
  }
  if (constraints.length === 0) {
    constraints = [
      'Analyze the problem carefully and optimize time and space complexity.',
      'Handle boundary conditions and potential null/empty edge cases gracefully.',
    ]
  }

  // Parse Examples from structured data, test cases, or description text
  let examples: ProblemExample[] = []
  if (Array.isArray(question.examples) && question.examples.length > 0) {
    examples = question.examples.map((ex, idx) => {
      if (typeof ex === 'string') {
        return { example_number: idx + 1, input: ex, output: '', explanation: '' }
      }
      return {
        example_number: idx + 1,
        input: ex.input || '',
        output: ex.output || (ex as any).expected_output || '',
        explanation: ex.explanation || '',
      }
    })
  } else if (Array.isArray(question.test_cases) && question.test_cases.length > 0) {
    const sampleCases = question.test_cases.filter((tc) => !tc.is_hidden)
    examples = sampleCases.slice(0, 3).map((tc, idx) => ({
      example_number: idx + 1,
      input: tc.input || '(no input)',
      output: tc.expected_output || '',
      explanation: (tc as any).explanation || 'Sample test case input and verified benchmark output.',
    }))
  } else if (question.text) {
    // Attempt parsing examples from problem description text
    examples = extractExamplesFromText(question.text)
  }

  // Input & Output Format
  let inputFormat = question.input_format || ''
  let outputFormat = question.output_format || ''
  if (!inputFormat) {
    inputFormat = isSql
      ? 'Database tables and relational schema provided in sandbox.'
      : 'Standard inputs passed via function arguments or standard input.'
  }
  if (!outputFormat) {
    outputFormat = isSql
      ? 'Resulting dataset rows matching the query specification.'
      : 'Calculated return value or printed standard output.'
  }

  // Test Cases
  const rawTests = Array.isArray(question.test_cases) ? question.test_cases : []
  let testCases: TestCase[] = rawTests.map((tc: any, idx: number) => {
    let rawExpected = tc.expected_output !== undefined && tc.expected_output !== null
      ? tc.expected_output
      : (tc.output !== undefined && tc.output !== null
        ? tc.output
        : (tc.expected !== undefined && tc.expected !== null ? tc.expected : tc.result))

    // If public test case is still missing expected output, try matching with examples
    if ((rawExpected === undefined || rawExpected === null || String(rawExpected).trim() === '') && !tc.is_hidden && examples[idx]) {
      rawExpected = examples[idx].output
    }

    return {
      id: tc.id || `tc_${idx + 1}`,
      input: tc.input !== undefined && tc.input !== null ? String(tc.input) : '',
      expected_output: rawExpected !== undefined && rawExpected !== null ? String(rawExpected) : '',
      is_hidden: Boolean(tc.is_hidden),
      explanation: tc.explanation || '',
    }
  })
  if (testCases.length === 0 && examples.length > 0) {
    testCases = examples.map((ex, idx) => ({
      id: `tc_${idx + 1}`,
      input: ex.input,
      expected_output: ex.output,
      is_hidden: false,
      explanation: ex.explanation,
    }))
  }
  const testCasesAvailable = testCases.length > 0

  // Starter templates
  const starterTemplates: Record<string, string> = {}
  if (question.code_template && typeof question.code_template === 'object') {
    Object.assign(starterTemplates, question.code_template)
  } else if (typeof question.code_template === 'string') {
    starterTemplates[currentLang] = question.code_template
  }

  // Generate clean template if missing
  const rawFnName =
    (question as any).function_name ||
    (extractedTitle.replace(/[^a-zA-Z0-9]/g, '') || 'solve')
  const defaultMethodName = rawFnName.charAt(0).toLowerCase() + rawFnName.slice(1)

  if (!starterTemplates.python) {
    starterTemplates.python = isSql
      ? `-- Write your SQL query here\nSELECT * FROM employees LIMIT 10;\n`
      : `class Solution:\n    def ${defaultMethodName}(self, *args):\n        # Write your solution here\n        pass\n`
  }
  if (!starterTemplates.javascript) {
    starterTemplates.javascript = `function ${defaultMethodName}(...args) {\n    // Write your solution here\n}\n`
  }
  if (!starterTemplates.typescript) {
    starterTemplates.typescript = `function ${defaultMethodName}(...args: any[]): any {\n    // Write your solution here\n}\n`
  }
  if (!starterTemplates.cpp) {
    starterTemplates.cpp = `#include <iostream>\n#include <vector>\n\nusing namespace std;\n\nclass Solution {\npublic:\n    void ${defaultMethodName}() {\n        // Write your solution here\n    }\n};\n`
  }
  if (!starterTemplates.java) {
    starterTemplates.java = `import java.util.*;\n\nclass Solution {\n    public void ${defaultMethodName}() {\n        // Write your solution here\n    }\n}\n`
  }
  if (!starterTemplates.csharp) {
    starterTemplates.csharp = `using System;\nusing System.Collections.Generic;\n\npublic class Solution {\n    public void ${defaultMethodName}() {\n        // Write your solution here\n    }\n}\n`
  }
  if (!starterTemplates.go) {
    starterTemplates.go = `package main\n\nfunc ${defaultMethodName}() {\n    // Write your solution here\n}\n`
  }
  if (!starterTemplates.rust) {
    starterTemplates.rust = `impl Solution {\n    pub fn ${defaultMethodName}() {\n        // Write your solution here\n    }\n}\n`
  }
  if (!starterTemplates.sql) {
    starterTemplates.sql = `-- Write your SQL query here\nSELECT * FROM employees LIMIT 10;\n`
  }

  const executionContract: 'function' | 'stdio' | 'sql' = isSql
    ? 'sql'
    : textLower.includes('stdin') || textLower.includes('standard input') || textLower.includes('read input')
    ? 'stdio'
    : 'function'

  let executionHint = ''
  if (executionContract === 'function') {
    executionHint =
      'Function-based question: Your code must return the expected value directly from the designated function/method. Arguments are automatically injected by the execution runner.'
  } else if (executionContract === 'stdio') {
    executionHint =
      'Standard I/O question: Your program must read input from standard input (stdin) and write/print your final output to standard output (stdout).'
  } else {
    executionHint =
      'SQL query question: Write a standard SELECT query against the provided relational sandbox tables to produce the expected result set columns and rows.'
  }

  return {
    id: question.id,
    title: extractedTitle,
    difficulty: ((question.difficulty as any) || 'Medium'),
    assessed_skill: question.assessed_skill || 'Problem Solving',
    description: question.text,
    input_format: inputFormat,
    output_format: outputFormat,
    constraints,
    examples,
    test_cases: testCases,
    starter_templates: starterTemplates,
    is_sql: isSql,
    sql_fixture: question.sql_fixture || 'employees_departments',
    test_cases_available: testCasesAvailable,
    execution_contract: executionContract,
    execution_hint: executionHint,
    function_name: (question as any).function_name || defaultMethodName,
  }
}
