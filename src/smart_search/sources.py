import ast
import json
import re
import uuid
from collections import OrderedDict
from typing import Any

import asyncio

from .config import config
from .utils import NO_WEB_SEARCH_MARKER, extract_unique_urls


_MD_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
_INLINE_CITATION_LINK_PATTERN = re.compile(r"\[\[(\d+)\]\]\((https?://[^)]+)\)")
# How OpenAI search models cite at the end of a sentence or bullet: "... in 2026. ([python.org](https://...))"
_PARENTHESIZED_CITATION_PATTERN = re.compile(r"[(（]\s*\[[^\]]+\]\(https?://[^)\s]+\)\s*[)）]")
_BARE_OR_ANGLE_URL_PATTERN = re.compile(r"<?https?://[^\s>]+>?")
_SOURCES_HEADING_PATTERN = re.compile(
    r"(?im)^"
    r"(?:#{1,6}\s*)?"
    r"(?:\*\*|__)?\s*"
    r"(sources?|references?|citations?|信源|参考资料|参考|引用|来源列表|来源)"
    r"\s*(?:\*\*|__)?"
    r"(?:\s*[（(][^)\n]*[)）])?"
    r"\s*[:：]?\s*$"
)
_SOURCES_FUNCTION_PATTERN = re.compile(
    r"(?im)(^|\n)\s*(sources|source|citations|citation|references|reference|citation_card|source_cards|source_card)\s*\("
)

_THINK_BLOCK_PATTERN = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)

_INTENT_SENTENCE = re.compile(
    r"(?:(?:ok(?:ay)?|sure|alright)[,!.]?\s+)?"
    r"(?:(?:i'll|i will|i'm going to|i am going to|let me|let's|i need to|first,?\s+i'll)\b.{0,200}?"
    r"\b(?:look|search|check|find|research|browse|dig|gather|pull|review|investigate|query|consult|verify)"
    r"|(?:searching|looking up|looking into|checking|researching|gathering|browsing|pulling up)\b"
    r"(?!\s+(?:is|are|was|were|can|could|will|would|should|has|have|must|may|might)\b))"
    r"|(?:好的?[，,]?\s*)?(?:我|让我|下面我|接下来我|正在)(?:先|将|会|来|马上|去|再)*"
    r"(?:检索|搜索|查找|查询|查一下|查阅|搜一下|调研|核实)",
    re.IGNORECASE,
)

_LEADING_POLICY_PATTERNS = [
    re.compile(r"^I\s+cannot\s+(comply|assist|help|provide|fulfill)", re.IGNORECASE),
    re.compile(r"^I\s+(can't|won't|will\s+not|am\s+unable\s+to)\s+(comply|assist|help|provide|fulfill)", re.IGNORECASE),
    re.compile(r"^I('m|\s+am)\s+not\s+able\s+to", re.IGNORECASE),
    re.compile(r"^(Sorry|Apologies|I\s+apologize),?\s+(but\s+)?I\s+(cannot|can't|won't)", re.IGNORECASE),
    re.compile(r"^As\s+an?\s+AI(\s+language\s+model)?", re.IGNORECASE),
    re.compile(r"^我(无法|不能|没有办法)(遵从|遵守|协助|帮助|提供|满足)", re.IGNORECASE),
    re.compile(r"^(抱歉|对不起|很遗憾)[，,]?\s*我(无法|不能)", re.IGNORECASE),
]

_POLICY_META_KEYWORDS = {
    "policy", "policies", "guideline", "guidelines", "content policy",
    "usage policy", "terms of service", "acceptable use",
    "策略", "政策", "准则", "使用条款", "服务条款",
}

_POLICY_CONTEXT_KEYWORDS = {
    "prompt injection", "jailbreak", "system prompt", "hidden instruction",
    "bypass", "override", "ignore previous",
    "提示注入", "越狱", "系统提示", "隐藏指令",
}


def _normalize_policy_text(text: str) -> str:
    text = re.sub(r"[*_`#~\[\](){}]", "", text)
    return text.lower().strip()


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _looks_like_policy_block(text: str) -> bool:
    normalized = _normalize_policy_text(text)
    if not normalized:
        return False

    for pattern in _LEADING_POLICY_PATTERNS:
        if pattern.search(normalized):
            return True

    meta_count = sum(1 for kw in _POLICY_META_KEYWORDS if kw in normalized)
    ctx_count = sum(1 for kw in _POLICY_CONTEXT_KEYWORDS if kw in normalized)
    if meta_count >= 2 or ctx_count >= 2 or (meta_count >= 1 and ctx_count >= 1):
        return True

    return False


