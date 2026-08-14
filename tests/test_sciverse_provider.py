import json

import httpx
import pytest

from smart_search.providers.sciverse import SciverseProvider


class FakeSciverseClient:
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

    async def get(self, url, headers, params):
        self.__class__.calls.append({"method": "GET", "url": url, "headers": headers, "params": params, "timeout": self.timeout})
        if self.__class__.exception:
            raise self.__class__.exception
        return self.__class__.response

    async def post(self, url, headers, json):
        self.__class__.calls.append({"method": "POST", "url": url, "headers": headers, "json": json, "timeout": self.timeout})
        if self.__class__.exception:
            raise self.__class__.exception
        return self.__class__.response


@pytest.fixture(autouse=True)
def reset_fake_client():
    FakeSciverseClient.calls = []
    FakeSciverseClient.response = None
    FakeSciverseClient.exception = None


@pytest.mark.asyncio
async def test_sciverse_missing_token_returns_config_error_without_request(monkeypatch):
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)

    provider = SciverseProvider("https://api.sciverse.space", None)
    results = [
        json.loads(await provider.list_catalog()),
        json.loads(await provider.search_papers("query", page_size=51)),
        json.loads(await provider.semantic_search("query", top_k=31)),
        json.loads(await provider.read_content("doc-1", limit=16385)),
        json.loads(await provider.list_paper_relations("paper-1", relation="BAD", page_size=201)),
    ]

    assert [data["tool"] for data in results] == [
        "list_catalog",
        "search_papers",
        "semantic_search",
        "read_content",
        "list_paper_relations",
    ]
    assert all(data["ok"] is False for data in results)
    assert all(data["provider"] == "sciverse" for data in results)
    assert all(data["error_type"] == "config_error" for data in results)
    assert all("SCIVERSE_API_TOKEN" in data["error"] for data in results)
    assert FakeSciverseClient.calls == []


@pytest.mark.asyncio
async def test_sciverse_catalog_sends_bearer_header_and_normalizes_fields(monkeypatch):
    FakeSciverseClient.response = httpx.Response(
        200,
        json={
            "fields": [{"name": "title", "type": "string"}],
            "default_fields": ["title"],
            "filter_operators": ["contains"],
        },
        request=httpx.Request("GET", "https://api.sciverse.space/meta-catalog"),
    )
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)

    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret", timeout=12)
    data = json.loads(await provider.list_catalog(collection="papers", include_sample_values=True))

    assert data["ok"] is True
    assert data["provider"] == "sciverse"
    assert data["tool"] == "list_catalog"
    assert data["fields"][0]["name"] == "title"
    call = FakeSciverseClient.calls[0]
    assert call["method"] == "GET"
    assert call["url"] == "https://api.sciverse.space/meta-catalog"
    assert call["headers"]["Authorization"] == "Bearer sciverse-test-secret"
    assert call["params"]["collection"] == "papers"
    assert call["params"]["include_sample_values"] is True
    assert call["timeout"].read == 12.0


@pytest.mark.asyncio
async def test_sciverse_search_payload_and_pagination(monkeypatch):
    FakeSciverseClient.response = httpx.Response(
        200,
        json={
            "results": [
                {
                    "unique_id": "paper-1",
                    "doc_id": "doc-1",
                    "title": "Transformer Retrieval",
                    "metadata": {"year": 2024},
                }
            ],
            "total_count": 1,
            "page": 1,
            "page_size": 5,
            "total_pages": 1,
        },
        request=httpx.Request("POST", "https://api.sciverse.space/meta-search"),
    )
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)

    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret")
    data = json.loads(
        await provider.search_papers(
            "transformer retrieval",
            year_from=2020,
            authors="Ada Lovelace,Grace Hopper",
            filters_advanced=[{"field": "subjects", "op": "contains", "value": "IR"}],
            page_size=5,
        )
    )

    assert data["ok"] is True
    assert data["tool"] == "search_papers"
    assert data["results"][0]["unique_id"] == "paper-1"
    assert data["results"][0]["doc_id"] == "doc-1"
    assert data["total_count"] == 1
    payload = FakeSciverseClient.calls[0]["json"]
    assert payload["query"] == "transformer retrieval"
    filters_by_field = {}
    for item in payload["filters"]:
        filters_by_field.setdefault(item["field"], []).append(item)
    assert filters_by_field["author"] == [{"field": "author", "operator": "FILTER_OP_IN", "value": ["Ada Lovelace", "Grace Hopper"]}]
    assert filters_by_field["publication_published_year"] == [
        {"field": "publication_published_year", "operator": "FILTER_OP_GTE", "value": 2020}
    ]
    assert filters_by_field["subjects"] == [{"field": "subjects", "op": "contains", "value": "IR"}]
    assert payload["page_size"] == 5


