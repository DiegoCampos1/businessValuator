import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    provider: str = Field(pattern="^(openai|deepseek|other)$")
    api_key: str


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    key_hint: str
    created_at: datetime
    updated_at: datetime
