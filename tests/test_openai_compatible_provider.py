import asyncio
import httpx
import json
import pytest
import time

from smart_search.providers.openai_compatible import OpenAICompatibleSearchProvider, reset_openai_compatible_breakers
from smart_search.provider_errors import ProviderCallError
from smart_search.sources import split_answer_and_sources


class DummyResponse:
    """模拟 httpx.Response 用于测试 completion 解析"""

    def __init__(self, text="", json_data=None, json_error=None):
        self.text = text
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_data


@pytest.mark.asyncio
async def test_search_uses_non_stream_completion_and_headers(monkeypatch):
    """验证 search() 使用非流式 completion + 自定义 headers"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    captured = {}

    async def fake_execute(headers, payload, ctx):
        captured["headers"] = headers
        captured["payload"] = payload
        return "ok"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)

    result = await provider.search("What is Scrape.do?")

    assert result == "ok"
    assert "User-Agent" in captured["headers"]
    assert captured["headers"]["Accept"] == "application/json, text/event-stream"
    assert captured["payload"]["stream"] is False
    assert "tools" not in captured["payload"]
    assert "search_parameters" not in captured["payload"]


@pytest.mark.asyncio
async def test_responses_mode_builds_normalized_request_without_xai_fields(monkeypatch):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1/",
        "test-key",
        "test-model",
        api_mode="responses",
    )
    captured = {}

    async def fake_execute(headers, payload, ctx):
        captured["payload"] = payload
        return "ok"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)

    assert await provider.search("current release notes", platform="github.com") == "ok"
    assert provider._api_endpoint() == "https://api.example.com/v1/responses"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["instructions"]
    assert captured["payload"]["input"][0]["role"] == "user"
    assert "current release notes" in captured["payload"]["input"][0]["content"]
    assert "github.com" in captured["payload"]["input"][0]["content"]
    assert captured["payload"]["stream"] is False
    assert "messages" not in captured["payload"]
    assert "tools" not in captured["payload"]
    assert "search_parameters" not in captured["payload"]


@pytest.mark.parametrize(
    ("api_url", "api_mode", "expected_endpoint"),
    [
        ("https://api.example.com/v1/responses/", "responses", "https://api.example.com/v1/responses"),
        ("https://api.example.com/v1/chat/completions/", "responses", "https://api.example.com/v1/responses"),
        ("https://api.example.com/v1/responses/", "chat-completions", "https://api.example.com/v1/chat/completions"),
    ],
)
def test_openai_compatible_endpoint_normalizes_known_completion_suffixes(api_url, api_mode, expected_endpoint):
    provider = OpenAICompatibleSearchProvider(api_url, "test-key", "test-model", api_mode=api_mode)

    assert provider._api_endpoint() == expected_endpoint


@pytest.mark.asyncio
async def test_responses_fetch_respects_stream_while_describe_and_rank_stay_non_stream(monkeypatch):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        stream=True,
        api_mode="responses",
    )
    payloads = []

    async def fake_execute(headers, payload, ctx):
        payloads.append(payload)
        user_content = payload["input"][0]["content"]
        if user_content.startswith("Query:"):
            return "1"
        if user_content == "https://example.com":
            return "Title: Example\nExtracts: Some text"
        return "fetched content"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)
    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_execute)

    assert await provider.fetch("https://example.com/page") == "fetched content"
    assert (await provider.describe_url("https://example.com"))["title"] == "Example"
    assert await provider.rank_sources("query", "1. Source", 1) == [1]
    assert len(payloads) == 3
    assert [payload["stream"] for payload in payloads] == [True, False, False]
    assert all("instructions" in payload and "input" in payload for payload in payloads)
    assert all("messages" not in payload and "tools" not in payload for payload in payloads)


@pytest.mark.asyncio
@pytest.mark.parametrize("require", [False, True])
@pytest.mark.parametrize("tools", [["web_search"], ["web_search_preview"]])
async def test_responses_tools_ride_on_search_only(monkeypatch, tools, require):
    provider = OpenAICompatibleSearchProvider(
        "https://api.openai.com/v1", "test-key", "gpt-6.1-sol", api_mode="responses", tools=tools,
        require_web_search=require,
    )
    payloads = {}

    def capture(name):
        async def fake(headers, payload, ctx=None):
            payloads.setdefault(name, payload)
            return "1" if name == "rank" else "Title: T\nExtracts: E" if name == "describe" else "answer"
        return fake

    monkeypatch.setattr(provider, "_execute_with_transport_fallback", capture("search"))
    await provider.search("latest python release")
    monkeypatch.setattr(provider, "_execute_with_transport_fallback", capture("fetch"))
    await provider.fetch("https://example.com")
    monkeypatch.setattr(provider, "_execute_with_transport_fallback", capture("synthesize"))
    await provider.synthesize("q", [])
    monkeypatch.setattr(provider, "_execute_completion_with_retry", capture("describe"))
    await provider.describe_url("https://example.com")
    monkeypatch.setattr(provider, "_execute_completion_with_retry", capture("rank"))
    await provider.rank_sources("q", "1. a", 1)

    assert payloads["search"]["tools"] == [{"type": tool} for tool in tools]
    # Forcing the tool is opt-in: relays that reject tool_choice keep working by default.
    assert payloads["search"].get("tool_choice") == ("required" if require else None)
    assert all("tools" not in payloads[name] for name in ("fetch", "synthesize", "describe", "rank"))
    assert all("tool_choice" not in payloads[name] for name in ("fetch", "synthesize", "describe", "rank"))


@pytest.mark.asyncio
async def test_chat_completions_never_sends_tools(monkeypatch):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1", "test-key", "gpt-5-search-api", api_mode="chat-completions", tools=["web_search"],
    )
    captured = {}

    async def fake(headers, payload, ctx=None):
        captured["payload"] = payload
        return "answer"

    monkeypatch.setattr(provider, "_execute_with_transport_fallback", fake)
    await provider.search("latest python release")

    assert "tools" not in captured["payload"] and "messages" in captured["payload"]


@pytest.mark.asyncio
async def test_fetch_uses_non_stream(monkeypatch):
    """验证 fetch() 使用非流式 completion"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    captured = {}

    async def fake_execute(headers, payload, ctx):
        captured["payload"] = payload
        return "fetched content"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)

    result = await provider.fetch("https://example.com")

    assert result == "fetched content"
    assert captured["payload"]["stream"] is False


