import json
import re
import time
from typing import Any

import httpx

from .base import BaseSearchProvider


def _error_payload(exc: Exception) -> dict[str, str]:
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            error_type = "auth_error"
        elif status_code == 429:
            error_type = "rate_limited"
        else:
            error_type = "network_error"
        body = (exc.response.text or exc.response.reason_phrase or "")[:300]
        return {"error_type": error_type, "error": f"HTTP {status_code}: {body}"}
    if isinstance(exc, httpx.TimeoutException):
        return {"error_type": "timeout", "error": "request timed out"}
    if isinstance(exc, httpx.RequestError):
        return {"error_type": "network_error", "error": str(exc)}
    return {"error_type": "runtime_error", "error": str(exc)}


def _extract_text(result: dict[str, Any]) -> str:
    content = result.get("content") or []
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    if isinstance(content, str):
        return content.strip()
    return ""


def _parse_markdown_results(text: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        heading = re.match(r"^###\s+\d+\.\s+(.+?)\s*$", line)
        if heading:
            if current:
                results.append(current)
            current = {"title": heading.group(1).strip(), "url": "", "description": ""}
            continue
        if current is None:
            continue
        url_match = re.match(r"^-\s+\*\*URL\*\*:\s+(\S+)", line)
        if url_match:
            current["url"] = url_match.group(1).strip()
            continue
        if line.strip() and not line.startswith("#") and not line.startswith("- **URL**"):
            description = current.get("description", "")
            current["description"] = (description + " " + line.strip()).strip()
    if current:
        results.append(current)
    if results:
        return results
    urls = re.findall(r"https?://[^\s)>\]]+", text)
    return [{"title": url, "url": url, "description": ""} for url in dict.fromkeys(urls)]


def _parse_subdomain_catalog(text: str) -> list[dict[str, str]]:
    """Parse get_sub_domains markdown headings like `### security.vuln`."""
    results: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        heading = re.match(r"^###\s+([A-Za-z0-9][A-Za-z0-9_.-]*)\s*$", line)
        if heading:
            if current:
                results.append(current)
            current = {
                "title": heading.group(1).strip(),
                "url": "",
                "description": "",
                "evidence_type": "sub_domain",
            }
            continue
        if current is None:
            continue
        if line.strip() and not line.startswith("#"):
            description = current.get("description", "")
            current["description"] = (description + " " + line.strip()).strip()
    if current:
        results.append(current)
    return results


def _split_domain(domain: str, sub_domain: str = "") -> tuple[str, str]:
    if sub_domain or "." not in domain:
        return domain, sub_domain
    parent, child = domain.split(".", 1)
    return parent, child


def _batch_query_object(query: str, max_results: int) -> dict[str, Any]:
    return {"query": query, "max_results": max_results}


def parse_sub_domain_params(
    raw_json: str = "",
    key_values: list[str] | None = None,
) -> dict[str, Any]:
    """Parse `--sub-domain-params JSON` and repeatable `--param key=value`."""
    params: dict[str, Any] = {}
    raw = (raw_json or "").strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid --sub-domain-params JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("--sub-domain-params must be a JSON object")
        params.update(parsed)
    for item in key_values or []:
        token = (item or "").strip()
        if not token or "=" not in token:
            raise ValueError(f"invalid --param value (expected key=value): {item!r}")
        key, value = token.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"invalid --param value (empty key): {item!r}")
        params[key] = value
    return params


# Current AnySearch MCP get_sub_domains enum. Empty CLI calls return this local catalog
# because the live tool requires domain/domains.
ANYSEARCH_TOP_LEVEL_DOMAINS = (
    "general",
    "resource",
    "social_media",
    "finance",
    "academic",
    "legal",
    "health",
    "business",
    "security",
    "ip",
    "code",
    "energy",
    "environment",
    "agriculture",
    "travel",
    "film",
    "gaming",
)


