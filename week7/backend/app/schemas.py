from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class NoteRead(BaseModel):
    id: int
    title: str
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class NotePatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "NotePatch":
        if self.title is None and self.content is None:
            raise ValueError("At least one of 'title' or 'content' must be provided")
        return self


class ActionItemCreate(BaseModel):
    description: str = Field(..., min_length=1)


class ActionItemRead(BaseModel):
    id: int
    description: str
    completed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ActionItemPatch(BaseModel):
    description: str | None = Field(None, min_length=1)
    completed: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "ActionItemPatch":
        if self.description is None and self.completed is None:
            raise ValueError("At least one of 'description' or 'completed' must be provided")
        return self


