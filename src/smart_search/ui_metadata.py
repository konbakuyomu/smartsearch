"""Presentation metadata for the 68 config keys.

The config layer stores a flat set of key names with no grouping, labels, types or
descriptions, and the only human-readable label table lives inside the interactive
setup wizard's prompt list, which covers 50 of them. That is workable for a CLI that
asks one question at a time and hopeless for a page that has to show the whole
surface at once without burying the reader.

This module is deliberately additive. ``Config._CONFIG_KEYS`` stays authoritative for
which keys exist, and each getter's inline literal stays authoritative for what a key
defaults to; ``ConfigField.default`` mirrors it for display only. A test asserts the
two key sets are equal in both directions, so a 69th key cannot be added without the
UI learning about it.

Nothing here imports ``service``: provider ids are plain strings, checked against
``service.provider_profiles()`` by a test rather than by an import, so the lowest
config layer never gains a dependency on the highest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import Config


TIERS = ("essential", "enhancement", "advanced")
KINDS = ("secret", "url", "text", "int", "float", "enum", "bool", "csv")


@dataclass(frozen=True)
class Section:
    """One sidebar entry."""

    id: str
    order: int
    label_zh: str
    label_en: str
    blurb_zh: str
    blurb_en: str


@dataclass(frozen=True)
class ConfigField:
    """One editable config key, as the page needs to render it."""

    key: str
    section: str
    tier: str
    kind: str
    label_zh: str
    label_en: str
    help_zh: str = ""
    help_en: str = ""
    default: str = ""
    choices: tuple[str, ...] = ()
    provider: str = ""
    capabilities: tuple[str, ...] = ()
    placeholder: str = ""
    # Where to get this credential, and where the provider documents it. Both are
    # copied from the README's provider table; a test asserts they still match it,
    # so neither can drift or be invented.
    key_url: str = ""
    docs_url: str = ""


SECTIONS: tuple[Section, ...] = (
    Section(
        id="status",
        order=1,
        label_zh="概览",
        label_en="Overview",
        blurb_zh="现在生效的配置、能力是否齐全、哪个服务商在冷却。",
        blurb_en="What is in effect, whether the minimum profile is met, and which providers are cooling down.",
    ),
    Section(
        id="getting_started",
        order=2,
        label_zh="先配这三样",
        label_en="Start here",
        blurb_zh="主搜索、文档检索、网页抓取，每类配一个就能跑。其余的都可以先不管。",
        blurb_en="One provider each for main search, docs lookup and page fetching is enough to run. Everything else can wait.",
    ),
    Section(
        id="providers",
        order=3,
        label_zh="数据源",
        label_en="Providers",
        blurb_zh="每张卡片一个服务商。填好 key 之后点「测试」，就知道它现在还能不能用。",
        blurb_en="One card per provider. Fill in a key, then hit Test to find out whether it still works.",
    ),
    Section(
        id="routing",
        order=4,
        label_zh="意图路由",
        label_en="Intent routing",
        blurb_zh="决定一个问题该走哪几类能力。不配也能用，规则兜底。",
        blurb_en="Decides which capabilities a question needs. Optional; rules cover it when nothing is configured.",
    ),
    Section(
        id="reliability",
        order=5,
        label_zh="超时与兜底",
        label_en="Timeouts and fallback",
        blurb_zh="等多久、失败之后怎么办、冷却多长时间。默认值适合大多数人。",
        blurb_en="How long to wait, what happens after a failure, how long a dead provider stays out. The defaults suit most people.",
    ),
    Section(
        id="diagnostics",
        order=6,
        label_zh="日志与调试",
        label_en="Logging and debugging",
        blurb_zh="出问题的时候才需要动这里。",
        blurb_en="Only worth touching when something is wrong.",
    ),
    Section(
        id="tryit",
        order=8,
        label_zh="试跑一条",
        label_en="Try it",
        blurb_zh="先用不花钱的 route 看它打算走哪几类能力，确认配置对了再跑真实搜索。",
        blurb_en="Start with route, which costs nothing and just shows which capabilities a query needs, then run a real search once the config looks right.",
    ),
    Section(
        id="skills",
        order=7,
        label_zh="Skill 安装",
        label_en="Skill install",
        blurb_zh="把 smart-search 的用法装进你的 AI 工具，它才知道有这个命令。",
        blurb_en="Installs the smart-search skill into your AI tools so they know the command exists.",
    ),
)


def _f(**kwargs: Any) -> ConfigField:
    return ConfigField(**kwargs)


CONFIG_FIELDS: tuple[ConfigField, ...] = (
    # ---- getting_started: main_search -------------------------------------
    _f(key="XAI_API_KEY", section="getting_started", tier="essential", kind="secret",
       label_zh="xAI API Key", label_en="xAI API key",
       help_zh="用 xAI 做主搜索时填这个。和下面的 OpenAI 兼容接口二选一即可。",
       help_en="Fill this to use xAI for main search. Either this or the OpenAI-compatible block below is enough.",
       provider="xai-responses", capabilities=("main_search",), placeholder="xai-...",
       key_url="https://console.x.ai/team/default/api-keys",
       docs_url="https://docs.x.ai/docs"),
    _f(key="XAI_API_URL", section="getting_started", tier="advanced", kind="url",
       label_zh="xAI API 地址", label_en="xAI Responses API URL",
       help_zh="用官方地址就别动。走代理或中转时才改。",
       help_en="Leave it alone unless you go through a proxy or relay.",
       default="https://api.x.ai/v1", provider="xai-responses", capabilities=("main_search",)),
    _f(key="XAI_MODEL", section="getting_started", tier="advanced", kind="text",
       label_zh="xAI 模型", label_en="xAI Responses model",
       help_zh="留空用默认模型。", help_en="Leave empty for the default model.",
       default=Config._DEFAULT_MODEL, provider="xai-responses", capabilities=("main_search",)),
    _f(key="XAI_TOOLS", section="getting_started", tier="advanced", kind="csv",
       label_zh="xAI 联网工具", label_en="xAI Responses tools",
       help_zh="逗号分隔。可选 web_search 和 x_search。",
       help_en="Comma separated. web_search and x_search are the supported values.",
       default=Config._DEFAULT_XAI_TOOLS, choices=tuple(sorted(Config._ALLOWED_XAI_TOOLS)),
       provider="xai-responses", capabilities=("main_search",)),
    _f(key="OPENAI_COMPATIBLE_API_URL", section="getting_started", tier="essential", kind="url",
       label_zh="OpenAI 兼容接口地址", label_en="OpenAI-compatible API URL",
       help_zh="任何兼容 OpenAI 协议的服务都行。要和下面的 key 一起填才算配好。",
       help_en="Any OpenAI-protocol service works. Counts as configured only together with the key below.",
       provider="openai-compatible", capabilities=("main_search",),
       placeholder="https://api.example.com/v1"),
    _f(key="OPENAI_COMPATIBLE_API_KEY", section="getting_started", tier="essential", kind="secret",
       label_zh="OpenAI 兼容接口 Key", label_en="OpenAI-compatible API key",
       help_zh="下面的链接是 OpenAI 官方的。用中转或第三方服务的话，key 去对应服务商那里拿。",
       help_en="The link below is OpenAI's own. Using a relay or another provider? Get the key from them instead.",
       provider="openai-compatible", capabilities=("main_search",), placeholder="sk-...",
       key_url="https://platform.openai.com/api-keys",
       docs_url="https://platform.openai.com/docs"),
    _f(key="OPENAI_COMPATIBLE_MODEL", section="getting_started", tier="essential", kind="text",
       label_zh="模型名", label_en="OpenAI-compatible model",
       help_zh="按服务商文档填，例如 gpt-4o、deepseek-chat。",
       help_en="Whatever your provider documents, e.g. gpt-4o or deepseek-chat.",
       provider="openai-compatible", capabilities=("main_search",)),
    _f(key="OPENAI_COMPATIBLE_FALLBACK_MODELS", section="getting_started", tier="advanced", kind="csv",
       label_zh="备用模型", label_en="Fallback models",
       help_zh="逗号分隔。主模型不可用时按顺序往下试。",
       help_en="Comma separated. Tried in order when the main model is unavailable.",
       provider="openai-compatible", capabilities=("main_search",)),
    _f(key="OPENAI_COMPATIBLE_API_MODE", section="getting_started", tier="advanced", kind="enum",
       label_zh="接口模式", label_en="API mode",
       help_zh="大多数服务用 chat-completions。",
       help_en="Most services want chat-completions.",
       default=Config._DEFAULT_OPENAI_COMPATIBLE_API_MODE,
       choices=tuple(sorted(Config._ALLOWED_OPENAI_COMPATIBLE_API_MODES)),
       provider="openai-compatible", capabilities=("main_search",)),
    _f(key="OPENAI_COMPATIBLE_STREAM", section="getting_started", tier="advanced", kind="bool",
       label_zh="流式返回", label_en="Stream responses",
       help_zh="部分服务只在流式下才肯长时间思考。", help_en="Some services only think for long under streaming.",
       default="false", provider="openai-compatible", capabilities=("main_search",)),

    # ---- providers: Exa ----------------------------------------------------
    _f(key="EXA_API_KEY", section="providers", tier="essential", kind="secret",
       label_zh="Exa API Key", label_en="Exa API key",
       help_zh="文档检索能力的两个选项之一。", help_en="One of the two options for docs search.",
       provider="exa", capabilities=("docs_search",),
       key_url="https://dashboard.exa.ai/api-keys",
       docs_url="https://docs.exa.ai/"),
    _f(key="EXA_BASE_URL", section="providers", tier="advanced", kind="url",
       label_zh="Exa 地址", label_en="Exa base URL", default="https://api.exa.ai",
       provider="exa", capabilities=("docs_search",)),
    _f(key="EXA_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="Exa 超时（秒）", label_en="Exa timeout (seconds)", default="30",
       provider="exa", capabilities=("docs_search",)),

    # ---- providers: Context7 ----------------------------------------------
    _f(key="CONTEXT7_API_KEY", section="providers", tier="essential", kind="secret",
       label_zh="Context7 API Key", label_en="Context7 API key",
       help_zh="查开源库文档用。文档检索能力的另一个选项。",
       help_en="Looks up open-source library docs. The other docs-search option.",
       provider="context7", capabilities=("docs_search",),
       key_url="https://context7.com/",
       docs_url="https://context7.com/docs"),
    _f(key="CONTEXT7_BASE_URL", section="providers", tier="advanced", kind="url",
       label_zh="Context7 地址", label_en="Context7 base URL", default="https://context7.com",
       provider="context7", capabilities=("docs_search",)),
    _f(key="CONTEXT7_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="Context7 超时（秒）", label_en="Context7 timeout (seconds)", default="30",
       provider="context7", capabilities=("docs_search",)),

    # ---- providers: Zhipu web search --------------------------------------
    _f(key="ZHIPU_API_KEY", section="providers", tier="enhancement", kind="secret",
       label_zh="智谱 API Key", label_en="Zhipu API key",
       help_zh="国内时效内容搜得比较好。属于可选增强，不配也能跑。",
       help_en="Good at recent Chinese-language content. Optional; things run without it.",
       provider="zhipu", capabilities=("web_search",),
       key_url="https://open.bigmodel.cn/usercenter/apikeys",
       docs_url="https://docs.bigmodel.cn/cn/guide/tools/web-search"),
    _f(key="ZHIPU_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="智谱搜索地址", label_en="Zhipu Web Search API URL",
       default="https://open.bigmodel.cn/api", provider="zhipu", capabilities=("web_search",)),
    _f(key="ZHIPU_SEARCH_ENGINE", section="providers", tier="advanced", kind="text",
       label_zh="智谱搜索服务", label_en="Zhipu search service",
       help_zh="search_std / search_pro / search_pro_sogou / search_pro_quark，或自定义。",
       help_en="search_std, search_pro, search_pro_sogou, search_pro_quark, or a custom one.",
       default="search_std", provider="zhipu", capabilities=("web_search",)),
    _f(key="ZHIPU_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="智谱超时（秒）", label_en="Zhipu timeout (seconds)", default="30",
       provider="zhipu", capabilities=("web_search",)),

    # ---- providers: Zhipu Coding Plan MCP ---------------------------------
    _f(key="ZHIPU_MCP_API_KEY", section="providers", tier="essential", kind="secret",
       label_zh="智谱 Coding Plan MCP Key", label_en="Zhipu Coding Plan MCP API key",
       help_zh="一个 key 同时提供搜索和网页抓取，抓取那一路可以满足最低配置。",
       help_en="One key serves both search and page fetching; the reader side satisfies the minimum profile.",
       provider="zhipu-mcp", capabilities=("web_search", "web_fetch"),
       key_url="https://open.bigmodel.cn/usercenter/apikeys",
       docs_url="https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server"),
    _f(key="ZHIPU_MCP_SEARCH_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="智谱 MCP 搜索地址", label_en="Zhipu Coding Plan search MCP URL",
       default="https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
       provider="zhipu-mcp", capabilities=("web_search",)),
    _f(key="ZHIPU_MCP_READER_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="智谱 MCP 阅读地址", label_en="Zhipu Coding Plan reader MCP URL",
       default="https://open.bigmodel.cn/api/mcp/web_reader/mcp",
       provider="zhipu-mcp-reader", capabilities=("web_fetch",),
       docs_url="https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server"),
    _f(key="ZHIPU_MCP_ZREAD_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="智谱 MCP zread 地址", label_en="Zhipu Coding Plan zread MCP URL",
       default="https://open.bigmodel.cn/api/mcp/zread/mcp",
       provider="zhipu-mcp", capabilities=("docs_search",),
       docs_url="https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server"),
    _f(key="ZHIPU_MCP_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="智谱 MCP 超时（秒）", label_en="Zhipu Coding Plan MCP timeout (seconds)", default="30",
       provider="zhipu-mcp", capabilities=("web_search", "web_fetch")),

    # ---- providers: Jina ---------------------------------------------------
    _f(key="JINA_API_KEY", section="providers", tier="essential", kind="secret",
       label_zh="Jina API Key", label_en="Jina API key",
       help_zh="把网页转成干净正文。注意没有 key 的匿名模式不算满足最低配置。",
       help_en="Turns a page into clean text. Anonymous use does not satisfy the minimum profile.",
       provider="jina", capabilities=("web_fetch",),
       key_url="https://jina.ai/",
       docs_url="https://jina.ai/reader/"),
    _f(key="JINA_READER_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="Jina Reader 地址", label_en="Jina Reader API URL", default="https://r.jina.ai",
       provider="jina", capabilities=("web_fetch",)),
    _f(key="JINA_RESPOND_WITH", section="providers", tier="advanced", kind="text",
       label_zh="Jina 返回模式", label_en="Jina respond-with mode",
       help_zh="可留空。例如 readerlm-v2。", help_en="Optional, e.g. readerlm-v2.",
       provider="jina", capabilities=("web_fetch",)),
    _f(key="JINA_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="Jina 超时（秒）", label_en="Jina timeout (seconds)", default="30",
       provider="jina", capabilities=("web_fetch",)),

    # ---- providers: Tavily -------------------------------------------------
    _f(key="TAVILY_API_KEY", section="providers", tier="essential", kind="secret",
       label_zh="Tavily API Key", label_en="Tavily API key",
       help_zh="搜索和抓取都能做，一个 key 顶两类能力。",
       help_en="Does both search and fetching, so one key covers two capabilities.",
       provider="tavily", capabilities=("web_search", "web_fetch", "site_map"),
       key_url="https://app.tavily.com/home",
       docs_url="https://docs.tavily.com/"),
    _f(key="TAVILY_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="Tavily 地址", label_en="Tavily API URL", default="https://api.tavily.com",
       provider="tavily", capabilities=("web_search", "web_fetch")),
    _f(key="TAVILY_ENABLED", section="providers", tier="advanced", kind="bool",
       label_zh="启用 Tavily", label_en="Tavily enabled",
       help_zh="关掉之后即使填了 key 也不会被使用。",
       help_en="Turning this off makes Tavily unused even with a key saved.",
       default="true", provider="tavily", capabilities=("web_search", "web_fetch")),
    _f(key="TAVILY_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="Tavily 超时（秒）", label_en="Tavily timeout (seconds)", default="30",
       provider="tavily", capabilities=("web_search", "web_fetch")),

    # ---- providers: Firecrawl ---------------------------------------------
    _f(key="FIRECRAWL_API_KEY", section="providers", tier="enhancement", kind="secret",
       label_zh="Firecrawl API Key", label_en="Firecrawl API key",
       help_zh="抓取兜底链的最后一环。这个服务商没有便宜的校验接口，所以只能看出 key 填没填。",
       help_en="Last resort in the fetch chain. No cheap verification endpoint, so only presence can be checked.",
       provider="firecrawl", capabilities=("web_fetch", "web_search"),
       key_url="https://www.firecrawl.dev/app/api-keys",
       docs_url="https://docs.firecrawl.dev/"),
    _f(key="FIRECRAWL_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="Firecrawl 地址", label_en="Firecrawl API URL", default="https://api.firecrawl.dev/v2",
       provider="firecrawl", capabilities=("web_fetch", "web_search")),

    # ---- providers: AnySearch ---------------------------------------------
    _f(key="ANYSEARCH_API_KEY", section="providers", tier="enhancement", kind="secret",
       label_zh="AnySearch API Key", label_en="AnySearch API key",
       help_zh="垂直领域搜索，实验性。", help_en="Vertical-domain search. Experimental.",
       provider="anysearch", capabilities=("vertical_search",),
       key_url="https://www.anysearch.com/console/api-keys",
       docs_url="https://www.anysearch.com/docs"),
    _f(key="ANYSEARCH_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="AnySearch 地址", label_en="AnySearch MCP API URL",
       default="https://api.anysearch.com/mcp", provider="anysearch", capabilities=("vertical_search",)),
    _f(key="ANYSEARCH_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="AnySearch 超时（秒）", label_en="AnySearch timeout (seconds)", default="30",
       provider="anysearch", capabilities=("vertical_search",)),

    # ---- providers: Sciverse ----------------------------------------------
    _f(key="SCIVERSE_API_TOKEN", section="providers", tier="enhancement", kind="secret",
       label_zh="Sciverse API Token", label_en="Sciverse API token",
       help_zh="学术论文检索，实验性，只在明确指定时才会被用到。",
       help_en="Academic paper search. Experimental, and only used when asked for explicitly.",
       provider="sciverse", capabilities=("vertical_search",),
       docs_url="https://github.com/opendatalab/Sciverse-Agent-Tools"),
    _f(key="SCIVERSE_API_URL", section="providers", tier="advanced", kind="url",
       label_zh="Sciverse 地址", label_en="Sciverse API URL", default="https://api.sciverse.space",
       provider="sciverse", capabilities=("vertical_search",)),
    _f(key="SCIVERSE_TIMEOUT_SECONDS", section="providers", tier="advanced", kind="float",
       label_zh="Sciverse 超时（秒）", label_en="Sciverse timeout (seconds)", default="30",
       provider="sciverse", capabilities=("vertical_search",)),

    # ---- routing -----------------------------------------------------------
    _f(key="SMART_SEARCH_INTENT_ROUTER", section="routing", tier="advanced", kind="enum",
       label_zh="路由模式", label_en="Intent router mode",
       help_zh="hybrid 会在规则之外再问一次模型；rules 只用规则；off 全关。",
       help_en="hybrid asks a model on top of the rules, rules uses rules only, off disables it.",
       default=Config._DEFAULT_INTENT_ROUTER_MODE,
       choices=tuple(sorted(Config._ALLOWED_INTENT_ROUTER_MODES))),
    _f(key="INTENT_EMBEDDING_API_URL", section="routing", tier="advanced", kind="url",
       label_zh="向量接口地址", label_en="Intent embedding API URL"),
    _f(key="INTENT_EMBEDDING_API_KEY", section="routing", tier="advanced", kind="secret",
       label_zh="向量接口 Key", label_en="Intent embedding API key"),
    _f(key="INTENT_EMBEDDING_MODEL", section="routing", tier="advanced", kind="text",
       label_zh="向量模型", label_en="Intent embedding model"),
    _f(key="INTENT_EMBEDDING_THRESHOLD", section="routing", tier="advanced", kind="float",
       label_zh="向量判定阈值", label_en="Intent embedding threshold",
       help_zh="0 到 1 之间。", help_en="Between 0 and 1.",
       default=Config._DEFAULT_INTENT_EMBEDDING_THRESHOLD),
    _f(key="INTENT_EMBEDDING_MARGIN", section="routing", tier="advanced", kind="float",
       label_zh="向量判定间距", label_en="Intent embedding margin",
       help_zh="0 到 1 之间。", help_en="Between 0 and 1.",
       default=Config._DEFAULT_INTENT_EMBEDDING_MARGIN),
    _f(key="INTENT_CLASSIFIER_API_URL", section="routing", tier="advanced", kind="url",
       label_zh="分类模型地址", label_en="Intent classifier API URL"),
    _f(key="INTENT_CLASSIFIER_API_KEY", section="routing", tier="advanced", kind="secret",
       label_zh="分类模型 Key", label_en="Intent classifier API key"),
    _f(key="INTENT_CLASSIFIER_MODEL", section="routing", tier="advanced", kind="text",
       label_zh="分类模型", label_en="Intent classifier model"),
    _f(key="INTENT_ROUTER_TIMEOUT_SECONDS", section="routing", tier="advanced", kind="float",
       label_zh="路由超时（秒）", label_en="Intent router timeout (seconds)",
       default=Config._DEFAULT_INTENT_ROUTER_TIMEOUT_SECONDS),
    _f(key="SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS", section="routing", tier="advanced", kind="csv",
       label_zh="优先使用的数据源", label_en="Preferred providers",
       help_zh="逗号分隔的 provider id，深度研究时优先走这些。",
       help_en="Comma-separated provider ids to prefer during deep research."),
    _f(key="SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS", section="routing", tier="advanced", kind="csv",
       label_zh="禁用的数据源", label_en="Disabled providers",
       help_zh="逗号分隔的 provider id，深度研究时完全不走这些。",
       help_en="Comma-separated provider ids to keep out of deep research entirely."),

    # ---- reliability -------------------------------------------------------
    _f(key="SMART_SEARCH_VALIDATION_LEVEL", section="reliability", tier="advanced", kind="enum",
       label_zh="校验等级", label_en="Validation level",
       help_zh="strict 查得更严也更慢。", help_en="strict checks harder and runs slower.",
       default=Config._DEFAULT_VALIDATION_LEVEL, choices=tuple(sorted(Config._ALLOWED_VALIDATION_LEVELS))),
    _f(key="SMART_SEARCH_FALLBACK_MODE", section="reliability", tier="advanced", kind="enum",
       label_zh="兜底模式", label_en="Fallback mode",
       help_zh="auto 会在一个数据源失败后自动换下一个。",
       help_en="auto moves on to the next provider when one fails.",
       default=Config._DEFAULT_FALLBACK_MODE, choices=tuple(sorted(Config._ALLOWED_FALLBACK_MODES))),
    _f(key="SMART_SEARCH_MINIMUM_PROFILE", section="reliability", tier="advanced", kind="enum",
       label_zh="最低配置检查", label_en="Minimum profile",
       help_zh="standard 会在三类必需能力缺一时直接报错。关掉之后出问题更难查。",
       help_en="standard refuses to run when any of the three required capabilities is missing.",
       default=Config._DEFAULT_MINIMUM_PROFILE, choices=tuple(sorted(Config._ALLOWED_MINIMUM_PROFILES))),
    _f(key="SMART_SEARCH_TIMEOUT_SECONDS", section="reliability", tier="advanced", kind="float",
       label_zh="搜索总预算（秒）", label_en="Search budget (seconds)",
       help_zh="一整条搜索从开始到结束的上限。推理模型慢的时候需要调大。",
       help_en="Ceiling for one whole search. Raise it when a reasoning model is slow.",
       default=Config._DEFAULT_SEARCH_TIMEOUT_SECONDS),
    _f(key="SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS", section="reliability", tier="advanced", kind="float",
       label_zh="失败冷却时长（秒）", label_en="Provider failure cooldown (seconds)",
       help_zh="一个数据源挂了之后多久不再尝试。填 0 关闭冷却。",
       help_en="How long a failing provider is skipped. 0 disables cooldown.",
       default=Config._DEFAULT_PROVIDER_COOLDOWN_SECONDS),
    _f(key="SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD", section="reliability", tier="advanced", kind="int",
       label_zh="冷却触发次数", label_en="Failures before cooldown",
       help_zh="连续失败几次才冷却。鉴权错误第一次就冷却，不看这个值。",
       help_en="Consecutive soft failures before cooldown. Auth errors cool down on the first one regardless.",
       default=Config._DEFAULT_PROVIDER_FAILURE_THRESHOLD),
    _f(key="SMART_SEARCH_RETRY_MAX_ATTEMPTS", section="reliability", tier="advanced", kind="int",
       label_zh="重试次数", label_en="Retry max attempts", default="3"),
    _f(key="SMART_SEARCH_RETRY_MULTIPLIER", section="reliability", tier="advanced", kind="float",
       label_zh="重试退避倍数", label_en="Retry backoff multiplier", default="1"),
    _f(key="SMART_SEARCH_RETRY_MAX_WAIT", section="reliability", tier="advanced", kind="int",
       label_zh="重试最长等待（秒）", label_en="Retry max wait (seconds)", default="10"),

    # ---- diagnostics -------------------------------------------------------
    _f(key="SMART_SEARCH_DEBUG", section="diagnostics", tier="advanced", kind="bool",
       label_zh="调试输出", label_en="Debug output", default="false"),
    _f(key="SMART_SEARCH_LOG_LEVEL", section="diagnostics", tier="advanced", kind="text",
       label_zh="日志级别", label_en="Log level", default="INFO"),
    _f(key="SMART_SEARCH_LOG_DIR", section="diagnostics", tier="advanced", kind="text",
       label_zh="日志目录", label_en="Log directory", default="logs"),
    _f(key="SMART_SEARCH_LOG_TO_FILE", section="diagnostics", tier="advanced", kind="bool",
       label_zh="写日志文件", label_en="Log to file", default="false"),
    _f(key="SMART_SEARCH_OUTPUT_CLEANUP", section="diagnostics", tier="advanced", kind="bool",
       label_zh="清理输出", label_en="Clean up output", default="true"),
    _f(key="SSL_VERIFY", section="diagnostics", tier="advanced", kind="bool",
       label_zh="校验 SSL 证书", label_en="Verify SSL certificates",
       help_zh="关掉只该是临时排查手段。", help_en="Turning this off should only ever be a temporary debugging step.",
       default="true"),
)

FIELDS_BY_KEY: dict[str, ConfigField] = {item.key: item for item in CONFIG_FIELDS}


# Machine-readable status values that reach a user-facing surface. The native
# frontends render whatever the backend hands them, so without a table here the
# UI ends up showing `closed`, `up_to_date` or `provider.test` verbatim in an
# otherwise Chinese window. Frontends look a value up and fall back to printing
# it unchanged, so an unlisted value degrades instead of disappearing.
STATUS_LABELS: dict[str, dict[str, str]] = {
    # provider_health[].state
    "closed": {"zh": "正常", "en": "Normal"},
    "cooldown": {"zh": "冷却中", "en": "Cooling down"},
    # test result probe kind
    "main": {"zh": "主搜索探测", "en": "Main-search probe"},
    "live": {"zh": "真实请求", "en": "Live request"},
    "presence": {"zh": "仅检查已填写", "en": "Presence only"},
    "shared": {"zh": "共用凭据", "en": "Shared credential"},
    "none": {"zh": "无探针", "en": "No probe"},
    # connection-test status
    "ok": {"zh": "通过", "en": "Passed"},
    "not_configured": {"zh": "未配置", "en": "Not configured"},
    "configured": {"zh": "已填写，未验证", "en": "Filled in, unverified"},
    "disabled": {"zh": "已停用", "en": "Disabled"},
    "skipped": {"zh": "已跳过", "en": "Skipped"},
    "warning": {"zh": "有警告", "en": "Warning"},
    "timeout": {"zh": "超时", "en": "Timed out"},
    "error": {"zh": "失败", "en": "Failed"},
    "auth_error": {"zh": "鉴权失败", "en": "Auth failed"},
    "config_error": {"zh": "配置有误", "en": "Bad configuration"},
    "rate_limited": {"zh": "被限流", "en": "Rate limited"},
    "network_error": {"zh": "网络错误", "en": "Network error"},
    "parse_error": {"zh": "解析失败", "en": "Parse failed"},
    "provider_error": {"zh": "服务商报错", "en": "Provider error"},
    "parameter_error": {"zh": "参数有误", "en": "Bad parameter"},
    "runtime_error": {"zh": "运行出错", "en": "Runtime error"},
    "evidence_error": {"zh": "证据缺失", "en": "Evidence missing"},
    # run lifecycle
    "running": {"zh": "进行中", "en": "Running"},
    "cancelling": {"zh": "正在取消", "en": "Cancelling"},
    "cancelled": {"zh": "已取消", "en": "Cancelled"},
    "interrupted": {"zh": "已中断", "en": "Interrupted"},
    "finished": {"zh": "已完成", "en": "Finished"},
    "completed": {"zh": "已完成", "en": "Completed"},
    "failed": {"zh": "失败", "en": "Failed"},
    "stale": {"zh": "记录过期", "en": "Stale"},
    # skill install status
    "up_to_date": {"zh": "已是最新", "en": "Up to date"},
    "missing": {"zh": "未安装", "en": "Not installed"},
    "extra_files": {"zh": "有多余文件", "en": "Extra files present"},
    # config value source
    "environment": {"zh": "环境变量", "en": "Environment variable"},
    "config_file": {"zh": "配置文件", "en": "Config file"},
    "default": {"zh": "默认值", "en": "Default"},
}


def status_label(value: str, lang: str = "zh") -> str:
    """Translate one status value, falling back to the raw value."""
    entry = STATUS_LABELS.get(str(value or "").strip())
    if not entry:
        return str(value or "")
    return entry.get(lang) or entry.get("en") or str(value)


def metadata_payload() -> dict[str, Any]:
    """Serialise sections and fields for the page."""
    return {
        "sections": [
            {
                "id": section.id,
                "order": section.order,
                "label_zh": section.label_zh,
                "label_en": section.label_en,
                "blurb_zh": section.blurb_zh,
                "blurb_en": section.blurb_en,
            }
            for section in sorted(SECTIONS, key=lambda item: item.order)
        ],
        "fields": [
            {
                "key": item.key,
                "section": item.section,
                "tier": item.tier,
                "kind": item.kind,
                "label_zh": item.label_zh,
                "label_en": item.label_en,
                "help_zh": item.help_zh,
                "help_en": item.help_en,
                "default": item.default,
                "choices": list(item.choices),
                "provider": item.provider,
                "capabilities": list(item.capabilities),
                "placeholder": item.placeholder,
                "key_url": item.key_url,
                "docs_url": item.docs_url,
            }
            for item in CONFIG_FIELDS
        ],
        "status_labels": {key: dict(value) for key, value in STATUS_LABELS.items()},
    }
