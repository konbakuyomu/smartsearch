from typing import TYPE_CHECKING, List
import re

if TYPE_CHECKING:
    # A runtime import would load providers/__init__.py, whose providers import this
    # module back: importing smart_search.sources first then fails halfway.
    from .providers.base import SearchResult

_URL_PATTERN = re.compile(r'https?://[^\s<>"\'`，。、；：！？》）】\)]+')


def extract_unique_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for m in _URL_PATTERN.finditer(text):
        url = m.group().rstrip('.,;:!?')
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def format_extra_sources(tavily_results: list[dict] | None, firecrawl_results: list[dict] | None) -> str:
    sections = []
    idx = 1
    urls = []
    if firecrawl_results:
        lines = ["## Extra Sources [Firecrawl]"]
        for r in firecrawl_results:
            title = r.get("title") or "Untitled"
            url = r.get("url", "")
            if len(url) == 0:
                continue
            if url in urls:
                continue
            urls.append(url)
            desc = r.get("description", "")
            lines.append(f"{idx}. **[{title}]({url})**")
            if desc:
                lines.append(f"   {desc}")
            idx += 1
        sections.append("\n".join(lines))
    if tavily_results:
        lines = ["## Extra Sources [Tavily]"]
        for r in tavily_results:
            title = r.get("title") or "Untitled"
            url = r.get("url", "")
            if url in urls:
                continue
            content = r.get("content", "")
            lines.append(f"{idx}. **[{title}]({url})**")
            if content:
                lines.append(f"   {content}")
            idx += 1
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def format_search_results(results: List["SearchResult"]) -> str:
    if not results:
        return "No results found."

    formatted = []
    for i, result in enumerate(results, 1):
        parts = [f"## Result {i}: {result.title}"]

        if result.url:
            parts.append(f"**URL:** {result.url}")

        if result.snippet:
            parts.append(f"**Summary:** {result.snippet}")

        if result.source:
            parts.append(f"**Source:** {result.source}")

        if result.published_date:
            parts.append(f"**Published:** {result.published_date}")

        formatted.append("\n".join(parts))

    return "\n\n---\n\n".join(formatted)

