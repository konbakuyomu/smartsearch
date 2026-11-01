import asyncio
import json

import httpx
import pytest

from smart_search.provider_errors import ProviderCallError
from smart_search.providers.xai_responses import XAIResponsesSearchProvider
from smart_search.sources import split_answer_and_sources


class DummyResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def json(self):
        return self._json_data


def output_text_response(text, annotations=None):
    return DummyResponse(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": text,
                            "annotations": annotations or [],
                        }
                    ],
                }
            ]
        }
    )


def test_xai_responses_search_payload_uses_responses_shape():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search", "x_search"])

    payload = provider._build_search_payload("What is new?", "X")

    assert payload["model"] == "test-model"
    assert payload["instructions"]
    assert payload["stream"] is False
    assert "reasoning" not in payload
    assert payload["tools"] == [{"type": "web_search"}, {"type": "x_search"}]
    assert payload["input"][0]["role"] == "user"
    assert "What is new?" in payload["input"][0]["content"]
    assert "X" in payload["input"][0]["content"]


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_xai_responses_payload_sends_optional_reasoning_effort(effort):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", reasoning_effort=effort)

    assert provider._build_search_payload("query")["reasoning"] == {"effort": effort}


@pytest.mark.asyncio
async def test_xai_responses_stream_matches_non_stream_sources(monkeypatch):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", stream=True)
    annotations = [{"type": "url_citation", "url": "https://example.com/a", "title": "Source"}]
    events = [
        {"type": "response.output_text.delta", "delta": "Streamed "},
        {"type": "response.output_text.delta", "delta": "answer."},
        {"type": "response.output_text.annotation.added", "annotation": annotations[0]},
        {"type": "response.completed", "response": {"status": "completed", "output": []}},
    ]
    requests = []
    original_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                              text="".join(f"data: {json.dumps(event)}\n\n" for event in events))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))

    result = await provider.search("query")

    assert len(requests) == 1
    assert json.loads(requests[0].content)["stream"] is True
    assert result == await provider._parse_response(output_text_response("Streamed answer.", annotations))
    assert split_answer_and_sources(result) == ("Streamed answer.", [{"url": "https://example.com/a", "title": "Source"}])


@pytest.mark.asyncio
async def test_xai_stream_inline_urls_match_non_stream_sources(monkeypatch):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", stream=True)
    answer = "See HTTPS://example.org/source for details."
    events = [
        {"type": "response.output_text.delta", "delta": answer},
        {"type": "response.completed", "response": {"status": "completed", "output": []}},
    ]
    original_client = httpx.AsyncClient

    def handler(request):
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"},
                              text="".join(f"data: {json.dumps(event)}\n\n" for event in events))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))

    result = await provider.search("query")

    assert result == await provider._parse_response(output_text_response(answer))
    assert result.endswith('sources([{"url": "https://example.org/source"}])')
    assert split_answer_and_sources(result) == (answer, [{"url": "https://example.org/source"}])


@pytest.mark.asyncio
async def test_xai_responses_parse_output_text_and_url_citations():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = DummyResponse(
        {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Answer [[1]](https://example.com/a).",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/a",
                                    "title": "1",
                                    "start_index": 7,
                                    "end_index": 10,
                                },
                                {
                                    "type": "url_citation",
                                    "url": "https://example.com/a",
                                    "title": "duplicate",
                                },
                            ],
                        }
                    ],
                }
            ]
        }
    )

    result = await provider._parse_response(response)

    assert "Answer [[1]](https://example.com/a)." in result
    assert "sources(" in result
    assert result.count("https://example.com/a") == 2


@pytest.mark.asyncio
async def test_xai_responses_structured_url_citations_win_over_inline_urls():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = output_text_response(
        "Use [the inline link](https://inline.example.com/ignored) for context.",
        [
            {
                "type": "url_citation",
                "url": "https://structured.example.com/authoritative",
                "title": "Structured source",
            }
        ],
    )

    result = await provider._parse_response(response)
    answer, sources = split_answer_and_sources(result)

    assert answer == "Use [the inline link](https://inline.example.com/ignored) for context."
    assert sources == [
        {
            "url": "https://structured.example.com/authoritative",
            "title": "Structured source",
        }
    ]


@pytest.mark.asyncio
async def test_xai_responses_extracts_ordered_unique_markdown_and_bare_urls():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = output_text_response(
        "Read [the docs](https://docs.example.com/guide), then "
        "HTTPS://news.example.com/latest; repeat https://docs.example.com/guide."
    )

    result = await provider._parse_response(response)
    answer, sources = split_answer_and_sources(result)

    assert answer == (
        "Read [the docs](https://docs.example.com/guide), then "
        "HTTPS://news.example.com/latest; repeat https://docs.example.com/guide."
    )
    assert sources == [
        {"url": "https://docs.example.com/guide"},
        {"url": "https://news.example.com/latest"},
    ]


@pytest.mark.asyncio
async def test_xai_responses_inline_url_fallback_trims_ascii_and_cjk_terminal_punctuation():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = output_text_response(
        "[ASCII](https://ascii.example.com/path). "
        "CJK https://cjk.example.com/path， "
        "closer https://closer.example.com/path） "
        "bracket https://bracket.example.com/path】 "
        "balanced https://wiki.example.com/Function_(mathematics)."
    )

    result = await provider._parse_response(response)
    _, sources = split_answer_and_sources(result)

    assert [source["url"] for source in sources] == [
        "https://ascii.example.com/path",
        "https://cjk.example.com/path",
        "https://closer.example.com/path",
        "https://bracket.example.com/path",
        "https://wiki.example.com/Function_(mathematics)",
    ]


