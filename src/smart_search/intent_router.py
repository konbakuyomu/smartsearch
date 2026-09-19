import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from .embedding_presets import embedding_preset_for_model, embedding_threshold_commands


ALLOWED_INTENT_ROUTER_MODES = {"hybrid", "rules", "off"}
ROUTABLE_CAPABILITIES = {"docs_search", "web_search", "web_fetch", "vertical_search"}

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
    "接入",
}

CURRENT_INTENT_KEYWORDS = {
    "今天",
    "今日",
    "最新",
    "国内",
    "中国",
    "政策",
    "新闻",
    "实时",
    "刚刚",
    "当前",
    "现在",
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
    "today",
    "latest",
    "current",
    "realtime",
    "live",
    "recent",
}

ZH_CURRENT_INTENT_KEYWORDS = {
    "今天",
    "今日",
    "最新",
    "国内",
    "中国",
    "政策",
    "新闻",
    "实时",
    "刚刚",
    "当前",
    "现在",
    "本周",
    "本月",
    "战报",
    "比分",
    "赛程",
    "赛果",
    "季后赛",
    "比赛",
    "足球",
    "篮球",
}

FETCH_INTENT_KEYWORDS = {"http://", "https://"}

VERTICAL_INTENT_KEYWORDS = {
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

CAPABILITY_UTTERANCES: dict[str, list[str]] = {
    "docs_search": [
        "React useEffect API docs",
        "how to integrate this SDK",
        "Python function parameters reference",
        "OpenAI API documentation",
        "这个 SDK 怎么接入",
        "查一下框架官方文档和配置参数",
    ],
    "web_search": [
        "today China AI news",
        "latest policy announcement",
        "current market update",
        "NBA score today",
        "今天国内 AI 新闻",
        "最近有什么最新变化",
    ],
    "web_fetch": [
        "verify the claim in this URL https://example.com",
        "summarize this webpage",
        "fetch this PDF",
        "请核验这个链接里的说法 https://example.com",
        "抓取这个网页正文",
    ],
    "vertical_search": [
        "CVE-2026 OpenSSL vulnerability impact",
        "financial filing structured search",
        "legal regulation database search",
        "GitHub codebase search",
        "漏洞影响范围",
        "垂直领域结构化检索",
    ],
}

DEFAULT_ROUTE_CALIBRATION_MODELS = [
    "Qwen/Qwen3-Embedding-8B",
    "Qwen/Qwen3-Embedding-4B",
    "Qwen/Qwen3-Embedding-0.6B",
    "Pro/BAAI/bge-m3",
    "BAAI/bge-large-zh-v1.5",
]

ROUTE_CALIBRATION_QUERIES: dict[str, list[str]] = {
    "docs_search": [
        "React useEffect official docs",
        "Next.js app router caching docs",
        "Python pathlib Path API reference",
        "TypeScript compiler options documentation",
        "LangChain retriever integration guide",
        "OpenAI Responses API parameters",
        "Prisma migration CLI docs",
        "Vue watchEffect API usage",
        "FastAPI dependency injection docs",
        "Docker compose healthcheck reference",
        "这个 SDK 怎么接入",
        "查一下 React hooks 官方文档",
        "Python requests 超时参数怎么配置",
        "Vite 配置 alias 的文档",
        "Context7 怎么查 LangChain 文档",
        "OpenAI embeddings API 文档",
        "Next.js middleware 配置项",
        "Rust tokio select 文档",
        "Pandas groupby 参数说明",
        "Tailwind CSS container query docs",
    ],
    "web_search": [
        "今天国内 AI 新闻",
        "latest Nvidia earnings news",
        "current Bitcoin price movement",
        "今日人民币汇率变化",
        "NBA score today Lakers",
        "本周新能源车政策",
        "recent OpenAI product announcement",
        "latest Windows 11 update issue",
        "现在上海天气预警",
        "today stock market close summary",
        "刚刚苹果发布会消息",
        "最近美国大选民调",
        "current oil price news",
        "今日A股收盘行情",
        "latest CVE exploit in the wild",
        "本月中国芯片政策变化",
        "today SpaceX launch status",
        "latest Python release announcement",
        "近期比特币ETF新闻",
        "NBA今日赛程",
    ],
    "web_fetch": [
        "summarize https://example.com",
        "fetch this PDF https://example.com/report.pdf",
        "请读取这个网页 https://example.com/post",
        "核验这个链接里的说法 https://example.com/source",
        "extract the main text from https://example.org/article",
        "read this arxiv PDF https://arxiv.org/pdf/2401.00001.pdf",
        "抓取 https://example.com/docs 的正文",
        "summarize this url: http://example.net/page",
        "请打开链接看看写了什么 https://example.com",
        "compare the claim in https://example.com/claim",
        "pull metadata from https://example.com/product",
        "读取这篇博客 https://blog.example.com/a",
        "fetch known URL content https://news.example.com/item",
        "把这个PDF概括一下 https://example.com/file.pdf",
        "verify source page http://example.org/source",
        "get text from URL https://developer.example.com/changelog",
        "read webpage content at https://example.edu/paper",
        "请提取网页正文 https://docs.example.com/install",
        "summarize linked announcement https://company.example.com/news",
        "fetch this public page https://example.com/about",
    ],
    "vertical_search": [
        "CVE-2026 OpenSSL vulnerability impact",
        "Search GitHub codebase for auth middleware",
        "legal regulation database search GDPR",
        "financial filing structured search 10-K revenue",
        "academic paper search transformer retrieval",
        "漏洞影响范围 CVE-2025",
        "查找 GitHub 仓库里的配置文件",
        "法规条文数据库检索",
        "股票财报结构化查询",
        "医学论文数据库检索",
        "patent search battery materials",
        "code search repo function name",
        "SEC filing risk factors search",
        "法律案例检索 合同纠纷",
        "学术论文 引用 网络 搜索",
        "NVD vulnerability database query",
        "vertical domain search for finance filings",
        "repository search for Dockerfile examples",
        "法律法规 检索 个税",
        "数据库里查 CVE exploit score",
    ],
    "none": [
        "帮我把这句话翻译成英文",
        "写一封请假邮件",
        "总结下面这段文字",
        "解释这个错误堆栈的含义",
        "帮我给变量起名",
        "把这段 JSON 格式化",
        "生成一个会议纪要模板",
        "用更礼貌的语气改写这句话",
        "给我一个早餐计划",
        "计算 37 乘以 19",
        "explain what recursion means in simple words",
        "write a short haiku about winter",
        "classify these TODO items by priority",
        "make this paragraph shorter",
        "帮我润色项目介绍",
        "不联网也能回答的常识问题",
        "给代码加一点注释",
        "Python 函数是什么意思，用自己的话解释",
        "React 是什么，用中文解释",
        "帮我检查语法和错别字",
    ],
}

DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD = 0.74
DEFAULT_SEMANTIC_CONFIDENCE_MARGIN = 0.05


@dataclass
class IntentRouteResult:
    query: str
    intent_router_mode: str
    required_capabilities: list[str] = field(default_factory=list)
    intent_signals: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    router_engines_used: list[str] = field(default_factory=list)
    degraded: bool = False
    degraded_reason: str = ""
    reasons: list[str] = field(default_factory=list)
    docs_intent: bool = False
    zh_current_intent: bool = False
    web_current_intent: bool = False
    fetch_intent: bool = False
    supplemental_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "docs_intent": self.docs_intent,
            "zh_current_intent": self.zh_current_intent,
            "web_current_intent": self.web_current_intent,
            "fetch_intent": self.fetch_intent,
            "supplemental_paths": list(self.supplemental_paths),
            "intent_router_mode": self.intent_router_mode,
            "required_capabilities": list(self.required_capabilities),
            "intent_signals": dict(self.intent_signals),
            "confidence": self.confidence,
            "router_engines_used": list(self.router_engines_used),
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
            "reasons": list(self.reasons),
        }


