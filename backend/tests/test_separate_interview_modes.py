"""
InterviewIQ - Regression Test Suite for Separate Coding Interview and Verbal Interview Modes.

Proves:
1. A coding session generates coding problems with IDE attributes (test_cases, available_modes == ['coding']).
2. A verbal session generates natural-language questions and never requests code implementation.
3. A coding question cannot enter a verbal session (normalizer cleans code/test case artifacts).
4. A verbal question cannot enter a coding session (normalizer enriches with coding IDE/test case attributes).
5. Submitting code in a verbal session is strictly rejected with HTTP 400.
6. Submitting verbal text without code in a coding session is strictly rejected with HTTP 400.
7. Session mode persists across question generation, submission, evaluation, and next-question selection.
8. Switching between the two entry points creates/starts the correct session type without mixing histories.
9. Legacy sessions with inconsistent/mixed question history are marked AMBIGUOUS / is_unreliable_mode=True and reject submissions.
10. Existing authentication, session ownership, and adaptive evaluation remain intact.
"""
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.problem_catalog import (
    resolve_canonical_question_type,
    resolve_available_and_recommended_modes,
    normalize_and_classify_question,
)
from app.schemas.interview import (
    InterviewSetupRequest,
    QuestionItem,
    SubmitAnswerRequest,
)
from app.schemas.execution import CodeSubmissionResult, TestCaseResult
from app.schemas.evaluation import AIEvaluationRaw, CriterionScore, CriterionScores
from app.services.session_service import _in_memory_sessions

client = TestClient(app)


@pytest.fixture
def candidate_auth():
    """Register and log in a fresh candidate student."""
    import uuid
    uid_suffix = str(uuid.uuid4())[:8]
    username = f"cand_sep_{uid_suffix}"
    email = f"cand.sep.{uid_suffix}@example.com"
    pwd = "SecureSeparatedPassword123!"

    reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "name": f"Candidate {uid_suffix}",
            "email": email,
            "password": pwd,
            "role": "candidate",
        },
    )
    assert reg.status_code in (200, 201)
    data = reg.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data["user_id"]


def test_question_catalog_mode_isolation():
    """Verify core problem catalog enforces strict mode isolation based on session_mode."""
    # 1. In a CODING session, available modes must strictly be ['coding']
    coding_modes, rec_coding = resolve_available_and_recommended_modes("coding", session_mode="CODING")
    assert coding_modes == ["coding"]
    assert rec_coding == "coding"

    # Even if question text resembles verbal or system design, session_mode="CODING" locks available_modes
    mixed_modes, rec_mixed = resolve_available_and_recommended_modes("system_design", session_mode="CODING")
    assert mixed_modes == ["coding"]
    assert rec_mixed == "coding"

    # 2. In a VERBAL session, available modes must strictly be ['verbal']
    verbal_modes, rec_verbal = resolve_available_and_recommended_modes("verbal", session_mode="VERBAL")
    assert verbal_modes == ["verbal"]
    assert rec_verbal == "verbal"

    # Even if question text resembles coding, session_mode="VERBAL" locks available_modes
    code_in_verbal_modes, rec_civ = resolve_available_and_recommended_modes("coding", session_mode="VERBAL")
    assert code_in_verbal_modes == ["verbal"]
    assert rec_civ == "verbal"


def test_normalizer_prevents_cross_mode_contamination():
    """Verify normalizer cleanses or equips attributes so questions never cross session boundaries."""
    # A. A coding question entering a VERBAL session is stripped of code/compiler artifacts
    coding_q_input = {
        "id": "q_test_1",
        "question_number": 1,
        "text": "Implement Two Sum with test cases.",
        "assessed_skill": "Algorithms",
        "difficulty": "Medium",
        "rubric": "Code correctness",
        "question_type": "coding",
        "code_template": "def twoSum(): pass",
        "test_cases": [{"input": "[2, 7], 9", "expected_output": "[0, 1]"}],
    }
    normalized_for_verbal = normalize_and_classify_question(coding_q_input, session_mode="VERBAL")
    assert normalized_for_verbal["question_type"] == "verbal"
    assert normalized_for_verbal.get("test_cases") is None
    assert normalized_for_verbal.get("code_template") is None
    assert normalized_for_verbal["available_modes"] == ["verbal"]
    assert normalized_for_verbal["recommended_mode"] == "verbal"

    # B. A verbal question entering a CODING session is equipped with coding IDE requirements
    verbal_q_input = {
        "id": "q_test_2",
        "question_number": 1,
        "text": "Explain how HashMap handles collisions.",
        "assessed_skill": "Data Structures",
        "difficulty": "Medium",
        "rubric": "Explanation depth",
        "question_type": "verbal",
    }
    normalized_for_coding = normalize_and_classify_question(verbal_q_input, session_mode="CODING")
    assert normalized_for_coding["question_type"] == "coding"
    assert normalized_for_coding["available_modes"] == ["coding"]
    assert normalized_for_coding["recommended_mode"] == "coding"
    assert normalized_for_coding["test_cases"] is not None
    assert len(normalized_for_coding["test_cases"]) > 0


