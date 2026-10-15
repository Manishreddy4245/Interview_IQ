import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.security import get_optional_user, ROLE_CANDIDATE
from app.schemas.resume import (
    ResumeAnalysisResult,
    StartInterviewFromResumeRequest,
    UpdateExtractedSkillsRequest,
    SelectTargetRoleRequest,
)
from app.schemas.interview import InterviewSessionResponse
from app.services.pdf_extractor import extract_text_from_pdf_upload
from app.services.skill_gap_service import analyze_resume_and_gaps
from app.services.resume_service import (
    store_resume_analysis,
    get_resume_analysis,
    get_student_latest_resume_analysis,
    update_resume_skills,
    update_resume_target_role,
    create_interview_from_resume_analysis,
)

logger = logging.getLogger("interviewiq.resume_router")

router = APIRouter(prefix="/api/resume", tags=["Resume Intelligence"])


@router.post(
    "/analyze",
    response_model=ResumeAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Upload PDF resume and perform role skill-gap analysis",
)
async def analyze_resume(
    file: UploadFile = File(..., description="PDF resume file (.pdf)"),
    target_role: str = Form(..., description="Target job title or role"),
    experience_level: str = Form("Mid-Level", description="Candidate target level"),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> ResumeAnalysisResult:
    """
    Upload and evaluate candidate resume:
    1. Validates and extracts text from the uploaded PDF document.
    2. Identifies demonstrated skills, unevidenced skills, gaps, and validation areas using Groq.
    3. Formulates personalized interview questions linked to specific resume skills.
    4. Persists the analysis against the authenticated student's account.
    """
    clean_role = target_role.strip()
    if not clean_role or len(clean_role) < 2 or len(clean_role) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Target role must be between 2 and 100 characters.",
        )

    clean_level = experience_level.strip() or "Mid-Level"
    owner_id = current_user.get("user_id") if current_user else None

    # Step 1: Extract PDF text
    extracted_text = await extract_text_from_pdf_upload(file)

    # Step 2: Groq skill-gap analysis
    ai_output = await analyze_resume_and_gaps(
        resume_text=extracted_text,
        target_role=clean_role,
        experience_level=clean_level,
    )

    # Step 3: Persistence with owner association
    result = await store_resume_analysis(
        target_role=clean_role,
        experience_level=clean_level,
        ai_output=ai_output,
        owner_id=owner_id,
        raw_resume_text=extracted_text,
    )

    return result


@router.get(
    "/my-resume",
    response_model=ResumeAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Get Authenticated Student Latest Resume Analysis",
)
async def get_my_resume(
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> ResumeAnalysisResult:
    """Retrieve the latest resume analysis belonging to the authenticated student."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to view your student resume profile.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = current_user.get("user_id")
    analysis = await get_student_latest_resume_analysis(user_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uploaded resume found for your account. Please upload your resume to begin preparation.",
        )

    return analysis


@router.put(
    "/{analysis_id}/skills",
    response_model=ResumeAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Correct and Update Extracted Resume Skills",
)
async def update_extracted_skills(
    analysis_id: str,
    payload: UpdateExtractedSkillsRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> ResumeAnalysisResult:
    """Let the student correct extraction mistakes before proceeding."""
    user_id = current_user.get("user_id") if current_user else None
    try:
        updated = await update_resume_skills(analysis_id, payload.skills, user_id=user_id)
        return updated
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.post(
    "/{analysis_id}/select-role",
    response_model=ResumeAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Select Target Job Role for Resume Analysis",
)
async def select_target_role(
    analysis_id: str,
    payload: SelectTargetRoleRequest,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> ResumeAnalysisResult:
    """Update target job role and calculate initial skill-gap analysis against standardized competencies."""
    user_id = current_user.get("user_id") if current_user else None
    try:
        updated = await update_resume_target_role(
            analysis_id=analysis_id,
            target_role=payload.target_role,
            experience_level=payload.experience_level or "Mid-Level",
            user_id=user_id,
        )
        return updated
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))


@router.get(
    "/{analysis_id}",
    response_model=ResumeAnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an existing resume skill-gap analysis",
)
async def get_analysis(
    analysis_id: str,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> ResumeAnalysisResult:
    """Retrieve an existing resume analysis by ID with strict student ownership enforcement."""
    analysis = await get_resume_analysis(analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume analysis '{analysis_id}' was not found.",
        )

    # RBAC & Ownership: candidates can only access their own analyses
    if analysis.owner_id and current_user:
        if current_user.get("role") == ROLE_CANDIDATE and current_user.get("user_id") != analysis.owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot view another candidate's resume analysis.",
            )

    return analysis


@router.post(
    "/{analysis_id}/start-interview",
    response_model=InterviewSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start an active interview session from personalized resume questions",
)
async def start_interview_from_analysis(
    analysis_id: str,
    request: Optional[StartInterviewFromResumeRequest] = None,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
) -> InterviewSessionResponse:
    """
    Convert personalized questions or prioritized gaps from a resume analysis into an active interview session.
    Enforces student ownership and starts a genuinely sequential adaptive interview.
    """
    analysis = await get_resume_analysis(analysis_id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume analysis '{analysis_id}' was not found.",
        )

    caller_id = current_user.get("user_id") if current_user else None
    if analysis.owner_id and current_user:
        if current_user.get("role") == ROLE_CANDIDATE and caller_id != analysis.owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You cannot start an interview for another candidate's resume.",
            )

    adaptive = request.adaptive if request else False
    difficulty = request.difficulty if request else None
    question_count = request.question_count if request else None
    interview_mode = (request.interview_mode if request and request.interview_mode else "VERBAL").upper()

    session = await create_interview_from_resume_analysis(
        analysis_id=analysis_id,
        adaptive=adaptive,
        difficulty=difficulty,
        question_count=question_count,
        owner_id=caller_id or analysis.owner_id,
        interview_mode=interview_mode,
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to initialize interview session for analysis '{analysis_id}'.",
        )
    return session