def contains_any(query: str, keywords: set[str]) -> bool:
    q = query.lower()
    return any(keyword.lower() in q for keyword in keywords)


def extract_urls(query: str) -> list[str]:
    urls = []
    for match in re.findall(r"https?://[^\s<>\]\)\"'，。；！？、：）】》」』]+", query):
        cleaned = match.rstrip(".,;，。；)")
        if cleaned:
            urls.append(cleaned)
    return urls


def _ordered_capabilities(capabilities: set[str]) -> list[str]:
    order = ["docs_search", "web_search", "web_fetch", "vertical_search"]
    return [capability for capability in order if capability in capabilities]


def build_rules_route(
    query: str,
    *,
    validation_level: str = "",
    plan_intent_signals: dict[str, Any] | None = None,
    mode: str = "rules",
) -> IntentRouteResult:
    plan_intent_signals = plan_intent_signals or {}
    urls = extract_urls(query)
    docs_intent = bool(plan_intent_signals.get("docs_api_intent")) or contains_any(query, DOCS_INTENT_KEYWORDS)
    zh_current_intent = (
        plan_intent_signals.get("locale_domain_scope") == "china"
        or contains_any(query, ZH_CURRENT_INTENT_KEYWORDS)
    )
    web_current_intent = bool(
        zh_current_intent
        or plan_intent_signals.get("recency_requirement") in {"recent", "current"}
        or contains_any(query, CURRENT_INTENT_KEYWORDS)
    )
    fetch_intent = bool(plan_intent_signals.get("known_url")) or bool(urls) or contains_any(query, FETCH_INTENT_KEYWORDS)
    vertical_intent = contains_any(query, VERTICAL_INTENT_KEYWORDS)

    capabilities: set[str] = set()
    supplemental_paths: list[str] = []
    reasons: list[str] = []
    signal_scores: dict[str, float] = {}

    def add_capability(capability: str, reason: str, score: float) -> None:
        capabilities.add(capability)
        if capability not in supplemental_paths:
            supplemental_paths.append(capability)
        reasons.append(reason)
        signal_scores[capability] = max(signal_scores.get(capability, 0.0), score)

    if docs_intent:
        add_capability("docs_search", "rules matched docs/API/library terms", 0.82)
    if web_current_intent:
        add_capability("web_search", "rules matched current/locale/news terms", 0.84)
    if validation_level == "strict":
        add_capability("web_search", "strict validation requires source reinforcement", 0.72)
    if fetch_intent:
        add_capability("web_fetch", "rules matched a known URL or fetch request", 0.95 if urls else 0.78)
    if vertical_intent:
        add_capability("vertical_search", "rules matched vertical-domain terms", 0.72)

    confidence = max(signal_scores.values(), default=0.35)
    intent_signals: dict[str, Any] = {
        "docs_api_intent": docs_intent,
        "current_or_locale_intent": web_current_intent,
        "known_url": fetch_intent,
        "vertical_intent": vertical_intent,
        "strict_validation": validation_level == "strict",
        "rule_scores": signal_scores,
        "urls": urls,
    }
    for key, value in plan_intent_signals.items():
        intent_signals.setdefault(key, value)
    return IntentRouteResult(
        query=query,
        intent_router_mode=mode,
        required_capabilities=_ordered_capabilities(capabilities),
        intent_signals=intent_signals,
        confidence=round(confidence, 3),
        router_engines_used=["rules"],
        reasons=reasons or ["rules found no supplemental capability need"],
        docs_intent=docs_intent,
        zh_current_intent=bool(zh_current_intent),
        web_current_intent=web_current_intent,
        fetch_intent=fetch_intent,
        supplemental_paths=_ordered_capabilities(set(supplemental_paths)),
    )


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _classifier_can_add_capability(capability: str, rules: IntentRouteResult) -> bool:
    if capability != "web_search":
        return True
    signals = rules.intent_signals
    return bool(
        rules.web_current_intent
        or signals.get("strict_validation")
        or signals.get("cross_validation_need") == "high"
        or signals.get("recency_requirement") in {"recent", "current"}
        or signals.get("claim_risk") in {"medium", "high"}
        or rules.fetch_intent
    )


