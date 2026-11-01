import pytest

from smart_search.sources import (
    model_answer_problem,
    sanitize_answer_text,
    split_answer_and_sources,
    merge_sources,
)


@pytest.mark.parametrize("answer", [
    "I'll look up how 2026 AI/LLM disk-cleanup agents decide deletions, plus MCP servers for usage analysis and the main safety lessons.",
    "I'll look into how LLM agents decide which files are safe to delete during disk cleanup, and what disk-usage MCP servers actually expose. Searching authoritative docs and recent writeups.",
    "I'll look up typesafe.ai, \"jev\", and any related open-source Python SDK on GitHub.",
    "我先检索权威来源。",
    "让我先查一下官方文档。",
    "Let me search https://typesafe.ai and GitHub for this.",
    "Searching the official docs at [TypeSafe](https://docs.typesafe.ai) now...",
])
def test_model_answer_problem_rejects_preface_only(answer):
    assert model_answer_problem(answer, [{"url": "https://example.org/a"}]) == (
        "preface_only", "Search model returned only a preface announcing a search",
    )


@pytest.mark.parametrize("answer", [
    "Jev is TypeSafe AI's System One model [1].",
    "I'll explain the difference. Responses API supports tools natively, while Chat Completions does not.",
    "检索增强生成（RAG）是一种把检索结果拼进提示词的方法。",
    "搜索引擎优化（SEO）主要看三件事：内容、链接和技术。",
    "Checking is done by the CLI before each run.",
    "我查到的结论是：Jev 是 TypeSafe 的模型。",
    "I'll look up the details below.\n\n## Summary\nJev returns typed probabilities instead of text.",
])
def test_model_answer_problem_accepts_substantive_answer(answer):
    assert model_answer_problem(answer, [{"url": "https://example.org/a"}]) is None


@pytest.mark.parametrize("answer", ["NO_WEB_SEARCH", "**NO_WEB_SEARCH**"])
def test_model_answer_problem_prioritizes_no_web_search_marker(answer):
    assert model_answer_problem(answer, [{"url": "https://example.org/a"}]) == (
        "no_web_search", "Search model reported that it has no web search access",
    )


def test_model_answer_problem_prioritizes_missing_sources():
    assert model_answer_problem("我先检索权威来源。", []) == (
        "no_sources", "Search model answer contained no source URLs",
    )


class TestSanitizeAnswerText:
    def test_removes_think_blocks(self):
        text = "<think>reasoning here</think>The actual answer."
        result = sanitize_answer_text(text)
        assert "think" not in result.lower()
        assert "The actual answer." in result

    def test_removes_nested_think_blocks(self):
        text = "Before<think>some\nmultiline\nthinking</think>After"
        result = sanitize_answer_text(text)
        assert result == "Before\n\nAfter" or "After" in result
        assert "thinking" not in result

    def test_removes_policy_blocks(self):
        text = "I cannot comply with that request.\n\nHere is the actual answer."
        result = sanitize_answer_text(text)
        assert "cannot comply" not in result
        assert "actual answer" in result

    def test_removes_chinese_policy_blocks(self):
        text = "我无法遵从这个请求。\n\n这是实际回答。"
        result = sanitize_answer_text(text)
        assert "无法遵从" not in result
        assert "实际回答" in result

    def test_preserves_normal_text(self):
        text = "This is a normal answer with no think blocks or policy text."
        result = sanitize_answer_text(text)
        assert result == text

    def test_empty_input(self):
        assert sanitize_answer_text("") == ""
        assert sanitize_answer_text(None) == ""

    def test_think_block_only(self):
        result = sanitize_answer_text("<think>only reasoning</think>")
        assert result == ""


