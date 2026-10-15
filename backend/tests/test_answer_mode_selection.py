import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.core.problem_catalog import (
    resolve_canonical_question_type,
    resolve_available_and_recommended_modes,
    normalize_and_classify_question,
)
from app.schemas.interview import QuestionItem, SubmitAnswerRequest
from app.schemas.execution import CodeSubmissionResult, TestCaseResult
from app.schemas.evaluation import AIEvaluationRaw, CriterionScore, CriterionScores


client = TestClient(app)


# ============================================================================
# 1. QUESTION CLASSIFICATION & NORMALIZATION TESTS
# ============================================================================

def test_canonical_classification_never_classifies_coding_as_verbal():
    """Ensure coding problems are never classified as verbal even if they contain text."""
    coding_cases = [
        {"text": "Write a function to find the two numbers that sum up to target in an array."},
        {"text": "Given an array of integers nums and an integer target, return indices.", "code_template": "def twoSum(nums, target):"},
        {"text": "Reverse a linked list in O(n) time.", "test_cases": [{"input": "[1,2,3]", "output": "[3,2,1]"}]},
        {"text": "Implement Dijkstra shortest path algorithm in C++."},
        {"text": "What is the Big-O time complexity and implement Binary Search tree insertion.", "programming_language": "python"},
    ]
    for case in coding_cases:
        resolved, _, _ = resolve_canonical_question_type(case)
        assert resolved == "coding", f"Failed for {case}: got {resolved} instead of coding"


def test_canonical_classification_sql_and_system_design():
    """Verify SQL and System Design prompts are accurately distinguished."""
    sql_cases = [
        {"text": "Write a SQL query to find employees earning more than their managers.", "expected_sql_query": "SELECT * FROM emp"},
        {"text": "SELECT department_id, COUNT(*) FROM employees GROUP BY department_id HAVING COUNT(*) > 5;"},
        {"text": "Retrieve total revenue per customer from orders table with JOIN.", "sql_fixture": "ecommerce"},
    ]
    for case in sql_cases:
        resolved, _, _ = resolve_canonical_question_type(case)
        assert resolved == "sql", f"Failed for SQL case {case}: got {resolved}"

    design_cases = [
        {"text": "Design a URL shortening service like TinyURL handling 100M daily active users."},
        {"text": "Architect a distributed notification system with Kafka, microservices, and high availability."},
        {"text": "Design Instagram feed architecture considering caching, database sharding, and CDN."},
    ]
    for case in design_cases:
        resolved, _, _ = resolve_canonical_question_type(case)
        assert resolved == "system_design", f"Failed for system design case {case}: got {resolved}"


def test_canonical_classification_verbal_and_mcq():
    """Verify behavioral/conceptual questions and multiple choice questions."""
    verbal_case = {"text": "Tell me about a time you resolved a major disagreement within your engineering team."}
    resolved, _, _ = resolve_canonical_question_type(verbal_case)
    assert resolved == "verbal"

    mcq_case = {"text": "What is the worst-case time complexity of QuickSort?", "options": ["O(n)", "O(n log n)", "O(n^2)", "O(1)"]}
    resolved, _, _ = resolve_canonical_question_type(mcq_case)
    assert resolved == "multiple_choice"


def test_resolve_available_and_recommended_modes():
    """Ensure each question type resolves strictly compatible modes and default recommendation."""
    # Coding
    modes, rec = resolve_available_and_recommended_modes("coding", {})
    assert "coding" in modes
    assert "verbal" in modes
    assert rec == "coding"
    assert "sql" not in modes

    # SQL
    modes, rec = resolve_available_and_recommended_modes("sql", {})
    assert "sql" in modes
    assert "verbal" in modes
    assert rec == "sql"
    assert "coding" not in modes

    # System Design
    modes, rec = resolve_available_and_recommended_modes("system_design", {})
    assert "system_design" in modes
    assert "verbal" in modes
    assert rec == "system_design"
    assert "coding" not in modes

    # Verbal
    modes, rec = resolve_available_and_recommended_modes("verbal", {})
    assert modes == ["verbal"]
    assert rec == "verbal"


