from backend.app.services.extract import analyze_action_items, extract_action_items


def test_extract_action_items():
    text = """
    This is a note
    - TODO: write tests
    - ACTION: review PR
    - Ship it!
    Not actionable
    """.strip()
    items = extract_action_items(text)
    assert "TODO: write tests" in items
    assert "ACTION: review PR" in items
    assert "Ship it!" in items
    assert "Not actionable" not in items


def test_extract_action_items_recognizes_fixme_and_task_keywords():
    text = "FIXME: broken link\nTASK: update docs\nJust a sentence."
    items = extract_action_items(text)
    assert "FIXME: broken link" in items
    assert "TASK: update docs" in items
    assert "Just a sentence." not in items


def test_extract_action_items_strips_numbered_and_bullet_markers():
    text = "1. TODO: first thing\n* TODO: second thing\n• TODO: third thing"
    items = extract_action_items(text)
    assert "TODO: first thing" in items
    assert "TODO: second thing" in items
    assert "TODO: third thing" in items


def test_analyze_action_items_detects_keyword_and_priority():
    text = "TODO: fix the urgent bug!!"
    [analysis] = analyze_action_items(text)
    assert analysis.keyword == "todo"
    assert analysis.priority == "high"


def test_analyze_action_items_detects_low_priority():
    text = "TODO: clean up old comments (low priority)"
    [analysis] = analyze_action_items(text)
    assert analysis.priority == "low"


def test_analyze_action_items_detects_assignee():
    text = "ACTION(bob): review the PR @bob before merging"
    [analysis] = analyze_action_items(text)
    assert analysis.keyword == "action"
    assert analysis.assignee == "bob"


def test_analyze_action_items_detects_due_date():
    text = "TODO: submit the report by Friday"
    [analysis] = analyze_action_items(text)
    assert analysis.due_date == "Friday"


def test_analyze_action_items_no_matches_returns_empty_list():
    text = "Just some notes.\nNothing actionable here."
    assert analyze_action_items(text) == []


def test_analyze_action_items_exclamation_without_keyword_has_no_keyword():
    text = "Ship it!"
    [analysis] = analyze_action_items(text)
    assert analysis.keyword is None
    assert analysis.priority == "normal"