@pytest.mark.asyncio
async def test_search_stream_true_prefers_streaming_executor(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)
    captured = {}

    async def should_not_call_completion(headers, payload, ctx):
        raise AssertionError("completion should not run when stream succeeds")

    async def fake_stream(headers, payload, ctx):
        captured["headers"] = headers
        captured["payload"] = payload
        return "streamed search"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", should_not_call_completion)
    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)

    result = await provider.search("stream query")

    assert result == "streamed search"
    assert captured["payload"]["stream"] is True
    assert provider.last_transport_attempts[0]["transport"] == "stream"
    assert provider.last_transport_attempts[0]["status"] == "ok"


@pytest.mark.asyncio
async def test_fetch_stream_true_prefers_streaming_executor(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)
    captured = {}

    async def should_not_call_completion(headers, payload, ctx):
        raise AssertionError("completion should not run when stream succeeds")

    async def fake_stream(headers, payload, ctx):
        captured["payload"] = payload
        return "streamed fetch"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", should_not_call_completion)
    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)

    result = await provider.fetch("https://example.com")

    assert result == "streamed fetch"
    assert captured["payload"]["stream"] is True


@pytest.mark.asyncio
async def test_search_stream_empty_falls_back_to_non_stream(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)
    payloads = []

    async def fake_stream(headers, payload, ctx):
        payloads.append(dict(payload))
        return ""

    async def fake_completion(headers, payload, ctx):
        payloads.append(dict(payload))
        return "non-stream answer"

    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)
    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_completion)

    result = await provider.search("stream query")

    assert result == "non-stream answer"
    assert [payload["stream"] for payload in payloads] == [True, False]
    assert [attempt["status"] for attempt in provider.last_transport_attempts] == ["empty", "ok"]
    assert provider.last_transport_attempts[1]["fallback_from_transport"] == "stream"


@pytest.mark.asyncio
async def test_search_stream_retryable_exception_falls_back_to_non_stream(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)

    async def fake_stream(headers, payload, ctx):
        raise httpx.RemoteProtocolError("bad sse")

    async def fake_completion(headers, payload, ctx):
        return "non-stream answer"

    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)
    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_completion)

    result = await provider.search("stream query")

    assert result == "non-stream answer"
    assert [attempt["status"] for attempt in provider.last_transport_attempts] == ["error", "ok"]
    assert provider.last_transport_attempts[0]["error_type"] == "network_error"


@pytest.mark.asyncio
async def test_non_stream_transport_http_error_uses_shared_taxonomy(monkeypatch):
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(422, text="invalid request", request=request)

    async def fake_completion(headers, payload, ctx):
        raise httpx.HTTPStatusError("invalid request", request=request, response=response)

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_completion)

    with pytest.raises(httpx.HTTPStatusError):
        await provider.search("query")

    attempt = provider.last_transport_attempts[0]
    assert attempt["status"] == "error"
    assert attempt["error_type"] == "parameter_error"
    assert "HTTP 422" in attempt["error"]


