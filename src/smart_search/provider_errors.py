"""Stable provider failure classification shared by service call boundaries."""

from __future__ import annotations

import asyncio
import json
import re
import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from collections.abc import Iterable
from typing import Final

import httpx


APPROVED_PROVIDER_ERROR_TYPES: Final[frozenset[str]] = frozenset(
    {
        "parameter_error",
        "auth_error",
        "timeout",
        "rate_limited",
        "network_error",
        "parse_error",
        "quality_error",
        "provider_error",
        "runtime_error",
    }
)

_URL_CREDENTIALS_RE = re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (?P<prefix>
        \b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|token|secret|password|authorization)\b
        \s*[\"']?\s*[:=]\s*(?:bearer\s+)?
    )
    (?P<value>\"[^\"]*\"|'[^']*'|[^\s,;}&]+)
    """
)
_BEARER_SECRET_RE = re.compile(r"(?i)\bbearer\s+[^\s,;}&]+")


def retry_delay(response: httpx.Response | None = None, *, message: str = "") -> float | None:
    """Parse upstream retry hints; unknown delays retain the normal policy."""
    if response is not None:
        for header, scale in (("retry-after-ms", .001), ("retry-after", 1.0)):
            value = response.headers.get(header, "").strip()
            if not value:
                continue
            try:
                delay = float(value) * scale
                if math.isfinite(delay) and delay >= 0:
                    return delay
            except ValueError:
                if header == "retry-after":
                    try:
                        date = parsedate_to_datetime(value)
                        date = date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
                        return max(0, (date - datetime.now(timezone.utc)).total_seconds())
                    except (ValueError, TypeError, OverflowError):
                        pass
        try:
            message = response.text
        except httpx.ResponseNotRead:
            return None
    match = re.search(r"(?:try again in|retry after)\s+(\d+(?:\.\d+)?)\s*(ms|milliseconds?|s|seconds?)\b", message, re.I)
    if match:
        delay = float(match[1]) / (1000 if match[2].lower().startswith("m") else 1)
        return delay if math.isfinite(delay) else None
    return None


def sanitize_provider_error_message(
    value: object,
    *,
    additional_secrets: Iterable[str] = (),
    limit: int = 300,
) -> str:
    """Return a compact provider error excerpt without credentials."""
    from .config import config
    from .i18n import Message, render_messages

    # Only explicit tool-owned copy is translated. Upstream errors are never guessed.
    text = render_messages(value) if isinstance(value, Message) else str(value or "")
    for secret in sorted(set(additional_secrets) | set(config.secret_values()), key=len, reverse=True):
        if secret:
            text = text.replace(str(secret), "[REDACTED]")
    text = _URL_CREDENTIALS_RE.sub(r"\1[REDACTED]@", text)
    text = _SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group('prefix')}[REDACTED]", text)
    text = _BEARER_SECRET_RE.sub("Bearer [REDACTED]", text)
    return " ".join(text.split())[:limit]


class ProviderCallError(RuntimeError):
    """A provider failure whose public error type is already classified."""

    def __init__(self, error_type: str, error: str, *, additional_secrets: Iterable[str] = ()):
        if error_type not in APPROVED_PROVIDER_ERROR_TYPES:
            error_type = "runtime_error"
        safe_error = sanitize_provider_error_message(error, additional_secrets=additional_secrets)
        super().__init__(safe_error)
        self.error_type = error_type
        self.error = safe_error


def _response_excerpt(response: httpx.Response | None, *, additional_secrets: Iterable[str] = ()) -> str:
    if response is None:
        return ""
    try:
        text = response.text
    except Exception:
        text = ""
    return sanitize_provider_error_message(text or response.reason_phrase or "", additional_secrets=additional_secrets)


def classify_provider_exception(
    exc: BaseException,
    *,
    additional_secrets: Iterable[str] = (),
) -> tuple[str, str]:
    """Map transport and decoding failures to the public provider taxonomy."""
    secrets = tuple(str(secret) for secret in additional_secrets if secret)
    if isinstance(exc, ProviderCallError):
        return exc.error_type, sanitize_provider_error_message(exc.error, additional_secrets=secrets)
    if isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError, TimeoutError)):
        return "timeout", sanitize_provider_error_message(str(exc) or "request timed out", additional_secrets=secrets)
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        status = response.status_code if response is not None else 0
        if status in {400, 422}:
            error_type = "parameter_error"
        elif status in {401, 403}:
            error_type = "auth_error"
        elif status == 408:
            error_type = "timeout"
        elif status == 429:
            error_type = "rate_limited"
        elif 500 <= status <= 599:
            error_type = "network_error"
        else:
            error_type = "provider_error"
        excerpt = _response_excerpt(response, additional_secrets=secrets)
        message = f"HTTP {status}"
        if status == 429 and (delay := retry_delay(response)) is not None:
            message += f" retry after {delay}s"
        if excerpt:
            message = f"{message}: {excerpt}"
        return error_type, message
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError, httpx.DecodingError)):
        return "parse_error", sanitize_provider_error_message(
            str(exc) or "invalid provider response", additional_secrets=secrets
        )
    if isinstance(exc, httpx.RequestError):
        return "network_error", sanitize_provider_error_message(
            str(exc) or "network request failed", additional_secrets=secrets
        )
    return "runtime_error", sanitize_provider_error_message(
        str(exc) or exc.__class__.__name__, additional_secrets=secrets
    )


def provider_call_error(exc: BaseException, *, additional_secrets: Iterable[str] = ()) -> ProviderCallError:
    """Return a classified error while preserving an existing classification."""
    secrets = tuple(str(secret) for secret in additional_secrets if secret)
    if isinstance(exc, ProviderCallError):
        if not secrets:
            return exc
        error_type, error = classify_provider_exception(exc, additional_secrets=secrets)
        return ProviderCallError(error_type, error, additional_secrets=secrets)
    error_type, error = classify_provider_exception(exc, additional_secrets=secrets)
    return ProviderCallError(error_type, error, additional_secrets=secrets)