class TestSplitAnswerAndSources:
    def test_no_sources(self):
        answer, sources = split_answer_and_sources("Just a plain answer.")
        assert answer == "Just a plain answer."
        assert sources == []

    def test_empty_input(self):
        answer, sources = split_answer_and_sources("")
        assert answer == ""
        assert sources == []

    def test_none_input(self):
        answer, sources = split_answer_and_sources(None)
        assert answer == ""
        assert sources == []

    def test_heading_sources(self):
        text = "Here is the answer.\n\n## Sources\n- [Example](https://example.com)\n- [Test](https://test.com)"
        answer, sources = split_answer_and_sources(text)
        assert "Here is the answer" in answer
        assert len(sources) >= 2
        urls = [s["url"] for s in sources]
        assert "https://example.com" in urls
        assert "https://test.com" in urls

    def test_function_call_sources(self):
        text = 'The answer is here.\n\nsources([{"url": "https://example.com", "title": "Ex"}])'
        answer, sources = split_answer_and_sources(text)
        assert "The answer is here" in answer
        assert len(sources) == 1
        assert sources[0]["url"] == "https://example.com"

    def test_inline_citation_sources_are_extracted_and_answer_keeps_links(self):
        text = "The answer cites [[1]](https://example.com/a) and [[2]](https://example.com/b)."
        answer, sources = split_answer_and_sources(text)
        assert answer == text
        assert [s["url"] for s in sources] == ["https://example.com/a", "https://example.com/b"]

    def test_inline_citation_sources_deduplicate_by_url(self):
        text = "A [[1]](https://example.com/a) and again [[2]](https://example.com/a)."
        answer, sources = split_answer_and_sources(text)
        assert answer == text
        assert len(sources) == 1
        assert sources[0]["url"] == "https://example.com/a"

    def test_inline_citations_merge_with_function_sources(self):
        text = 'A [[1]](https://example.com/a).\n\nsources([{"url": "https://example.com/a"}, {"url": "https://example.com/b"}])'
        answer, sources = split_answer_and_sources(text)
        assert "[[1]](https://example.com/a)" in answer
        assert [s["url"] for s in sources] == ["https://example.com/a", "https://example.com/b"]

    # Real gpt-5-search-api answers (2026-11-01): every sentence or bullet ends with a "([site](url))" citation.
    def test_sentences_ending_in_inline_citations_stay_in_the_answer(self):
        text = (
            "The latest stable release of Python (as of November 1, 2026) is **Python 3.15.2**, released on "
            "**October 26, 2026**. ([blog.python.org](https://blog.python.org/?utm_source=openai))\n\n"
            "For more details, see the official release announcement: “Python 3.15.2, 3.14.10, 3.13.18, 3.12.16 "
            "and 3.11.18 are out”. ([blog.python.org](https://blog.python.org/?utm_source=openai))"
        )
        answer, _ = split_answer_and_sources(text)
        assert answer == text

    def test_cited_bullet_facts_stay_in_the_answer(self):
        text = (
            "The arXiv paper that introduced the *Mamba* selective state space model is:\n\n"
            "- **arXiv ID**: 2312.00752 ([arxiv.org](https://arxiv.org/abs/2312.00752?utm_source=openai))\n"
            "- **Authors**: Albert Gu and Tri Dao ([arxiv.org](https://arxiv.org/abs/2312.00752?utm_source=openai))\n"
            "- **Date of first version**: December 1, 2023 ([arxiv.org](https://arxiv.org/abs/2312.00752?utm_source=openai))"
        )
        answer, _ = split_answer_and_sources(text)
        assert answer == text

    def test_chinese_sentence_with_inline_citation_stays_in_the_answer(self):
        text = (
            "国家统计局公布，前三季度GDP同比增长4.6%。([stats.gov.cn](https://www.stats.gov.cn/sj/zxfb/a.html))\n"
            "初步核算，国内生产总值为1071071亿元。（[stats.gov.cn](https://www.stats.gov.cn/sj/zxfb/a.html)）"
        )
        answer, _ = split_answer_and_sources(text)
        assert answer == text

    def test_trailing_link_list_still_splits_from_the_answer(self):
        text = (
            "Here is the answer.\n\n"
            "- [Example](https://example.com)\n"
            "[2] [Test](https://test.com)\n"
            "<https://example.org/a> ([example.org](https://example.org/a))"
        )
        answer, sources = split_answer_and_sources(text)
        assert answer == "Here is the answer."
        assert [s["url"] for s in sources] == ["https://example.com", "https://test.com", "https://example.org/a"]


def test_sources_module_imports_on_its_own():
    # utils used to import providers at runtime, so importing sources first failed halfway.
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run([sys.executable, "-c", "import smart_search.sources"], cwd=src,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-500:]


class TestMergeSources:
    def test_deduplicates_by_url(self):
        a = [{"url": "https://a.com"}, {"url": "https://b.com"}]
        b = [{"url": "https://b.com"}, {"url": "https://c.com"}]
        merged = merge_sources(a, b)
        urls = [s["url"] for s in merged]
        assert urls == ["https://a.com", "https://b.com", "https://c.com"]

    def test_empty_inputs(self):
        assert merge_sources([], []) == []
        assert merge_sources(None, None) == []

    def test_skips_invalid_entries(self):
        sources = [{"url": ""}, {"url": None}, {}, {"url": "https://valid.com"}]
        merged = merge_sources(sources)
        assert len(merged) == 1
        assert merged[0]["url"] == "https://valid.com"
