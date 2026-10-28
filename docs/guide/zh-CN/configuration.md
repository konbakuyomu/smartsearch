[手册目录](../README.md) · [English](../en/configuration.md)

# 配置指南

全部可保存键的用途、取值和默认值见[全部配置项](configuration-reference.md)。普通使用可先按 [App 配置步骤](app.md)操作。

## 配置优先级和本地偏好

环境变量覆盖已保存值，命令中的单次参数覆盖对应设置。`config set KEY VALUE` 使用现有的原子写入保存配置，不会移除环境变量覆盖。诊断输出会掩码显示密钥；隔离测试请使用单独配置目录，不改生产 Key。

`SMART_SEARCH_LANGUAGE` 接受 `auto`、`zh`、`en`，也兼容 `zh-CN` 等形式。CLI 的 `--lang` 优先于环境变量和保存偏好，见 [CLI 语言和脚本调用](cli.md#语言和脚本调用)。App 的选择另存在 App 设置里，两者都不改变查询或来源的语言。

运行时还识别只从环境读取的变量：`SMART_SEARCH_CONFIG_DIR` 选择配置目录；`SMART_SEARCH_PYTHON` 只在 App 安装或修复较早发布、未内置运行环境的 npm 包时使用；`LC_ALL`、`LC_MESSAGES` 和 `LANG` 提供 CLI 自动语言。这些不是可保存的服务商键。当前 npm 包自带运行环境并会忽略 `SMART_SEARCH_PYTHON`。

## 服务商、Key 与配置

普通用户优先用 `smart-search setup` 配置。环境变量仍然支持 CI 和高级用户。
默认 setup 可选择 Jev 或本地路由；CLI 网页配置入口仍是 `smart-search ui`。

| Provider / 路线 | 用途 | 主要配置项 | 官方文档 | Key / 控制台 |
| --- | --- | --- | --- | --- |
| xAI Responses API | 主搜索，走 `web_search,x_search` 工具 | `XAI_API_KEY`、`XAI_API_URL`、`XAI_MODEL`、`XAI_TOOLS`、`XAI_REASONING_EFFORT`、`XAI_STREAM` | [docs.x.ai](https://docs.x.ai/docs) | [xAI API keys](https://console.x.ai/team/default/api-keys) |
| OpenAI-compatible Chat Completions / Responses | 主搜索，适合 OpenAI 官方或兼容中转；任一模式都不会发送 xAI search tools | `OPENAI_COMPATIBLE_API_URL`、`OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_MODEL`、`OPENAI_COMPATIBLE_API_MODE`、`OPENAI_COMPATIBLE_FALLBACK_MODELS`、`OPENAI_COMPATIBLE_STREAM` | [OpenAI platform docs](https://platform.openai.com/docs) | [OpenAI API keys](https://platform.openai.com/api-keys) 或你的兼容服务商 |
| Exa | 官方文档、API、论文、产品页、可信网页的低噪声发现 | `EXA_API_KEY` | [Exa docs](https://docs.exa.ai/) | [Exa API keys](https://dashboard.exa.ai/api-keys) |
| Context7 | SDK、库、框架、API 文档兜底 | `CONTEXT7_API_KEY`、`CONTEXT7_BASE_URL` | [Context7 docs](https://context7.com/docs) | [Context7](https://context7.com/) |
| 智谱 Web Search API | 中文、国内、时效、域名过滤类来源发现 | `ZHIPU_API_KEY`、`ZHIPU_API_URL`、`ZHIPU_SEARCH_ENGINE` | [智谱联网搜索文档](https://docs.bigmodel.cn/cn/guide/tools/web-search) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| 智谱 Coding Plan Remote MCP | 使用 Coding Plan 额度做联网搜索、网页读取、开源仓库发现 | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_SEARCH_API_URL`、`ZHIPU_MCP_READER_API_URL`、`ZHIPU_MCP_ZREAD_API_URL` | [联网搜索 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server)、[网页读取 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server)、[zread MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Tavily | 额外来源、URL fetch、站点 map | `TAVILY_API_URL`、`TAVILY_API_KEY`、`TAVILY_ENABLED` | [Tavily docs](https://docs.tavily.com/) | [Tavily app](https://app.tavily.com/home) |
| Jina Reader | 已知 URL 正文抓取；满足 standard 最低配置必须有 key | `JINA_API_KEY`、`JINA_READER_API_URL`、`JINA_RESPOND_WITH`、`JINA_TIMEOUT_SECONDS` | [Jina Reader](https://jina.ai/reader/) | [Jina AI](https://jina.ai/) |
| Firecrawl | fetch 兜底、补充网页来源 | `FIRECRAWL_API_URL`、`FIRECRAWL_API_KEY` | [Firecrawl docs](https://docs.firecrawl.dev/) | [Firecrawl API keys](https://www.firecrawl.dev/app/api-keys) |
| TinyFish | 搜索与抓取兜底 | `TINYFISH_API_KEY`、`TINYFISH_SEARCH_API_URL`、`TINYFISH_FETCH_API_URL`、`TINYFISH_TIMEOUT_SECONDS` | [TinyFish 文档](https://docs.tinyfish.ai/) | [TinyFish API keys](https://agent.tinyfish.ai/api-keys) |
| DeepSeek Search / Fetch | 网页搜索与抓取，与 DeepSeek 模型 API 共用 Key，按成功请求次数计费 | `DEEPSEEK_API_KEY`、`DEEPSEEK_API_URL`、`DEEPSEEK_TIMEOUT_SECONDS` | [网页搜索与抓取](https://api-docs.deepseek.com/zh-cn/guides/search)（[English](https://api-docs.deepseek.com/guides/search)） | [DeepSeek API keys](https://platform.deepseek.com/api_keys) |
| TypeSafe / Jev | 可选语义路由和证据判断 | `TYPESAFE_API_KEY`、`TYPESAFE_API_URL`、`TYPESAFE_MODEL` | [TypeSafe API](https://docs.typesafe.ai/api) | 参见 TypeSafe 文档 |
| AnySearch | 实验垂直搜索验收入口，不是默认兜底 | `ANYSEARCH_API_URL`、`ANYSEARCH_API_KEY`、`ANYSEARCH_TIMEOUT_SECONDS` | [AnySearch 文档](https://www.anysearch.com/docs) | [AnySearch API keys](https://www.anysearch.com/console/api-keys) |
| Sciverse | 显式实验学术检索、语义论文检索、正文片段和引用/参考文献关系，不是默认兜底 | `SCIVERSE_API_TOKEN`、`SCIVERSE_API_URL`、`SCIVERSE_TIMEOUT_SECONDS` | [Sciverse Agent Tools](https://github.com/opendatalab/Sciverse-Agent-Tools) | Sciverse 控制台 / token 提供方 |

## 路由与兼容

`search` 和 `research` 是两种联网搜索模式，共用渠道目录、执行器、总时限和证据记录。

- `search`：一次 Jev 选路，选择一个适合的渠道，返回结果与来源。Context7 查库后读文档等必要依赖调用，以及同能力故障兜底继续保留，模型回答与网页搜索互为兜底。不会执行充分性评估、自动补搜、过滤或汇总。`--extra-sources N` 只限制所选渠道的结果数量（最多 20），不增加渠道。`evidence_assessment.status=not_evaluated` 表示尚未评估，检索成功不等于事实核验成功。`--validation strict` 要求来源证据，不满足时可保留部分内容并返回证据错误。
- `research`：Jev 选择互补动作并发执行，读取发现的网页，判断证据缺口，必要时继续。原问题、子问题和有限缺口查询由程序提供，Jev 只选择候选，不生成任意查询或工具调用。只有实际 fetched/read 的内容进入 `citations`。可选过滤和 `SMART_SEARCH_JEV_SYNTHESIZE=false|auto|true` 只影响深入搜索。
- `deep` 继续离线生成计划，`steps[].command` 是供人或 AI 手动编排的建议。`research` 实际执行记录单独保存在 `routing_decision.rounds` 和 `stage_results` 中。

深入搜索的最终汇总只调用独立配置的 JEV 汇总模型，与主搜索模型无关。配置键为 `SMART_SEARCH_JEV_SYNTHESIS_API_URL`、`SMART_SEARCH_JEV_SYNTHESIS_API_KEY`、`SMART_SEARCH_JEV_SYNTHESIS_MODEL` 和 `SMART_SEARCH_JEV_SYNTHESIS_API_MODE`（`chat-completions` 或 `responses`）。汇总模式和诊断见 [Jev 路由与过滤](../../jev-routing.md)。

默认 `SMART_SEARCH_INTENT_ROUTER=jev`。没有 TypeSafe key 或无法得到有效判断时，`--fallback auto` 使用本地能力规则并标记降级，`--fallback off` 明确失败。显式 `local` 从不调用 Jev。旧 `hybrid` 映射为 `jev`，`rules` 和 `off` 映射为 `local`。旧 embedding/classifier 字段和 Key 保留但不使用，`route-calibrate` 是不联网的退役兼容命令。

`route` 默认只预览本地能力，不调用模型或检索服务；显式 `--remote` 才进行可能计费的 Jev 诊断。直接 provider 命令保持明确的调用语义。

只有已配置、启用、允许且不在冷却期的渠道可以执行。`--providers`、各 provider 开关、`SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` 和 explicit-only 限制在选路与派发前检查。普通渠道失败可在同能力内兜底，模型回答与网页搜索互为兜底，不能扩展成深研循环；用户偏好也不能绕过这些边界。

总时限默认 300 秒（`SMART_SEARCH_TIMEOUT_SECONDS`，`search --timeout` 可覆盖）。深研 quick/standard/deep 的上限分别是 2/3/10 轮、每轮 1/2/10 渠道、每渠道 3/5/20 个结果，以及 45/120/配置秒数，并受用户 Jev 预算进一步限制。证据充分、候选耗尽、无新证据或期限到达时停止；可选判断、过滤、汇总失败仍保留已完成的结果。

几个容易混淆的点：

- xAI 官方联网搜索通过 `XAI_*` 走 `/responses`。OpenAI-compatible 中转默认走 `/chat/completions`；只有中转明确支持文档化的 Responses 子集时才设置 `OPENAI_COMPATIBLE_API_MODE=responses`。
- `chat-completions` 不发送搜索工具；如果中转站上的模型只能通过 Responses 的 `web_search` 工具联网（例如 grok），把 `XAI_API_URL`、`XAI_API_KEY`、`XAI_MODEL` 指向该中转站，并用 `smart-search diagnose openai-compatible` 的“联网搜索能力”检查确认。
- `smart-search search --stream` 和 `smart-search research --stream` 会给 xAI Responses 和 OpenAI-compatible 搜索设置 `stream=true`，包括 Jev 调度的 Grok 搜索；`--no-stream` 关闭本次流式请求。`OPENAI_COMPATIBLE_STREAM=true` 仍只设置 OpenAI-compatible 搜索和 provider 侧 fetch 的默认流式行为。
- `XAI_STREAM` 默认 `false`，接受 `true`、`1`、`yes` 为真。设为真时所有 xAI Responses 请求都用 `stream=true`，包括 `research` 和 Jev 调度的 Grok 搜索；`--stream` / `--no-stream` 可单次覆盖。xAI 流式失败时直接报错，不会改用 `stream=false` 重试。
- `XAI_REASONING_EFFORT` 接受 `low`、`medium`、`high`，大小写不敏感，保存为小写。可选；设置后在 xAI Responses 请求中发送 reasoning.effort，默认不发送。Jev 调度的 Grok 搜索同样适用。provider attempts 记录实际 `stream` 和 `reasoning_effort`，xAI 的记录还带 `transport`（`stream` 或 `non_stream`）；`doctor` 显示 `XAI_REASONING_EFFORT` 和 `XAI_STREAM`，`model current` 显示 `xai_stream`。`doctor` 和 App 的 xAI 连接测试发送与搜索相同的 `reasoning.effort` 和 `stream`，不带工具，并在测试消息和 `sent` 中列出；HTTP 200 之后流式失败也算测试失败。上游因不支持 reasoning 返回 4xx 时原样报错，不删除字段重发。
- `SMART_SEARCH_TIMEOUT_SECONDS` 是持久化的 `search` 总时限；环境变量覆盖本机配置文件，单次 `search --timeout SECONDS` 覆盖两者，默认 `300` 秒。
- 主搜索 provider 直接用剩余的共享预算作为读取上限，不再额外套一层固定的 provider 读超时，因此慢推理模型不会在共享 deadline 之前被提前掐断。
- `OPENAI_COMPATIBLE_FALLBACK_MODELS` 是失败后接力，不是时间片。主模型会使用剩余的共享 main-search 预算；只有硬失败（例如 `model_not_found`、鉴权失败、空结果、不可重试协议错误）才会换兜底模型。`doctor` 和 `diagnose openai-compatible` 会在兜底模型不在 `/models` 里时给出警告。
- 旧的 `SMART_SEARCH_API_URL`、`SMART_SEARCH_API_KEY`、`SMART_SEARCH_API_MODE`、`SMART_SEARCH_MODEL`、`SMART_SEARCH_XAI_TOOLS` 不再是受支持配置项。请显式使用 `XAI_*` 或 `OPENAI_COMPATIBLE_*`。
- 不要给 OpenAI-compatible 任一 API mode 强塞 xAI 的 `web_search` / `x_search` 工具或旧 `search_parameters`。
- Responses mode 支持官方 `model` + `instructions`/`input` 请求子集、异构 `output` 文本部分、URL citation annotation 和 typed terminal stream event；这不等于所有标称 "OpenAI-compatible" 的中转都实现了 `/responses`。在依赖某个具名中转前，先用两种 stream 设置运行 `diagnose openai-compatible` 验收。
- `zhipu-search` 对应的是智谱 Web Search API，不是 Chat Completions `tools=[web_search]`，不是 Search Agent，也不是 MCP Server。
- 智谱 Coding Plan 是单独的 Remote MCP 路线：`web_search_prime` 对应 `web_search`，`webReader` 对应 `web_fetch`，zread 工具对应显式仓库/文档发现命令。它不会混进现有 `/paas/v4/web_search` 智谱 REST provider。
- 智谱 Coding Plan MCP 需要单独的 Coding Plan 权益。普通 `ZHIPU_API_KEY` 能用 Web Search API，不代表能用 `zhipu-mcp-search` 或 zread。未配置或未授权 `ZHIPU_MCP_API_KEY` 时，Smart Search 会跳过这些 MCP provider；`standard` 最低配置和同 capability 兜底仍会通过已配置的 REST/search/fetch provider 工作。
- Jina Reader 不是通用搜索 provider。只有配置 `JINA_API_KEY` 后才计入 `standard`；`JINA_RESPOND_WITH=readerlm-v2` 也必须配置 `JINA_API_KEY`。
- `ZHIPU_SEARCH_ENGINE` 默认是 `search_std`。官方值包括 `search_std`、`search_pro`、`search_pro_sogou`、`search_pro_quark`；`config set` 仍允许自定义值，方便官方以后新增服务。
- `TAVILY_API_URL` 只影响 Tavily，不会代理智谱。Tavily Hikari / 号池用 `https://<host>/api/tavily`；setup 会把根域名或 `/mcp` 输入规范化成这个 REST base。
- `TAVILY_ENABLED` 默认是 `true`。即使已有 key，设为 `false` 也会禁用 Tavily：它会从 web-search 和 fetch 路由中移除，直接 Tavily 调用和 `doctor` 都不会发 Tavily 请求，`map` 会本地返回配置错误。它不会启用 Firecrawl，也不会改变同 capability 兜底边界。
- `FIRECRAWL_API_URL` 默认是 `https://api.firecrawl.dev/v2`。
- `DEEPSEEK_API_URL` 默认是 `https://api.deepseek.com`，填 `.../v1` 也可以；程序调用 `/v1/tools/search` 和 `/v1/tools/fetch`。单个 `DEEPSEEK_API_KEY` 同时加入 `web_search` 与 `web_fetch`，不满足 `main_search` 或 `docs_search`。DeepSeek 查询词最多 128 个字符，更长的查询会在词边界截短；`site:`、`lang:`、`after:` 等搜索语法原样传递。抓取返回 403（安全策略拒绝）或 404（页面没有可用正文，目前 PDF 链接和内网地址也属于这种情况）只表示该页面读不到，会继续兜底且不让 DeepSeek 进入冷却。每次成功请求计费，`doctor` 与 `providers test deepseek` 会各发一次真实搜索和抓取。
- AnySearch 默认走 `https://api.anysearch.com/mcp` 的 JSON-RPC 2.0 `tools/call`。没有 key 时允许匿名请求；有 key 时发送 `Authorization: Bearer ...`。HTTP 200 但 `result.isError=true` 会按 provider error 处理，不能当成功证据。`--sub-domain-params` 会先解析成 JSON object，随后可重复的 `--param key=value` 覆盖同名键；参数不合法时会在发请求前失败。
- Sciverse 默认走 `https://api.sciverse.space` 的 native HTTP/OpenAPI。必须配置 `SCIVERSE_API_TOKEN`；未配置时本地返回 `config_error` 且不发网络请求；已配置时发送 `Authorization: Bearer ...`。它保持 explicit-only：不是 `docs_search`，不满足 `standard`，不进入默认 `search` / `research` 兜底。

非交互配置示例：

```powershell
smart-search setup --non-interactive `
  --xai-api-key "your-xai-key" `
  --xai-model "grok-4-fast" `
  --openai-compatible-api-url "https://api.openai.com/v1" `
  --openai-compatible-api-key "your-openai-or-relay-key" `
  --openai-compatible-model "gpt-4.1" `
  --openai-compatible-api-mode "chat-completions" `
  --openai-compatible-stream "false" `
  --validation-level "balanced" `
  --search-timeout "300" `
  --fallback-mode "auto" `
  --minimum-profile "standard" `
  --intent-router "jev" `
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

`standard` 最低要求是至少一个启用的自动检索渠道，Jev 和主模型均可选。渠道仍需支持当前操作；仅配置网页读取不能发现未知 URL。

AnySearch 是可选的垂直意图检索渠道：

```powershell
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "your-anysearch-key"
smart-search anysearch-domains security --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --param type=cve --param value=CVE-2024-3094 --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --max-length 12000 --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
```

简单垂直域仍支持点号简写，例如 `code.doc` 会由 CLI 发成 `domain=code` 加 `sub_domain=doc`。需要结构化参数的垂直域应先用 `anysearch-domains` 查看要求，再用拆分形式加 `--sub-domain-params` JSON object 和/或重复 `--param key=value`；重复参数会覆盖 JSON 中同名键，JSON 不合法、缺少 `=` 或空 key 会在发请求前失败。`anysearch-domains DOMAIN` 会调用 live `get_sub_domains`；省略 `DOMAIN` 时读取其 `tools/list` schema。`anysearch-extract --max-length` 上游只发送 `url`，仅在值为正时本地截断成功结果的顶层和 results 文本字段。

Sciverse 也是可选实验配置，不满足也不改变 `standard` 最低配置：

```powershell
smart-search setup --non-interactive --sciverse-token "your-sciverse-token" --sciverse-api-url "https://api.sciverse.space"
smart-search sciverse-catalog --collection papers --format json
smart-search sciverse-search "transformer retrieval" --year-from 2020 --page-size 5 --format json
smart-search sciverse-semantic "attention mechanism" --top-k 3 --retrieval hybrid --source-types web,pdf --format json
smart-search sciverse-read "doc-id-from-search" --offset 0 --limit 4096 --format json
smart-search sciverse-relations "unique-id-from-search" --relation CITATIONS --page-size 25 --format json
```

当前 `GET /meta-catalog` 和 `POST /meta-search` schema 都没有 `collection` selector。旧 `--collection papers` 仍可使用，但不会发给上游；`authors` 和 `sources` 会在发请求前返回 `parameter_error`。`POST /meta-search` 请求体只使用 `query`、`filters`、`sort`、`freshness_boost`、`page` 和 `page_size`。`--title-contains` 与 `--abstract-contains` 会并入 `query`；作者、期刊、主题和年份边界会转换为当前 `FieldFilterItem` 过滤条件。

`--filters-advanced` 和 `--sort-advanced` 接收结构化 JSON array，不再把任意 JSON 原样透传。过滤项必须有 `field` 和 `value`，使用 `FILTER_OP_GTE` 等当前 `operator`；旧 `op` 仅在能无歧义映射时兼容。排序项必须有 `field`，`order` 使用 `SORT_ORDER_ASC` / `SORT_ORDER_DESC` 或 `asc` / `desc`。当前 schema 不允许全文 `query` 与任意 sort 同时存在，因此 `--sort-by-year` 默认 `none`，排序仅用于无全文 query 的过滤检索。

语义检索使用 `--retrieval hybrid|milvus|es`。旧 `--mode fast|balanced|quality` 仍可使用，但会给出弃用警告并映射到 `--retrieval hybrid`；它与 `--retrieval milvus` 或 `--retrieval es` 一起使用时是参数错误。语义 `--source-types` 仅接受 `web,pdf`。`sciverse-read` 用 `doc_id`，`sciverse-relations` 用 `unique_id`。`CITATIONS` 表示引用目标论文的论文；`REFERENCES` 表示目标论文引用的论文；`RELATED_WORKS` 表示相关工作。

本机配置文件位置：

- Windows 默认：`%LOCALAPPDATA%\smart-search\config.json`。
- Linux/macOS 默认：`~/.config/smart-search/config.json`。
- `SMART_SEARCH_CONFIG_DIR` 是高级覆盖项，适合 CI、容器、沙箱或便携安装。
- `SMART_SEARCH_TIMEOUT_SECONDS` 保存默认 `search` 总时限；环境变量优先，单次 `search --timeout` 是最高优先级覆盖。
- 更早的 Windows 源码默认路径曾是 `~\.config\smart-search\config.json`，但有些安装会通过 `SMART_SEARCH_CONFIG_DIR` 提前固定到 `%LOCALAPPDATA%\smart-search`。如果新版默认位置还没有配置，但旧 home 路径存在配置，Smart Search 会以 `legacy_windows_home` 方式继续读取旧配置，避免升级后配置丢失；`doctor` 会同时报告当前生效路径、默认路径、旧 home 路径、`SMART_SEARCH_CONFIG_DIR` 的值，以及这个覆盖项是不是只是等于当前默认路径。

常用环境变量：

| 变量 | 用途 |
| --- | --- |
| `XAI_API_KEY` | xAI Responses provider key |
| `XAI_API_URL` | xAI API 地址，默认 `https://api.x.ai/v1` |
| `XAI_MODEL` | xAI 模型名 |
| `XAI_TOOLS` | xAI Responses 工具列表，通常 `web_search,x_search` |
| `XAI_REASONING_EFFORT` | 可选；设置后在 xAI Responses 请求中发送 reasoning.effort，默认不发送。 |
| `XAI_STREAM` | 可选；设为 `true` 时所有 xAI Responses 请求（含 research）使用 stream=true，默认 `false`。 |
| `OPENAI_COMPATIBLE_API_URL` | OpenAI-compatible `/v1` base URL |
| `OPENAI_COMPATIBLE_API_KEY` | OpenAI-compatible key |
| `OPENAI_COMPATIBLE_MODEL` | 兼容模型名 |
| `OPENAI_COMPATIBLE_API_MODE` | `chat-completions` 或 `responses`，默认 `chat-completions` |
| `OPENAI_COMPATIBLE_STREAM` | OpenAI-compatible 中转兼容开关，接受 `true/1/yes`，默认 `false` |
| `SMART_SEARCH_TIMEOUT_SECONDS` | `search` 总时限，默认 `300`；环境变量覆盖配置文件，`search --timeout` 单次覆盖 |
| `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS` | 可选 provider 失败冷却时长（秒），默认 `900`，`0` 关闭 |
| `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` | 进入冷却前的连续软失败次数，默认 `2` |
| `ANYSEARCH_API_URL` | AnySearch JSON-RPC endpoint，默认 `https://api.anysearch.com/mcp` |
| `ANYSEARCH_API_KEY` | 可选 AnySearch key |
| `ANYSEARCH_TIMEOUT_SECONDS` | AnySearch 请求超时，默认 `30` |
| `SCIVERSE_API_TOKEN` | 显式 Sciverse 学术命令需要的 token |
| `SCIVERSE_API_URL` | Sciverse API base URL，默认 `https://api.sciverse.space` |
| `SCIVERSE_TIMEOUT_SECONDS` | Sciverse 请求超时，默认 `30` |
| `SMART_SEARCH_INTENT_ROUTER` | 路由方式：`jev`（默认）或 `local`；旧值按兼容映射处理 |
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
| `TAVILY_ENABLED` | 默认 `true`；只有 `true`、`1`、`yes` 启用 Tavily，其他值禁用且不发 Tavily 网络请求 |
| `TAVILY_TIMEOUT_SECONDS` | Tavily 连通性检查超时，默认 `30`；公益站/号池较慢时可调大 |
| `FIRECRAWL_API_URL` | Firecrawl REST base |
| `FIRECRAWL_API_KEY` | Firecrawl key |
| `DEEPSEEK_API_KEY` | DeepSeek key，同时用于搜索与抓取 |
| `DEEPSEEK_API_URL` | DeepSeek API base，默认 `https://api.deepseek.com` |
| `DEEPSEEK_TIMEOUT_SECONDS` | DeepSeek 搜索与抓取的读取超时，默认 `60` |
| `SMART_SEARCH_VALIDATION_LEVEL` | `fast`、`balanced`、`strict` |
| `SMART_SEARCH_FALLBACK_MODE` | `auto` 或 `off` |
| `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` | 自动选路优先的 provider CSV，普通搜索和 `research` 都适用（名称沿用旧称）；只能在同 capability 内调整顺序 |
| `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` | 自动选路禁用的 provider CSV，普通搜索和 `research` 都适用（名称沿用旧称）；不能改变 provider capability 边界 |
| `SMART_SEARCH_CONFIG_DIR` | 指定本机配置和日志根目录 |

## 服务商失败冷却

可选 provider（`web_search`、`docs_search`、`web_fetch`、`vertical_search`）是增量能力。某个渠道一直失败时，比如智谱 key 被吊销、额度用尽或 endpoint 挂掉，每次调用都重试它只会浪费时间，并把同一条错误反复弹给用户。smart-search 是短生命周期 CLI 进程，所以这些失败会被记在 `config.json` 旁边的 `provider_health.json` 里：

- 硬失败（`auth_error`、`config_error`）第一次就进入冷却，并且不会再被试探：key 不对不会自己变好。
- 软失败（超时、`5xx`、限流）需要在一个冷却窗口内连续失败 `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` 次；它们保持可试探，恢复后不需要用户手动操作就会回来。
- 搜到 0 条结果不算失败，不会触发冷却。
- 主搜索 provider 永远不会被这样跳过。被冷却的 provider 也不是被静默丢弃：它在 `provider_attempts` 里是 `status=skipped` 并带着记住的 `error_type`，同时 `provider_notices` 每个降级 provider 只给一条去重后的提示，取代反复出现的报错。

常见情况下恢复是自动的：记录绑定在 provider 凭据的指纹上，用 `smart-search config set` 换 key 会自动清除冷却，`smart-search doctor` 探测成功也会清除。

```powershell
smart-search providers status --format markdown
smart-search providers reset zhipu --format json
smart-search providers reset --format json
smart-search config set SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS "0" --format json
```
