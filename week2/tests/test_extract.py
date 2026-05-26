# Exercise 2 (generated): unit tests for extract_action_items_llm (mocked Ollama).
import json
from unittest.mock import MagicMock

import pytest

from ..app.services.extract import extract_action_items, extract_action_items_llm


def test_extract_bullets_and_checkboxes():
    text = """
    Notes from meeting:
    - [ ] Set up database
    * implement API extract endpoint
    1. Write tests
    Some narrative sentence.
    """.strip()

    items = extract_action_items(text)
    assert "Set up database" in items
    assert "implement API extract endpoint" in items
    assert "Write tests" in items


def _mock_chat_response(items: list[str]) -> MagicMock:
    response = MagicMock()
    response.message.content = json.dumps(items)
    return response


def test_extract_action_items_llm_empty_input():
    assert extract_action_items_llm("") == []
    assert extract_action_items_llm("   ") == []


def test_extract_action_items_llm_bullet_list(monkeypatch):
    text = """
    - [ ] Set up database
    * implement API extract endpoint
    1. Write tests
    """.strip()

    def fake_chat(**kwargs):
        assert "Set up database" in kwargs["messages"][-1]["content"]
        return _mock_chat_response(
            [
                "- [ ] Set up database",
                "* implement API extract endpoint",
                "1. Write tests",
            ]
        )

    monkeypatch.setattr("week2.app.services.extract.chat", fake_chat)

    items = extract_action_items_llm(text)
    assert items == [
        "Set up database",
        "implement API extract endpoint",
        "Write tests",
    ]


def test_extract_action_items_llm_keyword_prefixed_lines(monkeypatch):
    text = """
    todo: review pull request
    action: deploy staging build
    next: schedule team sync
    """.strip()

    def fake_chat(**kwargs):
        return _mock_chat_response(
            [
                "todo: review pull request",
                "action: deploy staging build",
                "next: schedule team sync",
            ]
        )

    monkeypatch.setattr("week2.app.services.extract.chat", fake_chat)

    items = extract_action_items_llm(text)
    assert items == [
        "todo: review pull request",
        "action: deploy staging build",
        "next: schedule team sync",
    ]


def test_extract_action_items_llm_deduplicates_and_skips_blanks(monkeypatch):
    def fake_chat(**kwargs):
        return _mock_chat_response(
            [
                "Write tests",
                "write tests",
                "  ",
                "Deploy app",
            ]
        )

    monkeypatch.setattr("week2.app.services.extract.chat", fake_chat)

    items = extract_action_items_llm("Some notes")
    assert items == ["Write tests", "Deploy app"]


def test_extract_action_items_llm_empty_llm_response(monkeypatch):
    def fake_chat(**kwargs):
        response = MagicMock()
        response.message.content = ""
        return response

    monkeypatch.setattr("week2.app.services.extract.chat", fake_chat)

    assert extract_action_items_llm("Notes with no actionable items") == []


def test_extract_action_items_llm_invalid_response_shape(monkeypatch):
    def fake_chat(**kwargs):
        response = MagicMock()
        response.message.content = json.dumps({"items": ["Write tests"]})
        return response

    monkeypatch.setattr("week2.app.services.extract.chat", fake_chat)

    with pytest.raises(ValueError, match="JSON array"):
        extract_action_items_llm("Write tests today")
