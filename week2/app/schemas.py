# Exercise 3 (generated): Pydantic API request/response contracts.
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        return value.strip()


class NoteResponse(BaseModel):
    id: int
    content: str
    created_at: str


class ExtractActionItemsRequest(BaseModel):
    text: str = Field(..., min_length=1)
    save_note: bool = False

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ActionItemSummary(BaseModel):
    id: int
    text: str


class ExtractActionItemsResponse(BaseModel):
    note_id: int | None
    items: list[ActionItemSummary]


class ActionItemResponse(BaseModel):
    id: int
    note_id: int | None
    text: str
    done: bool
    created_at: str


class MarkActionItemDoneRequest(BaseModel):
    done: bool = True


class MarkActionItemDoneResponse(BaseModel):
    id: int
    done: bool
