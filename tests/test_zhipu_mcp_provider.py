import json

import httpx
import pytest

from smart_search.providers.zhipu_mcp import ZhipuMCPProvider


class FakeZhipuMCPClient:
    calls = []
    response: httpx.Response | None = None
    responses: list[httpx.Response] = []
    exception: Exception | None = None

    def __init__(self, timeout, follow_redirects=True):
        self.timeout = timeout
        self.follow_redirects = follow_redirects

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, headers, json):
        self.__class__.calls.append({"url": url, "headers": headers, "json": json, "timeout": self.timeout})
        if self.__class__.exception:
            raise self.__class__.exception
        if self.__class__.responses:
            return self.__class__.responses.pop(0)
        return self.__class__.response


@pytest.fixture(autouse=True)
def reset_fake_client():
    FakeZhipuMCPClient.calls = []
    FakeZhipuMCPClient.response = None
    FakeZhipuMCPClient.responses = []
    FakeZhipuMCPClient.exception = None


def _request(url: str) -> httpx.Request:
    return httpx.Request("POST", url)


def _initialize_response(url: str, session_id: str = "zmcp-session") -> httpx.Response:
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2024-11-05"}},
        headers={"Mcp-Session-Id": session_id},
        request=_request(url),
    )


@pytest.mark.asyncio
async def test_zhipu_mcp_web_search_calls_tool_and_parses_results(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": "### 1. Result\n- **URL**: https://example.com\nSnippet",
                        }
                    ]
                },
            },
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query", count=2))

    assert data["ok"] is True
    assert data["provider"] == "zhipu-mcp"
    assert data["tool"] == "web_search_prime"
    assert data["results"][0]["url"] == "https://example.com"
    initialize_call = FakeZhipuMCPClient.calls[0]
    assert initialize_call["headers"]["Authorization"] == "Bearer zmcp-secret"
    assert initialize_call["json"]["method"] == "initialize"
    assert initialize_call["json"]["params"]["protocolVersion"] == "2024-11-05"
    call = FakeZhipuMCPClient.calls[1]
    assert call["headers"]["Authorization"] == "Bearer zmcp-secret"
    assert call["headers"]["Mcp-Session-Id"] == "zmcp-session"
    assert call["json"]["method"] == "tools/call"
    assert call["json"]["params"]["name"] == "web_search_prime"
    assert call["json"]["params"]["arguments"] == {"search_query": "query"}


@pytest.mark.asyncio
async def test_zhipu_mcp_reader_returns_content(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_reader/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "# Page"}]}},
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret", provider_id="zhipu-mcp-reader")
    data = json.loads(await provider.web_reader("https://example.com"))

    assert data["ok"] is True
    assert data["provider"] == "zhipu-mcp-reader"
    assert data["tool"] == "webReader"
    assert data["content"] == "# Page"
    assert FakeZhipuMCPClient.calls[1]["headers"]["Mcp-Session-Id"] == "zmcp-session"
    assert FakeZhipuMCPClient.calls[1]["json"]["params"]["arguments"] == {"url": "https://example.com"}


@pytest.mark.asyncio
async def test_zhipu_mcp_reader_json_error_text_is_provider_error(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_reader/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": '"{\\"error\\":\\"fetch failed\\"}"'}]},
            },
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret", provider_id="zhipu-mcp-reader")
    data = json.loads(await provider.web_reader("https://example.com"))

    assert data["ok"] is False
    assert data["error_type"] == "provider_error"
    assert data["error"] == "fetch failed"


@pytest.mark.asyncio
async def test_zhipu_mcp_content_mcp_401_is_auth_error(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "MCP error -401: Api key not found"}]},
            },
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "Api key not found" in data["error"]


@pytest.mark.asyncio
async def test_zhipu_mcp_tool_error_redacts_credentials(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    leaked_secret = "zmcp-secret"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": f"MCP error -401: upstream repeated {leaked_secret}",
                        }
                    ],
                },
            },
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    rendered = json.dumps(data)
    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert leaked_secret not in rendered
    assert "[REDACTED]" in data["error"]
    assert data["content"] == data["error"]
    assert data["raw_content"] == data["error"]


