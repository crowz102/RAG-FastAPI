from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    username: str
    password: str
    email: EmailStr

class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str] = None
    is_admin: bool = False

class Token(BaseModel):
    access_token: str
    token_type: str
    is_admin: bool = False


class ChatRequest(BaseModel):
    question: str
    session_id: str = "default"
    top_k: int = 5
    filenames: Optional[list[str]] = None


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    sources: list[str]


class HistoryItem(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryItem]


class IngestResponse(BaseModel):
    message: str
    chunks_stored: int
    filename: str