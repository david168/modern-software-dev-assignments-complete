from __future__ import annotations

import json
import re
from typing import Any, List, Sequence

from ollama import chat

from ..config import settings

BULLET_PREFIX_PATTERN = re.compile(r"^\s*([-*•]|\d+\.)\s+")
KEYWORD_PREFIXES = (
    "todo:",
    "action:",
    "next:",
)


def _is_action_line(line: str) -> bool:
    stripped = line.strip().lower()
    if not stripped:
        return False
    if BULLET_PREFIX_PATTERN.match(stripped):
        return True
    if any(stripped.startswith(prefix) for prefix in KEYWORD_PREFIXES):
        return True
    if "[ ]" in stripped or "[todo]" in stripped:
        return True
    return False


def extract_action_items(text: str) -> List[str]:
    lines = text.splitlines()
    extracted: List[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_action_line(line):
            cleaned = BULLET_PREFIX_PATTERN.sub("", line)
            cleaned = cleaned.strip()
            # Trim common checkbox markers
            cleaned = cleaned.removeprefix("[ ]").strip()
            cleaned = cleaned.removeprefix("[todo]").strip()
            extracted.append(cleaned)
    # Fallback: if nothing matched, heuristically split into sentences and pick imperative-like ones
    if not extracted:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            if _looks_imperative(s):
                extracted.append(s)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for item in extracted:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(item)
    return unique


# Exercise 1 (generated): shared normalization for LLM + heuristic extraction output.
def _normalize_action_items(items: Sequence[str]) -> List[str]:
    cleaned_items: List[str] = []
    for raw in items:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        # Normalize common list/checkbox formats so LLM + heuristic output match.
        s = BULLET_PREFIX_PATTERN.sub("", s).strip()
        s = s.removeprefix("[ ]").strip()
        s = s.removeprefix("[todo]").strip()
        cleaned_items.append(s)

    # Deduplicate while preserving order (case-insensitive).
    seen: set[str] = set()
    unique: List[str] = []
    for item in cleaned_items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


# Exercise 1 (generated): LLM extraction via Ollama structured JSON output.
def extract_action_items_llm(text: str) -> List[str]:
    """
    Extract action items using an LLM via Ollama, returning a JSON array of strings.

    Configuration (optional):
    - OLLAMA_MODEL: model name to use (default: llama3.2)
    """
    prompt_text = str(text or "").strip()
    if not prompt_text:
        return []

    model = settings.ollama_model

    schema: dict[str, Any] = {
        "type": "array",
        "items": {"type": "string"},
    }

    response = chat(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract action items from notes. "
                    "Return ONLY valid JSON matching the provided schema."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract a concise list of actionable tasks from the notes below. "
                    "Return a JSON array of strings (each string is one action item). "
                    "Omit non-actionable statements.\n\n"
                    f"NOTES:\n{prompt_text}"
                ),
            },
        ],
        format=schema,
        options={"temperature": 0},
    )

    content = (getattr(getattr(response, "message", None), "content", None) or "").strip()
    if not content:
        return []

    parsed = json.loads(content)
    if not isinstance(parsed, list):
        raise ValueError("LLM output did not match expected JSON array format")

    return _normalize_action_items([str(x) for x in parsed if str(x).strip()])


def _looks_imperative(sentence: str) -> bool:
    words = re.findall(r"[A-Za-z']+", sentence)
    if not words:
        return False
    first = words[0]
    # Crude heuristic: treat these as imperative starters
    imperative_starters = {
        "add",
        "create",
        "implement",
        "fix",
        "update",
        "write",
        "check",
        "verify",
        "refactor",
        "document",
        "design",
        "investigate",
    }
    return first.lower() in imperative_starters