class AnySearchProvider(BaseSearchProvider):
    def __init__(self, api_url: str, api_key: str | None = None, timeout: float = 30.0):
        super().__init__(api_url.rstrip("/"), api_key or "")
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "AnySearch"

    async def search(self, query: str, max_results: int = 5) -> str:
        return await self.call_tool("search", {"query": query, "max_results": max_results})

    def _local_domain_catalog(self) -> str:
        """Return top-level domains without a network call when no domain is given."""
        results = [
            {
                "title": domain,
                "url": "",
                "description": f"AnySearch vertical domain: {domain}",
            }
            for domain in ANYSEARCH_TOP_LEVEL_DOMAINS
        ]
        lines = ["## AnySearch Domains", ""]
        lines.extend(f"- `{domain}`" for domain in ANYSEARCH_TOP_LEVEL_DOMAINS)
        lines.append("")
        lines.append(
            "Pass a domain to `anysearch-domains <domain>` for sub_domain details via get_sub_domains."
        )
        content = "\n".join(lines)
        return json.dumps(
            {
                "ok": True,
                "provider": "anysearch",
                "tool": "get_sub_domains",
                "content": content,
                "raw_content": content,
                "results": results,
                "total": len(results),
                "elapsed_ms": 0,
                "source": "local_catalog",
            },
            ensure_ascii=False,
            indent=2,
        )

    async def list_domains(self, domain: str = "") -> str:
        # Live AnySearch MCP renamed list_domains -> get_sub_domains.
        domain = (domain or "").strip()
        if not domain:
            return self._local_domain_catalog()
        parent, _child = _split_domain(domain, "")
        return await self.call_tool("get_sub_domains", {"domains": [parent]})

    async def vertical_search(
        self,
        query: str,
        domain: str = "",
        sub_domain: str = "",
        max_results: int = 5,
        sub_domain_params: dict[str, Any] | None = None,
    ) -> str:
        arguments: dict[str, Any] = {"query": query, "max_results": max_results}
        domain, sub_domain = _split_domain(domain, sub_domain)
        if domain:
            arguments["domain"] = domain
        if sub_domain:
            arguments["sub_domain"] = sub_domain
        if sub_domain_params:
            arguments["sub_domain_params"] = sub_domain_params
        return await self.call_tool("search", arguments)

    async def extract(self, url: str, max_length: int = 20000) -> str:
        # Live extract schema only accepts `url`; truncate locally when requested.
        raw = await self.call_tool("extract", {"url": url})
        if max_length is None or max_length <= 0:
            return raw
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if not data.get("ok"):
            return raw
        for key in ("content", "raw_content"):
            value = data.get(key)
            if isinstance(value, str) and len(value) > max_length:
                data[key] = value[:max_length]
        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            for key in ("description", "raw_content"):
                value = item.get(key)
                if isinstance(value, str) and len(value) > max_length:
                    item[key] = value[:max_length]
        data["max_length"] = max_length
        return json.dumps(data, ensure_ascii=False, indent=2)

    async def batch_search(self, queries: list[str], max_results: int = 3) -> str:
        if len(queries) > 5:
            return json.dumps(
                {
                    "ok": False,
                    "provider": "anysearch",
                    "tool": "batch_search",
                    "error_type": "parameter_error",
                    "error": f"too many queries: {len(queries)} (max 5)",
                    "elapsed_ms": 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        return await self.call_tool(
            "batch_search",
            {"queries": [_batch_query_object(query, max_results) for query in queries]},
        )

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        start = time.time()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
            output = self._normalize_response(name, arguments, data, start)
        except Exception as e:
            error = _error_payload(e)
            output = {
                "ok": False,
                "provider": "anysearch",
                "tool": name,
                "error_type": error["error_type"],
                "error": error["error"],
                "elapsed_ms": round((time.time() - start) * 1000, 2),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)

    def _normalize_response(self, name: str, arguments: dict[str, Any], data: dict[str, Any], start: float) -> dict[str, Any]:
        if "error" in data:
            error = data.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            return {
                "ok": False,
                "provider": "anysearch",
                "tool": name,
                "error_type": "provider_error",
                "error": message or "AnySearch JSON-RPC error",
                "elapsed_ms": round((time.time() - start) * 1000, 2),
            }

        result = data.get("result") or {}
        text = _extract_text(result)
        is_error = bool(result.get("isError"))
        parsed_results = [] if is_error else _parse_markdown_results(text)
        if name == "get_sub_domains" and not is_error:
            catalog = _parse_subdomain_catalog(text)
            if catalog:
                parsed_results = catalog
        if text and not is_error and not parsed_results:
            parsed_results = [
                {
                    "title": f"{name} structured evidence",
                    "url": "",
                    "description": text[:500],
                    "evidence_type": "structured",
                    "raw_content": text,
                }
            ]
        output: dict[str, Any] = {
            "ok": not is_error,
            "provider": "anysearch",
            "tool": name,
            "content": text,
            "raw_content": text,
            "results": parsed_results,
            "total": len(parsed_results),
            "elapsed_ms": round((time.time() - start) * 1000, 2),
        }
        for key in ("query", "domain", "sub_domain", "url"):
            if arguments.get(key):
                output[key] = arguments[key]
        if arguments.get("domains"):
            output["domains"] = arguments["domains"]
        if arguments.get("sub_domain_params"):
            output["sub_domain_params"] = arguments["sub_domain_params"]
        if is_error:
            output["error_type"] = "provider_error"
            output["error"] = text or "AnySearch tool returned isError=true"
        return output
