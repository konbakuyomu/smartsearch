from __future__ import annotations

import json

import httpx
import pytest

from smart_search import service
from smart_search.providers.specstream import SpecStreamFetchProvider, SpecStreamSearchProvider


@pytest.mark.asyncio
async def test_specstream_search_provider_normalizes_sources(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "sources": [
                        {
                            "title": "Example Docs",
                            "url": "https://example.com/docs",
                            "snippet": "Short snippet",
                            "excerpt": "Verified excerpt text",
                            "source": "example.com",
                            "published": "2026-11-20",
                        }
                    ]
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = SpecStreamSearchProvider("https://api.specstream.ai/v1/web-search", "ss-secret", 30.0)
    raw = await provider.search("example docs", max_results=4)
    data = json.loads(raw)

    assert data["ok"] is True
    assert data["provider"] == "specstream"
    assert captured["headers"]["Authorization"] == "Bearer ss-secret"
    assert captured["json"] == {"q": "example docs", "num": 4, "passages": True}
    assert len(data["results"]) == 1
    assert data["results"][0]["description"] == "Verified excerpt text"
    assert data["results"][0]["source"] == "example.com"


@pytest.mark.asyncio
async def test_specstream_fetch_provider_extracts_content(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "results": [
                        {
                            "url": "https://example.com/article",
                            "ok": True,
                            "title": "Article",
                            "text": "Clean page content.",
                        }
                    ]
                },
            )

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    provider = SpecStreamFetchProvider("https://api.specstream.ai/v1/extract", "ss-secret", 30.0)
    raw = await provider.fetch("https://example.com/article")
    data = json.loads(raw)

    assert data["ok"] is True
    assert data["provider"] == "specstream"
    assert data["title"] == "Article"
    assert data["content"] == "Clean page content."
    assert captured["json"] == {"urls": ["https://example.com/article"]}


@pytest.mark.asyncio
async def test_service_fetch_uses_specstream_when_only_configured_provider(monkeypatch):
    monkeypatch.setenv("SPECSTREAM_API_KEY", "ss-secret")
    for k in ("TAVILY_API_KEY", "JINA_API_KEY", "ZHIPU_MCP_API_KEY", "FIRECRAWL_API_KEY", "TINYFISH_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(k, raising=False)

    async def yes_specstream(url):
        return {"ok": True, "provider": "specstream", "url": url, "content": "# SpecStream Page"}

    monkeypatch.setattr(service, "call_specstream_fetch", yes_specstream)
    result = await service.fetch("https://example.com")
    assert result["ok"] is True
    assert result["provider"] == "specstream"
    assert result["content"] == "# SpecStream Page"
