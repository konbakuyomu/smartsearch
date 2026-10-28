"""Tencent Yuanbao Search: the Tencent Cloud wsa SearchPro API."""
import json

import httpx
import pytest

from smart_search.providers import yuanbao
from smart_search.providers.yuanbao import YuanbaoSearchProvider

API_URL = "https://wsa.tencentcloudapi.com"
SECRET_ID, SECRET_KEY = "AKIDEXAMPLE", "Gu5t9xGARNpq86cd98joQYCN3EXAMPLE"


def answer(monkeypatch, body):
    """Answer every request with one wsa JSON body and record the requests."""
    requests = []
    original_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json=body)

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    return requests


def page(**fields):
    return json.dumps({"title": "Title", "url": "https://view.inews.qq.com/a/1", **fields}, ensure_ascii=False)


async def search(query="query", **kwargs):
    return json.loads(await YuanbaoSearchProvider(API_URL, SECRET_ID, SECRET_KEY).search(query, **kwargs))


@pytest.mark.asyncio
@pytest.mark.parametrize(("query", "body", "signature"), [
    # Expected values come from tencentcloud-sdk-python-common with its clock frozen at 1761638400.
    ("smart search", '{"Query": "smart search"}', "d2f9d2e3aa0f719e1a17e74f1d83b99252731774a0b3c147e3fdd3da14f66d4f"),
    ("元宝搜索", '{"Query": "\\u5143\\u5b9d\\u641c\\u7d22"}', "6f7b8ece26a931e68160929c02dd4eb2f9d01b3accf899753fbc525e767bef4b"),
])
async def test_requests_are_signed_like_the_official_sdk(monkeypatch, query, body, signature):
    monkeypatch.setattr(yuanbao.time, "time", lambda: 1761638400)
    requests = answer(monkeypatch, {"Response": {"Pages": [], "RequestId": "r"}})

    await search(query)

    request = requests[0]
    assert (request.method, str(request.url), request.content) == ("POST", API_URL + "/", body.encode())
    assert request.headers["Authorization"] == (
        f"TC3-HMAC-SHA256 Credential={SECRET_ID}/2025-10-28/wsa/tc3_request, "
        f"SignedHeaders=content-type;host, Signature={signature}"
    )
    assert (request.headers["X-TC-Action"], request.headers["X-TC-Version"], request.headers["X-TC-Timestamp"]) == (
        "SearchPro", "2025-05-08", "1761638400")


@pytest.mark.asyncio
async def test_pages_become_search_results(monkeypatch):
    answer(monkeypatch, {"Response": {"Pages": [page(
        date="2026/10/21 22:30:00", site="腾讯新闻", passage="Standard summary", content="Dynamic summary", score=0.73,
    )], "Version": "standard", "RequestId": "r"}})

    data = await search()

    assert data["ok"] is True
    assert data["results"] == [{
        "title": "Title", "url": "https://view.inews.qq.com/a/1", "description": "Standard summary",
        "content": "Dynamic summary", "source": "腾讯新闻", "published_date": "2026/10/21 22:30:00", "provider": "yuanbao",
    }]


@pytest.mark.asyncio
async def test_results_stop_at_max_results(monkeypatch):
    answer(monkeypatch, {"Response": {"Pages": [page(passage=str(index)) for index in range(3)], "RequestId": "r"}})

    data = await search(max_results=2)

    assert [item["description"] for item in data["results"]] == ["0", "1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("code", "error_type"), [
    ("AuthFailure.SignatureFailure", "auth_error"),
    ("InvalidParameter", "parameter_error"),
    ("RequestLimitExceeded", "rate_limited"),
    ("InternalError", "provider_error"),
])
async def test_api_errors_keep_their_code_and_are_classified(monkeypatch, code, error_type):
    answer(monkeypatch, {"Response": {"Error": {"Code": code, "Message": "details"}, "RequestId": "r"}})

    data = await search()

    assert (data["ok"], data["error_type"]) == (False, error_type)
    assert code in data["error"]


@pytest.mark.asyncio
async def test_missing_credentials_are_a_config_error_without_a_request(monkeypatch):
    requests = answer(monkeypatch, {"Response": {"Pages": []}})

    data = json.loads(await YuanbaoSearchProvider(API_URL, SECRET_ID, "").search("query"))

    assert (data["ok"], data["error_type"], requests) == (False, "config_error", [])
