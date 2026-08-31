import pytest

from smart_search.sciverse_schema import (
    SciverseParameterError,
    build_sciverse_meta_search_payload,
    normalize_sciverse_catalog_params,
    normalize_sciverse_retrieval,
)


def test_sciverse_meta_search_maps_convenience_filters_to_current_schema():
    payload = build_sciverse_meta_search_payload(
        query="transformer",
        title_contains="retrieval",
        abstract_contains="retrieval",
        authors="Ada Lovelace,Grace Hopper",
        journals="NeurIPS,ICLR",
        subjects="IR,NLP",
        year_from=2020,
        year_to=2024,
        filters_advanced=[{"field": "language", "op": "eq", "value": "en"}],
        page_size=25,
    )

    assert payload == {
        "query": "transformer retrieval",
        "filters": [
            {"field": "author", "operator": "FILTER_OP_IN", "value": ["Ada Lovelace", "Grace Hopper"]},
            {"field": "publication_venue_name_unified", "operator": "FILTER_OP_MATCH", "value": "NeurIPS"},
            {"field": "publication_venue_name_unified", "operator": "FILTER_OP_MATCH", "value": "ICLR"},
            {"field": "subjects", "operator": "FILTER_OP_IN", "value": ["IR", "NLP"]},
            {"field": "publication_published_year", "operator": "FILTER_OP_GTE", "value": 2020},
            {"field": "publication_published_year", "operator": "FILTER_OP_LTE", "value": 2024},
            {"field": "language", "operator": "FILTER_OP_EQ", "value": "en"},
        ],
        "sort": [],
        "freshness_boost": "NONE",
        "page": 1,
        "page_size": 25,
    }
    assert "collection" not in payload


def test_sciverse_filter_only_search_allows_current_sort_items():
    payload = build_sciverse_meta_search_payload(
        sort_by_year="asc",
        sort_advanced=[{"field": "citation_count", "order": "desc"}],
        page=2,
        page_size=100,
    )

    assert payload["query"] == ""
    assert payload["sort"] == [
        {"field": "publication_published_year", "order": "SORT_ORDER_ASC"},
        {"field": "citation_count", "order": "SORT_ORDER_DESC"},
    ]


def test_sciverse_catalog_keeps_papers_compatibility_without_an_upstream_collection_param():
    assert normalize_sciverse_catalog_params(
        collection="papers",
        include_sample_values=True,
    ) == {"include_sample_values": True, "include_field_stats": False}

    with pytest.raises(SciverseParameterError, match="collection=papers only"):
        normalize_sciverse_catalog_params(collection="authors")


@pytest.mark.parametrize(
    ("retrieval", "mode", "expected", "has_warning"),
    [
        ("", None, "hybrid", False),
        ("es", None, "es", False),
        ("", "balanced", "hybrid", True),
        ("hybrid", "quality", "hybrid", True),
    ],
)
def test_sciverse_retrieval_bridge(retrieval, mode, expected, has_warning):
    effective, warning = normalize_sciverse_retrieval(retrieval, legacy_mode=mode)

    assert effective == expected
    assert bool(warning) is has_warning


def test_sciverse_retrieval_bridge_rejects_conflicting_values():
    with pytest.raises(SciverseParameterError, match="conflicts"):
        normalize_sciverse_retrieval("milvus", legacy_mode="fast")
