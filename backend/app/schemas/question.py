import uuid

from pydantic import BaseModel, ConfigDict, Field


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sector_id: uuid.UUID | None = None
    criteria: str
    text: str
    is_system: bool
    user_id: uuid.UUID | None = None
    enabled: bool = True
    custom_text: str | None = None


class QuestionCreate(BaseModel):
    sector_id: uuid.UUID | None = None
    criteria: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1)


class QuestionUpdate(BaseModel):
    criteria: str | None = Field(default=None, min_length=1, max_length=255)
    text: str | None = Field(default=None, min_length=1)
    sector_id: uuid.UUID | None = None
    enabled: bool | None = None


class QuestionToggle(BaseModel):
    enabled: bool