def _semantic_summary(scores: dict[str, float], threshold: float, margin: float) -> dict[str, Any]:
    candidates = [(capability, float(score)) for capability, score in scores.items() if capability in ROUTABLE_CAPABILITIES]
    ranked = sorted(candidates, key=lambda item: item[1], reverse=True)
    top_capability = ranked[0][0] if ranked else ""
    top_score = ranked[0][1] if ranked else 0.0
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    score_margin = top_score - second_score if ranked else 0.0
    return {
        "top_capability": top_capability,
        "top_score": top_score,
        "second_score": second_score,
        "margin": score_margin,
        "threshold": threshold,
        "minimum_margin": margin,
        "passed_threshold": bool(top_capability and top_score >= threshold),
        "passed_margin": bool(top_capability and score_margin >= margin),
    }


def _config_source(cfg: Any, key: str) -> str:
    getter = getattr(cfg, "get_config_source", None)
    if callable(getter):
        return str(getter(key))
    return "default"


def _matches_float_text(value: float, expected: str) -> bool:
    try:
        return abs(float(value) - float(expected)) < 0.0005
    except (TypeError, ValueError):
        return False


def _embedding_preset_recommendation(
    model: str,
    threshold: float,
    margin: float,
    threshold_source: str,
    margin_source: str,
) -> dict[str, Any]:
    preset = embedding_preset_for_model(model)
    if not preset:
        return {}
    threshold_matches = _matches_float_text(threshold, preset.threshold)
    margin_matches = _matches_float_text(margin, preset.margin)
    missing_or_mismatched = (
        threshold_source == "default"
        or margin_source == "default"
        or not threshold_matches
        or not margin_matches
    )
    message = ""
    if missing_or_mismatched:
        message = (
            f"{preset.model} works best with INTENT_EMBEDDING_THRESHOLD={preset.threshold} "
            f"and INTENT_EMBEDDING_MARGIN={preset.margin} based on the current Smart Search calibration set."
        )
    return {
        "embedding_preset_id": preset.preset_id,
        "embedding_preset_model": preset.model,
        "embedding_preset_api_url": preset.api_url,
        "embedding_preset_threshold": preset.threshold,
        "embedding_preset_margin": preset.margin,
        "embedding_preset_threshold_matches": threshold_matches,
        "embedding_preset_margin_matches": margin_matches,
        "embedding_preset_recommended": missing_or_mismatched,
        "embedding_preset_recommendation": message,
        "embedding_preset_commands": embedding_threshold_commands(preset) if missing_or_mismatched else [],
    }


