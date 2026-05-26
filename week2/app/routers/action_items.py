# Exercises 3–4 (generated/refactored): extract endpoints incl. POST /extract-llm.
from __future__ import annotations

from collections.abc import Callable
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import db
from ..schemas import (
    ActionItemResponse,
    ActionItemSummary,
    ExtractActionItemsRequest,
    ExtractActionItemsResponse,
    MarkActionItemDoneRequest,
    MarkActionItemDoneResponse,
)
from ..services.extract import extract_action_items, extract_action_items_llm

router = APIRouter(prefix="/action-items", tags=["action-items"])


def _extract_and_persist(
    payload: ExtractActionItemsRequest,
    extractor: Callable[[str], list[str]],
) -> ExtractActionItemsResponse:
    note_id: Optional[int] = None
    if payload.save_note:
        note = db.insert_note(payload.text)
        note_id = note.id

    items = extractor(payload.text)
    created = db.insert_action_items(items, note_id=note_id)
    return ExtractActionItemsResponse(
        note_id=note_id,
        items=[ActionItemSummary(id=item.id, text=item.text) for item in created],
    )


@router.post("/extract", response_model=ExtractActionItemsResponse)
def extract(payload: ExtractActionItemsRequest) -> ExtractActionItemsResponse:
    return _extract_and_persist(payload, extract_action_items)


@router.post("/extract-llm", response_model=ExtractActionItemsResponse)
def extract_llm(payload: ExtractActionItemsRequest) -> ExtractActionItemsResponse:
    try:
        return _extract_and_persist(payload, extract_action_items_llm)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM extraction failed. Ensure Ollama is running: {exc}",
        ) from exc


@router.get("", response_model=list[ActionItemResponse])
def list_all(note_id: Optional[int] = Query(default=None)) -> list[ActionItemResponse]:
    rows = db.list_action_items(note_id=note_id)
    return [
        ActionItemResponse.model_validate(row, from_attributes=True) for row in rows
    ]


@router.post("/{action_item_id}/done", response_model=MarkActionItemDoneResponse)
def mark_done(
    action_item_id: int, payload: MarkActionItemDoneRequest
) -> MarkActionItemDoneResponse:
    updated = db.mark_action_item_done(action_item_id, payload.done)
    return MarkActionItemDoneResponse(id=updated.id, done=updated.done)