@pytest.mark.asyncio
async def test_search_stream_then_non_stream_error_records_both_attempts(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)

    async def fake_stream(headers, payload, ctx):
        return ""

    async def fake_completion(headers, payload, ctx):
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)
    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_completion)

    with pytest.raises(httpx.TimeoutException):
        await provider.search("stream query")

    assert [attempt["transport"] for attempt in provider.last_transport_attempts] == ["stream", "non_stream"]
    assert [attempt["status"] for attempt in provider.last_transport_attempts] == ["empty", "error"]
    assert provider.last_transport_attempts[1]["fallback_from_transport"] == "stream"
    assert provider.last_transport_attempts[1]["error_type"] == "timeout"


@pytest.mark.asyncio
async def test_stream_breaker_opens_after_two_failures_and_skips_stream(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)
    stream_calls = 0

    async def fake_stream(headers, payload, ctx):
        nonlocal stream_calls
        stream_calls += 1
        return ""

    async def fake_completion(headers, payload, ctx):
        return "non-stream answer"

    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)
    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_completion)

    assert await provider.search("q1") == "non-stream answer"
    assert await provider.search("q2") == "non-stream answer"
    assert await provider.search("q3") == "non-stream answer"

    assert stream_calls == 2
    assert provider.last_transport_attempts[0]["transport"] == "stream"
    assert provider.last_transport_attempts[0]["status"] == "skipped"
    assert provider.last_transport_attempts[0]["breaker_state"]["state"] == "open"


@pytest.mark.asyncio
async def test_service_deadline_stops_openai_transport_before_a_request():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    provider.set_search_deadline(time.monotonic() - 0.01)

    with pytest.raises(asyncio.TimeoutError):
        await provider.search("expired deadline")

    assert provider.last_transport_attempts[0]["transport"] == "non_stream"
    assert provider.last_transport_attempts[0]["error_type"] == "timeout"


def test_retry_after_wait_is_capped_by_the_service_deadline():
    from smart_search.providers.openai_compatible import _WaitWithRetryAfter

    request = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    response = httpx.Response(429, headers={"Retry-After": "3600"}, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)

    class FailedOutcome:
        failed = True

        @staticmethod
        def exception():
            return error

    class RetryState:
        outcome = FailedOutcome()

    wait = _WaitWithRetryAfter(1, 60, deadline_monotonic=time.monotonic() + 5)

    assert 0 <= wait(RetryState()) <= 5


@pytest.mark.asyncio
async def test_describe_url_uses_non_stream(monkeypatch):
    """验证 describe_url() 使用非流式 completion"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    captured = {}

    async def fake_execute(headers, payload, ctx):
        captured["payload"] = payload
        return "Title: Example\nExtracts: Some text"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)

    result = await provider.describe_url("https://example.com")

    assert result["title"] == "Example"
    assert captured["payload"]["stream"] is False


@pytest.mark.asyncio
async def test_rank_sources_uses_non_stream(monkeypatch):
    """验证 rank_sources() 使用非流式 completion"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    captured = {}

    async def fake_execute(headers, payload, ctx):
        captured["payload"] = payload
        return "2 1 3"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)

    result = await provider.rank_sources("test query", "sources...", 3)

    assert result == [2, 1, 3]
    assert captured["payload"]["stream"] is False


@pytest.mark.asyncio
async def test_describe_and_rank_ignore_instance_stream_flag(monkeypatch):
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)
    payloads = []

    async def fake_execute(headers, payload, ctx):
        payloads.append(payload)
        if "Query:" in payload["messages"][1]["content"]:
            return "1"
        return "Title: Example\nExtracts: Some text"

    async def should_not_stream(headers, payload, ctx):
        raise AssertionError("short internal tasks must remain non-streaming")

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)
    monkeypatch.setattr(provider, "_execute_stream_with_retry", should_not_stream)

    await provider.describe_url("https://example.com")
    await provider.rank_sources("query", "1. Source", 1)

    assert [payload["stream"] for payload in payloads] == [False, False]


