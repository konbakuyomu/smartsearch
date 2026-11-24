"""Persistent provider health so one dead channel stops failing on every run.

Optional providers (``web_search``, ``docs_search``, ``web_fetch``,
``vertical_search``) are additive: when one keeps failing, retrying it on every
invocation only costs latency and repeats the same error back to the caller.
Smart Search runs as a short-lived CLI process, so the in-memory main-search
breaker cannot remember anything between runs. This store keeps that memory on
disk next to ``config.json``.

Two failure classes are tracked separately:

* hard failures (``auth_error``/``config_error``) open the cooldown on the first
  occurrence and are never probed - a 401 does not heal on its own;
* soft failures (timeouts, 5xx, rate limits) need ``failure_threshold``
  consecutive failures, and stay probeable so a recovered provider comes back
  without user action.

Each record stores a fingerprint of the provider credentials. Re-keying a
provider changes the fingerprint and clears its cooldown, so fixing the config
is all a user has to do.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable

from .config import config
from .state_files import file_lock
from .provider_errors import retry_delay


STORE_FILENAME = "provider_health.json"
STORE_VERSION = 1
HARD_FAILURE_ERROR_TYPES = frozenset({"auth_error", "config_error"})
HARD_FAILURE_COOLDOWN_MULTIPLIER = 4.0
MAX_TRACKED_PROVIDERS = 64


def provider_fingerprint(*parts: str | None) -> str:
    """Return a short, non-reversible fingerprint of provider credentials."""
    digest = hashlib.sha256()
    for part in parts:
        digest.update((part or "").encode("utf-8", "replace"))
        digest.update(b"\x00")
    return digest.hexdigest()[:16]


class ProviderHealthStore:
    """File-backed cooldown memory shared by every Smart Search invocation."""

    def __init__(
        self,
        path: Path | str | None = None,
        *,
        cooldown_seconds: float | None = None,
        failure_threshold: int | None = None,
        clock: Callable[[], float] = time.time,
    ):
        self._path = Path(path) if path is not None else None
        self._cooldown_seconds = cooldown_seconds
        self._failure_threshold = failure_threshold
        self._clock = clock

    @property
    def path(self) -> Path:
        if self._path is not None:
            return self._path
        return config.config_file.parent / STORE_FILENAME

    @property
    def cooldown_seconds(self) -> float:
        if self._cooldown_seconds is not None:
            return max(0.0, float(self._cooldown_seconds))
        return config.provider_cooldown_seconds

    @property
    def failure_threshold(self) -> int:
        if self._failure_threshold is not None:
            return max(1, int(self._failure_threshold))
        return config.provider_failure_threshold

    @property
    def enabled(self) -> bool:
        return self.cooldown_seconds > 0

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (FileNotFoundError, PermissionError, OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("version") != STORE_VERSION:
            return {}
        providers = data.get("providers")
        if not isinstance(providers, dict):
            return {}
        return {
            str(provider): dict(record)
            for provider, record in providers.items()
            if isinstance(record, dict) and self._is_live(record)
        }

    def _is_live(self, record: dict[str, Any]) -> bool:
        """Records outlive their cooldown only while failures still count.

        Consecutive failures count inside one cooldown window, so two unrelated
        blips days apart never add up to a cooldown, and a provider that has
        served its cooldown starts the next window from zero.
        """
        now = self._clock()
        return (
            float(record.get("cooldown_until") or 0.0) > now
            or float(record.get("last_failure_at") or 0.0) + self.cooldown_seconds > now
        )

    def _save(self, providers: dict[str, dict[str, Any]]) -> None:
        """Persist health records; a read-only config dir must never fail a search."""
        path = self.path
        temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        payload = {"version": STORE_VERSION, "providers": providers}
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except (PermissionError, OSError):
            try:
                temp_path.unlink()
            except OSError:
                pass

    def _prune(self, providers: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Bound the stored record count; `_load` already drops stale records."""
        live = {provider: record for provider, record in providers.items() if self._is_live(record)}
        if len(live) <= MAX_TRACKED_PROVIDERS:
            return live
        ordered = sorted(live.items(), key=lambda item: float(item[1].get("cooldown_until") or 0.0), reverse=True)
        return dict(ordered[:MAX_TRACKED_PROVIDERS])

    def _status_from_record(self, provider: str, record: dict[str, Any] | None) -> dict[str, Any]:
        if not record:
            return {
                "provider": provider,
                "state": "closed",
                "consecutive_failures": 0,
                "error_type": "",
                "error": "",
                "cooldown_remaining_seconds": 0.0,
                "hard_failure": False,
            }
        remaining = float(record.get("cooldown_until") or 0.0) - self._clock()
        hard_failure = bool(record.get("hard_failure"))
        return {
            "provider": provider,
            "state": "cooldown" if remaining > 0 else "closed",
            "consecutive_failures": int(record.get("consecutive_failures") or 0),
            "error_type": str(record.get("error_type") or ""),
            "error": str(record.get("error") or ""),
            "cooldown_remaining_seconds": round(max(0.0, remaining), 3),
            "hard_failure": hard_failure,
        }

    def status(self, provider: str, fingerprint: str = "") -> dict[str, Any]:
        """Return the current cooldown state for one provider."""
        if not self.enabled:
            return self._status_from_record(provider, None)
        record = self._load().get(provider)
        if record and fingerprint and str(record.get("fingerprint") or "") != fingerprint:
            # Credentials changed: the previous failures describe a different setup.
            return self._status_from_record(provider, None)
        return self._status_from_record(provider, record)

    def should_skip(self, provider: str, fingerprint: str = "", *, allow_probe: bool = False) -> tuple[bool, dict[str, Any]]:
        """Return whether the call should be skipped, plus the cooldown state.

        ``allow_probe`` is set by callers that have no healthy alternative left.
        A soft failure is then retried once per cooldown window instead of being
        skipped outright; a hard failure still waits for a config change.
        """
        state = self.status(provider, fingerprint)
        if state["state"] != "cooldown":
            return False, state
        if allow_probe and not state["hard_failure"]:
            state = {**state, "probe": True}
            return False, state
        return True, state

    def record_success(self, provider: str, fingerprint: str = "") -> None:
        # A success clears the record whatever it was keyed to.
        try:
            with file_lock(self.path, timeout=1.0):
                del fingerprint
                if not self.enabled:
                    return
                providers = self._load()
                if provider not in providers:
                    return
                providers.pop(provider, None)
                self._save(self._prune(providers))
        except OSError:
            # Health persistence must not make the provider request fail.
            return

    def record_failure(
        self,
        provider: str,
        fingerprint: str = "",
        error_type: str = "",
        error: str = "",
    ) -> dict[str, Any]:
        """Count one failure and open the cooldown once the provider earns it."""
        try:
            with file_lock(self.path, timeout=1.0):
                if not self.enabled:
                    return self._status_from_record(provider, None)
                providers = self._load()
                record = providers.get(provider) or {}
                if fingerprint and str(record.get("fingerprint") or "") != fingerprint:
                    record = {}
                hard_failure = error_type in HARD_FAILURE_ERROR_TYPES
                failures = int(record.get("consecutive_failures") or 0) + 1
                now = self._clock()
                cooldown_until = float(record.get("cooldown_until") or 0.0)
                if hard_failure:
                    cooldown_until = now + self.cooldown_seconds * HARD_FAILURE_COOLDOWN_MULTIPLIER
                elif failures >= self.failure_threshold:
                    cooldown_until = now + self.cooldown_seconds
                if error_type == "rate_limited" and (delay := retry_delay(message=error)) is not None:
                    # A short TPM window is not a dead credential. Retain the
                    # failure and skip only until the upstream retry hint expires.
                    cooldown_until = now + delay
                updated = {
                    "fingerprint": fingerprint,
                    "consecutive_failures": failures,
                    "error_type": error_type,
                    "error": error,
                    # The latest classification wins: a provider that now times out
                    # instead of returning 401 is reachable again and worth probing.
                    "hard_failure": hard_failure,
                    "last_failure_at": now,
                    "cooldown_until": cooldown_until,
                }
                providers[provider] = updated
                self._save(self._prune(providers))
                return self._status_from_record(provider, updated)
        except OSError:
            # Health persistence must not make the provider request fail.
            return self._status_from_record(provider, None)

    def snapshot(self) -> list[dict[str, Any]]:
        """Return every tracked provider, longest cooldown first."""
        records = self._load()
        states = [self._status_from_record(provider, record) for provider, record in records.items()]
        return sorted(states, key=lambda state: state["cooldown_remaining_seconds"], reverse=True)

    def reset(self, providers: list[str] | None = None) -> list[str]:
        """Clear cooldowns; returns the providers that actually had one."""
        try:
            with file_lock(self.path, timeout=1.0):
                records = self._load()
                if providers is None:
                    cleared = sorted(records)
                    if cleared:
                        self._save({})
                    return cleared
                cleared = [provider for provider in providers if provider in records]
                if cleared:
                    for provider in cleared:
                        records.pop(provider, None)
                    self._save(self._prune(records))
                return cleared
        except OSError:
            # Health persistence must not make the provider request fail.
            return []


provider_health = ProviderHealthStore()
