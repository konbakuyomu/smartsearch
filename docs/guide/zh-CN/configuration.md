[手册目录](../README.md) · [English](../en/configuration.md)

# 配置指南

全部可保存键的用途、取值和默认值见[全部配置项](configuration-reference.md)。普通使用可先按 [App 配置步骤](app.md)操作。

## 配置优先级和本地偏好

环境变量覆盖已保存值，命令中的单次参数覆盖对应设置。`config set KEY VALUE` 使用现有的原子写入保存配置，不会移除环境变量覆盖。诊断输出会掩码显示密钥；隔离测试请使用单独配置目录，不改生产 Key。

`SMART_SEARCH_LANGUAGE` 接受 `auto`、`zh`、`en`，也兼容 `zh-CN` 等形式。CLI 的 `--lang` 优先于环境变量和保存偏好，见 [CLI 语言和脚本调用](cli.md#语言和脚本调用)。App 的选择另存在 App 设置里，两者都不改变查询或来源的语言。

运行时还识别只从环境读取的变量：`SMART_SEARCH_CONFIG_DIR` 选择配置目录；`SMART_SEARCH_PYTHON` 为 npm 安装/修复指定已有 Python 可执行文件；`LC_ALL`、`LC_MESSAGES` 和 `LANG` 提供 CLI 自动语言。这些不是可保存的服务商键。`SMART_SEARCH_PYTHON` 应填完整路径，显式选择无效时会报错，不会静默改用另一个解释器。

## 服务商、Key 与配置

普通用户优先用 `smart-search setup` 配置。环境变量仍然支持 CI 和高级用户。
默认交互式 setup 已包含可选智能意图路由小节，可以直接配置 embeddings 和 classifier 路由，不需要进入 `--advanced`。

| Provider / 路线 | 用途 | 主要配置项 | 官方文档 | Key / 控制台 |
| --- | --- | --- | --- | --- |
| xAI Responses API | 主搜索，走 `web_search,x_search` 工具 | `XAI_API_KEY`、`XAI_API_URL`、`XAI_MODEL`、`XAI_TOOLS` | [docs.x.ai](https://docs.x.ai/docs) | [xAI API keys](https://console.x.ai/team/default/api-keys) |
| OpenAI-compatible Chat Completions / Responses | 主搜索，适合 OpenAI 官方或兼容中转；任一模式都不会发送 xAI search tools | `OPENAI_COMPATIBLE_API_URL`、`OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_MODEL`、`OPENAI_COMPATIBLE_API_MODE`、`OPENAI_COMPATIBLE_FALLBACK_MODELS`、`OPENAI_COMPATIBLE_STREAM` | [OpenAI platform docs](https://platform.openai.com/docs) | [OpenAI API keys](https://platform.openai.com/api-keys) 或你的兼容服务商 |
| Exa | 官方文档、API、论文、产品页、可信网页的低噪声发现 | `EXA_API_KEY` | [Exa docs](https://docs.exa.ai/) | [Exa API keys](https://dashboard.exa.ai/api-keys) |
| Context7 | SDK、库、框架、API 文档兜底 | `CONTEXT7_API_KEY`、`CONTEXT7_BASE_URL` | [Context7 docs](https://context7.com/docs) | [Context7](https://context7.com/) |
| 智谱 Web Search API | 中文、国内、时效、域名过滤类来源发现 | `ZHIPU_API_KEY`、`ZHIPU_API_URL`、`ZHIPU_SEARCH_ENGINE` | [智谱联网搜索文档](https://docs.bigmodel.cn/cn/guide/tools/web-search) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| 智谱 Coding Plan Remote MCP | 使用 Coding Plan 额度做联网搜索、网页读取、开源仓库发现 | `ZHIPU_MCP_API_KEY`、`ZHIPU_MCP_SEARCH_API_URL`、`ZHIPU_MCP_READER_API_URL`、`ZHIPU_MCP_ZREAD_API_URL` | [联网搜索 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server)、[网页读取 MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server)、[zread MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server) | [智谱 API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Tavily | 额外来源、URL fetch、站点 map | `TAVILY_API_URL`、`TAVILY_API_KEY`、`TAVILY_ENABLED` | [Tavily docs](https://docs.tavily.com/) | [Tavily app](https://app.tavily.com/home) |
| Jina Reader | 已知 URL 正文抓取；满足 standard 最低配置必须有 key | `JINA_API_KEY`、`JINA_READER_API_URL`、`JINA_RESPOND_WITH`、`JINA_TIMEOUT_SECONDS` | [Jina Reader](https://jina.ai/reader/) | [Jina AI](https://jina.ai/) |
| Firecrawl | fetch 兜底、补充网页来源 | `FIRECRAWL_API_URL`、`FIRECRAWL_API_KEY` | [Firecrawl docs](https://docs.firecrawl.dev/) | [Firecrawl API keys](https://www.firecrawl.dev/app/api-keys) |
| TinyFish | 搜索与抓取兜底 | `TINYFISH_API_KEY`、`TINYFISH_SEARCH_API_URL`、`TINYFISH_FETCH_API_URL`、`TINYFISH_TIMEOUT_SECONDS` | [TinyFish 文档](https://docs.tinyfish.ai/) | [TinyFish API keys](https://agent.tinyfish.ai/api-keys) |
| TypeSafe / Jev | 可选语义路由和证据判断 | `TYPESAFE_API_KEY`、`TYPESAFE_API_URL`、`TYPESAFE_MODEL` | [TypeSafe API](https://docs.typesafe.ai/api) | 参见 TypeSafe 文档 |
| AnySearch | 实验垂直搜索验收入口，不是默认兜底 | `ANYSEARCH_API_URL`、`ANYSEARCH_API_KEY`、`ANYSEARCH_TIMEOUT_SECONDS` | [AnySearch 文档](https://www.anysearch.com/docs) | [AnySearch API keys](https://www.anysearch.com/console/api-keys) |
| Sciverse | 显式实验学术检索、语义论文检索、正文片段和引用/参考文献关系，不是默认兜底 | `SCIVERSE_API_TOKEN`、`SCIVERSE_API_URL`、`SCIVERSE_TIMEOUT_SECONDS` | [Sciverse Agent Tools](https://github.com/opendatalab/Sciverse-Agent-Tools) | Sciverse 控制台 / token 提供方 |

意图路由配置：

| 配置项 | 用途 |
| --- | --- |
| `SMART_SEARCH_INTENT_ROUTER` | `hybrid`、`rules`、`off` 或 `jev`，默认 `hybrid` |
| `INTENT_EMBEDDING_API_URL` | 可选 OpenAI-compatible embeddings endpoint，用于语义能力路由；推荐 setup preset 使用 `https://api.siliconflow.cn/v1/embeddings` |
| `INTENT_EMBEDDING_API_KEY` | 可选 embeddings key；`doctor` 和 config 输出会脱敏 |
| `INTENT_EMBEDDING_MODEL` | embeddings 模型名；推荐 setup preset 使用 `Qwen/Qwen3-Embedding-8B` |
| `INTENT_EMBEDDING_THRESHOLD` | 语义路由阈值，默认 `0.74`；推荐 8B setup 值是 `0.475`；这是模型相关参数 |
| `INTENT_EMBEDDING_MARGIN` | top1 与第二名分数差阈值，默认 `0.05`；推荐 8B setup 值是 `0.053`；差距不足时只记录 ambiguous 信号，不直接加 capability |
| `INTENT_CLASSIFIER_API_URL` | 可选 OpenAI-compatible chat-completions endpoint，用于结构化意图分类 |
| `INTENT_CLASSIFIER_API_KEY` | 可选 classifier key；`doctor` 和 config 输出会脱敏 |
| `INTENT_CLASSIFIER_MODEL` | classifier 模型名 |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | 可选远程路由调用超时，默认 `8` |
| `SMART_SEARCH_TIMEOUT_SECONDS` | `search` 的总单调时限，默认 `300`；单次 `search --timeout` 可覆盖 |
| `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS` | 可选 provider 连续失败后被跳过的时长，默认 `900`；设为 `0` 关闭冷却 |
| `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` | 可选 provider 进入冷却前允许的连续软失败次数，默认 `2` |

`jev` 是推荐的可选语义路由，默认仍为 `hybrid`。它结合渠道专长和已有 provider 偏好选择搜索引擎，判断累计证据是否相关、有用和足够，再选择新查询、另一引擎或阅读已发现的网页。research 保留计划、预算、报告及“实际读正文后才能引用”的约束；可选过滤改变内容后重新判断。TypeSafe 故障时按允许的固定能力兜底并标记降级，不隐藏调用旧远程分类器。最终汇总保留 `true/false/auto` 三态，默认直接返回证据；启用时只调用独立配置的 JEV 汇总模型，与主搜索模型无关。`route --router-mode jev` 是本地候选预览，只有显式 `--remote` 才调用可能计费的 TypeSafe 判断。配置、限制和诊断见 [Jev 路由与过滤](../../jev-routing.md)。

默认 `hybrid` 是 fail-open：embeddings 或 classifier 没配置、超时或失败时，会在 `degraded_reason` 里说明，然后自动退回本地规则。语义路由只有在 top1 相似度达到 `INTENT_EMBEDDING_THRESHOLD`，并且 top1 与第二名差值达到 `INTENT_EMBEDDING_MARGIN` 时，才会直接添加 capability；否则只记录 ambiguous 信号。classifier 可以补充 capability，但未知 capability 和 provider 名会被忽略；provider 仍然只能由 capability-first 注册表选择。

普通用户推荐直接使用 Qwen3-Embedding-8B preset：`INTENT_EMBEDDING_API_URL=https://api.siliconflow.cn/v1/embeddings`、`INTENT_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`、`INTENT_EMBEDDING_THRESHOLD=0.475`、`INTENT_EMBEDDING_MARGIN=0.053`。选择 8B 模型且没有手动配置 threshold/margin 时，`smart-search setup` 会自动补齐这两个推荐值。

embedding 余弦分数强依赖模型。`route-calibrate` 保留给高级复验：换 `INTENT_EMBEDDING_MODEL`、换 embedding endpoint，或者后续加入真实 query 校准集后再运行：

```powershell
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
```

再按报告推荐值设置 `INTENT_EMBEDDING_THRESHOLD` 和 `INTENT_EMBEDDING_MARGIN`。校准主指标是 semantic-only Macro-F1；full-route Macro-F1 只用来验证 rules/classifier 兜底后的真实路由表现。

几个容易混淆的点：

- xAI 官方联网搜索通过 `XAI_*` 走 `/responses`。OpenAI-compatible 中转默认走 `/chat/completions`；只有中转明确支持文档化的 Responses 子集时才设置 `OPENAI_COMPATIBLE_API_MODE=responses`。
- `OPENAI_COMPATIBLE_STREAM=true` 或 `smart-search search --stream` 只会给 OpenAI-compatible 的 `search` 和 provider 侧 `fetch` 设置 `stream=true`。它是中转长请求兼容开关，不改变 xAI Responses、URL 描述和来源排序行为。
- `SMART_SEARCH_TIMEOUT_SECONDS` 是持久化的 `search` 总时限；环境变量覆盖本机配置文件，单次 `search --timeout SECONDS` 覆盖两者，默认 `300` 秒。
- service 以一个单调 deadline 协调 router、main search、extra sources 和 supplemental evidence。hybrid 远程路由共享一个上限，并为 main search 预留 `min(240 秒, 总时限的三分之二)`；可选工作超时只会产生部分成功，不会清空已有主答案。
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
- AnySearch 默认走 `https://api.anysearch.com/mcp` 的 JSON-RPC 2.0 `tools/call`。没有 key 时允许匿名请求；有 key 时发送 `Authorization: Bearer ...`。HTTP 200 但 `result.isError=true` 会按 provider error 处理，不能当成功证据。`--sub-domain-params` 会先解析成 JSON object，随后可重复的 `--param key=value` 覆盖同名键；参数不合法时会在发请求前失败。
- Sciverse 默认走 `https://api.sciverse.space` 的 native HTTP/OpenAPI。必须配置 `SCIVERSE_API_TOKEN`；未配置时本地返回 `config_error` 且不发网络请求；已配置时发送 `Authorization: Bearer ...`。它保持 explicit-only：不是 `docs_search`，不满足 `standard`，不进入默认 `search` / `research` 兜底。
- `doctor` 和 `route` 会报告 intent router 的配置状态、embedding 模型、threshold、margin、配置来源、超时和是否可降级，不会暴露 router API key。

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
- `web_fetch`：Tavily、带 `JINA_API_KEY` 的 Jina、智谱 Coding Plan MCP Reader、Firecrawl、TinyFish 五选一。

缺少任一最低能力时，`doctor` 和 `search` 会 fail closed 并返回缺失 capability。`SMART_SEARCH_MINIMUM_PROFILE=off` 只建议本地实验使用。

AnySearch 是可选实验配置，不满足也不改变 `standard` 最低配置：

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
| `SMART_SEARCH_INTENT_ROUTER` | 意图路由模式：`hybrid`、`rules`、`off`、`jev`，默认 `hybrid` |
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
| `TAVILY_ENABLED` | 默认 `true`；只有 `true`、`1`、`yes` 启用 Tavily，其他值禁用且不发 Tavily 网络请求 |
| `TAVILY_TIMEOUT_SECONDS` | Tavily 连通性检查超时，默认 `30`；公益站/号池较慢时可调大 |
| `FIRECRAWL_API_URL` | Firecrawl REST base |
| `FIRECRAWL_API_KEY` | Firecrawl key |
| `SMART_SEARCH_VALIDATION_LEVEL` | `fast`、`balanced`、`strict` |
| `SMART_SEARCH_FALLBACK_MODE` | `auto` 或 `off` |
| `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` | `research` 路由优先 provider CSV，只能在同 capability 内调整顺序 |
| `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` | `research` 禁用 provider CSV，不能改变 provider capability 边界 |
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
