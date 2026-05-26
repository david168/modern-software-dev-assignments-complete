# Exercise 3 (generated/refactored): typed SQLite data layer.
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from .config import settings
from .exceptions import ActionItemNotFoundError, NoteNotFoundError


@dataclass(frozen=True)
class Note:
    id: int
    content: str
    created_at: str


@dataclass(frozen=True)
class ActionItem:
    id: int
    note_id: Optional[int]
    text: str
    done: bool
    created_at: str


def _note_from_row(row: sqlite3.Row) -> Note:
    return Note(
        id=int(row["id"]),
        content=str(row["content"]),
        created_at=str(row["created_at"]),
    )


def _action_item_from_row(row: sqlite3.Row) -> ActionItem:
    return ActionItem(
        id=int(row["id"]),
        note_id=row["note_id"],
        text=str(row["text"]),
        done=bool(row["done"]),
        created_at=str(row["created_at"]),
    )


def ensure_data_directory_exists() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    ensure_data_directory_exists()
    connection = sqlite3.connect(settings.db_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id INTEGER,
                text TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (note_id) REFERENCES notes(id)
            );
            """
        )
        connection.commit()


def insert_note(content: str) -> Note:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO notes (content) VALUES (?)", (content,))
        note_id = int(cursor.lastrowid)
        connection.commit()
    return get_note(note_id)


def list_notes() -> list[Note]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, content, created_at FROM notes ORDER BY id DESC"
        )
        return [_note_from_row(row) for row in cursor.fetchall()]


def get_note(note_id: int) -> Optional[Note]:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, content, created_at FROM notes WHERE id = ?",
            (note_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return _note_from_row(row)


def require_note(note_id: int) -> Note:
    note = get_note(note_id)
    if note is None:
        raise NoteNotFoundError(note_id)
    return note


def insert_action_items(
    items: list[str], note_id: Optional[int] = None
) -> list[ActionItem]:
    if not items:
        return []

    with get_connection() as connection:
        cursor = connection.cursor()
        created: list[ActionItem] = []
        for item in items:
            cursor.execute(
                "INSERT INTO action_items (note_id, text) VALUES (?, ?)",
                (note_id, item),
            )
            action_item_id = int(cursor.lastrowid)
            cursor.execute(
                """
                SELECT id, note_id, text, done, created_at
                FROM action_items
                WHERE id = ?
                """,
                (action_item_id,),
            )
            row = cursor.fetchone()
            if row is not None:
                created.append(_action_item_from_row(row))
        connection.commit()
        return created


def list_action_items(note_id: Optional[int] = None) -> list[ActionItem]:
    with get_connection() as connection:
        cursor = connection.cursor()
        if note_id is None:
            cursor.execute(
                """
                SELECT id, note_id, text, done, created_at
                FROM action_items
                ORDER BY id DESC
                """
            )
        else:
            cursor.execute(
                """
                SELECT id, note_id, text, done, created_at
                FROM action_items
                WHERE note_id = ?
                ORDER BY id DESC
                """,
                (note_id,),
            )
        return [_action_item_from_row(row) for row in cursor.fetchall()]


def mark_action_item_done(action_item_id: int, done: bool) -> ActionItem:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE action_items SET done = ? WHERE id = ?",
            (1 if done else 0, action_item_id),
        )
        if cursor.rowcount == 0:
            raise ActionItemNotFoundError(action_item_id)

        cursor.execute(
            """
            SELECT id, note_id, text, done, created_at
            FROM action_items
            WHERE id = ?
            """,
            (action_item_id,),
        )
        row = cursor.fetchone()
        connection.commit()

    if row is None:
        raise ActionItemNotFoundError(action_item_id)
    return _action_item_from_row(row)
