import json

import httpx
import pytest

from smart_search.providers.zhipu_mcp import ZhipuMCPProvider


class FakeZhipuMCPClient:
    calls = []
    response: httpx.Response | None = None
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
        return self.__class__.response


@pytest.fixture(autouse=True)
def reset_fake_client():
    FakeZhipuMCPClient.calls = []
    FakeZhipuMCPClient.response = None
    FakeZhipuMCPClient.exception = None


@pytest.mark.asyncio
async def test_zhipu_mcp_web_search_calls_tool_and_parses_results(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "### 1. Result\n- **URL**: https://example.com\nSnippet",
                    }
                ]
            },
        },
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/web_search_prime/mcp", "zmcp-secret")
    data = json.loads(await provider.web_search("query", count=2))

    assert data["ok"] is True
    assert data["provider"] == "zhipu-mcp"
    assert data["tool"] == "web_search_prime"
    assert data["results"][0]["url"] == "https://example.com"
    call = FakeZhipuMCPClient.calls[0]
    assert call["headers"]["Authorization"] == "Bearer zmcp-secret"
    assert call["json"]["method"] == "tools/call"
    assert call["json"]["params"]["name"] == "web_search_prime"
    assert call["json"]["params"]["arguments"] == {"search_query": "query"}


@pytest.mark.asyncio
async def test_zhipu_mcp_reader_returns_content(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "# Page"}]}},
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/web_reader/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/web_reader/mcp", "zmcp-secret", provider_id="zhipu-mcp-reader")
    data = json.loads(await provider.web_reader("https://example.com"))

    assert data["ok"] is True
    assert data["provider"] == "zhipu-mcp-reader"
    assert data["tool"] == "webReader"
    assert data["content"] == "# Page"
    assert FakeZhipuMCPClient.calls[0]["json"]["params"]["arguments"] == {"url": "https://example.com"}


@pytest.mark.asyncio
async def test_zhipu_mcp_reader_json_error_text_is_provider_error(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": '"{\\"error\\":\\"fetch failed\\"}"'}]},
        },
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/web_reader/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/web_reader/mcp", "zmcp-secret", provider_id="zhipu-mcp-reader")
    data = json.loads(await provider.web_reader("https://example.com"))

    assert data["ok"] is False
    assert data["error_type"] == "provider_error"
    assert data["error"] == "fetch failed"


@pytest.mark.asyncio
async def test_zhipu_mcp_content_mcp_401_is_auth_error(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        200,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": "MCP error -401: Api key not found"}]},
        },
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/web_search_prime/mcp", "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "Api key not found" in data["error"]


@pytest.mark.asyncio
async def test_zhipu_mcp_zread_tools_send_expected_arguments(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        200,
        json={"jsonrpc": "2.0", "id": 1, "result": {"content": [{"type": "text", "text": "ok"}]}},
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/zread/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/zread/mcp", "zmcp-secret", provider_id="zhipu-mcp-zread")
    await provider.search_doc("owner/repo", "install", max_results=3)
    await provider.get_repo_structure("owner/repo", ref="main")
    await provider.read_file("owner/repo", "README.md", ref="main")

    assert [call["json"]["params"]["name"] for call in FakeZhipuMCPClient.calls] == [
        "search_doc",
        "get_repo_structure",
        "read_file",
    ]
    assert FakeZhipuMCPClient.calls[0]["json"]["params"]["arguments"] == {
        "repo_name": "owner/repo",
        "query": "install",
    }
    assert FakeZhipuMCPClient.calls[2]["json"]["params"]["arguments"] == {
        "repo_name": "owner/repo",
        "file_path": "README.md",
    }


@pytest.mark.asyncio
async def test_zhipu_mcp_http_401_is_auth_error(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        401,
        text="invalid token",
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/web_search_prime/mcp", "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is False
    assert data["error_type"] == "auth_error"
    assert "HTTP 401" in data["error"]
    assert "zmcp-secret" not in data["error"]


@pytest.mark.asyncio
async def test_zhipu_mcp_sse_response_is_parsed(monkeypatch):
    FakeZhipuMCPClient.response = httpx.Response(
        200,
        text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"### Result\\nhttps://example.com"}]}}\n\n',
        headers={"content-type": "text/event-stream"},
        request=httpx.Request("POST", "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"),
    )
    monkeypatch.setattr("smart_search.providers.zhipu_mcp.httpx.AsyncClient", FakeZhipuMCPClient)

    provider = ZhipuMCPProvider("https://open.bigmodel.cn/api/mcp/web_search_prime/mcp", "zmcp-secret")
    data = json.loads(await provider.web_search("query"))

    assert data["ok"] is True
    assert data["results"][0]["url"] == "https://example.com"
