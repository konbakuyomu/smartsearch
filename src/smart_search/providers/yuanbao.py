"""Tencent Yuanbao Search, served as the Tencent Cloud wsa SearchPro API.

Requests are signed with Tencent Cloud API 3.0 TC3-HMAC-SHA256 from a SecretId and
SecretKey, the same way the official SDK signs them. Failures arrive as HTTP 200
with `Response.Error`.
"""
from ..i18n import source_message

import datetime
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import BaseSearchProvider
from ..provider_errors import ProviderCallError, classify_provider_exception

SERVICE = "wsa"
ACTION = "SearchPro"
VERSION = "2025-05-08"
CONTENT_TYPE = "application/json"

ERROR_TYPES = (
    (("AuthFailure", "UnauthorizedOperation"), "auth_error"),
    (("RequestLimitExceeded", "LimitExceeded"), "rate_limited"),
    (("InvalidParameter", "MissingParameter", "UnknownParameter"), "parameter_error"),
)


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _signed_headers(secret_id: str, secret_key: str, host: str, body: str, timestamp: int) -> dict[str, str]:
    date = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y-%m-%d")
    canonical_request = "\n".join([
        "POST", "/", "", f"content-type:{CONTENT_TYPE}\nhost:{host}\n", "content-type;host",
        hashlib.sha256(body.encode("utf-8")).hexdigest(),
    ])
    scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = "\n".join([
        "TC3-HMAC-SHA256", str(timestamp), scope, hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    key = ("TC3" + secret_key).encode("utf-8")
    for part in (date, SERVICE, "tc3_request"):
        key = hmac.new(key, part.encode("utf-8"), hashlib.sha256).digest()
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Authorization": f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, SignedHeaders=content-type;host, Signature={signature}",
        "Content-Type": CONTENT_TYPE,
        "Host": host,
        "X-TC-Action": ACTION,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": VERSION,
    }


def _api_error(error: dict[str, Any], secrets: tuple[str, ...]) -> ProviderCallError:
    code = str(error.get("Code") or "UnknownError")
    error_type = next((kind for prefixes, kind in ERROR_TYPES if code.startswith(prefixes)), "provider_error")
    return ProviderCallError(error_type, f"{code}: {error.get('Message') or ''}".strip(), additional_secrets=secrets)


def _normalize_page(raw: Any) -> dict[str, Any] | None:
    page = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(page, dict) or not page.get("url"):
        return None
    out: dict[str, Any] = {
        "title": page.get("title") or "",
        "url": page["url"],
        "description": page.get("passage") or "",
    }
    # Only the standard and flagship tiers return the longer, query-specific summary.
    if page.get("content"):
        out["content"] = page["content"]
    if page.get("site"):
        out["source"] = page["site"]
    if page.get("date"):
        out["published_date"] = page["date"]
    out["provider"] = "yuanbao"
    return out


class YuanbaoSearchProvider(BaseSearchProvider):
    def __init__(self, api_url: str, secret_id: str, secret_key: str, timeout: float = 30.0):
        super().__init__(api_url.rstrip("/"), secret_key)
        self.secret_id = secret_id or ""
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "yuanbao"

    async def search(self, query: str, max_results: int = 10, ctx=None) -> str:
        start = time.time()
        if not (self.secret_id and self.api_key):
            return json.dumps(
                {
                    "ok": False,
                    "provider": "yuanbao",
                    "query": query,
                    "error_type": "config_error",
                    "error": source_message('YUANBAO_SECRET_ID and YUANBAO_SECRET_KEY are not configured.'),
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )
        secrets = (self.secret_id, self.api_key)
        # Sign exactly these bytes: json.dumps defaults, as the official SDK sends them.
        body = json.dumps({"Query": query})
        headers = _signed_headers(self.secret_id, self.api_key, urlparse(self.api_url).netloc, body, int(time.time()))
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.api_url + "/", headers=headers, content=body.encode("utf-8"))
                response.raise_for_status()
                payload = response.json()
            result = payload.get("Response") if isinstance(payload, dict) else None
            if not isinstance(result, dict):
                raise ProviderCallError("parse_error", source_message('Yuanbao search response is missing Response'))
            if isinstance(result.get("Error"), dict):
                raise _api_error(result["Error"], secrets)
            pages = result.get("Pages") or []
            if not isinstance(pages, list):
                raise ProviderCallError("parse_error", source_message('Yuanbao search Pages is not a list'))
            normalized = [item for item in map(_normalize_page, pages) if item][:max_results]
            output: dict[str, Any] = {
                "ok": True,
                "provider": "yuanbao",
                "query": query,
                "results": normalized,
                "total_results": len(normalized),
                "elapsed_ms": _elapsed_ms(start),
            }
        except Exception as exc:
            error_type, error = classify_provider_exception(exc, additional_secrets=secrets)
            output = {
                "ok": False,
                "provider": "yuanbao",
                "query": query,
                "error_type": error_type,
                "error": error,
                "elapsed_ms": _elapsed_ms(start),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)
