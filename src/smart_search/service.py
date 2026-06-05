import asyncio
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .config import config
from .logger import log_info
from .providers.anysearch import AnySearchProvider
from .providers.context7 import Context7Provider
from .providers.exa import ExaSearchProvider
from .providers.jina import JinaReaderProvider
from .providers.openai_compatible import OpenAICompatibleSearchProvider, get_local_time_info
from .providers.xai_responses import XAIResponsesSearchProvider
from .providers.zhipu import ZhipuWebSearchProvider
from .providers.zhipu_mcp import ZhipuMCPProvider
from .sources import merge_sources, new_session_id, split_answer_and_sources
from .utils import search_prompt


_AVAILABLE_MODELS_CACHE: dict[tuple[str, str], list[str]] = {}
_AVAILABLE_MODELS_LOCK = asyncio.Lock()
SOURCE_PROVENANCE_WARNING = (
    "extra_sources are retrieved in parallel and are not automatically used to verify generated content; "
    "use fetch on key URLs for claim-level evidence."
)
MINIMUM_PROFILE_ERROR = (
    "最低配置不满足：必须至少配置 main_search、docs_search、web_fetch 三类能力各一个 provider。"
)
OPENAI_COMPATIBLE_DIAGNOSE_COMMAND = "smart-search diagnose openai-compatible --format markdown"
DOCS_INTENT_KEYWORDS = {
    "api",
    "sdk",
    "library",
    "framework",
    "docs",
    "documentation",
    "reference",
    "react",
    "next.js",
    "vue",
    "python",
    "prisma",
    "langchain",
    "openai",
    "context7",
    "接口",
    "文档",
    "库",
    "框架",
    "函数",
    "参数",
    "配置",
}
ZH_CURRENT_KEYWORDS = {
    "今天",
    "最新",
    "国内",
    "中国",
    "政策",
    "新闻",
    "实时",
    "刚刚",
    "本周",
    "本月",
    "战报",
    "比分",
    "赛程",
    "赛果",
    "季后赛",
    "比赛",
    "nba",
    "足球",
    "篮球",
}
FETCH_INTENT_KEYWORDS = {"http://", "https://"}
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
RESEARCH_VERTICAL_KEYWORDS = {
    "cve",
    "vulnerability",
    "vulnerabilities",
    "安全漏洞",
    "漏洞",
    "finance",
    "financial",
    "股票",
    "基金",
    "财报",
    "法律",
    "法规",
    "legal",
    "law",
    "academic",
    "论文",
    "paper",
    "repo",
    "repository",
    "github",
    "gitlab",
    "codebase",
    "code search",
    "code docs",
    "代码",
    "代码库",
    "开源仓库",
}
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
    "web_search": ["zhipu", "zhipu-mcp", "tavily", "firecrawl"],
    "docs_search": ["context7", "exa"],
    "web_fetch": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"],
    "vertical_search": ["anysearch"],
    "site_map": ["tavily"],
    "synthesis": ["main-search"],
}
PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "xai-responses": {
        "capability": "main_search",
        "strengths": ["broad synthesis", "web_search", "x_search"],
        "exclusions": ["evidence proof without fetch"],
        "fallback_group": "main_search",
        "minimum_profile_role": "main_search",
        "quality_filters": ["source extraction required for high-risk claims"],
        "route_reasons": ["broad live answer", "primary synthesis"],
    },
    "openai-compatible": {
        "capability": "main_search",
        "strengths": ["broad synthesis", "relay compatibility"],
        "exclusions": ["xAI server tools"],
        "fallback_group": "main_search",
        "minimum_profile_role": "main_search",
        "quality_filters": ["source extraction required for high-risk claims"],
        "route_reasons": ["relay-compatible primary synthesis"],
    },
    "context7": {
        "capability": "docs_search",
        "strengths": ["library docs", "API docs", "framework docs", "versioned snippets"],
        "exclusions": ["general news", "generic web facts"],
        "fallback_group": "docs_search",
        "minimum_profile_role": "docs_search",
        "quality_filters": ["library id required", "content required before citation"],
        "route_reasons": ["docs/API evidence", "framework reference"],
    },
    "exa": {
        "capability": "docs_search",
        "strengths": ["official domains", "papers", "product pages", "trusted low-noise discovery", "similar pages"],
        "exclusions": ["default second hop for every high-risk claim"],
        "fallback_group": "docs_search",
        "minimum_profile_role": "docs_search",
        "quality_filters": ["URL required", "fetch before proof citation"],
        "route_reasons": ["official low-noise discovery", "paper/product discovery"],
    },
    "zhipu": {
        "capability": "web_search",
        "strengths": ["Chinese", "domestic China", "current", "policy", "announcements", "recency filters"],
        "exclusions": ["web_fetch", "chat model selection"],
        "fallback_group": "web_search",
        "minimum_profile_role": "",
        "quality_filters": ["URL required", "fetch before proof citation"],
        "route_reasons": ["Chinese/current/policy discovery"],
    },
    "zhipu-mcp": {
        "capability": "web_search",
        "strengths": ["Coding Plan quota", "remote MCP web_search_prime"],
        "exclusions": ["Zhipu REST Web Search API"],
        "fallback_group": "web_search",
        "minimum_profile_role": "",
        "quality_filters": ["URL required", "fetch before proof citation"],
        "route_reasons": ["Coding Plan quota web discovery"],
    },
    "tavily": {
        "capability": "web_search",
        "capabilities": ["web_search", "web_fetch", "site_map"],
        "strengths": ["broad source discovery", "site map", "URL extract"],
        "exclusions": ["docs semantic replacement"],
        "fallback_group": "web_search/web_fetch/site_map",
        "minimum_profile_role": "web_fetch",
        "quality_filters": ["non-empty normalized result", "non-empty extracted content"],
        "route_reasons": ["broad source discovery", "site map", "URL fetch"],
    },
    "jina": {
        "capability": "web_fetch",
        "strengths": ["known public URL", "PDF", "arXiv", "clean markdown", "ReaderLM-v2 with key"],
        "exclusions": ["general search provider", "anonymous standard minimum profile"],
        "fallback_group": "web_fetch",
        "minimum_profile_role": "web_fetch_with_key",
        "quality_filters": ["non-empty markdown", "challenge page rejection", "ReaderLM-v2 requires key"],
        "route_reasons": ["known URL extraction", "PDF/arXiv extraction"],
    },
    "zhipu-mcp-reader": {
        "capability": "web_fetch",
        "strengths": ["Coding Plan quota", "remote MCP webReader"],
        "exclusions": ["Zhipu REST Web Search API"],
        "fallback_group": "web_fetch",
        "minimum_profile_role": "",
        "quality_filters": ["non-empty reader content"],
        "route_reasons": ["Coding Plan quota page read"],
    },
    "firecrawl": {
        "capability": "web_fetch",
        "capabilities": ["web_search", "web_fetch"],
        "strengths": ["robust scrape fallback", "JS-heavy pages", "dynamic pages", "OCR/PDF/structured extraction"],
        "exclusions": ["docs semantic replacement"],
        "fallback_group": "web_search/web_fetch",
        "minimum_profile_role": "web_fetch",
        "quality_filters": ["non-empty normalized result", "non-empty extracted content"],
        "route_reasons": ["JS-heavy fetch", "dynamic/browser-like extraction", "robust fetch fallback"],
    },
    "anysearch": {
        "capability": "vertical_search",
        "strengths": ["CVE", "finance", "legal", "academic", "code/docs", "structured vertical domains"],
        "exclusions": ["generic default fallback", "standard minimum profile"],
        "fallback_group": "vertical_search",
        "minimum_profile_role": "",
        "quality_filters": ["vertical intent required", "URL required before evidence citation"],
        "route_reasons": ["vertical domain discovery"],
        "experimental": True,
    },
    "main-search": {
        "capability": "synthesis",
        "strengths": ["evidence-only final synthesis"],
        "exclusions": ["live source discovery during research synthesis"],
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
        "fallback_used": False,
        "validation_level": "",
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
) -> dict[str, Any]:
    return {
        "capability": capability,
        "provider": provider,
        "status": status,
        "error_type": error_type,
        "error": error,
        "elapsed_ms": _elapsed_ms(start),
        "result_count": result_count,
    }


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
        if attempt.get("status") in {"ok", "empty", "error"}:
            by_capability.setdefault(capability, []).append(attempt)
    for capability_attempts in by_capability.values():
        previous_failed = False
        previous_provider = ""
        for attempt in capability_attempts:
            provider = attempt.get("provider", "")
            status = attempt.get("status")
            if previous_failed:
                return True
            if previous_provider and provider and provider != previous_provider:
                return True
            previous_failed = status in {"empty", "error"}
            previous_provider = provider or previous_provider
    return False


def provider_profiles() -> dict[str, dict[str, Any]]:
    return {provider: dict(profile) for provider, profile in PROVIDER_PROFILES.items()}


def _provider_supports_capability(provider: str, capability: str) -> bool:
    profile = PROVIDER_PROFILES.get(provider, {})
    capabilities = set(profile.get("capabilities") or [profile.get("capability", "")])
    return capability in capabilities


def _provider_configured(provider: str) -> bool:
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
        return bool(config.tavily_api_key)
    if provider == "jina":
        return bool(config.jina_api_key)
    if provider == "zhipu-mcp-reader":
        return bool(config.zhipu_mcp_api_key)
    if provider == "firecrawl":
        return bool(config.firecrawl_api_key)
    if provider == "anysearch":
        return bool(config.anysearch_api_key)
    if provider == "main-search":
        return bool(config.xai_api_key or (config.openai_compatible_api_url and config.openai_compatible_api_key))
    return False


def _configured_for_capability(capability: str, capability_status: dict[str, Any] | None = None) -> list[str]:
    if capability_status is not None:
        configured = set(capability_status.get(capability, {}).get("configured") or [])
        return [
            provider
            for provider in RESEARCH_PROFILE_ORDER.get(capability, [])
            if provider in configured and _provider_supports_capability(provider, capability)
        ]
    return [provider for provider in RESEARCH_PROFILE_ORDER.get(capability, []) if _provider_configured(provider)]


def _safe_provider_overrides() -> tuple[list[str], list[str], list[str]]:
    known = set(PROVIDER_PROFILES)
    preferred = [provider for provider in config.research_preferred_providers if provider in known]
    disabled = [provider for provider in config.research_disabled_providers if provider in known]
    invalid = [
        provider
        for provider in config.research_preferred_providers + config.research_disabled_providers
        if provider not in known
    ]
    return preferred, disabled, invalid


