"""Local normalization for the current public Sciverse request schemas."""

from __future__ import annotations

import math
from typing import Any


SCIVERSE_FILTER_OPERATORS = frozenset(
    {
        "FILTER_OP_EQ",
        "FILTER_OP_NE",
        "FILTER_OP_GT",
        "FILTER_OP_GTE",
        "FILTER_OP_LT",
        "FILTER_OP_LTE",
        "FILTER_OP_IN",
        "FILTER_OP_NIN",
        "FILTER_OP_CONTAINS",
        "FILTER_OP_MATCH",
        "FILTER_OP_MATCH_PHRASE",
    }
)
SCIVERSE_RETRIEVALS = frozenset({"hybrid", "milvus", "es"})
SCIVERSE_RELATIONS = frozenset({"CITATIONS", "REFERENCES", "RELATED_WORKS"})
SCIVERSE_SORT_ORDERS = frozenset({"SORT_ORDER_ASC", "SORT_ORDER_DESC"})
SCIVERSE_SOURCE_TYPES = frozenset({"web", "pdf"})

LEGACY_SCIVERSE_MODES = frozenset({"fast", "balanced", "quality"})


class SciverseParameterError(ValueError):
    """A request cannot be represented by the current Sciverse OpenAPI schema."""


_FILTER_OPERATOR_ALIASES = {
    "=": "FILTER_OP_EQ",
    "==": "FILTER_OP_EQ",
    "EQ": "FILTER_OP_EQ",
    "!=": "FILTER_OP_NE",
    "<>": "FILTER_OP_NE",
    "NE": "FILTER_OP_NE",
    ">": "FILTER_OP_GT",
    "GT": "FILTER_OP_GT",
    ">=": "FILTER_OP_GTE",
    "GTE": "FILTER_OP_GTE",
    "<": "FILTER_OP_LT",
    "LT": "FILTER_OP_LT",
    "<=": "FILTER_OP_LTE",
    "LTE": "FILTER_OP_LTE",
    "IN": "FILTER_OP_IN",
    "NIN": "FILTER_OP_NIN",
    "NOT_IN": "FILTER_OP_NIN",
    "CONTAINS": "FILTER_OP_CONTAINS",
    "MATCH": "FILTER_OP_MATCH",
    "MATCH_PHRASE": "FILTER_OP_MATCH_PHRASE",
}
for _operator in SCIVERSE_FILTER_OPERATORS:
    _FILTER_OPERATOR_ALIASES[_operator] = _operator

_SORT_ORDER_ALIASES = {
    "ASC": "SORT_ORDER_ASC",
    "DESC": "SORT_ORDER_DESC",
    "ASCENDING": "SORT_ORDER_ASC",
    "DESCENDING": "SORT_ORDER_DESC",
}
for _order in SCIVERSE_SORT_ORDERS:
    _SORT_ORDER_ALIASES[_order] = _order


def split_sciverse_csv(values: list[str] | str | None) -> list[str]:
    """Return distinct, non-empty CSV/list values in their input order."""
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = values.split(",")
    elif isinstance(values, (list, tuple)):
        raw_values = values
    else:
        raise SciverseParameterError("Sciverse CSV values must be a string or list")
    normalized: list[str] = []
    for value in raw_values:
        text = str(value).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _non_empty_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SciverseParameterError(f"{label} must be a non-empty string")
    return value.strip()


def _normalize_filter_operator(value: Any, label: str) -> str:
    text = _non_empty_text(value, label).upper()
    operator = _FILTER_OPERATOR_ALIASES.get(text)
    if operator is None:
        allowed = ", ".join(sorted(SCIVERSE_FILTER_OPERATORS))
        raise SciverseParameterError(f"{label} must be one of {allowed}")
    return operator


def _normalize_sort_order(value: Any, label: str) -> str:
    text = _non_empty_text(value, label).upper()
    order = _SORT_ORDER_ALIASES.get(text)
    if order is None:
        allowed = ", ".join(sorted(SCIVERSE_SORT_ORDERS))
        raise SciverseParameterError(f"{label} must be one of {allowed}")
    return order


