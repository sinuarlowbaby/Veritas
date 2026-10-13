from typing import List, Optional
from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="Unique username")
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="Valid email address")
    password: str = Field(..., min_length=6, description="Password (at least 6 characters)")


class UserLoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=3, description="Username or email address")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    created_at: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class HistorySyncRequest(BaseModel):
    job_ids: List[str] = Field(
        default_factory=list,
        description="List of unauthenticated guest verification job IDs to persist to database user account.",
    )