def _apply_research_overrides(capability: str, providers: list[str]) -> list[str]:
    preferred, disabled, _ = _safe_provider_overrides()
    allowed = [
        provider
        for provider in providers
        if provider not in disabled and _provider_supports_capability(provider, capability)
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


def _research_route_signals(question: str, plan: dict[str, Any]) -> dict[str, Any]:
    intent = plan.get("intent_signals") or {}
    text = question.lower()
    return {
        "docs_api_intent": bool(intent.get("docs_api_intent")) or _is_docs_intent(question),
        "official_low_noise_intent": _contains_any(question, DEEP_EXA_DISCOVERY_KEYWORDS),
        "current_or_locale_intent": intent.get("recency_requirement") in {"recent", "current"}
        or intent.get("locale_domain_scope") == "china"
        or _is_zh_current_intent(question),
        "known_url": bool(intent.get("known_url")) or bool(_extract_urls(question)),
        "pdf_or_arxiv_intent": _contains_any(question, RESEARCH_PDF_KEYWORDS),
        "js_heavy_intent": _contains_any(question, RESEARCH_JS_HEAVY_KEYWORDS),
        "vertical_intent": _contains_any(question, RESEARCH_VERTICAL_KEYWORDS),
        "claim_risk": intent.get("claim_risk", "medium"),
        "cross_validation_need": intent.get("cross_validation_need", "normal"),
        "raw_query": text,
    }


def _research_capability_routes(
    question: str,
    plan: dict[str, Any],
    fallback: str,
    capability_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    signals = _research_route_signals(question, plan)
    _, _, invalid_overrides = _safe_provider_overrides()
    routes: dict[str, Any] = {
        "signals": signals,
        "fallback_mode": fallback,
        "route_policy_version": RESEARCH_ROUTE_POLICY_VERSION,
        "invalid_provider_overrides": invalid_overrides,
        "capabilities": {},
    }

    web_search = _configured_for_capability("web_search", capability_status)
    if signals["current_or_locale_intent"]:
        ordered = [provider for provider in ["zhipu", "zhipu-mcp", "tavily", "firecrawl"] if provider in web_search]
    else:
        ordered = [provider for provider in ["tavily", "firecrawl", "zhipu", "zhipu-mcp"] if provider in web_search]
    routes["capabilities"]["web_search"] = {
        "providers": _apply_research_overrides("web_search", ordered),
        "reason": "current/locale evidence" if signals["current_or_locale_intent"] else "broad source discovery",
    }

    docs = _configured_for_capability("docs_search", capability_status)
    docs_order = [provider for provider in ["context7", "exa"] if provider in docs]
    if signals["official_low_noise_intent"] and not signals["docs_api_intent"]:
        docs_order = [provider for provider in ["exa", "context7"] if provider in docs]
    routes["capabilities"]["docs_search"] = {
        "providers": _apply_research_overrides("docs_search", docs_order),
        "reason": "docs/API evidence" if signals["docs_api_intent"] else "official low-noise discovery",
    }

    fetch_order = _research_fetch_order(question, capability_status=capability_status)
    routes["capabilities"]["web_fetch"] = {
        "providers": fetch_order,
        "reason": "JS-heavy fetch" if signals["js_heavy_intent"] else ("known URL/PDF extraction" if signals["known_url"] or signals["pdf_or_arxiv_intent"] else "evidence extraction"),
    }

    vertical = _configured_for_capability("vertical_search", capability_status)
    routes["capabilities"]["vertical_search"] = {
        "providers": _apply_research_overrides("vertical_search", vertical) if signals["vertical_intent"] else [],
        "reason": "vertical intent matched" if signals["vertical_intent"] else "vertical intent absent",
        "experimental": True,
    }

    return routes


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


def _select_candidate_urls(sources: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        url = (source.get("url") or "").strip()
        if not url or url.startswith("context7:") or url in seen:
            continue
        seen.add(url)
        selected.append(source)
        if len(selected) >= limit:
            break
    return selected


def _artifact_path(evidence_root: str, name: str) -> Path:
    return Path(evidence_root) / name


def _write_research_artifact(evidence_root: str, name: str, data: Any) -> None:
    root = Path(evidence_root)
    root.mkdir(parents=True, exist_ok=True)
    path = _artifact_path(evidence_root, name)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_docs_intent(query: str) -> bool:
    q = query.lower()
    return any(keyword in q for keyword in DOCS_INTENT_KEYWORDS)


def _is_zh_current_intent(query: str) -> bool:
    q = query.lower()
    return any(keyword in q for keyword in ZH_CURRENT_KEYWORDS)


def _is_fetch_intent(query: str) -> bool:
    q = query.lower()
    return any(keyword in q for keyword in FETCH_INTENT_KEYWORDS)


def _contains_any(query: str, keywords: set[str]) -> bool:
    q = query.lower()
    return any(keyword.lower() in q for keyword in keywords)


def _extract_urls(query: str) -> list[str]:
    urls = []
    for match in re.findall(r"https?://[^\s<>\]\)\"']+", query):
        cleaned = match.rstrip(".,;，。；)")
        if cleaned:
            urls.append(cleaned)
    return urls


def _slugify_query(query: str) -> str:
    slug = re.sub(r"https?://", "", query.lower())
    slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", slug, flags=re.IGNORECASE)
    slug = slug.strip("-")
    return slug[:48] or "deep-research"


def _default_evidence_dir(query: str) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M")
    return str(Path("C:/tmp/smart-search-evidence") / f"{timestamp}-{_slugify_query(query)}")


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
    docs_intent = _is_docs_intent(question)
    zh_current_intent = _is_zh_current_intent(question)
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
) -> dict[str, Any]:
    start = time.time()
    question = query.strip()
    fallback_mode = (fallback or "auto").strip().lower()
    if fallback_mode not in {"auto", "off"}:
        return {
            "ok": False,
            "error_type": "parameter_error",
            "error": f"Invalid fallback mode: {fallback_mode}",
            "question": question,
            "mode": "deep_research_execution",
            "route_policy_version": RESEARCH_ROUTE_POLICY_VERSION,
            "elapsed_ms": _elapsed_ms(start),
        }

    minimum = validate_minimum_profile()
    if not minimum.get("ok"):
        return {
            "ok": False,
            "error_type": minimum.get("error_type", "config_error"),
            "error": minimum.get("error", MINIMUM_PROFILE_ERROR),
            "question": question,
            "mode": "deep_research_execution",
            "minimum_profile_ok": False,
            "capability_status": minimum.get("capability_status", {}),
            "final_answer": "",
            "citations": [],
            "evidence_items": [],
            "gap_check": {
                "status": "failed",
                "gaps": [{"subquestion_id": "", "reason": "minimum profile is missing required capabilities"}],
            },
            "provider_attempts": [],
            "fallback_used": False,
            "degraded": True,
            "route_policy_version": RESEARCH_ROUTE_POLICY_VERSION,
            "evidence_dir": evidence_dir,
            "elapsed_ms": _elapsed_ms(start),
        }

    plan = build_deep_research_plan(question, budget=_deep_budget(budget or "deep"), evidence_dir=evidence_dir)
    evidence_root = plan.get("evidence_dir") or _default_evidence_dir(question)
    routes = _research_capability_routes(question, plan, fallback_mode)
    provider_attempts: list[dict[str, Any]] = []
    discovery_sources: list[dict[str, Any]] = []
    evidence_items: list[dict[str, Any]] = []
    stage_results: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    _write_research_artifact(evidence_root, "00-plan.json", plan)

    urls = _extract_urls(question)
    fetch_order = routes["capabilities"]["web_fetch"]["providers"]
    if urls:
        for index, url in enumerate(urls, 1):
            fetch_result, attempts = await _run_web_fetch_fallback(url, fallback=fallback_mode, preferred_order=fetch_order)
            provider_attempts.extend(attempts)
            stage_results.append({"stage": "known_url_fetch", "url": url, "ok": bool(fetch_result), "provider_attempts": attempts})
            if fetch_result:
                item = _research_evidence_item(
                    url=fetch_result["url"],
                    provider=fetch_result["provider"],
                    title=fetch_result["url"],
                    content=fetch_result["content"],
                    subquestion_id="sq1",
                )
                evidence_items.append(item)
                _write_research_artifact(evidence_root, f"{index:02d}-fetch-{fetch_result['provider']}.md", fetch_result["content"])
            else:
                gaps.append({"subquestion_id": "sq1", "reason": f"failed to fetch known URL: {url}", "url": url})

    signals = routes["signals"]
    if signals["docs_api_intent"]:
        docs_providers = routes["capabilities"]["docs_search"]["providers"]
        selected_docs_providers = docs_providers[:1] if fallback_mode == "off" else docs_providers
        if not selected_docs_providers:
            gaps.append({"subquestion_id": "sq2", "reason": "no configured docs_search provider for docs/API evidence"})
        for provider in selected_docs_providers:
            step_start = time.time()
            if provider == "context7":
                data = await context7_library(question, question)
                if data.get("ok") and data.get("results"):
                    provider_attempts.append(_attempt("docs_search", "context7", "ok", step_start, result_count=len(data.get("results") or [])))
                    stage_results.append({"stage": "docs_discovery", "provider": "context7", "ok": True, "result_count": len(data.get("results") or [])})
                    library_id = (data.get("results") or [{}])[0].get("id", "")
                    if library_id:
                        docs_start = time.time()
                        docs_data = await context7_docs(library_id, question)
                        if docs_data.get("ok") and docs_data.get("content"):
                            provider_attempts.append(_attempt("docs_search", "context7", "ok", docs_start, result_count=1))
                            item = _research_evidence_item(
                                url=f"context7:{library_id}",
                                provider="context7",
                                title=library_id,
                                content=docs_data.get("content", ""),
                                source_type="docs",
                                subquestion_id="sq2",
                            )
                            evidence_items.append(item)
                            _write_research_artifact(evidence_root, "docs-context7.md", docs_data.get("content", ""))
                            break
                        docs_status = "error" if docs_data.get("error_type") else "empty"
                        provider_attempts.append(_attempt("docs_search", "context7", docs_status, docs_start, error_type=docs_data.get("error_type", ""), error=docs_data.get("error", "")))
                    if fallback_mode == "off":
                        break
                    continue
                status = "error" if data.get("error_type") in {"auth_error", "timeout", "network_error", "runtime_error"} else "empty"
                provider_attempts.append(_attempt("docs_search", "context7", status, step_start, error_type=data.get("error_type", ""), error=data.get("error", "")))
            elif provider == "exa":
                data = await exa_search(question, num_results=5, include_highlights=True)
                if data.get("ok"):
                    sources = _normalize_source_results(data.get("results"), "exa")
                    if sources:
                        provider_attempts.append(_attempt("docs_search", "exa", "ok", step_start, result_count=len(sources)))
                        discovery_sources.extend(sources)
                        stage_results.append({"stage": "docs_discovery", "provider": "exa", "ok": True, "result_count": len(sources)})
                        break
                provider_attempts.append(_attempt("docs_search", "exa", "error" if data.get("error_type") else "empty", step_start, error_type=data.get("error_type", ""), error=data.get("error", "")))

    should_run_web_discovery = (
        signals["current_or_locale_intent"]
        or signals["cross_validation_need"] == "high"
        or (not evidence_items and not discovery_sources)
    ) and not (urls and fallback_mode == "off")
    if should_run_web_discovery:
        web_provider_order = routes["capabilities"]["web_search"]["providers"]
        if web_provider_order:
            web_sources, attempts = await _run_web_search_fallback(
                question,
                count=5,
                providers=",".join(web_provider_order),
                fallback=fallback_mode,
            )
            provider_attempts.extend(attempts)
            discovery_sources.extend(web_sources)
            stage_results.append({"stage": "web_discovery", "ok": bool(web_sources), "result_count": len(web_sources), "provider_attempts": attempts})
        else:
            gaps.append({"subquestion_id": "", "reason": "no configured web_search provider for discovery"})

    exa_in_selected_docs_route = "exa" in routes["capabilities"]["docs_search"]["providers"]
    if (
        fallback_mode != "off"
        and signals["official_low_noise_intent"]
        and exa_in_selected_docs_route
        and not any(source.get("provider") == "exa" for source in discovery_sources)
    ):
        exa_start = time.time()
        data = await exa_search(question, num_results=5, include_highlights=True)
        if data.get("ok"):
            sources = _normalize_source_results(data.get("results"), "exa")
            if sources:
                provider_attempts.append(_attempt("docs_search", "exa", "ok", exa_start, result_count=len(sources)))
                discovery_sources.extend(sources)
        else:
            provider_attempts.append(_attempt("docs_search", "exa", "error", exa_start, error_type=data.get("error_type", ""), error=data.get("error", "")))

    if signals["vertical_intent"] and routes["capabilities"]["vertical_search"]["providers"]:
        vertical_start = time.time()
        data = await anysearch_search(question, max_results=5)
        if data.get("ok"):
            sources = _normalize_source_results(data.get("results"), "anysearch")
            provider_attempts.append(_attempt("vertical_search", "anysearch", "ok" if sources else "empty", vertical_start, result_count=len(sources)))
            discovery_sources.extend(sources)
            stage_results.append({"stage": "vertical_discovery", "provider": "anysearch", "ok": bool(sources), "result_count": len(sources)})
        else:
            provider_attempts.append(_attempt("vertical_search", "anysearch", "error", vertical_start, error_type=data.get("error_type", ""), error=data.get("error", "")))

    candidates = _select_candidate_urls(discovery_sources, limit=6)
    fetched_urls = {item.get("url") for item in evidence_items}
    no_new_evidence = True
    for index, candidate in enumerate(candidates, 1):
        url = candidate.get("url", "")
        if not url or url in fetched_urls:
            continue
        order = _research_fetch_order(question, url)
        fetch_result, attempts = await _run_web_fetch_fallback(url, fallback=fallback_mode, preferred_order=order)
        provider_attempts.extend(attempts)
        stage_results.append({"stage": "candidate_fetch", "url": url, "ok": bool(fetch_result), "provider_attempts": attempts})
        if fetch_result:
            no_new_evidence = False
            fetched_urls.add(url)
            content = fetch_result.get("content", "")
            item = _research_evidence_item(
                url=fetch_result["url"],
                provider=fetch_result["provider"],
                title=candidate.get("title") or fetch_result["url"],
                content=content,
                subquestion_id=candidate.get("subquestion_id", ""),
            )
            evidence_items.append(item)
            _write_research_artifact(evidence_root, f"fetch-{index:02d}-{fetch_result['provider']}.md", content)
        elif fallback_mode == "off":
            gaps.append({"subquestion_id": "", "reason": f"fetch failed with fallback off: {url}", "url": url})

    if not evidence_items:
        gaps.append({"subquestion_id": "", "reason": "no fetched/read evidence items were produced"})
    elif no_new_evidence and not urls and candidates:
        gaps.append({"subquestion_id": "", "reason": "discovery produced candidates but no new fetch evidence converged"})

    covered = bool(evidence_items)
    gap_status = "closed" if covered and not gaps else ("degraded" if evidence_items else "failed")
    citations = _citation_items(evidence_items)
    final_answer = _evidence_only_synthesis(question, evidence_items, gaps)
    result = {
        "ok": bool(evidence_items),
        "error_type": "" if evidence_items else "evidence_error",
        "error": "" if evidence_items else "research could not obtain fetched evidence",
        "mode": "deep_research_execution",
        "query_mode": "research",
        "question": question,
        "budget": _deep_budget(budget or "deep"),
        "research_plan": plan,
        "routing_decision": routes,
        "stage_results": stage_results,
        "discovery_sources": discovery_sources,
        "final_answer": final_answer,
        "content": final_answer,
        "citations": citations,
        "evidence_items": evidence_items,
        "gap_check": {
            "status": gap_status,
            "gaps": gaps,
            "stop_reason": "evidence_converged" if gap_status == "closed" else ("degraded_with_gaps" if evidence_items else "provider_exhausted"),
        },
        "provider_attempts": provider_attempts,
        "providers_used": _provider_names_from_attempts(provider_attempts),
        "fallback_used": _fallback_used(provider_attempts),
        "degraded": bool(gaps),
        "route_policy_version": RESEARCH_ROUTE_POLICY_VERSION,
        "evidence_dir": evidence_root,
        "minimum_profile_ok": minimum.get("ok", False),
        "capability_status": minimum.get("capability_status", {}),
        "elapsed_ms": _elapsed_ms(start),
    }
    _write_research_artifact(evidence_root, "summary.json", result)
    return result


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
                    ("zhipu", bool(config.zhipu_api_key)),
                    ("zhipu-mcp", bool(config.zhipu_mcp_api_key)),
                    ("tavily", bool(config.tavily_api_key)),
                    ("firecrawl", bool(config.firecrawl_api_key)),
                ]
                if enabled
            ],
            "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl"],
        },
        "docs_search": {
            "configured": [
                name
                for name, enabled in [
                    ("context7", bool(config.context7_api_key)),
                    ("exa", bool(config.exa_api_key)),
                ]
                if enabled
            ],
            "fallback_chain": ["context7", "exa"],
        },
        "web_fetch": {
            "configured": [
                name
                for name, enabled in [
                    ("tavily", bool(config.tavily_api_key)),
                    ("jina", bool(config.jina_api_key)),
                    ("zhipu-mcp-reader", bool(config.zhipu_mcp_api_key)),
                    ("firecrawl", bool(config.firecrawl_api_key)),
                ]
                if enabled
            ],
            "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"],
        },
        "vertical_search": {
            "configured": ["anysearch"] if config.anysearch_api_key else [],
            "fallback_chain": ["anysearch"],
            "experimental": True,
        },
    }
    for capability in ("web_search", "docs_search", "web_fetch", "vertical_search"):
        status[capability]["ok"] = bool(status[capability]["configured"])
    return status


