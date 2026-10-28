from .i18n import source_message
import asyncio
import hashlib
import json
import math
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from . import jev_search
from .config import config
from . import activity
from .jev import JevClient, noul
from .intent_router import (
    CURRENT_INTENT_KEYWORDS as ROUTER_CURRENT_INTENT_KEYWORDS,
    DOCS_INTENT_KEYWORDS as ROUTER_DOCS_INTENT_KEYWORDS,
    FETCH_INTENT_KEYWORDS as ROUTER_FETCH_INTENT_KEYWORDS,
    VERTICAL_INTENT_KEYWORDS as ROUTER_VERTICAL_INTENT_KEYWORDS,
    build_rules_route,
    extract_urls as router_extract_urls,
    normalize_router_mode,
)


from .logger import log_info
from .providers.anysearch import AnySearchProvider
from .providers.context7 import Context7Provider
from .providers.deepseek import DeepSeekToolsProvider
from .providers.exa import ExaSearchProvider
from .providers.jina import JinaReaderProvider
from .providers.openai_compatible import (
    OpenAICompatibleSearchProvider,
    get_local_time_info,
    normalize_openai_compatible_api_url,
    openai_compatible_endpoint,
)
from .providers.sciverse import SciverseProvider
from .providers.tinyfish import TinyFishFetchProvider, TinyFishSearchProvider
from .providers.xai_responses import XAIResponsesSearchProvider
from .providers.zhipu import ZhipuWebSearchProvider
from .providers.zhipu_mcp import ZhipuMCPProvider
from .provider_errors import (
    APPROVED_PROVIDER_ERROR_TYPES,
    ProviderCallError,
    classify_provider_exception,
    provider_call_error,
    sanitize_provider_error_message,
)
from .provider_descriptions import PROVIDER_DESCRIPTIONS
from .provider_health import provider_fingerprint, provider_health
from .sciverse_schema import (
    SciverseParameterError,
    build_sciverse_meta_search_payload,
    normalize_sciverse_catalog_params,
    normalize_sciverse_relations_payload,
    normalize_sciverse_retrieval,
    normalize_sciverse_semantic_payload,
)
from .sources import merge_sources, model_answer_problem, new_session_id, split_answer_and_sources
from .utils import extract_unique_urls, search_prompt


_AVAILABLE_MODELS_CACHE: dict[tuple[str, str], list[str]] = {}
_AVAILABLE_MODELS_LOCK = asyncio.Lock()
SOURCE_PROVENANCE_WARNING = (
    source_message('extra_sources are retrieved in parallel and are not automatically used to verify generated content; use fetch on key URLs for claim-level evidence.')
)
MINIMUM_PROFILE_ERROR = (
    source_message('最低配置不满足：必须至少配置 main_search、docs_search、web_fetch 三类能力各一个 provider。')
)
OPENAI_COMPATIBLE_DIAGNOSE_COMMAND = "smart-search diagnose openai-compatible --format markdown"
DOCS_INTENT_KEYWORDS = ROUTER_DOCS_INTENT_KEYWORDS
ZH_CURRENT_KEYWORDS = ROUTER_CURRENT_INTENT_KEYWORDS
FETCH_INTENT_KEYWORDS = ROUTER_FETCH_INTENT_KEYWORDS
DEEP_ALLOWED_TOOLS = {
    "search",
    "exa-search",
    "exa-similar",
    "zhipu-search",
    "zhipu-mcp-search",
    "zhipu-mcp-reader",
    "zhipu-mcp-search-doc",
    "zhipu-mcp-repo-structure",
    "zhipu-mcp-read-file",
    "context7-library",
    "context7-docs",
    "fetch",
    "map",
}
DEEP_TRIGGER_KEYWORDS = {
    "深度搜索",
    "深度调研",
    "深入搜索",
    "deep search",
    "deep research",
    "核验",
    "验证",
    "交叉验证",
    "选型",
    "对比",
    "评测",
}
DEEP_HIGH_COMPLEXITY_KEYWORDS = {
    "对比",
    "选型",
    "核验",
    "验证",
    "为什么",
    "架构",
    "方案",
    "趋势",
    "优缺点",
    "风险",
    "区别",
    "怎么选",
    "compare",
    "comparison",
    "evaluate",
    "architecture",
    "tradeoff",
    "trade-off",
    "risk",
}
DEEP_RECENT_KEYWORDS = {
    "最近",
    "最新",
    "当前",
    "现在",
    "今天",
    "实时",
    "刚刚",
    "本周",
    "本月",
    "recent",
    "latest",
    "current",
    "today",
}
DEEP_CURRENT_KEYWORDS = {"今天", "实时", "刚刚", "当前", "现在", "today", "current", "live", "realtime"}
DEEP_CHINA_KEYWORDS = {"中国", "国内", "中文", "政策", "监管", "公告", "A股", "港股"}
DEEP_EXA_DISCOVERY_KEYWORDS = {
    "官方",
    "官网",
    "论文",
    "paper",
    "papers",
    "research paper",
    "产品页",
    "product page",
    "可信站点",
    "trusted",
    "known domain",
    "known domains",
    "site:",
    "白皮书",
    "standard",
    "standards",
}
RESEARCH_ROUTE_POLICY_VERSION = "research-router-v1"
RESEARCH_JS_HEAVY_KEYWORDS = {
    "js-heavy",
    "javascript",
    "dynamic",
    "动态页面",
    "浏览器渲染",
    "登录页",
    "cloudflare",
    "screenshot",
    "ocr",
    "扫描",
}
RESEARCH_PDF_KEYWORDS = {"pdf", "arxiv", "论文", "paper", ".pdf"}
RESEARCH_PROFILE_ORDER = {
    "main_search": ["xai-responses", "openai-compatible"],
    "web_search": ["zhipu", "zhipu-mcp", "tavily", "firecrawl", "tinyfish", "deepseek"],
    "docs_search": ["context7", "exa"],
    "web_fetch": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish", "deepseek"],
    "vertical_search": ["anysearch"],
    "site_map": ["tavily"],
    "synthesis": ["main-search"],
}
PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "xai-responses": {
        "capability": "main_search",
        "fallback_group": "main_search",
        "minimum_profile_role": "main_search",
        "quality_filters": ["source extraction required for high-risk claims"],
        "route_reasons": ["broad live answer", "primary synthesis"],
    },
    "openai-compatible": {
        "capability": "main_search",
        "fallback_group": "main_search",
        "minimum_profile_role": "main_search",
        "quality_filters": ["source extraction required for high-risk claims"],
        "route_reasons": ["relay-compatible primary synthesis"],
    },
    "context7": {
        "capability": "docs_search",
        "fallback_group": "docs_search",
        "minimum_profile_role": "docs_search",
        "quality_filters": ["library id required", "content required before citation"],
        "route_reasons": ["docs/API evidence", "framework reference"],
    },
    "exa": {
        "capability": "docs_search",
        "fallback_group": "docs_search",
        "minimum_profile_role": "docs_search",
        "quality_filters": ["URL required", "fetch before proof citation"],
        "route_reasons": ["official low-noise discovery", "paper/product discovery"],
    },
    "zhipu": {
        "capability": "web_search",
        "fallback_group": "web_search",
        "minimum_profile_role": "",
        "quality_filters": ["URL required", "fetch before proof citation"],
        "route_reasons": ["Chinese/current/policy discovery"],
    },
    "zhipu-mcp": {
        "capability": "web_search",
        "fallback_group": "web_search",
        "minimum_profile_role": "",
        "quality_filters": ["URL required", "fetch before proof citation"],
        "route_reasons": ["Coding Plan quota web discovery"],
    },
    "tavily": {
        "capability": "web_search",
        "capabilities": ["web_search", "web_fetch", "site_map"],
        "fallback_group": "web_search/web_fetch/site_map",
        "minimum_profile_role": "web_fetch",
        "quality_filters": ["non-empty normalized result", "non-empty extracted content"],
        "route_reasons": ["broad source discovery", "site map", "URL fetch"],
    },
    "jina": {
        "capability": "web_fetch",
        "fallback_group": "web_fetch",
        "minimum_profile_role": "web_fetch_with_key",
        "quality_filters": ["non-empty markdown", "challenge page rejection", "ReaderLM-v2 requires key"],
        "route_reasons": ["known URL extraction", "PDF/arXiv extraction"],
    },
    "zhipu-mcp-reader": {
        "capability": "web_fetch",
        "fallback_group": "web_fetch",
        "minimum_profile_role": "",
        "quality_filters": ["non-empty reader content"],
        "route_reasons": ["Coding Plan quota page read"],
    },
    "firecrawl": {
        "capability": "web_fetch",
        "capabilities": ["web_search", "web_fetch"],
        "fallback_group": "web_search/web_fetch",
        "minimum_profile_role": "web_fetch",
        "quality_filters": ["non-empty normalized result", "non-empty extracted content"],
        "route_reasons": ["JS-heavy fetch", "dynamic/browser-like extraction", "robust fetch fallback"],
    },
    "tinyfish": {
        "capability": "web_search",
        "capabilities": ["web_search", "web_fetch"],
        "fallback_group": "web_search/web_fetch",
        "minimum_profile_role": "",
        "quality_filters": ["non-empty normalized result", "non-empty extracted content", "challenge page rejection"],
        "route_reasons": ["broad source discovery", "known URL extraction"],
    },
    "deepseek": {
        "capability": "web_search",
        "capabilities": ["web_search", "web_fetch"],
        "fallback_group": "web_search/web_fetch",
        "minimum_profile_role": "",
        "quality_filters": ["non-empty normalized result", "non-empty extracted content"],
        "route_reasons": ["broad source discovery", "Chinese/current discovery", "known URL extraction"],
    },
    "anysearch": {
        "capability": "vertical_search",
        "fallback_group": "vertical_search",
        "minimum_profile_role": "",
        "quality_filters": ["vertical intent required", "URL required before evidence citation"],
        "route_reasons": ["vertical domain discovery"],
        "experimental": True,
    },
    "sciverse": {
        "capability": "vertical_search",
        "fallback_group": "vertical_search",
        "minimum_profile_role": "",
        "quality_filters": ["explicit command required", "unique_id required for relations", "doc_id required for content"],
        "route_reasons": ["explicit academic vertical search"],
        "experimental": True,
        "explicit_only": True,
        "route_enabled": False,
    },
    "main-search": {
        "capability": "synthesis",
        "fallback_group": "synthesis",
        "minimum_profile_role": "",
        "quality_filters": ["fetched evidence only", "no provider calls during synthesis"],
        "route_reasons": ["evidence-only synthesis"],
    },
}
MAIN_SEARCH_FALLBACK_CHAIN = ["xai-responses", "openai-compatible"]
MAIN_SEARCH_PROVIDER_ALIASES = {
    "xai-responses": {"xai-responses", "xai", "grok", "grok-web-tools"},
    "openai-compatible": {"openai-compatible", "openai", "chat-completions", "primary"},
}
MODEL_BREAKER_FAILURE_THRESHOLD = 2
MODEL_BREAKER_COOLDOWN_SECONDS = 600.0
_OPENAI_COMPATIBLE_MODEL_BREAKERS: dict[tuple[str, str, str], dict[str, Any]] = {}


# asyncio may fire a timer up to one clock tick early (15.6 ms for Windows
# time.monotonic() before Python 3.13), so a sub-tick remainder counts as spent.
_CLOCK_RESOLUTION = time.get_clock_info("monotonic").resolution


class SearchBudget:
    """Internal monotonic deadline shared by one fast-search execution."""

    def __init__(self, total_seconds: float, started_at: float | None = None):
        if not math.isfinite(total_seconds) or total_seconds <= 0:
            raise ValueError(source_message('Search timeout must be a positive finite number.'))
        self.total_seconds = float(total_seconds)
        self.started_at = time.monotonic() if started_at is None else float(started_at)
        self.deadline = self.started_at + self.total_seconds

    def elapsed_seconds(self) -> float:
        return max(0.0, time.monotonic() - self.started_at)

    def remaining_seconds(self) -> float:
        remaining = self.deadline - time.monotonic()
        return remaining if remaining > _CLOCK_RESOLUTION else 0.0


