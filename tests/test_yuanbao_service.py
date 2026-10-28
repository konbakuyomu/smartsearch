"""Yuanbao Search as a web_search channel."""
import json

import httpx
import pytest

from smart_search import service

PAGE = {"title": "元宝搜索开放", "url": "https://view.inews.qq.com/a/1", "passage": "腾讯云开放元宝搜索。",
        "date": "2026/10/21 22:30:00", "site": "腾讯新闻"}


def configure(monkeypatch):
    monkeypatch.setenv("SMART_SEARCH_INTENT_ROUTER", "local")
    monkeypatch.setenv("YUANBAO_SECRET_ID", "AKIDtest")
    monkeypatch.setenv("YUANBAO_SECRET_KEY", "secret-test")


def answer_wsa(monkeypatch, response):
    """Answer wsa SearchPro at the HTTP boundary and record each request body."""
    bodies = []
    original_client = httpx.AsyncClient

    def handler(request):
        assert str(request.url) == "https://wsa.tencentcloudapi.com/"
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"Response": {"RequestId": "r", **response}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    return bodies


def web_search_providers():
    return service.get_capability_status()["web_search"]["configured"]


def test_yuanbao_is_a_web_search_channel_only_when_configured_and_enabled(monkeypatch):
    assert "yuanbao" not in web_search_providers()
    configure(monkeypatch)
    assert "yuanbao" in web_search_providers()
    monkeypatch.setenv("YUANBAO_ENABLED", "false")
    assert "yuanbao" not in web_search_providers()


@pytest.mark.asyncio
async def test_search_returns_yuanbao_results(monkeypatch):
    configure(monkeypatch)
    bodies = answer_wsa(monkeypatch, {"Pages": [json.dumps(PAGE, ensure_ascii=False)]})

    result = await service.search("元宝搜索 开放", providers="yuanbao")

    assert result["ok"] is True
    assert bodies == [{"Query": "元宝搜索 开放"}]
    assert result["provider"] == "yuanbao"
    assert PAGE["url"] in json.dumps(result, ensure_ascii=False)


@pytest.mark.asyncio
async def test_search_reports_a_yuanbao_auth_failure(monkeypatch):
    configure(monkeypatch)
    answer_wsa(monkeypatch, {"Error": {"Code": "AuthFailure.SignatureFailure", "Message": "bad signature"}})

    result = await service.search("元宝搜索", providers="yuanbao", fallback="off")

    assert result["ok"] is False
    assert result["provider_attempts"][0]["error_type"] == "auth_error"


@pytest.mark.asyncio
async def test_connection_test_runs_one_small_search(monkeypatch):
    configure(monkeypatch)
    bodies = answer_wsa(monkeypatch, {"Pages": [json.dumps(PAGE, ensure_ascii=False)]})

    result = await service.test_provider_connection("yuanbao")

    assert result["status"] == "ok"
    assert len(bodies) == 1


@pytest.mark.asyncio
async def test_connection_test_reports_an_auth_failure(monkeypatch):
    configure(monkeypatch)
    answer_wsa(monkeypatch, {"Error": {"Code": "AuthFailure.SecretIdNotFound", "Message": "not found"}})

    result = await service.test_provider_connection("yuanbao")

    assert result["status"] == "auth_error"
    assert "AuthFailure.SecretIdNotFound" in result["message"]


@pytest.mark.asyncio
async def test_doctor_reports_the_yuanbao_connection(monkeypatch):
    configure(monkeypatch)
    answer_wsa(monkeypatch, {"Pages": [json.dumps(PAGE, ensure_ascii=False)]})

    info = await service.doctor()

    assert info["yuanbao_connection_test"]["status"] == "ok"
