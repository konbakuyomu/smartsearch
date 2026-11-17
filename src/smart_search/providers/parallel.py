"""Anonymous Unified MCP search for an explicitly confirmed foreground query."""

import json
from typing import Any
from urllib.parse import urlsplit

import httpx

from ..provider_errors import ProviderCallError
from .zhipu_mcp import _parse_sse_or_json

PARALLEL_MCP_URL = "https://mcp.parallel.ai/mcp"
PARALLEL_USER_AGENT = "smart-search/0.1.34 (Parallel MCP)"
_PROTOCOL_VERSION = "2025-03-26"


def _result(response: httpx.Response, request_id: int) -> dict[str, Any]:
    response.raise_for_status()
    try:
        data = _parse_sse_or_json(response)
    except (ValueError, TypeError) as exc:
        raise ProviderCallError("provider_error", "Parallel MCP returned an invalid response") from exc
    if not isinstance(data, dict) or data.get("id") != request_id or data.get("error"):
        raise ProviderCallError("provider_error", "Parallel MCP request failed")
    result = data.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        raise ProviderCallError("provider_error", "Parallel MCP tool is unavailable or returned an error")
    return result


def _search_results(result: dict[str, Any], count: int) -> list[dict]:
    data = result.get("structuredContent")
    if data is None:
        try:
            data = json.loads(next(item["text"] for item in result.get("content", []) if item.get("type") == "text"))
        except (ValueError, StopIteration, KeyError, TypeError) as exc:
            raise ProviderCallError("provider_error", "Parallel MCP returned invalid search data") from exc
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ProviderCallError("provider_error", "Parallel MCP returned invalid search results")
    results = []
    for item in data["results"]:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str):
            continue
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password
        except ValueError:
            valid = False
        if not valid:
            continue
        excerpts = item.get("excerpts")
        if not isinstance(excerpts, list) or not all(isinstance(part, str) for part in excerpts):
            continue
        results.append({"url": url, "title": item.get("title") if isinstance(item.get("title"), str) else url,
                        "content": "\n\n".join(excerpts), "published_date": item.get("publish_date") or ""})
        if len(results) >= count:
            break
    return results


async def search_public_docs(query: str, count: int = 5, *, verify: bool = True) -> list[dict]:
    """One tool call; no credentials, model context, session history or fallback."""
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "User-Agent": PARALLEL_USER_AGENT}
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False, verify=verify) as client:
        response = await client.post(PARALLEL_MCP_URL, headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": _PROTOCOL_VERSION, "capabilities": {},
                "clientInfo": {"name": "smart-search", "version": "0.1.34"},
            },
        })
        initialized = _result(response, 1)
        if initialized.get("protocolVersion") != _PROTOCOL_VERSION:
            raise ProviderCallError("provider_error", "Parallel MCP protocol version is unsupported")
        headers["MCP-Protocol-Version"] = _PROTOCOL_VERSION
        if response.headers.get("Mcp-Session-Id"):
            headers["Mcp-Session-Id"] = response.headers["Mcp-Session-Id"]
        response = await client.post(PARALLEL_MCP_URL, headers=headers,
                                     json={"jsonrpc": "2.0", "method": "notifications/initialized"})
        response.raise_for_status()
        response = await client.post(PARALLEL_MCP_URL, headers=headers,
                                     json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = _result(response, 2).get("tools")
        if not isinstance(tools, list) or not any(isinstance(tool, dict) and tool.get("name") == "web_search" for tool in tools):
            raise ProviderCallError("provider_error", "Parallel MCP web_search is unavailable")
        response = await client.post(PARALLEL_MCP_URL, headers=headers, json={
            "jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "web_search", "arguments": {
                    "objective": "Find public software documentation matching the search query.",
                    "search_queries": [query],
                },
            },
        })
        return _search_results(_result(response, 3), count)
