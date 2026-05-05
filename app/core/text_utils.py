from __future__ import annotations


_EDGE_PUNCT = ".,!?;:\"'""\u201c\u201d\u2013\u2014-"


def _token_cmp_key(token: str) -> str:
    """Normalize token for boundary overlap: trim common punct/dashes, casefold."""
    t = token.strip()
    while t and t[0] in _EDGE_PUNCT:
        t = t[1:]
    while t and t[-1] in _EDGE_PUNCT:
        t = t[:-1]
    return t.casefold()


def _tokens_equal(a: str, b: str) -> bool:
    ka, kb = _token_cmp_key(a), _token_cmp_key(b)
    return bool(ka) and ka == kb


def _normalize(text: str) -> list[str]:
    return [part for part in text.strip().split() if part]


def _suffix_prefix_token_overlap(previous_tokens: list[str], current_tokens: list[str], *, max_window: int) -> int:
    """Longest k such that last k tokens of previous equal first k of current (normalized)."""
    if not previous_tokens or not current_tokens:
        return 0
    limit = min(len(previous_tokens), len(current_tokens), max_window)
    for size in range(limit, 0, -1):
        if size == 1:
            # 避免把自然续接的短功能词（a, I, to）误判为跨块重复
            only = _token_cmp_key(current_tokens[0])
            if len(only) < 5:
                continue
        pre = previous_tokens[-size:]
        cur = current_tokens[:size]
        if all(_tokens_equal(x, y) for x, y in zip(pre, cur, strict=True)):
            return size
    return 0


def remove_overlap(previous_text: str, current_text: str) -> str:
    previous_tokens = _normalize(previous_text)
    current_tokens = _normalize(current_text)
    if not previous_tokens or not current_tokens:
        return current_text.strip()
    overlap = _suffix_prefix_token_overlap(previous_tokens, current_tokens, max_window=16)
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
    if not previous_tokens or not current_tokens:
        return current_text.strip()

    overlap = _suffix_prefix_token_overlap(previous_tokens, current_tokens, max_window=24)
    return " ".join(current_tokens[overlap:]).strip() if overlap else current_text.strip()


def _remove_char_overlap(previous_text: str, current_text: str) -> str:
    raw_previous = "".join(previous_text.split())
    raw_current = "".join(current_text.split())
    cf_previous = raw_previous.casefold()
    cf_current = raw_current.casefold()
    short = min(len(cf_previous), len(cf_current)) < 36
    min_len = 4 if short else 8
    min_olap = 4 if short else 8
    if len(cf_previous) < min_len or len(cf_current) < min_len:
        return current_text.strip()

    limit = min(len(cf_previous), len(cf_current), 48 if short else 32)
    overlap = 0
    for size in range(limit, min_olap - 1, -1):
        if cf_previous[-size:] == cf_current[:size]:
            overlap = size
            break
    if not overlap:
        return current_text.strip()

    compact_current = raw_current[overlap:]
    return compact_whitespace(compact_current)