@pytest.mark.asyncio
async def test_xai_responses_inline_url_fallback_rejects_malformed_and_non_http_urls():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = output_text_response(
        "Ignore ftp://files.example.com/archive, mailto:person@example.com, "
        "https:///missing-host, https://?missing-host, http://[bad, and "
        "https://port.example.com:not-a-port, xhttps://prefixed.example.com/path, and "
        "https://backslash.example.com/path\\tail. Keep https://valid.example.com/path."
    )

    result = await provider._parse_response(response)
    _, sources = split_answer_and_sources(result)

    assert sources == [{"url": "https://valid.example.com/path"}]


@pytest.mark.asyncio
async def test_xai_responses_inline_url_fallback_keeps_answers_without_urls_unchanged():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])

    result = await provider._parse_response(output_text_response("No citation URLs were returned."))

    assert result == "No citation URLs were returned."


@pytest.mark.asyncio
async def test_xai_responses_inline_url_fallback_preserves_existing_sources_block():
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", ["web_search"])
    response = output_text_response('Answer.\n\nsources([{"url": "https://already.example.com"}])')

    result = await provider._parse_response(response)
    answer, sources = split_answer_and_sources(result)

    assert answer == "Answer."
    assert sources == [{"url": "https://already.example.com"}]


@pytest.mark.asyncio
async def test_xai_responses_execute_posts_to_responses(monkeypatch):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    calls = []

    class FakeAsyncClient:
        def __init__(self, timeout, follow_redirects, verify):
            self.timeout = timeout
            self.follow_redirects = follow_redirects
            self.verify = verify

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json, timeout=None):
            calls.append((url, headers, json))
            self.request_timeout = timeout
            return httpx.Response(
                200,
                json={"output": [{"content": [{"type": "output_text", "text": "ok", "annotations": []}]}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("smart_search.providers.xai_responses.httpx.AsyncClient", FakeAsyncClient)

    result = await provider.search("query")

    assert result == "ok"
    assert calls[0][0] == "https://api.x.ai/v1/responses"
    assert calls[0][2]["tools"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(("tools", "hinted"), [(["web_search", "x_search"], True), (["web_search"], False)])
async def test_xai_slot_explains_x_search_rejected_by_another_service(monkeypatch, tools, hinted):
    provider = XAIResponsesSearchProvider("https://api.openai.com/v1", "sk-test", "gpt-6.1-sol", tools)
    body = {"error": {"message": "Invalid value: 'x_search'. Supported values are: 'web_search_preview'.",
                      "type": "invalid_request_error", "param": "tools[1].type", "code": "invalid_value"}}

    def handler(request):
        return httpx.Response(400, json=body)

    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))

    with pytest.raises(Exception) as caught:
        await provider.search("query")

    if hinted:
        assert isinstance(caught.value, ProviderCallError) and caught.value.error_type == "parameter_error"
        assert "api.openai.com" in caught.value.error and "XAI_TOOLS" in caught.value.error and "web_search" in caught.value.error
    else:
        assert isinstance(caught.value, httpx.HTTPStatusError)


def test_xai_request_timeout_follows_the_shared_deadline():
    import time

    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    provider.set_search_deadline(time.monotonic() + 280.0)

    timeout = provider._request_timeout()

    assert timeout.read > 240.0
    assert timeout.connect == 6.0


def test_xai_standalone_request_timeout_uses_the_configured_budget(monkeypatch):
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    monkeypatch.setenv("SMART_SEARCH_TIMEOUT_SECONDS", "450")

    assert provider._request_timeout().read == 450.0

    monkeypatch.setenv("SMART_SEARCH_TIMEOUT_SECONDS", "not-a-number")

    # An invalid saved budget must not turn into a transport error here.
    assert provider._request_timeout().read == 300.0


@pytest.mark.asyncio
async def test_xai_expired_deadline_fails_before_any_request():
    import time

    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [])
    provider.set_search_deadline(time.monotonic() - 0.01)

    with pytest.raises(asyncio.TimeoutError):
        await provider.search("expired deadline")


@pytest.mark.asyncio
@pytest.mark.parametrize("delay,expected_requests", [(0.1, 1), (0, 4)])
@pytest.mark.parametrize("stream", [False, True])
async def test_xai_retry_stops_after_slow_failure(monkeypatch, delay, expected_requests, stream):
    import smart_search.providers.openai_compatible as provider_mod

    monkeypatch.setattr(provider_mod, "SLOW_FAILURE_SECONDS", 0.05)
    monkeypatch.setenv("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("SMART_SEARCH_RETRY_MULTIPLIER", "0")
    requests = []
    original_client = httpx.AsyncClient

    async def handler(request):
        requests.append(request)
        if delay:
            await asyncio.sleep(delay)
        return httpx.Response(503)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    provider = XAIResponsesSearchProvider("https://api.x.ai/v1", "test-key", "test-model", [], stream=stream)
    with pytest.raises(httpx.HTTPStatusError):
        await provider.search("query")

    assert len(requests) == expected_requests
