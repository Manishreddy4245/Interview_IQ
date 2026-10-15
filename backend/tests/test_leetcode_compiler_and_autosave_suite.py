"""
Comprehensive Verification Suite for InterviewIQ Coding IDE Improvements
Tests:
1. Java class/method solution with NO main() method
2. Python class/method solution with NO main() method
3. C++ class/method solution with NO main() method
4. Real test case evaluation via submit-code
5. Standalone program preservation (no duplicate main)
6. Autosave draft persistence to session (MongoDB + memory fallback)
7. Per-language draft isolation
8. Per-question draft isolation
9. Out-of-order write protection
10. Failed save handling & error status
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_java_leetcode_solution_without_main():
    """Java class/method solution without candidate-written main() runs and evaluates test cases."""
    candidate_code = """
import java.util.*;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (map.containsKey(complement)) {
                return new int[] { map.get(complement), i };
            }
            map.put(nums[i], i);
        }
        return new int[0];
    }
}
"""
    # 1. Test execute-code with custom stdin
    exec_res = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": candidate_code,
        "stdin": "[2,7,11,15]\n9",
        "question_id": "two_sum"
    })
    assert exec_res.status_code == 200, exec_res.text
    data = exec_res.json()
    assert data["exit_code"] == 0
    assert "[0,1]" in data["output"].replace(" ", "") or "[0, 1]" in data["output"]

    # 2. Test submit-code against real test cases
    sub_res = client.post("/api/interviews/submit-code", json={
        "question_id": "two_sum",
        "language": "java",
        "code": candidate_code,
        "test_cases": [
            {"id": "tc1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
            {"id": "tc2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": False},
            {"id": "tc3", "input": "[3,3]\n6", "expected_output": "[0,1]", "is_hidden": True}
        ]
    })
    assert sub_res.status_code == 200, sub_res.text
    sub_data = sub_res.json()
    assert sub_data["all_passed"] is True
    assert sub_data["passed_tests"] == 3
    assert sub_data["total_tests"] == 3


def test_python_leetcode_solution_without_main():
    """Python class Solution without main() executes and passes test cases."""
    candidate_code = """
class Solution:
    def isValid(self, s: str) -> bool:
        stack = []
        mapping = {")": "(", "}": "{", "]": "["}
        for char in s:
            if char in mapping:
                top_element = stack.pop() if stack else '#'
                if mapping[char] != top_element:
                    return False
            else:
                stack.append(char)
        return not stack
"""
    exec_res = client.post("/api/interviews/execute-code", json={
        "language": "python",
        "code": candidate_code,
        "stdin": "()[]{}",
        "question_id": "valid_parentheses"
    })
    assert exec_res.status_code == 200, exec_res.text
    data = exec_res.json()
    assert data["exit_code"] == 0
    assert "true" in data["output"].lower()

    sub_res = client.post("/api/interviews/submit-code", json={
        "question_id": "valid_parentheses",
        "language": "python",
        "code": candidate_code,
        "test_cases": [
            {"id": "tc1", "input": "()", "expected_output": "true", "is_hidden": False},
            {"id": "tc2", "input": "()[]{}", "expected_output": "true", "is_hidden": False},
            {"id": "tc3", "input": "(]", "expected_output": "false", "is_hidden": False},
            {"id": "tc4", "input": "([)]", "expected_output": "false", "is_hidden": True}
        ]
    })
    assert sub_res.status_code == 200, sub_res.text
    sub_data = sub_res.json()
    assert sub_data["all_passed"] is True
    assert sub_data["passed_tests"] == 4


def test_cpp_leetcode_solution_without_main():
    """C++ class Solution without main() executes and passes test cases."""
    candidate_code = """
#include <vector>
#include <unordered_map>

using namespace std;

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> m;
        for (int i = 0; i < (int)nums.size(); i++) {
            int comp = target - nums[i];
            if (m.find(comp) != m.end()) {
                return {m[comp], i};
            }
            m[nums[i]] = i;
        }
        return {};
    }
};
"""
    exec_res = client.post("/api/interviews/execute-code", json={
        "language": "cpp",
        "code": candidate_code,
        "stdin": "[2,7,11,15]\n9",
        "question_id": "two_sum"
    })
    assert exec_res.status_code == 200, exec_res.text
    data = exec_res.json()
    assert data["exit_code"] == 0
    assert "[0,1]" in data["output"].replace(" ", "")

    sub_res = client.post("/api/interviews/submit-code", json={
        "question_id": "two_sum",
        "language": "cpp",
        "code": candidate_code,
        "test_cases": [
            {"id": "tc1", "input": "[2,7,11,15]\n9", "expected_output": "[0,1]", "is_hidden": False},
            {"id": "tc2", "input": "[3,2,4]\n6", "expected_output": "[1,2]", "is_hidden": False}
        ]
    })
    assert sub_res.status_code == 200, sub_res.text
    sub_data = sub_res.json()
    assert sub_data["all_passed"] is True
    assert sub_data["passed_tests"] == 2


def test_standalone_program_preservation():
    """Candidate code with existing main() does NOT get wrapped with a second main()."""
    candidate_code = """