def _minimum_profile_result(profile: str, capability_status: dict[str, Any]) -> dict[str, Any]:
    required = [] if profile == "off" else ["main_search", "docs_search", "web_fetch"]
    missing = [capability for capability in required if not capability_status.get(capability, {}).get("ok")]
    return {
        "ok": not missing,
        "error_type": "config_error" if missing else "",
        "error": f"{MINIMUM_PROFILE_ERROR} 缺失能力: {', '.join(missing)}" if missing else "",
        "profile": profile,
        "required": required,
        "missing": missing,
        "capability_status": capability_status,
    }


def validate_minimum_profile() -> dict[str, Any]:
    try:
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
    configured: set[str] = set()

    if config.xai_api_key:
        configured.add("xai-responses")
    if config.openai_compatible_api_url and config.openai_compatible_api_key:
        configured.add("openai-compatible")

    return [provider for provider in MAIN_SEARCH_FALLBACK_CHAIN if provider in configured]


def _main_search_provider_configs(model_override: str = "", providers: str = "auto") -> list[dict[str, Any]]:
    provider_filter = _parse_provider_filter(providers)
    by_provider: dict[str, dict[str, Any]] = {}

    if config.xai_api_key:
        by_provider["xai-responses"] = {
            "provider": "xai-responses",
            "mode": "xai-responses",
            "api_url": config.xai_api_url,
            "api_key": config.xai_api_key,
            "model": model_override or config.xai_model,
            "tools": config.parse_xai_tools(config.xai_tools_raw),
            "source": "XAI_*",
        }

    if config.openai_compatible_api_url and config.openai_compatible_api_key:
        by_provider["openai-compatible"] = {
            "provider": "openai-compatible",
            "mode": "chat-completions",
            "api_url": config.openai_compatible_api_url,
            "api_key": config.openai_compatible_api_key,
            "model": model_override or config.openai_compatible_model,
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
                )
            )
        else:
            providers.append(
                OpenAICompatibleSearchProvider(
                    provider_config["api_url"],
                    provider_config["api_key"],
                    provider_config["model"],
                    provider_config.get("stream", False),
                )
            )
    return providers


async def fetch_available_models(api_url: str, api_key: str) -> list[str]:
    models_url = f"{api_url.rstrip('/')}/models"
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


