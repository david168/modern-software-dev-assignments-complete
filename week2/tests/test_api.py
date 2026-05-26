# Exercise 4 (generated): API tests for GET /notes and POST /extract-llm.
from unittest.mock import MagicMock


def test_list_notes_empty(client):
    response = client.get("/notes")
    assert response.status_code == 200
    assert response.json() == []


def test_list_notes_returns_saved_notes(client):
    client.post("/notes", json={"content": "First note"})
    client.post("/notes", json={"content": "Second note"})

    response = client.get("/notes")
    assert response.status_code == 200
    notes = response.json()
    assert len(notes) == 2
    assert notes[0]["content"] == "Second note"
    assert notes[1]["content"] == "First note"


def test_extract_llm_endpoint(client, monkeypatch):
    def fake_llm(text: str):
        return ["Task from LLM"]

    monkeypatch.setattr(
        "week2.app.routers.action_items.extract_action_items_llm", fake_llm
    )

    response = client.post(
        "/action-items/extract-llm",
        json={"text": "- do something", "save_note": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == [{"id": 1, "text": "Task from LLM"}]


def test_extract_llm_returns_503_on_failure(client, monkeypatch):
    def failing_llm(_text: str):
        raise RuntimeError("Ollama unavailable")

    monkeypatch.setattr(
        "week2.app.routers.action_items.extract_action_items_llm", failing_llm
    )

    response = client.post(
        "/action-items/extract-llm",
        json={"text": "notes", "save_note": False},
    )
    assert response.status_code == 503
    assert "LLM extraction failed" in response.json()["detail"]