import java.util.Scanner;

public class StandaloneApp {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNextLine()) {
            String line = sc.nextLine();
            System.out.println("Echo: " + line);
        }
    }
}
"""
    exec_res = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": candidate_code,
        "stdin": "Hello Standalone"
    })
    assert exec_res.status_code == 200, exec_res.text
    data = exec_res.json()
    assert data["exit_code"] == 0
    assert "Echo: Hello Standalone" in data["output"]


def test_autosave_draft_persistence_and_isolation():
    """Verify session drafts save, version ordering, per-language isolation, and retrieval."""
    from unittest.mock import patch, AsyncMock
    from app.schemas.interview import QuestionItem

    mock_questions = [
        QuestionItem(id="q1", question_number=1, text="Given an array of integers nums, return two sum indices.", assessed_skill="Arrays", difficulty="Easy", rubric="Rubric"),
        QuestionItem(id="q2", question_number=2, text="Given a string s containing parentheses, check validity.", assessed_skill="Stacks", difficulty="Easy", rubric="Rubric"),
        QuestionItem(id="q3", question_number=3, text="Given a string s, find the length of longest substring.", assessed_skill="Strings", difficulty="Medium", rubric="Rubric"),
    ]

    # 1. Setup interview session through real API endpoint
    with patch("app.routers.interview.generate_adaptive_questions", new_callable=AsyncMock, return_value=mock_questions):
        setup_res = client.post("/api/interviews/setup", json={
            "role": "Full Stack Engineer",
            "experience_level": "Mid",
            "difficulty": "Medium",
            "focus_areas": "Data Structures",
            "interview_mode": "CODING",
            "target_question_count": 3
        })
    assert setup_res.status_code in (200, 201), setup_res.text
    session = setup_res.json()
    session_id = session["session_id"]
    q1_id = session["questions"][0]["id"]
    q2_id = session["questions"][1]["id"]

    # 2. Save draft for Q1 in Python (v1)
    d1 = client.put(f"/api/interviews/{session_id}/questions/{q1_id}/draft", json={
        "language": "python",
        "code": "def solve(): return 42",
        "version": 1
    })
    assert d1.status_code == 200, d1.text
    res1 = d1.json()
    assert res1["version"] == 1
    assert res1["language"] == "python"

    # 3. Save draft for Q1 in Java (v1) - Language Isolation
    d2 = client.put(f"/api/interviews/{session_id}/questions/{q1_id}/draft", json={
        "language": "java",
        "code": "class Solution { public int solve() { return 42; } }",
        "version": 1
    })
    assert d2.status_code == 200, d2.text
    res2 = d2.json()
    assert res2["language"] == "java"

    # 4. Save draft for Q2 in Python (v1) - Question Isolation
    d3 = client.put(f"/api/interviews/{session_id}/questions/{q2_id}/draft", json={
        "language": "python",
        "code": "def q2_solve(): return 100",
        "version": 1
    })
    assert d3.status_code == 200, d3.text

    # 5. Out-of-order write protection test
    # Increment Q1 Python to v2
    d4 = client.put(f"/api/interviews/{session_id}/questions/{q1_id}/draft", json={
        "language": "python",
        "code": "def solve(): return 43 # updated",
        "version": 2
    })
    assert d4.status_code == 200, d4.text
    assert d4.json()["version"] == 2

    # Attempting to save version 1 again is ignored to protect newer draft
    d5 = client.put(f"/api/interviews/{session_id}/questions/{q1_id}/draft", json={
        "language": "python",
        "code": "def solve(): return 0 # stale slow request",
        "version": 1
    })
    assert d5.status_code == 200
    assert d5.json()["version"] == 2
    assert "ignored" in d5.json()["message"].lower()

    # 6. Retrieve all session drafts
    drafts_res = client.get(f"/api/interviews/{session_id}/drafts")
    assert drafts_res.status_code == 200, drafts_res.text
    drafts_data = drafts_res.json()["drafts"]

    # Verify Q1 has both python (updated v2) and java drafts
    assert q1_id in drafts_data
    assert drafts_data[q1_id]["python"]["code"] == "def solve(): return 43 # updated"
    assert drafts_data[q1_id]["python"]["version"] == 2
    assert "class Solution" in drafts_data[q1_id]["java"]["code"]

    # Verify Q2 has python draft
    assert q2_id in drafts_data
    assert drafts_data[q2_id]["python"]["code"] == "def q2_solve(): return 100"

    # 7. Check full session response includes drafts
    sess_res = client.get(f"/api/interviews/{session_id}")
    assert sess_res.status_code == 200, sess_res.text
    session_data = sess_res.json()
    assert "drafts" in session_data
    assert session_data["drafts"][q1_id]["python"]["version"] == 2


def test_failed_save_simulation():
    """Verify failed save returns proper 404 or error response and does not report false success."""
    non_existent_session = "00000000-0000-0000-0000-000000000000"
    res = client.put(f"/api/interviews/{non_existent_session}/questions/q1/draft", json={
        "language": "python",
        "code": "test",
        "version": 1
    })
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_java_argument_parsing_and_input_matrix():
    """
    Exhaustive regression test suite for Java argument parsing:
    1. Integer array [1,2,3]
    2. Empty array []
    3. Negative and zero values [-1, 0, 25]
    4. Arrays containing spaces [  1 ,   2 , 3   ]
    5. Multiple parameters (array + target integer, single-line and multiline)
    6. Missing required arguments (clear error)
    7. Invalid array input (clear validation error)
    8. Running class Solution method without candidate-written main()
    9. Parameter labels (nums = ..., target = ...)
    10. Verifying actual outputs against expected outputs
    """
    java_solution = """
