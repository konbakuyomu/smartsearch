import json
import time
from typing import Any

import httpx

from .base import BaseSearchProvider
from ..provider_errors import classify_provider_exception, sanitize_provider_error_message
from ..sciverse_schema import (
    SciverseParameterError,
    normalize_sciverse_catalog_params,
    normalize_sciverse_meta_search_payload,
    normalize_sciverse_relations_payload,
    normalize_sciverse_semantic_payload,
)


SCIVERSE_DEFAULT_API_URL = "https://api.sciverse.space"


class SciverseSchemaError(ValueError):
    pass


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _sanitize_message(message: str, token: str = "") -> str:
    return sanitize_provider_error_message(message, additional_secrets=(token,))


def _error_payload(exc: Exception, token: str = "") -> dict[str, str]:
    if isinstance(exc, SciverseSchemaError):
        return {"error_type": "parse_error", "error": _sanitize_message(str(exc), token)}
    error_type, error = classify_provider_exception(exc)
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code == 504:
        error_type = "timeout"
    return {"error_type": error_type, "error": _sanitize_message(error, token)}


def _config_error(tool: str, **extra: Any) -> str:
    payload = {
        "ok": False,
        "provider": "sciverse",
        "tool": tool,
        "error_type": "config_error",
        "error": "SCIVERSE_API_TOKEN is not configured",
        "elapsed_ms": 0,
    }
    payload.update({key: value for key, value in extra.items() if value})
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parameter_error(tool: str, message: str, **extra: Any) -> str:
    payload = {
        "ok": False,
        "provider": "sciverse",
        "tool": tool,
        "error_type": "parameter_error",
        "error": message,
        "elapsed_ms": 0,
    }
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _expect_response_object(data: Any, tool: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SciverseSchemaError(f"{tool} response must be a JSON object")
    return data


def _required_list(data: dict[str, Any], key: str, tool: str, *, item_objects: bool = False) -> list[Any]:
    if key not in data:
        raise SciverseSchemaError(f"{tool} response field {key!r} is required")
    value = data[key]
    if not isinstance(value, list):
        raise SciverseSchemaError(f"{tool} response field {key!r} must be an array")
    if item_objects:
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise SciverseSchemaError(f"{tool} response field {key!r} item {index} must be an object")
    return value


def _required_text(data: dict[str, Any], key: str, tool: str) -> str:
    if key not in data:
        raise SciverseSchemaError(f"{tool} response field {key!r} is required")
    value = data[key]
    if not isinstance(value, str):
        raise SciverseSchemaError(f"{tool} response field {key!r} must be a string")
    return value


def _content_from_results(results: list[Any]) -> str:
    lines = []
    for item in results:
        if not isinstance(item, dict):
            title = str(item)
        else:
            title = item.get("title") or item.get("name") or item.get("id") or item.get("unique_id") or ""
        if title:
            lines.append(str(title))
    return "\n".join(lines)


class SciverseProvider(BaseSearchProvider):
    def __init__(self, api_url: str = SCIVERSE_DEFAULT_API_URL, api_token: str | None = None, timeout: float = 30.0):
        super().__init__((api_url or SCIVERSE_DEFAULT_API_URL).rstrip("/"), api_token or "")
        self.timeout = timeout

    def get_provider_name(self) -> str:
        return "Sciverse"

    async def search(self, query: str, max_results: int = 5) -> str:
        return await self.search_papers(query=query, page_size=max_results)

    async def list_catalog(
        self,
        collection: str = "papers",
        include_sample_values: bool = False,
        include_field_stats: bool = False,
    ) -> str:
        if not self.api_key:
            return _config_error("list_catalog")
        try:
            params = normalize_sciverse_catalog_params(
                collection=collection,
                include_sample_values=include_sample_values,
                include_field_stats=include_field_stats,
            )
        except SciverseParameterError as exc:
            return _parameter_error("list_catalog", str(exc))
        return await self._request(
            "list_catalog",
            "GET",
            "/meta-catalog",
            params=params,
        )

    async def search_papers(
        self,
        query: str = "",
        filters: list[dict[str, Any]] | None = None,
        sort: list[dict[str, Any]] | None = None,
        freshness_boost: str = "NONE",
        page: int = 1,
        page_size: int = 10,
    ) -> str:
        if not self.api_key:
            return _config_error("search_papers", query=query)
        try:
            payload = normalize_sciverse_meta_search_payload(
                query=query,
                filters=filters,
                sort=sort,
                freshness_boost=freshness_boost,
                page=page,
                page_size=page_size,
            )
        except SciverseParameterError as exc:
            return _parameter_error("search_papers", str(exc), query=query)
        return await self._request("search_papers", "POST", "/meta-search", json_body=payload, query=query)

    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        retrieval: str = "hybrid",
        source_types: list[str] | str | None = None,
    ) -> str:
        if not self.api_key:
            return _config_error("semantic_search", query=query)
        try:
            payload = normalize_sciverse_semantic_payload(
                query=query,
                top_k=top_k,
                retrieval=retrieval,
                source_types=source_types,
            )
        except SciverseParameterError as exc:
            return _parameter_error("semantic_search", str(exc), query=query)
        return await self._request("semantic_search", "POST", "/agentic-search", json_body=payload, query=query)

    async def read_content(self, doc_id: str, offset: int = 0, limit: int = 4096) -> str:
        if not self.api_key:
            return _config_error("read_content", doc_id=doc_id)
        if offset < 0:
            return _parameter_error("read_content", "offset must be >= 0", doc_id=doc_id)
        if limit < 1 or limit > 16384:
            return _parameter_error("read_content", f"limit must be between 1 and 16384, got {limit}", doc_id=doc_id)
        return await self._request(
            "read_content",
            "GET",
            "/content",
            params={"doc_id": doc_id, "offset": offset, "limit": limit},
            doc_id=doc_id,
        )

    async def list_paper_relations(
        self,
        unique_id: str,
        relation: str = "CITATIONS",
        page: int = 1,
        page_size: int = 25,
    ) -> str:
        if not self.api_key:
            return _config_error("list_paper_relations", unique_id=unique_id, relation=(relation or "CITATIONS").upper())
        try:
            payload = normalize_sciverse_relations_payload(
                unique_id=unique_id,
                relation=relation,
                page=page,
                page_size=page_size,
            )
        except SciverseParameterError as exc:
            return _parameter_error("list_paper_relations", str(exc), unique_id=unique_id, relation=relation)
        return await self._request(
            "list_paper_relations",
            "POST",
            "/meta-paper-relations",
            json_body=payload,
            unique_id=payload["unique_id"],
            relation=payload["relation"],
        )

    async def _request(
        self,
        tool: str,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        **extra: Any,
    ) -> str:
        start = time.time()
        if not self.api_key:
            return _config_error(tool, **extra)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        try:
            timeout = httpx.Timeout(connect=6.0, read=self.timeout, write=10.0, pool=None)
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                if method == "GET":
                    response = await client.get(f"{self.api_url}{path}", headers=headers, params=params or {})
                else:
                    response = await client.post(f"{self.api_url}{path}", headers=headers, json=json_body or {})
                response.raise_for_status()
                data = _expect_response_object(response.json(), tool)
            output = self._normalize_response(tool, data, start, **extra)
        except Exception as exc:
            error = _error_payload(exc, self.api_key)
            output = {
                "ok": False,
                "provider": "sciverse",
                "tool": tool,
                "error_type": error["error_type"],
                "error": error["error"],
                "elapsed_ms": _elapsed_ms(start),
                **{key: value for key, value in extra.items() if value},
            }
        return json.dumps(output, ensure_ascii=False, indent=2)

    def _normalize_response(self, tool: str, data: dict[str, Any], start: float, **extra: Any) -> dict[str, Any]:
        output: dict[str, Any] = {
            "ok": True,
            "provider": "sciverse",
            "tool": tool,
            "elapsed_ms": _elapsed_ms(start),
            "raw": data,
        }
        output.update({key: value for key, value in extra.items() if value})
        if tool == "list_catalog":
            fields = _required_list(data, "fields", tool, item_objects=True)
            default_fields = _required_list(data, "default_fields", tool)
            filter_operators = _required_list(data, "filter_operators", tool)
            output.update(
                {
                    "fields": fields,
                    "default_fields": default_fields,
                    "filter_operators": filter_operators,
                    "total": len(fields),
                }
            )
            output["results"] = output["fields"]
            output["content"] = _content_from_results(output["fields"])
            return output
        if tool == "search_papers":
            results = _required_list(data, "results", tool, item_objects=True)
            output.update(
                {
                    "results": results,
                    "total": data.get("total_count", len(results)),
                    "total_count": data.get("total_count", len(results)),
                    "page": data.get("page"),
                    "page_size": data.get("page_size"),
                    "total_pages": data.get("total_pages"),
                    "next_cursor": data.get("next_cursor", ""),
                    "search_time_ms": data.get("search_time_ms"),
                }
            )
            output["content"] = _content_from_results(results)
            return output
        if tool == "semantic_search":
            hits = _required_list(data, "hits", tool, item_objects=True)
            output.update({"hits": hits, "results": hits, "total": len(hits)})
            output["content"] = _content_from_results(hits)
            return output
        if tool == "read_content":
            text = _required_text(data, "text", tool)
            output.update(
                {
                    "text": text,
                    "content": text,
                    "raw_content": text,
                    "bytes_returned": data.get("bytes_returned"),
                    "next_offset": data.get("next_offset"),
                    "more": data.get("more"),
                    "results": [],
                }
            )
            return output
        if tool == "list_paper_relations":
            items = _required_list(data, "items", tool, item_objects=True)
            relation = str(extra.get("relation") or "")
            direction = {
                "CITATIONS": "incoming: papers citing the target paper",
                "REFERENCES": "outgoing: papers cited by the target paper",
                "RELATED_WORKS": "related works for the target paper",
            }.get(relation, "")
            output.update(
                {
                    "items": items,
                    "results": items,
                    "total": data.get("total_count", len(items)),
                    "total_count": data.get("total_count", len(items)),
                    "page": data.get("page"),
                    "page_size": data.get("page_size"),
                    "total_pages": data.get("total_pages"),
                    "relation_direction": direction,
                }
            )
            output["content"] = _content_from_results(items)
            return output
        return output