class SearchExecutionState:
    """Collect additive scheduler telemetry without changing provider attempts."""

    def __init__(self, budget: SearchBudget):
        self.budget = budget
        self.phase_attempts: list[dict[str, Any]] = []
        self._timed_out_phases: list[str] = []

    def record(
        self,
        phase: str,
        status: str,
        started_at: float,
        budget_seconds: float,
        reason: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempt: dict[str, Any] = {
            "phase": phase,
            "status": status,
            "budget_ms": round(max(0.0, budget_seconds) * 1000, 2),
            "elapsed_ms": round(max(0.0, time.monotonic() - started_at) * 1000, 2),
            "remaining_ms": round(self.budget.remaining_seconds() * 1000, 2),
        }
        if reason:
            attempt["reason"] = reason
        if details:
            attempt.update(details)
        self.phase_attempts.append(attempt)
        activity.progress(f"{phase}:{status}")
        if status == "timeout" and phase not in self._timed_out_phases:
            self._timed_out_phases.append(phase)
        return attempt

    @property
    def timeout_phase(self) -> str:
        return self._timed_out_phases[0] if self._timed_out_phases else ""

    @property
    def timed_out_phases(self) -> list[str]:
        return list(self._timed_out_phases)

    def telemetry(self, *, partial_success: bool = False) -> dict[str, Any]:
        timed_out_phases = self.timed_out_phases
        return {
            "timeout_seconds": self.budget.total_seconds,
            "timeout_phase": self.timeout_phase,
            "timed_out_phases": timed_out_phases,
            "phase_attempts": list(self.phase_attempts),
            "deadline_elapsed_ms": round(self.budget.elapsed_seconds() * 1000, 2),
            "deadline_remaining_ms": round(self.budget.remaining_seconds() * 1000, 2),
            "partial_success": partial_success,
            "timeout_warning": (
                "Search deadline reached during: " + ", ".join(timed_out_phases)
                if timed_out_phases
                else ""
            ),
        }


def _resolve_search_timeout(timeout_seconds: float | None) -> float:
    if timeout_seconds is None:
        return config.search_timeout
    try:
        value = float(timeout_seconds)
    except (TypeError, ValueError):
        raise ValueError(source_message('Invalid --timeout: {0}. Expected a positive finite number.', timeout_seconds))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(source_message('Invalid --timeout: {0}. Expected a positive finite number.', timeout_seconds))
    return value


def _elapsed_ms(start: float) -> float:
    return round((time.time() - start) * 1000, 2)


def _normalize_domain_filter(value: str | list[str] | tuple[str, ...] | None) -> list[str] | None:
    if not value:
        return None

    raw_parts = [value] if isinstance(value, str) else [str(item) for item in value if item]
    domains: list[str] = []
    for part in raw_parts:
        domains.extend(item.strip() for item in re.split(r"[\s,]+", part) if item.strip())
    return domains or None


def _empty_search_result(
    start: float,
    session_id: str,
    query: str,
    error_type: str,
    error: str,
    primary_api_mode: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "error_type": error_type,
        "error": error,
        "session_id": session_id,
        "query": query,
        "primary_api_mode": primary_api_mode,
        "content": "",
        "sources": [],
        "sources_count": 0,
        "primary_sources": [],
        "primary_sources_count": 0,
        "extra_sources": [],
        "extra_sources_count": 0,
        "source_warning": "",
        "routing_decision": {},
        "providers_used": [],
        "provider_attempts": [],
        "provider_notices": [],
        "fallback_used": False,
        "validation_level": "",
        "timeout_seconds": None,
        "timeout_phase": "",
        "timed_out_phases": [],
        "phase_attempts": [],
        "deadline_elapsed_ms": 0.0,
        "deadline_remaining_ms": None,
        "partial_success": False,
        "timeout_warning": "",
        "elapsed_ms": _elapsed_ms(start),
    }
    if extra:
        data.update(extra)
    return data


def _attempt(
    capability: str,
    provider: str,
    status: str,
    start: float,
    result_count: int = 0,
    error_type: str = "",
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    activity.progress(f"{capability}:{status}", provider, (extra or {}).get("model", ""), error_type)
    data = {
        "capability": capability,
        "provider": provider,
        "status": status,
        "error_type": error_type,
        "error": error,
        "elapsed_ms": _elapsed_ms(start),
        "result_count": result_count,
    }
    if extra:
        data.update(extra)
    return data


def _attempt_from_exception(capability: str, provider: str, start: float, exc: BaseException) -> dict[str, Any]:
    error_type, error = classify_provider_exception(exc)
    return _attempt(capability, provider, "error", start, error_type=error_type, error=error)


def _attempt_with_health(capability: str, provider: str, start: float, exc: BaseException) -> dict[str, Any]:
    """Record a raised optional-provider failure in persisted health, then report it."""
    error_type, error = classify_provider_exception(exc)
    health_extra = _record_provider_result(provider, "error", error_type, error)
    return _attempt(capability, provider, "error", start, error_type=error_type, error=error, extra=health_extra)


def _attempt_status_for_result(data: dict[str, Any]) -> str:
    return "error" if data.get("error_type") else "empty"


def _tavily_is_enabled() -> bool:
    return bool(config.tavily_enabled and config.tavily_api_key)


def _tavily_disabled_message() -> str:
    return source_message('Tavily is disabled by TAVILY_ENABLED=false. No Tavily network request was made.')


def _provider_disabled_result(provider: str) -> dict[str, Any] | None:
    if config.provider_enabled(provider):
        return None
    message = _tavily_disabled_message() if provider == "tavily" else source_message(
        'Provider {0} is disabled by {1}=false. No network request was made.',
        provider, config.provider_enabled_key(provider),
    )
    return {"ok": False, "provider": provider, "disabled": True, "status": "disabled",
            "error_type": "config_error", "error": message, "message": message}


PROVIDER_CREDENTIAL_SOURCES: dict[str, Any] = {
    "xai-responses": lambda: (config.xai_api_key, config.xai_api_url),
    "openai-compatible": lambda: (config.openai_compatible_api_key, config.openai_compatible_api_url),
    "zhipu": lambda: (config.zhipu_api_key, config.zhipu_api_url),
    "zhipu-mcp": lambda: (config.zhipu_mcp_api_key, config.zhipu_mcp_search_api_url),
    "zhipu-mcp-reader": lambda: (config.zhipu_mcp_api_key, config.zhipu_mcp_reader_api_url),
    "tavily": lambda: (config.tavily_api_key, config.tavily_api_url),
    "firecrawl": lambda: (config.firecrawl_api_key, config.firecrawl_api_url),
    "tinyfish": lambda: (config.tinyfish_api_key, config.tinyfish_search_api_url, config.tinyfish_fetch_api_url),
    "deepseek": lambda: (config.deepseek_api_key, config.deepseek_api_url),
    "exa": lambda: (config.exa_api_key, config.exa_base_url),
    "context7": lambda: (config.context7_api_key, config.context7_base_url),
    "jina": lambda: (config.jina_api_key, config.jina_reader_api_url),
    "anysearch": lambda: (config.anysearch_api_key, config.anysearch_api_url),
    "sciverse": lambda: (config.sciverse_api_token, config.sciverse_api_url),
}
PROVIDER_COOLDOWN_HINT = (
    source_message('Run `smart-search providers status` for detail. Fixing the credential or `smart-search providers reset PROVIDER` retries it immediately.')
)


def _provider_fingerprint(provider: str) -> str:
    """Fingerprint a provider's credentials so re-keying clears its cooldown."""
    source = PROVIDER_CREDENTIAL_SOURCES.get(provider)
    if source is None:
        return ""
    return provider_fingerprint(*source())


def _provider_health_status(provider: str) -> dict[str, Any]:
    return provider_health.status(provider, _provider_fingerprint(provider))


def _cooldown_attempt_extra(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider_health": {
            "state": state.get("state", "closed"),
            "consecutive_failures": state.get("consecutive_failures", 0),
            "cooldown_remaining_seconds": state.get("cooldown_remaining_seconds", 0.0),
            "hard_failure": bool(state.get("hard_failure")),
            "probe": bool(state.get("probe")),
        }
    }


def _plan_provider_health(capability: str, providers: list[str]) -> tuple[list[str], list[dict]]:
    """Split a capability chain into providers worth calling and cooled-down skips.

    A provider that keeps failing is skipped instead of being retried on every
    run. When the whole chain is cooling, one soft failure is still probed so a
    recovered provider returns on its own; a hard failure (bad key, bad config)
    waits for a credential change or an explicit reset.
    """
    if not providers or not provider_health.enabled:
        return providers, []

    states = {provider: _provider_health_status(provider) for provider in providers}
    runnable = [provider for provider in providers if states[provider]["state"] != "cooldown"]
    if not runnable:
        probe = next((provider for provider in providers if not states[provider]["hard_failure"]), "")
        if probe:
            states[probe] = {**states[probe], "probe": True}
            runnable = [probe]

    skipped = []
    for provider in providers:
        if provider in runnable:
            continue
        state = states[provider]
        skipped.append(
            _attempt(
                capability,
                provider,
                "skipped",
                time.time(),
                error_type=state.get("error_type", ""),
                error=state.get("error", "") or "provider is on failure cooldown",
                extra=_cooldown_attempt_extra(state),
            )
        )
    return runnable, skipped


def _record_provider_result(
    provider: str,
    status: str,
    error_type: str = "",
    error: str = "",
) -> dict[str, Any]:
    """Update persisted health for one optional-provider call.

    ``empty`` is not a failure: a provider that answers with no results is
    working, it just had nothing to say about this query.
    """
    fingerprint = _provider_fingerprint(provider)
    if status == "ok":
        provider_health.record_success(provider, fingerprint)
        return {}
    if status != "error" and not error_type:
        return {}
    state = provider_health.record_failure(provider, fingerprint, error_type, error)
    return _cooldown_attempt_extra(state) if state.get("state") == "cooldown" else {}


def _provider_notices(attempts: list[dict]) -> list[dict[str, Any]]:
    """Collapse optional-provider failures into one deduplicated notice each."""
    notices: dict[str, dict[str, Any]] = {}
    for attempt in attempts:
        provider = str(attempt.get("provider") or "")
        status = attempt.get("status")
        capability = str(attempt.get("capability") or "")
        if not provider or capability == "main_search" or status not in {"error", "skipped"}:
            continue
        health = attempt.get("provider_health") or {}
        cooling = health.get("state") == "cooldown"
        notice = {
            "provider": provider,
            "capability": capability,
            "status": "cooldown" if cooling else "failed",
            "error_type": str(attempt.get("error_type") or ""),
            "error": str(attempt.get("error") or ""),
            "cooldown_remaining_seconds": float(health.get("cooldown_remaining_seconds") or 0.0),
            "hint": PROVIDER_COOLDOWN_HINT if cooling else "",
        }
        previous = notices.get(provider)
        if previous is None or (notice["status"] == "cooldown" and previous["status"] != "cooldown"):
            notices[provider] = notice
    return list(notices.values())


def reset_provider_health(providers: list[str] | None = None) -> dict[str, Any]:
    """Clear persisted provider cooldowns so the next run retries them."""
    known = sorted(PROVIDER_CREDENTIAL_SOURCES)
    if providers:
        unknown = [provider for provider in providers if provider not in known]
        if unknown:
            return {
                "ok": False,
                "error_type": "parameter_error",
                "error": source_message('Unknown provider: {0}. Known providers: {1}', ", ".join(unknown), ", ".join(known)),
                "known_providers": known,
                "cleared": [],
            }
    cleared = provider_health.reset(providers)
    return {"ok": True, "error_type": "", "error": "", "cleared": cleared, "known_providers": known}


def provider_health_status() -> dict[str, Any]:
    """Report the persisted cooldown state for every optional provider."""
    configured = [provider for provider in sorted(PROVIDER_CREDENTIAL_SOURCES) if _provider_configured(provider)]
    tracked = {state["provider"]: state for state in provider_health.snapshot()}
    providers = []
    for provider in configured:
        state = tracked.pop(provider, None) or _provider_health_status(provider)
        providers.append({**state, "configured": True})
    for provider, state in tracked.items():
        providers.append({**state, "configured": False})
    cooling = [state["provider"] for state in providers if state["state"] == "cooldown"]
    return {
        "ok": True,
        "enabled": provider_health.enabled,
        "cooldown_seconds": provider_health.cooldown_seconds,
        "failure_threshold": provider_health.failure_threshold,
        "store_path": str(provider_health.path),
        "providers": providers,
        "cooldown_providers": cooling,
    }


def _openai_model_breaker_key(api_url: str, model: str, api_mode: str = "chat-completions") -> tuple[str, str, str]:
    return (normalize_openai_compatible_api_url(api_url), model, api_mode)


def reset_runtime_breakers() -> None:
    _OPENAI_COMPATIBLE_MODEL_BREAKERS.clear()


def _openai_model_breaker_state(api_url: str, model: str, api_mode: str = "chat-completions") -> dict[str, Any]:
    key = _openai_model_breaker_key(api_url, model, api_mode)
    state = _OPENAI_COMPATIBLE_MODEL_BREAKERS.get(key, {})
    opened_until = float(state.get("opened_until") or 0.0)
    now = time.monotonic()
    if opened_until and opened_until > now:
        return {
            "state": "open",
            "opened_until_seconds": round(opened_until - now, 3),
            "consecutive_failures": int(state.get("consecutive_failures") or 0),
        }
    if opened_until and opened_until <= now:
        _OPENAI_COMPATIBLE_MODEL_BREAKERS.pop(key, None)
        state = {}
    return {"state": "closed", "consecutive_failures": int(state.get("consecutive_failures") or 0)}


def _record_openai_model_success(api_url: str, model: str, api_mode: str = "chat-completions") -> None:
    _OPENAI_COMPATIBLE_MODEL_BREAKERS.pop(_openai_model_breaker_key(api_url, model, api_mode), None)


def _record_openai_model_failure(api_url: str, model: str, api_mode: str = "chat-completions") -> dict[str, Any]:
    key = _openai_model_breaker_key(api_url, model, api_mode)
    state = _OPENAI_COMPATIBLE_MODEL_BREAKERS.setdefault(key, {"consecutive_failures": 0, "opened_until": 0.0})
    state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
    if state["consecutive_failures"] >= MODEL_BREAKER_FAILURE_THRESHOLD:
        state["opened_until"] = time.monotonic() + MODEL_BREAKER_COOLDOWN_SECONDS
    return _openai_model_breaker_state(api_url, model, api_mode)


def _openai_model_candidates(provider_config: dict[str, Any], *, fallback_mode: str, model_override: str) -> list[dict[str, Any]]:
    primary_model = provider_config["model"]
    candidates = [
        {
            **provider_config,
            "model": primary_model,
            "model_role": "primary",
            "fallback_from_model": "",
            "stream": provider_config.get("stream", False),
        }
    ]
    if fallback_mode == "off" or model_override:
        return candidates
    for fallback_model in provider_config.get("fallback_models") or []:
        candidates.append(
            {
                **provider_config,
                "model": fallback_model,
                "model_role": "fallback",
                "fallback_from_model": primary_model,
                "stream": False,
            }
        )
    return candidates


def _remaining_budget_seconds(start: float, timeout_seconds: float | None) -> float | None:
    if timeout_seconds is None:
        return None
    return max(0.0, float(timeout_seconds) - (time.monotonic() - start))


OPENAI_COMPATIBLE_TIMEOUT_POLICY = "remaining_budget"


def _attempt_timeout_seconds(
    search_start: float,
    timeout_seconds: float | None,
    remaining_candidates: int | None = None,
) -> float | None:
    """Return the remaining search budget for the current candidate.

    Model fallback is fail-over, not a time slice. Extra candidates must not
    shrink the active model's timeout. ``remaining_candidates`` is accepted for
    call-site compatibility and ignored.
    """
    del remaining_candidates
    remaining_budget = _remaining_budget_seconds(search_start, timeout_seconds)
    if remaining_budget is None:
        return None
    return max(0.001, remaining_budget)


def _openai_fallback_model_inventory(
    fallback_models: list[str],
    available_models: list[str] | None = None,
    *,
    primary_model: str = "",
) -> dict[str, Any]:
    available = [model for model in (available_models or []) if isinstance(model, str) and model]
    configured = [model for model in fallback_models if isinstance(model, str) and model]
    if not configured:
        return {
            "status": "not_configured",
            "message": source_message('未配置 OpenAI-compatible 兜底模型'),
            "fallback_models": [],
            "available_models": available,
            "unknown_fallback_models": [],
            "known_fallback_models": [],
            "timeout_policy": OPENAI_COMPATIBLE_TIMEOUT_POLICY,
            "timeout_policy_message": source_message('主模型使用剩余共享 main-search 预算；只有硬失败后才接力兜底模型'),
            "primary_model": primary_model,
        }
    if not available:
        return {
            "status": "skipped",
            "message": source_message('无法对照 /models 清单，已跳过兜底模型检查'),
            "fallback_models": configured,
            "available_models": [],
            "unknown_fallback_models": [],
            "known_fallback_models": configured,
            "timeout_policy": OPENAI_COMPATIBLE_TIMEOUT_POLICY,
            "timeout_policy_message": source_message('主模型使用剩余共享 main-search 预算；只有硬失败后才接力兜底模型'),
            "primary_model": primary_model,
        }

    unknown = [model for model in configured if model not in available]
    known = [model for model in configured if model in available]
    if unknown:
        status = "warning"
        message = source_message('这些兜底模型不在上游 /models 列表中: {0}', ", ".join(unknown))
    else:
        status = "ok"
        message = source_message('已配置的兜底模型都在上游 /models 列表中')
    return {
        "status": status,
        "message": message,
        "fallback_models": configured,
        "available_models": available,
        "unknown_fallback_models": unknown,
        "known_fallback_models": known,
        "timeout_policy": OPENAI_COMPATIBLE_TIMEOUT_POLICY,
        "timeout_policy_message": source_message('主模型使用剩余共享 main-search 预算；只有硬失败后才接力兜底模型'),
        "primary_model": primary_model,
    }


def _append_openai_transport_attempts(
    provider_attempts: list[dict],
    search_provider: Any,
    candidate_config: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> bool:
    transport_attempts = getattr(search_provider, "last_transport_attempts", [])
    if candidate_config.get("provider") != "openai-compatible" or not transport_attempts:
        return False
    for transport_attempt in transport_attempts:
        transport_extra = {
            key: value
            for key, value in transport_attempt.items()
            if key not in {"status", "error_type", "error", "elapsed_ms", "result_count"}
        }
        if extra:
            transport_extra.update(extra)
        if candidate_config.get("fallback_from_model"):
            transport_extra["fallback_from_model"] = candidate_config["fallback_from_model"]
        provider_attempts.append(
            {
                **_attempt(
                    "main_search",
                    search_provider.get_provider_name(),
                    transport_attempt.get("status", "error"),
                    time.time(),
                    result_count=int(transport_attempt.get("result_count") or 0),
                    error_type=transport_attempt.get("error_type", ""),
                    error=transport_attempt.get("error", ""),
                ),
                "elapsed_ms": transport_attempt.get("elapsed_ms", 0),
                **transport_extra,
            }
        )
    return True


def _normalize_source_results(results: list[dict] | None, provider: str) -> list[dict]:
    normalized: list[dict] = []
    for item in results or []:
        url = (item.get("url") or item.get("link") or "").strip()
        if not url:
            continue
        out = {"url": url, "provider": item.get("provider") or provider}
        title = (item.get("title") or "").strip()
        if title:
            out["title"] = title
        desc = (item.get("description") or item.get("content") or item.get("snippet") or "").strip()
        if desc:
            out["description"] = desc
        published = item.get("published_date") or item.get("publishedDate") or item.get("publish_date")
        if published:
            out["published_date"] = published
        source = item.get("source") or item.get("media")
        if source:
            out["source"] = source
        normalized.append(out)
    return normalized


def _provider_names_from_attempts(attempts: list[dict]) -> list[str]:
    names: list[str] = []
    for attempt in attempts:
        provider = attempt.get("provider")
        if attempt.get("status") == "ok" and provider and provider not in names:
            names.append(provider)
    return names


def _fallback_used(attempts: list[dict]) -> bool:
    by_capability: dict[str, list[dict]] = {}
    for attempt in attempts:
        capability = attempt.get("capability", "")
        if attempt.get("status") in {"ok", "empty", "error", "skipped"}:
            by_capability.setdefault(capability, []).append(attempt)
    for capability_attempts in by_capability.values():
        previous_failed = False
        previous_identity = ""
        for attempt in capability_attempts:
            provider = attempt.get("provider", "")
            model = str(attempt.get("model") or "")
            identity = f"{provider}:{model}" if provider == "OpenAI-compatible" and model else provider
            status = attempt.get("status")
            if previous_identity and identity and identity != previous_identity:
                return True
            if previous_failed and identity != previous_identity:
                return True
            previous_failed = status in {"empty", "error", "skipped"}
            previous_identity = identity or previous_identity
    return False


def provider_profiles() -> dict[str, dict[str, Any]]:
    return {
        provider: {
            **profile,
            "descriptions": PROVIDER_DESCRIPTIONS[provider],
            "enabled": config.provider_enabled(provider),
            "enabled_key": config.provider_enabled_key(provider),
        }
        for provider, profile in PROVIDER_PROFILES.items()
    }


def intent_router_status() -> dict[str, Any]:
    try:
        mode = config.intent_router_mode
        settings = config.jev_settings()
        configured = bool(settings.api_key)
        return {
            "mode": mode, "ok": True, "configured": configured,
            "effective_engine": "jev" if mode == "jev" and configured else "rules",
            "model": settings.model, "timeout_seconds": settings.timeout,
            "max_rounds": settings.max_rounds, "max_channels": settings.max_channels,
            "filter_results": settings.filter_results, "synthesize": settings.synthesis_mode,
            "degrades_to_rules": True, "error": "", "ordinary_search_rounds": 1,
            "legacy_remote_routing": "retired",
        }
    except ValueError as exc:
        return {"mode": "", "ok": False, "error": str(exc)}


def _provider_supports_capability(provider: str, capability: str) -> bool:
    profile = PROVIDER_PROFILES.get(provider, {})
    capabilities = set(profile.get("capabilities") or [profile.get("capability", "")])
    return capability in capabilities


def _provider_configured(provider: str) -> bool:
    if not config.provider_enabled(provider):
        return False
    if provider == "xai-responses":
        return bool(config.xai_api_key)
    if provider == "openai-compatible":
        return bool(config.openai_compatible_api_url and config.openai_compatible_api_key)
    if provider == "context7":
        return bool(config.context7_api_key)
    if provider == "exa":
        return bool(config.exa_api_key)
    if provider == "zhipu":
        return bool(config.zhipu_api_key)
    if provider == "zhipu-mcp":
        return bool(config.zhipu_mcp_api_key)
    if provider == "tavily":
        return _tavily_is_enabled()
    if provider == "jina":
        return bool(config.jina_api_key)
    if provider == "zhipu-mcp-reader":
        return bool(config.zhipu_mcp_api_key)
    if provider == "firecrawl":
        return bool(config.firecrawl_api_key)
    if provider == "tinyfish":
        return bool(config.tinyfish_api_key)
    if provider == "deepseek":
        return bool(config.deepseek_api_key)
    if provider == "anysearch":
        return bool(config.anysearch_api_key)
    if provider == "sciverse":
        return bool(config.sciverse_api_token)
    if provider == "main-search":
        return any(_provider_configured(item) for item in MAIN_SEARCH_FALLBACK_CHAIN)
    return False


def _configured_for_capability(capability: str, capability_status: dict[str, Any] | None = None) -> list[str]:
    if capability_status is not None:
        configured = set(capability_status.get(capability, {}).get("configured") or [])
        return [
            provider
            for provider in RESEARCH_PROFILE_ORDER.get(capability, [])
            if provider in configured and config.provider_enabled(provider) and _provider_supports_capability(provider, capability)
        ]
    return [provider for provider in RESEARCH_PROFILE_ORDER.get(capability, []) if _provider_configured(provider)]


def _safe_provider_overrides() -> tuple[list[str], list[str], list[str]]:
    search_providers = set(PROVIDER_PROFILES)
    allowed_disabled_providers = search_providers | {"jev-synthesis"}
    preferred = [provider for provider in config.research_preferred_providers if provider in search_providers]
    disabled = [provider for provider in config.research_disabled_providers if provider in allowed_disabled_providers]
    invalid = [provider for provider in config.research_preferred_providers if provider not in search_providers]
    invalid.extend(provider for provider in config.research_disabled_providers if provider not in allowed_disabled_providers)
    return preferred, disabled, invalid


def _apply_research_overrides(capability: str, providers: list[str]) -> list[str]:
    preferred, disabled, _ = _safe_provider_overrides()
    allowed = [
        provider
        for provider in providers
        if provider not in disabled and config.provider_enabled(provider) and _provider_supports_capability(provider, capability)
    ]
    ordered = [
        provider
        for provider in preferred
        if provider in allowed and _provider_supports_capability(provider, capability)
    ]
    ordered.extend(provider for provider in allowed if provider not in ordered)
    return ordered


def _research_fetch_order(query: str, url: str = "", capability_status: dict[str, Any] | None = None) -> list[str]:
    providers = _configured_for_capability("web_fetch", capability_status)
    target = f"{query} {url}".lower()
    if _contains_any(target, RESEARCH_JS_HEAVY_KEYWORDS):
        preferred = ["firecrawl", "tavily", "jina", "zhipu-mcp-reader"]
    elif _contains_any(target, RESEARCH_PDF_KEYWORDS) or url.lower().endswith(".pdf"):
        preferred = ["jina", "tavily", "zhipu-mcp-reader", "firecrawl"]
    elif url or _extract_urls(query):
        preferred = ["jina", "tavily", "zhipu-mcp-reader", "firecrawl"]
    else:
        preferred = providers
    ordered = [provider for provider in preferred if provider in providers]
    ordered.extend(provider for provider in providers if provider not in ordered)
    return _apply_research_overrides("web_fetch", ordered)


def _research_evidence_item(
    *,
    url: str,
    provider: str,
    title: str = "",
    content: str = "",
    source_type: str = "fetched_page",
    subquestion_id: str = "",
) -> dict[str, Any]:
    digest = hashlib.sha1(f"{url}\n{provider}\n{title}".encode("utf-8")).hexdigest()[:12]
    return {
        "id": f"e{digest}",
        "url": url,
        "title": title or url,
        "provider": provider,
        "source_type": source_type,
        "subquestion_id": subquestion_id,
        "content": content,
        "content_len": len(content or ""),
        "verified": bool(content and content.strip()),
    }


def _citation_items(evidence_items: list[dict[str, Any]]) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in evidence_items:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        citations.append({
            "url": url,
            "title": item.get("title") or url,
            "provider": item.get("provider") or "",
        })
    return citations


def _evidence_only_synthesis(question: str, evidence_items: list[dict[str, Any]], gaps: list[dict[str, Any]]) -> str:
    if not evidence_items:
        return (
            f"未能为 `{question}` 获取可引用的页面正文证据。"
            "本次 research 已停止在降级状态，未对缺证据的结论做断言。"
        )
    lines = [f"Research result for: {question}", ""]
    lines.append("Evidence-backed findings:")
    for index, item in enumerate(evidence_items, 1):
        content = re.sub(r"\s+", " ", (item.get("content") or "").strip())
        excerpt = content[:360]
        lines.append(f"{index}. {item.get('title') or item.get('url')} ({item.get('provider')})")
        if excerpt:
            lines.append(f"   Evidence excerpt: {excerpt}")
        lines.append(f"   Source: {item.get('url')}")
    if gaps:
        lines.extend(["", "Unverified gaps:"])
        for gap in gaps:
            lines.append(f"- {gap.get('subquestion_id', '')}: {gap.get('reason', '')}")
    return "\n".join(lines).strip()


def _write_research_artifact(evidence_root: str, name: str, data: Any) -> None:
    root = Path(evidence_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_docs_intent(query: str) -> bool:
    return build_rules_route(query, mode="rules").docs_intent


def _is_zh_current_intent(query: str) -> bool:
    return build_rules_route(query, mode="rules").zh_current_intent


def _is_web_current_intent(query: str) -> bool:
    return build_rules_route(query, mode="rules").web_current_intent


def _contains_any(query: str, keywords: set[str]) -> bool:
    q = query.lower()
    return any(keyword.lower() in q for keyword in keywords)


def _extract_urls(query: str) -> list[str]:
    return router_extract_urls(query)


def _slugify_query(query: str) -> str:
    slug = re.sub(r"https?://", "", query.lower())
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug, flags=re.IGNORECASE)
    slug = slug.strip("-")
    return slug[:48] or "deep-research"


def _default_evidence_dir(query: str) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M")
    return str(Path(tempfile.gettempdir()) / "smart-search-evidence" / f"{timestamp}-{_slugify_query(query)}")


def _quote_arg(value: str) -> str:
    escaped = value.replace("`", "``").replace("$", "`$").replace('"', '`"')
    return f'"{escaped}"'


def _path_join(base: str, filename: str) -> str:
    return str(Path(base) / filename)


def _deep_step(
    step_id: str,
    subquestion_id: str,
    tool: str,
    purpose: str,
    command: str,
    output_path: str,
) -> dict[str, str]:
    return {
        "id": step_id,
        "subquestion_id": subquestion_id,
        "tool": tool,
        "purpose": purpose,
        "command": command,
        "output_path": output_path,
    }


def _deep_capability(capability: str, tools: list[str], reason: str) -> dict[str, Any]:
    return {"capability": capability, "tools": tools, "reason": reason}


def _deep_subquestion(sub_id: str, question: str, reason: str, required_capabilities: list[str]) -> dict[str, Any]:
    return {
        "id": sub_id,
        "question": question,
        "reason": reason,
        "required_capabilities": required_capabilities,
    }


def _deep_budget(value: str) -> str:
    budget = (value or "standard").strip().lower()
    return budget if budget in {"quick", "standard", "deep"} else "standard"


def _is_deep_complex(query: str, budget: str) -> bool:
    q = re.sub(r"https?://[^\s<>\]\)\"']+", "", query)
    object_separators = len(re.findall(r"[/、,，]| 和 | 与 | vs | VS | versus ", q))
    return budget == "deep" or _contains_any(query, DEEP_HIGH_COMPLEXITY_KEYWORDS) or object_separators >= 2


def build_deep_research_plan(query: str, budget: str = "standard", evidence_dir: str = "") -> dict[str, Any]:
    start = time.time()
    question = query.strip()
    budget = _deep_budget(budget)
    evidence_root = evidence_dir.strip() or _default_evidence_dir(question)
    urls = _extract_urls(question)
    known_url = bool(urls)
    route = build_rules_route(question, mode="rules")
    docs_intent = route.docs_intent
    zh_current_intent = route.zh_current_intent
    recency_requirement = "none"
    if _contains_any(question, DEEP_CURRENT_KEYWORDS) or zh_current_intent:
        recency_requirement = "current"
    elif _contains_any(question, {"行情", "价格", "走势", "币圈", "股票", "市场"}) and _contains_any(question, DEEP_RECENT_KEYWORDS):
        recency_requirement = "current"
    elif _contains_any(question, DEEP_RECENT_KEYWORDS):
        recency_requirement = "recent"
    locale_domain_scope = "china" if _contains_any(question, DEEP_CHINA_KEYWORDS) else "global"
    if known_url:
        locale_domain_scope = "known_domains"
    claim_risk = "high" if recency_requirement in {"recent", "current"} or _contains_any(question, {"核验", "验证", "真假", "价格", "行情", "财经", "医疗", "政策", "监管", "risk"}) else "medium"
    cross_validation_need = "high" if claim_risk == "high" or _contains_any(question, {"对比", "选型", "核验", "验证", "compare", "versus"}) else "normal"
    authority_need = "high" if docs_intent or claim_risk == "high" or _contains_any(question, {"官方", "文档", "论文", "标准", "政策", "监管", "official"}) else "normal"
    complex_query = _is_deep_complex(question, budget)
    difficulty = "high" if complex_query else "standard"

    intent_signals = {
        "recency_requirement": recency_requirement,
        "docs_api_intent": docs_intent,
        "locale_domain_scope": locale_domain_scope,
        "known_url": known_url,
        "source_authority_need": authority_need,
        "claim_risk": claim_risk,
        "cross_validation_need": cross_validation_need,
        "breadth_depth_budget": budget,
    }

    decomposition: list[dict[str, Any]] = []
    capability_plan: list[dict[str, Any]] = []
    steps: list[dict[str, str]] = []

    def add_step(sub_id: str, tool: str, purpose: str, command: str, filename: str) -> None:
        step_id = f"s{len(steps) + 1}"
        steps.append(_deep_step(step_id, sub_id, tool, purpose, command, _path_join(evidence_root, filename)))

    def next_filename(suffix: str) -> str:
        return f"{len(steps) + 1:02d}-{suffix}"

    def command_search(q: str, extra_sources: int = 2) -> str:
        return f"smart-search search {_quote_arg(q)} --validation balanced --extra-sources {extra_sources} --format json --output {_quote_arg(_path_join(evidence_root, next_filename('search.json')))}"

    def command_exa(q: str) -> str:
        return f"smart-search exa-search {_quote_arg(q)} --num-results 5 --format json --output {_quote_arg(_path_join(evidence_root, next_filename('exa.json')))}"

    def command_zhipu(q: str) -> str:
        return f"smart-search zhipu-search {_quote_arg(q)} --count 5 --format json --output {_quote_arg(_path_join(evidence_root, next_filename('zhipu.json')))}"

    def command_fetch(target: str = "<key-url>") -> str:
        return f"smart-search fetch {_quote_arg(target)} --format markdown --output {_quote_arg(_path_join(evidence_root, next_filename('fetch.md')))}"

    def has_capability(name: str) -> bool:
        return any(item.get("capability") == name for item in capability_plan)

    if known_url:
        url = urls[0]
        parsed = urlparse(url)
        host = parsed.netloc or "provided URL"
        decomposition.append(
            _deep_subquestion(
                "sq1",
                f"这个已知来源页面本身说了什么？{url}",
                "用户已经给出 URL，Deep Research 必须先抓正文再扩展。",
                ["page_evidence"],
            )
        )
        decomposition.append(
            _deep_subquestion(
                "sq2",
                f"围绕 {host} 还需要哪些相邻来源或交叉来源？",
                "已知好 URL 适合用相似页面和广泛发现扩展证据。",
                ["adjacent_source_discovery", "broad_discovery"],
            )
        )
        capability_plan.extend(
            [
                _deep_capability("page_evidence", ["fetch"], "Fetch the user-provided URL before making claims."),
                _deep_capability("adjacent_source_discovery", ["exa-similar"], "Find pages adjacent to the known source."),
                _deep_capability("broad_discovery", ["search"], "Broaden the context if the fetched page leaves gaps."),
            ]
        )
        add_step("sq1", "fetch", "fetch user supplied URL first", f"smart-search fetch {_quote_arg(url)} --format markdown --output {_quote_arg(_path_join(evidence_root, '01-fetch.md'))}", "01-fetch.md")
        add_step("sq2", "exa-similar", "find adjacent sources from the provided URL", f"smart-search exa-similar {_quote_arg(url)} --num-results 5 --format json --output {_quote_arg(_path_join(evidence_root, '02-similar.json'))}", "02-similar.json")
        add_step("sq2", "search", "broad discovery for missing context", command_search(question, 1), "03-search.json")
    else:
        decomposition.append(
            _deep_subquestion(
                "sq1",
                f"{question} 的整体问题轮廓和候选来源是什么？",
                "先做 broad discovery，避免一开始把问题拆错。",
                ["broad_discovery"],
            )
        )
        capability_plan.append(_deep_capability("broad_discovery", ["search"], "Find the initial answer shape and candidate sources."))
        add_step("sq1", "search", "broad discovery and routing metadata", command_search(question, 1 if budget == "quick" else 3), "01-search.json")

        if docs_intent:
            decomposition.append(
                _deep_subquestion(
                    "sq2",
                    f"{question} 的官方文档、API 或 SDK 证据在哪里？",
                    "docs/API intent should resolve the library docs first, with Exa only as official-domain discovery.",
                    ["docs_source_discovery", "page_evidence"],
                )
            )
            capability_plan.append(
                _deep_capability(
                    "docs_source_discovery",
                    ["context7-library", "context7-docs"],
                    "Resolve official library/API documentation first; use Exa only for official-domain or supplemental discovery.",
                )
            )
            library_hint = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9_.-]*", question)[:2]) or "<library-name>"
            add_step(
                "sq2",
                "context7-library",
                "resolve library id for docs/API intent",
                f"smart-search context7-library {_quote_arg(library_hint)} {_quote_arg(question)} --format json --output {_quote_arg(_path_join(evidence_root, next_filename('context7-library.json')))}",
                next_filename("context7-library.json"),
            )
            add_step(
                "sq2",
                "context7-docs",
                "retrieve docs after selecting the best library_id",
                f"smart-search context7-docs {_quote_arg('<library_id>')} {_quote_arg(question)} --format json --output {_quote_arg(_path_join(evidence_root, next_filename('context7-docs.json')))}",
                next_filename("context7-docs.json"),
            )
            if _contains_any(question, DEEP_EXA_DISCOVERY_KEYWORDS):
                capability_plan.append(
                    _deep_capability(
                        "official_domain_discovery",
                        ["exa-search"],
                        "Use Exa for official-domain or low-noise supplemental docs discovery.",
                    )
                )
                add_step("sq2", "exa-search", "official-domain docs source discovery", command_exa(f"{question} official docs"), next_filename("exa.json"))

        if recency_requirement != "none" or locale_domain_scope == "china":
            sub_id = f"sq{len(decomposition) + 1}"
            decomposition.append(
                _deep_subquestion(
                    sub_id,
                    f"{question} 的最新或中文/国内来源如何交叉验证？",
                    "Current or China-scoped prompts benefit from Zhipu web-search reinforcement.",
                    ["current_or_locale_source_discovery"],
                )
            )
            capability_plan.append(
                _deep_capability("current_or_locale_source_discovery", ["zhipu-search"], "Reinforce Chinese, domestic, or current web evidence.")
            )
            add_step(sub_id, "zhipu-search", "current or locale-specific source discovery", command_zhipu(question), f"{len(steps) + 1:02d}-zhipu.json")

        if complex_query:
            while len(decomposition) < (2 if budget != "deep" else 4):
                sub_id = f"sq{len(decomposition) + 1}"
                if len(decomposition) == 1:
                    sub_question = f"{question} 里有哪些主要选项、说法或路线需要分别验证？"
                    reason = "Complex prompts need explicit comparison targets before final synthesis."
                    caps = ["cross_validation"]
                elif len(decomposition) == 2:
                    sub_question = f"{question} 的成本、风险、限制和适用边界是什么？"
                    reason = "High-difficulty research needs downside and boundary checks."
                    caps = ["low_noise_source_discovery", "page_evidence"]
                else:
                    sub_question = f"基于已抓取证据，{question} 应该如何形成可执行结论？"
                    reason = "A deep budget should reserve one synthesis-oriented gap check subquestion."
                    caps = ["gap_check"]
                decomposition.append(_deep_subquestion(sub_id, sub_question, reason, caps))
            if not has_capability("cross_validation"):
                capability_plan.append(
                    _deep_capability("cross_validation", ["search"], "Compare independent sources before final claims; supplemental tools depend on intent.")
                )
            if budget == "deep" and _contains_any(question, DEEP_EXA_DISCOVERY_KEYWORDS):
                add_step("sq3", "exa-search", "low-noise evidence for tradeoffs and risks", command_exa(f"{question} risks limitations comparison"), next_filename("exa.json"))

        if cross_validation_need == "high":
            if not has_capability("cross_validation"):
                capability_plan.append(
                    _deep_capability("cross_validation", ["search"], "Compare independent sources before final claims; supplemental tools depend on intent.")
                )
            target_subquestion = decomposition[-1]["id"] if decomposition else "sq1"
            cross_validation_tools = next((item["tools"] for item in capability_plan if item.get("capability") == "cross_validation"), [])
            if recency_requirement != "none" or locale_domain_scope == "china" or zh_current_intent:
                if "zhipu-search" not in cross_validation_tools:
                    cross_validation_tools.append("zhipu-search")
                if not any(step["tool"] == "zhipu-search" for step in steps):
                    add_step(target_subquestion, "zhipu-search", "current or locale-specific cross-source discovery", command_zhipu(question), next_filename("zhipu.json"))
            elif docs_intent:
                if "context7-library" not in cross_validation_tools:
                    cross_validation_tools.extend(["context7-library", "context7-docs"])
            elif _contains_any(question, DEEP_EXA_DISCOVERY_KEYWORDS):
                if "exa-search" not in cross_validation_tools:
                    cross_validation_tools.append("exa-search")
                if not any(step["tool"] == "exa-search" for step in steps):
                    add_step(target_subquestion, "exa-search", "official-domain or low-noise cross-source discovery", command_exa(question), next_filename("exa.json"))

        capability_plan.append(_deep_capability("page_evidence", ["fetch"], "Fetch key URLs before claim-level conclusions."))
        add_step("sq1" if len(decomposition) == 1 else decomposition[-1]["id"], "fetch", "fetch key URLs before final claims", command_fetch(), next_filename("fetch.md"))

    for item in capability_plan:
        item["tools"] = [tool for tool in item["tools"] if tool in DEEP_ALLOWED_TOOLS]
    steps = [step for step in steps if step["tool"] in DEEP_ALLOWED_TOOLS]
    if budget == "quick" and len(decomposition) > 2:
        decomposition = decomposition[:2]
    if budget == "quick" and len(steps) > 4:
        limited_steps = steps[:4]
        if not any(step["tool"] == "fetch" for step in limited_steps):
            first_fetch = next((step for step in steps if step["tool"] == "fetch"), None)
            if first_fetch:
                first_fetch = dict(first_fetch)
                fetch_path = _path_join(evidence_root, "04-fetch.md")
                first_fetch["command"] = f"smart-search fetch {_quote_arg('<key-url>')} --format markdown --output {_quote_arg(fetch_path)}"
                first_fetch["output_path"] = fetch_path
                limited_steps = steps[:3] + [first_fetch]
        steps = limited_steps[:4]
    if budget == "quick":
        valid_subquestion_ids = {item["id"] for item in decomposition}
        fallback_subquestion_id = decomposition[-1]["id"] if decomposition else "sq1"
        for index, step in enumerate(steps, start=1):
            step["id"] = f"s{index}"
            if step.get("subquestion_id") not in valid_subquestion_ids:
                step["subquestion_id"] = fallback_subquestion_id

    return {
        "ok": True,
        "mode": "deep_research",
        "query_mode": "deep",
        "question": question,
        "trigger_source": "explicit_cli",
        "difficulty": difficulty,
        "intent_signals": intent_signals,
        "decomposition": decomposition,
        "capability_plan": capability_plan,
        "evidence_policy": "fetch_before_claim",
        "preflight": {
            "tool": "doctor",
            "command": "smart-search doctor --format json",
            "when": "configuration or provider availability is uncertain",
            "executed_by_deep_command": False,
        },
        "steps": steps,
        "gap_check": {
            "required": True,
            "rule": "fetch missing evidence for key claims or downgrade unsupported claims to unverified candidates",
            "unsupported_claim_action": "downgrade_to_unverified_candidate",
        },
        "final_answer_policy": "cite fetched evidence, list unverified candidates, and include key commands",
        "usage_boundary": {
            "search": "smart-search search runs live fast/broad search immediately.",
            "deep": "smart-search deep is an offline planner; it does not execute provider calls or fetch pages.",
            "execution": "An AI agent or user executes the listed steps with existing CLI commands, then performs gap_check.",
        },
        "allowed_tools": sorted(DEEP_ALLOWED_TOOLS),
        "evidence_dir": evidence_root,
        "elapsed_ms": _elapsed_ms(start),
    }


async def research(
    query: str,
    budget: str = "deep",
    evidence_dir: str = "",
    fallback: str = "auto",
    stream: bool | None = None,
) -> dict[str, Any]:
    start = time.time()
    question = query.strip()
    fallback_mode = (fallback or "auto").strip().lower()
    if fallback_mode not in config._ALLOWED_FALLBACK_MODES:
        return {
            "ok": False, "error_type": "parameter_error",
            "error": source_message('Invalid fallback mode: {0}', fallback_mode),
            "question": question, "mode": "deep_research_execution",
            "route_policy_version": RESEARCH_ROUTE_POLICY_VERSION, "elapsed_ms": _elapsed_ms(start),
        }
    level = _deep_budget(budget or "deep")
    plan = build_deep_research_plan(question, budget=level, evidence_dir=evidence_dir)
    timeout = min(config.search_timeout, {"quick": 45, "standard": 120, "deep": config.search_timeout}[level])
    return await jev_search.search(
        question, validation="strict" if level == "deep" else "balanced", fallback=fallback_mode,
        providers="auto", timeout_seconds=timeout, stream=stream, research_plan=plan, single_pass=False,
    )


def get_capability_status() -> dict[str, Any]:
    main_configured = _configured_main_search_provider_ids()
    status = {
        "main_search": {
            "configured": main_configured,
            "fallback_chain": MAIN_SEARCH_FALLBACK_CHAIN,
            "ok": bool(main_configured),
        },
        "web_search": {
            "configured": [
                name
                for name, enabled in [
                    ("zhipu", _provider_configured("zhipu")),
                    ("zhipu-mcp", _provider_configured("zhipu-mcp")),
                    ("tavily", _provider_configured("tavily")),
                    ("firecrawl", _provider_configured("firecrawl")),
                    ("tinyfish", _provider_configured("tinyfish")),
                    ("deepseek", _provider_configured("deepseek")),
                ]
                if enabled
            ],
            "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl", "tinyfish", "deepseek"],
        },
        "docs_search": {
            "configured": [
                name
                for name, enabled in [
                    ("context7", _provider_configured("context7")),
                    ("exa", _provider_configured("exa")),
                ]
                if enabled
            ],
            "fallback_chain": ["context7", "exa"],
        },
        "web_fetch": {
            "configured": [
                name
                for name, enabled in [
                    ("tavily", _provider_configured("tavily")),
                    ("jina", _provider_configured("jina")),
                    ("zhipu-mcp-reader", _provider_configured("zhipu-mcp-reader")),
                    ("firecrawl", _provider_configured("firecrawl")),
                    ("tinyfish", _provider_configured("tinyfish")),
                    ("deepseek", _provider_configured("deepseek")),
                ]
                if enabled
            ],
            "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish", "deepseek"],
        },
        "vertical_search": {
            "configured": [
                name
                for name, enabled in [
                    ("anysearch", _provider_configured("anysearch")),
                    ("sciverse", _provider_configured("sciverse")),
                ]
                if enabled
            ],
            "fallback_chain": ["anysearch"],
            "experimental": True,
            "explicit_only": ["sciverse"],
            "route_enabled": {"anysearch": True, "sciverse": False},
        },
    }
    for capability in ("web_search", "docs_search", "web_fetch", "vertical_search"):
        status[capability]["ok"] = bool(status[capability]["configured"])
    return status