@pytest.mark.asyncio
async def test_parse_completion_response_reads_json():
    """验证 JSON completion 响应正常解析"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    response = DummyResponse(
        text='{"choices":[{"message":{"content":"hello world"}}]}',
        json_data={"choices": [{"message": {"content": "hello world"}}]},
    )

    result = await provider._parse_completion_response(response)

    assert result == "hello world"


@pytest.mark.asyncio
async def test_parse_streaming_response_ignores_done_and_empty_stream_returns_empty():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")

    class StreamResponse:
        async def aiter_lines(self):
            for line in [
                'data: {"choices":[{"delta":{"content":"hello"}}]}',
                'data: {"choices":[{"delta":{"content":" world"}}]}',
                "data: [DONE]",
            ]:
                yield line

    class EmptyStreamResponse:
        async def aiter_lines(self):
            for line in ["", "data: [DONE]"]:
                yield line

    assert await provider._parse_streaming_response(StreamResponse()) == "hello world"
    assert await provider._parse_streaming_response(EmptyStreamResponse()) == ""


@pytest.mark.asyncio
async def test_responses_non_stream_iterates_heterogeneous_output_and_keeps_citations_structured():
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )
    response = DummyResponse(
        text="",
        json_data={
            "status": "completed",
            "output_text": "First answer.\n\nSecond answer.",
            "output": [
                {"type": "reasoning", "content": []},
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "First answer.",
                            "annotations": [{"type": "url_citation", "url": "https://example.com/one", "title": "One"}],
                        },
                        {"type": "refusal", "refusal": "ignored"},
                    ],
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Second answer.",
                            "annotations": [{"type": "url_citation", "url": "https://example.com/two", "title": "Two"}],
                        }
                    ],
                },
            ],
        },
    )

    result = await provider._parse_completion_response(response)

    answer, raw_sources = result.split("\n\nsources(", 1)
    assert answer == "First answer.\n\nSecond answer."
    assert answer.count("First answer.") == 1
    assert "https://example.com/one" in raw_sources
    assert "https://example.com/two" in raw_sources


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "marker"),
    [
        ({"status": "failed", "error": {"code": "server_error", "message": "upstream failed"}}, "failed"),
        ({"status": "cancelled"}, "cancelled"),
        ({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}, "incomplete"),
        ({"status": "completed", "output": []}, "without output_text"),
    ],
)
async def test_responses_non_stream_terminal_failures_are_not_successful(payload, marker):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )
    with pytest.raises(ProviderCallError, match=marker) as error:
        await provider._parse_completion_response(DummyResponse(text="", json_data=payload))

    assert error.value.error_type == "provider_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("require_web_search", [False, True])
async def test_responses_stream_uses_typed_events_and_terminal_response_as_authority(require_web_search):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
        tools=["web_search"],
        require_web_search=require_web_search,
    )

    class StreamResponse:
        async def aiter_lines(self):
            for line in [
                'data: {"type":"response.created","response":{"status":"in_progress"}}',
                'data: {"type":"response.output_text.delta","output_index":0,"content_index":0,"delta":"partial"}',
                'data: {"type":"response.output_text.annotation.added","annotation":{"type":"url_citation","url":"https://partial.example.com"}}',
                'data: {"type":"response.web_search_call.completed","item_id":"ws_1"}',
                'data: {"type":"response.completed","response":{"status":"completed","output":[{"type":"reasoning","content":[]},{"type":"message","content":[{"type":"output_text","text":"authoritative answer","annotations":[{"type":"url_citation","url":"https://final.example.com","title":"Final"}]}]}]}}',
            ]:
                yield line

    result = await provider._parse_streaming_response(StreamResponse(), require_web_search=require_web_search)

    assert result.startswith("authoritative answer")
    assert "partial" not in result.split("\n\nsources(", 1)[0]
    assert "https://final.example.com" in result
    assert "https://partial.example.com" not in result
    # The completed event names ws_1 and the terminal state does not contradict it.
    assert provider.last_web_search_verified is True
    assert provider.last_web_search_calls == [{"id": "ws_1", "status": "completed", "action": {}, "seen_in": "event"}]


@pytest.mark.asyncio
async def test_responses_stream_terminal_failure_and_malformed_events_are_structured_errors():
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )

    class FailedResponse:
        async def aiter_lines(self):
            yield 'data: {"type":"response.failed","response":{"status":"failed","error":{"message":"backend failed"}}}'

    class MalformedResponse:
        async def aiter_lines(self):
            yield "data: not-json"
            yield "data: [DONE]"

    with pytest.raises(ProviderCallError, match="failed") as failed:
        await provider._parse_streaming_response(FailedResponse())
    assert failed.value.error_type == "provider_error"

    with pytest.raises(ProviderCallError, match="Malformed") as malformed:
        await provider._parse_streaming_response(MalformedResponse())
    assert malformed.value.error_type == "parse_error"


@pytest.mark.asyncio
async def test_responses_stream_rejects_malformed_event_before_completed_response():
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )

    class StreamResponse:
        async def aiter_lines(self):
            yield "data: not-json"
            yield 'data: {"type":"response.completed","response":{"status":"completed","output":[{"type":"message","content":[{"type":"output_text","text":"should not be returned"}]}]}}'

    with pytest.raises(ProviderCallError, match="Malformed") as error:
        await provider._parse_streaming_response(StreamResponse())

    assert error.value.error_type == "parse_error"


@pytest.mark.asyncio
async def test_responses_stream_error_event_is_a_redacted_provider_error():
    secret = "test-key"
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        secret,
        "test-model",
        api_mode="responses",
    )

    class StreamResponse:
        async def aiter_lines(self):
            yield 'data: {"type":"error","message":"upstream rejected Bearer test-key"}'

    with pytest.raises(ProviderCallError, match="Responses stream error") as error:
        await provider._parse_streaming_response(StreamResponse())

    assert error.value.error_type == "provider_error"
    assert secret not in str(error.value)


@pytest.mark.asyncio
async def test_responses_stream_empty_terminal_falls_back_to_non_stream(monkeypatch):
    reset_openai_compatible_breakers()
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        stream=True,
        api_mode="responses",
    )
    payloads = []

    async def fake_stream(headers, payload, ctx):
        payloads.append(dict(payload))
        return ""

    async def fake_completion(headers, payload, ctx):
        payloads.append(dict(payload))
        return "non-stream answer"

    monkeypatch.setattr(provider, "_execute_stream_with_retry", fake_stream)
    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_completion)

    assert await provider.search("query") == "non-stream answer"
    assert [payload["stream"] for payload in payloads] == [True, False]
    assert [attempt["status"] for attempt in provider.last_transport_attempts] == ["empty", "ok"]
    assert all(attempt["api_mode"] == "responses" for attempt in provider.last_transport_attempts)


@pytest.mark.asyncio
async def test_stream_breakers_are_isolated_by_api_mode(monkeypatch):
    reset_openai_compatible_breakers()
    chat_provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=True)
    responses_provider = OpenAICompatibleSearchProvider(
        "https://api.example.com",
        "test-key",
        "test-model",
        stream=True,
        api_mode="responses",
    )
    calls = {"chat": 0, "responses": 0}

    async def empty_chat_stream(headers, payload, ctx):
        calls["chat"] += 1
        return ""

    async def responses_stream(headers, payload, ctx):
        calls["responses"] += 1
        return "responses answer"

    async def completion(headers, payload, ctx):
        return "chat fallback"

    monkeypatch.setattr(chat_provider, "_execute_stream_with_retry", empty_chat_stream)
    monkeypatch.setattr(chat_provider, "_execute_completion_with_retry", completion)
    monkeypatch.setattr(responses_provider, "_execute_stream_with_retry", responses_stream)
    monkeypatch.setattr(responses_provider, "_execute_completion_with_retry", completion)

    assert await chat_provider.search("one") == "chat fallback"
    assert await chat_provider.search("two") == "chat fallback"
    assert await chat_provider.search("three") == "chat fallback"
    assert await responses_provider.search("responses") == "responses answer"
    assert calls == {"chat": 2, "responses": 1}
    assert responses_provider.last_transport_attempts[0]["api_mode"] == "responses"


@pytest.mark.asyncio
async def test_parse_completion_response_appends_message_citations():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    response = DummyResponse(
        text="",
        json_data={
            "choices": [
                {
                    "message": {
                        "content": "hello world",
                        "citations": [{"url": "https://example.com/a", "title": "A"}],
                    }
                }
            ]
        },
    )

    result = await provider._parse_completion_response(response)

    assert "hello world" in result
    assert "sources(" in result
    assert "https://example.com/a" in result


@pytest.mark.asyncio
async def test_parse_completion_response_appends_top_level_citations():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    response = DummyResponse(
        text="",
        json_data={
            "citations": ["https://example.com/top"],
            "choices": [{"message": {"content": "hello world"}}],
        },
    )

    result = await provider._parse_completion_response(response)

    assert "hello world" in result
    assert "https://example.com/top" in result


# OpenAI's Chat Completions search models (gpt-5-search-api) nest each citation under "url_citation".
CHAT_ANSWER = (
    "Python 3.15.2 is the latest stable release. ([python.org](https://www.python.org/getit/?utm_source=openai))\n\n"
    "It was released on October 25, 2026. ([python.org](https://www.python.org/getit/?utm_source=openai))"
)
CHAT_ANNOTATION = {
    "type": "url_citation",
    "url_citation": {
        "start_index": 45,
        "end_index": 104,
        "title": "Download Python | Python.org",
        "url": "https://www.python.org/getit/?utm_source=openai",
    },
}
CHAT_SOURCES = [{"url": "https://www.python.org/getit/?utm_source=openai", "title": "Download Python | Python.org"}]


@pytest.mark.asyncio
async def test_parse_completion_response_keeps_nested_chat_annotations():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "gpt-5-search-api")
    data = {"choices": [{"message": {"role": "assistant", "content": CHAT_ANSWER, "annotations": [CHAT_ANNOTATION]}}]}

    result = await provider._parse_completion_response(DummyResponse(text=json.dumps(data), json_data=data))

    assert split_answer_and_sources(result) == (CHAT_ANSWER, CHAT_SOURCES)


@pytest.mark.asyncio
async def test_parse_streaming_response_keeps_chat_delta_annotations():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "gpt-5-search-api")
    first, second = CHAT_ANSWER[:50], CHAT_ANSWER[50:]

    class StreamResponse:
        async def aiter_lines(self):
            for chunk in (
                {"choices": [{"delta": {"role": "assistant", "content": "", "refusal": None}}]},
                {"choices": [{"delta": {"content": first}}]},
                {"choices": [{"delta": {"annotations": [CHAT_ANNOTATION, CHAT_ANNOTATION]}}]},
                {"choices": [{"delta": {"content": second}}]},
            ):
                yield "data: " + json.dumps(chunk)
            yield "data: [DONE]"

    result = await provider._parse_streaming_response(StreamResponse())

    assert split_answer_and_sources(result) == (CHAT_ANSWER, CHAT_SOURCES)


@pytest.mark.asyncio
async def test_parse_completion_response_falls_back_to_sse():
    """验证 JSON 解析失败时 fallback 到 SSE 文本解析"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    response = DummyResponse(
        text=(
            'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
            'data: [DONE]\n'
        ),
        json_error=ValueError("not json"),
    )

    result = await provider._parse_completion_response(response)

    assert result == "hello world"


