# Action Item Extractor

> **Exercise 5 (generated):** Project documentation produced with Cursor from the codebase.

A full-stack web application that turns free-form notes into structured action-item checklists. Paste meeting notes, bullet lists, or todo-style text in the browser; the backend extracts tasks (heuristically or via a local LLM), persists notes and items in SQLite, and lets you mark tasks complete in the UI.

Part of **CS146S: The Modern Software Developer** (Week 2). See [assignment.md](./assignment.md) for the full exercise brief.

## Features

- **Heuristic extraction** — Bullets, numbered lists, checkboxes (`[ ]`), keyword prefixes (`todo:`, `action:`, `next:`), plus an imperative-sentence fallback.
- **LLM extraction** — `extract_action_items_llm()` uses [Ollama](https://ollama.com/) structured JSON output to extract tasks.
- **Web UI** — **Extract**, **Extract LLM**, and **List Notes** buttons on a single HTML page (no frontend build step).
- **SQLite persistence** — Notes and action items stored in `week2/data/app.db`.
- **Typed REST API** — Pydantic request/response schemas, OpenAPI docs at `/docs`.
- **Error handling** — Domain exceptions (404 for missing notes/items), validation errors (422), LLM failures (503).

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | [FastAPI](https://fastapi.tiangolo.com/) |
| Server | [Uvicorn](https://www.uvicorn.org/) |
| Validation | [Pydantic](https://docs.pydantic.dev/) v2 |
| Database | SQLite (`sqlite3`) |
| LLM | [Ollama](https://ollama.com/) Python client |
| Frontend | Static HTML + vanilla JavaScript |
| Dependencies | Poetry (repo root `pyproject.toml`) |
| Testing | pytest, FastAPI `TestClient` |

## Prerequisites

Install once at the **repository root** (see [../README.md](../README.md)):

- **Python 3.10+** (3.12 recommended)
- **Conda** (recommended: `cs146s` environment)
- **Poetry**

```bash
conda create -n cs146s python=3.12 -y
conda activate cs146s
curl -sSL https://install.python-poetry.org | python -
poetry install --no-interaction
```

**For LLM extraction:**

- [Ollama](https://ollama.com/) installed and running (desktop app or `ollama serve`)
- A pulled model (default: `llama3.2`):

  ```bash
  ollama pull llama3.2
  ```

## Installation

From the repository root:

```bash
cd modern-software-dev-assignments-master
conda activate cs146s
poetry install --no-interaction
```

The database is created automatically on first server start (`week2/data/app.db`). No manual migrations.

## Running the Application

```bash
poetry run uvicorn week2.app.main:app --reload
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/).

### UI workflow

1. Paste notes into the text area.
2. Optionally leave **Save as note** checked to store the raw text.
3. Click **Extract** (heuristics) or **Extract LLM** (Ollama).
4. Toggle checkboxes to mark items done.
5. Click **List Notes** to view all saved notes.

Interactive API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Ollama setup (LLM button)

The app calls the Ollama **server** at `http://localhost:11434`. You do not need an interactive `ollama run` session open.

1. Start Ollama (open the Ollama app on macOS, or run `ollama serve`).
2. Pull the model: `ollama pull llama3.2`
3. Start the FastAPI server (see above).
4. Use **Extract LLM** in the browser.

Verify the server:

```bash
curl http://localhost:11434/api/tags
```

## Configuration

Optional environment variables (via `.env` or shell):

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name for LLM extraction |
| `DB_PATH` | `week2/data/app.db` | SQLite database file path |

## API Reference

### UI & static

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serves `frontend/index.html` |
| — | `/static/*` | Static assets from `frontend/` |

### Notes (`/notes`)

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET` | `/notes` | — | List all notes (newest first) |
| `POST` | `/notes` | `{ "content": "..." }` | Create a note |
| `GET` | `/notes/{note_id}` | — | Get one note |

### Action items (`/action-items`)

| Method | Path | Body / query | Description |
|--------|------|----------------|-------------|
| `POST` | `/action-items/extract` | `{ "text": "...", "save_note": true }` | Heuristic extraction |
| `POST` | `/action-items/extract-llm` | `{ "text": "...", "save_note": true }` | LLM extraction (Ollama) |
| `GET` | `/action-items` | `?note_id=` (optional) | List action items |
| `POST` | `/action-items/{id}/done` | `{ "done": true }` | Mark item done/undone |

**Example — heuristic extract:**

```bash
curl -X POST http://127.0.0.1:8000/action-items/extract \
  -H "Content-Type: application/json" \
  -d '{"text": "- [ ] Set up database\n- Write tests", "save_note": true}'
```

**Example — LLM extract:**

```bash
curl -X POST http://127.0.0.1:8000/action-items/extract-llm \
  -H "Content-Type: application/json" \
  -d '{"text": "todo: review PR\naction: deploy staging", "save_note": false}'
```

**Example — list notes:**

```bash
curl http://127.0.0.1:8000/notes
```

## Project Structure

```
week2/
├── README.md
├── assignment.md
├── writeup.md
├── app/
│   ├── main.py              # FastAPI app, lifespan, exception handlers
│   ├── config.py            # Settings (DB path, Ollama model)
│   ├── schemas.py           # Pydantic API contracts
│   ├── exceptions.py        # Domain errors
│   ├── db.py                # SQLite layer (Note, ActionItem models)
│   ├── routers/
│   │   ├── notes.py
│   │   └── action_items.py
│   └── services/
│       └── extract.py       # Heuristic + LLM extraction
├── frontend/
│   └── index.html
├── tests/
│   ├── test_extract.py      # Unit tests (extraction, mocked LLM)
│   └── test_api.py          # API tests (list notes, extract-llm)
└── data/                    # Created at runtime
    └── app.db
```

## Primary Modules

### `app/main.py`

- FastAPI app with **lifespan** hook that runs `init_db()` on startup.
- Global exception handlers for `NoteNotFoundError`, `ActionItemNotFoundError`, validation errors.
- Serves the frontend and mounts `/static`.

### `app/config.py`

Central configuration: `settings.db_path`, `settings.ollama_model`, `FRONTEND_DIR`.

### `app/schemas.py`

Pydantic models for all API inputs/outputs (`NoteCreate`, `NoteResponse`, `ExtractActionItemsRequest`, etc.).

### `app/db.py`

Typed `Note` and `ActionItem` dataclasses, connection context manager, CRUD helpers. Raises `NoteNotFoundError` / `ActionItemNotFoundError` when appropriate.

### `app/routers/notes.py`

`GET /notes`, `POST /notes`, `GET /notes/{id}`.

### `app/routers/action_items.py`

`POST /extract`, `POST /extract-llm`, `GET /action-items`, `POST /{id}/done`. Shared `_extract_and_persist()` for both extract paths.

### `app/services/extract.py`

| Function | Description |
|----------|-------------|
| `extract_action_items(text)` | Regex/heuristic extraction |
| `extract_action_items_llm(text)` | Ollama chat with JSON schema (`array` of `string`), temperature 0 |

### `frontend/index.html`

Buttons for **Extract**, **Extract LLM**, and **List Notes**; renders action items and saved notes.

## Data Flow

```
Browser
  ├─ POST /action-items/extract      → extract_action_items()
  ├─ POST /action-items/extract-llm  → extract_action_items_llm() → Ollama
  └─ GET  /notes                     → db.list_notes()
         │
         ▼
  action_items / notes routers
         │
         ▼
  db.py → SQLite (week2/data/app.db)
         │
         ▼
  JSON response → UI renders checklist / notes list
```

## Running Tests

From the repository root:

```bash
poetry run pytest week2/tests -v
```

| File | Coverage |
|------|----------|
| `test_extract.py` | Heuristic extraction; `extract_action_items_llm()` with mocked Ollama |
| `test_api.py` | `GET /notes`, `POST /extract-llm`, 503 on LLM failure |

Quick run:

```bash
poetry run pytest week2/tests -q
```

## Related Documentation

- [assignment.md](./assignment.md) — Week 2 exercises and rubric
- [writeup.md](./writeup.md) — Submission template
- [../README.md](../README.md) — Repository setup (Conda, Poetry)

## License

Course materials for CS146S. Refer to your course policies for use and distribution.