def _minimum_profile_result(profile: str, capability_status: dict[str, Any]) -> dict[str, Any]:
    required = [] if profile == "off" else ["retrieval"]
    available = any(
        provider not in config.research_disabled_providers
        and not PROVIDER_PROFILES.get(provider, {}).get("explicit_only")
        for status in capability_status.values() for provider in status.get("configured", [])
    )
    missing = required if not available else []
    return {
        "ok": not missing,
        "error_type": "config_error" if missing else "",
        "error": source_message('Configure at least one enabled retrieval channel.') if missing else "",
        "profile": profile,
        "required": required,
        "missing": missing,
        "capability_status": capability_status,
    }


def validate_minimum_profile() -> dict[str, Any]:
    try:
        config.intent_router_mode
        profile = config.minimum_profile
    except ValueError as e:
        return {"ok": False, "error_type": "parameter_error", "error": str(e), "missing": []}
    return _minimum_profile_result(profile, get_capability_status())


def _parse_provider_filter(providers: str = "auto") -> set[str] | None:
    if not providers or providers.strip().lower() == "auto":
        return None
    return {item.strip().lower() for item in providers.split(",") if item.strip()}


def _provider_allowed(provider_id: str, provider_filter: set[str] | None) -> bool:
    if provider_filter is None:
        return True
    aliases = MAIN_SEARCH_PROVIDER_ALIASES.get(provider_id, {provider_id})
    return bool(provider_filter.intersection(aliases))


def _configured_main_search_provider_ids() -> list[str]:
    return [provider for provider in MAIN_SEARCH_FALLBACK_CHAIN if _provider_configured(provider)]