def test_normalize_and_classify_question_enriches_missing_metadata():
    """Missing or corrupted question metadata is safely normalized and migrated."""
    raw = {
        "id": "two_sum",
        "text": "Given an array of integers nums and an integer target, return indices of the two numbers.",
        "rubric": "Code correctness, O(n) time, O(n) space",
    }
    enriched = normalize_and_classify_question(raw)
    assert enriched["question_type"] == "coding"
    assert enriched["recommended_mode"] == "coding"
    assert "coding" in enriched["available_modes"]
    assert "verbal" in enriched["available_modes"]
    assert "starter_templates" in enriched
    assert len(enriched.get("test_cases", [])) > 0


# ============================================================================
# 2. SCHEMA & SUBMISSION VALIDATION TESTS
# ============================================================================

def test_submit_answer_request_requires_mode_specific_payload():
    """Verify SubmitAnswerRequest enforces content based on answer_mode."""
    # Coding mode without code should fail
    with pytest.raises(ValueError):
        SubmitAnswerRequest(
            question_id="q1",
            answer_mode="coding",
            answer_text="Here is my thought",
            code=None,
        )

    # Coding mode with code should pass
    req = SubmitAnswerRequest(
        question_id="q1",
        answer_mode="coding",
        code="def solve(): pass",
        language="python",
    )
    assert req.answer_mode == "coding"
    assert req.code == "def solve(): pass"

    # SQL mode without sql_query should fail
    with pytest.raises(ValueError):
        SubmitAnswerRequest(
            question_id="q1",
            answer_mode="sql",
            sql_query="",
        )

    # SQL mode with sql_query should pass
    req_sql = SubmitAnswerRequest(
        question_id="q1",
        answer_mode="sql",
        sql_query="SELECT 1;",
    )
    assert req_sql.answer_mode == "sql"

    # Verbal mode without answer_text should fail
    with pytest.raises(ValueError):
        SubmitAnswerRequest(
            question_id="q1",
            answer_mode="verbal",
            answer_text="",
        )


from datetime import datetime, timezone
from app.services.session_service import _in_memory_sessions


# ============================================================================
# 3. END-TO-END ROUTING & MODE SWITCHING IN INTERVIEW SESSIONS
# ============================================================================

@pytest.fixture
def auth_headers():
    """Register and login a student to get auth token and user_id."""
    import uuid
    suffix = str(uuid.uuid4())[:8]
    uname = f"stud_{suffix}"
    email = f"student.modes.{suffix}@example.com"
    pwd = "SecureStudentPass123!"

    reg_res = client.post("/api/auth/register", json={
        "username": uname,
        "name": "Mode Test Student",
        "email": email,
        "password": pwd,
        "role": "candidate",
    })
    assert reg_res.status_code in (200, 201)
    data = reg_res.json()
    token = data["access_token"]
    user_id = data["user_id"]
    return {"Authorization": f"Bearer {token}"}, user_id


