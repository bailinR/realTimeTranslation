from __future__ import annotations


def _normalize(text: str) -> list[str]:
    return [part for part in text.strip().split() if part]


def remove_overlap(previous_text: str, current_text: str) -> str:
    previous_tokens = _normalize(previous_text)
    current_tokens = _normalize(current_text)
    if not previous_tokens or not current_tokens:
        return current_text.strip()
    limit = min(len(previous_tokens), len(current_tokens), 8)
    overlap = 0
    for size in range(limit, 0, -1):
        if previous_tokens[-size:] == current_tokens[:size]:
            overlap = size
            break
    return " ".join(current_tokens[overlap:]).strip()


def compact_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()