def _main_search_provider_configs(model_override: str = "", providers: str = "auto") -> list[dict[str, Any]]:
    provider_filter = _parse_provider_filter(providers)
    by_provider: dict[str, dict[str, Any]] = {}

    if _provider_allowed("xai-responses", provider_filter) and _provider_configured("xai-responses"):
        by_provider["xai-responses"] = {
            "provider": "xai-responses",
            "mode": "xai-responses",
            "api_url": config.xai_api_url,
            "api_key": config.xai_api_key,
            "model": model_override or config.xai_model,
            "tools": config.parse_xai_tools(config.xai_tools_raw),
            "reasoning_effort": config.xai_reasoning_effort,
            "stream": config.xai_stream,
            "source": "XAI_*",
        }

    if _provider_allowed("openai-compatible", provider_filter) and _provider_configured("openai-compatible"):
        by_provider["openai-compatible"] = {
            "provider": "openai-compatible",
            "mode": config.openai_compatible_api_mode,
            "api_mode": config.openai_compatible_api_mode,
            "api_url": config.openai_compatible_api_url,
            "api_key": config.openai_compatible_api_key,
            "model": model_override or config.openai_compatible_model,
            "fallback_models": [] if model_override else config.openai_compatible_fallback_models,
            "stream": config.openai_compatible_stream,
            "tools": [],
            "source": "OPENAI_COMPATIBLE_*",
        }

    return [
        by_provider[provider]
        for provider in MAIN_SEARCH_FALLBACK_CHAIN
        if provider in by_provider and _provider_allowed(provider, provider_filter)
    ]


def _main_search_providers(provider_configs: list[dict[str, Any]], fallback: str) -> list[Any]:
    selected = provider_configs if fallback != "off" else provider_configs[:1]
    providers: list[Any] = []
    for provider_config in selected:
        if provider_config["provider"] == "xai-responses":
            providers.append(
                XAIResponsesSearchProvider(
                    provider_config["api_url"],
                    provider_config["api_key"],
                    provider_config["model"],
                    provider_config["tools"],
                    stream=provider_config.get("stream", False),
                    reasoning_effort=provider_config.get("reasoning_effort", ""),
                )
            )
        else:
            providers.append(
                OpenAICompatibleSearchProvider(
                    provider_config["api_url"],
                    provider_config["api_key"],
                    provider_config["model"],
                    provider_config.get("stream", False),
                    provider_config.get("api_mode", provider_config.get("mode", "chat-completions")),
                )
            )
    return providers


async def _search_model_channel(
    provider_config: dict[str, Any], query: str, platform: str, *,
    deadline: float, fallback: str, model_override: str,
) -> dict[str, Any]:
    """Keep existing model/transport failover inside the selected search channel."""
    candidates = (_openai_model_candidates(provider_config, fallback_mode=fallback, model_override=model_override)
                  if provider_config["provider"] == "openai-compatible" else [provider_config])
    attempts: list[dict] = []
    result: dict[str, Any] = {"ok": False, "content": "", "attempts": attempts,
                              "primary_api_mode": provider_config["mode"],
                              "error_type": "network_error", "error": "No available search model",
                              "models": [item["model"] for item in candidates],
                              "stream": bool(provider_config.get("stream")),
                              "api_mode": provider_config.get("api_mode", provider_config["mode"])}
    for candidate in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= _CLOCK_RESOLUTION:
            result.update(error_type="timeout", error="Search deadline exhausted")
            break
        started = time.time()
        api_mode = candidate.get("api_mode", candidate["mode"])
        relay = candidate["provider"] == "openai-compatible"
        extra = {"model": candidate["model"], "model_role": candidate.get("model_role", "primary"),
                 "stream": bool(candidate.get("stream")), "api_mode": api_mode,
                 "attempt_timeout_seconds": round(remaining, 3)}
        if candidate["provider"] == "xai-responses":
            extra["reasoning_effort"] = candidate.get("reasoning_effort", "")
            extra["transport"] = "stream" if candidate.get("stream") else "non_stream"
        if candidate.get("fallback_from_model"):
            extra["fallback_from_model"] = candidate["fallback_from_model"]
        if relay:
            extra["endpoint"] = openai_compatible_endpoint(candidate["api_url"], api_mode)
            breaker = _openai_model_breaker_state(candidate["api_url"], candidate["model"], api_mode)
            if breaker.get("state") == "open":
                attempts.append(_attempt("main_search", candidate["provider"], "skipped", started,
                                         error_type="network_error", error="model breaker open", extra={**extra, "breaker_state": breaker}))
                continue
        provider = _main_search_providers([candidate], fallback="off")[0]
        set_deadline = getattr(provider, "set_search_deadline", None)
        if callable(set_deadline):
            set_deadline(deadline)
        activity.progress("main_search", candidate["provider"], candidate["model"])
        status, error_type, error = "error", "", ""
        try:
            content = await asyncio.wait_for(provider.search(query, platform), max(0.001, deadline - time.monotonic()))
            if not content:
                raise ProviderCallError("network_error", "Search model returned an empty response")
            answer, sources = split_answer_and_sources(content)
            problem = model_answer_problem(answer, sources)
            if problem:
                status, error_type, error = "empty", "evidence_error", problem[1]
                result.update(error_type=error_type, error=error)
                result.update(answer_check={"status": "rejected", "method": "local", "reason": problem[0],
                                            "provider": candidate["provider"], "api_mode": api_mode, "model": candidate["model"]})
                continue
            result["answer_check"] = {"status": "passed", "method": "local", "reason": "",
                                      "provider": candidate["provider"], "api_mode": api_mode, "model": candidate["model"]}
            status = "ok"
            result.update(ok=True, content=content, model=candidate["model"], primary_api_mode=candidate["mode"],
                          error_type="", error="")
            if relay:
                _record_openai_model_success(candidate["api_url"], candidate["model"], api_mode)
        except Exception as exc:
            error_type, error = classify_provider_exception(exc)
            result.update(error_type=error_type, error=error)
            if relay:
                extra["breaker_state"] = _record_openai_model_failure(candidate["api_url"], candidate["model"], api_mode)
        finally:
            if not _append_openai_transport_attempts(attempts, provider, candidate, extra=extra):
                attempts.append(_attempt("main_search", candidate["provider"], status, started,
                                         result_count=1 if status == "ok" else 0,
                                         error_type=error_type, error=error, extra=extra))
            elif error_type == "evidence_error":
                attempts[-1].update(status=status, result_count=0, error_type=error_type, error=error)
        if result["ok"]:
            break
    return result


async def fetch_available_models(api_url: str, api_key: str) -> list[str]:
    models_url = f"{normalize_openai_compatible_api_url(api_url)}/models"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            models_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()

    models: list[str] = []
    for item in (data or {}).get("data", []) or []:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return models


async def get_available_models_cached(api_url: str, api_key: str) -> list[str]:
    key = (api_url, api_key)
    async with _AVAILABLE_MODELS_LOCK:
        if key in _AVAILABLE_MODELS_CACHE:
            return _AVAILABLE_MODELS_CACHE[key]

    try:
        models = await fetch_available_models(api_url, api_key)
    except Exception:
        models = []

    async with _AVAILABLE_MODELS_LOCK:
        _AVAILABLE_MODELS_CACHE[key] = models
    return models


async def _run_web_fetch_fallback(
    url: str,
    fallback: str = "auto",
    preferred_order: list[str] | None = None,
    *,
    deadline: float | None = None,
) -> tuple[dict[str, Any] | None, list[dict]]:
    attempts: list[dict] = []
    providers = []
    if _provider_configured("tavily"):
        providers.append("tavily")
    if _provider_configured("jina"):
        providers.append("jina")
    if _provider_configured("zhipu-mcp-reader"):
        providers.append("zhipu-mcp-reader")
    if _provider_configured("firecrawl"):
        providers.append("firecrawl")
    if _provider_configured("tinyfish"):
        providers.append("tinyfish")
    if _provider_configured("deepseek"):
        providers.append("deepseek")
    if preferred_order:
        allowed = {provider for provider in providers}
        ordered = [provider for provider in preferred_order if provider in allowed]
        ordered.extend(provider for provider in providers if provider not in ordered)
        providers = ordered
    if fallback == "off":
        providers = providers[:1]

    providers, skipped = _plan_provider_health("web_fetch", providers)
    attempts.extend(skipped)

    def bounded(call):
        return call if deadline is None else asyncio.wait_for(call, deadline - time.monotonic())

    for provider in providers:
        start = time.time()
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= _CLOCK_RESOLUTION:
            attempts.append(_attempt("web_fetch", provider, "skipped", start,
                                     error_type="timeout", error="fetch deadline exhausted"))
            break
        activity.progress("web_fetch", provider)
        try:
            if provider == "tavily":
                content = await bounded(call_tavily_extract(url))
            elif provider == "jina":
                data = await bounded(jina_fetch(url))
                content = data.get("content") if data.get("ok") else None
                if not data.get("ok"):
                    status = _attempt_status_for_result(data)
                    health_extra = _record_provider_result(provider, status, data.get("error_type", ""), data.get("error", ""))
                    attempts.append(_attempt("web_fetch", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", ""), extra=health_extra))
                    continue
            elif provider == "zhipu-mcp-reader":
                data = await bounded(zhipu_mcp_reader(url))
                content = data.get("content") if data.get("ok") else None
                if not data.get("ok"):
                    status = _attempt_status_for_result(data)
                    health_extra = _record_provider_result(provider, status, data.get("error_type", ""), data.get("error", ""))
                    attempts.append(_attempt("web_fetch", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", ""), extra=health_extra))
                    continue
            elif provider == "tinyfish":
                data = await bounded(call_tinyfish_fetch(url))
                content = data.get("content") if data.get("ok") else None
                if not data.get("ok"):
                    status = _attempt_status_for_result(data)
                    health_extra = _record_provider_result(provider, status, data.get("error_type", ""), data.get("error", ""))
                    attempts.append(_attempt("web_fetch", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", ""), extra=health_extra))
                    continue
            elif provider == "deepseek":
                content = await bounded(call_deepseek_fetch(url))
            else:
                content = await bounded(call_firecrawl_scrape(url))
            if content and content.strip():
                _record_provider_result(provider, "ok")
                attempts.append(_attempt("web_fetch", provider, "ok", start, result_count=1))
                return {
                    "ok": True,
                    "url": url,
                    "provider": provider,
                    "content": content,
                }, attempts
            attempts.append(_attempt("web_fetch", provider, "empty", start))
        except Exception as e:
            attempts.append(_attempt_with_health("web_fetch", provider, start, e))
    return None, attempts


def _provider_response_object(data: Any, provider: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProviderCallError("parse_error", source_message('{0} response is not a JSON object', provider))
    return data


def _provider_tool_error(
    data: dict[str, Any], provider: str, *, additional_secrets: tuple[str, ...] = ()
) -> ProviderCallError | None:
    if data.get("success") is not False and not data.get("error") and not data.get("detail"):
        return None
    raw_error = data.get("error") or data.get("detail") or f"{provider} reported a tool failure"
    if isinstance(raw_error, dict):
        raw_error = raw_error.get("message") or raw_error.get("detail") or json.dumps(raw_error, ensure_ascii=False)
    return ProviderCallError(
        "provider_error", str(raw_error)[:300], additional_secrets=additional_secrets
    )


async def call_tavily_extract(url: str) -> str | None:
    if not _tavily_is_enabled():
        return None
    api_key = config.tavily_api_key
    endpoint = f"{config.tavily_api_url.rstrip('/')}/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"urls": [url], "format": "markdown"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = _provider_response_object(response.json(), "Tavily")
    except Exception as exc:
        raise provider_call_error(exc, additional_secrets=(api_key,)) from exc
    tool_error = _provider_tool_error(data, "Tavily", additional_secrets=(api_key,))
    if tool_error:
        raise tool_error
    results = data.get("results")
    if not isinstance(results, list):
        raise ProviderCallError("parse_error", source_message('Tavily extract response is missing results'))
    if not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        raise ProviderCallError("parse_error", source_message('Tavily extract result is not an object'))
    content = first.get("raw_content", "")
    if not isinstance(content, str):
        raise ProviderCallError("parse_error", source_message('Tavily extract content is not text'))
    return content if content.strip() else None


async def call_tavily_search(query: str, max_results: int = 6) -> list[dict] | None:
    if not _tavily_is_enabled():
        return None
    api_key = config.tavily_api_key
    endpoint = f"{config.tavily_api_url.rstrip('/')}/search"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
        "include_raw_content": False,
        "include_answer": False,
    }
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = _provider_response_object(response.json(), "Tavily")
    except Exception as exc:
        raise provider_call_error(exc, additional_secrets=(api_key,)) from exc
    tool_error = _provider_tool_error(data, "Tavily", additional_secrets=(api_key,))
    if tool_error:
        raise tool_error
    results = data.get("results")
    if not isinstance(results, list):
        raise ProviderCallError("parse_error", source_message('Tavily search response is missing results'))
    if not results:
        return None
    if not all(isinstance(item, dict) for item in results):
        raise ProviderCallError("parse_error", source_message('Tavily search result is not an object'))
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "score": item.get("score", 0),
        }
        for item in results
    ]


async def call_firecrawl_search(query: str, limit: int = 14) -> list[dict] | None:
    if not config.provider_enabled("firecrawl"):
        return None
    api_key = config.firecrawl_api_key
    if not api_key:
        return None
    endpoint = f"{config.firecrawl_api_url.rstrip('/')}/search"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"query": query, "limit": limit}
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = _provider_response_object(response.json(), "Firecrawl")
    except Exception as exc:
        raise provider_call_error(exc, additional_secrets=(api_key,)) from exc
    tool_error = _provider_tool_error(data, "Firecrawl", additional_secrets=(api_key,))
    if tool_error:
        raise tool_error
    payload = data.get("data")
    if not isinstance(payload, dict):
        raise ProviderCallError("parse_error", source_message('Firecrawl search response is missing data'))
    results = payload.get("web")
    if not isinstance(results, list):
        raise ProviderCallError("parse_error", source_message('Firecrawl search response is missing web results'))
    if not results:
        return None
    if not all(isinstance(item, dict) for item in results):
        raise ProviderCallError("parse_error", source_message('Firecrawl search result is not an object'))
    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
        }
        for item in results
    ]


async def call_firecrawl_scrape(url: str, ctx=None) -> str | None:
    if not config.provider_enabled("firecrawl"):
        return None
    api_key = config.firecrawl_api_key
    if not api_key:
        return None
    endpoint = f"{config.firecrawl_api_url.rstrip('/')}/scrape"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    for attempt in range(config.retry_max_attempts):
        body = {
            "url": url,
            "formats": ["markdown"],
            "timeout": 60000,
            "waitFor": (attempt + 1) * 1500,
        }
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                response = await client.post(endpoint, headers=headers, json=body)
                response.raise_for_status()
                data = _provider_response_object(response.json(), "Firecrawl")
        except Exception as exc:
            raise provider_call_error(exc, additional_secrets=(api_key,)) from exc
        tool_error = _provider_tool_error(data, "Firecrawl", additional_secrets=(api_key,))
        if tool_error:
            raise tool_error
        payload = data.get("data")
        if not isinstance(payload, dict):
            raise ProviderCallError("parse_error", source_message('Firecrawl scrape response is missing data'))
        markdown = payload.get("markdown", "")
        if not isinstance(markdown, str):
            raise ProviderCallError("parse_error", source_message('Firecrawl scrape content is not text'))
        if markdown.strip():
            return markdown
        await log_info(ctx, f"Firecrawl: markdown empty, retry {attempt + 1}/{config.retry_max_attempts}", config.debug_enabled)
    return None


async def call_tinyfish_search(query: str, max_results: int = 6) -> list[dict] | None:
    """Return normalized TinyFish candidates, or None when the provider gave nothing.

    A provider-side failure raises so the shared web_search boundary records the
    attempt and falls through to the next configured provider.
    """
    if not config.provider_enabled("tinyfish"):
        return None
    api_key = config.tinyfish_api_key
    if not api_key:
        return None
    data = await _decode_provider_json(
        await TinyFishSearchProvider(
            config.tinyfish_search_api_url,
            api_key,
            config.tinyfish_timeout,
        ).search(query, max_results=max_results),
        provider="tinyfish",
    )
    if not data.get("ok"):
        raise ProviderCallError(
            str(data.get("error_type") or "provider_error"),
            str(data.get("error") or "TinyFish search failed"),
            additional_secrets=(api_key,),
        )
    results = data.get("results")
    if not isinstance(results, list):
        raise ProviderCallError("parse_error", source_message('TinyFish search payload is missing results'))
    return [item for item in results if isinstance(item, dict)]


async def call_tinyfish_fetch(url: str) -> dict[str, Any]:
    if disabled := _provider_disabled_result("tinyfish"):
        return disabled
    api_key = config.tinyfish_api_key
    if not api_key:
        return {
            "ok": False,
            "provider": "tinyfish",
            "url": url,
            "error_type": "config_error",
            "error": (
                source_message('TINYFISH_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set TINYFISH_API_KEY <key>`。')
            ),
        }
    raw = await TinyFishFetchProvider(
        config.tinyfish_fetch_api_url,
        api_key,
        config.tinyfish_timeout,
    ).fetch(url)
    return await _decode_provider_json(raw, provider="tinyfish")


def _deepseek_provider() -> DeepSeekToolsProvider:
    return DeepSeekToolsProvider(config.deepseek_api_url, config.deepseek_api_key or "", config.deepseek_timeout)


async def call_deepseek_search(query: str, max_results: int = 6) -> list[dict] | None:
    """Return normalized DeepSeek candidates; a provider failure raises for fallback."""
    if not config.provider_enabled("deepseek") or not config.deepseek_api_key:
        return None
    return await _deepseek_provider().search(query, max_results=max_results)


async def call_deepseek_fetch(url: str) -> str | None:
    """Return page Markdown, or None when DeepSeek has no usable text for the URL."""
    if not config.provider_enabled("deepseek") or not config.deepseek_api_key:
        return None
    page = await _deepseek_provider().fetch(url)
    return page["content"] if page else None


async def call_jina_reader(url: str) -> dict[str, Any]:
    if disabled := _provider_disabled_result("jina"):
        return disabled
    raw = await JinaReaderProvider(
        config.jina_reader_api_url,
        config.jina_api_key,
        config.jina_respond_with,
        config.jina_timeout,
    ).fetch(url)
    return await _decode_provider_json(raw, provider="jina")


async def call_tavily_map(
    url: str,
    instructions: str = "",
    max_depth: int = 1,
    max_breadth: int = 20,
    limit: int = 50,
    timeout: int = 150,
) -> dict[str, Any]:
    if not config.tavily_enabled:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": _tavily_disabled_message(),
            "disabled": True,
        }
    api_key = config.tavily_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": source_message('TAVILY_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set TAVILY_API_KEY <key>`。'),
        }

    endpoint = f"{config.tavily_api_url.rstrip('/')}/map"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"url": url, "max_depth": max_depth, "max_breadth": max_breadth, "limit": limit, "timeout": timeout}
    if instructions:
        body["instructions"] = instructions
    try:
        async with httpx.AsyncClient(timeout=float(timeout + 10)) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = _provider_response_object(response.json(), "Tavily")
        tool_error = _provider_tool_error(data, "Tavily", additional_secrets=(api_key,))
        if tool_error:
            raise tool_error
        results = data.get("results")
        if not isinstance(results, list):
            raise ProviderCallError("parse_error", source_message('Tavily map response is missing results'))
        return {
            "ok": True,
            "base_url": data.get("base_url", ""),
            "results": results,
            "response_time": data.get("response_time", 0),
        }
    except Exception as exc:
        error_type, error = classify_provider_exception(exc, additional_secrets=(api_key,))
        return {"ok": False, "error_type": error_type, "error": error}


