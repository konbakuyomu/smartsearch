"""TinyFish web search and page fetch.

Search and fetch run on their own product hosts rather than the automation API
on `agent.tinyfish.ai`. Both authenticate with the `X-API-Key` header.
"""

import json
import time
from typing import Any

import httpx

from .base import BaseSearchProvider
from ..provider_errors import ProviderCallError, classify_provider_exception


CHALLENGE_MARKERS = (
    "checking if the site connection is secure",
    "enable javascript and cookies to continue",
    "attention required! | cloudflare",
)


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _error_payload(exc: Exception, api_key: str = "") -> dict[str, str]:
    error_type, error = classify_provider_exception(exc, additional_secrets=(api_key,))
    return {"error_type": error_type, "error": error}


def _challenge_marker(content: str) -> str:
    lowered = content.strip().lower()
    for marker in CHALLENGE_MARKERS:
        if marker in lowered:
            return marker
    return ""


def _normalize_search_result(item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {
        "title": item.get("title") or "",
        "url": item.get("url") or "",
        "description": item.get("snippet") or "",
        "provider": "tinyfish",
    }
    site_name = item.get("site_name") or ""
    if site_name:
        out["source"] = site_name
    published = item.get("date") or ""
    if published:
        out["published_date"] = published
    return out


def _first_fetch_error(errors: Any) -> str:
    if not isinstance(errors, list) or not errors:
        return ""
    first = errors[0]
    if isinstance(first, dict):
        return str(first.get("error") or "").strip()
    return str(first or "").strip()


class TinyFishSearchProvider(BaseSearchProvider):
    def __init__(self, api_url: str, api_key: str, timeout: float = 30.0):
        super().__init__(api_url, api_key)
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "tinyfish"

    async def search(self, query: str, max_results: int = 5, ctx=None) -> str:
        start = time.time()
        if not self.api_key:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "tinyfish",
                    "error_type": "config_error",
                    "error": "TINYFISH_API_KEY is not configured.",
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(self.api_url, headers=headers, params={"query": query})
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                raise ProviderCallError("parse_error", "TinyFish search response is not a JSON object")
            results = payload.get("results")
            if not isinstance(results, list):
                raise ProviderCallError("parse_error", "TinyFish search response is missing results")
            normalized = [
                _normalize_search_result(item)
                for item in results[:max_results]
                if isinstance(item, dict)
            ]
            output: dict[str, Any] = {
                "ok": True,
                "provider": "tinyfish",
                "query": query,
                "results": normalized,
                "total_results": len(normalized),
                "elapsed_ms": _elapsed_ms(start),
            }
        except Exception as exc:
            error = _error_payload(exc, self.api_key)
            output = {
                "ok": False,
                "provider": "tinyfish",
                "query": query,
                "error_type": error["error_type"],
                "error": error["error"],
                "elapsed_ms": _elapsed_ms(start),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)


class TinyFishFetchProvider:
    def __init__(self, api_url: str, api_key: str, timeout: float = 60.0):
        self.api_url = api_url
        self.api_key = api_key or ""
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "tinyfish"

    async def fetch(self, url: str, ctx=None) -> str:
        start = time.time()
        if not self.api_key:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "tinyfish",
                    "url": url,
                    "error_type": "config_error",
                    "error": "TINYFISH_API_KEY is not configured.",
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {"urls": [url], "format": "markdown"}
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.api_url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                raise ProviderCallError("parse_error", "TinyFish fetch response is not a JSON object")
            results = payload.get("results")
            if not isinstance(results, list):
                raise ProviderCallError("parse_error", "TinyFish fetch response is missing results")
            if not results:
                raise ProviderCallError(
                    "provider_error",
                    _first_fetch_error(payload.get("errors")) or "TinyFish fetch returned no content",
                    additional_secrets=(self.api_key,),
                )
            first = results[0]
            if not isinstance(first, dict):
                raise ProviderCallError("parse_error", "TinyFish fetch result is not an object")
            content = first.get("text")
            if not isinstance(content, str):
                raise ProviderCallError("parse_error", "TinyFish fetch content is not text")
            challenge = _challenge_marker(content)
            if challenge:
                return json.dumps(
                    {
                        "ok": False,
                        "provider": "tinyfish",
                        "url": url,
                        "error_type": "quality_error",
                        "error": f"low-quality challenge page detected: {challenge}",
                        "content": content,
                        "elapsed_ms": _elapsed_ms(start),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            output: dict[str, Any] = {
                "ok": True,
                "provider": "tinyfish",
                "url": url,
                "final_url": first.get("final_url") or url,
                "title": first.get("title") or "",
                "published_date": first.get("published_date") or "",
                "content": content,
                "elapsed_ms": _elapsed_ms(start),
            }
        except Exception as exc:
            error = _error_payload(exc, self.api_key)
            output = {
                "ok": False,
                "provider": "tinyfish",
                "url": url,
                "error_type": error["error_type"],
                "error": error["error"],
                "elapsed_ms": _elapsed_ms(start),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)
