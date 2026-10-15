import asyncio
from app.services.code_execution_service import execute_code_sandboxed, evaluate_code_against_test_cases
from app.schemas.execution import TestCase
from app.services.session_service import (
    create_interview_session,
    save_question_draft,
    get_session_drafts,
)
from app.schemas.interview import InterviewSetupRequest, QuestionItem, SaveDraftRequest

async def main():
    print("--- 1. Testing Java Class/Method without main() ---")
    java_code = """
import java.util.*;

class Solution {
    public int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> map = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int comp = target - nums[i];
            if (map.containsKey(comp)) return new int[]{map.get(comp), i};
            map.put(nums[i], i);
        }
        return new int[]{};
    }
}
"""
    res = await execute_code_sandboxed(
        language="java",
        code=java_code,
        stdin="[2,7,11,15]\n9",
        function_name="twoSum",
    )
    print("Java execution status:", res.status)
    print("Java stdout:", res.stdout.strip())
    assert res.status == "success", f"Java execution failed: {res.stderr or res.error}"
    assert res.stdout.strip() == "[0,1]", f"Unexpected Java stdout: {res.stdout}"

    # Evaluate against real test cases
    tcs = [
        TestCase(id="tc_1", input="[2,7,11,15]\n9", expected_output="[0,1]", is_hidden=False),
        TestCase(id="tc_2", input="[3,2,4]\n6", expected_output="[1,2]", is_hidden=False),
    ]
    sub_res = await evaluate_code_against_test_cases(
        question_id="two_sum",
        language="java",
        code=java_code,
        test_cases=tcs,
        function_name="twoSum",
    )
    print("Java test cases passed:", sub_res.passed_tests, "/", sub_res.total_tests)
    assert sub_res.all_passed, f"Java test cases failed: {sub_res.results}"

    print("--- 2. Testing Python Class/Method without main() ---")
    py_code = """
from typing import List

class Solution:
    def twoSum(self, nums: List[int], target: int) -> List[int]:
        seen = {}
        for i, n in enumerate(nums):
            comp = target - n
            if comp in seen:
                return [seen[comp], i]
            seen[n] = i
        return []
"""
    py_res = await execute_code_sandboxed(
        language="python",
        code=py_code,
        stdin="[3,2,4]\n6",
        function_name="twoSum",
    )
    print("Python stdout:", py_res.stdout.strip())
    assert py_res.status == "success"
    assert py_res.stdout.strip() == "[1,2]"

    print("--- 3. Testing Python String Parens without Tuple Conversion ---")
    py_paren_code = """
class Solution:
    def isValid(self, s: str) -> bool:
        assert isinstance(s, str), f"Expected str, got {type(s)}"
        stack = []
        mapping = {')': '(', '}': '{', ']': '['}
        for char in s:
            if char in mapping:
                top = stack.pop() if stack else '#'
                if mapping[char] != top:
                    return False
            else:
                stack.append(char)
        return not stack
"""
    py_p_res = await execute_code_sandboxed(
        language="python",
        code=py_paren_code,
        stdin="()[]{}",
        function_name="isValid",
    )
    print("Python paren stdout:", py_p_res.stdout.strip())
    assert py_p_res.status == "success"
    assert py_p_res.stdout.strip() == "true"

    print("--- 4. Testing C++ Class/Method without main() ---")
    cpp_code = """
#include <vector>
#include <unordered_map>
using namespace std;

class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> m;
        for (int i = 0; i < (int)nums.size(); ++i) {
            int comp = target - nums[i];
            if (m.count(comp)) return {m[comp], i};
            m[nums[i]] = i;
        }
        return {};
    }
};
"""
    cpp_res = await execute_code_sandboxed(
        language="cpp",
        code=cpp_code,
        stdin="[3,3]\n6",
        function_name="twoSum",
    )
    print("C++ stdout:", repr(cpp_res.stdout), "status:", cpp_res.status, "error:", repr(cpp_res.error), "stderr:", repr(cpp_res.stderr))
    assert cpp_res.status == "success", f"C++ failed: {cpp_res.stderr or cpp_res.error}"
    assert cpp_res.stdout.strip() == "[0,1]"

    print("--- 5. Testing Standalone Java Program with Candidate main() ---")
    java_standalone = """
import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        if (sc.hasNext()) {
            System.out.println("Hello " + sc.next());
        }
    }
}
"""
    java_std_res = await execute_code_sandboxed(
        language="java",
        code=java_standalone,
        stdin="World",
    )
    print("Java standalone stdout:", java_std_res.stdout.strip())
    assert java_std_res.status == "success"
    assert java_std_res.stdout.strip() == "Hello World"

    print("--- 6. Testing Autosave Draft Persistence & Out-of-order Protection ---")
    setup_req = InterviewSetupRequest(
        role="Full Stack Engineer",
        experience_level="Mid-Level",
        difficulty="Medium",
        focus_areas="Data Structures, Algorithms",
        interview_mode="CODING",
    )
    q1 = QuestionItem(
        id="q_1",
        question_number=1,
        text="Implement Two Sum algorithm",
        assessed_skill="Hash Maps",
        difficulty="Easy",
        rubric="O(N) time complexity",
        question_type="coding",
    )
    session_res = await create_interview_session(setup=setup_req, questions=[q1])
    sid = session_res.session_id
    print("Created session:", sid)

    # Save draft v1 (Python)
    d1 = await save_question_draft(
        session_id=sid,
        question_id="q_1",
        draft_data=SaveDraftRequest(
            language="python",
            code="def twoSum(): pass",
            version=1,
        ),
    )
    print("Draft 1 saved:", d1.saved_to_db, d1.db_status, d1.version)
    assert d1.version == 1

    # Save draft v2 (Python)
    d2 = await save_question_draft(
        session_id=sid,
        question_id="q_1",
        draft_data=SaveDraftRequest(
            language="python",
            code="def twoSum(nums, target): return [0, 1]",
            version=2,
        ),
    )
    print("Draft 2 saved:", d2.version)
    assert d2.version == 2

    # Attempt to save stale draft v1 (simulating slow out-of-order network response)
    d_stale = await save_question_draft(
        session_id=sid,
        question_id="q_1",
        draft_data=SaveDraftRequest(
            language="python",
            code="OLDER STALE DRAFT",
            version=1,
        ),
    )
    print("Stale draft response:", d_stale.message, "active version:", d_stale.version)
    assert d_stale.version == 2

    # Save draft for Java (different language isolation on same question)
    d_java = await save_question_draft(
        session_id=sid,
        question_id="q_1",
        draft_data=SaveDraftRequest(
            language="java",
            code="class Solution { ... }",
            version=1,
        ),
    )
    print("Java draft saved:", d_java.language, d_java.version)

    # Retrieve all drafts
    all_drafts = await get_session_drafts(sid)
    print("Session drafts:", all_drafts)
    assert "python" in all_drafts["q_1"]
    assert "java" in all_drafts["q_1"]
    assert all_drafts["q_1"]["python"]["code"] == "def twoSum(nums, target): return [0, 1]"
    assert all_drafts["q_1"]["java"]["code"] == "class Solution { ... }"

    print("\nALL BACKEND VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
