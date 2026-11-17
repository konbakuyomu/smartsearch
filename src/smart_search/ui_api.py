"""Request handlers for the local config UI.

Every function here is a thin adapter over an existing ``service`` / ``config`` /
``skill_installer`` call and returns a plain dict. Nothing in this module knows about
HTTP, so the whole API surface is unit-testable without opening a socket, and the
"no business logic in the server" rule is structural rather than a convention.

Secrets never leave the process: reads go through ``config.get_saved_config(masked=True)``
and ``config_list(show_secrets=True)`` is never called from here.
"""

from __future__ import annotations
from .i18n import source_message

from typing import Any
import math

from . import service
from .config import config
from .skill_installer import (
    DEFAULT_SKILL_TARGET_IDS,
    SKILL_TARGETS,
    SkillInstallError,
    install_skill_targets,
    parse_skill_targets,
    status_skill_targets,
)
from .ui_metadata import CONFIG_FIELDS, metadata_payload


def _parameter_error(message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error_type": "parameter_error", "error": message, **extra}


def _capability_chains() -> dict[str, list[str]]:
    """The declared fallback order per capability, straight from the router's table."""
    return {
        capability: list(providers)
        for capability, providers in service.RESEARCH_PROFILE_ORDER.items()
    }


def status() -> dict[str, Any]:
    """Everything the page shows, computed locally. Makes no network calls."""
    with config.snapshot():
        return _status()


def _status() -> dict[str, Any]:
    info = config.get_config_info()
    minimum = service.validate_minimum_profile()
    effective = config.effective_values(masked=False)
    return {
        "ok": True,
        "error_type": "",
        "error": "",
        "values": config.effective_values(masked=True),
        "saved_values": config.get_saved_config(masked=True),
        # Empty and short keys can have the same legacy mask. Report presence
        # separately so native clients never mistake an empty key for a saved one.
        "secret_presence": {
            field.key: bool(effective.get(field.key))
            for field in CONFIG_FIELDS if field.kind == "secret"
        },
        "revision": config.snapshot_revision(),
        "sources": config.get_config_sources(),
        "resolved": {
            "config_status": info.get("config_status", ""),
            "config_parameter_errors": info.get("config_parameter_errors", []),
            "primary_api_mode": info.get("primary_api_mode", ""),
            "resolved_log_dir": info.get("resolved_log_dir", ""),
            "file_logging_enabled": info.get("file_logging_enabled", False),
        },
        "capability_status": service.get_capability_status(),
        "capability_chains": _capability_chains(),
        "minimum_profile": minimum,
        "provider_health": service.provider_health_status(),
        "provider_profiles": service.provider_profiles(),
        "probe_kinds": dict(service.PROBE_KIND),
        "config_path": service.config_path(),
    }


def state() -> dict[str, Any]:
    """`status` plus the field metadata the page only needs to fetch once."""
    payload = status()
    payload["metadata"] = metadata_payload()
    payload["skill_targets"] = [
        {"id": target.target_id, "label": target.label, "default": target.target_id in DEFAULT_SKILL_TARGET_IDS}
        for target in SKILL_TARGETS
    ]
    return payload


async def test_provider(payload: dict[str, Any]) -> dict[str, Any]:
    """Probe one provider. Every call costs a real request, so the page asks first."""
    provider = str(payload.get("provider") or "").strip()
    if not provider:
        return _parameter_error(source_message('provider is required'), known_providers=sorted(service.PROBE_KIND))
    overrides = payload.get("overrides")
    if overrides is not None and not isinstance(overrides, dict):
        return _parameter_error(source_message('overrides must be an object'))
    timeout = payload.get("timeout_seconds")
    try:
        timeout_seconds = float(timeout) if timeout is not None else None
    except (TypeError, ValueError):
        return _parameter_error(source_message('timeout_seconds must be a number'))
    if timeout_seconds is not None and (not math.isfinite(timeout_seconds) or timeout_seconds <= 0):
        return _parameter_error(source_message('timeout_seconds must be a positive finite number'))
    return await service.test_provider_connection(
        provider,
        overrides={str(k): str(v) for k, v in overrides.items()} if overrides is not None else None,
        timeout_seconds=timeout_seconds,
    )


def apply_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Save a batch of edits, all-or-nothing, then hand back the refreshed status.

    A key whose value comes from an environment variable is refused rather than
    written: the write would succeed and change nothing the user can see, because
    the environment wins on every read.
    """
    set_values = payload.get("set", {})
    unset_keys = payload.get("unset", [])
    if not isinstance(set_values, dict):
        return _parameter_error(source_message('set must be an object'))
    if not isinstance(unset_keys, list):
        return _parameter_error(source_message('unset must be a list'))

    normalized = {str(key).strip().upper(): "" if value is None else str(value) for key, value in set_values.items()}
    unset = [str(key).strip().upper() for key in unset_keys]

    shadowed = sorted(
        key for key in list(normalized) + unset
        if key in config._CONFIG_KEYS and config.get_config_source(key) == "environment"
    )
    if shadowed:
        return _parameter_error(
            source_message('These keys are set by environment variables, which win over the config file: {0}', ", ".join(shadowed)),
            shadowed=shadowed,
        )

    revision = payload.get("revision")
    if revision is not None and not isinstance(revision, str):
        return _parameter_error(source_message('revision must be a string'))
    result = service.config_update(normalized, unset, expected_revision=revision)
    with config.snapshot(directory=str(config.config_file.parent)):
        result["status"] = status()
    return result


def preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Answer "would this configuration pass?" without saving or calling anything."""
    values = payload.get("values")
    if not isinstance(values, dict):
        return _parameter_error(source_message('values must be an object'))
    merged = {str(key).strip().upper(): "" if value is None else str(value) for key, value in values.items()}
    with config.snapshot(merged):
        capability_status = service.get_capability_status()
        # The same minimum profile the overview reports, so a draft never "passes" differently.
        minimum = service._minimum_profile_result(config.minimum_profile, capability_status)
    return {
        "ok": True,
        "error_type": "",
        "error": "",
        "capability_status": capability_status,
        "required": minimum["required"],
        "missing": minimum["missing"],
        "minimum_profile_ok": minimum["ok"],
    }


async def run_doctor() -> dict[str, Any]:
    """The full diagnostic. Fires every probe at once, so it is never automatic."""
    return await service.doctor()


RUNNABLE_COMMANDS = ("route", "search")


async def run_query(payload: dict[str, Any]) -> dict[str, Any]:
    """Run one query from the page.

    `route` is offline and free, so it is the default and the safe thing to try
    first. `search` is a real, billable search and the page asks before sending it.
    """
    command = str(payload.get("command") or "route").strip().lower()
    if command not in RUNNABLE_COMMANDS:
        return _parameter_error(
            source_message('command must be one of {0}', ', '.join(RUNNABLE_COMMANDS)),
            known_commands=list(RUNNABLE_COMMANDS),
        )
    query = str(payload.get("query") or "").strip()
    if not query:
        return _parameter_error(source_message('query is required'))
    if len(query) > 2000:
        return _parameter_error(source_message('query is too long'))

    provider = str(payload.get("provider") or "auto").strip().lower()
    if provider not in {"auto", "parallel"}:
        return _parameter_error("provider must be auto or parallel")
    if command == "route":
        return await service.route(query, allow_remote=False)
    if provider == "parallel" and payload.get("public_query_confirmed") is not True:
        return _parameter_error("Confirm that the typed query is for public software documentation before sending it to Parallel")

    timeout = payload.get("timeout_seconds")
    try:
        timeout_seconds = float(timeout) if timeout is not None else None
    except (TypeError, ValueError):
        return _parameter_error(source_message('timeout_seconds must be a number'))
    if provider == "parallel":
        return await service.search(query, timeout_seconds=timeout_seconds, foreground_provider=provider)
    return await service.search(query, timeout_seconds=timeout_seconds)


def reset_health(payload: dict[str, Any]) -> dict[str, Any]:
    providers = payload.get("providers")
    if providers is None:
        return service.reset_provider_health(None)
    if not isinstance(providers, list):
        return _parameter_error(source_message('providers must be a list or null'))
    return service.reset_provider_health([str(item) for item in providers])


def _resolve_targets(raw: Any) -> list[str]:
    if raw in (None, "", []):
        return list(DEFAULT_SKILL_TARGET_IDS)
    if isinstance(raw, list):
        raw = ",".join(str(item) for item in raw)
    return parse_skill_targets(str(raw))


def skills_status(targets: Any = None) -> dict[str, Any]:
    try:
        target_ids = _resolve_targets(targets)
        return status_skill_targets(target_ids)
    except SkillInstallError as e:
        return _parameter_error(str(e), selected=[])


def skills_install(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        target_ids = _resolve_targets(payload.get("targets"))
    except SkillInstallError as e:
        return _parameter_error(str(e), selected=[])
    if not target_ids:
        return _parameter_error(source_message('no skill targets selected'), selected=[])
    try:
        return install_skill_targets(target_ids)
    except SkillInstallError as e:
        return {"ok": False, "error_type": "runtime_error", "error": str(e), "selected": target_ids}
