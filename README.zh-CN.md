# smart-search

简体中文 | [English](README.md)

`smart-search` 是一个给 AI 助手和命令行用户使用的 CLI-first 网页研究工具。它把普通联网搜索、来源发现、网页正文抓取、站点 map、配置检查、Deep Research 离线规划和 live Deep Research 执行统一成一个可复现的命令层。

<p>
  <a href="https://www.npmjs.com/package/@konbakuyomu/smart-search">
    <img src="https://img.shields.io/npm/v/@konbakuyomu/smart-search?label=npm%20latest" alt="npm latest">
  </a>
</p>

![Star History Chart](https://api.star-history.com/svg?repos=konbakuyomu/smartsearch&type=Date)

## 它到底是什么

它不是 MCP Server，而是一个普通命令行工具。AI 工具通过 `smart-search-cli` skill 调它，脚本和终端用户也可以直接调它：

```powershell
smart-search search "今天 OpenAI Responses API 有什么新变化" --format json
smart-search fetch "https://example.com/article" --format markdown
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --format json
smart-search research "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --format markdown
```

当前架构分两层：

| 层 | 负责什么 |
| --- | --- |
| CLI 执行层 | 稳定执行命令、provider 路由、同能力兜底、JSON/Markdown 输出、本机配置、smoke/regression |
| Skill / AI 编排层 | 判断用户意图，决定普通搜索还是 Deep Research，按计划执行 CLI 积木，最后写出有来源支撑的回答 |

`smart-search search` 保持快速、直接联网。`smart-search deep` 是显式 Deep Research 离线规划入口：默认不联网、不跑 provider、不抓网页，只输出 `research_plan`。真正联网可以由 AI 或用户继续执行 `steps[].command`，也可以交给新的 `smart-search research` live 执行器完成。`research` 会按 plan -> discover -> fetch/read -> gap check -> evidence-only synthesis 执行。

现在意图路由单独成了一层。可以把它理解成“更聪明的分诊台”：先判断用户到底需要哪些能力，再让已有 provider 注册表在同一能力内兜底，而不是让模型直接乱选 provider：

```text
用户问题
 -> 规则路由：URL、文档/实时/抓取/垂直搜索硬信号、strict 校验
 -> 语义路由：可选 embeddings，对典型例句做相似度
 -> 模型路由：可选小模型输出结构化能力分类
 -> 合并成 required_capabilities
 -> 在 docs_search / web_search / web_fetch / vertical_search 内选择 provider 和兜底
```

`smart-search route "query"` 只解释这次会需要哪些能力，不执行搜索、文档查询、网页抓取或 provider 调用。`smart-search deep` 仍保持离线 planner 契约，只使用本地/rules 信号。

## 安装

稳定版：

```powershell
npm install -g @konbakuyomu/smart-search@latest
smart-search --version
smart-search setup
```

测试版：

```powershell
npm install -g @konbakuyomu/smart-search@next
smart-search --version
```

npm 包安装时会自动创建隔离的 Python 运行环境。你平时只需要使用 `smart-search` 这个命令。

前置条件：

- 已安装 Node.js / npm。
- 已安装 Python 3.10 或更新版本，并且终端里能运行 `python`、`python3` 或 Windows 的 `py -3`。

## 快速开始

1. 配置 provider：

```powershell
smart-search setup
smart-search doctor --format json
```

2. 普通快速搜索：

```powershell
smart-search search "今天有什么值得关注的 AI 新闻？" --validation balanced --extra-sources 2 --format json
```

3. 只看意图路由，不调用 provider：

```powershell
smart-search route "React useEffect API docs" --format markdown
smart-search route "请核验这个链接里的说法 https://example.com/source" --format json
```

4. 抓取关键网页正文：

```powershell
smart-search fetch "https://example.com/source" --format markdown --output evidence.md
```

5. 生成 Deep Research 计划：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --budget standard --format json
```

6. 让 CLI 直接执行 live Deep Research：

```powershell
smart-search research "深度搜索一下最近的比特币行情" --budget deep --format markdown
```

7. 把 skill 安装给 AI 工具：

```powershell
smart-search setup --non-interactive --install-skills codex,claude,cursor,hermes
```

Skill 安装会把内置 `smart-search-cli` 写入用户级工具目录，例如 `~/.codex/skills`、
`~/.claude/skills`、`~/.cursor/skills`、`~/.hermes/skills`。它不会初始化 Trellis、hooks、
agents 或 commands。`--skills-root PATH` 只适合便携安装或测试时高级覆盖根目录。

8. 升级 CLI 后，同步已经安装到全局 AI 工具里的 skill：

```powershell
smart-search skills status --targets codex --format json
smart-search skills update --targets codex --format json
```

`setup --install-skills` 仍然保留给第一次配置使用。平时升级包以后，优先用 `skills status` 和
`skills update`；它们只检查或覆盖 `smart-search-cli` 托管文件，不会改 provider key，也不会创建
Trellis、hooks、agents 或 commands。

## 当前架构

| 能力 | 主要命令 | Provider | 负责什么 |
| --- | --- | --- | --- |
| `main_search` | `search` | xAI Responses、OpenAI-compatible Chat Completions | 综合回答、快速搜索、初步总结 |
| `docs_search` | `context7-library`、`context7-docs`、`exa-search` | Context7、Exa | 官方文档、SDK、API、框架/库文档 |
| `web_search` | `zhipu-search`、`zhipu-mcp-search`、`search` 内部意图补强 | 智谱 Web Search API、智谱 Coding Plan MCP、Tavily、Firecrawl | 中文、国内、时效、域名过滤、补充来源 |
| `web_fetch` | `fetch`、`zhipu-mcp-reader` | Tavily、Jina Reader、智谱 Coding Plan MCP Reader、Firecrawl | 已知 URL 正文抓取、证据提取 |
| `vertical_search` | `anysearch-domains`、`anysearch-search`、`anysearch-extract`、`anysearch-batch` | AnySearch（实验） | 验收 CVE、金融、法律、学术、代码/文档等结构化垂直域 |
| `site_map` | `map` | Tavily | 文档站、产品站、目录型站点结构 |
| `deep_planner` | `deep` / `dr` | 本地 planner | 离线生成 Deep Research 计划，不默认联网 |
| `research_executor` | `research` / `rs` | 按 capability 注册的 provider | live 深度研究执行：规划、发现、抓取/读取、gap check、仅基于证据综合 |

同能力兜底关系：

| 能力 | 兜底链 |
| --- | --- |
| `main_search` | xAI Responses -> OpenAI-compatible |
| `docs_search` | Context7 处理库/API/文档意图；Exa 处理官方域名、论文、产品页、可信站点发现 |
| `web_search` | 智谱 Web Search API -> 智谱 Coding Plan MCP `web_search_prime` -> Tavily -> Firecrawl |
| `web_fetch` | Tavily -> 带 `JINA_API_KEY` 的 Jina Reader -> 智谱 Coding Plan MCP `webReader` -> Firecrawl |

AnySearch 当前只作为实验 `vertical_search` 暴露，不进入 `web_search` 兜底链，也不是 `standard` 最低配置要求。请先用显式命令做验收和能力边界判断，再决定未来是否把某个垂直域提升成正式路线。

Jina Reader 只属于 `web_fetch`，不是通用搜索 provider。只有配置 `JINA_API_KEY` 后，它才可以满足 `SMART_SEARCH_MINIMUM_PROFILE=standard`；匿名 `r.jina.ai` 只能当显式/实验抓取能力，不能让最低配置检查放松。

这里有一个重要边界：兜底只在同一类能力里发生。不会用 Context7 去查普通新闻，也不会用 Firecrawl 假装做文档语义检索。

输出里会保留可观测字段：

| 字段 | 作用 |
| --- | --- |
| `routing_decision` | 为什么触发了某些补强路径 |
| `provider_attempts` | 每个 provider 的尝试结果 |
| `providers_used` | 最终用到哪些 provider |
| `fallback_used` | 是否触发同能力兜底 |
| `primary_sources` | 主搜索回答里带出的来源 |
| `extra_sources` | Tavily / Firecrawl 等额外发现的候选来源 |
| `source_warning` | 来源和回答之间可能存在的证据边界提醒 |

`routing_decision` 会保留旧字段：`docs_intent`、`zh_current_intent`、`web_current_intent`、`fetch_intent`、`supplemental_paths`；同时新增统一路由字段：`intent_router_mode`、`required_capabilities`、`intent_signals`、`confidence`、`router_engines_used`、`degraded_reason`。

`extra_sources` 只是候选来源，不等于自动事实校验。新闻、政策、财经、医疗、严肃评测、工具选型等高风险问题，建议先发现来源，再 `fetch` 关键网页正文，最后只基于抓到的正文写结论。

搜索引擎选择速记：先用 `search` 做宽泛探索和综合；想让 CLI 执行完整证据流时用 `research`；中文、国内、政策、公告、当前新闻优先补 `zhipu-search`；只有明确要用 Coding Plan 额度时才走 `zhipu-mcp-*`；库/API/框架文档优先用 Context7；官方域名、论文、产品页、可信站点和低噪声发现再用 Exa；Tavily/Firecrawl 通过 `search --extra-sources` 做横向候选，通过 `fetch` 做正文证据；Jina 用于已知 URL 正文抓取；AnySearch 只在明确要实验性垂直搜索时使用。

## Deep Research 深度搜索

普通问题用：

```powershell
smart-search search "React useEffect cleanup 文档" --format json
```

需要先拆解、规划、再由你或 AI 分步执行时用：

```powershell
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search dr "https://example.com/source" --format json
```

Deep Research 不是固定题材配方。行情、选型、技术文档、新闻政策、真假核验、用户给 URL 这些只是用户语言示例，不是 schema 枚举。它会先抽取 `intent_signals`，再生成 `decomposition` 和 `capability_plan`。

计划里会包含：

- `mode="deep_research"` 和 `query_mode="deep"`；
- `intent_signals`：是否强时效、是否 docs/API、是否给 URL、是否高风险、是否需要权威来源、是否需要交叉验证；
- `decomposition`：复杂问题拆成 1-6 个子问题；
- `capability_plan`：选择需要的能力；
- `steps[]`：每一步的 `tool`、`purpose`、`command`、`output_path`、`subquestion_id`；
- `evidence_policy="fetch_before_claim"`；
- `gap_check`：关键结论没有正文证据就继续抓，或者降级成未验证候选。
- `usage_boundary`：说明 `search` 是直接联网，`deep` 是离线规划，真正执行发生在计划命令里。

Deep Research 只允许组合现有 CLI 积木：

```text
search, exa-search, exa-similar, zhipu-search, context7-library, context7-docs, fetch, map
```

`doctor` 是 preflight 配置预检，不是 research step。`smart-search deep` 这一步本身是离线 planner；后续执行计划里的 `steps[].command` 时才会联网。

换句话说，`doctor` 只是配置预检；它帮助 AI 判断当前 provider 是否可用，但不算 Deep Research 的取证步骤。

如果你希望 CLI 直接执行完整 live Deep Research，用：

```powershell
smart-search research "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --fallback auto --format json
smart-search rs "https://example.com/source" --fallback off --format markdown
```

`research` 会执行 plan -> discover -> fetch/read -> gap check -> evidence-only synthesis。默认 `--fallback auto`，会在同一 capability 内兜底；`--fallback off` 只尝试每个 capability 选中的第一个 provider，适合手动调试某个 provider。

`research` JSON 会包含 `final_answer`、`citations`、`evidence_items`、`gap_check`、`provider_attempts`、`fallback_used`、`degraded`、`route_policy_version` 和 `evidence_dir`。发现阶段的 snippet 只是候选，不会直接变成 citation；只有 fetch/read 到正文的来源才会被引用。兜底仍然补不齐证据时，`research` 会降级输出 gap，不会编造结论。

`research` 的路由是 capability-first 加 provider 优势：

- Context7 优先处理库/API/框架文档，Exa 用于官方域名、论文、产品页、可信站点和低噪声发现。
- 智谱 Web Search API 优先处理中文、国内、时效、政策、公告搜索。
- 智谱 Coding Plan MCP 仍是单独额度路线，通过 `web_search_prime` 和 `webReader` 加入对应 capability。
- Jina 优先用于已知公开 URL、PDF、arXiv 正文抽取；ReaderLM-v2 仍要求 `JINA_API_KEY`。
- Firecrawl 优先用于 JS-heavy、动态页面、浏览器式抽取、OCR/PDF 或强兜底抓取。
- AnySearch 只在垂直意图清楚时加入，例如 CVE、金融、法律、学术、代码库/仓库搜索。

高级路由覆盖项是 `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` 和 `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`。它们只能在 provider 已支持的 capability 内调整顺序或禁用，不能把 provider 移到另一个 capability。

可以用这些标准问题测试是否进入深搜模式：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search deep "帮我核验这个说法是真是假：某某工具已经完全替代 Tavily 做 AI 搜索了" --format json
smart-search deep "https://example.com/source" --format json
```

看到输出里有 `mode=deep_research`、`decomposition`、多步 `steps`、`evidence_policy=fetch_before_claim`、`preflight.executed_by_deep_command=false`，就说明已经进入 Deep Research 计划模式。

## API 和 Key 申请入口

普通用户优先用 `smart-search setup` 配置。环境变量仍然支持 CI 和高级用户。
默认交互式 setup 已包含可选智能意图路由小节，可以直接配置 embeddings 和 classifier 路由，不需要进入 `--advanced`。

| Provider / 路线 | 用途 | 主要配置项 | 官方文档 | Key / 控制台 |
| --- | --- | --- | --- | --- |
| xAI Responses API | 主搜索，走 `web_search,x_search` 工具 | `XAI_API_KEY`、`XAI_API_URL`、`XAI_MODEL`、`XAI_TOOLS` | [docs.x.ai](https://docs.x.ai/docs) | [xAI API keys](https://console.x.ai/team/default/api-keys) |
| OpenAI-compatible Chat Completions | 主搜索，适合 OpenAI 官方或兼容中转；这里不会发送 xAI search tools | `OPENAI_COMPATIBLE_API_URL`、`OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_MODEL`、`OPENAI_COMPATIBLE_STREAM` | [OpenAI platform docs](https://platform.openai.com/docs) | [OpenAI API keys](https://platform.openai.com/api-keys) 或你的兼容服务商 |
| Exa | 官方文档、API、论文、产品页、可信网页的低噪声发现 | `EXA_API_KEY` | [Exa docs](https://docs.exa.ai/) | [Exa API keys](https://dashboard.exa.ai/api-keys) |
| Context7 | SDK、库、框架、API 文档兜底 | `CONTEXT7_API_KEY`、`CONTEXT7_BASE_URL` | [Context7 docs](https://context7.com/docs) | [Context7](https://context7.com/) |
| 智谱 Web Search API | 中文、国内、时效、域名过滤类来源发现 | `ZHIPU_API_KEY`、`ZHIPU_API_URL`、`ZHIPU_SEARCH_ENGINE` | [智谱联网搜索文档](https://docs.bigmodel.cn/cn/guide/tools/web-search) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| 智谱 Coding Plan Remote MCP | 使用 Coding Plan 额度做联网搜索、网页读取、开源仓库发现 | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_SEARCH_API_URL`、`ZHIPU_MCP_READER_API_URL`、`ZHIPU_MCP_ZREAD_API_URL` | [联网搜索 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server)、[网页读取 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server)、[zread MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Tavily | 额外来源、URL fetch、站点 map | `TAVILY_API_URL`、`TAVILY_API_KEY` | [Tavily docs](https://docs.tavily.com/) | [Tavily app](https://app.tavily.com/home) |
| Jina Reader | 已知 URL 正文抓取；满足 standard 最低配置必须有 key | `JINA_API_KEY`、`JINA_READER_API_URL`、`JINA_RESPOND_WITH`、`JINA_TIMEOUT_SECONDS` | [Jina Reader](https://jina.ai/reader/) | [Jina AI](https://jina.ai/) |
| Firecrawl | fetch 兜底、补充网页来源 | `FIRECRAWL_API_URL`、`FIRECRAWL_API_KEY` | [Firecrawl docs](https://docs.firecrawl.dev/) | [Firecrawl API keys](https://www.firecrawl.dev/app/api-keys) |
| AnySearch | 实验垂直搜索验收入口，不是默认兜底 | `ANYSEARCH_API_URL`、`ANYSEARCH_API_KEY`、`ANYSEARCH_TIMEOUT_SECONDS` | [AnySearch 文档](https://www.anysearch.com/docs) | [AnySearch API keys](https://www.anysearch.com/console/api-keys) |

意图路由配置：

| 配置项 | 用途 |
| --- | --- |
| `SMART_SEARCH_INTENT_ROUTER` | `hybrid`、`rules` 或 `off`，默认 `hybrid` |
| `INTENT_EMBEDDING_API_URL` | 可选 OpenAI-compatible embeddings endpoint，用于语义能力路由；推荐 setup preset 使用 `https://api.siliconflow.cn/v1/embeddings` |
| `INTENT_EMBEDDING_API_KEY` | 可选 embeddings key；`doctor` 和 config 输出会脱敏 |
| `INTENT_EMBEDDING_MODEL` | embeddings 模型名；推荐 setup preset 使用 `Qwen/Qwen3-Embedding-8B` |
| `INTENT_EMBEDDING_THRESHOLD` | 语义路由阈值，默认 `0.74`；推荐 8B setup 值是 `0.475`；这是模型相关参数 |
| `INTENT_EMBEDDING_MARGIN` | top1 与第二名分数差阈值，默认 `0.05`；推荐 8B setup 值是 `0.053`；差距不足时只记录 ambiguous 信号，不直接加 capability |
| `INTENT_CLASSIFIER_API_URL` | 可选 OpenAI-compatible chat-completions endpoint，用于结构化意图分类 |
| `INTENT_CLASSIFIER_API_KEY` | 可选 classifier key；`doctor` 和 config 输出会脱敏 |
| `INTENT_CLASSIFIER_MODEL` | classifier 模型名 |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | 可选远程路由调用超时，默认 `8` |

默认 `hybrid` 是 fail-open：embeddings 或 classifier 没配置、超时或失败时，会在 `degraded_reason` 里说明，然后自动退回本地规则。语义路由只有在 top1 相似度达到 `INTENT_EMBEDDING_THRESHOLD`，并且 top1 与第二名差值达到 `INTENT_EMBEDDING_MARGIN` 时，才会直接添加 capability；否则只记录 ambiguous 信号。classifier 可以补充 capability，但未知 capability 和 provider 名会被忽略；provider 仍然只能由 capability-first 注册表选择。

普通用户推荐直接使用 Qwen3-Embedding-8B preset：`INTENT_EMBEDDING_API_URL=https://api.siliconflow.cn/v1/embeddings`、`INTENT_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`、`INTENT_EMBEDDING_THRESHOLD=0.475`、`INTENT_EMBEDDING_MARGIN=0.053`。选择 8B 模型且没有手动配置 threshold/margin 时，`smart-search setup` 会自动补齐这两个推荐值。

embedding 余弦分数强依赖模型。`route-calibrate` 保留给高级复验：换 `INTENT_EMBEDDING_MODEL`、换 embedding endpoint，或者后续加入真实 query 校准集后再运行：

```powershell
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
```

再按报告推荐值设置 `INTENT_EMBEDDING_THRESHOLD` 和 `INTENT_EMBEDDING_MARGIN`。校准主指标是 semantic-only Macro-F1；full-route Macro-F1 只用来验证 rules/classifier 兜底后的真实路由表现。

几个容易混淆的点：

- xAI 官方联网搜索路线是 Responses API `/responses`，只通过 `XAI_*` 配置。兼容中转/网关走 Chat Completions `/chat/completions`，只通过 `OPENAI_COMPATIBLE_*` 配置。
- `OPENAI_COMPATIBLE_STREAM=true` 或 `smart-search search --stream` 只会给 OpenAI-compatible 的 `search` 和 provider 侧 `fetch` 设置 `stream=true`。它是中转长请求兼容开关，不改变 xAI Responses、URL 描述和来源排序行为。
- 旧的 `SMART_SEARCH_API_URL`、`SMART_SEARCH_API_KEY`、`SMART_SEARCH_API_MODE`、`SMART_SEARCH_MODEL`、`SMART_SEARCH_XAI_TOOLS` 不再是受支持配置项。请显式使用 `XAI_*` 或 `OPENAI_COMPATIBLE_*`。
- 不要给 OpenAI-compatible Chat Completions 中转强塞 xAI 的 `web_search` / `x_search` 工具或旧 `search_parameters`。
- `zhipu-search` 对应的是智谱 Web Search API，不是 Chat Completions `tools=[web_search]`，不是 Search Agent，也不是 MCP Server。
- 智谱 Coding Plan 是单独的 Remote MCP 路线：`web_search_prime` 对应 `web_search`，`webReader` 对应 `web_fetch`，zread 工具对应显式仓库/文档发现命令。它不会混进现有 `/paas/v4/web_search` 智谱 REST provider。
- 智谱 Coding Plan MCP 需要单独的 Coding Plan 权益。普通 `ZHIPU_API_KEY` 能用 Web Search API，不代表能用 `zhipu-mcp-search` 或 zread。未配置或未授权 `ZHIPU_MCP_API_KEY` 时，Smart Search 会跳过这些 MCP provider；`standard` 最低配置和同 capability 兜底仍会通过已配置的 REST/search/fetch provider 工作。
- Jina Reader 不是通用搜索 provider。只有配置 `JINA_API_KEY` 后才计入 `standard`；`JINA_RESPOND_WITH=readerlm-v2` 也必须配置 `JINA_API_KEY`。
- `ZHIPU_SEARCH_ENGINE` 默认是 `search_std`。官方值包括 `search_std`、`search_pro`、`search_pro_sogou`、`search_pro_quark`；`config set` 仍允许自定义值，方便官方以后新增服务。
- `TAVILY_API_URL` 只影响 Tavily，不会代理智谱。Tavily Hikari / 号池用 `https://<host>/api/tavily`；setup 会把根域名或 `/mcp` 输入规范化成这个 REST base。
- `FIRECRAWL_API_URL` 默认是 `https://api.firecrawl.dev/v2`。
- AnySearch 默认走 `https://api.anysearch.com/mcp` 的 JSON-RPC 2.0 `tools/call`。没有 key 时允许匿名请求；有 key 时发送 `Authorization: Bearer ...`。HTTP 200 但 `result.isError=true` 会按 provider error 处理，不能当成功证据。
- `doctor` 和 `route` 会报告 intent router 的配置状态、embedding 模型、threshold、margin、配置来源、超时和是否可降级，不会暴露 router API key。

非交互配置示例：

```powershell
smart-search setup --non-interactive `
  --xai-api-key "your-xai-key" `
  --xai-model "grok-4-fast" `
  --openai-compatible-api-url "https://api.openai.com/v1" `
  --openai-compatible-api-key "your-openai-or-relay-key" `
  --openai-compatible-model "gpt-4.1" `
  --openai-compatible-stream "false" `
  --validation-level "balanced" `
  --fallback-mode "auto" `
  --minimum-profile "standard" `
  --intent-router "hybrid" `
  --intent-embedding-api-url "https://api.siliconflow.cn/v1/embeddings" `
  --intent-embedding-api-key "your-siliconflow-key" `
  --intent-embedding-model "Qwen/Qwen3-Embedding-8B" `
  --intent-embedding-threshold "0.475" `
  --intent-embedding-margin "0.053" `
  --exa-key "your-exa-key" `
  --context7-key "your-context7-key" `
  --zhipu-key "your-zhipu-key" `
  --zhipu-api-url "https://open.bigmodel.cn/api" `
  --zhipu-search-engine "search_pro_sogou" `
  --zhipu-mcp-key "your-zhipu-coding-plan-key" `
  --jina-key "your-jina-key" `
  --tavily-api-url "https://api.tavily.com" `
  --tavily-key "your-tavily-key" `
  --firecrawl-api-url "https://api.firecrawl.dev/v2" `
  --firecrawl-key "your-firecrawl-key"
```

默认最低配置是 `SMART_SEARCH_MINIMUM_PROFILE=standard`，至少需要：

- `main_search`：xAI Responses 或 OpenAI-compatible 二选一；
- `docs_search`：Exa 或 Context7 二选一；
- `web_fetch`：Tavily、带 `JINA_API_KEY` 的 Jina、智谱 Coding Plan MCP Reader、Firecrawl 四选一。

缺少任一最低能力时，`doctor` 和 `search` 会 fail closed 并返回缺失 capability。`SMART_SEARCH_MINIMUM_PROFILE=off` 只建议本地实验使用。

AnySearch 是可选实验配置，不满足也不改变 `standard` 最低配置：

```powershell
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "your-anysearch-key"
smart-search anysearch-domains security --format json
smart-search anysearch-search "CVE-2024-3094" --domain security.cve --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
```

垂直域支持点号简写：`security.cve` 会由 CLI 发成 `domain=security` 加 `sub_domain=cve`。也可以显式写成 `--domain security --sub-domain cve`。

本机配置文件位置：

- Windows 默认：`%LOCALAPPDATA%\smart-search\config.json`。
- Linux/macOS 默认：`~/.config/smart-search/config.json`。
- `SMART_SEARCH_CONFIG_DIR` 是高级覆盖项，适合 CI、容器、沙箱或便携安装。
- 更早的 Windows 源码默认路径曾是 `~\.config\smart-search\config.json`，但有些安装会通过 `SMART_SEARCH_CONFIG_DIR` 提前固定到 `%LOCALAPPDATA%\smart-search`。如果新版默认位置还没有配置，但旧 home 路径存在配置，Smart Search 会以 `legacy_windows_home` 方式继续读取旧配置，避免升级后配置丢失；`doctor` 会同时报告当前生效路径、默认路径、旧 home 路径、`SMART_SEARCH_CONFIG_DIR` 的值，以及这个覆盖项是不是只是等于当前默认路径。

常用环境变量：

| 变量 | 用途 |
| --- | --- |
| `XAI_API_KEY` | xAI Responses provider key |
| `XAI_API_URL` | xAI API 地址，默认 `https://api.x.ai/v1` |
| `XAI_MODEL` | xAI 模型名 |
| `XAI_TOOLS` | xAI Responses 工具列表，通常 `web_search,x_search` |
| `OPENAI_COMPATIBLE_API_URL` | OpenAI-compatible `/v1` base URL |
| `OPENAI_COMPATIBLE_API_KEY` | OpenAI-compatible key |
| `OPENAI_COMPATIBLE_MODEL` | 兼容模型名 |
| `OPENAI_COMPATIBLE_STREAM` | OpenAI-compatible 中转兼容开关，接受 `true/1/yes`，默认 `false` |
| `ANYSEARCH_API_URL` | AnySearch JSON-RPC endpoint，默认 `https://api.anysearch.com/mcp` |
| `ANYSEARCH_API_KEY` | 可选 AnySearch key |
| `ANYSEARCH_TIMEOUT_SECONDS` | AnySearch 请求超时，默认 `30` |
| `SMART_SEARCH_INTENT_ROUTER` | 意图路由模式：`hybrid`、`rules`、`off`，默认 `hybrid` |
| `INTENT_EMBEDDING_API_URL` | 可选 embeddings endpoint，用于语义路由 |
| `INTENT_EMBEDDING_API_KEY` | 可选 embeddings key |
| `INTENT_EMBEDDING_MODEL` | embeddings 模型名 |
| `INTENT_EMBEDDING_THRESHOLD` | 语义路由阈值，默认 `0.74`，换模型后用 `route-calibrate` 校准 |
| `INTENT_EMBEDDING_MARGIN` | top1 与第二名分数差阈值，默认 `0.05` |
| `INTENT_CLASSIFIER_API_URL` | 可选 classifier chat-completions endpoint |
| `INTENT_CLASSIFIER_API_KEY` | 可选 classifier key |
| `INTENT_CLASSIFIER_MODEL` | classifier 模型名 |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | 可选路由调用超时，默认 `8` |
| `EXA_API_KEY` | Exa key |
| `CONTEXT7_API_KEY` | Context7 key |
| `ZHIPU_API_KEY` | 智谱 Web Search key |
| `ZHIPU_API_URL` | 智谱 API 地址，默认 `https://open.bigmodel.cn/api` |
| `ZHIPU_SEARCH_ENGINE` | 智谱搜索服务，例如 `search_pro_sogou` |
| `ZHIPU_MCP_API_KEY` | 智谱 Coding Plan Remote MCP key |
| `ZHIPU_MCP_SEARCH_API_URL` | 智谱 Coding Plan 联网搜索 MCP endpoint |
| `ZHIPU_MCP_READER_API_URL` | 智谱 Coding Plan 网页读取 MCP endpoint |
| `ZHIPU_MCP_ZREAD_API_URL` | 智谱 Coding Plan zread MCP endpoint |
| `ZHIPU_MCP_TIMEOUT_SECONDS` | 智谱 Coding Plan MCP 请求超时，默认 `30` |
| `JINA_API_KEY` | Jina Reader key；满足 standard 必须配置 |
| `JINA_READER_API_URL` | Jina Reader endpoint，默认 `https://r.jina.ai` |
| `JINA_RESPOND_WITH` | Jina Reader 响应模式，例如 `readerlm-v2`；需要 `JINA_API_KEY` |
| `JINA_TIMEOUT_SECONDS` | Jina Reader 请求超时，默认 `30` |
| `TAVILY_API_URL` | Tavily REST base |
| `TAVILY_API_KEY` | Tavily key |
| `TAVILY_TIMEOUT_SECONDS` | Tavily 连通性检查超时，默认 `30`；公益站/号池较慢时可调大 |
| `FIRECRAWL_API_URL` | Firecrawl REST base |
| `FIRECRAWL_API_KEY` | Firecrawl key |
| `SMART_SEARCH_VALIDATION_LEVEL` | `fast`、`balanced`、`strict` |
| `SMART_SEARCH_FALLBACK_MODE` | `auto` 或 `off` |
| `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` | `research` 路由优先 provider CSV，只能在同 capability 内调整顺序 |
| `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` | `research` 禁用 provider CSV，不能改变 provider capability 边界 |
| `SMART_SEARCH_CONFIG_DIR` | 指定本机配置和日志根目录 |

## 常用命令

| 命令 | 简写 | 用途 |
| --- | --- | --- |
| `search` | `s` | 快速联网搜索和综合回答 |
| `route` | `rt` | 只解释需要哪些 capability，不调用 provider |
| `deep` | `dr` | Deep Research 离线计划 |
| `research` | `rs` | live Deep Research 执行 |
| `fetch` | `f` | 抓一个 URL 正文 |
| `map` | `m` | 读取站点结构 |
| `exa-search` | `exa`、`x` | Exa 来源发现 |
| `exa-similar` | `xs` | 从一个 URL 找相似页面 |
| `zhipu-search` | `z`、`zp` | 智谱 Web Search API |
| `zhipu-mcp-search` | `zmcp-search` | 智谱 Coding Plan MCP `web_search_prime` |
| `zhipu-mcp-reader` | `zmcp-reader` | 智谱 Coding Plan MCP `webReader` |
| `zhipu-mcp-search-doc` | `zmcp-doc` | 通过 zread MCP 搜开源仓库文档 |
| `zhipu-mcp-repo-structure` | `zmcp-tree` | 通过 zread MCP 读仓库结构 |
| `zhipu-mcp-read-file` | `zmcp-file` | 通过 zread MCP 读单个仓库文件 |
| `anysearch-domains` | `as-domains` | 实验 AnySearch 域名/能力发现 |
| `anysearch-search` | `as-search`、`as` | 实验 AnySearch 垂直/通用搜索 |
| `anysearch-extract` | `as-extract` | 实验 AnySearch URL 抽取 |
| `anysearch-batch` | `as-batch` | 实验 AnySearch 批量搜索，最多 5 条 |
| `context7-library` | `c7`、`ctx7` | 查 Context7 库候选 |
| `context7-docs` | `c7d`、`c7docs`、`ctx7-docs` | 抓 Context7 文档 |
| `route-calibrate` | `route-cal`、`rcal` | 评测 embedding 路由模型并推荐 threshold/margin |
| `doctor` | `d` | 配置和连通性检查 |
| `setup` | `init` | 配置向导 |
| `config` | `cfg` | 本机配置读写 |
| `model` | `mdl` | 查看显式 provider 模型；修改请用 `config set XAI_MODEL` 或 `OPENAI_COMPATIBLE_MODEL` |
| `smoke` | `sm` | provider 路由冒烟测试 |
| `regression` | `reg` | 离线回归测试 |

示例：

```powershell
smart-search search "query" --validation balanced --extra-sources 3 --timeout 90 --format json --output result.json
smart-search route "React useEffect API docs" --format markdown
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
smart-search research "query" --budget deep --fallback auto --format json --output research.json
smart-search search "query" --stream --format json
smart-search search "query" --no-stream --format json
smart-search search "nba战报" --format content
smart-search exa-search "OpenAI Responses API documentation" --include-domains platform.openai.com developers.openai.com --num-results 5 --include-text --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/facebook/react" "useEffect cleanup" --format json
smart-search zhipu-search "今天国内 AI 新闻" --search-engine search_pro_sogou --count 5 --format json
smart-search zhipu-mcp-search "今天国内 AI 新闻" --count 5 --format json
smart-search zhipu-mcp-reader "https://example.com/source" --format json
smart-search zhipu-mcp-search-doc "owner/repo" "install" --format json
smart-search anysearch-search "CVE-2024-3094" --domain security.cve --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search exa-similar "https://example.com/source" --num-results 5 --format json
smart-search fetch "https://example.com/source" --format markdown --output page.md
smart-search map "https://docs.example.com" --instructions "Find API reference pages" --max-depth 1 --limit 50 --format json
smart-search doctor --format markdown
smart-search smoke --mock --format json
smart-search regression
```

## 输出和证据策略

AI 和脚本解析优先用 JSON：

```powershell
smart-search search "query" --format json
smart-search doctor --format json
```

给人看连接状态、详细排障报告、冒烟结果、来源列表、网页正文时用 Markdown：

```powershell
smart-search doctor --format markdown
smart-search smoke --mock --format markdown
smart-search exa-search "OpenAI Responses API documentation" --format markdown
smart-search fetch "https://example.com" --format markdown
```

终端快速扫正文或摘要用 content：

```powershell
smart-search search "nba战报" --format content
smart-search doctor --format content
```

`content` 刻意保持很短，只适合快速看结论。完整排障给人看用 `doctor --format markdown`，给脚本和 AI 解析用 `doctor --format json`。

多来源研究建议显式指定稳定目录保存证据文件。默认使用平台临时目录，以 Windows 显式路径为例：

```powershell
smart-search exa-search "Reuters Iran Hormuz latest" --format json --output C:\tmp\smart-search-evidence\iran-hormuz\01-exa.json
smart-search fetch "https://example.com/source" --format markdown --output C:\tmp\smart-search-evidence\iran-hormuz\02-fetch.md
```

写 claim-level 结论时建议流程：

1. 用 `search`、`exa-search`、`zhipu-search` 或 `exa-similar` 找候选 URL。
2. 用 `fetch` 抓关键 URL 正文。
3. 最终回答只引用 fetch 正文能支撑的事实。
4. 没有 fetch 的来源标为未验证候选。

## 排障

如果 `doctor` 返回 `config_error`：

```powershell
smart-search setup
smart-search config list --format json
smart-search doctor --format markdown
```

如果搜索慢：

- 降低 `--extra-sources`；
- 把大问题拆成多个小问题；
- 先用 `exa-search` 或 `zhipu-search` 找来源，再 `fetch` 关键网页。

如果想确认安装是否正常：

```powershell
smart-search --help
smart-search --version
smart-search regression
smart-search smoke --mock --format json
```

Windows npm/mise 安装后建议验证中文 JSON 管道：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json | ConvertFrom-Json
```

## 开发验证

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m smart_search.cli regression
.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json
npm test
npm pack --dry-run
```

## 最新稳定版说明

### v0.1.14

这个稳定补丁版把已经验证过的 `0.1.13-beta.4` CLI 和内置 skill contract 推到 npm `latest`。

- 修复 GitHub issue #7：npm `latest` 现在包含新版 `smart-search-cli` skill 会调用的 `smart-search skills` 命令。
- `smart-search skills status` 可以只读检查用户级 skill 是缺失、过期、已最新，还是有额外文件。
- `smart-search skills update` 用于升级 CLI 后刷新指定 AI 工具里的托管 `smart-search-cli` 文件，不会改 provider key，也不会创建 Trellis/hooks/agents/commands。
- `smart-search diagnose openai-compatible --format markdown` 会生成适合复制给维护者的 OpenAI-compatible 卡住/超时诊断报告。
- 文档/API 路由现在优先用 Context7 处理库/框架文档，Exa 继续负责官方域名、论文、产品页和可信站点发现。
- README、打包 skill 资源、release notes 和测试已经同步说明并验证这次稳定包行为。

## 发布通道

稳定版走 Git tag 和 npm `latest`：

```powershell
git tag v0.1.14
git push origin v0.1.14
```

测试版不移动 `latest`。推送到 `main` 会发布下一个 `<package.json version>-beta.N` 到 npm `next`，并且 `N` 按每个稳定版本重新从 1 开始。例如 `0.1.10-beta.1`、`0.1.10-beta.2` 之后是 `0.1.10-beta.3`。

已发布 npm 版本不可变。旧的 `*-dev.*` 包不能原地改名，只能发布新的 `*-beta.N` 替代。

稳定版 GitHub Release 会读取 `.github/releases/vX.Y.Z.md` 作为正文，并自动追加 npm package、dist-tag、workflow run 等元数据。打稳定 tag 前先写这个文件，避免 Release 页面只显示包名和 workflow 链接。

发布收尾检查：

1. 先读 `npm view @konbakuyomu/smart-search versions --json`、`npm view @konbakuyomu/smart-search dist-tags --json`、`gh release list --repo konbakuyomu/smartsearch --limit 100`。
2. beta 发布必须保持 `latest` 不动，只移动 `next` 或指定的非 latest tag。
3. 遇到 npm `E409`，先查版本是否已经发布，再串行重跑对应版本。
4. 最后安装指定版本并运行 `smart-search --version`、`smart-search regression`、`smart-search smoke --mock --format json`。
5. Windows npm/mise 包装层额外跑中文 JSON 管道：`smart-search deep "深度搜索一下最近的比特币行情" --format json | ConvertFrom-Json`。

## License

MIT
