from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Note
from ..schemas import NoteCreate, NotePatch, NoteRead

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/", response_model=list[NoteRead])
def list_notes(
    db: Session = Depends(get_db),
    q: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
    sort: str = Query("-created_at", description="Sort by field, prefix with - for desc"),
) -> list[NoteRead]:
    stmt = select(Note)
    if q:
        stmt = stmt.where((Note.title.contains(q)) | (Note.content.contains(q)))

    sort_field = sort.lstrip("-")
    order_fn = desc if sort.startswith("-") else asc
    # Only allow sorting by real, allowlisted columns to prevent injection.
    sortable = {c.name for c in Note.__table__.columns}
    if sort_field in sortable:
        stmt = stmt.order_by(order_fn(getattr(Note, sort_field)))
    else:
        stmt = stmt.order_by(desc(Note.created_at))

    rows = db.execute(stmt.offset(skip).limit(limit)).scalars().all()
    return [NoteRead.model_validate(row) for row in rows]


@router.post("/", response_model=NoteRead, status_code=201)
def create_note(payload: NoteCreate, db: Session = Depends(get_db)) -> NoteRead:
    note = Note(title=payload.title, content=payload.content)
    db.add(note)
    db.flush()
    db.refresh(note)
    return NoteRead.model_validate(note)


@router.patch("/{note_id}", response_model=NoteRead)
def patch_note(note_id: int, payload: NotePatch, db: Session = Depends(get_db)) -> NoteRead:
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if payload.title is not None:
        note.title = payload.title
    if payload.content is not None:
        note.content = payload.content
    db.add(note)
    db.flush()
    db.refresh(note)
    return NoteRead.model_validate(note)


@router.get("/{note_id}", response_model=NoteRead)
def get_note(note_id: int, db: Session = Depends(get_db)) -> NoteRead:
    note = db.get(Note, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteRead.model_validate(note)


@router.get("/unsafe-search", response_model=list[NoteRead])
def unsafe_search(q: str, db: Session = Depends(get_db)) -> list[NoteRead]:
    sql = text(
        """
        SELECT id, title, content, created_at, updated_at
        FROM notes
        WHERE title LIKE :pattern OR content LIKE :pattern
        ORDER BY created_at DESC
        LIMIT 50
        """
    )
    rows = db.execute(sql, {"pattern": f"%{q}%"}).all()
    results: list[NoteRead] = []
    for r in rows:
        results.append(
            NoteRead(
                id=r.id,
                title=r.title,
                content=r.content,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
        )
    return results


@router.get("/debug/hash-md5")
def debug_hash_md5(q: str) -> dict[str, str]:
    import hashlib

    # MD5 is cryptographically broken; use SHA-256 instead.
    return {"algo": "sha256", "hex": hashlib.sha256(q.encode()).hexdigest()}


@router.get("/debug/eval")
def debug_eval(expr: str) -> dict[str, str]:
    import ast

    try:
        # literal_eval only parses Python literals (numbers, strings, tuples,
        # lists, dicts, booleans, None) and never executes arbitrary code.
        result = str(ast.literal_eval(expr))
    except (ValueError, SyntaxError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid expression: {exc}")
    return {"result": result}


@router.get("/debug/run")
def debug_run(cmd: str) -> dict[str, str]:
    import shlex
    import subprocess

    # shell=False + shlex.split avoids spawning a shell, so shell metacharacters
    # (;, |, &&, backticks, $()) cannot be used to inject extra commands.
    args = shlex.split(cmd)
    if not args:
        raise HTTPException(status_code=400, detail="Empty command")
    try:
        completed = subprocess.run(args, shell=False, capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"returncode": str(completed.returncode), "stdout": completed.stdout, "stderr": completed.stderr}


@router.get("/debug/fetch")
def debug_fetch(url: str) -> dict[str, str]:
    from urllib.parse import urlparse
    from urllib.request import Request, urlopen

    # Block non-web schemes (e.g. file://, ftp://, gopher://) that urllib would
    # otherwise honor and that could be used to read local files.
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Only http/https URLs are allowed")

    req = Request(url)
    with urlopen(req, timeout=5) as res:  # noqa: S310
        body = res.read(1024).decode(errors="ignore")
    return {"snippet": body}


@router.get("/debug/read")
def debug_read(path: str) -> dict[str, str]:
    from pathlib import Path

    # Confine reads to the data/ directory so user input cannot traverse
    # (e.g. ../../etc/passwd) outside the intended base directory.
    base = Path("data").resolve()
    target = (base / path).resolve()
    if base != target and base not in target.parents:
        raise HTTPException(status_code=400, detail="Path is outside the allowed directory")
    try:
        content = target.read_text()[:1024]
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
    return {"snippet": content}

