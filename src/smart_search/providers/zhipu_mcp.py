from ..i18n import source_message
import json
import re
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..provider_errors import classify_provider_exception, sanitize_provider_error_message

_MCP_PROTOCOL_VERSION = "2024-11-05"


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


class ZhipuMCPSessionError(Exception):
    pass


def _error_payload(exc: Exception, api_key: str = "") -> dict[str, str]:
    if isinstance(exc, ZhipuMCPSessionError):
        return {
            "error_type": "provider_error",
            "error": sanitize_provider_error_message(str(exc), additional_secrets=(api_key,)),
        }
    error_type, error = classify_provider_exception(exc, additional_secrets=(api_key,))
    return {"error_type": error_type, "error": error}


def _mask_secret(text: str, secret: str) -> str:
    return text.replace(secret, "***") if secret else text


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


def _parse_sse_or_json(response: httpx.Response) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    if "json" in content_type:
        return response.json()
    data_lines = []
    for line in response.text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
    for line in reversed(data_lines):
        if not line or line == "[DONE]":
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return response.json()


def _jsonrpc_error_message(data: dict[str, Any]) -> str:
    error = data.get("error") or {}
    if isinstance(error, dict):
        message = error.get("message")
        if message:
            return str(message)
    if error:
        return str(error)
    return ""


# Quotes and backslashes end a URL: otherwise a JSON string that slipped into the
# Markdown parser swallows the following `","content":"...` into the link.
_URL_PATTERN = re.compile(r"https?://[^\s)>\]\"\\]+")
_JSON_RESULTS_START = re.compile(r'^\s*(?:\[\s*[\{\]]|\{|"\s*\[)')