async def search(
    query: str,
    platform: str = "",
    model: str = "",
    extra_sources: int = 0,
    validation: str = "",
    fallback: str = "",
    providers: str = "auto",
    stream: bool | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    start = time.time()
    try:
        effective_timeout = _resolve_search_timeout(timeout_seconds)
        validation_level = (validation or config.validation_level).strip().lower()
        fallback_mode = (fallback or config.fallback_mode).strip().lower()
        if validation_level not in config._ALLOWED_VALIDATION_LEVELS:
            raise ValueError(source_message('Invalid validation level: {0}', validation_level))
        if fallback_mode not in config._ALLOWED_FALLBACK_MODES:
            raise ValueError(source_message('Invalid fallback mode: {0}', fallback_mode))
        config.intent_router_mode
    except ValueError as exc:
        return _empty_search_result(start, new_session_id(), query, "parameter_error", str(exc))
    return await jev_search.search(
        query, validation=validation_level, fallback=fallback_mode, providers=providers,
        timeout_seconds=effective_timeout, platform=platform, model=model, stream=stream, extra_sources=extra_sources,
    )


async def route(
    query: str,
    validation: str = "",
    mode: str = "",
    allow_remote: bool = False,
) -> dict[str, Any]:
    start = time.time()
    try:
        validation_level = (validation or config.validation_level).strip().lower()
        if validation_level not in config._ALLOWED_VALIDATION_LEVELS:
            raise ValueError(source_message('Invalid validation level: {0}', validation_level))
        selected_mode = normalize_router_mode(mode or config.intent_router_mode)
        return await jev_search.plan(query, validation_level, allow_remote=allow_remote, mode=selected_mode)
    except ValueError as exc:
        return {"ok": False, "query": query, "error_type": "parameter_error", "error": str(exc), "elapsed_ms": _elapsed_ms(start)}


async def route_calibrate(models: str = "") -> dict[str, Any]:
    return {
        "ok": False, "error_type": "parameter_error", "deprecated": True,
        "error": source_message('Embedding/classifier routing is retired. Use route for a local preview or route --remote for Jev diagnostics.'),
        "executed_remote": False, "model_results": [], "elapsed_ms": 0.0,
    }


async def fetch(url: str, timeout_seconds: float | None = None) -> dict[str, Any]:
    start = time.time()
    try:
        effective = _resolve_search_timeout(timeout_seconds)
        budget = SearchBudget(effective)
    except ValueError as exc:
        return {"ok": False, "url": url, "error_type": "parameter_error", "error": str(exc), "elapsed_ms": _elapsed_ms(start)}
    fetch_result, attempts = await _run_web_fetch_fallback(url, deadline=budget.deadline)
    if fetch_result:
        return {
            **fetch_result,
            "provider_attempts": attempts,
            "provider_notices": _provider_notices(attempts),
            "fallback_used": _fallback_used(attempts),
            "elapsed_ms": _elapsed_ms(start),
        }

    configured_fetch_providers = [
        provider
        for provider in ("tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish", "deepseek")
        if _provider_configured(provider)
    ]
    if not configured_fetch_providers:
        error = "No enabled web_fetch provider is configured"
        if config.tavily_api_key and not config.tavily_enabled:
            error = f"{error}; {_tavily_disabled_message()}"
        error_type = "config_error"
    else:
        # A cooled-down provider still carries the failure that opened it, so a
        # fully skipped chain reports that cause instead of "returned empty".
        failed_attempts = [
            attempt
            for attempt in attempts
            if attempt.get("status") in {"error", "skipped"} and attempt.get("error_type")
        ]
        if failed_attempts:
            last_failure = failed_attempts[-1]
            error_type = str(last_failure.get("error_type") or "network_error")
            error = str(last_failure.get("error") or "All extract providers failed")
        else:
            error = "All extract providers returned empty content"
            error_type = "network_error"
    if any(attempt.get("error_type") == "timeout" for attempt in attempts):
        error_type = "timeout"
    return {
        "ok": False,
        "url": url,
        "provider": "",
        "content": "",
        "error_type": error_type,
        "error": error,
        "provider_attempts": attempts,
        "provider_notices": _provider_notices(attempts),
        "fallback_used": _fallback_used(attempts),
        "elapsed_ms": _elapsed_ms(start),
    }


async def map_site(
    url: str,
    instructions: str = "",
    max_depth: int = 1,
    max_breadth: int = 20,
    limit: int = 50,
    timeout: int = 150,
) -> dict[str, Any]:
    start = time.time()
    result = await call_tavily_map(url, instructions, max_depth, max_breadth, limit, timeout)
    result.setdefault("url", url)
    result.setdefault("elapsed_ms", _elapsed_ms(start))
    return result


async def exa_search(
    query: str,
    num_results: int = 5,
    search_type: str = "neural",
    include_text: bool = False,
    include_highlights: bool = False,
    start_published_date: str = "",
    include_domains: str | list[str] | tuple[str, ...] = "",
    exclude_domains: str | list[str] | tuple[str, ...] = "",
    category: str = "",
) -> dict[str, Any]:
    if disabled := _provider_disabled_result("exa"):
        return disabled
    api_key = config.exa_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": source_message('EXA_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set EXA_API_KEY <key>`。'),
        }

    provider = ExaSearchProvider(config.exa_base_url, api_key, config.exa_timeout)
    include_domain_list = _normalize_domain_filter(include_domains)
    exclude_domain_list = _normalize_domain_filter(exclude_domains)

    activity.progress("provider_request", "exa")
    raw = await provider.search(
        query=query,
        num_results=num_results,
        search_type=search_type,
        include_text=include_text,
        include_highlights=include_highlights,
        start_published_date=start_published_date or None,
        include_domains=include_domain_list,
        exclude_domains=exclude_domain_list,
        category=category or None,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": sanitize_provider_error_message(raw)}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


def _anysearch_provider() -> AnySearchProvider:
    activity.progress("provider_preparing", "anysearch")
    return AnySearchProvider(config.anysearch_api_url, config.anysearch_api_key, config.anysearch_timeout)


def _sciverse_provider() -> SciverseProvider:
    activity.progress("provider_preparing", "sciverse")
    return SciverseProvider(config.sciverse_api_url, config.sciverse_api_token, config.sciverse_timeout)


async def _decode_provider_json(raw: str, provider: str = "anysearch") -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "provider": provider, "error_type": "parse_error", "error": sanitize_provider_error_message(raw)}


def _sciverse_parameter_error(tool: str, error: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "provider": "sciverse",
        "tool": tool,
        "error_type": "parameter_error",
        "error": error,
        "elapsed_ms": 0,
    }
    result.update({key: value for key, value in extra.items() if value not in (None, "")})
    return result


async def anysearch_domains(domain: str = "") -> dict[str, Any]:
    if disabled := _provider_disabled_result("anysearch"):
        return disabled
    return await _decode_provider_json(await _anysearch_provider().get_sub_domains(domain))


async def anysearch_search(
    query: str,
    domain: str = "",
    sub_domain: str = "",
    max_results: int = 5,
    sub_domain_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if disabled := _provider_disabled_result("anysearch"):
        return disabled
    return await _decode_provider_json(
        await _anysearch_provider().vertical_search(
            query=query,
            domain=domain,
            sub_domain=sub_domain,
            max_results=max_results,
            sub_domain_params=sub_domain_params,
        )
    )


async def anysearch_extract(url: str, max_length: int = 20000) -> dict[str, Any]:
    if disabled := _provider_disabled_result("anysearch"):
        return disabled
    return await _decode_provider_json(await _anysearch_provider().extract(url, max_length=max_length))


async def anysearch_batch(queries: list[str], max_results: int = 3) -> dict[str, Any]:
    if disabled := _provider_disabled_result("anysearch"):
        return disabled
    return await _decode_provider_json(await _anysearch_provider().batch_search(queries, max_results=max_results))


async def sciverse_catalog(
    collection: str = "papers",
    include_sample_values: bool = False,
    include_field_stats: bool = False,
) -> dict[str, Any]:
    if disabled := _provider_disabled_result("sciverse"):
        return disabled
    try:
        params = normalize_sciverse_catalog_params(
            collection=collection,
            include_sample_values=include_sample_values,
            include_field_stats=include_field_stats,
        )
    except SciverseParameterError as exc:
        return _sciverse_parameter_error("list_catalog", str(exc))
    return await _decode_provider_json(
        await _sciverse_provider().list_catalog(
            collection="papers",
            **params,
        ),
        provider="sciverse",
    )


async def sciverse_search(
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
    if disabled := _provider_disabled_result("sciverse"):
        return disabled
    try:
        payload = build_sciverse_meta_search_payload(
            query=query,
            collection=collection,
            title_contains=title_contains,
            abstract_contains=abstract_contains,
            authors=authors,
            journals=journals,
            subjects=subjects,
            year_from=year_from,
            year_to=year_to,
            filters_advanced=filters_advanced,
            sort_advanced=sort_advanced,
            sort_by_year=sort_by_year,
            freshness_boost=freshness_boost,
            page=page,
            page_size=page_size,
        )
    except SciverseParameterError as exc:
        return _sciverse_parameter_error("search_papers", str(exc), query=query)
    return await _decode_provider_json(
        await _sciverse_provider().search_papers(**payload),
        provider="sciverse",
    )


async def sciverse_semantic(
    query: str,
    top_k: int = 10,
    retrieval: str = "",
    source_types: list[str] | str | None = None,
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    if disabled := _provider_disabled_result("sciverse"):
        return disabled
    legacy_mode = mode
    if legacy_mode is None and isinstance(retrieval, str) and retrieval.strip().lower() in {"fast", "balanced", "quality"}:
        legacy_mode = retrieval
        retrieval = ""
    try:
        effective_retrieval, warning = normalize_sciverse_retrieval(retrieval, legacy_mode=legacy_mode)
        payload = normalize_sciverse_semantic_payload(
            query=query,
            top_k=top_k,
            retrieval=effective_retrieval,
            source_types=source_types,
        )
    except SciverseParameterError as exc:
        return _sciverse_parameter_error("semantic_search", str(exc), query=query)
    result = await _decode_provider_json(
        await _sciverse_provider().semantic_search(**payload),
        provider="sciverse",
    )
    if warning:
        result["warnings"] = [warning]
    return result


async def sciverse_read(doc_id: str, offset: int = 0, limit: int = 4096) -> dict[str, Any]:
    if disabled := _provider_disabled_result("sciverse"):
        return disabled
    return await _decode_provider_json(
        await _sciverse_provider().read_content(doc_id=doc_id, offset=offset, limit=limit),
        provider="sciverse",
    )


async def sciverse_relations(
    unique_id: str,
    relation: str = "CITATIONS",
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    if disabled := _provider_disabled_result("sciverse"):
        return disabled
    try:
        payload = normalize_sciverse_relations_payload(
            unique_id=unique_id,
            relation=relation,
            page=page,
            page_size=page_size,
        )
    except SciverseParameterError as exc:
        return _sciverse_parameter_error("list_paper_relations", str(exc), unique_id=unique_id, relation=relation)
    return await _decode_provider_json(
        await _sciverse_provider().list_paper_relations(**payload),
        provider="sciverse",
    )


def _zhipu_mcp_search_provider() -> ZhipuMCPProvider:
    activity.progress("provider_preparing", "zhipu-mcp")
    return ZhipuMCPProvider(
        config.zhipu_mcp_search_api_url,
        config.zhipu_mcp_api_key or "",
        config.zhipu_mcp_timeout,
        provider_id="zhipu-mcp",
    )


def _zhipu_mcp_reader_provider() -> ZhipuMCPProvider:
    activity.progress("provider_preparing", "zhipu-mcp-reader")
    return ZhipuMCPProvider(
        config.zhipu_mcp_reader_api_url,
        config.zhipu_mcp_api_key or "",
        config.zhipu_mcp_timeout,
        provider_id="zhipu-mcp-reader",
    )


def _zhipu_mcp_zread_provider() -> ZhipuMCPProvider:
    activity.progress("provider_preparing", "zhipu-mcp-zread")
    return ZhipuMCPProvider(
        config.zhipu_mcp_zread_api_url,
        config.zhipu_mcp_api_key or "",
        config.zhipu_mcp_timeout,
        provider_id="zhipu-mcp-zread",
    )


async def jina_fetch(url: str) -> dict[str, Any]:
    return await call_jina_reader(url)


async def zhipu_mcp_search(query: str, count: int = 5) -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu-mcp"):
        return disabled
    return await _decode_provider_json(await _zhipu_mcp_search_provider().web_search(query, count=count), provider="zhipu-mcp")


async def zhipu_mcp_reader(url: str) -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu-mcp-reader"):
        return disabled
    return await _decode_provider_json(await _zhipu_mcp_reader_provider().web_reader(url), provider="zhipu-mcp-reader")


async def zhipu_mcp_search_doc(repo: str, query: str, max_results: int = 5) -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu-mcp-zread"):
        return disabled
    return await _decode_provider_json(await _zhipu_mcp_zread_provider().search_doc(repo, query, max_results=max_results), provider="zhipu-mcp-zread")


async def zhipu_mcp_repo_structure(repo: str, ref: str = "") -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu-mcp-zread"):
        return disabled
    return await _decode_provider_json(await _zhipu_mcp_zread_provider().get_repo_structure(repo, ref=ref), provider="zhipu-mcp-zread")


async def zhipu_mcp_read_file(repo: str, path: str, ref: str = "") -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu-mcp-zread"):
        return disabled
    return await _decode_provider_json(await _zhipu_mcp_zread_provider().read_file(repo, path, ref=ref), provider="zhipu-mcp-zread")


async def exa_find_similar(url: str, num_results: int = 5) -> dict[str, Any]:
    if disabled := _provider_disabled_result("exa"):
        return disabled
    api_key = config.exa_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": source_message('EXA_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set EXA_API_KEY <key>`。'),
        }

    provider = ExaSearchProvider(config.exa_base_url, api_key, config.exa_timeout)
    activity.progress("provider_request", "exa")
    raw = await provider.find_similar(url=url, num_results=num_results)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": sanitize_provider_error_message(raw)}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def zhipu_search(
    query: str,
    count: int = 10,
    search_engine: str = "",
    search_recency_filter: str = "noLimit",
    search_domain_filter: str = "",
    content_size: str = "medium",
) -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu"):
        return disabled
    api_key = config.zhipu_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": source_message('ZHIPU_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set ZHIPU_API_KEY <key>`。'),
        }
    provider = ZhipuWebSearchProvider(
        config.zhipu_api_url,
        api_key,
        search_engine or config.zhipu_search_engine,
        config.zhipu_timeout,
    )
    activity.progress("provider_request", "zhipu")
    raw = await provider.search(
        query=query,
        count=count,
        search_engine=search_engine or None,
        search_recency_filter=search_recency_filter,
        search_domain_filter=search_domain_filter,
        content_size=content_size,
    )
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": sanitize_provider_error_message(raw)}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def context7_library(name: str, query: str = "") -> dict[str, Any]:
    if disabled := _provider_disabled_result("context7"):
        return disabled
    api_key = config.context7_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": source_message('CONTEXT7_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set CONTEXT7_API_KEY <key>`。'),
        }
    provider = Context7Provider(config.context7_base_url, api_key, config.context7_timeout)
    activity.progress("provider_request", "context7")
    raw = await provider.library(name, query)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": sanitize_provider_error_message(raw)}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def context7_docs(library_id: str, query: str) -> dict[str, Any]:
    if disabled := _provider_disabled_result("context7"):
        return disabled
    api_key = config.context7_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": source_message('CONTEXT7_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set CONTEXT7_API_KEY <key>`。'),
        }
    provider = Context7Provider(config.context7_base_url, api_key, config.context7_timeout)
    activity.progress("provider_request", "context7")
    raw = await provider.docs(library_id, query)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": sanitize_provider_error_message(raw)}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def _test_primary_chat_completion(api_url: str, api_key: str, model: str) -> dict[str, Any]:
    return await _test_openai_compatible_primary(api_url, api_key, model, api_mode="chat-completions")


async def _test_openai_compatible_primary(
    api_url: str,
    api_key: str,
    model: str,
    *,
    api_mode: str,
) -> dict[str, Any]:
    provider = OpenAICompatibleSearchProvider(api_url, api_key, model, stream=False, api_mode=api_mode)
    start = time.time()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            provider._api_endpoint(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            json=provider._build_request_payload("Reply with exactly: ok", "Reply with exactly: ok", stream=False),
        )
        response_time = _elapsed_ms(start)
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200:
            return {
                "status": "warning",
                "message": source_message('HTTP {0}: {1}', response.status_code, sanitize_provider_error_message(response.text, limit=100)),
                "response_time_ms": response_time,
                "http_status": response.status_code,
                "content_type": content_type,
                "has_content": bool(response.text.strip()),
                "api_mode": api_mode,
                "endpoint": provider._api_endpoint(),
            }
        return {
            "status": "ok",
            "message": source_message('{0} endpoint available (HTTP {1})', api_mode, response.status_code),
            "response_time_ms": response_time,
            "http_status": response.status_code,
            "content_type": content_type,
            "has_content": bool(response.text.strip()),
            "api_mode": api_mode,
            "endpoint": provider._api_endpoint(),
        }


def _diagnose_check_result(
    *,
    name: str,
    status: str,
    message: str,
    start: float,
    http_status: int | None = None,
    content_type: str = "",
    has_content: bool = False,
    stream: bool | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "status": status,
        "message": message,
        "response_time_ms": _elapsed_ms(start),
        "has_content": has_content,
    }
    if http_status is not None:
        result["http_status"] = http_status
    if content_type:
        result["content_type"] = content_type
    if stream is not None:
        result["stream"] = stream
    return result


def _openai_compatible_diagnosis(quick: dict[str, Any], no_stream: dict[str, Any], stream: dict[str, Any]) -> tuple[bool, str, str]:
    quick_ok = quick.get("status") == "ok"
    no_stream_ok = no_stream.get("status") == "ok"
    stream_ok = stream.get("status") == "ok"
    search_timeout = no_stream.get("status") == "timeout" or stream.get("status") == "timeout"

    if no_stream_ok and stream_ok:
        return (
            True,
            source_message('OpenAI-compatible 主链路正常。'),
            source_message('真实 search 形态的 stream=false 和 stream=true 都能返回。若用户仍卡住，更可能是调用方、PATH、超时设置或上游偶发波动。'),
        )
    if stream_ok and not no_stream_ok:
        return (
            False,
            source_message('非流式请求不稳定，流式请求可用。'),
            source_message('建议设置 `OPENAI_COMPATIBLE_STREAM=true`，或临时使用 `smart-search search ... --stream`。'),
        )
    if no_stream_ok and not stream_ok:
        return (
            False,
            source_message('流式请求不稳定，非流式请求可用。'),
            source_message('建议设置 `OPENAI_COMPATIBLE_STREAM=false`，或临时使用 `smart-search search ... --no-stream`。'),
        )
    if quick_ok and search_timeout:
        return (
            False,
            source_message('小请求能通，但真实 search 形态超时。'),
            source_message('这通常是上游模型或中转站在处理 smart-search 的完整 prompt 时卡住；建议换模型/中转，或把本诊断报告贴给维护者。'),
        )
    if quick_ok:
        return (
            False,
            source_message('小请求能通，但真实 search 形态失败。'),
            source_message('这更像上游模型/中转站对 smart-search 请求形态不兼容；建议换模型/中转，或把本诊断报告贴给维护者。'),
        )
    return (
        False,
        source_message('OpenAI-compatible 基础请求不可用。'),
        source_message('请先检查 API URL、API key、模型名和网络；修好后再运行本诊断命令。'),
    )


async def _probe_openai_compatible_search_shape(
    api_url: str,
    api_key: str,
    model: str,
    *,
    stream: bool,
    timeout_seconds: float,
    api_mode: str = "chat-completions",
) -> dict[str, Any]:
    name = f"真实 {api_mode} search 请求 (stream={'true' if stream else 'false'})"
    start = time.time()
    provider = OpenAICompatibleSearchProvider(api_url, api_key, model, stream=stream, api_mode=api_mode)
    payload = provider._build_request_payload(search_prompt, get_local_time_info() + "\nping", stream=stream)
    headers = provider._build_api_headers()
    headers["User-Agent"] = "smart-search/diagnose"
    timeout = httpx.Timeout(connect=6.0, read=timeout_seconds, write=10.0, pool=None)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=config.ssl_verify_enabled) as client:
            if stream:
                async with client.stream(
                    "POST",
                    provider._api_endpoint(),
                    headers=headers,
                    json=payload,
                ) as response:
                    content_type = response.headers.get("content-type", "")
                    if response.status_code >= 400:
                        await response.aread()
                    response.raise_for_status()
                    content = await provider._parse_streaming_response(response)
                    has_content = bool(content.strip())
                    status = "ok" if has_content else "empty"
                    message = f"HTTP {response.status_code}; {'收到流式内容' if has_content else '未收到内容'}"
                    return _diagnose_check_result(
                        name=name,
                        status=status,
                        message=message,
                        start=start,
                        http_status=response.status_code,
                        content_type=content_type,
                        has_content=has_content,
                        stream=stream,
                    )

            response = await client.post(
                provider._api_endpoint(),
                headers=headers,
                json=payload,
            )
            content_type = response.headers.get("content-type", "")
            response.raise_for_status()
            content = await provider._parse_completion_response(response)
            has_content = bool(content.strip())
            status = "ok" if has_content else "empty"
            message = f"HTTP {response.status_code}; {'收到内容' if has_content else '返回为空'}"
            return _diagnose_check_result(
                name=name,
                status=status,
                message=message,
                start=start,
                http_status=response.status_code,
                content_type=content_type,
                has_content=has_content,
                stream=stream,
            )
    except httpx.TimeoutException as e:
        return _diagnose_check_result(
            name=name,
            status="timeout",
            message=f"请求超时: {sanitize_provider_error_message(e)}",
            start=start,
            stream=stream,
        )
    except httpx.HTTPStatusError as e:
        body = sanitize_provider_error_message(e.response.text if e.response is not None else e, limit=200)
        status_code = e.response.status_code if e.response is not None else None
        content_type = e.response.headers.get("content-type", "") if e.response is not None else ""
        return _diagnose_check_result(
            name=name,
            status="warning",
            message=f"HTTP {status_code}: {body}",
            start=start,
            http_status=status_code,
            content_type=content_type,
            stream=stream,
        )
    except httpx.RequestError as e:
        return _diagnose_check_result(
            name=name,
            status="error",
            message=f"网络错误: {sanitize_provider_error_message(e)}",
            start=start,
            stream=stream,
        )
    except Exception as e:
        return _diagnose_check_result(
            name=name,
            status="error",
            message=f"运行错误: {sanitize_provider_error_message(e)}",
            start=start,
            stream=stream,
        )


