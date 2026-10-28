from ..i18n import source_message
import asyncio
import json
import logging
import re
import time
from typing import Any
from urllib.parse import urlsplit

import httpx
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt

from .base import BaseSearchProvider
from .openai_compatible import OpenAICompatibleSearchProvider, _StopAfterSlowFailure, _StopAtDeadline, _WaitWithRetryAfter, _is_retryable_exception, get_local_time_info
from ..config import config
from ..logger import log_info
from ..utils import search_prompt


_logger = logging.getLogger(__name__)
_ssl_warning_emitted = False
_INLINE_URL_PATTERN = re.compile(r"(?<![A-Za-z0-9+.\-])https?://[^\s<>'\"\x60]+", re.IGNORECASE)
_SERIALIZED_SOURCES_PATTERN = re.compile(r"(?ims)(?:^|\n)\s*sources\s*\(\s*\[.*\]\s*\)\s*\Z")
_INLINE_URL_TRAILING_PUNCTUATION = ".,;:!?，。；：！？、…．"
_INLINE_URL_BRACKET_PAIRS = (
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
    ("（", "）"),
    ("【", "】"),
    ("《", "》"),
    ("〈", "〉"),
    ("「", "」"),
    ("『", "』"),
)


class XAIResponsesSearchProvider(BaseSearchProvider):
    def __init__(self, api_url: str, api_key: str, model: str = "grok-4-fast", tools: list[str] | None = None,
                 stream: bool = False, reasoning_effort: str = ""):
        super().__init__(api_url.rstrip("/"), api_key)
        self.model = model
        self.tools = tools or []
        self.stream = stream
        self.reasoning_effort = reasoning_effort
        self._search_deadline_monotonic: float | None = None

    def set_search_deadline(self, deadline_monotonic: float | None) -> None:
        """Set by the service for one main-search candidate; standalone calls stay unchanged."""
        self._search_deadline_monotonic = deadline_monotonic

    def _request_timeout(self) -> httpx.Timeout:
        if self._search_deadline_monotonic is None:
            return httpx.Timeout(connect=6.0, read=config.search_timeout_or_default, write=10.0, pool=None)
        remaining = self._search_deadline_monotonic - time.monotonic()
        if remaining <= 0:
            raise asyncio.TimeoutError(source_message('main_search deadline exhausted'))
        bounded = max(0.001, remaining)
        return httpx.Timeout(
            connect=min(6.0, bounded),
            read=bounded,
            write=min(10.0, bounded),
            pool=bounded,
        )

    def _retry_stop(self):
        stop = stop_after_attempt(config.retry_max_attempts + 1) | _StopAfterSlowFailure(self)
        if self._search_deadline_monotonic is not None:
            return stop | _StopAtDeadline(self._search_deadline_monotonic)
        return stop

    def get_provider_name(self) -> str:
        return "xAI Responses"

    def _build_api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "smart-search/0.1.0",
        }

    def _get_ssl_verify(self) -> bool:
        global _ssl_warning_emitted
        verify = config.ssl_verify_enabled
        if not verify and not _ssl_warning_emitted:
            _ssl_warning_emitted = True
            _logger.warning("SSL_VERIFY=false: xAI Responses API 请求已禁用 SSL 证书验证，存在安全风险")
        return verify

    def request_options(self) -> dict[str, Any]:
        """The transport and reasoning fields that searches and connection tests both send."""
        options: dict[str, Any] = {"stream": self.stream}
        if self.reasoning_effort:
            options["reasoning"] = {"effort": self.reasoning_effort}
        return options

    async def parse_stream(self, response: httpx.Response, ctx=None) -> str:
        parser = OpenAICompatibleSearchProvider(self.api_url, self.api_key, self.model, api_mode="responses")
        return await parser._parse_responses_streaming_response(response, ctx)

    def _build_search_payload(self, query: str, platform: str = "") -> dict[str, Any]:
        platform_prompt = ""
        if platform:
            platform_prompt = "\n\nYou should search the web for the information you need, and focus on these platform: " + platform + "\n"
        time_context = get_local_time_info() + "\n"
        return {
            "model": self.model,
            "instructions": search_prompt,
            "input": [{"role": "user", "content": time_context + query + platform_prompt}],
            "tools": [{"type": tool} for tool in self.tools],
            **self.request_options(),
        }

    async def search(self, query: str, platform: str = "", ctx=None) -> str:
        payload = self._build_search_payload(query, platform)
        await log_info(ctx, f"platform_prompt: {query}", config.debug_enabled)
        return await self._execute_response_with_retry(self._build_api_headers(), payload, ctx)

    async def _execute_response_with_retry(self, headers: dict, payload: dict, ctx=None) -> str:
        timeout = self._request_timeout()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=self._get_ssl_verify()) as client:
            async for attempt in AsyncRetrying(
                stop=self._retry_stop(),
                wait=_WaitWithRetryAfter(
                    config.retry_multiplier,
                    config.retry_max_wait,
                    deadline_monotonic=self._search_deadline_monotonic,
                ),
                retry=retry_if_exception(_is_retryable_exception),
                reraise=True,
            ):
                with attempt:
                    self._attempt_started_at = time.monotonic()
                    if self.stream:
                        async with client.stream(
                            "POST",
                            f"{self.api_url}/responses",
                            headers=headers,
                            json=payload,
                            timeout=self._request_timeout(),
                        ) as response:
                            if response.status_code >= 400:
                                await response.aread()
                            response.raise_for_status()
                            answer = await self.parse_stream(response, ctx)
                            if answer and not _SERIALIZED_SOURCES_PATTERN.search(answer):
                                sources = self._extract_inline_urls(answer)
                                if sources:
                                    answer = f"{answer}\n\nsources({json.dumps(sources, ensure_ascii=False)})".strip()
                            return answer
                    response = await client.post(
                        f"{self.api_url}/responses",
                        headers=headers,
                        json=payload,
                        timeout=self._request_timeout(),
                    )
                    response.raise_for_status()
                    return await self._parse_response(response, ctx)
        return ""

    async def _parse_response(self, response: httpx.Response, ctx=None) -> str:
        data = response.json()
        text_parts: list[str] = []
        sources: list[dict[str, str]] = []
        seen: set[str] = set()

        for item in data.get("output", []) if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue
                if content.get("type") != "output_text":
                    continue
                text = content.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
                for annotation in content.get("annotations", []) or []:
                    if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                        continue
                    url = annotation.get("url")
                    if not isinstance(url, str) or not url.startswith(("http://", "https://")) or url in seen:
                        continue
                    seen.add(url)
                    source: dict[str, str] = {"url": url}
                    title = annotation.get("title")
                    if isinstance(title, str) and title.strip():
                        source["title"] = title.strip()
                    sources.append(source)

        answer = "\n\n".join(part.strip() for part in text_parts if part.strip()).strip()
        if not sources and answer and not _SERIALIZED_SOURCES_PATTERN.search(answer):
            sources = self._extract_inline_urls(answer)
        if sources:
            answer = f"{answer}\n\nsources({json.dumps(sources, ensure_ascii=False)})".strip()

        await log_info(ctx, f"content: {answer}", config.debug_enabled)
        return answer

    @staticmethod
    def _extract_inline_urls(text: str) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen: set[str] = set()

        for match in _INLINE_URL_PATTERN.finditer(text):
            url = XAIResponsesSearchProvider._trim_inline_url_terminal_punctuation(match.group())
            if not XAIResponsesSearchProvider._is_valid_inline_http_url(url):
                continue
            scheme, separator, remainder = url.partition(":")
            url = f"{scheme.lower()}{separator}{remainder}"
            if url in seen:
                continue
            seen.add(url)
            sources.append({"url": url})

        return sources

    @staticmethod
    def _trim_inline_url_terminal_punctuation(url: str) -> str:
        trimmed = url
        while trimmed:
            candidate = trimmed.rstrip(_INLINE_URL_TRAILING_PUNCTUATION)
            for opening, closing in _INLINE_URL_BRACKET_PAIRS:
                while candidate.endswith(closing) and candidate.count(closing) > candidate.count(opening):
                    candidate = candidate[:-1]
            if candidate == trimmed:
                return candidate
            trimmed = candidate
        return trimmed

    @staticmethod
    def _is_valid_inline_http_url(url: str) -> bool:
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            _ = parsed.port
        except ValueError:
            return False

        return (
            parsed.scheme.lower() in {"http", "https"}
            and bool(parsed.netloc)
            and bool(hostname)
            and not any(char.isspace() for char in url)
            and "\\" not in url
        )
