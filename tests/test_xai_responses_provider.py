import httpx
import pytest

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
    assert payload["tools"] == [{"type": "web_search"}, {"type": "x_search"}]
    assert payload["input"][0]["role"] == "user"
    assert "What is new?" in payload["input"][0]["content"]
    assert "X" in payload["input"][0]["content"]


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

        async def post(self, url, headers, json):
            calls.append((url, headers, json))
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
