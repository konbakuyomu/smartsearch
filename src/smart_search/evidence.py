"""Bounded, query-relevant excerpts shared by judgments and research reports."""

from __future__ import annotations

import re
import unicodedata


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
    units, weights = [], []
    section_weight = 0.0
    for paragraph in re.split(r"\n\s*\n", content):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        heading = re.match(r"^#{1,6}\s+(.+)", paragraph)
        if heading:
            title = heading[1].casefold()
            section_weight = (-5.0 if re.search(r"references|bibliography|参考文献", title)
                              else 1.5 if re.search(r"abstract|summary|conclusion|摘要|结论", title)
                              else 1.0 if re.search(r"results|discussion|experimental|materials|methods|结果|讨论|实验|材料", title)
                              else .25)
        width = max(160, min(600, limit // 2))
        for offset in range(0, len(paragraph), width):
            units.append(paragraph[offset:offset + width])
            weights.append(section_weight)
    ranked = sorted(range(len(units)), key=lambda i: (-(passage_score(units[i], terms) + weights[i]), i))
    selected, used = [], 0
    for index in ranked:
        cost = len(units[index]) + (7 if selected else 0)
        if used + cost <= limit:
            selected.append(index)
            used += cost
        if len(selected) >= 4:
            break
    if not selected:
        return content[:limit]
    return "\n[…]\n".join(units[index] for index in sorted(selected))[:limit]