def _valid_http_url(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ""
    return value if parsed.scheme in {"http", "https"} and parsed.hostname else ""


def _parse_json_results(text: str, provider: str) -> list[dict[str, str]] | None:
    """Map web_search_prime's JSON array (possibly encoded twice) to results.

    Returns None when the text is not JSON and should go to the Markdown parser.
    Raises ValueError for JSON that is malformed or has an unknown shape.
    """
    decoded: Any = (text or "").strip()
    if not decoded.startswith(("[", "{", '"')):
        return None
    for layer in range(2):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError as exc:
            # Markdown may also start with "[" (a link); only JSON-shaped text is an error.
            if not _JSON_RESULTS_START.match(decoded):
                return None if layer == 0 else _parse_markdown_results(decoded, provider)
            raise ValueError(source_message('Zhipu MCP returned malformed JSON search results')) from exc
    if isinstance(decoded, str):
        return _parse_markdown_results(decoded, provider)
    if not isinstance(decoded, list):
        raise ValueError(source_message('Zhipu MCP returned search results in an unknown format'))
    results: list[dict[str, str]] = []
    for item in decoded:
        if not isinstance(item, dict):
            continue
        url = _valid_http_url(item.get("link")) or _valid_http_url(item.get("url"))
        if not url:
            continue
        title = item.get("title")
        results.append({
            "title": title.strip() if isinstance(title, str) and title.strip() else url,
            "url": url,
            "description": item.get("content") if isinstance(item.get("content"), str) else "",
            "provider": provider,
            "source": item.get("media") if isinstance(item.get("media"), str) else "",
            "published_date": item.get("publish_date") if isinstance(item.get("publish_date"), str) else "",
            "refer": item.get("refer") if isinstance(item.get("refer"), str) else "",
        })
    return results


def _parse_markdown_results(text: str, provider: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        heading = re.match(r"^#{2,4}\s+(?:\d+[.)]\s*)?(.+?)\s*$", line.strip())
        if heading:
            if current:
                results.append(current)
            current = {"title": heading.group(1).strip(), "url": "", "description": "", "provider": provider}
            continue
        url_match = _URL_PATTERN.search(line)
        if url_match:
            if current is None:
                current = {"title": url_match.group(0), "url": "", "description": "", "provider": provider}
            current["url"] = current.get("url") or url_match.group(0).rstrip(".,")
            continue
        if current is not None and line.strip() and not line.startswith("#"):
            current["description"] = (current.get("description", "") + " " + line.strip()).strip()
    if current:
        results.append(current)
    if results:
        return results
    urls = _URL_PATTERN.findall(text)
    return [{"title": url, "url": url, "description": "", "provider": provider} for url in dict.fromkeys(urls)]


def _content_error(text: str) -> tuple[str, str] | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    if stripped.lower().startswith("mcp error"):
        lowered = stripped.lower()
        error_type = "auth_error" if "-401" in stripped or "api key" in lowered else "provider_error"
        return error_type, stripped
    decoded: Any = stripped
    for _ in range(2):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except json.JSONDecodeError:
            break
    if isinstance(decoded, dict) and decoded.get("error"):
        return "provider_error", str(decoded.get("error"))
    return None


class ZhipuMCPProvider:
    def __init__(self, api_url: str, api_key: str, timeout: float = 30.0, provider_id: str = "zhipu-mcp"):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.provider_id = provider_id
        self._session_id: str | None = None
        self._request_id = 0

    def _next_request_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self, session_id: str = "") -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if session_id:
            headers["Mcp-Session-Id"] = session_id
        return headers

    async def _ensure_session(self, client: httpx.AsyncClient) -> str:
        if self._session_id:
            return self._session_id

        payload = {
            "jsonrpc": "2.0",
            "id": self._next_request_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "smart-search", "version": "1"},
            },
        }
        response = await client.post(self.api_url, headers=self._headers(), json=payload)
        response.raise_for_status()
        data = _parse_sse_or_json(response)
        if "error" in data:
            message = _jsonrpc_error_message(data)
            raise ZhipuMCPSessionError(message or source_message('Zhipu MCP initialize failed.'))

        session_id = (response.headers.get("Mcp-Session-Id") or "").strip()
        if not session_id:
            raise ZhipuMCPSessionError(source_message('Zhipu MCP initialize response did not include Mcp-Session-Id.'))
        self._session_id = session_id
        return session_id

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        start = time.time()
        if not self.api_key:
            return json.dumps(
                {
                    "ok": False,
                    "provider": self.provider_id,
                    "tool": name,
                    "error_type": "config_error",
                    "error": source_message('ZHIPU_MCP_API_KEY is not configured.'),
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )

        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                session_id = await self._ensure_session(client)
                payload = {
                    "jsonrpc": "2.0",
                    "id": self._next_request_id(),
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                }
                headers = self._headers(session_id)
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = _parse_sse_or_json(response)
            output = self._normalize_response(name, arguments, data, start)
        except Exception as e:
            error = _error_payload(e, self.api_key)
            output = {
                "ok": False,
                "provider": self.provider_id,
                "tool": name,
                "error_type": error["error_type"],
                "error": _mask_secret(error["error"], self.api_key),
                "elapsed_ms": _elapsed_ms(start),
            }
        return json.dumps(output, ensure_ascii=False, indent=2)

    def _normalize_response(self, name: str, arguments: dict[str, Any], data: dict[str, Any], start: float) -> dict[str, Any]:
        if "error" in data:
            error = data.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            safe_error = sanitize_provider_error_message(
                message or "Zhipu MCP JSON-RPC error", additional_secrets=(self.api_key,)
            )
            return {
                "ok": False,
                "provider": self.provider_id,
                "tool": name,
                "error_type": "provider_error",
                "error": safe_error,
                "elapsed_ms": _elapsed_ms(start),
            }

        result = data.get("result") or {}
        text = _extract_text(result)
        content_error = _content_error(text)
        is_error = bool(result.get("isError")) or bool(content_error)
        output: dict[str, Any] = {
            "ok": not is_error,
            "provider": self.provider_id,
            "tool": name,
            "content": text,
            "raw_content": text,
            "elapsed_ms": _elapsed_ms(start),
        }
        for key in ("query", "url", "repo", "path", "ref"):
            if arguments.get(key):
                output[key] = arguments[key]
        if name == "webReader":
            output["url"] = arguments.get("url", "")
        else:
            results: list[dict[str, str]] = []
            if not is_error:
                try:
                    parsed = _parse_json_results(text, self.provider_id) if name == "web_search_prime" else None
                except ValueError as exc:
                    content_error = ("parse_error", str(exc))
                    is_error = True
                    output["ok"] = False
                else:
                    results = parsed if parsed is not None else _parse_markdown_results(text, self.provider_id)
            output["results"] = results
            output["total"] = len(results)
        if is_error:
            output["error_type"] = content_error[0] if content_error else "provider_error"
            safe_error = sanitize_provider_error_message(
                content_error[1] if content_error else (text or "Zhipu MCP tool returned isError=true"),
                additional_secrets=(self.api_key,),
            )
            output["content"] = safe_error
            output["raw_content"] = safe_error
            output["error"] = safe_error
        return output

    async def web_search(self, query: str, count: int = 5) -> str:
        del count
        return await self.call_tool("web_search_prime", {"search_query": query})

    async def web_reader(self, url: str) -> str:
        return await self.call_tool("webReader", {"url": url})

    async def search_doc(self, repo: str, query: str, max_results: int = 5) -> str:
        del max_results
        return await self.call_tool("search_doc", {"repo_name": repo, "query": query})

    async def get_repo_structure(self, repo: str, ref: str = "") -> str:
        arguments = {"repo_name": repo}
        if ref:
            arguments["dir_path"] = ref
        return await self.call_tool("get_repo_structure", arguments)

    async def read_file(self, repo: str, path: str, ref: str = "") -> str:
        del ref
        arguments = {"repo_name": repo, "file_path": path}
        return await self.call_tool("read_file", arguments)