async def _probe_openai_compatible_web_search(
    api_url: str,
    api_key: str,
    model: str,
    *,
    api_mode: str,
    stream: bool,
    timeout_seconds: float,
) -> dict:
    name = "联网搜索能力"
    start = time.time()
    provider = OpenAICompatibleSearchProvider(api_url, api_key, model, stream=stream, api_mode=api_mode)
    answer = ""
    try:
        content = await asyncio.wait_for(provider.search("What is the latest stable Python release? Cite the source URL."), timeout_seconds)
        answer, sources = split_answer_and_sources(content or "")
        problem = model_answer_problem(answer, sources)
        if problem:
            status, message = "warning", f"{problem[1]}（{problem[0]}）"
        else:
            status, message = "ok", f"返回 {len(sources) or len(extract_unique_urls(answer))} 个来源"
    except asyncio.TimeoutError:
        status, message = "timeout", f"请求超时（{timeout_seconds:g} 秒）"
    except Exception as e:
        status, message = "error", f"运行错误: {sanitize_provider_error_message(e)}"
    return _diagnose_check_result(
        name=name, status=status, message=message, start=start, has_content=bool(answer.strip()), stream=stream,
    )


async def diagnose_openai_compatible(timeout_seconds: float = 30.0) -> dict[str, Any]:
    if disabled := _provider_disabled_result("openai-compatible"):
        return disabled
    start = time.time()
    api_url = config.openai_compatible_api_url
    api_key = config.openai_compatible_api_key
    model = config.openai_compatible_model
    info = config.config_path_info()
    try:
        api_mode = config.openai_compatible_api_mode
    except ValueError as e:
        return {
            "ok": False,
            "provider": "openai-compatible",
            "api_url": api_url or "未配置",
            "api_key": config._mask_api_key(api_key) if api_key else "未配置",
            "model": model,
            "configured_api_mode": "invalid",
            "configured_stream": config.openai_compatible_stream,
            "timeout_seconds": timeout_seconds,
            "config_file": info.get("config_file", ""),
            "config_dir_source": info.get("config_dir_source", ""),
            "checks": [],
            "next_command": OPENAI_COMPATIBLE_DIAGNOSE_COMMAND,
            "error_type": "parameter_error",
            "error": str(e),
            "summary": source_message('OpenAI-compatible API mode is invalid.'),
            "recommendation": source_message('Set OPENAI_COMPATIBLE_API_MODE to chat-completions or responses.'),
            "elapsed_ms": _elapsed_ms(start),
        }
    endpoint = openai_compatible_endpoint(api_url or "", api_mode)
    result: dict[str, Any] = {
        "ok": False,
        "provider": "openai-compatible",
        "api_url": api_url or "未配置",
        "api_key": config._mask_api_key(api_key) if api_key else "未配置",
        "model": model,
        "configured_api_mode": api_mode,
        "endpoint": endpoint if api_url else "",
        "configured_stream": config.openai_compatible_stream,
        "timeout_seconds": timeout_seconds,
        "config_file": info.get("config_file", ""),
        "config_dir_source": info.get("config_dir_source", ""),
        "checks": [],
        "next_command": OPENAI_COMPATIBLE_DIAGNOSE_COMMAND,
    }
    missing = []
    if not api_url:
        missing.append("OPENAI_COMPATIBLE_API_URL")
    if not api_key:
        missing.append("OPENAI_COMPATIBLE_API_KEY")
    if missing:
        result.update(
            {
                "error_type": "config_error",
                "error": source_message('缺少 OpenAI-compatible 配置: {0}', ", ".join(missing)),
                "summary": source_message('OpenAI-compatible 配置不完整。'),
                "recommendation": source_message('请先运行 `smart-search setup`，或用 `smart-search config set` 填好缺失项。'),
                "missing": missing,
                "elapsed_ms": _elapsed_ms(start),
            }
        )
        return result

    try:
        quick = (
            await _test_primary_chat_completion(api_url, api_key, model)
            if api_mode == "chat-completions"
            else await _test_openai_compatible_primary(api_url, api_key, model, api_mode=api_mode)
        )
    except httpx.TimeoutException as e:
        quick = {"status": "timeout", "message": source_message('轻量 {0} 请求超时: {1}', api_mode, sanitize_provider_error_message(e))}
    except httpx.RequestError as e:
        quick = {"status": "error", "message": source_message('轻量 {0} 网络错误: {1}', api_mode, sanitize_provider_error_message(e))}
    except Exception as e:
        quick = {"status": "error", "message": source_message('轻量 {0} 运行错误: {1}', api_mode, sanitize_provider_error_message(e))}
    quick_check = {
        "name": f"轻量 {api_mode} 请求",
        "status": quick.get("status", "error"),
        "message": quick.get("message", ""),
        "response_time_ms": quick.get("response_time_ms"),
        "http_status": quick.get("http_status"),
        "content_type": quick.get("content_type", ""),
        "has_content": bool(quick.get("has_content", quick.get("status") == "ok")),
    }
    result["checks"].append(quick_check)
    probe_kwargs = {"stream": False, "timeout_seconds": timeout_seconds}
    if api_mode != "chat-completions":
        probe_kwargs["api_mode"] = api_mode
    no_stream = await _probe_openai_compatible_search_shape(api_url, api_key, model, **probe_kwargs)
    result["checks"].append(no_stream)
    probe_kwargs = {"stream": True, "timeout_seconds": timeout_seconds}
    if api_mode != "chat-completions":
        probe_kwargs["api_mode"] = api_mode
    stream = await _probe_openai_compatible_search_shape(api_url, api_key, model, **probe_kwargs)
    result["checks"].append(stream)
    web = await _probe_openai_compatible_web_search(api_url, api_key, model, api_mode=api_mode,
                                                   stream=config.openai_compatible_stream, timeout_seconds=timeout_seconds)
    result["checks"].append(web)
    result["web_search_capable"] = web["status"] == "ok"

    available_models: list[str] = []
    try:
        available_models = await fetch_available_models(api_url, api_key)
    except Exception:
        available_models = []
    inventory = _openai_fallback_model_inventory(
        config.openai_compatible_fallback_models,
        available_models,
        primary_model=model,
    )
    result["checks"].append(
        {
            "name": "兜底模型清单",
            "status": inventory["status"],
            "message": inventory["message"],
            "response_time_ms": None,
            "http_status": None,
            "content_type": "",
            "has_content": False,
        }
    )
    result["fallback_model_inventory"] = inventory
    result["timeout_policy"] = OPENAI_COMPATIBLE_TIMEOUT_POLICY

    ok, summary, recommendation = _openai_compatible_diagnosis(quick_check, no_stream, stream)
    if web["status"] != "ok":
        recommendation = source_message('{0} 另外，联网搜索能力检查未通过：{1}。OpenAI-compatible 不会发送搜索工具；如果该模型只能通过 Responses 的 web_search 工具联网，请把 XAI_API_URL、XAI_API_KEY、XAI_MODEL 指向支持 /v1/responses 的中转站。', recommendation, web['message'])
    if inventory.get("status") == "warning":
        recommendation = source_message('{0} 另外，{1}。兜底只在主模型硬失败后接力，不会再把主模型砍成 30 秒。', recommendation, inventory['message'])
    result.update(
        {
            "ok": ok,
            "error_type": "" if ok else "network_error",
            "error": "" if ok else summary,
            "summary": summary,
            "recommendation": recommendation,
            "elapsed_ms": _elapsed_ms(start),
        }
    )
    return result


async def _test_primary_connection(
    api_url: str,
    api_key: str,
    model: str,
    *,
    api_mode: str = "chat-completions",
) -> dict[str, Any]:
    completion_test = await _test_openai_compatible_primary(api_url, api_key, model, api_mode=api_mode)
    completion_label = "聊天接口" if api_mode == "chat-completions" else "Responses 接口"
    completion_key = "chat_completion_test" if api_mode == "chat-completions" else "responses_test"

    models_url = f"{normalize_openai_compatible_api_url(api_url)}/models"
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            response_time = _elapsed_ms(start)
            if response.status_code != 200:
                models_test = {
                    "status": "warning",
                    "message": source_message('HTTP {0}: {1}', response.status_code, sanitize_provider_error_message(response.text, limit=100)),
                    "response_time_ms": response_time,
                }
            else:
                models_test = {"status": "ok", "message": source_message('成功获取模型列表 (HTTP {0})', response.status_code), "response_time_ms": response_time}
                try:
                    models_data = response.json()
                    model_names = [m["id"] for m in models_data.get("data", []) if isinstance(m, dict) and "id" in m]
                    models_test["message"] += f"，共 {len(model_names)} 个模型"
                    if model_names:
                        models_test["available_models"] = model_names
                except Exception:
                    pass
    except httpx.HTTPError as e:
        models_test = {
            "status": "warning",
            "message": source_message('模型列表接口请求失败: {0}', sanitize_provider_error_message(e)),
            "response_time_ms": _elapsed_ms(start),
        }

    if completion_test.get("status") != "ok":
        models_state = "可用" if models_test.get("status") == "ok" else "不可用"
        result = {
            "status": "warning",
            "message": source_message('{0}不可用: {1}；模型列表接口{2}: {3}', completion_label, completion_test.get('message', ''), models_state, models_test['message']),
            "response_time_ms": completion_test.get("response_time_ms", models_test.get("response_time_ms")),
            "models_endpoint_test": models_test,
            "completion_test": completion_test,
            "api_mode": api_mode,
        }
        result[completion_key] = completion_test
        return result

    if models_test.get("status") != "ok":
        result = {
            "status": "ok",
            "message": source_message('{0}；模型列表接口不可用: {1}', completion_test['message'], models_test['message']),
            "response_time_ms": completion_test.get("response_time_ms"),
            "models_endpoint_test": models_test,
            "completion_test": completion_test,
            "api_mode": api_mode,
        }
        result[completion_key] = completion_test
        return result

    result: dict[str, Any] = {
        "status": "ok",
        "message": f"{completion_test['message']}；{models_test['message']}",
        "response_time_ms": completion_test.get("response_time_ms"),
        "models_endpoint_test": models_test,
        "completion_test": completion_test,
        "api_mode": api_mode,
    }
    result[completion_key] = completion_test
    if "available_models" in models_test:
        result["available_models"] = models_test["available_models"]
    return result


async def _test_primary_responses(provider: XAIResponsesSearchProvider) -> dict[str, Any]:
    start = time.time()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"{provider.api_url}/responses",
            headers={"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"},
            # Same transport and reasoning as a search, but no tools, so a test never runs a billed search.
            json={
                "model": provider.model,
                "input": [{"role": "user", "content": "Reply with exactly: ok"}],
                **provider.request_options(),
            },
        )
        response_time = _elapsed_ms(start)
        if response.status_code != 200:
            return {
                "status": "warning",
                "message": source_message('HTTP {0}: {1}', response.status_code, sanitize_provider_error_message(response.text, limit=100)),
                "response_time_ms": response_time,
            }
        # A stream can still fail after HTTP 200, so read it the way a search does.
        if provider.stream and not await provider.parse_stream(response):
            return {"status": "warning", "message": source_message('xAI Responses 流式响应没有返回文本'), "response_time_ms": response_time}
        return {"status": "ok", "message": source_message('xAI Responses API 可用 (HTTP {0})', response.status_code), "response_time_ms": response_time}


async def _test_main_provider_connection(provider_config: dict[str, Any]) -> dict[str, Any]:
    if provider_config["mode"] == "xai-responses":
        return await _test_primary_responses(_main_search_providers([provider_config], fallback="off")[0])
    api_mode = provider_config.get("api_mode", provider_config.get("mode", "chat-completions"))
    if api_mode == "chat-completions":
        return await _test_primary_connection(provider_config["api_url"], provider_config["api_key"], provider_config["model"])
    return await _test_primary_connection(
        provider_config["api_url"],
        provider_config["api_key"],
        provider_config["model"],
        api_mode=api_mode,
    )


async def _safe_test_main_provider_connection(provider_config: dict[str, Any]) -> dict[str, Any]:
    try:
        result = await _test_main_provider_connection(provider_config)
    except httpx.TimeoutException:
        result = {"status": "timeout", "message": source_message('{0} 请求超时，请检查网络连接或 API URL', provider_config['provider'])}
    except httpx.RequestError as e:
        result = {
            "status": "error",
            "message": source_message('{0} 网络错误: {1}', provider_config['provider'], sanitize_provider_error_message(e)),
        }
    except Exception as e:
        result = {
            "status": "error",
            "message": source_message('{0} 未知错误: {1}', provider_config['provider'], sanitize_provider_error_message(e)),
        }
    if provider_config["mode"] == "xai-responses":
        # Name what the test sent in every outcome, so it can be compared with a real search.
        effort, stream = provider_config.get("reasoning_effort", ""), bool(provider_config.get("stream"))
        result["sent"] = {"reasoning_effort": effort, "stream": stream, "tools": []}
        sent = ", ".join(([f"reasoning.effort={effort}"] if effort else []) + [f"stream={str(stream).lower()}", "tools=[]"])
        result["message"] = source_message('{0}（本次发送：{1}）', result["message"], sent)
    return result


async def _test_exa_connection() -> dict[str, Any]:
    if disabled := _provider_disabled_result("exa"):
        return disabled
    exa_key = config.exa_api_key
    if not exa_key:
        return {"status": "not_configured", "message": source_message('EXA_API_KEY 未设置，Exa 搜索功能不可用')}
    start = time.time()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{config.exa_base_url.rstrip('/')}/search",
            headers={"x-api-key": exa_key, "content-type": "application/json"},
            json={"query": "test", "numResults": 1, "type": "keyword"},
        )
        response_time = _elapsed_ms(start)
        if resp.status_code == 200:
            return {"status": "ok", "message": source_message('Exa API 可用 (HTTP 200)'), "response_time_ms": response_time}
        return {
            "status": "warning",
            "message": source_message('HTTP {0}: {1}', resp.status_code, sanitize_provider_error_message(resp.text, limit=100)),
            "response_time_ms": response_time,
        }


async def _test_tavily_connection() -> dict[str, Any]:
    if not config.tavily_enabled:
        return {"status": "disabled", "message": _tavily_disabled_message()}
    tavily_key = config.tavily_api_key
    if not tavily_key:
        return {"status": "not_configured", "message": source_message('TAVILY_API_KEY 未设置，Tavily 功能不可用')}
    start = time.time()
    timeout = httpx.Timeout(connect=6.0, read=config.tavily_timeout, write=10.0, pool=None)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=config.ssl_verify_enabled) as client:
        resp = await client.post(
            f"{config.tavily_api_url.rstrip('/')}/search",
            headers={"Authorization": f"Bearer {tavily_key}", "Content-Type": "application/json"},
            json={"query": "test", "max_results": 1, "search_depth": "basic"},
        )
        response_time = _elapsed_ms(start)
        if resp.status_code == 200:
            return {"status": "ok", "message": source_message('Tavily API 可用 (HTTP 200)'), "response_time_ms": response_time}
        return {
            "status": "warning",
            "message": source_message('HTTP {0}: {1}', resp.status_code, sanitize_provider_error_message(resp.text, limit=100)),
            "response_time_ms": response_time,
        }


async def _test_jina_connection() -> dict[str, Any]:
    if disabled := _provider_disabled_result("jina"):
        return disabled
    if config.jina_respond_with and not config.jina_api_key:
        return {"status": "config_error", "message": source_message('JINA_RESPOND_WITH requires JINA_API_KEY')}
    if not config.jina_api_key:
        return {"status": "not_configured", "message": source_message('JINA_API_KEY 未设置，Jina 不满足 standard web_fetch；匿名 Reader 只能作为显式实验使用')}
    start = time.time()
    data = await jina_fetch("https://example.com")
    response_time = _elapsed_ms(start)
    if data.get("ok"):
        return {"status": "ok", "message": source_message('Jina Reader 可用'), "response_time_ms": response_time}
    error_type = data.get("error_type", "")
    status = error_type if error_type in {"auth_error", "config_error", "parameter_error", "rate_limited", "timeout"} else "warning"
    return {"status": status, "message": data.get("error", source_message('Jina Reader 不可用')), "response_time_ms": response_time}


async def _test_zhipu_connection() -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu"):
        return disabled
    if not config.zhipu_api_key:
        return {"status": "not_configured", "message": source_message('ZHIPU_API_KEY 未设置，智谱搜索功能不可用')}
    result = await zhipu_search("test", count=1)
    if result.get("ok"):
        return {"status": "ok", "message": source_message('智谱 Web Search 可用'), "response_time_ms": result.get("elapsed_ms", 0)}
    return {"status": "warning", "message": result.get("error", source_message('智谱 Web Search 不可用')), "response_time_ms": result.get("elapsed_ms", 0)}


async def _test_zhipu_mcp_connection() -> dict[str, Any]:
    if disabled := _provider_disabled_result("zhipu-mcp"):
        return disabled
    if not config.zhipu_mcp_api_key:
        return {"status": "not_configured", "message": source_message('ZHIPU_MCP_API_KEY 未设置，智谱 Coding Plan MCP 功能不可用')}
    result = await zhipu_mcp_search("test", count=1)
    if result.get("ok"):
        return {"status": "ok", "message": source_message('智谱 Coding Plan MCP 可用'), "response_time_ms": result.get("elapsed_ms", 0)}
    error_type = result.get("error_type", "")
    status = error_type if error_type in {"auth_error", "config_error", "provider_error", "rate_limited", "timeout"} else "warning"
    return {"status": status, "message": result.get("error", source_message('智谱 Coding Plan MCP 不可用')), "response_time_ms": result.get("elapsed_ms", 0)}


async def _test_context7_connection() -> dict[str, Any]:
    if disabled := _provider_disabled_result("context7"):
        return disabled
    if not config.context7_api_key:
        return {"status": "not_configured", "message": source_message('CONTEXT7_API_KEY 未设置，Context7 功能不可用')}
    result = await context7_library("react", "hooks")
    if result.get("ok"):
        return {"status": "ok", "message": source_message('Context7 API 可用'), "response_time_ms": result.get("elapsed_ms", 0)}
    return {"status": "warning", "message": result.get("error", source_message('Context7 API 不可用')), "response_time_ms": result.get("elapsed_ms", 0)}


async def _test_anysearch_connection() -> dict[str, Any]:
    """Probe AnySearch with a domain listing, which costs no search quota."""
    if disabled := _provider_disabled_result("anysearch"):
        return disabled
    if not config.anysearch_api_key:
        return {"status": "not_configured", "message": source_message('ANYSEARCH_API_KEY 未设置，AnySearch 垂直搜索不可用')}
    start = time.time()
    result = await anysearch_domains()
    response_time = result.get("elapsed_ms") or _elapsed_ms(start)
    if result.get("ok"):
        return {"status": "ok", "message": source_message('AnySearch API 可用'), "response_time_ms": response_time}
    error_type = str(result.get("error_type") or "")
    status = error_type if error_type in APPROVED_PROVIDER_ERROR_TYPES else "warning"
    return {"status": status, "message": result.get("error", source_message('AnySearch API 不可用')), "response_time_ms": response_time}


async def _test_sciverse_connection() -> dict[str, Any]:
    """Probe Sciverse with a catalog listing, which costs no search quota."""
    if disabled := _provider_disabled_result("sciverse"):
        return disabled
    if not config.sciverse_api_token:
        return {"status": "not_configured", "message": source_message('SCIVERSE_API_TOKEN 未设置，Sciverse 学术检索不可用')}
    start = time.time()
    result = await sciverse_catalog()
    response_time = result.get("elapsed_ms") or _elapsed_ms(start)
    if result.get("ok"):
        return {"status": "ok", "message": source_message('Sciverse API 可用'), "response_time_ms": response_time}
    error_type = str(result.get("error_type") or "")
    status = error_type if error_type in APPROVED_PROVIDER_ERROR_TYPES else "warning"
    return {"status": status, "message": result.get("error", source_message('Sciverse API 不可用')), "response_time_ms": response_time}