fetch_prompt = """
# Profile: Web Content Fetcher

- **Language**: Preserve the original page's language. Do not translate the source text.
- **Role**: 你是一个专业的网页内容抓取和解析专家，获取指定 URL 的网页内容，并将其转换为与原网页高度一致的结构化 Markdown 文本格式。

---

## Workflow

### 1. URL 验证与内容获取
- 验证 URL 格式有效性，检查可访问性（处理重定向/超时）
- **关键**：优先识别页面目录/大纲结构（Table of Contents），作为内容抓取的导航索引
- 全量获取 HTML 内容，确保不遗漏任何章节或动态加载内容

### 2. 智能解析与内容提取
- **结构优先**：若存在目录/大纲，严格按其层级结构进行内容提取和组织
- 解析 HTML 文档树，识别所有内容元素：
  - 标题层级（h1-h6）及其嵌套关系
  - 正文段落、文本格式（粗体/斜体/下划线）
  - 列表结构（有序/无序/嵌套）
  - 表格（包含表头/数据行/合并单元格）
  - 代码块（行内代码/多行代码块/语言标识）
  - 引用块、分隔线
  - 图片（src/alt/title 属性）
  - 链接（内部/外部/锚点）

### 3. 内容清理与语义保留
- 移除非内容标签：`<script>`、`<style>`、`<iframe>`、`<noscript>`
- 过滤干扰元素：广告模块、追踪代码、社交分享按钮
- **保留语义信息**：图片 alt/title、链接 href/title、代码语言标识
- 特殊模块标注：导航栏、侧边栏、页脚用特殊标记保留

---

## Skills

### 1. 内容精准提取与还原
- **如果存在目录或者大纲，则按照目录或者大纲的结构进行提取**
- **完整保留原始内容结构**，不遗漏任何信息
- **准确识别并提取**标题、段落、列表、表格、代码块等所有元素
- **保持原网页的内容层次和逻辑关系**
- **精确处理特殊字符**，确保无乱码和格式错误
- **还原文本内容**，包括换行、缩进、空格等细节

### 2. 结构化组织与呈现
- **标题层级**：使用 `#`、`##`、`###` 等还原标题层级
- **目录结构**：使用列表生成 Table of Contents，带锚点链接
- **内容分区**：使用 `###` 或代码块（` ```section ``` `）明确划分 Section
- **嵌套结构**：使用缩进列表或引用块（`>`）保持层次关系
- **辅助模块**：侧边栏、导航等用特殊代码块（` ```sidebar ``` `、` ```nav ``` `）包裹

### 3. 格式转换优化
- **HTML 转 Markdown**：保持 100% 内容一致性
- **表格处理**：使用 Markdown 表格语法（`|---|---|`）
- **代码片段**：用 ` ```语言标识``` ` 包裹，保留原始缩进
- **图片处理**：转换为 `![alt](url)` 格式，保留所有属性
- **链接处理**：转换为 `[文本](URL)` 格式，保持完整路径
- **强调样式**：`<strong>` → `**粗体**`，`<em>` → `*斜体*`

### 4. 内容完整性保障
- **零删减原则**：不删减任何原网页文本内容
- **元数据保留**：保留时间戳、作者信息、标签等关键信息
- **多媒体标注**：视频、音频以链接或占位符标注（`[视频: 标题](URL)`）
- **动态内容处理**：尽可能抓取完整内容

---

## Rules

### 1. 内容一致性原则（核心）
- ✅ 返回内容必须与原网页内容**完全一致**，不能有信息缺失
- ✅ 保持原网页的**所有文本、结构和语义信息**
- ❌ **不进行**内容摘要、精简、改写或总结
- ✅ 保留原始的**段落划分、换行、空格**等格式细节

### 2. 格式转换标准
| HTML | Markdown | 示例 |
|------|----------|------|
| `<h1>`-`<h6>` | `#`-`######` | `# 标题` |
| `<strong>` | `**粗体**` | **粗体** |
| `<em>` | `*斜体*` | *斜体* |
| `<a>` | `[文本](url)` | [链接](url) |
| `<img>` | `![alt](url)` | ![图](url) |
| `<code>` | `` `代码` `` | `code` |
| `<pre><code>` | ` ```\n代码\n``` ` | 代码块 |

### 3. 输出质量要求
- **元数据头部**：
  ```markdown
  ---
  source: [原始URL]
  title: [网页标题]
  fetched_at: [抓取时间]
  ---
  ```
- **编码标准**：统一使用 UTF-8
- **可用性**：输出可直接用于文档生成或阅读

---

## Initialization

当接收到 URL 时：
1. 按 Workflow 执行抓取和处理
2. 返回完整的结构化 Markdown 文档
"""


url_describe_prompt = (
    "Browse the given URL. Return exactly two sections:\n\n"
    "Title: <page title from the page's own <title> tag or top heading; "
    "if missing/generic, craft one using key terms found in the page>\n\n"
    "Extracts: <copy 2-4 verbatim fragments from the page that best represent "
    "its core content. Each fragment must be the author's original words, "
    "wrapped in quotes, separated by ' | '. "
    "Do NOT paraphrase, rephrase, interpret, or describe. "
    "Do NOT write sentences like 'This page discusses...' or 'The author argues...'. "
    "You are a copy-paste machine.>\n\n"
    "Nothing else."
)

rank_sources_prompt = (
    "Given a user query and a numbered source list, output ONLY the source numbers "
    "reordered by relevance to the query (most relevant first). "
    "Format: space-separated integers on a single line (e.g., 14 12 1 3 5). "
    "Include every number exactly once. Nothing else."
)

NO_WEB_SEARCH_MARKER = "NO_WEB_SEARCH"

search_prompt = """You are a helpful research assistant. Answer the user's question thoroughly using web search results.

Guidelines:
- Infer the user's true intent even when the question is vague. Consider multiple angles.
- Search broadly first (5+ perspectives), then go deep on the 2-3 most relevant ones.
- Prioritize authoritative sources: official docs, Wikipedia, academic papers, reputable journalism.
- Search in English first for breadth, switch to Chinese when the topic demands it.
- Every factual claim should cite its source. More credible sources strengthen the answer.
- Lead with the most likely answer, then provide supporting analysis.
- Define technical terms in plain language. Use real-world analogies for complex concepts.
- Format output in clean Markdown. Use LaTeX for formulas, code blocks for scripts.
- Be direct and concise. No filler or unnecessary follow-up questions.
- Deliver the complete final answer in this reply. Never reply with only a plan, a preface, or an announcement of what you are going to search.
- Never claim to have searched or to have found nothing unless you actually received web search results in this conversation.
- If you cannot access web search results right now, reply with exactly NO_WEB_SEARCH and nothing else. Do not answer from memory.
"""
