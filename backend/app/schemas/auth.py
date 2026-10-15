from typing import List, Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials payload for JWT authentication (username or email)."""
    username: str = Field(..., min_length=2, max_length=100, description="Username or email address")
    password: str = Field(..., min_length=4, max_length=100, description="Password")


class RegisterRequest(BaseModel):
    """Payload for candidate account registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, max_length=100, description="Password")
    name: str = Field(..., min_length=2, max_length=100, description="Full Name")
    email: Optional[str] = Field(None, description="Optional email address")
    role: Optional[str] = Field(None, description="Requested role (never allows privilege escalation)")



class TokenResponse(BaseModel):
    """JWT Token response payload."""
    access_token: str = Field(..., description="Signed JWT Bearer access token")
    token_type: str = Field(default="bearer", description="Token scheme")
    expires_in: int = Field(..., description="Seconds until expiration")
    user_id: str = Field(..., description="Authenticated user ID")
    username: str = Field(..., description="Authenticated username")
    name: str = Field(..., description="User display name")
    role: str = Field(..., description="Assigned role: candidate, reviewer, or admin")


class UserProfile(BaseModel):
    """Authenticated user profile with active permissions."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    name: str = Field(..., description="Full Name")
    role: str = Field(..., description="User Role")
    permissions: List[str] = Field(default_factory=list, description="List of granted system permissions")
