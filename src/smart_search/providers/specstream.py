"""SpecStream live web search and page extract provider.

Both endpoints authenticate with Bearer auth via ``SPECSTREAM_API_KEY``:
- Search: ``POST https://api.specstream.ai/v1/web-search``
- Extract: ``POST https://api.specstream.ai/v1/extract``
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from ..i18n import source_message
from ..provider_errors import ProviderCallError, classify_provider_exception
from .base import BaseSearchProvider

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
        "description": item.get("excerpt") or item.get("snippet") or "",
        "provider": "specstream",
    }
    site_name = item.get("source") or ""
    if site_name:
        out["source"] = site_name
    published = item.get("published") or ""
    if published:
        out["published_date"] = published
    return out


class SpecStreamSearchProvider(BaseSearchProvider):
    def __init__(self, api_url: str, api_key: str, timeout: float = 30.0):
        super().__init__(api_url, api_key)
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "specstream"

    async def search(self, query: str, max_results: int = 5, ctx=None) -> str:
        start = time.time()
        if not self.api_key:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "specstream",
                    "error_type": "config_error",
                    "error": source_message("SPECSTREAM_API_KEY is not configured."),
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {
            "q": query,
            "num": min(max(1, int(max_results)), 20),
            "passages": True,
        }
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.api_url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                raise ProviderCallError(
                    "parse_error",
                    source_message("SpecStream search response is not a JSON object"),
                )
            sources = payload.get("sources")
            if not isinstance(sources, list):
                raise ProviderCallError(
                    "parse_error",
                    source_message("SpecStream search response is missing sources"),
                )
            normalized = [
                _normalize_search_result(item)
                for item in sources[:max_results]
                if isinstance(item, dict)
            ]
            output: dict[str, Any] = {
                "ok": True,
                "provider": "specstream",
                "query": query,
                "results": normalized,
                "total_results": len(normalized),
                "elapsed_ms": _elapsed_ms(start),
            }
        except Exception as exc:
            error = _error_payload(exc, self.api_key)
            output = {
                "ok": False,
                "provider": "specstream",
                "query": query,
                "error_type": error["error_type"],
                "error": error["error"],
                "elapsed_ms": _elapsed_ms(start),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)


class SpecStreamFetchProvider:
    def __init__(self, api_url: str, api_key: str, timeout: float = 45.0):
        self.api_url = api_url
        self.api_key = api_key or ""
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "specstream"

    async def fetch(self, url: str, ctx=None) -> str:
        start = time.time()
        if not self.api_key:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "specstream",
                    "url": url,
                    "error_type": "config_error",
                    "error": source_message("SPECSTREAM_API_KEY is not configured."),
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        body = {"urls": [url]}
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.api_url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
            if not isinstance(payload, dict):
                raise ProviderCallError(
                    "parse_error",
                    source_message("SpecStream extract response is not a JSON object"),
                )
            results = payload.get("results")
            if not isinstance(results, list) or not results:
                raise ProviderCallError(
                    "provider_error",
                    source_message("SpecStream extract returned no results"),
                    additional_secrets=(self.api_key,),
                )
            first = results[0]
            if not isinstance(first, dict):
                raise ProviderCallError(
                    "parse_error",
                    source_message("SpecStream extract result is not an object"),
                )
            if first.get("ok") is False:
                raise ProviderCallError(
                    "provider_error",
                    str(first.get("error") or "SpecStream extract failed"),
                    additional_secrets=(self.api_key,),
                )
            content = first.get("markdown") or first.get("text")
            if not isinstance(content, str) or not content.strip():
                raise ProviderCallError(
                    "provider_error",
                    source_message("SpecStream extract returned empty content"),
                    additional_secrets=(self.api_key,),
                )
            challenge = _challenge_marker(content)
            if challenge:
                return json.dumps(
                    {
                        "ok": False,
                        "provider": "specstream",
                        "url": url,
                        "error_type": "quality_error",
                        "error": source_message(
                            "low-quality challenge page detected: {0}", challenge
                        ),
                        "content": content,
                        "elapsed_ms": _elapsed_ms(start),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            output: dict[str, Any] = {
                "ok": True,
                "provider": "specstream",
                "url": url,
                "final_url": first.get("url") or url,
                "title": first.get("title") or "",
                "content": content,
                "elapsed_ms": _elapsed_ms(start),
            }
        except Exception as exc:
            error = _error_payload(exc, self.api_key)
            output = {
                "ok": False,
                "provider": "specstream",
                "url": url,
                "error_type": error["error_type"],
                "error": error["error"],
                "elapsed_ms": _elapsed_ms(start),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)