def _validate_json_value(value: Any, label: str) -> None:
    if value is None:
        raise SciverseParameterError(f"{label} must not be null")
    if isinstance(value, float) and not math.isfinite(value):
        raise SciverseParameterError(f"{label} must be finite")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{label}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SciverseParameterError(f"{label} object keys must be strings")
            _validate_json_value(item, f"{label}.{key}")
    elif not isinstance(value, (str, int, float, bool)):
        raise SciverseParameterError(f"{label} must be JSON-compatible")


def normalize_sciverse_filters(filters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize current and legacy advanced filter forms to FieldFilterItem."""
    if filters is None:
        return []
    if not isinstance(filters, list):
        raise SciverseParameterError("--filters-advanced must be a JSON array")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(filters):
        label = f"--filters-advanced[{index}]"
        if not isinstance(item, dict):
            raise SciverseParameterError(f"{label} must be a JSON object")
        unexpected = set(item) - {"field", "operator", "op", "value"}
        if unexpected:
            raise SciverseParameterError(f"{label} has unsupported keys: {', '.join(sorted(unexpected))}")
        field = _non_empty_text(item.get("field"), f"{label}.field")
        if "value" not in item:
            raise SciverseParameterError(f"{label}.value is required")
        value = item["value"]
        _validate_json_value(value, f"{label}.value")

        operator = "FILTER_OP_EQ"
        if "operator" in item:
            operator = _normalize_filter_operator(item["operator"], f"{label}.operator")
        if "op" in item:
            legacy_operator = _normalize_filter_operator(item["op"], f"{label}.op")
            if "operator" in item and legacy_operator != operator:
                raise SciverseParameterError(f"{label}.operator conflicts with legacy {label}.op")
            operator = legacy_operator
        if operator in {"FILTER_OP_IN", "FILTER_OP_NIN"} and (not isinstance(value, list) or not value):
            raise SciverseParameterError(f"{label}.value must be a non-empty array for {operator}")

        normalized.append({"field": field, "operator": operator, "value": value})
    return normalized


def normalize_sciverse_sort(sort: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalize advanced sort forms to the current SortFieldItem shape."""
    if sort is None:
        return []
    if not isinstance(sort, list):
        raise SciverseParameterError("--sort-advanced must be a JSON array")

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(sort):
        label = f"--sort-advanced[{index}]"
        if not isinstance(item, dict):
            raise SciverseParameterError(f"{label} must be a JSON object")
        unexpected = set(item) - {"field", "order"}
        if unexpected:
            raise SciverseParameterError(f"{label} has unsupported keys: {', '.join(sorted(unexpected))}")
        field = _non_empty_text(item.get("field"), f"{label}.field")
        order = "SORT_ORDER_DESC" if "order" not in item else _normalize_sort_order(item["order"], f"{label}.order")
        normalized.append({"field": field, "order": order})
    return normalized


def _normalize_positive_int(value: Any, label: str, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SciverseParameterError(f"{label} must be >= 1, got {value}")
    if maximum is not None and value > maximum:
        raise SciverseParameterError(f"{label} must be between 1 and {maximum}, got {value}")
    return value


def _normalize_sort_by_year(value: str | None) -> str:
    if value is not None and not isinstance(value, str):
        raise SciverseParameterError("sort_by_year must be a string")
    text = (value or "none").strip().lower()
    if text not in {"asc", "desc", "none"}:
        raise SciverseParameterError("sort_by_year must be one of asc, desc, none")
    return text


def _normalize_freshness_boost(value: str | None) -> str:
    if value is not None and not isinstance(value, str):
        raise SciverseParameterError("freshness_boost must be a string")
    boost = (value or "NONE").strip().upper()
    if boost not in {"NONE", "MILD", "STRONG"}:
        raise SciverseParameterError("freshness_boost must be one of NONE, MILD, STRONG")
    return boost


def _validate_sciverse_papers_collection(collection: str | None, *, command: str) -> None:
    if collection is not None and not isinstance(collection, str):
        raise SciverseParameterError("collection must be a string")
    if (collection or "papers").strip().lower() != "papers":
        raise SciverseParameterError(
            f"{command} currently supports collection=papers only; the current Sciverse OpenAPI has no collection selector"
        )


def normalize_sciverse_catalog_params(
    *,
    collection: str = "papers",
    include_sample_values: bool = False,
    include_field_stats: bool = False,
) -> dict[str, bool]:
    """Validate the legacy catalog selector without emitting it upstream."""
    _validate_sciverse_papers_collection(collection, command="sciverse-catalog")
    if not isinstance(include_sample_values, bool):
        raise SciverseParameterError("include_sample_values must be a boolean")
    if not isinstance(include_field_stats, bool):
        raise SciverseParameterError("include_field_stats must be a boolean")
    return {
        "include_sample_values": include_sample_values,
        "include_field_stats": include_field_stats,
    }


def _merge_query_parts(*values: str | None) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        if not isinstance(value, str):
            raise SciverseParameterError("query, title_contains, and abstract_contains must be strings")
        text = value.strip()
        key = text.casefold()
        if text and key not in seen:
            parts.append(text)
            seen.add(key)
    return " ".join(parts)


def normalize_sciverse_meta_search_payload(
    *,
    query: str = "",
    filters: list[dict[str, Any]] | None = None,
    sort: list[dict[str, Any]] | None = None,
    freshness_boost: str = "NONE",
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """Validate a payload that is already in current MetaSearchRequest form."""
    effective_query = _merge_query_parts(query)
    normalized_filters = normalize_sciverse_filters(filters)
    normalized_sort = normalize_sciverse_sort(sort)
    normalized_page = _normalize_positive_int(page, "page")
    normalized_page_size = _normalize_positive_int(page_size, "page_size", 200)
    if normalized_page * normalized_page_size > 10000:
        raise SciverseParameterError("page * page_size must not exceed 10000")
    if effective_query and normalized_sort:
        raise SciverseParameterError("Sciverse /meta-search does not allow query together with sort")
    boost = _normalize_freshness_boost(freshness_boost)
    return {
        "query": effective_query,
        "filters": normalized_filters,
        "sort": normalized_sort,
        "freshness_boost": boost,
        "page": normalized_page,
        "page_size": normalized_page_size,
    }


def build_sciverse_meta_search_payload(
    *,
    query: str = "",
    collection: str = "papers",
    title_contains: str = "",
    abstract_contains: str = "",
    authors: list[str] | str | None = None,
    journals: list[str] | str | None = None,
    subjects: list[str] | str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    filters_advanced: list[dict[str, Any]] | None = None,
    sort_advanced: list[dict[str, Any]] | None = None,
    sort_by_year: str = "none",
    freshness_boost: str = "NONE",
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """Translate the established CLI conveniences into the current wire schema."""
    _validate_sciverse_papers_collection(collection, command="sciverse-search")
    if year_from is not None and (isinstance(year_from, bool) or not isinstance(year_from, int)):
        raise SciverseParameterError("year_from must be an integer")
    if year_to is not None and (isinstance(year_to, bool) or not isinstance(year_to, int)):
        raise SciverseParameterError("year_to must be an integer")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise SciverseParameterError("year_from must be less than or equal to year_to")

    filters: list[dict[str, Any]] = []
    author_values = split_sciverse_csv(authors)
    if author_values:
        filters.append({"field": "author", "operator": "FILTER_OP_IN", "value": author_values})
    for journal in split_sciverse_csv(journals):
        filters.append(
            {
                "field": "publication_venue_name_unified",
                "operator": "FILTER_OP_MATCH",
                "value": journal,
            }
        )
    subject_values = split_sciverse_csv(subjects)
    if subject_values:
        filters.append({"field": "subjects", "operator": "FILTER_OP_IN", "value": subject_values})
    if year_from is not None:
        filters.append(
            {
                "field": "publication_published_year",
                "operator": "FILTER_OP_GTE",
                "value": year_from,
            }
        )
    if year_to is not None:
        filters.append(
            {
                "field": "publication_published_year",
                "operator": "FILTER_OP_LTE",
                "value": year_to,
            }
        )
    filters.extend(normalize_sciverse_filters(filters_advanced))

    sort = []
    direction = _normalize_sort_by_year(sort_by_year)
    if direction != "none":
        sort.append(
            {
                "field": "publication_published_year",
                "order": "SORT_ORDER_ASC" if direction == "asc" else "SORT_ORDER_DESC",
            }
        )
    sort.extend(normalize_sciverse_sort(sort_advanced))
    return normalize_sciverse_meta_search_payload(
        query=_merge_query_parts(query, title_contains, abstract_contains),
        filters=filters,
        sort=sort,
        freshness_boost=freshness_boost,
        page=page,
        page_size=page_size,
    )


def normalize_sciverse_retrieval(retrieval: str | None = "", legacy_mode: str | None = None) -> tuple[str, str]:
    """Resolve the modern retrieval option and the deprecated --mode bridge."""
    if retrieval is not None and not isinstance(retrieval, str):
        raise SciverseParameterError("retrieval must be a string")
    if legacy_mode is not None and not isinstance(legacy_mode, str):
        raise SciverseParameterError("mode must be a string")
    explicit = (retrieval or "").strip().lower()
    if explicit and explicit not in SCIVERSE_RETRIEVALS:
        allowed = ", ".join(sorted(SCIVERSE_RETRIEVALS))
        raise SciverseParameterError(f"retrieval must be one of {allowed}")
    legacy = (legacy_mode or "").strip().lower()
    warning = ""
    if legacy:
        if legacy not in LEGACY_SCIVERSE_MODES:
            allowed = ", ".join(sorted(LEGACY_SCIVERSE_MODES))
            raise SciverseParameterError(f"mode must be one of {allowed}")
        if explicit and explicit != "hybrid":
            raise SciverseParameterError("--mode maps to --retrieval hybrid and conflicts with the explicit --retrieval value")
        explicit = "hybrid"
        warning = "--mode is deprecated and maps to --retrieval hybrid; use --retrieval hybrid|milvus|es."
    return explicit or "hybrid", warning


def normalize_sciverse_semantic_payload(
    *,
    query: str,
    top_k: int = 10,
    retrieval: str = "hybrid",
    source_types: list[str] | str | None = None,
) -> dict[str, Any]:
    """Validate an AgenticSearchRequest using the current public enum values."""
    normalized_query = _non_empty_text(query, "query")
    if len(normalized_query) > 4096:
        raise SciverseParameterError("query must be at most 4096 characters")
    normalized_top_k = _normalize_positive_int(top_k, "top_k", 100)
    normalized_retrieval, _ = normalize_sciverse_retrieval(retrieval)
    normalized_source_types: list[str] = []
    for source_type in split_sciverse_csv(source_types):
        value = source_type.lower()
        if value not in SCIVERSE_SOURCE_TYPES:
            allowed = ", ".join(sorted(SCIVERSE_SOURCE_TYPES))
            raise SciverseParameterError(f"source_types values must be one of {allowed}")
        if value not in normalized_source_types:
            normalized_source_types.append(value)
    return {
        "query": normalized_query,
        "top_k": normalized_top_k,
        "retrieval": normalized_retrieval,
        "source_types": normalized_source_types,
    }


def normalize_sciverse_relations_payload(
    *,
    unique_id: str,
    relation: str = "CITATIONS",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """Validate the documented relation combinations before an HTTP request."""
    normalized_unique_id = _non_empty_text(unique_id, "unique_id")
    normalized_relation = _non_empty_text(relation, "relation").upper()
    if normalized_relation not in SCIVERSE_RELATIONS:
        allowed = ", ".join(sorted(SCIVERSE_RELATIONS))
        raise SciverseParameterError(f"relation must be one of {allowed}")
    return {
        "unique_id": normalized_unique_id,
        "relation": normalized_relation,
        "page": _normalize_positive_int(page, "page"),
        "page_size": _normalize_positive_int(page_size, "page_size", 200),
    }