def test_answer_submission_and_evaluator_routing(auth_headers):
    """Test submission routing with separate Coding and Verbal interview sessions."""
    headers, user_id = auth_headers

    # 1. CODING SESSION: Only accepts code submissions; rejects verbal text submissions
    coding_session_id = f"sess_coding_{user_id}"
    _in_memory_sessions[coding_session_id] = {
        "session_id": coding_session_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Full Stack Engineer",
        "experience_level": "mid-level",
        "interview_mode": "CODING",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "is_adaptive": False,
        "active_question_id": "q-code-1",
        "questions": [
            {
                "id": "q-code-1",
                "text": "Given an array of integers, return the indices of two numbers that sum to target.",
                "rubric": "Time complexity O(n), Space complexity O(n)",
                "question_type": "coding",
                "available_modes": ["coding"],
                "recommended_mode": "coding",
                "test_cases": [{"input": "[2,7,11,15], 9", "output": "[0, 1]"}],
            },
        ],
        "answers": {},
    }

    get_coding_res = client.get(f"/api/interviews/{coding_session_id}", headers=headers)
    assert get_coding_res.status_code == 200
    coding_questions = get_coding_res.json()["questions"]
    assert coding_questions[0]["recommended_mode"] == "coding"
    assert "coding" in coding_questions[0]["available_modes"]

    # Submit code in CODING mode -> runs sandbox compiler test cases
    with patch("app.routers.interview.evaluate_code_against_test_cases", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = CodeSubmissionResult(
            question_id="q-code-1",
            language="python",
            all_passed=True,
            passed_tests=1,
            total_tests=1,
            results=[
                TestCaseResult(
                    test_case_id="tc_1",
                    passed=True,
                    input="[2,7,11,15], 9",
                    expected_output="[0, 1]",
                    actual_output="[0, 1]",
                    execution_time_ms=12,
                )
            ],
            total_execution_time_ms=12,
        )

        submit_code_res = client.post(
            f"/api/interviews/{coding_session_id}/questions/q-code-1/evaluate",
            json={
                "question_id": "q-code-1",
                "answer_mode": "coding",
                "code": "def two_sum(nums, target):\n    return [0, 1]",
                "language": "python",
            },
            headers=headers,
        )
        assert submit_code_res.status_code == 200
        data = submit_code_res.json()
        assert data["overall_score"] > 0
        assert "criterion_scores" in data

    # Attempt to submit text without code in a CODING interview session -> Strictly rejected HTTP 400
    reject_verbal_in_coding = client.post(
        f"/api/interviews/{coding_session_id}/questions/q-code-1/evaluate",
        json={
            "question_id": "q-code-1",
            "answer_mode": "verbal",
            "answer_text": "I would use a hash map to solve this.",
        },
        headers=headers,
    )
    assert reject_verbal_in_coding.status_code == 400
    assert "Coding Interview session" in reject_verbal_in_coding.json()["detail"]

    # 2. VERBAL SESSION: Only accepts verbal/conceptual answers; rejects code submissions
    verbal_session_id = f"sess_verbal_{user_id}"
    _in_memory_sessions[verbal_session_id] = {
        "session_id": verbal_session_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Full Stack Engineer",
        "experience_level": "mid-level",
        "interview_mode": "VERBAL",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "is_adaptive": False,
        "active_question_id": "q-sys-1",
        "questions": [
            {
                "id": "q-sys-1",
                "text": "Design a real-time collaborative code editor like Google Docs / VS Code Live Share.",
                "rubric": "OT/CRDT, WebSockets, conflict resolution, persistence",
                "question_type": "system_design",
                "available_modes": ["verbal"],
                "recommended_mode": "verbal",
            },
        ],
        "answers": {},
    }

    mock_design_raw = AIEvaluationRaw(
        overall_score=92,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Addressed collaboration"),
            technical_depth=CriterionScore(score=9, feedback="Deep CRDT design"),
            completeness=CriterionScore(score=9, feedback="Addressed all 5 pillars"),
            structure_flow=CriterionScore(score=9, feedback="Well structured markdown"),
            clarity_conciseness=CriterionScore(score=10, feedback="Professional engineering proposal"),
        ),
        strengths=["Excellent breakdown of CRDT vs OT algorithms", "Clean WebSocket connection pool architecture"],
        areas_for_improvement=["Detail snapshotting frequency in Redis"],
        actionable_suggestions=["Provide concrete throughput figures."],
        coaching_summary="Professional and thorough system design proposal.",
        stronger_example_answer="A distributed CRDT model with WebSocket gateways.",
        recommended_practice="How to handle network partitions?",
    )

    with patch("app.routers.interview.evaluate_candidate_answer", new_callable=AsyncMock) as mock_verbal_eval:
        mock_verbal_eval.return_value = mock_design_raw

        submit_verbal_res = client.post(
            f"/api/interviews/{verbal_session_id}/questions/q-sys-1/evaluate",
            json={
                "question_id": "q-sys-1",
                "answer_mode": "verbal",
                "answer_text": "### 1. Scope & Scale\nSupport 50 simultaneous editors per document.\n### 2. Architecture\nClient connects via WebSocket to Gateway. Changes broadcast using Yjs CRDT.\n### 3. Data Storage\nPostgres for document metadata, S3 for immutable snapshots, Redis for presence.\n### 4. Scalability\nSticky sessions via HAProxy, Redis Pub/Sub between nodes.\n### 5. Trade-offs\nEventual consistency chosen over strict ACID lock.",
            },
            headers=headers,
        )
        assert submit_verbal_res.status_code == 200
        assert submit_verbal_res.json()["overall_score"] == 92

    # Attempt to submit code to a VERBAL session -> Strictly rejected HTTP 400
    reject_code_in_verbal = client.post(
        f"/api/interviews/{verbal_session_id}/questions/q-sys-1/evaluate",
        json={
            "question_id": "q-sys-1",
            "answer_mode": "coding",
            "code": "def solve(): pass",
            "language": "python",
        },
        headers=headers,
    )
    assert reject_code_in_verbal.status_code == 400
    assert "Verbal Interview session" in reject_code_in_verbal.json()["detail"]


