from __future__ import annotations

import json

import httpx


def summarize_httpx_exception(exc: Exception, *, body_limit: int = 500) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        request = exc.request
        method = request.method if request is not None else "UNKNOWN"
        url = str(request.url) if request is not None else "unknown-url"
        status_code = response.status_code if response is not None else "unknown-status"
        reason = response.reason_phrase if response is not None else ""
        body = _extract_response_text(response, limit=body_limit)
        summary = f"{exc.__class__.__name__}: {method} {url} -> {status_code} {reason}".strip()
        return f"{summary}; body={body}" if body else summary

    if isinstance(exc, httpx.RequestError):
        request = exc.request
        method = request.method if request is not None else "UNKNOWN"
        url = str(request.url) if request is not None else "unknown-url"
        detail = str(exc).strip() or repr(exc)
        return f"{exc.__class__.__name__}: {method} {url}; detail={detail}"

    detail = str(exc).strip() or repr(exc)
    return f"{exc.__class__.__name__}: {detail}"


def _extract_response_text(response: httpx.Response | None, *, limit: int) -> str:
    if response is None:
        return ""

    text = response.text.strip()
    if not text:
        return ""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _truncate(text, limit)

    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return _truncate(compact, limit)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."