async def _test_firecrawl_presence() -> dict[str, Any]:
    """The current Firecrawl probe checks presence, without authenticating the key.

    Reported as `probe: presence` so callers can render "key present, unverified"
    instead of a green tick they have not earned.
    """
    if disabled := _provider_disabled_result("firecrawl"):
        return disabled
    if not config.firecrawl_api_key:
        return {"status": "not_configured", "message": source_message('FIRECRAWL_API_KEY 未设置，Firecrawl 功能不可用')}
    return {"status": "configured", "message": source_message('FIRECRAWL_API_KEY 已配置（未发起真实请求验证）')}


async def _test_tinyfish_connection() -> dict[str, Any]:
    if disabled := _provider_disabled_result("tinyfish"):
        return disabled
    if not config.tinyfish_api_key:
        return {"status": "not_configured", "message": source_message('TINYFISH_API_KEY 未设置，TinyFish 功能不可用')}
    start = time.time()
    raw_results = await asyncio.gather(
        TinyFishSearchProvider(config.tinyfish_search_api_url, config.tinyfish_api_key, config.tinyfish_timeout)
        .search("tinyfish connectivity check", max_results=1),
        TinyFishFetchProvider(config.tinyfish_fetch_api_url, config.tinyfish_api_key, config.tinyfish_timeout)
        .fetch("https://example.com"),
    )
    # Both endpoints share one health fingerprint; search alone cannot clear a
    # fetch failure. The caller controls the total probe deadline and persistence.
    for label, raw in zip(("搜索", "抓取"), raw_results):
        data = json.loads(raw)
        if not data.get("ok"):
            error_type = str(data.get("error_type") or "")
            status = error_type if error_type in APPROVED_PROVIDER_ERROR_TYPES else "warning"
            return {"status": status, "message": source_message('TinyFish {0}：{1}', label, data.get('error', '请求未成功')),
                    "response_time_ms": _elapsed_ms(start)}
    return {"status": "ok", "message": source_message('TinyFish 搜索与抓取 API 均可用'), "response_time_ms": _elapsed_ms(start)}


async def _test_deepseek_connection() -> dict[str, Any]:
    """Probe search and fetch once each; DeepSeek bills every successful request."""
    if disabled := _provider_disabled_result("deepseek"):
        return disabled
    if not config.deepseek_api_key:
        return {"status": "not_configured", "message": source_message('DEEPSEEK_API_KEY 未设置，DeepSeek 搜索与抓取不可用')}
    start = time.time()
    provider = _deepseek_provider()
    search_result, fetch_result = await asyncio.gather(
        provider.search("DeepSeek", max_results=1),
        provider.fetch("https://example.com"),
        return_exceptions=True,
    )
    # Both tools share one key and one health fingerprint, so either failing fails the probe.
    failed = search_result if isinstance(search_result, Exception) else fetch_result
    if isinstance(failed, Exception):
        error_type, error = classify_provider_exception(failed, additional_secrets=(config.deepseek_api_key,))
        status = error_type if error_type in APPROVED_PROVIDER_ERROR_TYPES else "warning"
        message = (source_message('DeepSeek search: {0}', error) if failed is search_result
                   else source_message('DeepSeek fetch: {0}', error))
        return {"status": status, "message": message, "response_time_ms": _elapsed_ms(start)}
    if fetch_result is None:
        return {"status": "warning", "message": source_message('DeepSeek fetch returned no content for {0}', "https://example.com"),
                "response_time_ms": _elapsed_ms(start)}
    return {"status": "ok", "message": source_message('DeepSeek 搜索与抓取 API 均可用'), "response_time_ms": _elapsed_ms(start)}


DOCTOR_PROBE_PROVIDERS = {
    "exa_connection_test": "exa",
    "tavily_connection_test": "tavily",
    "jina_connection_test": "jina",
    "zhipu_connection_test": "zhipu",
    "zhipu_mcp_connection_test": "zhipu-mcp",
    "context7_connection_test": "context7",
    "tinyfish_connection_test": "tinyfish",
    "deepseek_connection_test": "deepseek",
}
DOCTOR_PROBE_NEUTRAL_STATUSES = {"not_configured", "configured", "skipped", "disabled"}


def _record_probe_result(provider: str, test: dict[str, Any]) -> None:
    """Fold one connection-test result into the persistent cooldown store.

    Shared by `doctor` and by the single-provider dispatcher, so testing a key
    anywhere is a first-class recovery path for a cooled-down provider.
    """
    if not isinstance(test, dict):
        return
    status = str(test.get("status") or "")
    if status in DOCTOR_PROBE_NEUTRAL_STATUSES:
        return
    if status == "ok":
        _record_provider_result(provider, "ok")
        return
    error_type = status if status in APPROVED_PROVIDER_ERROR_TYPES or status == "config_error" else "provider_error"
    _record_provider_result(provider, "error", error_type, str(test.get("message") or ""))


def _record_doctor_probes(info: dict[str, Any]) -> None:
    """Let `doctor` double as the recovery path for a cooled-down provider."""
    for key, provider in DOCTOR_PROBE_PROVIDERS.items():
        _record_probe_result(provider, info.get(key))


PROBE_TIMEOUT_CEILING = 20.0
# How each provider id can be checked. "main" goes through the main-search provider
# configs (which accept a dict, so unsaved candidate credentials work); "live" is a
# real request; "shared:<id>" reuses another provider's probe because they share a
# credential; "presence" only reports that a key is set.
PROBE_KIND: dict[str, str] = {
    "xai-responses": "main",
    "openai-compatible": "main",
    "exa": "live",
    "tavily": "live",
    "jina": "live",
    "zhipu": "live",
    "zhipu-mcp": "live",
    "context7": "live",
    "tinyfish": "live",
    "deepseek": "live",
    "anysearch": "live",
    "sciverse": "live",
    "zhipu-mcp-reader": "shared:zhipu-mcp",
    "firecrawl": "presence",
}
_LIVE_PROBES: dict[str, Any] = {
    "exa": _test_exa_connection,
    "tavily": _test_tavily_connection,
    "jina": _test_jina_connection,
    "zhipu": _test_zhipu_connection,
    "zhipu-mcp": _test_zhipu_mcp_connection,
    "context7": _test_context7_connection,
    "tinyfish": _test_tinyfish_connection,
    "deepseek": _test_deepseek_connection,
    "anysearch": _test_anysearch_connection,
    "sciverse": _test_sciverse_connection,
    "firecrawl": _test_firecrawl_presence,
}