@pytest.mark.asyncio
async def test_parse_completion_response_empty_choices():
    """验证空 choices 返回空字符串"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    response = DummyResponse(
        text='{"choices":[]}',
        json_data={"choices": []},
    )

    result = await provider._parse_completion_response(response)

    assert result == ""


@pytest.mark.asyncio
async def test_parse_completion_response_null_content():
    """验证 content 为 null 时返回空字符串"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    response = DummyResponse(
        text='{"choices":[{"message":{"content":null}}]}',
        json_data={"choices": [{"message": {"content": None}}]},
    )

    result = await provider._parse_completion_response(response)

    assert result == ""


@pytest.mark.asyncio
async def test_build_api_headers():
    """验证 headers 包含 Accept 和 User-Agent"""
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    headers = provider._build_api_headers()

    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"
    assert "text/event-stream" in headers["Accept"]
    assert headers["User-Agent"].startswith("smart-search/")


# ─── SSL verification tests ─────────────────────────────────────────────────


def test_ssl_verify_default():
    """验证 ssl_verify_enabled 默认为 True"""
    from smart_search.config import Config
    c = Config.__new__(Config)
    c._config_file = None
    c._cached_model = None
    assert c.ssl_verify_enabled is True


def test_ssl_verify_disabled(monkeypatch):
    """验证 SSL_VERIFY=false 时 ssl_verify_enabled 为 False"""
    monkeypatch.setenv("SSL_VERIFY", "false")
    from smart_search.config import Config
    c = Config.__new__(Config)
    c._config_file = None
    c._cached_model = None
    assert c.ssl_verify_enabled is False


