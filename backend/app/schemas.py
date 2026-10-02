"""Request and response shapes. FastAPI uses these for validation and for the API docs."""
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.-]+$",
                          examples=["rakib"])
    password: str = Field(..., min_length=6, max_length=100, examples=["secret123"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, examples=["What are the library opening hours?"])
    session_id: str | None = Field(None, description="Leave empty to start a new chat.")


class Source(BaseModel):
    source: str
    similarity: float


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    found: bool = Field(..., description="False when the answer is not in the knowledge base.")
    type: str = Field(..., description="answer | not_found | small_talk")
    sources: list[Source]
    search_query: str | None = Field(None, description="The question used for searching (after rewriting).")


class SessionOut(BaseModel):
    id: str
    title: str
    created_at: str


class MessageOut(BaseModel):
    role: str
    content: str
    sources: list[Source] = []
    found: bool = True
    created_at: str


class UrlRequest(BaseModel):
    url: str = Field(..., pattern=r"^https?://", examples=["https://en.wikipedia.org/wiki/Retrieval-augmented_generation"])


class DocumentOut(BaseModel):
    id: str
    name: str
    source_type: str
    chunks: int
    words: int
    added_by: str | None
    created_at: str


class UploadResult(BaseModel):
    added: list[DocumentOut]
    errors: list[str]


class StatsOut(BaseModel):
    documents: int
    chunks: int
    users: int
    chats: int
    messages: int
    model: str