@pytest.mark.asyncio
async def test_zhipu_mcp_zread_tools_send_expected_arguments(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/zread/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": "ok"}]}},
            request=_request(url),
        ),
        httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 3, "result": {"content": [{"type": "text", "text": "ok"}]}},
            request=_request(url),
        ),
        httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 4, "result": {"content": [{"type": "text", "text": "ok"}]}},
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret", provider_id="zhipu-mcp-zread")
    await provider.search_doc("owner/repo", "install", max_results=3)
    await provider.get_repo_structure("owner/repo", ref="main")
    await provider.read_file("owner/repo", "README.md", ref="main")

    assert [call["json"]["method"] for call in FakeZhipuMCPClient.calls] == [
        "initialize",
        "tools/call",
        "tools/call",
        "tools/call",
    ]
    assert [call["json"]["params"]["name"] for call in FakeZhipuMCPClient.calls[1:]] == [
        "search_doc",
        "get_repo_structure",
        "read_file",
    ]
    assert all(call["headers"]["Mcp-Session-Id"] == "zmcp-session" for call in FakeZhipuMCPClient.calls[1:])
    assert FakeZhipuMCPClient.calls[0]["json"]["method"] == "initialize"
    assert FakeZhipuMCPClient.calls[1]["json"]["params"]["arguments"] == {
        "repo_name": "owner/repo",
        "query": "install",
    }
    assert FakeZhipuMCPClient.calls[3]["json"]["params"]["arguments"] == {
        "repo_name": "owner/repo",
        "file_path": "README.md",
    }