import java.util.*;

class Solution {
    public int sumElements(int[] nums) {
        int sum = 0;
        for (int x : nums) sum += x;
        return sum;
    }

    public int[] twoSum(int[] nums, int target) {
        for (int i = 0; i < nums.length; i++) {
            for (int j = i + 1; j < nums.length; j++) {
                if (nums[i] + nums[j] == target) {
                    return new int[] { i, j };
                }
            }
        }
        return new int[0];
    }
}
"""
    # 1. Standard integer array [1,2,3]
    r1 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[1,2,3]",
        "function_name": "sumElements"
    })
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["exit_code"] == 0, d1.get("stderr")
    assert d1["output"].strip() == "6"

    # 2. Empty array []
    r2 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[]",
        "function_name": "sumElements"
    })
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["exit_code"] == 0
    assert d2["output"].strip() == "0"

    # 3. Negative and zero values [-1, 0, 25]
    r3 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[-1, 0, 25]",
        "function_name": "sumElements"
    })
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["exit_code"] == 0
    assert d3["output"].strip() == "24"

    # 4. Arrays containing spaces [  1 ,   2 , 3   ]
    r4 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[  1 ,   2 , 3   ]",
        "function_name": "sumElements"
    })
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["exit_code"] == 0
    assert d4["output"].strip() == "6"

    # 5. Multiple parameters on single line with labels: nums = [1, 2, 3], target = 4
    r5 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "nums = [1, 2, 3], target = 4",
        "function_name": "twoSum"
    })
    assert r5.status_code == 200
    d5 = r5.json()
    assert d5["exit_code"] == 0, d5.get("stderr")
    assert "[0,2]" in d5["output"].replace(" ", "")

    # 5b. Multiple parameters raw comma-separated: [2, 7, 11, 15], 9
    r5b = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[2, 7, 11, 15], 9",
        "function_name": "twoSum"
    })
    assert r5b.status_code == 200
    d5b = r5b.json()
    assert d5b["exit_code"] == 0
    assert "[0,1]" in d5b["output"].replace(" ", "")

    # 6. Missing required arguments: method expects 2 parameters (nums, target), but received only 1
    r6 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[1, 2, 3]",
        "function_name": "twoSum"
    })
    assert r6.status_code == 200
    d6 = r6.json()
    assert d6["exit_code"] != 0
    assert "Missing required argument" in (d6.get("stderr") or d6.get("error") or d6.get("output"))

    # 7. Invalid array input: non-integer element returns clean Validation Error
    r7 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[1, abc, 3]",
        "function_name": "sumElements"
    })
    assert r7.status_code == 200
    d7 = r7.json()
    assert d7["exit_code"] != 0
    assert "Validation Error" in (d7.get("stderr") or d7.get("output"))

    # 8. Malformed array input (e.g. "[1" missing closing bracket)
    r8 = client.post("/api/interviews/execute-code", json={
        "language": "java",
        "code": java_solution,
        "stdin": "[1",
        "function_name": "sumElements"
    })
    assert r8.status_code == 200
    d8 = r8.json()
    assert d8["exit_code"] != 0
    assert "Validation Error" in (d8.get("stderr") or d8.get("output"))
