import httpx
import pytest

from smart_search.providers.openai_compatible import OpenAICompatibleSearchProvider, reset_openai_compatible_breakers


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
async def test_search_responses_mode_uses_responses_payload(monkeypatch):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )
    captured = {}

    async def fake_execute(headers, payload, ctx):
        captured["payload"] = payload
        return "ok"

    monkeypatch.setattr(provider, "_execute_completion_with_retry", fake_execute)

    result = await provider.search("current release notes", platform="github.com")

    assert result == "ok"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["instructions"]
    assert captured["payload"]["input"][0]["role"] == "user"
    assert "current release notes" in captured["payload"]["input"][0]["content"]
    assert "github.com" in captured["payload"]["input"][0]["content"]
    assert captured["payload"]["stream"] is False
    assert "messages" not in captured["payload"]
    assert "tools" not in captured["payload"]


@pytest.mark.asyncio
async def test_responses_mode_posts_to_responses_endpoint(monkeypatch):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )
    captured = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            captured["url"] = url
            captured["payload"] = json
            return httpx.Response(
                200,
                json={"output": [{"content": [{"type": "output_text", "text": "ok"}]}]},
                request=httpx.Request("POST", url),
            )

    monkeypatch.setattr("smart_search.providers.openai_compatible.httpx.AsyncClient", FakeAsyncClient)

    result = await provider.search("ping")

    assert result == "ok"
    assert captured["url"] == "https://api.example.com/v1/responses"
    assert captured["payload"]["stream"] is False


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
async def test_responses_mode_fetch_describe_and_rank_use_responses_payloads(monkeypatch):
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
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
    assert all("input" in payload and "instructions" in payload for payload in payloads)
    assert all("messages" not in payload for payload in payloads)
    assert all(payload["stream"] is False for payload in payloads)


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
async def test_parse_responses_streaming_response_reads_deltas_and_citations():
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )

    class StreamResponse:
        async def aiter_lines(self):
            for line in [
                "event: response.output_text.delta",
                'data: {"type":"response.output_text.delta","delta":"hello"}',
                "event: response.output_text.delta",
                'data: {"type":"response.output_text.delta","delta":" world"}',
                "event: response.completed",
                'data: {"type":"response.completed","response":{"output":[{"content":[{"type":"output_text","text":"hello world","annotations":[{"type":"url_citation","url":"https://example.com/a","title":"A"}]}]}]}}',
            ]:
                yield line

    result = await provider._parse_streaming_response(StreamResponse())

    assert result.startswith("hello world")
    assert "https://example.com/a" in result


@pytest.mark.asyncio
async def test_parse_responses_completion_reads_output_and_citations():
    provider = OpenAICompatibleSearchProvider(
        "https://api.example.com/v1",
        "test-key",
        "test-model",
        api_mode="responses",
    )
    response = DummyResponse(
        text="",
        json_data={
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": "hello world",
                            "annotations": [
                                {"type": "url_citation", "url": "https://example.com/a", "title": "A"}
                            ],
                        }
                    ]
                }
            ]
        },
    )

    result = await provider._parse_completion_response(response)

    assert result.startswith("hello world")
    assert "https://example.com/a" in result


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