def test_ssl_verify_disabled_zero(monkeypatch):
    """验证 SSL_VERIFY=0 时 ssl_verify_enabled 为 False"""
    monkeypatch.setenv("SSL_VERIFY", "0")
    from smart_search.config import Config
    c = Config.__new__(Config)
    c._config_file = None
    c._cached_model = None
    assert c.ssl_verify_enabled is False


@pytest.mark.asyncio
async def test_get_ssl_verify_returns_config_value(monkeypatch):
    """验证 _get_ssl_verify 返回 config 中的 ssl_verify_enabled"""
    import smart_search.providers.openai_compatible as provider_mod
    provider_mod._ssl_warning_emitted = False

    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")

    monkeypatch.setenv("SSL_VERIFY", "true")
    assert provider._get_ssl_verify() is True

    provider_mod._ssl_warning_emitted = False
    monkeypatch.setenv("SSL_VERIFY", "false")
    assert provider._get_ssl_verify() is False


@pytest.mark.asyncio
async def test_ssl_warning_emitted_once(monkeypatch, caplog):
    """验证禁用 SSL 时警告仅打印一次"""
    import logging
    import smart_search.providers.openai_compatible as provider_mod
    provider_mod._ssl_warning_emitted = False

    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    monkeypatch.setenv("SSL_VERIFY", "false")

    with caplog.at_level(logging.WARNING, logger="smart_search.providers.openai_compatible"):
        provider._get_ssl_verify()
        provider._get_ssl_verify()

    warning_count = sum(1 for r in caplog.records if "SSL_VERIFY=false" in r.message)
    assert warning_count == 1


