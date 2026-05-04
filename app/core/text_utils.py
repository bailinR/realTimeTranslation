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


def remove_adjacent_overlap(previous_text: str, current_text: str) -> str:
    current = current_text.strip()
    previous = previous_text.strip()
    if not previous or not current:
        return current

    token_trimmed = _remove_token_overlap(previous, current)
    if token_trimmed != current:
        return token_trimmed

    return _remove_char_overlap(previous, current)


def _remove_token_overlap(previous_text: str, current_text: str) -> str:
    previous_tokens = _normalize(previous_text)
    current_tokens = _normalize(current_text)
    if len(previous_tokens) < 2 or len(current_tokens) < 2:
        return current_text.strip()

    limit = min(len(previous_tokens), len(current_tokens), 12)
    overlap = 0
    for size in range(limit, 1, -1):
        if previous_tokens[-size:] == current_tokens[:size]:
            overlap = size
            break
    return " ".join(current_tokens[overlap:]).strip() if overlap else current_text.strip()


def _remove_char_overlap(previous_text: str, current_text: str) -> str:
    normalized_previous = "".join(previous_text.split())
    normalized_current = "".join(current_text.split())
    if len(normalized_previous) < 8 or len(normalized_current) < 8:
        return current_text.strip()

    limit = min(len(normalized_previous), len(normalized_current), 24)
    overlap = 0
    for size in range(limit, 7, -1):
        if normalized_previous[-size:] == normalized_current[:size]:
            overlap = size
            break
    if not overlap:
        return current_text.strip()

    compact_current = normalized_current[overlap:]
    return compact_whitespace(compact_current)
