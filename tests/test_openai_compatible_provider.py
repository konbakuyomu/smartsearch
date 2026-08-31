import asyncio
import httpx
import pytest
import time

from smart_search.providers.openai_compatible import OpenAICompatibleSearchProvider, reset_openai_compatible_breakers
from smart_search.provider_errors import ProviderCallError


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
async def test_responses_mode_fetch_describe_and_rank_use_non_stream_responses_payloads(monkeypatch):
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

    assert await provider.fetch("https://example.com/page") == "fetched content"
    assert (await provider.describe_url("https://example.com"))["title"] == "Example"
    assert await provider.rank_sources("query", "1. Source", 1) == [1]
    assert len(payloads) == 3
    assert all(payload["stream"] is False for payload in payloads)
    assert all("instructions" in payload and "input" in payload for payload in payloads)
    assert all("messages" not in payload and "tools" not in payload for payload in payloads)


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
async def test_responses_stream_uses_typed_events_and_terminal_response_as_authority():
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
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

    result = await provider._parse_streaming_response(StreamResponse())

    assert result.startswith("authoritative answer")
    assert "partial" not in result.split("\n\nsources(", 1)[0]
    assert "https://final.example.com" in result
    assert "https://partial.example.com" not in result


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