def test_request_read_timeout_follows_the_shared_deadline(monkeypatch):
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    provider.set_search_deadline(time.monotonic() + 280.0)

    timeout = provider._request_timeout()

    # The shared main_search deadline is the only ceiling; a slow reasoning model
    # must not be cut off by a second, smaller read cap.
    assert timeout.read > 240.0
    assert timeout.connect == 6.0
    assert timeout.write == 10.0


def test_standalone_request_read_timeout_uses_the_configured_budget(monkeypatch):
    from smart_search.providers.openai_compatible import config

    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    monkeypatch.setenv("SMART_SEARCH_TIMEOUT_SECONDS", "450")

    assert provider._request_timeout().read == 450.0
    assert config.search_timeout == 450.0

    monkeypatch.setenv("SMART_SEARCH_TIMEOUT_SECONDS", "not-a-number")

    # An invalid saved budget must not turn into a transport error here.
    assert provider._request_timeout().read == 300.0


def test_short_deadline_still_shrinks_every_timeout_component():
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model")
    provider.set_search_deadline(time.monotonic() + 2.0)

    timeout = provider._request_timeout()

    assert timeout.read <= 2.0
    assert timeout.connect <= 2.0
    assert timeout.write <= 2.0


@pytest.mark.asyncio
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("delay,expected_requests", [(0.1, 1), (0, 4)])
async def test_openai_retry_stops_after_slow_failure(monkeypatch, stream, delay, expected_requests):
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
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "test-model", stream=stream)
    execute = provider._execute_stream_with_retry if stream else provider._execute_completion_with_retry
    with pytest.raises(httpx.HTTPStatusError):
        await execute({}, {"stream": stream})

    assert len(requests) == expected_requests


@pytest.mark.asyncio
async def test_chat_stream_done_returns_without_eof(monkeypatch):
    import smart_search.providers.openai_compatible as provider_mod

    monkeypatch.setattr(provider_mod, "_STREAM_BREAKERS", {})
    never = asyncio.Event()

    class OpenEndedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n'
            yield b'data: {"choices":[{"delta":{"content":" world"}}]}\n\n'
            yield b'data: [DONE]\n\n'
            await never.wait()

    async def handler(request):
        return httpx.Response(200, headers={"Content-Type": "text/event-stream"}, stream=OpenEndedStream())

    original_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    provider = OpenAICompatibleSearchProvider("https://api.example.com", "test-key", "done-test-model", stream=True)

    result = await asyncio.wait_for(provider.search("query"), 2)

    assert result == "Hello world"
    assert [attempt["transport"] for attempt in provider.last_transport_attempts] == ["stream"]


# ---- OPENAI_COMPATIBLE_REQUIRE_WEB_SEARCH at the HTTP boundary -------------------------------
# Off (the default) behaves like a plain Responses request with tools: no tool_choice, and a
# missing tool item never rejects an answer; the attempt only reports web_search_verified.
# On, the request forces the tool and the answer needs a completed call.

_CITED_ANSWER = {"type": "message", "content": [{"type": "output_text", "text": "A cited answer.",
                 "annotations": [{"type": "url_citation", "url": "https://e.org/source", "title": "Source"}]}]}
_WS_COMPLETED_EVENT = {"type": "response.web_search_call.completed", "item_id": "ws_1", "output_index": 0}
_WEB_SEARCH_SCENARIOS = {
    # name: (stream-only events, terminal output, expected verified, expected recorded statuses)
    "citations_only": ([], [_CITED_ANSWER], False, []),
    "completed_event_only": ([{"type": "response.web_search_call.in_progress", "item_id": "ws_1", "output_index": 0},
                              _WS_COMPLETED_EVENT], [_CITED_ANSWER], True, ["completed"]),
    "explicit_failed": ([_WS_COMPLETED_EVENT], [{"type": "web_search_call", "id": "ws_1", "status": "failed"},
                                                _CITED_ANSWER], False, ["failed"]),
    "failed_item_after_completed_event": ([_WS_COMPLETED_EVENT, {"type": "response.output_item.done", "output_index": 0,
                                           "item": {"type": "web_search_call", "id": "ws_1", "status": "failed"}}],
                                          [_CITED_ANSWER], False, ["failed"]),
    "completed_tool_item": ([{"type": "response.output_item.done", "output_index": 0,
                              "item": {"type": "web_search_call", "id": "ws_1", "status": "completed", "action": {"type": "search"}}}],
                            [{"type": "web_search_call", "id": "ws_1", "status": "completed", "action": {"type": "search"}},
                             _CITED_ANSWER], True, ["completed"]),
}


def _sse(events):
    return "".join("data: " + json.dumps(event) + "\n\n" for event in events)


