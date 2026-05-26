# Week 2 Write-up
Tip: To preview this markdown file
- On Mac, press `Command (⌘) + Shift + V`
- On Windows/Linux, press `Ctrl + Shift + V`

## INSTRUCTIONS

Fill out all of the `TODO`s in this file.

## SUBMISSION DETAILS

Name: **David Lai** \
SUNet ID: **TODO — fill in before submitting** \
Citations: Cursor AI (Claude) for implementation assistance across Exercises 1–5; [Ollama structured outputs](https://ollama.com/blog/structured-outputs) documentation for LLM JSON schema design.

This assignment took me about **TODO** hours to do.


## YOUR RESPONSES
For each exercise, please include what prompts you used to generate the answer, in addition to the location of the generated response. Make sure to clearly add comments in your code documenting which parts are generated.

### Exercise 1: Scaffold a New Feature
Prompt:
```
Analyze the existing `extract_action_items()` function in `week2/app/services/extract.py`, which currently extracts action items using predefined heuristics.

Your task is to implement an **LLM-powered** alternative, `extract_action_items_llm()`, that utilizes Ollama to perform action item extraction via a large language model.

Some tips:
- To produce structured outputs (i.e. JSON array of strings), refer to this documentation: https://ollama.com/blog/structured-outputs
- To browse available Ollama models, refer to this documentation: https://ollama.com/library. Note that larger models will be more resource-intensive, so start small. To pull and run a model: `ollama run {MODEL_NAME}`
```

Generated Code Snippets:
```
week2/app/services/extract.py
  - Lines 67–91:  _normalize_action_items() — cleans/deduplicates LLM output
  - Lines 94–145: extract_action_items_llm() — Ollama chat() with JSON array schema, temperature 0
```

**Summary:** Added `extract_action_items_llm()` using Ollama's `format` parameter with a JSON schema (`type: array`, `items: string`). Empty input returns `[]`. Model name is read from `OLLAMA_MODEL` (default `llama3.2`).

---

### Exercise 2: Add Unit Tests
Prompt:
```
Let perform TODO 2, Write unit tests for `extract_action_items_llm()` covering multiple inputs (e.g., bullet lists, keyword-prefixed lines, empty input) in `week2/tests/test_extract.py`
```

Generated Code Snippets:
```
week2/tests/test_extract.py
  - Lines 1–7:    imports and module header (Exercise 2)
  - Lines 24–27:  _mock_chat_response() helper
  - Lines 30–32:  test_extract_action_items_llm_empty_input
  - Lines 35–59:  test_extract_action_items_llm_bullet_list
  - Lines 62–85:  test_extract_action_items_llm_keyword_prefixed_lines
  - Lines 88–102: test_extract_action_items_llm_deduplicates_and_skips_blanks
  - Lines 105–113: test_extract_action_items_llm_empty_llm_response
  - Lines 116–125: test_extract_action_items_llm_invalid_response_shape
```

**Summary:** Six new tests mock `ollama.chat` via `monkeypatch` so tests run without a live Ollama server. Coverage includes empty input, bullets, keyword prefixes, deduplication, empty LLM response, and invalid JSON shape.

---

### Exercise 3: Refactor Existing Code for Clarity
Prompt:
```
Perform a refactor of the code in the backend, focusing in particular on well-defined API contracts/schemas, database layer cleanup, app lifecycle/configuration, error handling.
```

Generated/Modified Code Snippets:
```
week2/app/config.py          (new)  — Lines 1–31: Settings, paths, env vars (DB_PATH, OLLAMA_MODEL)
week2/app/schemas.py         (new)  — Lines 1–55: Pydantic request/response models
week2/app/exceptions.py      (new)  — Lines 1–17: NoteNotFoundError, ActionItemNotFoundError, AppError
week2/app/db.py              (refactored) — Lines 1–203: Note/ActionItem dataclasses, connection context manager, typed CRUD
week2/app/main.py            (refactored) — Lines 1–66: lifespan init_db(), exception handlers, static mount
week2/app/routers/notes.py   (refactored) — Lines 1–26: Pydantic models, require_note()
week2/app/routers/action_items.py (refactored) — Lines 1–68: Pydantic models, shared extract flow
week2/app/services/extract.py (updated) — uses settings.ollama_model from config.py
```

**Summary:** Replaced `Dict[str, Any]` payloads with Pydantic schemas; moved DB init to FastAPI lifespan; added domain exceptions and global handlers (404/422/500); refactored `db.py` to return typed `Note` and `ActionItem` objects.

---

### Exercise 4: Use Agentic Mode to Automate a Small Task
Prompt:
```
Perform task "TODO 4" - 1. Integrate the LLM-powered extraction as a new endpoint. Update the frontend to include an "Extract LLM" button that, when clicked, triggers the extraction process via the new endpoint.

2. Expose one final endpoint to retrieve all notes. Update the frontend to include a "List Notes" button that, when clicked, fetches and displays them.
```

Generated Code Snippets:
```
week2/app/routers/action_items.py
  - Lines 22–36:  _extract_and_persist() shared helper
  - Lines 44–52:  POST /action-items/extract-llm (503 on Ollama failure)

week2/app/routers/notes.py
  - Lines 11–14:  GET /notes — list all notes

week2/frontend/index.html
  - Lines 1, 26–28: Extract LLM + List Notes buttons
  - Lines 31–35:    Action items + Saved notes sections
  - Lines 37–120:   Shared extractFrom(), renderActionItems(), listNotes()

week2/tests/test_api.py (new)
  - Lines 1–52: API tests for GET /notes, POST /extract-llm, 503 error path

week2/tests/conftest.py (new)
  - Lines 1–27: per-test temporary SQLite DB fixture for isolated API tests
```

**Summary:** Added `POST /action-items/extract-llm` and `GET /notes`. Frontend has three buttons: **Extract**, **Extract LLM**, **List Notes**. API tests use FastAPI `TestClient` with an isolated temp database per test.

---

### Exercise 5: Generate a README from the Codebase
Prompt:
```
TODO 5: Generate a README from the Codebase
```

(Also used earlier for initial draft:)
```
@Codebase Act as a technical writer. Write a comprehensive README.md for this project. Include a project description, prerequisite list, installation steps, and a breakdown of the primary modules.
```

Generated Code Snippets:
```
week2/README.md (new/updated) — full project documentation:
  - Overview, features, tech stack
  - Prerequisites, installation, running the app
  - Ollama setup for LLM extraction
  - Configuration (OLLAMA_MODEL, DB_PATH)
  - API reference (all endpoints with curl examples)
  - Project structure and primary modules
  - Data flow diagram
  - Test instructions: poetry run pytest week2/tests -v
```

**Summary:** Generated `week2/README.md` reflecting the completed codebase (heuristic + LLM extraction, refactored backend, UI buttons, tests).

---

## Verification

All tests pass from the repository root:

```bash
poetry run pytest week2/tests -v
```

Expected: **11 passed** (7 extraction unit tests + 4 API tests).

Run the application:

```bash
poetry run uvicorn week2.app.main:app --reload
```

## SUBMISSION INSTRUCTIONS
1. Hit a `Command (⌘) + F` (or `Ctrl + F`) to find any remaining `TODO`s in this file. If no results are found, congratulations – you've completed all required fields.
2. Make sure you have all changes pushed to your remote repository for grading.
3. Submit via Gradescope.

**Before submitting:** Replace `SUNet ID` and `hours` placeholders in SUBMISSION DETAILS above.
