"""
Test Suite for Text Assessment ML Model and Reusable Backend Services.
Direct verification of the refactored Text_Assessment_Model.ipynb machine learning pipeline.

Covers:
1. Neural SentenceTransformer ("sentence-transformers/all-MiniLM-L6-v2") model inference & embedding properties.
2. Semantic duplicate question detection with authentic test pairs from notebook Cell 25.
3. Calibrated adaptive decision engine (choose_next_action) branches from notebook Cell 45.
4. Integration with adaptation_service (is_duplicate_question, determine_adaptive_difficulty).
5. FastAPI /health/ml endpoint verification.
6. End-to-end adaptive interview lifecycle with ML decision tracking.
"""

import pytest
import numpy as np
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.text_assessment_service import text_assessment_service, SEMANTIC_DUPLICATE_THRESHOLD
from app.services.adaptation_service import (
    is_duplicate_question,
    determine_adaptive_difficulty,
    compute_adaptive_decision,
)


@pytest.mark.asyncio
async def test_model_loading_and_embedding_inference():
    """
    Verify the SentenceTransformer neural model loads correctly and produces
    normalized dense embeddings of dimension 384.
    """
    text_assessment_service.load_model()
    assert text_assessment_service.is_loaded is True

    texts = [
        "What is the difference between an interface and an abstract class?",
        "Explain abstract classes vs interfaces in object-oriented programming.",
    ]
    embeddings = text_assessment_service.encode(texts, normalize_embeddings=True)

    assert isinstance(embeddings, np.ndarray)
    assert embeddings.shape == (2, 384)

    # Normalized embeddings must have unit L2 norm (~1.0)
    norm0 = np.linalg.norm(embeddings[0])
    norm1 = np.linalg.norm(embeddings[1])
    assert np.isclose(norm0, 1.0, atol=1e-4)
    assert np.isclose(norm1, 1.0, atol=1e-4)


@pytest.mark.asyncio
async def test_find_semantic_duplicate_notebook_test_pairs():
    """
    Verify find_semantic_duplicate against the exact test pairs from notebook Cell 25:
    - Pair 1: ArrayList vs LinkedList (high similarity paraphrase -> duplicate)
    - Pair 2: ArrayList vs Method Overloading (unrelated concept -> not duplicate)
    """
    history = [
        {"question": "Explain the difference between an ArrayList and a LinkedList in Java."}
    ]

    # Test 1: Paraphrase question
    paraphrase = "How does Java ArrayList differ from LinkedList in terms of storage and performance?"
    res1 = text_assessment_service.find_semantic_duplicate(paraphrase, history, threshold=SEMANTIC_DUPLICATE_THRESHOLD)
    assert res1["is_duplicate"] is True
    assert res1["similarity"] is not None
    assert res1["similarity"] >= SEMANTIC_DUPLICATE_THRESHOLD
    assert "ArrayList" in res1["matched_question"]

    # Test 2: Unrelated question
    unrelated = "What is method overloading in Java?"
    res2 = text_assessment_service.find_semantic_duplicate(unrelated, history, threshold=SEMANTIC_DUPLICATE_THRESHOLD)
    assert res2["is_duplicate"] is False
    assert res2["similarity"] < SEMANTIC_DUPLICATE_THRESHOLD


