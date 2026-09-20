"""The metadata registry must describe every config key, forever.

The single assertion that matters here is the key-set equality: without it, a 69th
config key gets added to config.py and the UI silently stops being complete.
"""

import pytest

from smart_search import service
from smart_search.config import Config
from smart_search.ui_metadata import (
    CONFIG_FIELDS,
    FIELDS_BY_KEY,
    KINDS,
    SECTIONS,
    TIERS,
    metadata_payload,
)


def test_every_config_key_is_described():
    described = {item.key for item in CONFIG_FIELDS}
    missing = sorted(Config._CONFIG_KEYS - described)
    unknown = sorted(described - Config._CONFIG_KEYS)
    assert not missing, (
        f"these config keys have no UI metadata: {missing}. "
        "Add them to ui_metadata.CONFIG_FIELDS."
    )
    assert not unknown, (
        f"ui_metadata describes keys that config.py does not have: {unknown}. "
        "Remove them from ui_metadata.CONFIG_FIELDS."
    )


def test_no_duplicate_keys():
    keys = [item.key for item in CONFIG_FIELDS]
    assert len(keys) == len(set(keys))
    assert len(FIELDS_BY_KEY) == len(CONFIG_FIELDS)


def test_sections_and_tiers_are_valid():
    section_ids = {section.id for section in SECTIONS}
    for item in CONFIG_FIELDS:
        assert item.section in section_ids, f"{item.key} points at unknown section {item.section}"
        assert item.tier in TIERS, f"{item.key} has unknown tier {item.tier}"
        assert item.kind in KINDS, f"{item.key} has unknown kind {item.kind}"


def test_section_order_is_unique_and_dense():
    orders = sorted(section.order for section in SECTIONS)
    assert orders == list(range(1, len(SECTIONS) + 1))


def test_every_field_is_labelled_in_both_languages():
    for item in CONFIG_FIELDS:
        assert item.label_zh.strip(), f"{item.key} has no Chinese label"
        assert item.label_en.strip(), f"{item.key} has no English label"


@pytest.mark.parametrize(
    "key,allowed_attr",
    [
        ("OPENAI_COMPATIBLE_API_MODE", "_ALLOWED_OPENAI_COMPATIBLE_API_MODES"),
        ("SMART_SEARCH_VALIDATION_LEVEL", "_ALLOWED_VALIDATION_LEVELS"),
        ("SMART_SEARCH_FALLBACK_MODE", "_ALLOWED_FALLBACK_MODES"),
        ("SMART_SEARCH_MINIMUM_PROFILE", "_ALLOWED_MINIMUM_PROFILES"),
        ("SMART_SEARCH_INTENT_ROUTER", "_ALLOWED_INTENT_ROUTER_MODES"),
    ],
)
def test_enum_choices_track_the_config_layer(key, allowed_attr):
    # A new enum member must not be able to slip past the UI.
    assert set(FIELDS_BY_KEY[key].choices) == set(getattr(Config, allowed_attr))


def test_provider_ids_are_real():
    known = set(service.provider_profiles()) | {""}
    for item in CONFIG_FIELDS:
        assert item.provider in known, f"{item.key} names unknown provider {item.provider}"


def test_capabilities_are_real():
    known = set(service.RESEARCH_PROFILE_ORDER)
    for item in CONFIG_FIELDS:
        for capability in item.capabilities:
            assert capability in known, f"{item.key} names unknown capability {capability}"


def test_every_testable_provider_has_at_least_one_field():
    described = {item.provider for item in CONFIG_FIELDS if item.provider}
    for provider in service.PROBE_KIND:
        assert provider in described, f"{provider} can be tested but has no field to configure it"


