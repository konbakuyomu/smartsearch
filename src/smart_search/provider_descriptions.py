"""User-facing provider descriptions shared with Jev channel selection."""

PROVIDER_DESCRIPTIONS: dict[str, dict[str, dict[str, str]]] = {
    "xai-responses": {
        "search": {
            "en": "Answers questions with an xAI model, using web or X search when those tools are enabled.",
            "zh": "通过 xAI 模型回答问题；启用相应工具时可搜索网页或 X。",
            "guidance_en": "Best for broad questions needing a model answer or enabled web/X discovery; not sufficient for claims that require fetched page text.",
            "guidance_zh": "擅长综合回答，并在启用相应工具时发现网页、X 来源；不适合单独证明需要网页正文核验的结论。",
        },
    },
    "openai-compatible": {
        "search": {
            "en": "Searches the web and answers questions through the user's configured OpenAI-compatible search model or service.",
            "zh": "通过用户配置的 OpenAI 兼容搜索模型或服务检索网页并回答问题。",
            "guidance_en": "Best for general web discovery and synthesis; not a substitute for fetched page evidence. Coverage, freshness and citations depend on the upstream.",
            "guidance_zh": "擅长通用网页检索与综合回答；不适合直接充当网页正文证据。搜索范围、时效和引用由上游决定。",
        },
    },
    "context7": {
        "search": {
            "en": "Finds a matching software library and reads its documentation.",
            "zh": "查找匹配的软件库并读取其文档。",
            "guidance_en": "Best for library APIs, framework usage and code examples; unsuitable for general web facts or news.",
            "guidance_zh": "擅长类库 API、框架用法和代码示例；不适合一般网页事实或新闻检索。",
        },
    },
    "exa": {
        "search": {
            "en": "Finds web pages with URLs and query-relevant highlights.",
            "zh": "查找网页并返回链接和相关摘录。",
            "guidance_en": "Best for discovering documentation, papers and product pages; less suitable when this route must enforce domain, date or similar-page filters.",
            "guidance_zh": "擅长发现文档、论文与产品页面；不适合必须按域名、日期或相似页面筛选的路由请求。",
        },
    },
    "zhipu": {
        "search": {
            "en": "Searches the web through Zhipu's configured engine and returns linked results.",
            "zh": "通过已配置的智谱搜索引擎检索网页并返回链接结果。",
            "guidance_en": "Best for Chinese-language web source discovery; less suitable when recency or domain limits must be enforced, since this action sets neither.",
            "guidance_zh": "擅长发现中文网页来源；不适合必须强制限定时间或域名的请求，因为此操作未设置这些筛选。",
        },
    },
    "zhipu-mcp": {
        "search": {
            "en": "Discovers linked web results through the GLM Coding Plan MCP web_search_prime tool.",
            "zh": "通过 GLM Coding Plan 的 MCP web_search_prime 工具发现网页来源。",
            "guidance_en": "Best for finding web sources; unsuitable for reading complete page content.",
            "guidance_zh": "擅长发现网页来源；不适合读取完整页面正文。",
        },
    },
    "tavily": {
        "search": {
            "en": "Discovers web pages and excerpts through Tavily Search.",
            "zh": "通过 Tavily Search 发现网页和摘录。",
            "guidance_en": "Best for broad source discovery; unsuitable for reading full pages in this action.",
            "guidance_zh": "擅长广泛发现网页来源；此操作不适合读取完整页面正文。",
        },
        "fetch": {
            "en": "Extracts markdown content from a known URL through Tavily Extract.",
            "zh": "通过 Tavily Extract 读取已知链接的 Markdown 正文。",
            "guidance_en": "Best for reading a selected page; unsuitable for discovering new pages without a URL.",
            "guidance_zh": "擅长读取已选定的页面；没有 URL 时不适合用于发现新页面。",
        },
        "site_map": {
            "en": "Maps URLs within a site to discover pages.",
            "zh": "梳理站点内的链接以发现页面。",
            "guidance_en": "Best for exploring site structure through the separate site map command; unsuitable for extracting page text.",
            "guidance_zh": "擅长通过独立的站点地图命令探索网站结构；不适合提取页面正文。",
        },
    },
    "jina": {
        "fetch": {
            "en": "Reads a known public URL as markdown with Jina Reader.",
            "zh": "用 Jina Reader 将已知公开链接读取为 Markdown。",
            "guidance_en": "Best for public pages, including supported PDF and arXiv content; unsuitable for finding URLs. ReaderLM mode requires separate configuration and a key.",
            "guidance_zh": "擅长读取公开页面及受支持的 PDF、arXiv 内容；不适合发现新链接。ReaderLM 模式需单独配置和密钥。",
        },
    },
    "zhipu-mcp-reader": {
        "fetch": {
            "en": "Reads a known URL through the GLM Coding Plan MCP webReader tool.",
            "zh": "通过 GLM Coding Plan 的 MCP webReader 工具读取已知链接。",
            "guidance_en": "Best for reading page text from a URL already found; unsuitable for searching for new URLs.",
            "guidance_zh": "擅长读取已找到链接的正文；不适合搜索新链接。",
        },
    },
    "firecrawl": {
        "search": {
            "en": "Discovers web URLs and snippets through Firecrawl Search.",
            "zh": "通过 Firecrawl Search 发现网页链接和摘要。",
            "guidance_en": "Best for finding sources; unsuitable for reading full pages or structured extraction in this action.",
            "guidance_zh": "擅长发现网页来源；此操作不适合读取完整正文或做结构化提取。",
        },
        "fetch": {
            "en": "Scrapes a known page as markdown with Firecrawl.",
            "zh": "使用 Firecrawl 将已知页面抓取为 Markdown。",
            "guidance_en": "Best for known pages that need rendering; unsuitable for discovering new pages or requesting JSON extraction in this action.",
            "guidance_zh": "擅长抓取需要渲染的已知页面；此操作不适合发现新页面或请求 JSON 提取。",
        },
    },
    "tinyfish": {
        "search": {
            "en": "Finds web URLs and snippets through TinyFish Search.",
            "zh": "通过 TinyFish Search 查找网页链接和摘要。",
            "guidance_en": "Best for broad web discovery; less suitable for news, locale or domain constrained searches because this action passes only the query.",
            "guidance_zh": "擅长广泛发现网页；不适合需要新闻、地区或域名筛选的搜索，因为此操作只传入查询词。",
        },
        "fetch": {
            "en": "Fetches a known URL as markdown through TinyFish Fetch.",
            "zh": "通过 TinyFish Fetch 将已知链接读取为 Markdown。",
            "guidance_en": "Best for reading pages already found; unsuitable for source discovery or browser automation.",
            "guidance_zh": "擅长读取已找到的页面；不适合发现新来源或执行浏览器自动化。",
        },
    },
    "anysearch": {
        "search": {
            "en": "Searches AnySearch's available domains with a plain query.",
            "zh": "用普通查询词搜索 AnySearch 可用的领域。",
            "guidance_en": "Best for broad cross-domain discovery; less suitable when a specific vertical or domain must be selected explicitly.",
            "guidance_zh": "擅长跨领域发现来源；不适合必须显式指定垂直类别或领域的请求。",
        },
    },
    "sciverse": {
        "search": {
            "en": "Finds academic papers with SciVerse.",
            "zh": "通过 SciVerse 查找学术论文。",
            "guidance_en": "Best for scholarly paper discovery; unsuitable for general web search. Citation relationships and paper content require separate commands.",
            "guidance_zh": "擅长发现学术论文；不适合一般网页检索。引用关系和论文内容需通过独立命令读取。",
        },
    },
    "main-search": {
        "synthesis": {
            "en": "Combines retrieved evidence into a final answer with the configured main model.",
            "zh": "使用已配置的主模型将现有证据汇总为最终回答。",
            "guidance_en": "Best for explaining or comparing collected evidence; unsuitable for discovering or fetching new sources in this step.",
            "guidance_zh": "擅长解释或比较已有证据；此步骤不适合发现或抓取新来源。",
        },
    },
}