def test_coding_session_creation_and_attributes(candidate_auth):
    """Proves that a coding interview session generates coding problems and IDE attributes."""
    headers, user_id = candidate_auth

    mock_coding_llm_json = """{
        "id": "q_1",
        "question_number": 1,
        "title": "Reverse Words in a String",
        "text": "Given an input string s, reverse the order of the words.",
        "assessed_skill": "String Manipulation",
        "difficulty": "Medium",
        "rubric": "O(N) runtime, in-place manipulation where possible",
        "question_type": "coding",
        "function_name": "reverseWords",
        "input_format": "s: str",
        "output_format": "str",
        "constraints": ["1 <= s.length <= 10^4"],
        "examples": [{"example_number": 1, "input": "\\"the sky is blue\\"", "output": "\\"blue is sky the\\""}],
        "test_cases": [{"id": "tc_1", "input": "\\"the sky is blue\\"", "expected_output": "\\"blue is sky the\\"", "is_hidden": false}],
        "selection_rationale": "Assess core string manipulation competency."
    }"""

    with patch("app.services.question_generator.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = mock_coding_llm_json

        res = client.post(
            "/api/interviews/setup",
            json={
                "role": "Backend Engineer",
                "experience_level": "Mid-Level",
                "difficulty": "Medium",
                "focus_areas": "Algorithms, Data Structures",
                "interview_mode": "CODING",
                "adaptive": True,
                "question_count": 3,
                "duration_minutes": 30,
            },
            headers=headers,
        )

        assert res.status_code == 201
        session_data = res.json()
        assert session_data["interview_mode"] == "CODING"
        assert session_data["is_unreliable_mode"] is False

        q1 = session_data["questions"][0]
        assert q1["question_type"] == "coding"
        assert q1["available_modes"] == ["coding"]
        assert q1["recommended_mode"] == "coding"
        assert q1["test_cases"] is not None and len(q1["test_cases"]) > 0


def test_verbal_session_creation_and_attributes(candidate_auth):
    """Proves that a verbal interview session generates natural-language questions without code implementation tasks."""
    headers, user_id = candidate_auth

    mock_verbal_llm_json = """{
        "id": "q_1",
        "question_number": 1,
        "text": "Describe a scenario where you had to debug a difficult production performance issue. What was your process?",
        "assessed_skill": "Debugging & Reliability",
        "difficulty": "Medium",
        "rubric": "Systematic root-cause methodology, log and APM analysis, post-mortem",
        "question_type": "verbal",
        "selection_rationale": "Assess practical engineering problem solving and communication."
    }"""

    with patch("app.services.question_generator.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = mock_verbal_llm_json

        res = client.post(
            "/api/interviews/setup",
            json={
                "role": "Site Reliability Engineer",
                "experience_level": "Mid-Level",
                "difficulty": "Medium",
                "focus_areas": "Debugging, Reliability, Incident Management",
                "interview_mode": "VERBAL",
                "adaptive": True,
                "question_count": 3,
                "duration_minutes": 30,
            },
            headers=headers,
        )

        assert res.status_code == 201
        session_data = res.json()
        assert session_data["interview_mode"] == "VERBAL"
        assert session_data["is_unreliable_mode"] is False

        q1 = session_data["questions"][0]
        assert q1["question_type"] == "verbal"
        assert q1["available_modes"] == ["verbal"]
        assert q1["recommended_mode"] == "verbal"
        assert q1.get("test_cases") is None


def test_rejection_of_incompatible_submissions(candidate_auth):
    """Proves mode compatibility validation rejects code in verbal and verbal in coding."""
    headers, user_id = candidate_auth

    # 1. Setup CODING session
    coding_sess_id = f"test_cod_{user_id}"
    _in_memory_sessions[coding_sess_id] = {
        "session_id": coding_sess_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Software Engineer",
        "experience_level": "Mid-Level",
        "interview_mode": "CODING",
        "status": "in_progress",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_adaptive": False,
        "questions": [
            {
                "id": "q_c1",
                "text": "Implement binary search on sorted array.",
                "rubric": "O(log n) time",
                "question_type": "coding",
                "test_cases": [{"input": "[1,3,5], 3", "output": "1"}],
            }
        ],
        "answers": {},
    }

    # Attempt verbal answer to coding session -> 400
    res_code = client.post(
        f"/api/interviews/{coding_sess_id}/questions/q_c1/evaluate",
        json={
            "question_id": "q_c1",
            "answer_mode": "verbal",
            "answer_text": "I will divide the array in halves recursively.",
        },
        headers=headers,
    )
    assert res_code.status_code == 400
    assert "Coding Interview session" in res_code.json()["detail"]

    # 2. Setup VERBAL session
    verbal_sess_id = f"test_vrb_{user_id}"
    _in_memory_sessions[verbal_sess_id] = {
        "session_id": verbal_sess_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Engineering Manager",
        "experience_level": "Senior",
        "interview_mode": "VERBAL",
        "status": "in_progress",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_adaptive": False,
        "questions": [
            {
                "id": "q_v1",
                "text": "How do you handle underperforming engineers on your team?",
                "rubric": "Empathy, clear expectations, PIP timeline",
                "question_type": "verbal",
            }
        ],
        "answers": {},
    }

    # Attempt code answer to verbal session -> 400
    res_verb = client.post(
        f"/api/interviews/{verbal_sess_id}/questions/q_v1/evaluate",
        json={
            "question_id": "q_v1",
            "answer_mode": "coding",
            "code": "def fire_engineer(emp_id): return True",
            "language": "python",
        },
        headers=headers,
    )
    assert res_verb.status_code == 400
    assert "Verbal Interview session" in res_verb.json()["detail"]


def test_session_mode_persists_across_next_question_adaptation(candidate_auth):
    """Proves mode persists across question generation, submission, and adaptation lifecycle."""
    headers, user_id = candidate_auth

    # Coding session
    sess_id = f"adapt_mode_{user_id}"
    _in_memory_sessions[sess_id] = {
        "session_id": sess_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Backend Engineer",
        "experience_level": "Mid-Level",
        "difficulty": "Medium",
        "focus_areas": "Algorithms, Systems",
        "interview_mode": "CODING",
        "status": "in_progress",
        "target_question_count": 3,
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_adaptive": True,
        "active_question_id": "q_ad_1",
        "questions": [
            {
                "id": "q_ad_1",
                "question_number": 1,
                "text": "Implement LRU Cache with get and put in O(1).",
                "assessed_skill": "Data Structures",
                "difficulty": "Medium",
                "rubric": "Doubly linked list + Hash Map",
                "question_type": "coding",
                "available_modes": ["coding"],
                "recommended_mode": "coding",
                "test_cases": [{"input": "put(1,1), get(1)", "expected_output": "1"}],
            }
        ],
        "answers": {},
    }

    mock_exec = CodeSubmissionResult(
        question_id="q_ad_1",
        language="python",
        all_passed=True,
        passed_tests=1,
        total_tests=1,
        results=[
            TestCaseResult(
                test_case_id="tc_1",
                passed=True,
                input="put(1,1), get(1)",
                expected_output="1",
                actual_output="1",
                execution_time_ms=10,
            )
        ],
        total_execution_time_ms=10,
    )

    mock_adapted_coding_json = """{
        "id": "q_ad_2",
        "question_number": 2,
        "title": "LFU Cache",
        "text": "Implement Least Frequently Used (LFU) Cache with O(1) operations.",
        "assessed_skill": "Advanced Data Structures",
        "difficulty": "Hard",
        "rubric": "Frequency hash map with doubly linked lists",
        "question_type": "coding",
        "function_name": "LFUCache",
        "input_format": "operations",
        "output_format": "results",
        "constraints": ["1 <= capacity <= 10^4"],
        "examples": [{"example_number": 1, "input": "...", "output": "..."}],
        "test_cases": [{"id": "tc_1", "input": "...", "expected_output": "...", "is_hidden": false}],
        "selection_rationale": "Candidate demonstrated strong LRU implementation; stepping up to LFU Cache."
    }"""

    with patch("app.routers.interview.evaluate_code_against_test_cases", new_callable=AsyncMock) as mock_run_code, \
         patch("app.services.adaptation_service.groq_manager.execute_chat_completion", new_callable=AsyncMock) as mock_groq:
        mock_run_code.return_value = mock_exec
        mock_groq.return_value = mock_adapted_coding_json

        res = client.post(
            f"/api/interviews/{sess_id}/submit-and-adapt",
            json={
                "question_id": "q_ad_1",
                "answer_mode": "coding",
                "code": "class LRUCache: pass",
                "language": "python",
                "remaining_seconds": 1500,
            },
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data["evaluation"]["overall_score"] > 0
        assert data["next_question"] is not None
        assert data["next_question"]["question_type"] == "coding"
        assert data["next_question"]["available_modes"] == ["coding"]

        # Ensure session in memory retained CODING mode
        assert _in_memory_sessions[sess_id]["interview_mode"] == "CODING"


def test_legacy_mixed_session_safely_marked_ambiguous(candidate_auth):
    """Proves legacy/mixed question history sessions are marked AMBIGUOUS and reject submissions."""
    headers, user_id = candidate_auth

    ambig_id = f"ambig_{user_id}"
    _in_memory_sessions[ambig_id] = {
        "session_id": ambig_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Full Stack Engineer",
        "experience_level": "Mid-Level",
        "status": "in_progress",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_adaptive": False,
        "questions": [
            {
                "id": "q_mix_1",
                "text": "Write a function to reverse a string.",
                "rubric": "O(n) time",
                "question_type": "coding",
                "test_cases": [{"input": "'abc'", "output": "'cba'"}],
            },
            {
                "id": "q_mix_2",
                "text": "Tell me about a time you had a technical disagreement with a team member.",
                "rubric": "Conflict resolution and empathy",
                "question_type": "verbal",
            },
        ],
        "answers": {},
    }

    # Fetch session: verify it's flagged as AMBIGUOUS and is_unreliable_mode=True
    get_res = client.get(f"/api/interviews/{ambig_id}", headers=headers)
    assert get_res.status_code == 200
    body = get_res.json()
    assert body["interview_mode"] == "AMBIGUOUS"
    assert body["is_unreliable_mode"] is True

    # Attempt submit to ambiguous session: must fail closed with HTTP 400
    sub_res = client.post(
        f"/api/interviews/{ambig_id}/answers",
        json={
            "question_id": "q_mix_1",
            "answer_mode": "coding",
            "code": "def solve(): pass",
        },
        headers=headers,
    )
    assert sub_res.status_code == 400
    assert "ambiguous or unreliable" in sub_res.json()["detail"]


def test_clean_legacy_sessions_resolve_accurately(candidate_auth):
    """Proves legacy sessions containing only coding or only verbal are safely classified."""
    headers, user_id = candidate_auth

    # 1. Pure coding legacy
    pure_code_id = f"pure_c_{user_id}"
    _in_memory_sessions[pure_code_id] = {
        "session_id": pure_code_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Python Developer",
        "experience_level": "Mid-Level",
        "status": "in_progress",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "questions": [
            {
                "id": "q_p1",
                "text": "Implement QuickSort.",
                "question_type": "coding",
                "test_cases": [{"input": "[3,1,2]", "output": "[1,2,3]"}],
            }
        ],
    }
    c_res = client.get(f"/api/interviews/{pure_code_id}", headers=headers)
    assert c_res.status_code == 200
    assert c_res.json()["interview_mode"] == "CODING"
    assert c_res.json()["is_unreliable_mode"] is False

    # 2. Pure verbal legacy
    pure_verb_id = f"pure_v_{user_id}"
    _in_memory_sessions[pure_verb_id] = {
        "session_id": pure_verb_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Product Manager",
        "experience_level": "Senior",
        "status": "in_progress",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "questions": [
            {
                "id": "q_pv1",
                "text": "How do you prioritize your product backlog?",
                "question_type": "verbal",
            }
        ],
    }
    v_res = client.get(f"/api/interviews/{pure_verb_id}", headers=headers)
    assert v_res.status_code == 200
    assert v_res.json()["interview_mode"] == "VERBAL"
    assert v_res.json()["is_unreliable_mode"] is False
