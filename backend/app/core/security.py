import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
import re
from typing import Any, Callable, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.database import db_manager

logger = logging.getLogger("interviewiq.security")

# Role definitions
ROLE_CANDIDATE = "candidate"
ROLE_REVIEWER = "reviewer"
ROLE_ADMIN = "admin"
VALID_ROLES = {ROLE_CANDIDATE, ROLE_REVIEWER, ROLE_ADMIN}

# HTTP Bearer scheme
http_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash password with salted PBKDF2-HMAC-SHA256 (100,000 iterations)."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()
    return f"{salt}:{key}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verify password against salted PBKDF2 hash using constant-time comparison."""
    try:
        parts = password_hash.split(":")
        if len(parts) != 2:
            return False
        salt, expected_key = parts
        computed_key = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


# Verified user directory (no plaintext passwords)
# Supports authenticated role issuance and demonstration
USERS_DB: Dict[str, Dict[str, Any]] = {
    "candidate_demo": {
        "user_id": "usr_cand_01",
        "username": "candidate_demo",
        "email": "candidate@interviewiq.com",
        "name": "Alex Mercer (Candidate)",
        "role": ROLE_CANDIDATE,
        "password_hash": "6957a7b9248576dc3ccc513d8ad91d2c:8c6f3dfb5a6b7155dc5b4c5c887fe38745cf7e2843f5359c8f87357c0db6c83e",
    },
    "reviewer_demo": {
        "user_id": "usr_rev_01",
        "username": "reviewer_demo",
        "email": "reviewer@interviewiq.com",
        "name": "Sarah Chen (Senior Reviewer)",
        "role": ROLE_REVIEWER,
        "password_hash": "43bb4438b24edb3f3a526983dd8858ac:545ddf810214581010f44c2328e9ab5fc0c1756332a5ffbdf3a2c68ab362a7d6",
    },
    "admin_demo": {
        "user_id": "usr_adm_01",
        "username": "admin_demo",
        "email": "admin@interviewiq.com",
        "name": "System Administrator",
        "role": ROLE_ADMIN,
        "password_hash": "1bebef4d56f531ff7d1aacf8a4f6c7c8:6f72b1712277e65512416ba5cfe0601afde5657c7fd070d5a2753e95651f119a",
    },
}


async def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate username or email and password against verified accounts in memory and MongoDB Atlas."""
    clean_id = username.strip()
    clean_lower = clean_id.lower()

    # 1. Exact or case-insensitive username or email match from in-memory USERS_DB
    user = USERS_DB.get(clean_id)
    if not user:
        for u in USERS_DB.values():
            if u.get("username", "").lower() == clean_lower:
                user = u
                break
            if u.get("email") and u.get("email", "").lower() == clean_lower:
                user = u
                break

    if user and verify_password(password, user.get("password_hash", "")):
        return user

    # 2. Case-insensitive username or email match from MongoDB Atlas
    if settings.is_mongodb_configured:
        try:
            db = db_manager.get_database()
            query = {
                "$or": [
                    {"username": {"$regex": f"^{re.escape(clean_id)}$", "$options": "i"}},
                    {"email": {"$regex": f"^{re.escape(clean_id)}$", "$options": "i"}},
                ]
            }
            doc = await db["users"].find_one(query)
            if doc and doc.get("password_hash"):
                if verify_password(password, doc["password_hash"]):
                    role = doc.get("role", ROLE_CANDIDATE)
                    if role not in VALID_ROLES:
                        role = ROLE_CANDIDATE
                    user_dict = {
                        "user_id": doc.get("user_id", f"usr_{doc.get('username')}"),
                        "username": doc.get("username", clean_id),
                        "name": doc.get("name", doc.get("username", "User")),
                        "email": doc.get("email"),
                        "role": role,
                        "password_hash": doc["password_hash"],
                    }
                    # Populate in-memory cache for fast session access
                    USERS_DB[user_dict["username"]] = user_dict
                    return user_dict
                return None
        except Exception as exc:
            logger.error("MongoDB Atlas error during user authentication: %s", type(exc).__name__)

    return None



def create_access_token(
    user_id: str,
    role: str,
    name: str,
    expires_delta: Optional[timedelta] = None,
    username: Optional[str] = None,
) -> str:
    """Create a signed JWT access token containing subject, role, and expiration."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {VALID_ROLES}")

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "role": role,
        "name": name,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    if username:
        payload["username"] = username

    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token signature and expiration."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role"]},
        )
        return payload
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please authenticate again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature or payload.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """
    FastAPI dependency requiring a valid Bearer token.
    Returns authenticated user dict with user_id, role, name.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token in Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(auth.credentials)
    user_id = payload.get("sub")
    role = payload.get("role")

    if not user_id or not role or role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims: missing valid subject or role.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "user_id": user_id,
        "role": role,
        "name": payload.get("name", "User"),
        "username": payload.get("username"),
    }


async def get_optional_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Optional[Dict[str, Any]]:
    """FastAPI dependency for optional authentication. Returns user if token is valid, otherwise None."""
    if not auth or not auth.credentials:
        return None
    try:
        payload = decode_access_token(auth.credentials)
        return {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "name": payload.get("name"),
            "username": payload.get("username"),
        }
    except Exception:
        return None


def require_role(allowed_roles: List[str]) -> Callable:
    """
    Dependency factory to enforce role-based access control.
    Returns 401 if unauthenticated, 403 if authenticated user lacks required role.
    """
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in allowed_roles:
            logger.warning(
                "Access denied for user %s with role '%s'. Required roles: %s",
                current_user.get("user_id"),
                user_role,
                allowed_roles,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access forbidden: role '{user_role}' lacks permission for this action. "
                    f"Authorized roles: {', '.join(allowed_roles)}."
                ),
            )
        return current_user

    return role_checker
