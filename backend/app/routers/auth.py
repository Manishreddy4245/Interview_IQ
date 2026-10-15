import logging
import uuid
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.database import db_manager
from app.core.security import (
    ROLE_CANDIDATE,
    ROLE_REVIEWER,
    ROLE_ADMIN,
    USERS_DB,
    authenticate_user,
    create_access_token,
    get_current_user,
    hash_password,
)
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserProfile

logger = logging.getLogger("interviewiq.auth_router")

router = APIRouter(prefix="/api/auth", tags=["Authentication & RBAC"])

ROLE_PERMISSIONS: Dict[str, List[str]] = {
    ROLE_CANDIDATE: [
        "interview:create",
        "interview:answer",
        "interview:evaluate",
        "interview:explain_integrity",
        "resume:analyze",
        "communication:coach",
        "report:view_own",
    ],
    ROLE_REVIEWER: [
        "report:view_all",
        "decision:view_overview",
        "decision:review_dossier",
        "integrity:audit_review",
        "integrity:record_decision",
        "communication:coach",
    ],
    ROLE_ADMIN: [
        "*",
    ],
}


class SwitchRoleDemoRequest(BaseModel):
    """Request to generate signed token for one of the valid demo roles."""
    role: str = Field(..., description="Role to switch to: candidate, reviewer, or admin")


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and Issue JWT Access Token",
    description="Validates credentials using salted PBKDF2 hashes and issues a cryptographically signed HMAC-SHA256 JWT.",
)
async def login_for_access_token(payload: LoginRequest) -> TokenResponse:
    """Issue JWT token with role claims upon valid credentials."""
    user = authenticate_user(payload.username, payload.password)
    if not user:
        logger.warning("Failed login attempt for username: %s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        user_id=user["user_id"],
        role=user["role"],
        name=user["name"],
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user["user_id"],
        username=user["username"],
        name=user["name"],
        role=user["role"],
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register New Candidate Account",
    description="Registers a new candidate user. Role is strictly assigned as 'candidate' to prevent privilege escalation.",
)
async def register_candidate(payload: RegisterRequest) -> TokenResponse:
    """Register a new candidate and issue an initial signed JWT access token."""
    clean_username = payload.username.strip()
    if len(clean_username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long.",
        )

    # Check for disallowed characters in username
    if not clean_username.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username may only contain letters, numbers, underscores, and hyphens.",
        )

    # Check if username or email already exists in USERS_DB (case-insensitive)
    for existing_user in USERS_DB.values():
        if existing_user.get("username", "").lower() == clean_username.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{clean_username}' is already registered.",
            )
        if payload.email and existing_user.get("email"):
            if existing_user["email"].lower() == payload.email.strip().lower():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{payload.email.strip()}' is already registered.",
                )

    # Check MongoDB if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            existing_doc = await db["users"].find_one({"username": {"$regex": f"^{clean_username}$", "$options": "i"}})
            if existing_doc:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Username '{clean_username}' is already registered.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("MongoDB lookup warning during registration: %s", type(exc).__name__)

    # CRITICAL: Strict Role Enforcement.
    # Candidate registration MUST NEVER allow selecting Reviewer or Admin privileges.
    # Reviewer/Admin privileges can only be assigned through an authorized backend process.
    assigned_role = ROLE_CANDIDATE
    user_id = f"usr_cand_{uuid.uuid4().hex[:8]}"
    pwd_hash = hash_password(payload.password)

    new_user = {
        "user_id": user_id,
        "username": clean_username,
        "name": payload.name.strip(),
        "email": payload.email.strip().lower() if payload.email else None,
        "role": assigned_role,
        "password_hash": pwd_hash,
    }

    # Store in memory
    USERS_DB[clean_username] = new_user

    # Store in MongoDB if configured
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            await db["users"].insert_one({
                "user_id": user_id,
                "username": clean_username,
                "name": payload.name.strip(),
                "email": payload.email.strip().lower() if payload.email else None,
                "role": assigned_role,
                "password_hash": pwd_hash,
            })
        except Exception as exc:
            logger.warning("MongoDB insert warning during registration: %s", type(exc).__name__)

    logger.info("Successfully registered candidate user: %s (id: %s)", clean_username, user_id)

    token = create_access_token(
        user_id=user_id,
        role=assigned_role,
        name=payload.name.strip(),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user_id,
        username=clean_username,
        name=payload.name.strip(),
        role=assigned_role,
    )


@router.post(
    "/demo-token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Issue Signed Demo Role Token",
    description="Generates a genuine signed JWT token for the requested demo role (candidate, reviewer, admin) for live browser inspection and testing.",
)
async def get_demo_role_token(payload: SwitchRoleDemoRequest) -> TokenResponse:
    """Issue a signed JWT for the requested demo role."""
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo role token issuance is disabled in production environments.",
        )

    target_role = payload.role.strip().lower()
    matching_user = None
    for u in USERS_DB.values():
        if u["role"] == target_role:
            matching_user = u
            break

    if not matching_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{target_role}'. Valid roles: candidate, reviewer, admin.",
        )

    token = create_access_token(
        user_id=matching_user["user_id"],
        role=matching_user["role"],
        name=matching_user["name"],
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=matching_user["user_id"],
        username=matching_user["username"],
        name=matching_user["name"],
        role=matching_user["role"],
    )


@router.get(
    "/me",
    response_model=UserProfile,
    status_code=status.HTTP_200_OK,
    summary="Get Current Authenticated User Profile",
    description="Decodes caller's JWT Bearer token and returns active permissions and role.",
)
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> UserProfile:
    """Return user profile and active permissions for the verified token."""
    role = current_user.get("role", ROLE_CANDIDATE)
    permissions = ROLE_PERMISSIONS.get(role, [])

    # Find username from USERS_DB if present
    username = "unknown"
    for u in USERS_DB.values():
        if u["user_id"] == current_user.get("user_id"):
            username = u["username"]
            break

    return UserProfile(
        user_id=current_user["user_id"],
        username=username,
        name=current_user.get("name", "User"),
        role=role,
        permissions=permissions,
    )
