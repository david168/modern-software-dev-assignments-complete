# Exercises 3–4 (generated/refactored): notes API incl. GET /notes list endpoint.
from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..schemas import NoteCreate, NoteResponse

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=list[NoteResponse])
def list_all_notes() -> list[NoteResponse]:
    notes = db.list_notes()
    return [NoteResponse.model_validate(note, from_attributes=True) for note in notes]


@router.post("", response_model=NoteResponse)
def create_note(payload: NoteCreate) -> NoteResponse:
    note = db.insert_note(payload.content)
    return NoteResponse.model_validate(note, from_attributes=True)


@router.get("/{note_id}", response_model=NoteResponse)
def get_single_note(note_id: int) -> NoteResponse:
    note = db.require_note(note_id)
    return NoteResponse.model_validate(note, from_attributes=True)