def sanitize_answer_text(text: str) -> str:
    text = _THINK_BLOCK_PATTERN.sub("", text or "").strip()
    if not text:
        return ""

    paragraphs = _split_paragraphs(text)
    cleaned: list[str] = []
    leading = True
    for para in paragraphs:
        if leading and _looks_like_policy_block(para):
            continue
        leading = False
        cleaned.append(para)

    return "\n\n".join(cleaned).strip()


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


class SourcesCache:
    def __init__(self, max_size: int = 256):
        self._max_size = max_size
        self._lock = asyncio.Lock()
        self._cache: OrderedDict[str, list[dict]] = OrderedDict()

    async def set(self, session_id: str, sources: list[dict]) -> None:
        async with self._lock:
            self._cache[session_id] = sources
            self._cache.move_to_end(session_id)
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    async def get(self, session_id: str) -> list[dict] | None:
        async with self._lock:
            sources = self._cache.get(session_id)
            if sources is None:
                return None
            self._cache.move_to_end(session_id)
            return sources


def merge_sources(*source_lists: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for sources in source_lists:
        for item in sources or []:
            url = (item or {}).get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            url = url.strip()
            if url in seen:
                continue
            seen.add(url)
            merged.append(item)
    return merged


def model_answer_problem(answer: str, sources: list[dict]) -> tuple[str, str] | None:
    if answer.strip().split("\n", 1)[0].strip("*_` ") == NO_WEB_SEARCH_MARKER:
        return "no_web_search", "Search model reported that it has no web search access"
    if not sources and not extract_unique_urls(answer):
        return "no_sources", "Search model answer contained no source URLs"
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", answer.strip())
    body = re.sub(r"https?://\S+", "", body)
    body = re.sub(r"\[\d+\]", "", body).strip()
    sentences = [s.strip(" -*>#") for s in re.split(r"(?<=[.!?])\s+|(?<=[。！？；])|\n+", body)]
    sentences = [s for s in sentences if s]
    if len(body) <= 500 and sentences and all(_INTENT_SENTENCE.match(s) for s in sentences):
        return "preface_only", "Search model returned only a preface announcing a search"
    return None


def split_answer_and_sources(text: str) -> tuple[str, list[dict]]:
    raw = (text or "").strip()
    if not raw:
        return "", []

    if config.output_cleanup_enabled:
        cleaned = sanitize_answer_text(raw)
        if cleaned:
            raw = cleaned

    inline_sources = _extract_inline_citation_sources(raw)

    split = _split_function_call_sources(raw)
    if split:
        answer, sources = split
        return answer, merge_sources(sources, inline_sources)

    split = _split_heading_sources(raw)
    if split:
        answer, sources = split
        return answer, merge_sources(sources, inline_sources)

    split = _split_details_block_sources(raw)
    if split:
        answer, sources = split
        return answer, merge_sources(sources, inline_sources)

    split = _split_tail_link_block(raw)
    if split:
        answer, sources = split
        return answer, merge_sources(sources, inline_sources)

    return raw, inline_sources


def _split_function_call_sources(text: str) -> tuple[str, list[dict]] | None:
    matches = list(_SOURCES_FUNCTION_PATTERN.finditer(text))
    if not matches:
        return None

    for m in reversed(matches):
        open_paren_idx = m.end() - 1
        extracted = _extract_balanced_call_at_end(text, open_paren_idx)
        if not extracted:
            continue

        close_paren_idx, args_text = extracted
        sources = _parse_sources_payload(args_text)
        if not sources:
            continue

        answer = text[: m.start()].rstrip()
        return answer, sources

    return None


def _extract_balanced_call_at_end(text: str, open_paren_idx: int) -> tuple[int, str] | None:
    if open_paren_idx < 0 or open_paren_idx >= len(text) or text[open_paren_idx] != "(":
        return None

    depth = 1
    in_string: str | None = None
    escape = False

    for idx in range(open_paren_idx + 1, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == in_string:
                in_string = None
            continue

        if ch in ("'", '"'):
            in_string = ch
            continue

        if ch == "(":
            depth += 1
            continue
        if ch == ")":
            depth -= 1
            if depth == 0:
                if text[idx + 1 :].strip():
                    return None
                args_text = text[open_paren_idx + 1 : idx]
                return idx, args_text

    return None


def _split_heading_sources(text: str) -> tuple[str, list[dict]] | None:
    matches = list(_SOURCES_HEADING_PATTERN.finditer(text))
    if not matches:
        return None

    for m in reversed(matches):
        start = m.start()
        sources_text = text[start:]
        sources = _extract_sources_from_text(sources_text)
        if not sources:
            continue
        answer = text[:start].rstrip()
        return answer, sources
    return None


def _split_tail_link_block(text: str) -> tuple[str, list[dict]] | None:
    lines = text.splitlines()
    if not lines:
        return None

    idx = len(lines) - 1
    while idx >= 0 and not lines[idx].strip():
        idx -= 1
    if idx < 0:
        return None

    tail_end = idx
    link_like_count = 0
    while idx >= 0:
        line = lines[idx].strip()
        if not line:
            idx -= 1
            continue
        if not _is_link_only_line(line):
            break
        link_like_count += 1
        idx -= 1

    tail_start = idx + 1
    if link_like_count < 2:
        return None

    block_text = "\n".join(lines[tail_start : tail_end + 1])
    sources = _extract_sources_from_text(block_text)
    if not sources:
        return None

    answer = "\n".join(lines[:tail_start]).rstrip()
    return answer, sources


def _split_details_block_sources(text: str) -> tuple[str, list[dict]] | None:
    lower = text.lower()
    close_idx = lower.rfind("</details>")
    if close_idx == -1:
        return None
    tail = text[close_idx + len("</details>") :].strip()
    if tail:
        return None

    open_idx = lower.rfind("<details", 0, close_idx)
    if open_idx == -1:
        return None

    block_text = text[open_idx : close_idx + len("</details>")]
    sources = _extract_sources_from_text(block_text)
    if len(sources) < 2:
        return None

    answer = text[:open_idx].rstrip()
    return answer, sources


def _is_link_only_line(line: str) -> bool:
    stripped = re.sub(r"^\s*(?:[-*]|\d+\.)\s*", "", line).strip()
    if not stripped:
        return False
    if stripped.startswith(("http://", "https://")):
        return True
    citation = _PARENTHESIZED_CITATION_PATTERN.search(stripped)
    if citation and _has_prose(stripped[: citation.start()]):
        # A sentence that ends with its citation belongs to the answer, not to a trailing source list.
        return False
    if _MD_LINK_PATTERN.search(stripped):
        return True
    return False


def _has_prose(text: str) -> bool:
    text = _BARE_OR_ANGLE_URL_PATTERN.sub("", _MD_LINK_PATTERN.sub("", text))
    return re.search(r"[^\W\d_]", text) is not None


def _parse_sources_payload(payload: str) -> list[dict]:
    payload = (payload or "").strip().rstrip(";")
    if not payload:
        return []

    data: Any = None
    try:
        data = json.loads(payload)
    except Exception:
        try:
            data = ast.literal_eval(payload)
        except Exception:
            data = None

    if data is None:
        return _extract_sources_from_text(payload)

    if isinstance(data, dict):
        for key in ("sources", "citations", "references", "urls"):
            if key in data:
                return _normalize_sources(data[key])
        return _normalize_sources(data)

    return _normalize_sources(data)


def _normalize_sources(data: Any) -> list[dict]:
    items: list[Any]
    if isinstance(data, (list, tuple)):
        items = list(data)
    elif isinstance(data, dict):
        items = [data]
    else:
        items = [data]

    normalized: list[dict] = []
    seen: set[str] = set()

    for item in items:
        if isinstance(item, str):
            for url in extract_unique_urls(item):
                if url not in seen:
                    seen.add(url)
                    normalized.append({"url": url})
            continue

        if isinstance(item, (list, tuple)) and len(item) >= 2:
            title, url = item[0], item[1]
            if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in seen:
                seen.add(url)
                out: dict = {"url": url}
                if isinstance(title, str) and title.strip():
                    out["title"] = title.strip()
                normalized.append(out)
            continue

        if isinstance(item, dict):
            url = item.get("url") or item.get("href") or item.get("link")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            out: dict = {"url": url}
            title = item.get("title") or item.get("name") or item.get("label")
            if isinstance(title, str) and title.strip():
                out["title"] = title.strip()
            desc = item.get("description") or item.get("snippet") or item.get("content")
            if isinstance(desc, str) and desc.strip():
                out["description"] = desc.strip()
            normalized.append(out)
            continue

    return normalized


def _extract_sources_from_text(text: str) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()

    for title, url in _MD_LINK_PATTERN.findall(text or ""):
        url = (url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        title = (title or "").strip()
        if title:
            sources.append({"title": title, "url": url})
        else:
            sources.append({"url": url})

    for url in extract_unique_urls(text or ""):
        if url in seen:
            continue
        seen.add(url)
        sources.append({"url": url})

    return sources


def _extract_inline_citation_sources(text: str) -> list[dict]:
    sources: list[dict] = []
    seen: set[str] = set()
    for number, url in _INLINE_CITATION_LINK_PATTERN.findall(text or ""):
        url = (url or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"title": number, "url": url})
    return sources