def test_submit_and_adapt_lifecycle_with_answer_mode(auth_headers):
    """Verify adaptive progression records answer_mode and adapts sequentially."""
    headers, user_id = auth_headers
    session_id = f"sess_adapt_{user_id}"

    _in_memory_sessions[session_id] = {
        "session_id": session_id,
        "owner_id": user_id,
        "candidate_id": user_id,
        "role": "Backend Engineer",
        "experience_level": "mid-level",
        "duration_minutes": 30,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "in_progress",
        "is_adaptive": True,
        "active_question_id": "q-adapt-1",
        "questions": [
            {
                "id": "q-adapt-1",
                "question_number": 1,
                "assessed_skill": "Databases",
                "difficulty": "Medium",
                "text": "Explain the difference between optimistic and pessimistic locking in relational databases.",
                "rubric": "Transaction isolation, concurrency trade-offs",
                "question_type": "verbal",
                "available_modes": ["verbal"],
                "recommended_mode": "verbal",
            }
        ],
        "answers": {},
    }

    next_q_mock = QuestionItem(
        id="q-adapt-2",
        question_number=2,
        assessed_skill="Data Structures",
        difficulty="Hard",
        text="Write a Python function to implement a thread-safe LRU Cache with O(1) get and put.",
        rubric="Thread safety, Lock/RLock, O(1) hash map + doubly linked list",
        question_type="coding",
        available_modes=["coding", "verbal"],
        recommended_mode="coding",
    )

    mock_verbal_raw = AIEvaluationRaw(
        overall_score=85,
        criterion_scores=CriterionScores(
            relevance=CriterionScore(score=9, feedback="Direct answer"),
            technical_depth=CriterionScore(score=8, feedback="Good understanding"),
            completeness=CriterionScore(score=8, feedback="Covered both"),
            structure_flow=CriterionScore(score=9, feedback="Clear explanation"),
            clarity_conciseness=CriterionScore(score=9, feedback="Structured"),
        ),
        strengths=["Accurately defined both locking mechanisms"],
        areas_for_improvement=["Give a concrete deadlock example"],
        actionable_suggestions=["Provide deadlock examples."],
        coaching_summary="Good explanation of optimistic versus pessimistic concurrency.",
        stronger_example_answer="Optimistic uses versioning, pessimistic uses row locks.",
        recommended_practice="When does optimistic locking cause starvation?",
    )

    with patch("app.routers.interview.evaluate_candidate_answer", new_callable=AsyncMock) as mock_eval, \
         patch("app.routers.interview.generate_next_adaptive_question", new_callable=AsyncMock) as mock_gen_next:

        mock_eval.return_value = mock_verbal_raw
        mock_gen_next.return_value = next_q_mock

        res = client.post(
            f"/api/interviews/{session_id}/submit-and-adapt",
            json={
                "question_id": "q-adapt-1",
                "answer_mode": "verbal",
                "answer_text": "Optimistic locking assumes collisions are rare and verifies record version upon update. Pessimistic locking acquires a row lock (SELECT FOR UPDATE) preventing concurrent access.",
            },
            headers=headers,
        )

        assert res.status_code == 200
        data = res.json()
        assert data["answer_mode"] == "verbal"
        assert data["evaluation"]["overall_score"] == 85
        assert data["next_question"] is not None
        assert data["next_question"]["id"] == "q-adapt-2"
        assert data["next_question"]["recommended_mode"] == "coding"
        assert "coding" in data["next_question"]["available_modes"]
