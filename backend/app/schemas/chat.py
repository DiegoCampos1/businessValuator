import uuid

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: uuid.UUID | None = None


class Citation(BaseModel):
    source: str
    title: str | None = None
    url: str


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None = None
    created_at: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[Citation] | None = None
    created_at: str