def _relay(monkeypatch, respond):
    reset_openai_compatible_breakers()
    bodies = []
    original = httpx.AsyncClient

    def handler(request):
        body = json.loads(request.content)
        bodies.append(body)
        return respond(body)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    return bodies


@pytest.mark.asyncio
@pytest.mark.parametrize("require", [False, True])
@pytest.mark.parametrize(("scenario", "transport"), [
    (scenario, transport) for scenario in sorted(_WEB_SEARCH_SCENARIOS) for transport in ("json", "sse_in_non_stream", "stream")
    # A JSON body has no stream events, so event-only evidence is an SSE case.
    if transport != "json" or scenario in {"citations_only", "explicit_failed", "completed_tool_item"}
])
async def test_web_search_verification_policy_correlates_events_with_terminal_state(monkeypatch, scenario, transport, require):
    events, terminal_output, verified, statuses = _WEB_SEARCH_SCENARIOS[scenario]

    def respond(body):
        terminal = {"status": "completed", "output": terminal_output}
        if transport == "json":
            return httpx.Response(200, json=terminal)
        return httpx.Response(200, text=_sse([*events, {"type": "response.completed", "response": terminal}]))

    bodies = _relay(monkeypatch, respond)
    provider = OpenAICompatibleSearchProvider("https://relay.example/v1", "dummy", "sol", transport == "stream", "responses",
                                              tools=["web_search"], require_web_search=require)
    if verified or not require:
        assert "A cited answer" in await provider.search("current fact")
    else:
        with pytest.raises(ProviderCallError, match="did not complete a web_search_call") as raised:
            await provider.search("current fact")
        assert raised.value.error_type == "quality_error"

    assert [body.get("tool_choice") for body in bodies] == ["required" if require else None]
    attempt = provider.last_transport_attempts[-1]
    assert attempt["status"] == ("ok" if verified or not require else "error")
    assert (attempt["web_search_verified"], attempt["web_search_required"]) == (verified, require)
    assert [call["status"] for call in attempt.get("web_search_calls", [])] == statuses


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 422])
@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("require", [False, True])
async def test_relay_rejecting_tool_choice_is_a_parameter_error_only_when_opted_in(monkeypatch, status, stream, require):
    def respond(body):
        if "tool_choice" in body:
            return httpx.Response(status, json={"error": {"message": "Unknown parameter: 'tool_choice'.", "param": "tool_choice"}})
        terminal = {"status": "completed", "output": [_CITED_ANSWER]}
        if body["stream"]:
            return httpx.Response(200, text=_sse([{"type": "response.completed", "response": terminal}]))
        return httpx.Response(200, json=terminal)

    bodies = _relay(monkeypatch, respond)
    provider = OpenAICompatibleSearchProvider("https://relay.example/v1", "secret-key", "sol", stream, "responses",
                                              tools=["web_search"], require_web_search=require)
    if not require:
        # The same request as before tool_choice existed: this relay keeps answering, unverified.
        assert "A cited answer" in await provider.search("current fact")
        assert all("tool_choice" not in body for body in bodies)
        assert provider.last_transport_attempts[-1]["web_search_verified"] is False
        return
    with pytest.raises(ProviderCallError) as raised:
        await provider.search("current fact")
    assert raised.value.error_type == "parameter_error"
    assert f"HTTP {status}" in raised.value.error and "tool_choice" in raised.value.error
    assert "OPENAI_COMPATIBLE_REQUIRE_WEB_SEARCH=false" in raised.value.error
    assert "secret-key" not in raised.value.error
    assert len(bodies) == 1  # a 4xx is not retried and does not fall back to another transport
    assert provider.last_transport_attempts[-1]["error_type"] == "parameter_error"


@pytest.mark.asyncio
async def test_other_4xx_without_tool_choice_keeps_its_plain_classification(monkeypatch):
    _relay(monkeypatch, lambda body: httpx.Response(400, json={"error": {"message": "bad model"}}))
    provider = OpenAICompatibleSearchProvider("https://relay.example/v1", "dummy", "sol", False, "responses", tools=["web_search"])
    with pytest.raises(httpx.HTTPStatusError):
        await provider.search("current fact")


@pytest.mark.asyncio
async def test_synthesis_never_carries_search_tools_even_when_verification_is_required(monkeypatch):
    bodies = _relay(monkeypatch, lambda body: httpx.Response(200, json={"status": "completed", "output_text": "From evidence."}))
    provider = OpenAICompatibleSearchProvider("https://relay.example/v1", "dummy", "sol", api_mode="responses",
                                              tools=["web_search"], require_web_search=True)
    assert await provider.synthesize("q", []) == "From evidence."
    assert "tools" not in bodies[0] and "tool_choice" not in bodies[0]
    assert "web_search_verified" not in provider.last_transport_attempts[-1]