@pytest.mark.parametrize(
    "key,constant",
    [
        ("XAI_MODEL", "_DEFAULT_MODEL"),
        ("XAI_TOOLS", "_DEFAULT_XAI_TOOLS"),
        ("OPENAI_COMPATIBLE_API_MODE", "_DEFAULT_OPENAI_COMPATIBLE_API_MODE"),
        ("SMART_SEARCH_VALIDATION_LEVEL", "_DEFAULT_VALIDATION_LEVEL"),
        ("SMART_SEARCH_FALLBACK_MODE", "_DEFAULT_FALLBACK_MODE"),
        ("SMART_SEARCH_MINIMUM_PROFILE", "_DEFAULT_MINIMUM_PROFILE"),
        ("SMART_SEARCH_INTENT_ROUTER", "_DEFAULT_INTENT_ROUTER_MODE"),
        ("INTENT_ROUTER_TIMEOUT_SECONDS", "_DEFAULT_INTENT_ROUTER_TIMEOUT_SECONDS"),
        ("SMART_SEARCH_TIMEOUT_SECONDS", "_DEFAULT_SEARCH_TIMEOUT_SECONDS"),
        ("SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", "_DEFAULT_PROVIDER_COOLDOWN_SECONDS"),
        ("SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD", "_DEFAULT_PROVIDER_FAILURE_THRESHOLD"),
        ("INTENT_EMBEDDING_THRESHOLD", "_DEFAULT_INTENT_EMBEDDING_THRESHOLD"),
        ("INTENT_EMBEDDING_MARGIN", "_DEFAULT_INTENT_EMBEDDING_MARGIN"),
    ],
)
def test_displayed_defaults_match_the_config_constants(key, constant):
    assert FIELDS_BY_KEY[key].default == getattr(Config, constant)


def test_displayed_defaults_are_writable_values():
    # A default shown in the form must be one the user could actually save.
    config = Config()
    for item in CONFIG_FIELDS:
        if not item.default:
            continue
        config._validate_config_value(item.key, item.default)


def test_minimum_profile_capabilities_are_all_reachable():
    # Someone must be able to satisfy each required capability from the form alone.
    for capability in ("main_search", "docs_search", "web_fetch"):
        fields = [item for item in CONFIG_FIELDS if capability in item.capabilities]
        assert fields, f"no field can configure {capability}"


def test_payload_is_json_serialisable_and_complete():
    import json

    payload = metadata_payload()
    json.dumps(payload)
    assert len(payload["fields"]) == len(CONFIG_FIELDS)
    assert [section["order"] for section in payload["sections"]] == sorted(
        section["order"] for section in payload["sections"]
    )


# ---- provider links -----------------------------------------------------
def _readme_urls() -> set[str]:
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    text = (root / "README.md").read_text(encoding="utf-8")
    text += (root / "README.zh-CN.md").read_text(encoding="utf-8")
    return set(re.findall(r"https://[^\s)\]|`\"']+", text))


def test_every_link_is_documented_in_the_readme():
    """Links must come from the README's provider table, never from memory.

    An invented key page sends someone to a 404 while they are already unsure
    where the key lives, so the README is the single source and this assertion
    keeps the two from drifting apart.
    """
    documented = _readme_urls()
    for item in CONFIG_FIELDS:
        for label, url in (("key_url", item.key_url), ("docs_url", item.docs_url)):
            if not url:
                continue
            assert url in documented, (
                f"{item.key}.{label} = {url} is not in README.md or README.zh-CN.md. "
                "Add it to the provider table there first, or remove it here."
            )


def test_links_are_https():
    for item in CONFIG_FIELDS:
        for url in (item.key_url, item.docs_url):
            assert not url or url.startswith("https://"), f"{item.key} has a non-https link: {url}"


def test_every_probeable_provider_can_be_signed_up_for():
    """Each provider the page can test must say where to get its credential."""
    linked: dict[str, bool] = {}
    for item in CONFIG_FIELDS:
        if item.provider and (item.key_url or item.docs_url):
            linked[item.provider] = True
    # zhipu-mcp-reader shares zhipu-mcp's credential and is linked through it.
    shares = {"zhipu-mcp-reader": "zhipu-mcp"}
    missing = []
    for provider in service.PROBE_KIND:
        target = shares.get(provider, provider)
        if not linked.get(target) and not linked.get(provider):
            missing.append(provider)
    assert not missing, f"no key or docs link for: {missing}"


def test_secret_fields_for_real_providers_link_somewhere():
    # Intent routing credentials are deliberately unlinked: the README names a
    # recommended endpoint but documents no signup page for it.
    unlinked_ok = {
        "INTENT_EMBEDDING_API_KEY",
        "INTENT_CLASSIFIER_API_KEY",
    }
    for item in CONFIG_FIELDS:
        if item.kind != "secret" or item.key in unlinked_ok:
            continue
        assert item.key_url or item.docs_url, f"{item.key} is a secret with nowhere to get it"


def test_status_labels_ship_in_the_payload():
    # Both native frontends read the table from here rather than hardcoding it.
    payload = metadata_payload()
    assert payload["status_labels"], "status_labels must reach the desktop frontends"
    assert payload["status_labels"]["cooldown"]["zh"] == "冷却中"