@pytest.mark.asyncio
async def test_sciverse_semantic_read_and_relations_normalize_outputs(monkeypatch):
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)
    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret")

    FakeSciverseClient.response = httpx.Response(
        200,
        json={"hits": [{"doc_id": "doc-1", "offset": 120, "score": 0.91, "title": "Attention"}]},
        request=httpx.Request("POST", "https://api.sciverse.space/agentic-search"),
    )
    semantic = json.loads(await provider.semantic_search("attention mechanism", top_k=3, retrieval="hybrid", source_types="paper,abstract"))

    FakeSciverseClient.response = httpx.Response(
        200,
        json={"text": "Full text chunk", "bytes_returned": 15, "next_offset": 15, "more": False},
        request=httpx.Request("GET", "https://api.sciverse.space/content"),
    )
    read = json.loads(await provider.read_content("doc-1", offset=0, limit=4096))

    FakeSciverseClient.response = httpx.Response(
        200,
        json={"items": [{"unique_id": "paper-2", "title": "Citing paper"}], "total_count": 1, "page": 1, "total_pages": 1},
        request=httpx.Request("POST", "https://api.sciverse.space/meta-paper-relations"),
    )
    relations = json.loads(await provider.list_paper_relations("paper-1", relation="CITATIONS", page_size=25))

    assert semantic["hits"][0]["doc_id"] == "doc-1"
    assert FakeSciverseClient.calls[0]["json"]["source_types"] == ["paper", "abstract"]
    assert read["text"] == "Full text chunk"
    assert FakeSciverseClient.calls[1]["params"] == {"doc_id": "doc-1", "offset": 0, "limit": 4096}
    assert relations["items"][0]["unique_id"] == "paper-2"
    assert relations["relation_direction"].startswith("incoming")
    assert FakeSciverseClient.calls[2]["json"]["unique_id"] == "paper-1"


@pytest.mark.asyncio
async def test_sciverse_parameter_bounds_return_local_errors_without_request(monkeypatch):
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)
    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret")

    failures = [
        json.loads(await provider.search_papers("query", page_size=51)),
        json.loads(await provider.semantic_search("query", top_k=31)),
        json.loads(await provider.read_content("doc-1", limit=16385)),
        json.loads(await provider.list_paper_relations("paper-1", page_size=201)),
        json.loads(await provider.list_paper_relations("paper-1", relation="BAD")),
    ]

    assert [item["error_type"] for item in failures] == ["parameter_error"] * 5
    assert FakeSciverseClient.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, "parameter_error"),
        (401, "auth_error"),
        (403, "auth_error"),
        (404, "provider_error"),
        (429, "rate_limited"),
        (502, "network_error"),
        (503, "network_error"),
    ],
)
async def test_sciverse_http_errors_map_to_contract_error_types(monkeypatch, status_code, expected):
    FakeSciverseClient.response = httpx.Response(
        status_code,
        text=f"failure without sciverse-test-secret",
        request=httpx.Request("GET", "https://api.sciverse.space/meta-catalog"),
    )
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)

    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret")
    data = json.loads(await provider.list_catalog())

    assert data["ok"] is False
    assert data["error_type"] == expected
    assert "sciverse-test-secret" not in data["error"]


@pytest.mark.asyncio
async def test_sciverse_timeout_and_invalid_json_are_normalized(monkeypatch):
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)
    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret")

    FakeSciverseClient.exception = httpx.ReadTimeout("too slow", request=httpx.Request("GET", "https://api.sciverse.space/meta-catalog"))
    timeout = json.loads(await provider.list_catalog())
    assert timeout["error_type"] == "timeout"

    FakeSciverseClient.exception = None
    FakeSciverseClient.response = httpx.Response(200, text="not json", request=httpx.Request("GET", "https://api.sciverse.space/meta-catalog"))
    invalid_json = json.loads(await provider.list_catalog())
    assert invalid_json["error_type"] == "parse_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response_body", "method_name", "expected_error"),
    [
        ([], "list_catalog", "list_catalog response must be a JSON object"),
        ({}, "list_catalog", "list_catalog response field 'fields' is required"),
        ({"data": {"results": []}}, "search_papers", "search_papers response field 'results' is required"),
        ({"message": "schema changed"}, "list_paper_relations", "list_paper_relations response field 'items' is required"),
        ({"fields": "title"}, "list_catalog", "list_catalog response field 'fields' must be an array"),
        (
            {"fields": [1], "default_fields": ["title"], "filter_operators": ["contains"]},
            "list_catalog",
            "list_catalog response field 'fields' item 0 must be an object",
        ),
        ({"results": {"unique_id": "paper-1"}}, "search_papers", "search_papers response field 'results' must be an array"),
        ({"results": [1]}, "search_papers", "search_papers response field 'results' item 0 must be an object"),
        ({"hits": {"doc_id": "doc-1"}}, "semantic_search", "semantic_search response field 'hits' must be an array"),
        ({"text": {"chunk": "not text"}}, "read_content", "read_content response field 'text' must be a string"),
        ({"items": {"unique_id": "paper-2"}}, "list_paper_relations", "list_paper_relations response field 'items' must be an array"),
    ],
)
async def test_sciverse_valid_json_wrong_shape_is_parse_error(monkeypatch, response_body, method_name, expected_error):
    FakeSciverseClient.response = httpx.Response(
        200,
        json=response_body,
        request=httpx.Request("POST", "https://api.sciverse.space/test"),
    )
    monkeypatch.setattr("smart_search.providers.sciverse.httpx.AsyncClient", FakeSciverseClient)
    provider = SciverseProvider("https://api.sciverse.space", "sciverse-test-secret")

    if method_name == "list_catalog":
        result = await provider.list_catalog()
    elif method_name == "search_papers":
        result = await provider.search_papers("query")
    elif method_name == "semantic_search":
        result = await provider.semantic_search("query")
    elif method_name == "read_content":
        result = await provider.read_content("doc-1")
    else:
        result = await provider.list_paper_relations("paper-1")

    data = json.loads(result)
    assert data["ok"] is False
    assert data["error_type"] == "parse_error"
    assert expected_error in data["error"]
