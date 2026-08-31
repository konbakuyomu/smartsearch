import asyncio
import httpx
import json
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, List, Optional
from tenacity import AsyncRetrying, retry_if_exception, stop_after_attempt, wait_random_exponential
from tenacity.stop import stop_base
from tenacity.wait import wait_base
from .base import BaseSearchProvider, SearchResult
from ..utils import search_prompt, fetch_prompt, url_describe_prompt, rank_sources_prompt
from ..logger import log_info
from ..config import config
from ..provider_errors import ProviderCallError, classify_provider_exception

_logger = logging.getLogger(__name__)
_ssl_warning_emitted = False
_STREAM_BREAKERS: dict[tuple[str, str, str], dict[str, Any]] = {}
STREAM_BREAKER_FAILURE_THRESHOLD = 2
STREAM_BREAKER_COOLDOWN_SECONDS = 600.0
OPENAI_COMPATIBLE_API_MODES = frozenset({"chat-completions", "responses"})
_OPENAI_COMPATIBLE_ENDPOINT_SUFFIXES = ("chat/completions", "responses")


def get_local_time_info() -> str:
    try:
        local_tz = datetime.now().astimezone().tzinfo
        local_now = datetime.now(local_tz)
    except Exception:
        local_now = datetime.now(timezone.utc)

    weekdays_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays_cn[local_now.weekday()]

    return (
        f"[Current Time Context]\n"
        f"- Date: {local_now.strftime('%Y-%m-%d')} ({weekday})\n"
        f"- Time: {local_now.strftime('%H:%M:%S')}\n"
        f"- Timezone: {local_now.tzname() or 'Local'}\n"
    )


RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _is_retryable_exception(exc) -> bool:
    if isinstance(exc, (asyncio.TimeoutError, httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return False


def _is_stream_fallback_exception(exc: BaseException) -> bool:
    return _is_retryable_exception(exc) or (
        isinstance(exc, ProviderCallError) and exc.error_type == "parse_error"
    )


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _transport_error_type(exc: BaseException) -> str:
    return classify_provider_exception(exc)[0]


def _transport_error_message(exc: BaseException, api_key: str = "") -> str:
    return classify_provider_exception(exc, additional_secrets=(api_key,))[1]


def normalize_openai_compatible_api_url(api_url: str) -> str:
    """Normalize a configured base URL so a known completion path is added once."""
    base_url = str(api_url or "").strip().rstrip("/")
    lower_base_url = base_url.lower()
    for suffix in _OPENAI_COMPATIBLE_ENDPOINT_SUFFIXES:
        marker = f"/{suffix}"
        if lower_base_url.endswith(marker):
            return base_url[: -len(marker)].rstrip("/")
    return base_url


def openai_compatible_endpoint(api_url: str, api_mode: str) -> str:
    base_url = normalize_openai_compatible_api_url(api_url)
    if not base_url:
        return ""
    path = "responses" if api_mode == "responses" else "chat/completions"
    return f"{base_url}/{path}"


def _stream_breaker_key(api_url: str, model: str, api_mode: str) -> tuple[str, str, str]:
    return (normalize_openai_compatible_api_url(api_url), model, api_mode)


def reset_openai_compatible_breakers() -> None:
    _STREAM_BREAKERS.clear()


class _StopAtDeadline(stop_base):
    def __init__(self, deadline_monotonic: float):
        self._deadline_monotonic = deadline_monotonic

    def __call__(self, retry_state) -> bool:
        del retry_state
        return time.monotonic() >= self._deadline_monotonic


class _WaitWithRetryAfter(wait_base):

    def __init__(self, multiplier: float, max_wait: int, deadline_monotonic: float | None = None):
        self._base_wait = wait_random_exponential(multiplier=multiplier, max=max_wait)
        self._protocol_error_base = 3.0
        self._deadline_monotonic = deadline_monotonic

    def __call__(self, retry_state):
        if retry_state.outcome and retry_state.outcome.failed:
            exc = retry_state.outcome.exception()
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
                retry_after = self._parse_retry_after(exc.response)
                if retry_after is not None:
                    return self._bounded_wait(retry_after)
            if isinstance(exc, httpx.RemoteProtocolError):
                return self._bounded_wait(self._base_wait(retry_state) + self._protocol_error_base)
        return self._bounded_wait(self._base_wait(retry_state))

    def _bounded_wait(self, value: float) -> float:
        if self._deadline_monotonic is None:
            return value
        return max(0.0, min(value, self._deadline_monotonic - time.monotonic()))

    def _parse_retry_after(self, response: httpx.Response) -> Optional[float]:
        header = response.headers.get("Retry-After")
        if not header:
            return None
        header = header.strip()

        if header.isdigit():
            return float(header)

        try:
            retry_dt = parsedate_to_datetime(header)
            if retry_dt.tzinfo is None:
                retry_dt = retry_dt.replace(tzinfo=timezone.utc)
            delay = (retry_dt - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, delay)
        except (TypeError, ValueError):
            return None


class OpenAICompatibleSearchProvider(BaseSearchProvider):
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str = "grok-4-fast",
        stream: bool = False,
        api_mode: str = "chat-completions",
    ):
        super().__init__(normalize_openai_compatible_api_url(api_url), api_key)
        self.model = model
        self.stream = stream
        self.api_mode = (api_mode or "chat-completions").strip().lower()
        if self.api_mode not in OPENAI_COMPATIBLE_API_MODES:
            allowed = ", ".join(sorted(OPENAI_COMPATIBLE_API_MODES))
            raise ValueError(f"Invalid OpenAI-compatible API mode: {self.api_mode}. Supported values: {allowed}")
        self.last_transport_attempts: list[dict[str, Any]] = []
        self._search_deadline_monotonic: float | None = None

    def set_search_deadline(self, deadline_monotonic: float | None) -> None:
        """Set by the service for one main-search candidate; standalone calls stay unchanged."""
        self._search_deadline_monotonic = deadline_monotonic

    def _remaining_search_deadline(self) -> float | None:
        if self._search_deadline_monotonic is None:
            return None
        return self._search_deadline_monotonic - time.monotonic()

    def _request_timeout(self) -> httpx.Timeout:
        remaining = self._remaining_search_deadline()
        if remaining is None:
            return httpx.Timeout(connect=6.0, read=120.0, write=10.0, pool=None)
        if remaining <= 0:
            raise asyncio.TimeoutError("main_search deadline exhausted")
        bounded = max(0.001, remaining)
        return httpx.Timeout(
            connect=min(6.0, bounded),
            read=min(120.0, bounded),
            write=min(10.0, bounded),
            pool=bounded,
        )

    def _retry_stop(self):
        stop = stop_after_attempt(config.retry_max_attempts + 1)
        if self._search_deadline_monotonic is not None:
            return stop | _StopAtDeadline(self._search_deadline_monotonic)
        return stop

    def _retry_wait(self) -> _WaitWithRetryAfter:
        return _WaitWithRetryAfter(
            config.retry_multiplier,
            config.retry_max_wait,
            deadline_monotonic=self._search_deadline_monotonic,
        )

    def get_provider_name(self) -> str:
        return "OpenAI-compatible"

    def _build_api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "smart-search/0.1.0",
        }

    def _get_ssl_verify(self) -> bool:
        global _ssl_warning_emitted
        verify = config.ssl_verify_enabled
        if not verify and not _ssl_warning_emitted:
            _ssl_warning_emitted = True
            _logger.warning("SSL_VERIFY=false: OpenAI-compatible API 请求已禁用 SSL 证书验证，存在安全风险")
        return verify

    def _api_endpoint(self) -> str:
        return openai_compatible_endpoint(self.api_url, self.api_mode)

    def _build_request_payload(self, instructions: str, user_content: str, *, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "stream": stream}
        if self.api_mode == "responses":
            payload.update(
                {
                    "instructions": instructions,
                    "input": [{"role": "user", "content": user_content}],
                }
            )
        else:
            payload["messages"] = [
                {"role": "system", "content": instructions},
                {"role": "user", "content": user_content},
            ]
        return payload

    async def search(self, query: str, platform: str = "", ctx=None) -> List[SearchResult]:
        headers = self._build_api_headers()
        platform_prompt = ""

        if platform:
            platform_prompt = "\n\nYou should search the web for the information you need, and focus on these platform: " + platform + "\n"

        time_context = get_local_time_info() + "\n"

        payload = self._build_request_payload(
            search_prompt,
            time_context + query + platform_prompt,
            stream=self.stream,
        )

        await log_info(ctx, f"platform_prompt: { query + platform_prompt}", config.debug_enabled)

        return await self._execute_with_transport_fallback(headers, payload, ctx)

    async def fetch(self, url: str, ctx=None) -> str:
        headers = self._build_api_headers()
        payload = self._build_request_payload(
            fetch_prompt,
            url + "\n获取该网页内容并返回其结构化Markdown格式",
            stream=self.stream,
        )
        return await self._execute_with_transport_fallback(headers, payload, ctx)

    def _breaker_state(self) -> dict[str, Any]:
        key = _stream_breaker_key(self.api_url, self.model, self.api_mode)
        state = _STREAM_BREAKERS.get(key, {})
        opened_until = float(state.get("opened_until") or 0.0)
        now = time.monotonic()
        if opened_until and opened_until > now:
            return {
                "state": "open",
                "opened_until_seconds": round(opened_until - now, 3),
                "consecutive_failures": int(state.get("consecutive_failures") or 0),
            }
        if opened_until and opened_until <= now:
            _STREAM_BREAKERS.pop(key, None)
        return {"state": "closed", "consecutive_failures": int(state.get("consecutive_failures") or 0)}

    def _record_stream_success(self) -> None:
        _STREAM_BREAKERS.pop(_stream_breaker_key(self.api_url, self.model, self.api_mode), None)

    def _record_stream_failure(self) -> dict[str, Any]:
        key = _stream_breaker_key(self.api_url, self.model, self.api_mode)
        state = _STREAM_BREAKERS.setdefault(key, {"consecutive_failures": 0, "opened_until": 0.0})
        state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
        if state["consecutive_failures"] >= STREAM_BREAKER_FAILURE_THRESHOLD:
            state["opened_until"] = time.monotonic() + STREAM_BREAKER_COOLDOWN_SECONDS
        return self._breaker_state()

    def _transport_attempt(
        self,
        transport: str,
        status: str,
        start: float,
        *,
        error_type: str = "",
        error: str = "",
        breaker_state: dict[str, Any] | None = None,
        fallback_from_transport: str = "",
    ) -> dict[str, Any]:
        attempt: dict[str, Any] = {
            "transport": transport,
            "status": status,
            "error_type": error_type,
            "error": error,
            "elapsed_ms": _elapsed_ms(start),
            "result_count": 1 if status == "ok" else 0,
            "model": self.model,
            "api_mode": self.api_mode,
            "endpoint": self._api_endpoint(),
        }
        if breaker_state:
            attempt["breaker_state"] = breaker_state
        if fallback_from_transport:
            attempt["fallback_from_transport"] = fallback_from_transport
        return attempt

    async def _execute_with_transport_fallback(self, headers: dict, payload: dict, ctx=None) -> str:
        self.last_transport_attempts = []
        if not self.stream:
            payload["stream"] = False
            start = time.time()
            try:
                content = await self._execute_completion_with_retry(headers, payload, ctx)
                self.last_transport_attempts.append(self._transport_attempt("non_stream", "ok" if content else "empty", start))
                return content
            except asyncio.CancelledError:
                self.last_transport_attempts.append(
                    self._transport_attempt(
                        "non_stream",
                        "error",
                        start,
                        error_type="timeout",
                        error="main_search deadline cancelled the non-stream transport",
                    )
                )
                raise
            except Exception as e:
                self.last_transport_attempts.append(
                    self._transport_attempt(
                        "non_stream",
                        "error",
                        start,
                        error_type=_transport_error_type(e),
                        error=_transport_error_message(e, self.api_key),
                    )
                )
                raise

        breaker_state = self._breaker_state()
        if breaker_state.get("state") == "open":
            self.last_transport_attempts.append(
                self._transport_attempt("stream", "skipped", time.time(), breaker_state=breaker_state, error="stream breaker open")
            )
        else:
            payload["stream"] = True
            stream_start = time.time()
            try:
                content = await self._execute_stream_with_retry(headers, payload, ctx)
                if content and content.strip():
                    self._record_stream_success()
                    self.last_transport_attempts.append(
                        self._transport_attempt("stream", "ok", stream_start, breaker_state=self._breaker_state())
                    )
                    return content
                breaker_state = self._record_stream_failure()
                self.last_transport_attempts.append(
                    self._transport_attempt(
                        "stream",
                        "empty",
                        stream_start,
                        error_type="network_error",
                        error="OpenAI-compatible stream returned empty content",
                        breaker_state=breaker_state,
                    )
                )
            except asyncio.CancelledError:
                self.last_transport_attempts.append(
                    self._transport_attempt(
                        "stream",
                        "error",
                        stream_start,
                        error_type="timeout",
                        error="main_search deadline cancelled the stream transport",
                        breaker_state=breaker_state,
                    )
                )
                raise
            except Exception as e:
                breaker_state = self._record_stream_failure()
                self.last_transport_attempts.append(
                    self._transport_attempt(
                        "stream",
                        "error",
                        stream_start,
                        error_type=_transport_error_type(e),
                        error=_transport_error_message(e, self.api_key),
                        breaker_state=breaker_state,
                    )
                )
                if not _is_stream_fallback_exception(e):
                    raise

        payload["stream"] = False
        completion_start = time.time()
        try:
            content = await self._execute_completion_with_retry(headers, payload, ctx)
            self.last_transport_attempts.append(
                self._transport_attempt(
                    "non_stream",
                    "ok" if content else "empty",
                    completion_start,
                    error_type="" if content else "network_error",
                    error="" if content else "OpenAI-compatible non-stream returned empty content",
                    fallback_from_transport="stream",
                )
            )
            return content
        except asyncio.CancelledError:
            self.last_transport_attempts.append(
                self._transport_attempt(
                    "non_stream",
                    "error",
                    completion_start,
                    error_type="timeout",
                    error="main_search deadline cancelled the non-stream transport",
                    fallback_from_transport="stream",
                )
            )
            raise
        except Exception as e:
            self.last_transport_attempts.append(
                self._transport_attempt(
                    "non_stream",
                    "error",
                    completion_start,
                    error_type=_transport_error_type(e),
                    error=_transport_error_message(e, self.api_key),
                    fallback_from_transport="stream",
                )
            )
            raise

    async def _parse_streaming_response(self, response, ctx=None) -> str:
        if self.api_mode == "responses":
            return await self._parse_responses_streaming_response(response, ctx)

        content = ""
        full_body_buffer = []

        async for line in response.aiter_lines():
            line = line.strip()
            if not line:
                continue

            full_body_buffer.append(line)

            if line.startswith("data:"):
                if line in ("data: [DONE]", "data:[DONE]"):
                    continue
                try:
                    json_str = line[5:].lstrip()
                    data = json.loads(json_str)
                    choices = data.get("choices", [])
                    if choices and len(choices) > 0:
                        delta = choices[0].get("delta", {})
                        if "content" in delta:
                            content += delta["content"]
                except (json.JSONDecodeError, IndexError):
                    continue

        if not content and full_body_buffer:
            try:
                full_text = "".join(full_body_buffer)
                data = json.loads(full_text)
                if "choices" in data and len(data["choices"]) > 0:
                    message = data["choices"][0].get("message", {})
                    content = message.get("content", "")
            except json.JSONDecodeError:
                pass

        await log_info(ctx, f"content: {content}", config.debug_enabled)

        return content

    @staticmethod
    def _response_stream_part_key(data: dict[str, Any]) -> tuple[int, int]:
        output_index = data.get("output_index")
        content_index = data.get("content_index")
        return (
            output_index if isinstance(output_index, int) else -1,
            content_index if isinstance(content_index, int) else -1,
        )

    @staticmethod
    def _join_response_text_parts(parts: dict[tuple[int, int], str], fallback_parts: list[str]) -> str:
        ordered = [parts[key].strip() for key in sorted(parts) if parts[key].strip()]
        if not ordered:
            ordered = [part.strip() for part in fallback_parts if isinstance(part, str) and part.strip()]
        return "\n\n".join(ordered).strip()

    async def _parse_responses_streaming_response(self, response, ctx=None) -> str:
        delta_parts: dict[tuple[int, int], str] = {}
        completed_parts: dict[tuple[int, int], str] = {}
        output_item_parts: list[str] = []
        stream_sources: list[dict] = []
        malformed_events: list[str] = []

        async for line in response.aiter_lines():
            stripped = line.strip()
            if not stripped or not stripped.startswith("data:"):
                continue
            raw_data = stripped[5:].lstrip()
            if raw_data == "[DONE]":
                continue
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                malformed_events.append("invalid JSON data")
                continue
            if not isinstance(data, dict):
                malformed_events.append("event data was not an object")
                continue

            event_type = data.get("type")
            if not isinstance(event_type, str) or not event_type:
                malformed_events.append("event type was missing")
                continue

            if event_type == "response.output_text.delta":
                delta = data.get("delta")
                if not isinstance(delta, str):
                    malformed_events.append("response.output_text.delta had no string delta")
                    continue
                key = self._response_stream_part_key(data)
                delta_parts[key] = delta_parts.get(key, "") + delta
                continue

            if event_type == "response.output_text.done":
                text = data.get("text")
                if not isinstance(text, str):
                    malformed_events.append("response.output_text.done had no string text")
                    continue
                completed_parts[self._response_stream_part_key(data)] = text
                stream_sources = self._merge_citations(
                    stream_sources,
                    self._normalize_responses_citations(data.get("annotations")),
                )
                continue

            if event_type == "response.content_part.done":
                part = data.get("part")
                if not isinstance(part, dict):
                    malformed_events.append("response.content_part.done had no part object")
                    continue
                if part.get("type") == "output_text":
                    text = part.get("text")
                    if not isinstance(text, str):
                        malformed_events.append("output_text part had no string text")
                        continue
                    completed_parts[self._response_stream_part_key(data)] = text
                    stream_sources = self._merge_citations(
                        stream_sources,
                        self._normalize_responses_citations(part.get("annotations")),
                    )
                continue

            if event_type == "response.output_item.done":
                item = data.get("item")
                if not isinstance(item, dict):
                    malformed_events.append("response.output_item.done had no item object")
                    continue
                item_text, item_sources = self._extract_responses_content({"output": [item]})
                if item_text:
                    output_item_parts.append(item_text)
                stream_sources = self._merge_citations(stream_sources, item_sources)
                continue

            if event_type == "response.output_text.annotation.added":
                annotation = data.get("annotation")
                if not isinstance(annotation, dict):
                    malformed_events.append("response.output_text.annotation.added had no annotation object")
                    continue
                stream_sources = self._merge_citations(
                    stream_sources,
                    self._normalize_responses_citations(annotation),
                )
                continue

            if event_type == "error":
                detail = self._responses_error_detail(data.get("error") or data.get("message") or data)
                raise ProviderCallError(
                    "provider_error",
                    "Responses stream error: " + detail,
                    additional_secrets=(self.api_key,),
                )

            if event_type in {"response.completed", "response.failed", "response.cancelled", "response.canceled", "response.incomplete"}:
                response_data = data.get("response")
                if not isinstance(response_data, dict):
                    raise ProviderCallError(
                        "parse_error",
                        f"Malformed {event_type}: response object is missing",
                        additional_secrets=(self.api_key,),
                    )
                implied_status = {
                    "response.completed": "completed",
                    "response.failed": "failed",
                    "response.cancelled": "cancelled",
                    "response.canceled": "cancelled",
                    "response.incomplete": "incomplete",
                }[event_type]
                terminal_error = self._responses_terminal_error(response_data, implied_status=implied_status)
                if terminal_error is not None:
                    raise terminal_error
                if malformed_events:
                    raise ProviderCallError(
                        "parse_error",
                        "Malformed Responses stream event: " + malformed_events[0],
                        additional_secrets=(self.api_key,),
                    )

                content, sources = self._extract_responses_content(response_data)
                if not sources:
                    sources = stream_sources
                if not content:
                    content = self._join_response_text_parts(completed_parts, output_item_parts)
                if not content:
                    content = self._join_response_text_parts(delta_parts, [])
                content = self._append_sources(content, sources)
                await log_info(ctx, f"content: {content}", config.debug_enabled)
                return content

            # Other typed events describe tools, reasoning, or queue state. They are
            # deliberately ignored; a completed terminal event still decides success.

        if malformed_events:
            raise ProviderCallError(
                "parse_error",
                "Malformed Responses stream event: " + malformed_events[0],
                additional_secrets=(self.api_key,),
            )
        # A transport that never produces a Responses terminal event is not a
        # successful answer. Returning empty preserves the existing same-model
        # stream-to-non-stream fallback and records an empty transport attempt.
        return ""

    async def _execute_stream_with_retry(self, headers: dict, payload: dict, ctx=None) -> str:
        timeout = self._request_timeout()

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=self._get_ssl_verify()) as client:
            async for attempt in AsyncRetrying(
                stop=self._retry_stop(),
                wait=self._retry_wait(),
                retry=retry_if_exception(_is_retryable_exception),
                reraise=True,
            ):
                with attempt:
                    request_timeout = self._request_timeout()
                    async with client.stream(
                        "POST",
                        self._api_endpoint(),
                        headers=headers,
                        json=payload,
                        timeout=request_timeout,
                    ) as response:
                        if response.status_code >= 400:
                            await response.aread()
                        response.raise_for_status()
                        return await self._parse_streaming_response(response, ctx)

    async def _parse_completion_response(self, response: httpx.Response, ctx=None) -> str:
        """解析非流式 completion 响应，兼容 JSON 和 SSE 文本 fallback"""
        content = ""
        body_text = response.text or ""
        sources: list[dict] = []

        try:
            data = response.json()
        except Exception:
            data = None

        if self.api_mode == "responses":
            if isinstance(data, dict):
                terminal_error = self._responses_terminal_error(data)
                if terminal_error is not None:
                    raise terminal_error
                content, sources = self._extract_responses_content(data)
            elif body_text.strip() and not body_text.lstrip().startswith("data:"):
                raise ProviderCallError(
                    "parse_error",
                    "Responses response was not a JSON object",
                    additional_secrets=(self.api_key,),
                )
        elif isinstance(data, dict):
            sources = self._extract_citations(data)
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                if isinstance(message, dict):
                    content = message.get("content", "") or ""
                    message_citations = self._normalize_citations(message.get("citations"))
                    if message_citations:
                        sources = self._merge_citations(sources, message_citations)

        # SSE fallback: 部分中转站即使设置 stream=False 仍可能返回 SSE 格式
        if not content and body_text.lstrip().startswith("data:"):
            class _LineResponse:
                def __init__(self, text: str):
                    self._lines = text.splitlines()

                async def aiter_lines(self):
                    for line in self._lines:
                        yield line

            content = await self._parse_streaming_response(_LineResponse(body_text), ctx)

        if self.api_mode == "responses" and not content:
            raise ProviderCallError(
                "provider_error",
                "Responses response completed without output_text content",
                additional_secrets=(self.api_key,),
            )

        content = self._append_sources(content, sources)

        await log_info(ctx, f"content: {content}", config.debug_enabled)

        return content

    def _responses_terminal_error(
        self,
        data: dict[str, Any],
        *,
        implied_status: str = "",
    ) -> ProviderCallError | None:
        status = data.get("status")
        if not isinstance(status, str) or not status.strip():
            status = implied_status
        else:
            status = status.strip().lower()

        if not status or status == "completed":
            error = data.get("error")
            if error:
                return ProviderCallError(
                    "provider_error",
                    "Responses returned an error: " + self._responses_error_detail(error),
                    additional_secrets=(self.api_key,),
                )
            return None

        if status in {"failed", "cancelled", "canceled", "incomplete"}:
            detail = data.get("error") if status == "failed" else data.get("incomplete_details")
            message = f"Responses terminal state {status}"
            if detail:
                message += ": " + self._responses_error_detail(detail)
            return ProviderCallError("provider_error", message, additional_secrets=(self.api_key,))

        return ProviderCallError(
            "provider_error",
            f"Responses returned non-terminal status: {status}",
            additional_secrets=(self.api_key,),
        )

    @staticmethod
    def _responses_error_detail(value: Any) -> str:
        if isinstance(value, dict):
            parts = [str(value[key]) for key in ("code", "reason", "message") if value.get(key)]
            if parts:
                return ": ".join(parts)
            return "unknown response error"
        return str(value)

    def _extract_responses_content(self, data: Any) -> tuple[str, list[dict]]:
        if not isinstance(data, dict):
            return "", []

        text_parts: list[str] = []
        sources = self._normalize_citations(data.get("citations"))
        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue
            content_items = item.get("content", []) or []
            if item.get("type") == "output_text":
                content_items = [item]
            if not isinstance(content_items, list):
                continue
            for content_item in content_items:
                if not isinstance(content_item, dict) or content_item.get("type") != "output_text":
                    continue
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    text_parts.append(text.strip())
                sources = self._merge_citations(
                    sources,
                    self._normalize_responses_citations(content_item.get("annotations")),
                )

        if not text_parts:
            top_level_text = data.get("output_text")
            if isinstance(top_level_text, str) and top_level_text.strip():
                text_parts.append(top_level_text.strip())
        return "\n\n".join(text_parts).strip(), sources

    def _append_sources(self, content: str, sources: list[dict]) -> str:
        if content and sources:
            return f"{content.rstrip()}\n\nsources({json.dumps(sources, ensure_ascii=False)})"
        return content

    def _extract_citations(self, data: dict) -> list[dict]:
        sources = self._normalize_citations(data.get("citations"))
        for choice in data.get("choices", []) or []:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                sources = self._merge_citations(sources, self._normalize_citations(message.get("citations")))
        return sources

    def _normalize_responses_citations(self, citations: Any) -> list[dict]:
        if not citations:
            return []
        if not isinstance(citations, list):
            citations = [citations]

        normalized: list[dict] = []
        for citation in citations:
            if not isinstance(citation, dict) or citation.get("type") != "url_citation":
                continue
            normalized = self._merge_citations(normalized, self._normalize_citations(citation))
        return normalized

    def _normalize_citations(self, citations) -> list[dict]:
        if not citations:
            return []
        if not isinstance(citations, list):
            citations = [citations]

        normalized: list[dict] = []
        seen: set[str] = set()
        for item in citations:
            source: dict = {}
            if isinstance(item, str):
                url = item.strip()
                if not url.startswith(("http://", "https://")):
                    continue
                source["url"] = url
            elif isinstance(item, dict):
                url = item.get("url") or item.get("href") or item.get("link")
                if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                    continue
                source["url"] = url
                title = item.get("title") or item.get("name") or item.get("label")
                if isinstance(title, str) and title.strip():
                    source["title"] = title.strip()
            else:
                continue

            if source["url"] in seen:
                continue
            seen.add(source["url"])
            normalized.append(source)
        return normalized

    def _merge_citations(self, *source_lists: list[dict]) -> list[dict]:
        merged: list[dict] = []
        seen: set[str] = set()
        for source_list in source_lists:
            for item in source_list or []:
                url = item.get("url")
                if not isinstance(url, str) or not url or url in seen:
                    continue
                seen.add(url)
                merged.append(item)
        return merged

    async def _execute_completion_with_retry(self, headers: dict, payload: dict, ctx=None) -> str:
        """执行带重试机制的非流式 HTTP 请求，兼容上游返回 JSON 或 SSE 文本"""
        timeout = self._request_timeout()

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=self._get_ssl_verify()) as client:
            async for attempt in AsyncRetrying(
                stop=self._retry_stop(),
                wait=self._retry_wait(),
                retry=retry_if_exception(_is_retryable_exception),
                reraise=True,
            ):
                with attempt:
                    request_timeout = self._request_timeout()
                    response = await client.post(
                        self._api_endpoint(),
                        headers=headers,
                        json=payload,
                        timeout=request_timeout,
                    )
                    response.raise_for_status()
                    return await self._parse_completion_response(response, ctx)

    async def describe_url(self, url: str, ctx=None) -> dict:
        headers = self._build_api_headers()
        payload = self._build_request_payload(url_describe_prompt, url, stream=False)
        result = await self._execute_completion_with_retry(headers, payload, ctx)
        title, extracts = url, ""
        for line in result.strip().splitlines():
            if line.startswith("Title:"):
                title = line[6:].strip() or url
            elif line.startswith("Extracts:"):
                extracts = line[9:].strip()
        return {"title": title, "extracts": extracts, "url": url}

    async def rank_sources(self, query: str, sources_text: str, total: int, ctx=None) -> list[int]:
        """让 OpenAI-compatible 模型按查询相关度对信源排序，返回排序后的序号列表"""
        headers = self._build_api_headers()
        payload = self._build_request_payload(
            rank_sources_prompt,
            f"Query: {query}\n\n{sources_text}",
            stream=False,
        )
        result = await self._execute_completion_with_retry(headers, payload, ctx)
        order: list[int] = []
        seen: set[int] = set()
        for token in result.strip().split():
            try:
                n = int(token)
                if 1 <= n <= total and n not in seen:
                    seen.add(n)
                    order.append(n)
            except ValueError:
                continue
        for i in range(1, total + 1):
            if i not in seen:
                order.append(i)
        return order
