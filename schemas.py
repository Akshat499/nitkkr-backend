from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserSignup(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Optional[str] = "student"  # student | admin | teacher

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str

class ResultResponse(BaseModel):
    id: int
    degree: str
    branch: str
    semester: int
    year: int
    type: str
    original_filename: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

class QueryRequest(BaseModel):
    question: str

class UnifiedChatRequest(BaseModel):
    question: str
    context: Optional[str] = None  # Optional extra context (e.g. current page, branch)
