import re
from dataclasses import dataclass

# Matches a leading keyword such as "TODO", "TODO(alice):", "action -" etc.
_KEYWORD_PATTERN = re.compile(
    r"^(?P<keyword>todo|action|fixme|task)\s*(?:\([^)]*\))?\s*[:\-]?\s*",
    re.IGNORECASE,
)
_BULLET_PATTERN = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")
_ASSIGNEE_PATTERN = re.compile(r"@(?P<assignee>\w+)")
_DUE_DATE_PATTERN = re.compile(
    r"\b(?:by|due(?:\s+by)?)\s+(?P<due_date>[A-Za-z0-9][\w,/\- ]*?)(?=\s*[.!,]|$)",
    re.IGNORECASE,
)
_HIGH_PRIORITY_PATTERN = re.compile(r"\b(urgent|asap|critical|high priority)\b", re.IGNORECASE)
_LOW_PRIORITY_PATTERN = re.compile(r"\blow priority\b", re.IGNORECASE)


@dataclass
class ActionItemAnalysis:
    text: str
    keyword: str | None
    priority: str
    assignee: str | None
    due_date: str | None


def _strip_bullet(line: str) -> str:
    return _BULLET_PATTERN.sub("", line).strip()


def _match_keyword(line: str) -> str | None:
    match = _KEYWORD_PATTERN.match(line)
    return match.group("keyword").lower() if match else None


def _detect_priority(line: str) -> str:
    if _HIGH_PRIORITY_PATTERN.search(line) or "!!" in line:
        return "high"
    if _LOW_PRIORITY_PATTERN.search(line):
        return "low"
    return "normal"


def _detect_assignee(line: str) -> str | None:
    match = _ASSIGNEE_PATTERN.search(line)
    return match.group("assignee") if match else None


def _detect_due_date(line: str) -> str | None:
    match = _DUE_DATE_PATTERN.search(line)
    if not match:
        return None
    due_date = match.group("due_date").strip()
    return due_date or None


def analyze_action_items(text: str) -> list[ActionItemAnalysis]:
    """Scan free-form text and return structured analysis for each actionable line.

    A line is considered actionable if it starts with a recognized keyword
    (TODO/ACTION/FIXME/TASK, optionally with an "(assignee)" suffix and a
    trailing ":" or "-") or ends with "!". Each match is further annotated
    with a priority level, an "@mention" assignee, and a "by/due <date>"
    phrase, when present.
    """
    results: list[ActionItemAnalysis] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            continue
        line = _strip_bullet(raw_line)
        if not line:
            continue

        keyword = _match_keyword(line)
        if keyword is None and not line.endswith("!"):
            continue

        results.append(
            ActionItemAnalysis(
                text=line,
                keyword=keyword,
                priority=_detect_priority(line),
                assignee=_detect_assignee(line),
                due_date=_detect_due_date(line),
            )
        )
    return results


def extract_action_items(text: str) -> list[str]:
    """Backward-compatible entry point returning just the matched line text."""
    return [item.text for item in analyze_action_items(text)]
