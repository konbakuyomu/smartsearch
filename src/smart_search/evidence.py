"""Bounded, query-relevant excerpts shared by judgments and research reports."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit


_STOP = frozenset("the and how does what official documentation only from with this that which when where please explain compare using use latest sources source read summary results in on of to by as or at an be it is are for".split())


def _normalized(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().translate(str.maketrans({"–": "-", "—": "-", "−": "-"}))


def query_terms(query: str) -> set[str]:
    # URLs identify targets, rather than vocabulary to match in their navigation.
    query = re.sub(r"https?://\S+", " ", _normalized(query))
    terms = {s for s in re.findall(r"[a-z0-9][a-z0-9_.%-]+", query) if s not in _STOP}
    terms.update(part for term in list(terms) for part in term.split("-") if len(part) >= 2 and part not in _STOP)
    for phrase in re.findall(r"[\u3400-\u9fff]+", query):
        terms.update(phrase[i:i + 2] for i in range(len(phrase) - 1))
    return terms


def passage_score(text: str, terms: set[str]) -> float:
    plain = _normalized(text)
    matched = sum(1 for term in terms if (bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", plain)) if term.isascii() else term in plain))
    # Dense link lists and bibliography entries are weak answer excerpts even
    # when their titles repeat the query's vocabulary.
    links = len(re.findall(r"https?://|\]\(", text))
    reference = bool(re.search(r"(?im)^\s*(?:#{1,6}\s*)?(?:references|bibliography|参考文献)\s*$", text))
    return matched - min(4, links * 0.25) - (3 if reference else 0)


def relevant_excerpt(content: str, query: str, limit: int = 2000) -> str:
    """Return verbatim passages in document order, with explicit omission marks."""
    if len(content) <= limit:
        return content
    if limit <= 0:
        return ""
    terms = query_terms(query)
    # Short paragraph units keep a navigation header from hiding a nearby fact.
    units, weights, metadata = [], [], []
    section_weight = 0.0
    bibliography = False
    position = 0
    for paragraph in re.split(r"\n\s*\n", content):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)", paragraph)
        if heading:
            title = heading[1].casefold()
            bibliography = bibliography or bool(re.search(r"references|bibliography|参考文献", title))
            section_weight = (-5.0 if re.search(r"references|bibliography|参考文献", title)
                              else 1.5 if re.search(r"abstract|summary|conclusion|摘要|结论", title)
                              else 1.0 if re.search(r"results|discussion|experimental|materials|methods|结果|讨论|实验|材料", title)
                              else .25)
        width = max(160, min(600, limit // 2))
        for offset in range(0, len(paragraph), width):
            units.append(paragraph[offset:offset + width])
            weights.append(section_weight)
            unit = units[-1]
            position += len(unit)
            # Preserve the document's own header/identifiers before ranking body
            # passages. Bibliography titles and years are not article metadata.
            if not bibliography and position < 15000:
                is_title = bool(re.match(r"^#\s+\S", unit)) and len(unit) <= 350 and "http" not in unit
                identifier = bool(re.search(r"\b(?:DOI\s*:|10\.\d{4,9}/\S+|PMCID\s*:)", unit, re.I))
                year = bool(re.search(r"\b(?:19|20)\d{2}\b", unit) and re.search(r"conference|published|publication|journal|NIPS|NeurIPS|发表|出版|年", unit, re.I))
                if is_title or identifier or year:
                    metadata.append(len(units) - 1)
    ranked = sorted(range(len(units)), key=lambda i: (-(passage_score(units[i], terms) + weights[i]), i))
    selected, used = [], 0
    metadata_limit = min(850, limit // 2)
    for index in metadata:
        cost = len(units[index]) + (5 if selected else 0)
        if used + cost <= metadata_limit:
            selected.append(index)
            used += cost
    for index in ranked:
        if index in selected:
            continue
        cost = len(units[index]) + (5 if selected else 0)
        if used + cost <= limit:
            selected.append(index)
            used += cost
        if len(selected) >= 7:
            break
    if not selected:
        return content[:limit]
    return "\n[…]\n".join(units[index] for index in sorted(selected))[:limit]


def linked_sources(evidence: list[dict], query: str) -> list[dict]:
    """Expose relevant same-origin page links as discovery, never as read facts."""
    terms = query_terms(query)
    linked: dict[str, dict] = {}
    for item in evidence:
        parent = item.get("url", "")
        if not item.get("read") or not parent.startswith(("https://", "http://")):
            continue
        content = item.get("content", "")
        # Use labels and nearby text; a site footer cannot win solely by having
        # many links. Cross-origin links remain ordinary discovery candidates.
        for match in re.finditer(r"(?<!!)\[([^\]\n]{1,300})\]\(([^\s)]+)(?:\s+[^)]*)?\)", content):
            url = urljoin(parent, match[2].strip("<>"))
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or parsed.netloc != urlsplit(parent).netloc or parsed.username or parsed.password:
                continue
            if re.search(r"\.(?:png|jpe?g|svg|gif|zip|tgz|gz|xz|exe|msi|dmg|whl|sigstore|asc|sig|sha256|sha512|spdx\.json)$", parsed.path, re.I):
                continue
            url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))
            if url == parent.split("#")[0]:
                continue
            context = content[max(0, match.start() - 180):match.end() + 180]
            score = passage_score(match[1] + " " + parsed.path, terms) + .25 * max(0, passage_score(context, terms))
            if score <= 0:
                continue
            candidate = {"url": url, "title": match[1], "content": context, "provider": item.get("provider", ""),
                         "kind": "discovery", "read": False, "parent_url": parent, "link_score": score}
            if score > linked.get(url, {}).get("link_score", float("-inf")):
                linked[url] = candidate
    return sorted(linked.values(), key=lambda item: (-item["link_score"], item["url"]))[:20]