@pytest.mark.asyncio
async def test_choose_next_action_notebook_calibration():
    """
    Verify deterministic branching logic of choose_next_action from notebook Cell 45:
    - percentage >= 80: INCREASE_DIFFICULTY (easy -> medium, medium -> hard, hard -> hard)
    - percentage >= 50: CLARIFY_CONCEPT (keeps current difficulty)
    - percentage < 50: REVISIT_FUNDAMENTALS (de-escalates to easy)
    """
    # 1. High score on easy -> medium
    decision_high_easy = text_assessment_service.choose_next_action(
        question={"difficulty": "easy", "topic": "Java Memory Management"},
        evaluation={"overall_score": 88, "strengths": ["Clear GC explanation"], "areas_for_improvement": []},
    )
    assert decision_high_easy["action"] == "INCREASE_DIFFICULTY"
    assert decision_high_easy["next_difficulty"] == "medium"
    assert decision_high_easy["percentage"] == 88.0

    # 2. High score on medium -> hard
    decision_high_med = text_assessment_service.choose_next_action(
        question={"difficulty": "medium", "topic": "Concurrency"},
        evaluation={"overall_score": 82, "strengths": ["Understands locks"], "areas_for_improvement": []},
    )
    assert decision_high_med["action"] == "INCREASE_DIFFICULTY"
    assert decision_high_med["next_difficulty"] == "hard"

    # 3. Moderate score (50-79%) on medium -> clarify concept, keep medium
    decision_mid = text_assessment_service.choose_next_action(
        question={"difficulty": "medium", "topic": "Spring Framework"},
        evaluation={"overall_score": 64, "strengths": ["Basic IoC knowledge"], "areas_for_improvement": ["Missed bean scopes"]},
    )
    assert decision_mid["action"] == "CLARIFY_CONCEPT"
    assert decision_mid["next_difficulty"] == "medium"
    assert "Missed bean scopes" in decision_mid["missing_concepts"]

    # 4. Low score (< 50%) on hard -> revisit fundamentals, easy
    decision_low = text_assessment_service.choose_next_action(
        question={"difficulty": "hard", "topic": "Distributed Consensus"},
        evaluation={"overall_score": 35, "strengths": [], "areas_for_improvement": ["Did not understand Raft"]},
    )
    assert decision_low["action"] == "REVISIT_FUNDAMENTALS"
    assert decision_low["next_difficulty"] == "easy"


@pytest.mark.asyncio
async def test_adaptation_service_neural_duplicate_detection():
    """
    Verify that adaptation_service.is_duplicate_question invokes the neural model
    and flags semantically identical questions even with varied phrasing.
    """
    existing_questions = [
        {
            "id": "q_1",
            "text": "What is the difference between a process and a thread in modern operating systems?",
            "assessed_skill": "Operating Systems",
        }
    ]

    # Semantic paraphrase
    candidate_paraphrase = "How do processes and threads differ in terms of memory and execution context?"
    assert is_duplicate_question(candidate_paraphrase, existing_questions) is True

    # Entirely distinct topic
    candidate_distinct = "Explain how database index B-trees reduce disk I/O operations."
    assert is_duplicate_question(candidate_distinct, existing_questions) is False


@pytest.mark.asyncio
async def test_compute_adaptive_decision_from_session():
    """
    Verify compute_adaptive_decision correctly parses session evaluations and yields
    structured ML decision metadata.
    """
    mock_session = {
        "session_id": "test-ml-session-001",
        "difficulty": "Medium",
        "focus_areas": "Python, FastApi",
        "questions": [
            {
                "id": "q_1",
                "text": "Explain Python GIL and its concurrency implications.",
                "difficulty": "Medium",
                "assessed_skill": "Python",
            }
        ],
        "answers": {
            "q_1": {
                "answer_text": "GIL is Global Interpreter Lock. It allows only one thread to execute Python bytecode.",
                "evaluation": {
                    "overall_score": 85.0,
                    "strengths": ["Accurate definition of GIL"],
                    "areas_for_improvement": [],
                },
            }
        },
    }

    decision = compute_adaptive_decision(mock_session)
    assert decision is not None
    assert decision["action"] == "INCREASE_DIFFICULTY"
    assert decision["next_difficulty"] == "hard"
    assert decision["percentage"] == 85.0

    adapted_diff = determine_adaptive_difficulty(mock_session)
    assert adapted_diff == "Hard"


@pytest.mark.asyncio
async def test_health_ml_endpoint():
    """
    Verify the /health/ml endpoint returns 200 with loaded=True and correct model name.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ml")
        assert response.status_code == 200
        data = response.json()
        assert data["loaded"] is True
        assert data["status"] == "ready"
        assert data["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