@pytest.mark.asyncio
async def test_zhipu_mcp_http_401_is_auth_error(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            401,
            text="invalid token",
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "HTTP 401" in data["error"]
    assert "zmcp-secret" not in data["error"]


@pytest.mark.asyncio
async def test_zhipu_mcp_initialize_401_is_auth_error(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    FakeZhipuMCPClient.responses = [
        httpx.Response(
            401,
            text="invalid token",
            request=_request(url),
        )
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "HTTP 401" in data["error"]
    assert "zmcp-secret" not in data["error"]
    assert [call["json"]["method"] for call in FakeZhipuMCPClient.calls] == ["initialize"]


@pytest.mark.asyncio
async def test_zhipu_mcp_initialize_without_session_header_is_provider_error(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    FakeZhipuMCPClient.responses = [
        httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {}},
            request=_request(url),
        )
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is False
    assert data["error_type"] == "provider_error"
    assert "Mcp-Session-Id" in data["error"]
    assert [call["json"]["method"] for call in FakeZhipuMCPClient.calls] == ["initialize"]


@pytest.mark.asyncio
async def test_zhipu_mcp_sse_response_is_parsed(monkeypatch):
    url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
    FakeZhipuMCPClient.responses = [
        _initialize_response(url),
        httpx.Response(
            200,
            text='event: message\ndata: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":"### Result\\nhttps://example.com"}]}}\n\n',
            headers={"content-type": "text/event-stream"},
            request=_request(url),
        ),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider(url, "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is True
    assert data["results"][0]["url"] == "https://example.com"


# ---- web_search_prime JSON results (issue #84) -------------------------------

SEARCH_URL = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"


def _search_items(count: int = 9) -> list[dict]:
    items = []
    for index in range(count):
        item = {
            "title": f"Result {index}",
            "link": f"https://example.com/page-{index}?q=a%20b",
            "content": f"Snippet {index}",
            "refer": f"ref_{index + 1}",
        }
        if index == 0:
            item.update(publish_date="2026-10-01", media="IRS")
        items.append(item)
    return items


def _search_response(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 2, "result": {"content": [{"type": "text", "text": text}]}},
        request=_request(SEARCH_URL),
    )


async def _search_with_text(monkeypatch, text: str, tool: str = "web_search") -> dict:
    FakeZhipuMCPClient.responses = [_initialize_response(SEARCH_URL), _search_response(text)]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)
    provider = ZhipuMCPProvider(SEARCH_URL, "zmcp-secret")
    if tool == "search_doc":
        return json.loads(await provider.search_doc("owner/repo", "install"))
    return json.loads(await provider.web_search("IRS ITIN renewal"))


@pytest.mark.asyncio
@pytest.mark.parametrize("layers", [1, 2])
async def test_zhipu_mcp_web_search_parses_json_results(monkeypatch, layers):
    text = json.dumps(_search_items(), ensure_ascii=False)
    if layers == 2:  # The Coding Plan endpoint wraps the array in one more JSON string.
        text = json.dumps(text, ensure_ascii=False)

    data = await _search_with_text(monkeypatch, text)

    assert data["ok"] is True
    assert data["total"] == 9
    assert [item["url"] for item in data["results"]] == [f"https://example.com/page-{i}?q=a%20b" for i in range(9)]
    first = data["results"][0]
    assert first["title"] == "Result 0"
    assert first["description"] == "Snippet 0"
    assert first["published_date"] == "2026-10-01"
    assert first["source"] == "IRS"
    assert first["refer"] == "ref_1"
    assert first["provider"] == "zhipu-mcp"
    assert data["raw_content"] == text


@pytest.mark.asyncio
async def test_zhipu_mcp_web_search_skips_items_without_a_usable_link(monkeypatch):
    items = [
        "not an object",
        {"title": "no link", "content": "x"},
        {"title": "blank link", "link": "   ", "url": "https://example.com/fallback"},
        {"title": "ftp", "link": "ftp://example.com/file"},
        {"title": "", "link": " https://example.com/trimmed "},
        {"title": 3, "link": "https://example.com/odd-title", "content": None},
    ]

    data = await _search_with_text(monkeypatch, json.dumps(items))

    assert data["ok"] is True
    assert [item["url"] for item in data["results"]] == [
        "https://example.com/fallback", "https://example.com/trimmed", "https://example.com/odd-title"]
    assert data["results"][1]["title"] == "https://example.com/trimmed"
    assert data["results"][2]["description"] == ""


@pytest.mark.asyncio
async def test_zhipu_mcp_web_search_empty_array_is_zero_results(monkeypatch):
    data = await _search_with_text(monkeypatch, "[]")

    assert data["ok"] is True
    assert data["total"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ['[{"title": "cut off", "link": "https://example.com', '"[{\\"title\\": ', '{"items": []}'])
async def test_zhipu_mcp_web_search_malformed_or_unknown_json_is_parse_error(monkeypatch, text):
    data = await _search_with_text(monkeypatch, text)

    assert data["ok"] is False
    assert data["error_type"] == "parse_error"
    assert data["results"] == []
    assert "zmcp-secret" not in json.dumps(data)


@pytest.mark.asyncio
async def test_zhipu_mcp_web_search_double_encoded_error_stays_provider_error(monkeypatch):
    data = await _search_with_text(monkeypatch, json.dumps(json.dumps({"error": "quota exceeded"})))

    assert data["ok"] is False
    assert data["error_type"] == "provider_error"
    assert "quota exceeded" in data["error"]


@pytest.mark.asyncio
async def test_zhipu_mcp_markdown_results_still_parse_and_stop_urls_at_quotes(monkeypatch):
    text = '## Result\n- **URL**: https://example.com/a","content":"tail\n[Docs](https://example.com/b)'

    data = await _search_with_text(monkeypatch, text)

    assert data["ok"] is True
    assert data["results"][0]["url"] == "https://example.com/a"


@pytest.mark.asyncio
async def test_zread_output_keeps_the_markdown_path(monkeypatch):
    # Only web_search_prime returns the JSON array; other tools keep their text parsing.
    data = await _search_with_text(monkeypatch, "[Install](https://example.com/install)", tool="search_doc")

    assert data["ok"] is True
    assert data["results"][0]["url"] == "https://example.com/install"


@pytest.mark.asyncio
async def test_ordinary_search_receives_the_full_original_urls(monkeypatch):
    from smart_search import jev_search, service

    monkeypatch.setenv("ZHIPU_MCP_API_KEY", "zmcp-secret")
    monkeypatch.setenv("ZHIPU_MCP_ENABLED", "true")
    FakeZhipuMCPClient.responses = [
        _initialize_response(SEARCH_URL),
        _search_response(json.dumps(json.dumps(_search_items(3)))),
    ]
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    data = await service.zhipu_mcp_search("IRS ITIN renewal", count=3)
    sources = jev_search._normalize_results(data["results"], "zhipu-mcp", "search")

    assert [source["url"] for source in sources] == [f"https://example.com/page-{i}?q=a%20b" for i in range(3)]
    assert sources[0]["content"] == "Snippet 0"
    assert sources[0]["published_date"] == "2026-10-01"


@pytest.mark.asyncio
async def test_zhipu_mcp_json_encoded_markdown_text_is_parsed_as_markdown(monkeypatch):
    data = await _search_with_text(monkeypatch, json.dumps("### Result\nhttps://example.com/quoted"))

    assert data["ok"] is True
    assert data["results"][0]["url"] == "https://example.com/quoted"
