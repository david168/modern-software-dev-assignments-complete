# Exercise 3 (generated): domain exceptions for API error handling.
from __future__ import annotations


class AppError(Exception):
    """Base exception for application domain errors."""


class NoteNotFoundError(AppError):
    def __init__(self, note_id: int) -> None:
        self.note_id = note_id
        super().__init__(f"Note {note_id} not found")


class ActionItemNotFoundError(AppError):
    def __init__(self, action_item_id: int) -> None:
        self.action_item_id = action_item_id
        super().__init__(f"Action item {action_item_id} not found")