class IntentRouter:
    def __init__(self, cfg: Any):
        self.config = cfg

    def status(self) -> dict[str, Any]:
        errors: list[str] = []
        try:
            mode = self.config.intent_router_mode
        except ValueError as exc:
            mode = ""
            errors.append(str(exc))
        try:
            timeout_seconds = self.config.intent_router_timeout
        except ValueError as exc:
            timeout_seconds = 8.0
            errors.append(str(exc))
        try:
            embedding_threshold = self.config.intent_embedding_threshold
        except ValueError as exc:
            embedding_threshold = DEFAULT_SEMANTIC_CONFIDENCE_THRESHOLD
            errors.append(str(exc))
        try:
            embedding_margin = self.config.intent_embedding_margin
        except ValueError as exc:
            embedding_margin = DEFAULT_SEMANTIC_CONFIDENCE_MARGIN
            errors.append(str(exc))
        embedding_model = self.config.intent_embedding_model or ""
        threshold_source = _config_source(self.config, "INTENT_EMBEDDING_THRESHOLD")
        margin_source = _config_source(self.config, "INTENT_EMBEDDING_MARGIN")
        preset_recommendation = _embedding_preset_recommendation(
            embedding_model,
            embedding_threshold,
            embedding_margin,
            threshold_source,
            margin_source,
        )
        return {
            "mode": mode,
            "ok": not errors,
            "error": "; ".join(errors),
            "embeddings_configured": self._embeddings_configured(),
            "classifier_configured": self._classifier_configured(),
            "embedding_model": embedding_model,
            "embedding_threshold": embedding_threshold,
            "embedding_margin": embedding_margin,
            "embedding_threshold_source": threshold_source,
            "embedding_margin_source": margin_source,
            "classifier_model": self.config.intent_classifier_model or "",
            "timeout_seconds": timeout_seconds,
            "degrades_to_rules": True,
            **preset_recommendation,
        }

    async def route(
        self,
        query: str,
        *,
        validation_level: str = "",
        mode: str = "",
        allow_remote: bool = True,
        plan_intent_signals: dict[str, Any] | None = None,
    ) -> IntentRouteResult:
        selected_mode = (mode or self.config.intent_router_mode).strip().lower()
        if selected_mode not in ALLOWED_INTENT_ROUTER_MODES:
            allowed = ", ".join(sorted(ALLOWED_INTENT_ROUTER_MODES))
            raise ValueError(f"Invalid SMART_SEARCH_INTENT_ROUTER: {selected_mode}. Supported values: {allowed}")
        if selected_mode == "off":
            return IntentRouteResult(
                query=query,
                intent_router_mode="off",
                router_engines_used=["off"],
                reasons=["intent router disabled"],
            )

        rules = build_rules_route(
            query,
            validation_level=validation_level,
            plan_intent_signals=plan_intent_signals,
            mode="rules" if selected_mode == "rules" or not allow_remote else selected_mode,
        )
        if selected_mode == "rules" or not allow_remote:
            return rules

        degraded_reasons: list[str] = []
        engines = ["rules"]
        semantic: dict[str, Any] = {}
        classifier: dict[str, Any] = {}
        merged_caps = set(rules.required_capabilities)
        merged_signals = dict(rules.intent_signals)
        merged_reasons = list(rules.reasons)
        confidence = rules.confidence

        if self._embeddings_configured():
            try:
                semantic = await self._semantic_route(query)
                engines.append("embeddings")
                scores = semantic.get("scores") if isinstance(semantic.get("scores"), dict) else {}
                summary = _semantic_summary(
                    {capability: float(score) for capability, score in scores.items()},
                    self.config.intent_embedding_threshold,
                    self.config.intent_embedding_margin,
                )
                for capability, score in (semantic.get("scores") or {}).items():
                    if capability in ROUTABLE_CAPABILITIES:
                        merged_signals[f"semantic_{capability}_score"] = round(float(score), 3)
                merged_signals.update(
                    {
                        "semantic_top_capability": summary["top_capability"],
                        "semantic_top_score": round(float(summary["top_score"]), 3),
                        "semantic_second_score": round(float(summary["second_score"]), 3),
                        "semantic_margin": round(float(summary["margin"]), 3),
                        "semantic_threshold": round(float(summary["threshold"]), 3),
                        "semantic_minimum_margin": round(float(summary["minimum_margin"]), 3),
                        "semantic_passed_threshold": bool(summary["passed_threshold"]),
                        "semantic_passed_margin": bool(summary["passed_margin"]),
                    }
                )
                if summary["passed_threshold"] and summary["passed_margin"]:
                    capability = str(summary["top_capability"])
                    merged_caps.add(capability)
                    merged_reasons.append(
                        f"embeddings matched {capability} examples "
                        f"(score {summary['top_score']:.3f}, margin {summary['margin']:.3f})"
                    )
                    confidence = max(confidence, float(summary["top_score"]))
                elif summary["passed_threshold"] and not summary["passed_margin"]:
                    merged_reasons.append(
                        "embeddings ambiguous: top semantic score passed threshold "
                        f"but margin {summary['margin']:.3f} was below {summary['minimum_margin']:.3f}"
                    )
            except Exception as exc:
                degraded_reasons.append(f"embeddings unavailable: {exc}")
        else:
            degraded_reasons.append("embeddings not configured")

        if self._classifier_configured():
            try:
                classifier = await self._classifier_route(query, rules.to_dict(), semantic)
                engines.append("classifier")
                for capability in classifier.get("required_capabilities") or []:
                    if capability in ROUTABLE_CAPABILITIES and _classifier_can_add_capability(capability, rules):
                        merged_caps.add(capability)
                    elif capability in ROUTABLE_CAPABILITIES:
                        merged_reasons.append(f"classifier ignored unsupported capability for current signals: {capability}")
                    else:
                        merged_reasons.append(f"classifier ignored unknown capability: {capability}")
                if classifier.get("provider") or classifier.get("providers"):
                    merged_reasons.append("classifier provider choices were ignored; router only accepts capabilities")
                classifier_signals = classifier.get("intent_signals") if isinstance(classifier.get("intent_signals"), dict) else {}
                for key, value in classifier_signals.items():
                    if key not in {"provider", "providers", "provider_id"}:
                        merged_signals[key] = value
                classifier_confidence = classifier.get("confidence")
                if isinstance(classifier_confidence, (int, float)):
                    confidence = max(confidence, float(classifier_confidence))
                for reason in classifier.get("reasons") or []:
                    if isinstance(reason, str) and reason:
                        merged_reasons.append(f"classifier: {reason}")
            except Exception as exc:
                degraded_reasons.append(f"classifier unavailable: {exc}")
        else:
            degraded_reasons.append("classifier not configured")

        required_capabilities = _ordered_capabilities(merged_caps)
        return IntentRouteResult(
            query=query,
            intent_router_mode="hybrid",
            required_capabilities=required_capabilities,
            intent_signals=merged_signals,
            confidence=round(min(confidence, 1.0), 3),
            router_engines_used=engines,
            degraded=bool(degraded_reasons),
            degraded_reason="; ".join(degraded_reasons),
            reasons=merged_reasons,
            docs_intent=rules.docs_intent or "docs_search" in required_capabilities,
            zh_current_intent=rules.zh_current_intent,
            web_current_intent=rules.web_current_intent,
            fetch_intent=rules.fetch_intent or "web_fetch" in required_capabilities,
            supplemental_paths=required_capabilities,
        )

    def _embeddings_configured(self) -> bool:
        return bool(
            self.config.intent_embedding_api_url
            and self.config.intent_embedding_api_key
            and self.config.intent_embedding_model
        )

    def _classifier_configured(self) -> bool:
        return bool(
            self.config.intent_classifier_api_url
            and self.config.intent_classifier_api_key
            and self.config.intent_classifier_model
        )

    async def _semantic_route(self, query: str) -> dict[str, Any]:
        utterances: list[tuple[str, str]] = []
        inputs = [query]
        for capability, examples in CAPABILITY_UTTERANCES.items():
            for example in examples:
                utterances.append((capability, example))
                inputs.append(example)
        embeddings = await self._embed(inputs)
        query_embedding = embeddings[0]
        scores: dict[str, float] = {}
        for index, (capability, _example) in enumerate(utterances, start=1):
            score = _cosine_similarity(query_embedding, embeddings[index])
            scores[capability] = max(scores.get(capability, 0.0), score)
        return {
            "scores": scores,
            **_semantic_summary(
                scores,
                self.config.intent_embedding_threshold,
                self.config.intent_embedding_margin,
            ),
        }

    async def _embed(self, inputs: list[str]) -> list[list[float]]:
        headers = {
            "Authorization": f"Bearer {self.config.intent_embedding_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"model": self.config.intent_embedding_model, "input": inputs}
        timeout = httpx.Timeout(self.config.intent_router_timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.config.intent_embedding_api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list) or len(rows) < len(inputs):
            raise ValueError("embedding response missing data rows")
        embeddings: list[list[float]] = []
        for row in rows[: len(inputs)]:
            embedding = row.get("embedding") if isinstance(row, dict) else None
            if not isinstance(embedding, list):
                raise ValueError("embedding response row missing embedding")
            embeddings.append([float(value) for value in embedding])
        return embeddings

    async def _classifier_route(self, query: str, rules: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]:
        prompt = {
            "query": query,
            "rules_result": rules,
            "semantic_result": semantic,
            "allowed_capabilities": sorted(ROUTABLE_CAPABILITIES),
            "instruction": (
                "Return strict JSON with required_capabilities, intent_signals, confidence, and reasons. "
                "Choose only allowed capabilities. Do not choose providers."
            ),
        }
        headers = {
            "Authorization": f"Bearer {self.config.intent_classifier_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.config.intent_classifier_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You classify routing capabilities for Smart Search. Output JSON only.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        timeout = httpx.Timeout(self.config.intent_router_timeout)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(self.config.intent_classifier_api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        content = self._extract_classifier_content(data)
        parsed = json.loads(content) if isinstance(content, str) else content
        if not isinstance(parsed, dict):
            raise ValueError("classifier response is not a JSON object")
        return parsed

    @staticmethod
    def _extract_classifier_content(data: Any) -> Any:
        if isinstance(data, dict) and "required_capabilities" in data:
            return data
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                if isinstance(message, dict) and "content" in message:
                    return message["content"]
            if "output_text" in data:
                return data["output_text"]
        raise ValueError("classifier response missing JSON content")