async def test_provider_connection(
    provider: str,
    *,
    overrides: dict[str, str] | None = None,
    record_health: bool | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """Check one provider's credentials without firing every probe `doctor` runs.

    `overrides` tests candidate settings in an isolated snapshot for any provider. Health is
    not recorded for an override run: a success would clear a real cooldown under a
    fingerprint that does not match what is stored, and a failure would cool down a
    key that is actually fine.
    """
    if overrides is not None:
        try:
            normalized = {str(key).strip().upper(): str(value) for key, value in overrides.items()}
            for key, value in normalized.items():
                if key not in config._CONFIG_KEYS:
                    raise ValueError(source_message('Unsupported config key: {0}', key))
                config._validate_config_value(key, value)
            with config.snapshot(normalized):
                return await test_provider_connection(provider, record_health=False, timeout_seconds=timeout_seconds)
        except ValueError as error:
            return {"ok": False, "provider": provider, "status": "parameter_error", "error_type": "parameter_error",
                    "message": str(error), "error": str(error), "recorded_as": "", "probe": "none"}
    provider = (provider or "").strip().lower()
    kind = PROBE_KIND.get(provider)
    if kind is None:
        known = ", ".join(sorted(PROBE_KIND))
        message = source_message('Unknown provider: {0}. Known providers: {1}', provider, known)
        return {
            "ok": False,
            "provider": provider,
            "status": "parameter_error",
            "message": message,
            "response_time_ms": 0,
            "probe": "none",
            "recorded_as": "",
            "error_type": "parameter_error",
            "error": message,
            "known_providers": sorted(PROBE_KIND),
        }
    if disabled := _provider_disabled_result(provider):
        return {**disabled, "response_time_ms": 0, "probe": "none", "recorded_as": ""}
    if record_health is None:
        record_health = not overrides
    ceiling = timeout_seconds if timeout_seconds and timeout_seconds > 0 else PROBE_TIMEOUT_CEILING

    recorded_as = provider
    probe_label = kind
    probe_model = ""
    if kind.startswith("shared:"):
        recorded_as = kind.split(":", 1)[1]
        probe_label = "shared"

    async def _run() -> dict[str, Any]:
        nonlocal probe_model
        if kind == "main":
            if overrides:
                provider_config = _main_search_override_config(provider, overrides)
                if provider_config is None:
                    return {"status": "config_error", "message": source_message('{0} 覆盖参数不完整', provider)}
            else:
                configs = _main_search_provider_configs(providers=provider)
                if not configs:
                    return {"status": "not_configured", "message": source_message('{0} 未配置', provider)}
                provider_config = configs[0]
            probe_model = str(provider_config.get("model", ""))
            activity.progress("provider.test", provider, probe_model)
            return await _safe_test_main_provider_connection(provider_config)
        probe = _LIVE_PROBES.get(recorded_as)
        if probe is None:
            return {"status": "not_configured", "message": source_message('{0} 无可用探针', provider)}
        return await probe()

    start = time.time()
    try:
        test = await asyncio.wait_for(_run(), timeout=ceiling)
    except asyncio.TimeoutError:
        test = {
            "status": "timeout",
            "message": source_message('{0} 探测超过 {1:g}s 上限', provider, ceiling),
            "response_time_ms": _elapsed_ms(start),
        }
    except Exception as e:
        test = {
            "status": "error",
            "message": source_message('{0} 探测失败: {1}', provider, sanitize_provider_error_message(e)),
            "response_time_ms": _elapsed_ms(start),
        }

    if record_health and recorded_as in PROVIDER_CREDENTIAL_SOURCES:
        _record_probe_result(recorded_as, test)

    status = str(test.get("status") or "")
    result = {
        "ok": status == "ok",
        "provider": provider,
        "model": probe_model,
        "status": status,
        "message": str(test.get("message") or ""),
        "response_time_ms": test.get("response_time_ms", _elapsed_ms(start)),
        "probe": probe_label,
        "recorded_as": recorded_as if record_health else "",
        "error_type": "" if status == "ok" else (status if status in APPROVED_PROVIDER_ERROR_TYPES else ""),
        "error": "" if status == "ok" else str(test.get("message") or ""),
        "health": _provider_health_status(recorded_as),
    }
    if "sent" in test:
        result["sent"] = test["sent"]
    if probe_label == "shared":
        result["message"] = (
            f"{result['message']} (与 {recorded_as} 共用同一组凭据)" if result["message"] else f"与 {recorded_as} 共用同一组凭据"
        )
    return result


def _main_search_override_config(provider: str, overrides: dict[str, str]) -> dict[str, Any] | None:
    """Build a main-search provider config from unsaved form values."""
    get = lambda key, fallback="": str(overrides.get(key) or fallback).strip()  # noqa: E731
    if provider == "xai-responses":
        api_key = get("XAI_API_KEY", config.xai_api_key)
        if not api_key:
            return None
        return {
            "provider": "xai-responses",
            "mode": "xai-responses",
            "api_url": get("XAI_API_URL", config.xai_api_url),
            "api_key": api_key,
            "model": get("XAI_MODEL", config.xai_model),
        }
    api_url = get("OPENAI_COMPATIBLE_API_URL", config.openai_compatible_api_url)
    api_key = get("OPENAI_COMPATIBLE_API_KEY", config.openai_compatible_api_key)
    if not api_url or not api_key:
        return None
    return {
        "provider": "openai-compatible",
        "mode": "openai-compatible",
        "api_url": api_url,
        "api_key": api_key,
        "model": get("OPENAI_COMPATIBLE_MODEL", config.openai_compatible_model),
        "api_mode": get("OPENAI_COMPATIBLE_API_MODE", config.openai_compatible_api_mode),
    }


async def doctor() -> dict[str, Any]:
    info = config.get_config_info()

    main_provider_configs: list[dict[str, Any]] = []
    try:
        main_provider_configs = _main_search_provider_configs()
        info["main_search_connection_tests"] = {}
        for provider_config in main_provider_configs:
            info["main_search_connection_tests"][provider_config["provider"]] = await _safe_test_main_provider_connection(provider_config)
        openai_provider_config = next(
            (item for item in main_provider_configs if item["provider"] == "openai-compatible"),
            None,
        )
        if openai_provider_config:
            info["openai_compatible_endpoint"] = openai_compatible_endpoint(
                openai_provider_config["api_url"],
                openai_provider_config.get("api_mode", openai_provider_config["mode"]),
            )
        if main_provider_configs:
            first_provider = main_provider_configs[0]
            info["primary_api_mode"] = first_provider["mode"]
            info["primary_connection_test"] = info["main_search_connection_tests"][first_provider["provider"]]
        else:
            info["primary_connection_test"] = {"status": "config_error", "message": MINIMUM_PROFILE_ERROR}
    except ValueError as e:
        info["main_search_connection_tests"] = {}
        info["primary_connection_test"] = {"status": "config_error", "message": sanitize_provider_error_message(e)}
    except Exception as e:
        info["main_search_connection_tests"] = {}
        info["primary_connection_test"] = {"status": "error", "message": source_message('未知错误: {0}', sanitize_provider_error_message(e))}

    try:
        info["exa_connection_test"] = await _test_exa_connection()
    except httpx.TimeoutException:
        info["exa_connection_test"] = {"status": "timeout", "message": source_message('Exa API 请求超时')}
    except Exception as e:
        info["exa_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    try:
        info["tavily_connection_test"] = await _test_tavily_connection()
    except httpx.TimeoutException:
        info["tavily_connection_test"] = {"status": "timeout", "message": source_message('Tavily API 请求超时')}
    except Exception as e:
        info["tavily_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    try:
        info["jina_connection_test"] = await _test_jina_connection()
    except httpx.TimeoutException:
        info["jina_connection_test"] = {"status": "timeout", "message": source_message('Jina Reader 请求超时')}
    except Exception as e:
        info["jina_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    info["firecrawl_connection_test"] = {**await _test_firecrawl_presence(), "probe": "presence"}

    try:
        info["zhipu_connection_test"] = await _test_zhipu_connection()
    except httpx.TimeoutException:
        info["zhipu_connection_test"] = {"status": "timeout", "message": source_message('智谱 API 请求超时')}
    except Exception as e:
        info["zhipu_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    try:
        info["zhipu_mcp_connection_test"] = await _test_zhipu_mcp_connection()
    except httpx.TimeoutException:
        info["zhipu_mcp_connection_test"] = {"status": "timeout", "message": source_message('智谱 Coding Plan MCP 请求超时')}
    except Exception as e:
        info["zhipu_mcp_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    try:
        info["context7_connection_test"] = await _test_context7_connection()
    except httpx.TimeoutException:
        info["context7_connection_test"] = {"status": "timeout", "message": source_message('Context7 API 请求超时')}
    except Exception as e:
        info["context7_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    try:
        info["tinyfish_connection_test"] = await _test_tinyfish_connection()
    except httpx.TimeoutException:
        info["tinyfish_connection_test"] = {"status": "timeout", "message": source_message('TinyFish API 请求超时')}
    except Exception as e:
        info["tinyfish_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    try:
        info["deepseek_connection_test"] = await _test_deepseek_connection()
    except httpx.TimeoutException:
        info["deepseek_connection_test"] = {"status": "timeout", "message": source_message('DeepSeek API 请求超时')}
    except Exception as e:
        info["deepseek_connection_test"] = {"status": "error", "message": sanitize_provider_error_message(e)}

    _record_doctor_probes(info)
    info["provider_health"] = provider_health_status()

    minimum = validate_minimum_profile()
    info["capability_status"] = minimum.get("capability_status", get_capability_status())
    info["minimum_profile_ok"] = minimum.get("ok", False)
    info["minimum_profile_missing"] = minimum.get("missing", [])
    info["intent_router_status"] = intent_router_status()
    openai_test = (info.get("main_search_connection_tests") or {}).get("openai-compatible") or {}
    available_models = []
    if isinstance(openai_test, dict):
        available_models = openai_test.get("available_models") or (openai_test.get("models_endpoint_test") or {}).get("available_models") or []
    info["openai_compatible_fallback_inventory"] = _openai_fallback_model_inventory(
        config.openai_compatible_fallback_models,
        available_models if isinstance(available_models, list) else [],
        primary_model=config.openai_compatible_model,
    )
    main_connection_tests = info.get("main_search_connection_tests") or {}
    primary_test = info.get("primary_connection_test", {})
    primary_status = primary_test.get("status")
    required_connection_ok = True
    if info["intent_router_status"].get("mode") == "jev" and info["intent_router_status"].get("configured"):
        try:
            settings = config.jev_settings()
            client = JevClient(settings, time.monotonic() + settings.timeout, verify=config.ssl_verify_enabled)
            await client.evaluate(
                {"diagnostic": "Smart Search connection check"},
                {"connection": noul("Is this state a connection check?", "It is a diagnostic connection check.", "It is not a connection check.")},
                "diagnostic",
            )
            info["jev_connection_test"] = {"status": "ok", "model": settings.model, "usage": client.usage()}
            if settings.synthesis_mode == "false":
                info["jev_synthesis_connection_test"] = {
                    "status": "skipped", "message": source_message('Jev synthesis is disabled'),
                }
            elif "jev-synthesis" in config.research_disabled_providers:
                info["jev_synthesis_connection_test"] = {
                    "status": "config_error" if settings.synthesis_mode == "true" else "skipped",
                    "message": source_message('Jev synthesis is disabled'), "reason": "provider_disabled",
                }
            else:
                try:
                    dedicated_config = settings.dedicated_synthesis_config()
                except ValueError as exc:
                    info["jev_synthesis_connection_test"] = {"status": "config_error", "message": str(exc)}
                else:
                    if dedicated_config is None:
                        info["jev_synthesis_connection_test"] = {
                            "status": "not_configured", "message": source_message('Jev synthesis model is not configured'),
                        }
                    else:
                        info["jev_synthesis_connection_test"] = await _safe_test_main_provider_connection(dedicated_config)
            synthesis_test = info["jev_synthesis_connection_test"]
            synthesis_status = synthesis_test["status"]
            if synthesis_status == "config_error":
                required_connection_ok = False
            elif settings.synthesis_mode == "true":
                required_connection_ok = synthesis_status == "ok"
            if settings.synthesis_mode == "true" or synthesis_status == "config_error":
                primary_test = synthesis_test
                primary_status = synthesis_status
        except (ValueError, ProviderCallError) as exc:
            error_type, error = classify_provider_exception(exc)
            info["jev_connection_test"] = {"status": "error", "error_type": error_type, "message": error}
            primary_test = info["jev_connection_test"]
            primary_status = "error"
    else:
        info["jev_connection_test"] = {"status": "skipped", "message": source_message('Using local routing; no Jev probe was sent.')}
    retrieval_tests = [*main_connection_tests.values(), *(info.get(f"{name}_connection_test", {}) for name in (
        "exa", "tavily", "jina", "firecrawl", "zhipu", "zhipu_mcp", "context7", "tinyfish", "deepseek",
    ))]
    retrieval_ready = any(test.get("status") in {"ok", "configured"} for test in retrieval_tests)
    info["retrieval_connection_verified"] = any(test.get("status") == "ok" for test in retrieval_tests)
    info["degraded"] = info["jev_connection_test"].get("status") == "error"
    info["ok"] = retrieval_ready and minimum.get("ok", False) and not info.get("config_parameter_errors") and required_connection_ok
    if not main_provider_configs:
        info["primary_connection_test"] = {"status": "not_required", "message": source_message('Search can use a retrieval channel without a main model.')}
    if info["ok"]:
        info["error_type"] = ""
        info["error"] = ""
    elif info.get("config_parameter_errors"):
        info["error"] = "; ".join(info["config_parameter_errors"])
        info["error_type"] = "parameter_error"
    elif not minimum.get("ok", False):
        info["error"] = minimum.get("error", MINIMUM_PROFILE_ERROR)
        info["error_type"] = minimum.get("error_type", "config_error")
    elif info.get("jev_connection_test", {}).get("status") == "error":
        info["error"] = info["jev_connection_test"]["message"]
        info["error_type"] = info["jev_connection_test"]["error_type"]
    else:
        info["error"] = primary_test.get("message", "Primary connection check failed")
        if primary_status in {"config_error", "not_configured"}:
            info["error_type"] = "config_error"
        elif primary_status in {"timeout", "error", "warning"}:
            info["error_type"] = "network_error"
        else:
            info["error_type"] = "runtime_error"
    return info


def current_model() -> dict[str, Any]:
    try:
        api_mode = config.openai_compatible_api_mode
    except ValueError as e:
        return {
            "ok": False,
            "error_type": "parameter_error",
            "error": str(e),
            "config_file": str(config.config_file),
        }
    return {
        "ok": True,
        "xai_model": config.xai_model,
        "xai_stream": config.xai_stream,
        "openai_compatible_model": config.openai_compatible_model,
        "openai_compatible_fallback_models": config.openai_compatible_fallback_models,
        "openai_compatible_api_mode": api_mode,
        "config_file": str(config.config_file),
    }


def set_model(model: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": "parameter_error",
        "error": (
            source_message('The legacy default model command was removed. Use `smart-search config set XAI_MODEL <model>` or `smart-search config set OPENAI_COMPATIBLE_MODEL <model>`.')
        ),
        "config_file": str(config.config_file),
    }


def config_path() -> dict[str, Any]:
    return config.config_path_info()


def config_list(show_secrets: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "config_file": str(config.config_file),
        "values": config.get_saved_config(masked=not show_secrets),
    }


def config_set(key: str, value: str) -> dict[str, Any]:
    try:
        config.set_config_value(key, value)
    except ValueError as e:
        return {"ok": False, "error_type": "parameter_error", "error": str(e), "config_file": str(config.config_file)}
    saved = config.get_saved_config(masked=True, data=config._load_config_file())
    return {
        "ok": True,
        "config_file": str(config.config_file),
        "key": key.strip().upper(),
        "value": saved.get(key.strip().upper(), ""),
    }


def config_update(
    set_values: dict[str, str] | None = None,
    unset_keys: list[str] | None = None,
    *,
    expected_revision: str | None = None,
) -> dict[str, Any]:
    """Apply a batch of config changes in one validated, atomic write."""
    try:
        result = config.update_config_values(set_values, unset_keys, expected_revision=expected_revision)
    except ValueError as e:
        return {
            "ok": False,
            "error_type": "parameter_error",
            "error": str(e),
            "config_file": str(config.config_file),
            "errors": [],
            "saved": {},
            "unset": [],
        }
    if not result["ok"]:
        return {
            "ok": False,
            "error_type": "config_conflict" if result.get("conflict") else "parameter_error",
            "error": "; ".join(f"{item['key']}: {item['error']}" for item in result["errors"]),
            "config_file": str(config.config_file),
            "errors": result["errors"],
            "saved": {},
            "unset": [],
        }
    saved = config.get_saved_config(masked=True, data=config._load_config_file())
    return {
        "ok": True,
        "error_type": "",
        "error": "",
        "config_file": str(config.config_file),
        "errors": [],
        "saved": {key: saved.get(key, "") for key in result["saved"]},
        "unset": result["unset"],
    }


def capability_status_from_values(values: dict[str, str]) -> dict[str, Any]:
    """Use the runtime capability rules for unsaved configuration too."""
    with config.snapshot(values, merge=False):
        return get_capability_status()


def config_unset(key: str) -> dict[str, Any]:
    try:
        config.unset_config_value(key)
    except ValueError as e:
        return {"ok": False, "error_type": "parameter_error", "error": str(e), "config_file": str(config.config_file), "key": key.strip().upper()}
    return {"ok": True, "config_file": str(config.config_file), "key": key.strip().upper()}


async def smoke(mode: str = "mock") -> dict[str, Any]:
    start = time.time()
    mode = (mode or "mock").strip().lower()
    if mode not in {"mock", "live"}:
        return {"ok": False, "error_type": "parameter_error", "error": source_message('mode must be mock or live')}
    if mode == "live":
        return await _smoke_live(start)
    return await _smoke_mock(start)


def _case(name: str, ok: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": ok, **(details or {})}


def _case_failed(case: dict[str, Any]) -> bool:
    return not case.get("ok") and case.get("severity", "critical") != "degraded"


def _skipped_case(name: str, reason: str) -> dict[str, Any]:
    return _case(name, True, {"status": "skipped", "skipped": reason})


def _smoke_case_summary(cases: list[dict[str, Any]]) -> tuple[list[str], list[str], list[str], str]:
    failed = [case["name"] for case in cases if _case_failed(case)]
    degraded = [case["name"] for case in cases if not case.get("ok") and case.get("severity") == "degraded"]
    skipped = [
        case["name"]
        for case in cases
        if case.get("status") == "skipped" or bool(case.get("skipped"))
    ]
    status = "failed" if failed else ("degraded" if degraded else "healthy")
    return failed, degraded, skipped, status


async def _smoke_mock(start: float) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    minimum_status = {
        "main_search": {
            "configured": ["xai-responses", "openai-compatible"],
            "fallback_chain": MAIN_SEARCH_FALLBACK_CHAIN,
            "ok": True,
        },
        "web_search": {"configured": ["zhipu"], "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl", "tinyfish", "deepseek"], "ok": True},
        "docs_search": {"configured": ["context7"], "fallback_chain": ["context7", "exa"], "ok": True},
        "web_fetch": {"configured": ["tavily"], "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish", "deepseek"], "ok": True},
        "vertical_search": {
            "configured": [],
            "fallback_chain": ["anysearch"],
            "ok": False,
            "experimental": True,
            "explicit_only": ["sciverse"],
            "route_enabled": {"anysearch": True, "sciverse": False},
        },
    }
    minimum = _minimum_profile_result("standard", minimum_status)
    cases.append(
        _case(
            "doctor minimum profile gate",
            minimum["ok"] and not minimum["missing"],
            {"minimum_profile_ok": minimum["ok"], "capability_status": minimum["capability_status"]},
        )
    )

    missing_minimum = _minimum_profile_result("standard", {})
    cases.append(
        _case(
            "doctor minimum profile fails closed",
            not missing_minimum["ok"] and missing_minimum["missing"] == ["retrieval"],
            {"missing": missing_minimum["missing"], "error_type": missing_minimum["error_type"]},
        )
    )

    main_attempts = [_attempt("main_search", "xAI Responses", "ok", time.time(), result_count=1)]
    cases.append(_case("main_search xai responses answer path", True, {"provider_attempts": main_attempts}))

    responses_provider = OpenAICompatibleSearchProvider(
        "https://relay.example.com/v1",
        "mock-key",
        "mock-model",
        api_mode="responses",
    )
    responses_payload = responses_provider._build_request_payload("mock instructions", "mock input", stream=False)
    cases.append(
        _case(
            "openai-compatible Responses mock protocol subset",
            responses_provider._api_endpoint() == "https://relay.example.com/v1/responses"
            and responses_payload.get("input") == [{"role": "user", "content": "mock input"}]
            and "messages" not in responses_payload
            and "tools" not in responses_payload,
            {"api_mode": "responses", "endpoint": responses_provider._api_endpoint()},
        )
    )

    main_fallback_attempts = [
        _attempt("main_search", "xAI Responses", "error", time.time(), error_type="network_error", error="mock failure"),
        _attempt("main_search", "OpenAI-compatible", "ok", time.time(), result_count=1),
    ]
    cases.append(_case("main_search fallback xai_to_openai_compatible", _fallback_used(main_fallback_attempts), {"provider_attempts": main_fallback_attempts}))

    web_attempts = [
        _attempt("web_search", "grok-web-tools", "error", time.time(), error_type="network_error", error="mock failure"),
        _attempt("web_search", "zhipu", "ok", time.time(), result_count=1),
    ]
    cases.append(_case("web_search fallback grok_to_zhipu", _fallback_used(web_attempts), {"provider_attempts": web_attempts}))

    attempts = [
        _attempt("web_fetch", "tavily", "empty", time.time()),
        _attempt("web_fetch", "firecrawl", "ok", time.time(), result_count=1),
    ]
    cases.append(_case("web_fetch fallback tavily_to_firecrawl", _fallback_used(attempts), {"provider_attempts": attempts}))

    docs_attempts = [
        _attempt("docs_search", "context7", "empty", time.time()),
        _attempt("docs_search", "exa", "ok", time.time(), result_count=1),
    ]
    cases.append(_case("docs_search fallback context7_to_exa", _fallback_used(docs_attempts), {"provider_attempts": docs_attempts}))

    general_route = {
        "docs_intent": _is_docs_intent("today AI news"),
        "zh_current_intent": _is_zh_current_intent("today AI news"),
        "web_current_intent": _is_web_current_intent("today AI news"),
        "supplemental_paths": [],
    }
    cases.append(_case("search balanced avoids context7 for general query", not general_route["docs_intent"], {"routing_decision": general_route}))

    docs_route = {
        "docs_intent": _is_docs_intent("React useEffect API docs"),
        "web_current_intent": _is_web_current_intent("React useEffect API docs"),
        "supplemental_paths": ["docs_search"],
    }
    cases.append(_case("search docs intent uses docs route", docs_route["docs_intent"], {"routing_decision": docs_route}))

    zh_route = {
        "zh_current_intent": _is_zh_current_intent("今天国内 AI 新闻"),
        "web_current_intent": _is_web_current_intent("今天国内 AI 新闻"),
        "supplemental_paths": ["web_search"],
    }
    cases.append(_case("search zh current intent uses zhipu reinforcement", zh_route["zh_current_intent"], {"routing_decision": zh_route}))

    sports_route = {
        "zh_current_intent": _is_zh_current_intent("nba战报"),
        "web_current_intent": _is_web_current_intent("nba战报"),
        "supplemental_paths": ["web_search"],
    }
    cases.append(_case("search sports current intent uses web reinforcement", sports_route["web_current_intent"], {"routing_decision": sports_route}))

    strict_attempts = [_attempt("main_search", "xAI Responses", "ok", time.time(), result_count=1)]
    strict_sources: list[dict[str, Any]] = []
    cases.append(
        _case(
            "strict insufficient evidence fails closed",
            not strict_sources,
            {"provider_attempts": strict_attempts, "error_type": "evidence_error"},
        )
    )

    deep_allowed_tools = {
        "search",
        "exa-search",
        "exa-similar",
        "zhipu-search",
        "context7-library",
        "context7-docs",
        "fetch",
        "map",
    }
    fixed_recipe_ids = {
        "current_market_research",
        "product_comparison_research",
        "technical_docs_research",
        "news_or_policy_research",
        "claim_verification_research",
        "url_first_research",
    }
    base_plan_fields = {
        "mode",
        "question",
        "difficulty",
        "intent_signals",
        "capability_plan",
        "evidence_policy",
        "steps",
        "gap_check",
        "final_answer_policy",
    }
    market_plan = build_deep_research_plan("深度搜索一下最近的比特币行情", evidence_dir=r"C:\tmp\smart-search-evidence\market")
    market_tools = {step["tool"] for step in market_plan["steps"]}
    cases.append(
        _case(
            "deep_research explicit planner simple current prompt uses capability plan",
            base_plan_fields.issubset(market_plan)
            and market_plan["intent_signals"]["recency_requirement"] == "current"
            and market_plan["intent_signals"]["claim_risk"] == "high"
            and market_plan["trigger_source"] == "explicit_cli"
            and market_plan["preflight"]["executed_by_deep_command"] is False
            and market_plan["evidence_policy"] == "fetch_before_claim"
            and "search" in market_tools
            and "zhipu-search" in market_tools
            and "exa-search" not in market_tools
            and "fetch" in market_tools
            and market_tools <= deep_allowed_tools,
            {"research_plan": market_plan},
        )
    )

    docs_plan = build_deep_research_plan("深度调研 React useEffect 最新文档", evidence_dir=r"C:\tmp\smart-search-evidence\docs")
    docs_tools = {step["tool"] for step in docs_plan["steps"]}
    cases.append(
        _case(
            "deep_research docs api prompt uses docs capabilities",
            docs_plan["intent_signals"]["docs_api_intent"]
            and {"context7-library", "context7-docs", "fetch"} <= docs_tools
            and "exa-search" not in docs_tools
            and docs_tools <= deep_allowed_tools,
            {"research_plan": docs_plan},
        )
    )

    claim_plan = build_deep_research_plan("帮我核验这个说法是真是假", evidence_dir=r"C:\tmp\smart-search-evidence\claim")
    cases.append(
        _case(
            "deep_research claim verification requires fetch_before_claim",
            claim_plan["evidence_policy"] == "fetch_before_claim"
            and claim_plan["intent_signals"]["cross_validation_need"] == "high"
            and any(step["tool"] == "fetch" for step in claim_plan["steps"])
            and not any(step["tool"] == "exa-search" for step in claim_plan["steps"])
            and claim_plan["gap_check"]["unsupported_claim_action"] == "downgrade_to_unverified_candidate",
            {"research_plan": claim_plan},
        )
    )

    url_first_plan = build_deep_research_plan("深度调研 https://example.com/source", evidence_dir=r"C:\tmp\smart-search-evidence\url")
    cases.append(
        _case(
            "deep_research url prompt is fetch first",
            url_first_plan["intent_signals"]["known_url"]
            and url_first_plan["steps"][0]["tool"] == "fetch"
            and any(step["tool"] == "exa-similar" for step in url_first_plan["steps"]),
            {"research_plan": url_first_plan},
        )
    )

    normal_prompt = "搜索一下 smart-search 怎么安装"
    cases.append(
        _case(
            "deep_research normal search prompt does not trigger",
            not any(marker in normal_prompt.lower() for marker in ("深度搜索", "深度调研", "深入搜索", "deep search", "deep research")),
            {"prompt": normal_prompt, "deep_research_triggered": False},
        )
    )

    missing_for_deep = _minimum_profile_result("standard", {})
    cases.append(
        _case(
            "deep_research missing provider gives capability guidance",
            not missing_for_deep["ok"] and missing_for_deep["missing"] == ["retrieval"],
            {"missing": missing_for_deep["missing"], "error_type": missing_for_deep["error_type"]},
        )
    )

    schema_modes = {"deep_research"}
    cases.append(
        _case(
            "deep_research fixed topic recipes are examples not schema",
            schema_modes.isdisjoint(fixed_recipe_ids) and "deep_research" in schema_modes,
            {"schema_modes": sorted(schema_modes), "not_schema_modes": sorted(fixed_recipe_ids)},
        )
    )

    mock_research_status = {
        **minimum_status,
        "web_search": {
            "configured": ["zhipu", "zhipu-mcp", "tavily", "firecrawl", "tinyfish"],
            "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl", "tinyfish", "deepseek"],
            "ok": True,
        },
        "docs_search": {"configured": ["context7", "exa"], "fallback_chain": ["context7", "exa"], "ok": True},
        "web_fetch": {
            "configured": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish"],
            "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl", "tinyfish", "deepseek"],
            "ok": True,
        },
        "vertical_search": {
            "configured": ["anysearch"],
            "fallback_chain": ["anysearch"],
            "ok": True,
            "experimental": True,
            "explicit_only": ["sciverse"],
            "route_enabled": {"anysearch": True, "sciverse": False},
        },
    }
    from types import SimpleNamespace
    local = SimpleNamespace(build_rules_route=build_rules_route, _extract_urls=_extract_urls,
                            _research_fetch_order=lambda q, u: _research_fetch_order(q, u, mock_research_status))
    channels = [{"provider": provider, "capability": capability, "operation": "search", "query": query,
                 "preference_rank": 0, "url": ""}
                for provider, capability, query in [("context7", "docs_search", "React docs"),
                                                    ("zhipu", "web_search", "今天新闻"),
                                                    ("anysearch", "vertical_search", "CVE")]]
    for channel in channels:
        selected = jev_search.fallback_channels(local, channel["query"], channels, 1)
        cases.append(_case("local route " + channel["capability"], selected == [channel]))

    research_fallback_attempts = [
        _attempt("web_fetch", "jina", "empty", time.time()),
        _attempt("web_fetch", "firecrawl", "ok", time.time(), result_count=1),
    ]
    cases.append(
        _case(
            "research fallback remains same capability",
            _fallback_used(research_fallback_attempts),
            {"provider_attempts": research_fallback_attempts},
        )
    )

    all_attempts: list[dict] = []
    for c in cases:
        all_attempts.extend(c.get("provider_attempts", []))
    failed, degraded, skipped, status = _smoke_case_summary(cases)
    return {
        "ok": status != "failed",
        "mode": "mock",
        "status": status,
        "failed_cases": failed,
        "degraded_cases": degraded,
        "skipped_cases": skipped,
        "cases": cases,
        "provider_attempts": all_attempts,
        "providers_used": _provider_names_from_attempts(all_attempts),
        "fallback_used": _fallback_used(all_attempts),
        "elapsed_ms": _elapsed_ms(start),
    }


async def _smoke_live(start: float) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    doctor_result = await doctor()
    capability_status = doctor_result.get("capability_status", {})
    cases.append(
        _case(
            "doctor minimum profile",
            bool(doctor_result.get("minimum_profile_ok")),
            {
                "error_type": doctor_result.get("error_type", ""),
                "error": doctor_result.get("error", ""),
                "capability_status": doctor_result.get("capability_status", {}),
            },
        )
    )

    # A configured minimum profile is necessary but not sufficient for a live
    # smoke pass: doctor has already probed the configured main-search route
    # chain. Do not downgrade that required path to a merely configured check.
    if doctor_result.get("minimum_profile_ok"):
        primary_status = doctor_result.get("primary_connection_test", {})
        main_connection_tests = doctor_result.get("main_search_connection_tests", {})
        available_providers = [
            provider
            for provider, connection in main_connection_tests.items()
            if isinstance(connection, dict) and connection.get("status") == "ok"
        ]
        cases.append(
            _case(
                "main search connection",
                bool(doctor_result.get("ok")),
                {
                    "status": "ok" if doctor_result.get("ok") else primary_status.get("status", ""),
                    "error": "" if doctor_result.get("ok") else primary_status.get("message", ""),
                    "available_providers": available_providers,
                },
            )
        )

    zhipu_status = doctor_result.get("zhipu_connection_test", {})
    if config.zhipu_api_key:
        zhipu_ok = zhipu_status.get("status") == "ok"
        web_fallback_available = len(capability_status.get("web_search", {}).get("configured", [])) > 1
        cases.append(
            _case(
                "zhipu search",
                zhipu_ok,
                {
                    "status": zhipu_status.get("status", ""),
                    "error": zhipu_status.get("message", ""),
                    "severity": "" if zhipu_ok else ("degraded" if web_fallback_available else "critical"),
                    "fallback_available": web_fallback_available,
                },
            )
        )
    else:
        cases.append(_skipped_case("zhipu search", "ZHIPU_API_KEY not configured"))

    context7_status = doctor_result.get("context7_connection_test", {})
    if config.context7_api_key:
        context7_ok = context7_status.get("status") == "ok"
        docs_fallback_available = len(capability_status.get("docs_search", {}).get("configured", [])) > 1
        cases.append(
            _case(
                "context7 library",
                context7_ok,
                {
                    "status": context7_status.get("status", ""),
                    "error": context7_status.get("message", ""),
                    "severity": "" if context7_ok else ("degraded" if docs_fallback_available else "critical"),
                    "fallback_available": docs_fallback_available,
                },
            )
        )
    else:
        cases.append(_skipped_case("context7 library", "CONTEXT7_API_KEY not configured"))

    if config.tavily_api_key and not config.tavily_enabled:
        cases.append(_skipped_case("tavily", "TAVILY_ENABLED=false"))

    enabled_fetch_providers = capability_status.get("web_fetch", {}).get("configured", [])
    if enabled_fetch_providers:
        fetch_result = await fetch("https://example.com")
        cases.append(_case("web fetch fallback chain", bool(fetch_result.get("ok")), {"provider": fetch_result.get("provider", ""), "provider_attempts": fetch_result.get("provider_attempts", [])}))
    else:
        cases.append(_skipped_case("web fetch fallback chain", "no enabled web_fetch provider configured"))

    failed, degraded, skipped, status = _smoke_case_summary(cases)
    attempts: list[dict] = []
    for c in cases:
        attempts.extend(c.get("provider_attempts", []))
    return {
        "ok": status != "failed",
        "mode": "live",
        "status": status,
        "failed_cases": failed,
        "degraded_cases": degraded,
        "skipped_cases": skipped,
        "cases": cases,
        "provider_attempts": attempts,
        "elapsed_ms": _elapsed_ms(start),
    }


def write_output(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