def extra_results_to_sources(
    tavily_results: list[dict] | None,
    firecrawl_results: list[dict] | None,
) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()

    if firecrawl_results:
        for r in firecrawl_results:
            url = (r.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            item: dict = {"url": url, "provider": "firecrawl"}
            title = (r.get("title") or "").strip()
            if title:
                item["title"] = title
            desc = (r.get("description") or "").strip()
            if desc:
                item["description"] = desc
            sources.append(item)

    if tavily_results:
        for r in tavily_results:
            url = (r.get("url") or "").strip()
            if not url or url in seen:
                continue
            seen.add(url)
            item = {"url": url, "provider": "tavily"}
            title = (r.get("title") or "").strip()
            if title:
                item["title"] = title
            content = (r.get("content") or "").strip()
            if content:
                item["description"] = content
            sources.append(item)

    return sources


async def _run_web_fetch_fallback(
    url: str,
    fallback: str = "auto",
    preferred_order: list[str] | None = None,
) -> tuple[dict[str, Any] | None, list[dict]]:
    attempts: list[dict] = []
    providers = []
    if config.tavily_api_key:
        providers.append("tavily")
    if config.jina_api_key:
        providers.append("jina")
    if config.zhipu_mcp_api_key:
        providers.append("zhipu-mcp-reader")
    if config.firecrawl_api_key:
        providers.append("firecrawl")
    if preferred_order:
        allowed = {provider for provider in providers}
        ordered = [provider for provider in preferred_order if provider in allowed]
        ordered.extend(provider for provider in providers if provider not in ordered)
        providers = ordered
    if fallback == "off":
        providers = providers[:1]

    for provider in providers:
        start = time.time()
        try:
            if provider == "tavily":
                content = await call_tavily_extract(url)
            elif provider == "jina":
                data = await jina_fetch(url)
                content = data.get("content") if data.get("ok") else None
                if not data.get("ok"):
                    status = "error" if data.get("error_type") in {"auth_error", "config_error", "parameter_error", "quality_error", "rate_limited", "timeout", "network_error", "runtime_error"} else "empty"
                    attempts.append(_attempt("web_fetch", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", "")))
                    continue
            elif provider == "zhipu-mcp-reader":
                data = await zhipu_mcp_reader(url)
                content = data.get("content") if data.get("ok") else None
                if not data.get("ok"):
                    status = "error" if data.get("error_type") in {"auth_error", "config_error", "provider_error", "rate_limited", "timeout", "network_error", "runtime_error"} else "empty"
                    attempts.append(_attempt("web_fetch", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", "")))
                    continue
            else:
                content = await call_firecrawl_scrape(url)
            if content and content.strip():
                attempts.append(_attempt("web_fetch", provider, "ok", start, result_count=1))
                return {
                    "ok": True,
                    "url": url,
                    "provider": provider,
                    "content": content,
                }, attempts
            attempts.append(_attempt("web_fetch", provider, "empty", start))
        except Exception as e:
            attempts.append(_attempt("web_fetch", provider, "error", start, error_type="runtime_error", error=str(e)))
    return None, attempts


async def _run_web_search_fallback(
    query: str,
    count: int = 5,
    providers: str = "auto",
    fallback: str = "auto",
) -> tuple[list[dict], list[dict]]:
    provider_filter = _parse_provider_filter(providers)
    attempts: list[dict] = []
    configured: list[str] = []
    if config.zhipu_api_key:
        configured.append("zhipu")
    if config.zhipu_mcp_api_key:
        configured.append("zhipu-mcp")
    if config.tavily_api_key:
        configured.append("tavily")
    if config.firecrawl_api_key:
        configured.append("firecrawl")
    if provider_filter is not None:
        configured = [p for p in configured if p in provider_filter]
    if fallback == "off":
        configured = configured[:1]

    for provider in configured:
        start = time.time()
        try:
            if provider == "zhipu":
                data = await zhipu_search(query, count=count)
                if data.get("ok"):
                    sources = _normalize_source_results(data.get("results"), "zhipu")
                    if sources:
                        attempts.append(_attempt("web_search", provider, "ok", start, result_count=len(sources)))
                        return sources, attempts
                status = "error" if data.get("error_type") in {"rate_limited", "auth_error", "timeout", "network_error", "runtime_error"} else "empty"
                attempts.append(_attempt("web_search", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", "")))
            elif provider == "zhipu-mcp":
                data = await zhipu_mcp_search(query, count=count)
                if data.get("ok"):
                    sources = _normalize_source_results(data.get("results"), "zhipu-mcp")
                    if sources:
                        attempts.append(_attempt("web_search", provider, "ok", start, result_count=len(sources)))
                        return sources, attempts
                status = "error" if data.get("error_type") in {"rate_limited", "auth_error", "timeout", "network_error", "runtime_error", "provider_error"} else "empty"
                attempts.append(_attempt("web_search", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", "")))
            elif provider == "tavily":
                results = await call_tavily_search(query, count)
                sources = _normalize_source_results(results, "tavily")
                if sources:
                    attempts.append(_attempt("web_search", provider, "ok", start, result_count=len(sources)))
                    return sources, attempts
                attempts.append(_attempt("web_search", provider, "empty", start))
            elif provider == "firecrawl":
                results = await call_firecrawl_search(query, count)
                sources = _normalize_source_results(results, "firecrawl")
                if sources:
                    attempts.append(_attempt("web_search", provider, "ok", start, result_count=len(sources)))
                    return sources, attempts
                attempts.append(_attempt("web_search", provider, "empty", start))
        except Exception as e:
            attempts.append(_attempt("web_search", provider, "error", start, error_type="runtime_error", error=str(e)))
    return [], attempts


async def _run_docs_search_fallback(
    query: str,
    providers: str = "auto",
    fallback: str = "auto",
) -> tuple[list[dict], list[dict]]:
    provider_filter = _parse_provider_filter(providers)
    attempts: list[dict] = []
    configured: list[str] = []
    if config.context7_api_key:
        configured.append("context7")
    if config.exa_api_key:
        configured.append("exa")
    if provider_filter is not None:
        configured = [p for p in configured if p in provider_filter]
    if fallback == "off":
        configured = configured[:1]

    for provider in configured:
        start = time.time()
        try:
            if provider == "exa":
                data = await exa_search(query, num_results=5, include_highlights=True)
                if data.get("ok"):
                    sources = _normalize_source_results(data.get("results"), "exa")
                    if sources:
                        attempts.append(_attempt("docs_search", provider, "ok", start, result_count=len(sources)))
                        return sources, attempts
                status = "error" if data.get("error_type") in {"auth_error", "parameter_error", "rate_limited", "timeout", "network_error", "runtime_error"} else "empty"
                attempts.append(_attempt("docs_search", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", "")))
            elif provider == "context7":
                data = await context7_library(query, query)
                if data.get("ok"):
                    sources = [
                        {
                            "url": f"context7:{item.get('id')}",
                            "title": item.get("title") or item.get("id") or "Context7",
                            "description": item.get("description") or "",
                            "provider": "context7",
                        }
                        for item in data.get("results", [])
                        if item.get("id")
                    ]
                    if sources:
                        attempts.append(_attempt("docs_search", provider, "ok", start, result_count=len(sources)))
                        return sources, attempts
                status = "error" if data.get("error_type") in {"auth_error", "timeout", "network_error", "runtime_error"} else "empty"
                attempts.append(_attempt("docs_search", provider, status, start, error_type=data.get("error_type", ""), error=data.get("error", "")))
        except Exception as e:
            attempts.append(_attempt("docs_search", provider, "error", start, error_type="runtime_error", error=str(e)))
    return [], attempts


async def call_tavily_extract(url: str) -> str | None:
    api_key = config.tavily_api_key
    if not api_key:
        return None
    endpoint = f"{config.tavily_api_url.rstrip('/')}/extract"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"urls": [url], "format": "markdown"}
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            data = response.json()
            if data.get("results") and len(data["results"]) > 0:
                content = data["results"][0].get("raw_content", "")
                return content if content and content.strip() else None
            return None
    except Exception:
        return None


async def call_tavily_search(query: str, max_results: int = 6) -> list[dict] | None:
    api_key = config.tavily_api_key
    if not api_key:
        return None
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
            data = response.json()
            results = data.get("results", [])
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score", 0),
                }
                for r in results
            ] if results else None
    except Exception:
        return None


async def call_firecrawl_search(query: str, limit: int = 14) -> list[dict] | None:
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
            data = response.json()
            results = data.get("data", {}).get("web", [])
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "description": r.get("description", ""),
                }
                for r in results
            ] if results else None
    except Exception:
        return None


async def call_firecrawl_scrape(url: str, ctx=None) -> str | None:
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
                data = response.json()
                markdown = data.get("data", {}).get("markdown", "")
                if markdown and markdown.strip():
                    return markdown
                await log_info(ctx, f"Firecrawl: markdown为空, 重试 {attempt + 1}/{config.retry_max_attempts}", config.debug_enabled)
        except Exception as e:
            await log_info(ctx, f"Firecrawl error: {e}", config.debug_enabled)
            return None
    return None


async def call_jina_reader(url: str) -> dict[str, Any]:
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
    api_key = config.tavily_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": "TAVILY_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set TAVILY_API_KEY <key>`。",
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
            data = response.json()
            return {
                "ok": True,
                "base_url": data.get("base_url", ""),
                "results": data.get("results", []),
                "response_time": data.get("response_time", 0),
            }
    except httpx.TimeoutException:
        return {"ok": False, "error_type": "network_error", "error": f"映射超时: 请求超过{timeout}秒"}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error_type": "network_error", "error": f"HTTP错误: {e.response.status_code} - {e.response.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error_type": "network_error", "error": f"映射错误: {str(e)}"}


async def search(
    query: str,
    platform: str = "",
    model: str = "",
    extra_sources: int = 0,
    validation: str = "",
    fallback: str = "",
    providers: str = "auto",
    stream: bool | None = None,
) -> dict[str, Any]:
    start = time.time()
    session_id = new_session_id()
    try:
        validation_level = (validation or config.validation_level).strip().lower()
        fallback_mode = (fallback or config.fallback_mode).strip().lower()
        if validation_level not in config._ALLOWED_VALIDATION_LEVELS:
            raise ValueError(f"Invalid validation level: {validation_level}")
        if fallback_mode not in config._ALLOWED_FALLBACK_MODES:
            raise ValueError(f"Invalid fallback mode: {fallback_mode}")
    except ValueError as e:
        return _empty_search_result(start, session_id, query, "parameter_error", str(e))

    minimum = validate_minimum_profile()
    if not minimum.get("ok"):
        return _empty_search_result(
            start,
            session_id,
            query,
            minimum.get("error_type", "config_error"),
            minimum.get("error", MINIMUM_PROFILE_ERROR),
            extra={
                "capability_status": minimum.get("capability_status", {}),
                "minimum_profile_ok": False,
                "validation_level": validation_level,
            },
        )

    try:
        main_provider_configs = _main_search_provider_configs(model_override=model, providers=providers)
    except ValueError as e:
        return _empty_search_result(start, session_id, query, "parameter_error", str(e), extra={"validation_level": validation_level})

    if not main_provider_configs:
        return _empty_search_result(
            start,
            session_id,
            query,
            "config_error",
            "No configured main_search provider matches --providers.",
            extra={
                "validation_level": validation_level,
                "capability_status": minimum.get("capability_status", {}),
                "minimum_profile_ok": minimum.get("ok", False),
            },
        )

    primary_api_mode = main_provider_configs[0]["mode"]
    if stream is not None:
        for provider_config in main_provider_configs:
            if provider_config["provider"] == "openai-compatible":
                provider_config["stream"] = stream

    has_tavily = bool(config.tavily_api_key)
    has_firecrawl = bool(config.firecrawl_api_key)
    tavily_count = 0
    firecrawl_count = 0
    if extra_sources > 0:
        if has_tavily and has_firecrawl:
            tavily_count = max(1, round(extra_sources * 0.6))
            firecrawl_count = extra_sources - tavily_count
        elif has_tavily:
            tavily_count = extra_sources
        elif has_firecrawl:
            firecrawl_count = extra_sources

    docs_intent = _is_docs_intent(query)
    zh_current_intent = _is_zh_current_intent(query)
    web_current_intent = zh_current_intent
    fetch_urls = _extract_urls(query)
    fetch_intent = bool(fetch_urls) or _is_fetch_intent(query)
    supplemental_paths: list[str] = []
    if docs_intent:
        supplemental_paths.append("docs_search")
    if web_current_intent or validation_level == "strict":
        supplemental_paths.append("web_search")
    if fetch_intent:
        supplemental_paths.append("web_fetch")
    selected_main_provider_configs = main_provider_configs if fallback_mode != "off" else main_provider_configs[:1]
    routing_decision = {
        "docs_intent": docs_intent,
        "zh_current_intent": zh_current_intent,
        "web_current_intent": web_current_intent,
        "fetch_intent": fetch_intent,
        "supplemental_paths": supplemental_paths,
        "validation_level": validation_level,
        "fallback_mode": fallback_mode,
        "providers": providers,
        "main_search_chain": [item["provider"] for item in selected_main_provider_configs],
        "openai_compatible_stream": next((bool(item.get("stream")) for item in selected_main_provider_configs if item["provider"] == "openai-compatible"), False),
    }

    provider_attempts: list[dict] = []
    main_providers = _main_search_providers(main_provider_configs, fallback_mode)
    primary_start = time.time()
    primary_result = None
    successful_main_config: dict[str, Any] | None = None
    last_primary_error: dict[str, Any] | None = None
    for provider_config, search_provider in zip(selected_main_provider_configs, main_providers):
        primary_start = time.time()
        try:
            candidate_result = await search_provider.search(query, platform)
            if candidate_result:
                primary_result = candidate_result
                successful_main_config = provider_config
                provider_attempts.append(_attempt("main_search", search_provider.get_provider_name(), "ok", primary_start, result_count=1))
                break
            last_primary_error = _primary_search_error_result(
                start,
                session_id,
                query,
                provider_config["mode"],
                "network_error",
                f"{search_provider.get_provider_name()} 返回空结果",
            )
            provider_attempts.append(_attempt("main_search", search_provider.get_provider_name(), "empty", primary_start))
        except Exception as e:
            error_result = _primary_search_exception_result(start, session_id, query, provider_config["mode"], search_provider.get_provider_name(), e)
            last_primary_error = error_result
            provider_attempts.append(
                _attempt(
                    "main_search",
                    search_provider.get_provider_name(),
                    "error",
                    primary_start,
                    error_type=error_result["error_type"],
                    error=error_result["error"],
                )
            )
    if primary_result is None:
        result = last_primary_error or _primary_search_error_result(start, session_id, query, primary_api_mode, "network_error", "搜索失败或无结果")
        result["provider_attempts"] = provider_attempts
        result["providers_used"] = _provider_names_from_attempts(provider_attempts)
        result["fallback_used"] = _fallback_used(provider_attempts)
        result["routing_decision"] = routing_decision
        result["validation_level"] = validation_level
        result["minimum_profile_ok"] = minimum.get("ok", False)
        result["capability_status"] = minimum.get("capability_status", {})
        return result

    successful_main_config = successful_main_config or selected_main_provider_configs[0]
    primary_api_mode = successful_main_config["mode"]
    effective_model = successful_main_config["model"]

    coros: list[Any] = []
    if tavily_count:
        coros.append(call_tavily_search(query, tavily_count))
    if firecrawl_count:
        coros.append(call_firecrawl_search(query, firecrawl_count))

    gathered = await asyncio.gather(*coros, return_exceptions=True)
    primary_result = primary_result or ""
    tavily_results: list[dict] | None = None
    firecrawl_results: list[dict] | None = None
    idx = 0
    if tavily_count:
        tavily_results = None if isinstance(gathered[idx], BaseException) else gathered[idx]
        idx += 1
    if firecrawl_count:
        firecrawl_results = None if isinstance(gathered[idx], BaseException) else gathered[idx]

    answer, primary_sources = split_answer_and_sources(primary_result)
    extra_source_items = extra_results_to_sources(tavily_results, firecrawl_results)
    for item_provider, results in (("tavily", tavily_results), ("firecrawl", firecrawl_results)):
        if results:
            provider_attempts.append(_attempt("web_search", item_provider, "ok", start, result_count=len(results)))

    supplemental_sources: list[dict] = []
    if validation_level in {"balanced", "strict"}:
        if docs_intent:
            docs_sources, docs_attempts = await _run_docs_search_fallback(query, providers=providers, fallback=fallback_mode)
            provider_attempts.extend(docs_attempts)
            supplemental_sources.extend(docs_sources)
        if web_current_intent or validation_level == "strict":
            web_sources, web_attempts = await _run_web_search_fallback(query, count=max(1, extra_sources or 3), providers=providers, fallback=fallback_mode)
            provider_attempts.extend(web_attempts)
            supplemental_sources.extend(web_sources)
        if fetch_intent:
            fetch_url = fetch_urls[0] if fetch_urls else query.strip()
            fetch_result, fetch_attempts = await _run_web_fetch_fallback(fetch_url, fallback=fallback_mode)
            provider_attempts.extend(fetch_attempts)
            if fetch_result:
                supplemental_sources.append({"url": fetch_result["url"], "provider": fetch_result["provider"], "description": fetch_result["content"][:300]})

    extra_source_items = merge_sources(extra_source_items, supplemental_sources)
    sources = merge_sources(primary_sources, extra_source_items)
    ok = bool(answer or sources)
    if validation_level == "strict" and not sources:
        ok = False
    return {
        "ok": ok,
        "error_type": "" if ok else ("evidence_error" if validation_level == "strict" else "network_error"),
        "error": "" if ok else ("strict 模式证据不足" if validation_level == "strict" else "搜索失败或无结果"),
        "session_id": session_id,
        "query": query,
        "platform": platform,
        "model": effective_model,
        "primary_api_mode": primary_api_mode,
        "content": answer,
        "sources": sources,
        "sources_count": len(sources),
        "primary_sources": primary_sources,
        "primary_sources_count": len(primary_sources),
        "extra_sources": extra_source_items,
        "extra_sources_count": len(extra_source_items),
        "source_warning": SOURCE_PROVENANCE_WARNING if extra_source_items else "",
        "routing_decision": routing_decision,
        "providers_used": _provider_names_from_attempts(provider_attempts),
        "provider_attempts": provider_attempts,
        "fallback_used": _fallback_used(provider_attempts),
        "validation_level": validation_level,
        "minimum_profile_ok": minimum.get("ok", False),
        "capability_status": minimum.get("capability_status", {}),
        "elapsed_ms": _elapsed_ms(start),
    }


def _primary_search_exception_result(
    start: float,
    session_id: str,
    query: str,
    primary_api_mode: str,
    provider_name: str,
    exc: BaseException,
) -> dict[str, Any]:
    if isinstance(exc, httpx.TimeoutException):
        return _primary_search_error_result(
            start,
            session_id,
            query,
            primary_api_mode,
            "network_error",
            f"{provider_name} 请求超时: {str(exc)}",
        )
    if isinstance(exc, httpx.HTTPStatusError):
        body = exc.response.text[:300] if exc.response is not None else str(exc)
        status = exc.response.status_code if exc.response is not None else "unknown"
        return _primary_search_error_result(
            start,
            session_id,
            query,
            primary_api_mode,
            "network_error",
            f"{provider_name} HTTP {status}: {body}",
        )
    if isinstance(exc, httpx.RequestError):
        return _primary_search_error_result(
            start,
            session_id,
            query,
            primary_api_mode,
            "network_error",
            f"{provider_name} 网络错误: {str(exc)}",
        )
    return _primary_search_error_result(
        start,
        session_id,
        query,
        primary_api_mode,
        "runtime_error",
        f"{provider_name} 运行错误: {str(exc)}",
    )


def _primary_search_error_result(
    start: float,
    session_id: str,
    query: str,
    primary_api_mode: str,
    error_type: str,
    error: str,
) -> dict[str, Any]:
    return {
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
        "elapsed_ms": _elapsed_ms(start),
    }


async def fetch(url: str) -> dict[str, Any]:
    start = time.time()
    fetch_result, attempts = await _run_web_fetch_fallback(url)
    if fetch_result:
        return {
            **fetch_result,
            "provider_attempts": attempts,
            "fallback_used": _fallback_used(attempts),
            "elapsed_ms": _elapsed_ms(start),
        }

    if not (config.tavily_api_key or config.jina_api_key or config.zhipu_mcp_api_key or config.firecrawl_api_key):
        error = "TAVILY_API_KEY、JINA_API_KEY、ZHIPU_MCP_API_KEY 和 FIRECRAWL_API_KEY 均未配置"
        error_type = "config_error"
    else:
        error = "所有提取服务均未能获取内容"
        error_type = "network_error"
    return {
        "ok": False,
        "url": url,
        "provider": "",
        "content": "",
        "error_type": error_type,
        "error": error,
        "provider_attempts": attempts,
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
    api_key = config.exa_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": "EXA_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set EXA_API_KEY <key>`。",
        }

    provider = ExaSearchProvider(config.exa_base_url, api_key, config.exa_timeout)
    include_domain_list = _normalize_domain_filter(include_domains)
    exclude_domain_list = _normalize_domain_filter(exclude_domains)

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
        return {"ok": False, "error_type": "parse_error", "error": raw}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


def _anysearch_provider() -> AnySearchProvider:
    return AnySearchProvider(config.anysearch_api_url, config.anysearch_api_key, config.anysearch_timeout)


async def _decode_provider_json(raw: str, provider: str = "anysearch") -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "provider": provider, "error_type": "parse_error", "error": raw}


async def anysearch_domains(domain: str = "") -> dict[str, Any]:
    return await _decode_provider_json(await _anysearch_provider().list_domains(domain))


async def anysearch_search(query: str, domain: str = "", sub_domain: str = "", max_results: int = 5) -> dict[str, Any]:
    return await _decode_provider_json(
        await _anysearch_provider().vertical_search(
            query=query,
            domain=domain,
            sub_domain=sub_domain,
            max_results=max_results,
        )
    )


async def anysearch_extract(url: str, max_length: int = 20000) -> dict[str, Any]:
    return await _decode_provider_json(await _anysearch_provider().extract(url, max_length=max_length))


async def anysearch_batch(queries: list[str], max_results: int = 3) -> dict[str, Any]:
    return await _decode_provider_json(await _anysearch_provider().batch_search(queries, max_results=max_results))


def _zhipu_mcp_search_provider() -> ZhipuMCPProvider:
    return ZhipuMCPProvider(
        config.zhipu_mcp_search_api_url,
        config.zhipu_mcp_api_key or "",
        config.zhipu_mcp_timeout,
        provider_id="zhipu-mcp",
    )


def _zhipu_mcp_reader_provider() -> ZhipuMCPProvider:
    return ZhipuMCPProvider(
        config.zhipu_mcp_reader_api_url,
        config.zhipu_mcp_api_key or "",
        config.zhipu_mcp_timeout,
        provider_id="zhipu-mcp-reader",
    )


def _zhipu_mcp_zread_provider() -> ZhipuMCPProvider:
    return ZhipuMCPProvider(
        config.zhipu_mcp_zread_api_url,
        config.zhipu_mcp_api_key or "",
        config.zhipu_mcp_timeout,
        provider_id="zhipu-mcp-zread",
    )


async def jina_fetch(url: str) -> dict[str, Any]:
    return await call_jina_reader(url)


async def zhipu_mcp_search(query: str, count: int = 5) -> dict[str, Any]:
    return await _decode_provider_json(await _zhipu_mcp_search_provider().web_search(query, count=count), provider="zhipu-mcp")


async def zhipu_mcp_reader(url: str) -> dict[str, Any]:
    return await _decode_provider_json(await _zhipu_mcp_reader_provider().web_reader(url), provider="zhipu-mcp-reader")


async def zhipu_mcp_search_doc(repo: str, query: str, max_results: int = 5) -> dict[str, Any]:
    return await _decode_provider_json(await _zhipu_mcp_zread_provider().search_doc(repo, query, max_results=max_results), provider="zhipu-mcp-zread")


async def zhipu_mcp_repo_structure(repo: str, ref: str = "") -> dict[str, Any]:
    return await _decode_provider_json(await _zhipu_mcp_zread_provider().get_repo_structure(repo, ref=ref), provider="zhipu-mcp-zread")


async def zhipu_mcp_read_file(repo: str, path: str, ref: str = "") -> dict[str, Any]:
    return await _decode_provider_json(await _zhipu_mcp_zread_provider().read_file(repo, path, ref=ref), provider="zhipu-mcp-zread")


async def exa_find_similar(url: str, num_results: int = 5) -> dict[str, Any]:
    api_key = config.exa_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": "EXA_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set EXA_API_KEY <key>`。",
        }

    provider = ExaSearchProvider(config.exa_base_url, api_key, config.exa_timeout)
    raw = await provider.find_similar(url=url, num_results=num_results)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": raw}
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
    api_key = config.zhipu_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": "ZHIPU_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set ZHIPU_API_KEY <key>`。",
        }
    provider = ZhipuWebSearchProvider(
        config.zhipu_api_url,
        api_key,
        search_engine or config.zhipu_search_engine,
        config.zhipu_timeout,
    )
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
        return {"ok": False, "error_type": "parse_error", "error": raw}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def context7_library(name: str, query: str = "") -> dict[str, Any]:
    api_key = config.context7_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": "CONTEXT7_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set CONTEXT7_API_KEY <key>`。",
        }
    provider = Context7Provider(config.context7_base_url, api_key, config.context7_timeout)
    raw = await provider.library(name, query)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": raw}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def context7_docs(library_id: str, query: str) -> dict[str, Any]:
    api_key = config.context7_api_key
    if not api_key:
        return {
            "ok": False,
            "error_type": "config_error",
            "error": "CONTEXT7_API_KEY 未配置。请运行 `smart-search setup`，或使用 `smart-search config set CONTEXT7_API_KEY <key>`。",
        }
    provider = Context7Provider(config.context7_base_url, api_key, config.context7_timeout)
    raw = await provider.docs(library_id, query)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error_type": "parse_error", "error": raw}
    if not data.get("ok", False):
        data.setdefault("error_type", "network_error")
    return data


async def _test_primary_chat_completion(api_url: str, api_key: str, model: str) -> dict[str, Any]:
    chat_url = f"{api_url.rstrip('/')}/chat/completions"
    start = time.time()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            chat_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": "Reply with exactly: ok"}],
                "stream": False,
                "max_tokens": 8,
            },
        )
        response_time = _elapsed_ms(start)
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200:
            return {
                "status": "warning",
                "message": f"HTTP {response.status_code}: {response.text[:100]}",
                "response_time_ms": response_time,
                "http_status": response.status_code,
                "content_type": content_type,
                "has_content": bool(response.text.strip()),
            }
        return {
            "status": "ok",
            "message": f"聊天接口可用 (HTTP {response.status_code})",
            "response_time_ms": response_time,
            "http_status": response.status_code,
            "content_type": content_type,
            "has_content": bool(response.text.strip()),
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
            "OpenAI-compatible 主链路正常。",
            "真实 search 形态的 stream=false 和 stream=true 都能返回。若用户仍卡住，更可能是调用方、PATH、超时设置或上游偶发波动。",
        )
    if stream_ok and not no_stream_ok:
        return (
            False,
            "非流式请求不稳定，流式请求可用。",
            "建议设置 `OPENAI_COMPATIBLE_STREAM=true`，或临时使用 `smart-search search ... --stream`。",
        )
    if no_stream_ok and not stream_ok:
        return (
            False,
            "流式请求不稳定，非流式请求可用。",
            "建议设置 `OPENAI_COMPATIBLE_STREAM=false`，或临时使用 `smart-search search ... --no-stream`。",
        )
    if quick_ok and search_timeout:
        return (
            False,
            "小请求能通，但真实 search 形态超时。",
            "这通常是上游模型或中转站在处理 smart-search 的完整 prompt 时卡住；建议换模型/中转，或把本诊断报告贴给维护者。",
        )
    if quick_ok:
        return (
            False,
            "小请求能通，但真实 search 形态失败。",
            "这更像上游模型/中转站对 smart-search 请求形态不兼容；建议换模型/中转，或把本诊断报告贴给维护者。",
        )
    return (
        False,
        "OpenAI-compatible 基础请求不可用。",
        "请先检查 API URL、API key、模型名和网络；修好后再运行本诊断命令。",
    )


async def _probe_openai_compatible_search_shape(
    api_url: str,
    api_key: str,
    model: str,
    *,
    stream: bool,
    timeout_seconds: float,
) -> dict[str, Any]:
    name = "真实 search 请求 (stream=true)" if stream else "真实 search 请求 (stream=false)"
    start = time.time()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": search_prompt},
            {"role": "user", "content": get_local_time_info() + "\nping"},
        ],
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "smart-search/diagnose",
    }
    timeout = httpx.Timeout(connect=6.0, read=timeout_seconds, write=10.0, pool=None)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, verify=config.ssl_verify_enabled) as client:
            if stream:
                async with client.stream(
                    "POST",
                    f"{api_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as response:
                    content_type = response.headers.get("content-type", "")
                    response.raise_for_status()
                    has_content = False
                    async for line in response.aiter_lines():
                        stripped = line.strip()
                        if not stripped:
                            continue
                        if not stripped.startswith("data:"):
                            continue
                        if stripped in ("data: [DONE]", "data:[DONE]"):
                            continue
                        try:
                            data = json.loads(stripped[5:].lstrip())
                        except json.JSONDecodeError:
                            continue
                        choices = data.get("choices", []) if isinstance(data, dict) else []
                        if not choices:
                            continue
                        delta = choices[0].get("delta", {})
                        if isinstance(delta, dict) and str(delta.get("content") or "").strip():
                            has_content = True
                            break
                        message = choices[0].get("message", {})
                        if isinstance(message, dict) and str(message.get("content") or "").strip():
                            has_content = True
                            break
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
                f"{api_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            content_type = response.headers.get("content-type", "")
            response.raise_for_status()
            content = await OpenAICompatibleSearchProvider(api_url, api_key, model, stream=False)._parse_completion_response(response)
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
        return _diagnose_check_result(name=name, status="timeout", message=f"请求超时: {e}", start=start, stream=stream)
    except httpx.HTTPStatusError as e:
        body = e.response.text[:200] if e.response is not None else str(e)
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
        return _diagnose_check_result(name=name, status="error", message=f"网络错误: {e}", start=start, stream=stream)
    except Exception as e:
        return _diagnose_check_result(name=name, status="error", message=f"运行错误: {e}", start=start, stream=stream)


async def diagnose_openai_compatible(timeout_seconds: float = 30.0) -> dict[str, Any]:
    start = time.time()
    api_url = config.openai_compatible_api_url
    api_key = config.openai_compatible_api_key
    model = config.openai_compatible_model
    info = config.config_path_info()
    result: dict[str, Any] = {
        "ok": False,
        "provider": "openai-compatible",
        "api_url": api_url or "未配置",
        "api_key": config._mask_api_key(api_key) if api_key else "未配置",
        "model": model,
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
                "error": "缺少 OpenAI-compatible 配置: " + ", ".join(missing),
                "summary": "OpenAI-compatible 配置不完整。",
                "recommendation": "请先运行 `smart-search setup`，或用 `smart-search config set` 填好缺失项。",
                "missing": missing,
                "elapsed_ms": _elapsed_ms(start),
            }
        )
        return result

    try:
        quick = await _test_primary_chat_completion(api_url, api_key, model)
    except httpx.TimeoutException as e:
        quick = {"status": "timeout", "message": f"轻量 chat 请求超时: {e}"}
    except httpx.RequestError as e:
        quick = {"status": "error", "message": f"轻量 chat 网络错误: {e}"}
    except Exception as e:
        quick = {"status": "error", "message": f"轻量 chat 运行错误: {e}"}
    quick_check = {
        "name": "轻量 chat 请求",
        "status": quick.get("status", "error"),
        "message": quick.get("message", ""),
        "response_time_ms": quick.get("response_time_ms"),
        "http_status": quick.get("http_status"),
        "content_type": quick.get("content_type", ""),
        "has_content": bool(quick.get("has_content", quick.get("status") == "ok")),
    }
    result["checks"].append(quick_check)
    no_stream = await _probe_openai_compatible_search_shape(api_url, api_key, model, stream=False, timeout_seconds=timeout_seconds)
    result["checks"].append(no_stream)
    stream = await _probe_openai_compatible_search_shape(api_url, api_key, model, stream=True, timeout_seconds=timeout_seconds)
    result["checks"].append(stream)

    ok, summary, recommendation = _openai_compatible_diagnosis(quick_check, no_stream, stream)
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


async def _test_primary_connection(api_url: str, api_key: str, model: str) -> dict[str, Any]:
    chat_test = await _test_primary_chat_completion(api_url, api_key, model)

    models_url = f"{api_url.rstrip('/')}/models"
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            response_time = _elapsed_ms(start)
            if response.status_code != 200:
                models_test = {"status": "warning", "message": f"HTTP {response.status_code}: {response.text[:100]}", "response_time_ms": response_time}
            else:
                models_test = {"status": "ok", "message": f"成功获取模型列表 (HTTP {response.status_code})", "response_time_ms": response_time}
                try:
                    models_data = response.json()
                    model_names = [m["id"] for m in models_data.get("data", []) if isinstance(m, dict) and "id" in m]
                    models_test["message"] += f"，共 {len(model_names)} 个模型"
                    if model_names:
                        models_test["available_models"] = model_names
                except Exception:
                    pass
    except httpx.HTTPError as e:
        models_test = {"status": "warning", "message": f"模型列表接口请求失败: {e}", "response_time_ms": _elapsed_ms(start)}

    if chat_test.get("status") != "ok":
        models_state = "可用" if models_test.get("status") == "ok" else "不可用"
        return {
            "status": "warning",
            "message": f"聊天接口不可用: {chat_test.get('message', '')}；模型列表接口{models_state}: {models_test['message']}",
            "response_time_ms": chat_test.get("response_time_ms", models_test.get("response_time_ms")),
            "models_endpoint_test": models_test,
            "chat_completion_test": chat_test,
        }

    if models_test.get("status") != "ok":
        return {
            "status": "ok",
            "message": f"{chat_test['message']}；模型列表接口不可用: {models_test['message']}",
            "response_time_ms": chat_test.get("response_time_ms"),
            "models_endpoint_test": models_test,
            "chat_completion_test": chat_test,
        }

    result: dict[str, Any] = {
        "status": "ok",
        "message": f"{chat_test['message']}；{models_test['message']}",
        "response_time_ms": chat_test.get("response_time_ms"),
        "models_endpoint_test": models_test,
        "chat_completion_test": chat_test,
    }
    if "available_models" in models_test:
        result["available_models"] = models_test["available_models"]
    return result


async def _test_primary_responses(api_url: str, api_key: str, model: str) -> dict[str, Any]:
    responses_url = f"{api_url.rstrip('/')}/responses"
    start = time.time()
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            responses_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "input": [{"role": "user", "content": "Reply with exactly: ok"}],
                "stream": False,
            },
        )
        response_time = _elapsed_ms(start)
        if response.status_code != 200:
            return {"status": "warning", "message": f"HTTP {response.status_code}: {response.text[:100]}", "response_time_ms": response_time}
        return {"status": "ok", "message": f"xAI Responses API 可用 (HTTP {response.status_code})", "response_time_ms": response_time}


async def _test_main_provider_connection(provider_config: dict[str, Any]) -> dict[str, Any]:
    if provider_config["mode"] == "xai-responses":
        return await _test_primary_responses(provider_config["api_url"], provider_config["api_key"], provider_config["model"])
    return await _test_primary_connection(provider_config["api_url"], provider_config["api_key"], provider_config["model"])


async def _safe_test_main_provider_connection(provider_config: dict[str, Any]) -> dict[str, Any]:
    try:
        return await _test_main_provider_connection(provider_config)
    except httpx.TimeoutException:
        return {"status": "timeout", "message": f"{provider_config['provider']} 请求超时，请检查网络连接或 API URL"}
    except httpx.RequestError as e:
        return {"status": "error", "message": f"{provider_config['provider']} 网络错误: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"{provider_config['provider']} 未知错误: {str(e)}"}


async def _test_exa_connection() -> dict[str, Any]:
    exa_key = config.exa_api_key
    if not exa_key:
        return {"status": "not_configured", "message": "EXA_API_KEY 未设置，Exa 搜索功能不可用"}
    start = time.time()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{config.exa_base_url.rstrip('/')}/search",
            headers={"x-api-key": exa_key, "content-type": "application/json"},
            json={"query": "test", "numResults": 1, "type": "keyword"},
        )
        response_time = _elapsed_ms(start)
        if resp.status_code == 200:
            return {"status": "ok", "message": "Exa API 可用 (HTTP 200)", "response_time_ms": response_time}
        return {"status": "warning", "message": f"HTTP {resp.status_code}: {resp.text[:100]}", "response_time_ms": response_time}


async def _test_tavily_connection() -> dict[str, Any]:
    tavily_key = config.tavily_api_key
    if not tavily_key:
        return {"status": "not_configured", "message": "TAVILY_API_KEY 未设置，Tavily 功能不可用"}
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
            return {"status": "ok", "message": "Tavily API 可用 (HTTP 200)", "response_time_ms": response_time}
        return {"status": "warning", "message": f"HTTP {resp.status_code}: {resp.text[:100]}", "response_time_ms": response_time}


async def _test_jina_connection() -> dict[str, Any]:
    if config.jina_respond_with and not config.jina_api_key:
        return {"status": "config_error", "message": "JINA_RESPOND_WITH requires JINA_API_KEY"}
    if not config.jina_api_key:
        return {"status": "not_configured", "message": "JINA_API_KEY 未设置，Jina 不满足 standard web_fetch；匿名 Reader 只能作为显式实验使用"}
    start = time.time()
    data = await jina_fetch("https://example.com")
    response_time = _elapsed_ms(start)
    if data.get("ok"):
        return {"status": "ok", "message": "Jina Reader 可用", "response_time_ms": response_time}
    error_type = data.get("error_type", "")
    status = error_type if error_type in {"auth_error", "config_error", "parameter_error", "rate_limited", "timeout"} else "warning"
    return {"status": status, "message": data.get("error", "Jina Reader 不可用"), "response_time_ms": response_time}


async def _test_zhipu_connection() -> dict[str, Any]:
    if not config.zhipu_api_key:
        return {"status": "not_configured", "message": "ZHIPU_API_KEY 未设置，智谱搜索功能不可用"}
    result = await zhipu_search("test", count=1)
    if result.get("ok"):
        return {"status": "ok", "message": "智谱 Web Search 可用", "response_time_ms": result.get("elapsed_ms", 0)}
    return {"status": "warning", "message": result.get("error", "智谱 Web Search 不可用"), "response_time_ms": result.get("elapsed_ms", 0)}


async def _test_zhipu_mcp_connection() -> dict[str, Any]:
    if not config.zhipu_mcp_api_key:
        return {"status": "not_configured", "message": "ZHIPU_MCP_API_KEY 未设置，智谱 Coding Plan MCP 功能不可用"}
    result = await zhipu_mcp_search("test", count=1)
    if result.get("ok"):
        return {"status": "ok", "message": "智谱 Coding Plan MCP 可用", "response_time_ms": result.get("elapsed_ms", 0)}
    error_type = result.get("error_type", "")
    status = error_type if error_type in {"auth_error", "config_error", "provider_error", "rate_limited", "timeout"} else "warning"
    return {"status": status, "message": result.get("error", "智谱 Coding Plan MCP 不可用"), "response_time_ms": result.get("elapsed_ms", 0)}


async def _test_context7_connection() -> dict[str, Any]:
    if not config.context7_api_key:
        return {"status": "not_configured", "message": "CONTEXT7_API_KEY 未设置，Context7 功能不可用"}
    result = await context7_library("react", "hooks")
    if result.get("ok"):
        return {"status": "ok", "message": "Context7 API 可用", "response_time_ms": result.get("elapsed_ms", 0)}
    return {"status": "warning", "message": result.get("error", "Context7 API 不可用"), "response_time_ms": result.get("elapsed_ms", 0)}


async def doctor() -> dict[str, Any]:
    info = config.get_config_info()

    main_provider_configs: list[dict[str, Any]] = []
    try:
        main_provider_configs = _main_search_provider_configs()
        info["main_search_connection_tests"] = {}
        for provider_config in main_provider_configs:
            info["main_search_connection_tests"][provider_config["provider"]] = await _safe_test_main_provider_connection(provider_config)
        if main_provider_configs:
            first_provider = main_provider_configs[0]
            info["primary_api_mode"] = first_provider["mode"]
            info["primary_connection_test"] = info["main_search_connection_tests"][first_provider["provider"]]
        else:
            info["primary_connection_test"] = {"status": "config_error", "message": MINIMUM_PROFILE_ERROR}
    except ValueError as e:
        info["main_search_connection_tests"] = {}
        info["primary_connection_test"] = {"status": "config_error", "message": str(e)}
    except Exception as e:
        info["main_search_connection_tests"] = {}
        info["primary_connection_test"] = {"status": "error", "message": f"未知错误: {str(e)}"}

    try:
        info["exa_connection_test"] = await _test_exa_connection()
    except httpx.TimeoutException:
        info["exa_connection_test"] = {"status": "timeout", "message": "Exa API 请求超时"}
    except Exception as e:
        info["exa_connection_test"] = {"status": "error", "message": str(e)}

    try:
        info["tavily_connection_test"] = await _test_tavily_connection()
    except httpx.TimeoutException:
        info["tavily_connection_test"] = {"status": "timeout", "message": "Tavily API 请求超时"}
    except Exception as e:
        info["tavily_connection_test"] = {"status": "error", "message": str(e)}

    try:
        info["jina_connection_test"] = await _test_jina_connection()
    except httpx.TimeoutException:
        info["jina_connection_test"] = {"status": "timeout", "message": "Jina Reader 请求超时"}
    except Exception as e:
        info["jina_connection_test"] = {"status": "error", "message": str(e)}

    if config.firecrawl_api_key:
        info["firecrawl_connection_test"] = {"status": "configured", "message": "FIRECRAWL_API_KEY 已设置"}
    else:
        info["firecrawl_connection_test"] = {"status": "not_configured", "message": "FIRECRAWL_API_KEY 未设置，Firecrawl 功能不可用"}

    try:
        info["zhipu_connection_test"] = await _test_zhipu_connection()
    except httpx.TimeoutException:
        info["zhipu_connection_test"] = {"status": "timeout", "message": "智谱 API 请求超时"}
    except Exception as e:
        info["zhipu_connection_test"] = {"status": "error", "message": str(e)}

    try:
        info["zhipu_mcp_connection_test"] = await _test_zhipu_mcp_connection()
    except httpx.TimeoutException:
        info["zhipu_mcp_connection_test"] = {"status": "timeout", "message": "智谱 Coding Plan MCP 请求超时"}
    except Exception as e:
        info["zhipu_mcp_connection_test"] = {"status": "error", "message": str(e)}

    try:
        info["context7_connection_test"] = await _test_context7_connection()
    except httpx.TimeoutException:
        info["context7_connection_test"] = {"status": "timeout", "message": "Context7 API 请求超时"}
    except Exception as e:
        info["context7_connection_test"] = {"status": "error", "message": str(e)}

    minimum = validate_minimum_profile()
    info["capability_status"] = minimum.get("capability_status", get_capability_status())
    info["minimum_profile_ok"] = minimum.get("ok", False)
    info["minimum_profile_missing"] = minimum.get("missing", [])
    main_connection_tests = info.get("main_search_connection_tests") or {}
    main_search_statuses = [item.get("status") for item in main_connection_tests.values() if isinstance(item, dict)]
    primary_test = info.get("primary_connection_test", {})
    primary_status = primary_test.get("status")
    main_search_ok = any(status == "ok" for status in main_search_statuses) if main_connection_tests else primary_status == "ok"
    info["ok"] = main_search_ok and minimum.get("ok", False)
    if info["ok"]:
        info["error_type"] = ""
        info["error"] = ""
    elif info.get("config_parameter_errors"):
        info["error"] = "; ".join(info["config_parameter_errors"])
        info["error_type"] = "parameter_error"
    elif not minimum.get("ok", False):
        info["error"] = minimum.get("error", MINIMUM_PROFILE_ERROR)
        info["error_type"] = minimum.get("error_type", "config_error")
    else:
        info["error"] = primary_test.get("message", "Primary connection check failed")
        if primary_status == "config_error":
            info["error_type"] = "config_error"
        elif primary_status in {"timeout", "error", "warning"}:
            info["error_type"] = "network_error"
        else:
            info["error_type"] = "runtime_error"
    return info


def current_model() -> dict[str, Any]:
    return {
        "ok": True,
        "xai_model": config.xai_model,
        "openai_compatible_model": config.openai_compatible_model,
        "config_file": str(config.config_file),
    }


def set_model(model: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error_type": "parameter_error",
        "error": (
            "The legacy default model command was removed. Use `smart-search config set XAI_MODEL <model>` "
            "or `smart-search config set OPENAI_COMPATIBLE_MODEL <model>`."
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
    saved = config.get_saved_config(masked=True)
    return {
        "ok": True,
        "config_file": str(config.config_file),
        "key": key.strip().upper(),
        "value": saved.get(key.strip().upper(), ""),
    }


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
        return {"ok": False, "error_type": "parameter_error", "error": "mode must be mock or live"}
    if mode == "live":
        return await _smoke_live(start)
    return await _smoke_mock(start)


def _case(name: str, ok: bool, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "ok": ok, **(details or {})}


def _case_failed(case: dict[str, Any]) -> bool:
    return not case.get("ok") and case.get("severity", "critical") != "degraded"


async def _smoke_mock(start: float) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []

    minimum_status = {
        "main_search": {
            "configured": ["xai-responses", "openai-compatible"],
            "fallback_chain": MAIN_SEARCH_FALLBACK_CHAIN,
            "ok": True,
        },
        "web_search": {"configured": ["zhipu"], "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl"], "ok": True},
        "docs_search": {"configured": ["context7"], "fallback_chain": ["context7", "exa"], "ok": True},
        "web_fetch": {"configured": ["tavily"], "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"], "ok": True},
        "vertical_search": {"configured": [], "fallback_chain": ["anysearch"], "ok": False, "experimental": True},
    }
    minimum = _minimum_profile_result("standard", minimum_status)
    cases.append(
        _case(
            "doctor minimum profile gate",
            minimum["ok"] and not minimum["missing"],
            {"minimum_profile_ok": minimum["ok"], "capability_status": minimum["capability_status"]},
        )
    )

    missing_minimum = _minimum_profile_result(
        "standard",
        {
            **minimum_status,
            "docs_search": {"configured": [], "fallback_chain": ["context7", "exa"], "ok": False},
        },
    )
    cases.append(
        _case(
            "doctor minimum profile fails closed",
            not missing_minimum["ok"] and missing_minimum["missing"] == ["docs_search"],
            {"missing": missing_minimum["missing"], "error_type": missing_minimum["error_type"]},
        )
    )

    main_attempts = [_attempt("main_search", "xAI Responses", "ok", time.time(), result_count=1)]
    cases.append(_case("main_search xai responses answer path", True, {"provider_attempts": main_attempts}))

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
        "web_current_intent": _is_zh_current_intent("today AI news"),
        "supplemental_paths": [],
    }
    cases.append(_case("search balanced avoids context7 for general query", not general_route["docs_intent"], {"routing_decision": general_route}))

    docs_route = {
        "docs_intent": _is_docs_intent("React useEffect API docs"),
        "web_current_intent": _is_zh_current_intent("React useEffect API docs"),
        "supplemental_paths": ["docs_search"],
    }
    cases.append(_case("search docs intent uses docs route", docs_route["docs_intent"], {"routing_decision": docs_route}))

    zh_route = {
        "zh_current_intent": _is_zh_current_intent("今天国内 AI 新闻"),
        "web_current_intent": _is_zh_current_intent("今天国内 AI 新闻"),
        "supplemental_paths": ["web_search"],
    }
    cases.append(_case("search zh current intent uses zhipu reinforcement", zh_route["zh_current_intent"], {"routing_decision": zh_route}))

    sports_route = {
        "zh_current_intent": _is_zh_current_intent("nba战报"),
        "web_current_intent": _is_zh_current_intent("nba战报"),
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

    missing_for_deep = _minimum_profile_result(
        "standard",
        {
            **minimum_status,
            "docs_search": {"configured": [], "fallback_chain": ["context7", "exa"], "ok": False},
            "web_fetch": {"configured": [], "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"], "ok": False},
        },
    )
    cases.append(
        _case(
            "deep_research missing provider gives capability guidance",
            not missing_for_deep["ok"] and set(missing_for_deep["missing"]) == {"docs_search", "web_fetch"},
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
            "configured": ["zhipu", "zhipu-mcp", "tavily", "firecrawl"],
            "fallback_chain": ["zhipu", "zhipu-mcp", "tavily", "firecrawl"],
            "ok": True,
        },
        "docs_search": {"configured": ["context7", "exa"], "fallback_chain": ["context7", "exa"], "ok": True},
        "web_fetch": {
            "configured": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"],
            "fallback_chain": ["tavily", "jina", "zhipu-mcp-reader", "firecrawl"],
            "ok": True,
        },
        "vertical_search": {"configured": ["anysearch"], "fallback_chain": ["anysearch"], "ok": True, "experimental": True},
    }
    docs_routes = _research_capability_routes("React useEffect API docs", docs_plan, "auto", capability_status=mock_research_status)
    zh_routes = _research_capability_routes("今天国内 AI 政策最新公告", market_plan, "auto", capability_status=mock_research_status)
    pdf_fetch_order = _research_fetch_order("summarize https://arxiv.org/pdf/2401.00001.pdf", capability_status=mock_research_status)
    dynamic_fetch_order = _research_fetch_order("dynamic javascript cloudflare page", "https://example.com/app", capability_status=mock_research_status)
    vertical_routes = _research_capability_routes("CVE OpenSSL 漏洞影响范围", claim_plan, "auto", capability_status=mock_research_status)

    cases.append(
        _case(
            "research router docs api prefers context7 then exa",
            docs_routes["capabilities"]["docs_search"]["providers"][:2] == ["context7", "exa"]
            and docs_routes["capabilities"]["vertical_search"]["providers"] == [],
            {"routing_decision": docs_routes},
        )
    )
    cases.append(
        _case(
            "research router chinese current prefers zhipu web_search",
            zh_routes["capabilities"]["web_search"]["providers"][0] == "zhipu",
            {"routing_decision": zh_routes},
        )
    )
    cases.append(
        _case(
            "research router known url pdf favors jina fetch",
            pdf_fetch_order[0] == "jina",
            {"fetch_order": pdf_fetch_order},
        )
    )
    cases.append(
        _case(
            "research router js heavy favors firecrawl fetch",
            dynamic_fetch_order[0] == "firecrawl",
            {"fetch_order": dynamic_fetch_order},
        )
    )
    cases.append(
        _case(
            "research router vertical intent uses anysearch only when matched",
            vertical_routes["capabilities"]["vertical_search"]["providers"] == ["anysearch"],
            {"routing_decision": vertical_routes},
        )
    )

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
    failed = [c["name"] for c in cases if _case_failed(c)]
    return {
        "ok": not failed,
        "mode": "mock",
        "failed_cases": failed,
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
        cases.append(_case("zhipu search", True, {"skipped": "ZHIPU_API_KEY not configured"}))

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
        cases.append(_case("context7 library", True, {"skipped": "CONTEXT7_API_KEY not configured"}))

    if config.tavily_api_key or config.firecrawl_api_key:
        fetch_result = await fetch("https://example.com")
        cases.append(_case("web fetch fallback chain", bool(fetch_result.get("ok")), {"provider": fetch_result.get("provider", ""), "provider_attempts": fetch_result.get("provider_attempts", [])}))
    else:
        cases.append(_case("web fetch fallback chain", True, {"skipped": "no fetch providers configured"}))

    failed = [c["name"] for c in cases if _case_failed(c)]
    degraded = [c["name"] for c in cases if not c.get("ok") and c.get("severity") == "degraded"]
    attempts: list[dict] = []
    for c in cases:
        attempts.extend(c.get("provider_attempts", []))
    return {
        "ok": not failed,
        "mode": "live",
        "failed_cases": failed,
        "degraded_cases": degraded,
        "cases": cases,
        "provider_attempts": attempts,
        "elapsed_ms": _elapsed_ms(start),
    }


def write_output(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
