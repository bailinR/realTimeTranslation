from __future__ import annotations

import httpx

from app.net_utils import summarize_httpx_exception


def test_summarize_http_status_error_includes_request_and_body() -> None:
    request = httpx.Request("POST", "https://example.com/audio/transcriptions")
    response = httpx.Response(
        401,
        request=request,
        json={"error": {"message": "invalid api key", "type": "auth_error"}},
    )
    exc = httpx.HTTPStatusError("boom", request=request, response=response)

    summary = summarize_httpx_exception(exc)

    assert "HTTPStatusError" in summary
    assert "POST https://example.com/audio/transcriptions" in summary
    assert "401 Unauthorized" in summary
    assert '"message":"invalid api key"' in summary


def test_summarize_request_error_falls_back_to_repr_when_message_empty() -> None:
    request = httpx.Request("POST", "https://example.com/chat/completions")
    exc = httpx.ReadTimeout("", request=request)

    summary = summarize_httpx_exception(exc)

    assert "ReadTimeout" in summary
    assert "POST https://example.com/chat/completions" in summary
    assert "ReadTimeout('')" in summary
