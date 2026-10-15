import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

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


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate username or email and password against verified accounts."""
    clean_id = username.strip()
    # 1. Exact username match
    user = USERS_DB.get(clean_id)
    # 2. Case-insensitive username or email match
    if not user:
        clean_lower = clean_id.lower()
        for u in USERS_DB.values():
            if u.get("username", "").lower() == clean_lower:
                user = u
                break
            if u.get("email") and u.get("email", "").lower() == clean_lower:
                user = u
                break
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user



def create_access_token(
    user_id: str,
    role: str,
    name: str,
    expires_delta: Optional[timedelta] = None,
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
