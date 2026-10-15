"""
Text Assessment Machine Learning Service.
Direct refactor of the authentic Text_Assessment_Model.ipynb machine learning pipeline.

Responsibilities:
1. SentenceTransformer Neural Model ("sentence-transformers/all-MiniLM-L6-v2"):
   - Pre-warmed singleton loaded once at application startup.
   - Computes dense normalized sentence embeddings for candidate questions.
   - Computes pairwise cosine similarity matrices locally (zero API cost, fast inference).
   - Detects semantic duplicate questions using calibrated cosine similarity thresholds.
2. Calibrated Adaptive Decision Engine:
   - Evaluates performance percentages against rubric criteria.
   - Deterministically chooses next action (INCREASE_DIFFICULTY, CLARIFY_CONCEPT, REVISIT_FUNDAMENTALS).
   - Escalates/de-escalates difficulty based on candidate evidence.
3. Question Concept Metadata & Technical Accuracy Validation:
   - Extracts specific concept and tested angle.
   - Validates factual correctness and API premise integrity before issuance.
"""

import json
import logging
import math
from typing import Dict, Any, List, Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import settings
from app.core.groq_client import groq_manager

logger = logging.getLogger("interviewiq.text_assessment_service")

# Calibrated semantic duplicate threshold from notebook Cell 100
SEMANTIC_DUPLICATE_THRESHOLD = 0.78
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class TextAssessmentService:
    """
    Singleton service managing the SentenceTransformer neural model and
    adaptive decision logic refactored directly from Text_Assessment_Model.ipynb.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name
        self._similarity_model: Optional[SentenceTransformer] = None
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded and self._similarity_model is not None

    def load_model(self) -> None:
        """
        Load the pretrained SentenceTransformer model into memory at application startup.
        Separates model initialization from per-request inference.
        """
        if self._is_loaded and self._similarity_model is not None:
            return

        logger.info("Loading SentenceTransformer model '%s'...", self.model_name)
        try:
            self._similarity_model = SentenceTransformer(self.model_name)
            self._is_loaded = True
            logger.info("SentenceTransformer model '%s' loaded successfully.", self.model_name)
        except Exception as exc:
            logger.error("Failed to load SentenceTransformer model '%s': %s", self.model_name, str(exc))
            self._is_loaded = False
            raise

    def get_model(self) -> SentenceTransformer:
        """Retrieve the loaded SentenceTransformer model, loading lazily if necessary."""
        if not self._is_loaded or self._similarity_model is None:
            self.load_model()
        return self._similarity_model

    def encode(self, texts: List[str], normalize_embeddings: bool = True) -> np.ndarray:
        """Generate normalized embeddings for input texts using the local neural model."""
        model = self.get_model()
        return model.encode(texts, normalize_embeddings=normalize_embeddings)

    def find_semantic_duplicate(
        self,
        candidate_question: str,
        history: List[Any],
        threshold: float = SEMANTIC_DUPLICATE_THRESHOLD,
    ) -> Dict[str, Any]:
        """
        Exact implementation from Text_Assessment_Model.ipynb Cell 26:
        Encodes candidate question and history questions into dense vector embeddings,
        computes cosine similarity, and checks against the duplicate threshold.
        """
        if not candidate_question or not candidate_question.strip():
            return {
                "is_duplicate": False,
                "similarity": None,
                "matched_question": None,
            }

        history_questions: List[str] = []
        for item in history:
            if isinstance(item, dict):
                # Support both notebook format ("question") and backend format ("text")
                text = item.get("question") or item.get("text")
                if text and isinstance(text, str) and text.strip():
                    history_questions.append(text.strip())
            elif isinstance(item, str) and item.strip():
                history_questions.append(item.strip())
            elif hasattr(item, "text") and getattr(item, "text"):
                history_questions.append(str(getattr(item, "text")).strip())

        if not history_questions:
            return {
                "is_duplicate": False,
                "similarity": None,
                "matched_question": None,
            }

        model = self.get_model()

        candidate_embedding = model.encode(
            [candidate_question.strip()],
            normalize_embeddings=True,
        )

        history_embeddings = model.encode(
            history_questions,
            normalize_embeddings=True,
        )

        similarities = cosine_similarity(
            candidate_embedding,
            history_embeddings,
        )[0]

        best_index = int(similarities.argmax())
        best_score = float(similarities[best_index])

        return {
            "is_duplicate": best_score >= threshold,
            "similarity": round(best_score, 4),
            "matched_question": history_questions[best_index],
        }

    def choose_next_action(
        self,
        question: Any,
        evaluation: Any,
        asked_topics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Exact implementation from Text_Assessment_Model.ipynb Cell 45:
        Calculates percentage score against max marks and branches deterministically:
        - percentage >= 80: INCREASE_DIFFICULTY
        - percentage >= 50: CLARIFY_CONCEPT
        - percentage < 50: REVISIT_FUNDAMENTALS
        """
        asked_topics = asked_topics or []

        # Support Pydantic objects, dicts, or generic objects
        if hasattr(evaluation, "model_dump"):
            evaluation_dict = evaluation.model_dump()
        elif isinstance(evaluation, dict):
            evaluation_dict = evaluation
        else:
            try:
                evaluation_dict = vars(evaluation)
            except Exception:
                evaluation_dict = {}

        if hasattr(question, "model_dump"):
            question_dict = question.model_dump()
        elif isinstance(question, dict):
            question_dict = question
        else:
            try:
                question_dict = vars(question)
            except Exception:
                question_dict = {}

        # Extract score and max marks (support both notebook 'score' and backend 'overall_score')
        score = evaluation_dict.get("score")
        if score is None:
            score = evaluation_dict.get("overall_score", 0.0)
        score = float(score or 0.0)

        max_marks = float(evaluation_dict.get("max_marks", 100.0) or 100.0)
        percentage = (score / max_marks * 100.0) if max_marks > 0 else 0.0

        difficulty = str(question_dict.get("difficulty", "medium")).lower()

        if percentage >= 80.0:
            next_difficulty = {
                "easy": "medium",
                "medium": "hard",
                "hard": "hard",
            }.get(difficulty, "medium")
            action = "INCREASE_DIFFICULTY"
            reason = "Strong answer; test deeper understanding."
        elif percentage >= 50.0:
            next_difficulty = difficulty
            action = "CLARIFY_CONCEPT"
            reason = "Partial understanding; validate missing concepts."
        else:
            next_difficulty = "easy"
            action = "REVISIT_FUNDAMENTALS"
            reason = "Low score; check foundational understanding."

        current_topic = (
            question_dict.get("topic")
            or question_dict.get("assessed_skill")
            or "Unknown"
        )

        missing_concepts = (
            evaluation_dict.get("missing_concepts")
            or evaluation_dict.get("areas_for_improvement")
            or []
        )

        return {
            "action": action,
            "current_topic": current_topic,
            "next_difficulty": next_difficulty,
            "percentage": round(percentage, 2),
            "strengths": evaluation_dict.get("strengths", []),
            "missing_concepts": missing_concepts,
            "asked_topics": asked_topics,
            "reason": reason,
        }

    async def extract_question_metadata(
        self,
        question_text: str,
        topic: str,
    ) -> Dict[str, str]:
        """
        Implementation from Text_Assessment_Model.ipynb Cell 51:
        Extracts specific concept (2-5 words) and angle (3-8 words) via LLM.
        """
        prompt = f"""
Analyze this interview question.

Question: {question_text}
Broad topic: {topic}

Return JSON with exactly these keys:
- concept: the specific concept being tested (2-5 words)
- angle: the exact knowledge angle being tested (3-8 words)

Examples:
Question: What is a resource leak and why is it harmful?
Output: {{"concept": "Resource leaks", "angle": "Definition and consequences"}}

Question: In what order are try-with-resources closed?
Output: {{"concept": "Try-with-resources", "angle": "Reverse resource closing order"}}

Use the actual question. Do not invent unrelated concepts.
"""
        try:
            raw_output = await groq_manager.execute_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=256,
            )
            data = json.loads(raw_output)
            return {
                "concept": str(data.get("concept", topic)).strip(),
                "angle": str(data.get("angle", "Core principles")).strip(),
            }
        except Exception as exc:
            logger.warning("Failed to extract question metadata: %s", str(exc))
            return {
                "concept": topic.strip(),
                "angle": "Core concepts and trade-offs",
            }

    async def validate_question_technical_accuracy(
        self,
        question_text: str,
        role: str = "Software Developer",
    ) -> Dict[str, Any]:
        """
        Implementation from Text_Assessment_Model.ipynb Cell 95:
        Reviews generated question for technical accuracy, factual errors,
        and misleading premises.
        """
        prompt = f"""
You are a strict technical reviewer for {role} interview questions.

Review this interview question for technical correctness:

{question_text}

Check whether it:
1. Contains any false or misleading technical premise.
2. Describes APIs, behaviors, algorithms, or language semantics correctly.
3. Requests something impossible or incorrectly described.
4. Is clear and answerable.

Return JSON with exactly these fields:
{{
  "is_accurate": true,
  "issues": [],
  "explanation": "Short explanation"
}}

Set is_accurate to false if the question contains a factual error or a misleading premise.
Do not reject a question merely because it discusses a difficult concept.
"""
        try:
            raw_output = await groq_manager.execute_chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": f"You review technical interview questions for factual correctness.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=350,
            )
            data = json.loads(raw_output)
            return {
                "is_accurate": bool(data.get("is_accurate", True)),
                "issues": list(data.get("issues", [])),
                "explanation": str(data.get("explanation", "")),
            }
        except Exception as exc:
            logger.warning("Technical accuracy validation error: %s", str(exc))
            return {
                "is_accurate": True,
                "issues": [],
                "explanation": "Validation bypassed due to transient error.",
            }


# Global singleton instance
text_assessment_service = TextAssessmentService()
