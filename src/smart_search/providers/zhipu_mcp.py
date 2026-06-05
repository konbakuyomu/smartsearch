import json
import re
import time
from typing import Any

import httpx


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


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
        url_match = re.search(r"https?://[^\s)>\]]+", line)
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
    urls = re.findall(r"https?://[^\s)>\]]+", text)
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

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        start = time.time()
        if not self.api_key:
            return json.dumps(
                {
                    "ok": False,
                    "provider": self.provider_id,
                    "tool": name,
                    "error_type": "config_error",
                    "error": "ZHIPU_MCP_API_KEY is not configured.",
                    "elapsed_ms": _elapsed_ms(start),
                },
                ensure_ascii=False,
                indent=2,
            )

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = _parse_sse_or_json(response)
            output = self._normalize_response(name, arguments, data, start)
        except Exception as e:
            error = _error_payload(e)
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
            return {
                "ok": False,
                "provider": self.provider_id,
                "tool": name,
                "error_type": "provider_error",
                "error": message or "Zhipu MCP JSON-RPC error",
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
            results = [] if is_error else _parse_markdown_results(text, self.provider_id)
            output["results"] = results
            output["total"] = len(results)
        if is_error:
            output["error_type"] = content_error[0] if content_error else "provider_error"
            output["error"] = content_error[1] if content_error else (text or "Zhipu MCP tool returned isError=true")
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
