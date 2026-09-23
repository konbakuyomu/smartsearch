[手册目录](../README.md) · [English](../en/configuration-reference.md)

# 全部配置项

由当前配置元数据生成。下表列出全部可保存键；申请 Key、配置优先级、运行环境变量及最低能力要求见[配置指南](configuration.md)。未设置的密钥必须由用户提供；可选服务未配置时不会自动启用。

## 先配这三样

| 配置键 | 用途及条件 | 类型 / 取值 | 默认值 |
| --- | --- | --- | --- |
| `XAI_API_KEY` | 用 xAI 做主搜索时填这个。和下面的 OpenAI 兼容接口二选一即可。 | `secret` | 未设置 |
| `XAI_API_URL` | 用官方地址就别动。走代理或中转时才改。 | `url` | `https://api.x.ai/v1` |
| `XAI_MODEL` | 留空用默认模型。 | `text` | `grok-4-fast` |
| `XAI_TOOLS` | 逗号分隔。可选 web_search 和 x_search。 | `web_search, x_search` | `web_search,x_search` |
| `OPENAI_COMPATIBLE_API_URL` | 任何兼容 OpenAI 协议的服务都行。要和下面的 key 一起填才算配好。 | `url` | 未设置 |
| `OPENAI_COMPATIBLE_API_KEY` | 下面的链接是 OpenAI 官方的。用中转或第三方服务的话，key 去对应服务商那里拿。 | `secret` | 未设置 |
| `OPENAI_COMPATIBLE_MODEL` | 按服务商文档填，例如 gpt-4o、deepseek-chat。 | `text` | 未设置 |
| `OPENAI_COMPATIBLE_FALLBACK_MODELS` | 逗号分隔。主模型不可用时按顺序往下试。 | `csv` | 未设置 |
| `OPENAI_COMPATIBLE_API_MODE` | 大多数服务用 chat-completions。 | `chat-completions, responses` | `chat-completions` |
| `OPENAI_COMPATIBLE_STREAM` | 部分服务只在流式下才肯长时间思考。 | `bool` | `false` |
| `XAI_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `OPENAI_COMPATIBLE_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |

## 数据源

| 配置键 | 用途及条件 | 类型 / 取值 | 默认值 |
| --- | --- | --- | --- |
| `EXA_API_KEY` | 文档检索能力的两个选项之一。 | `secret` | 未设置 |
| `EXA_BASE_URL` | Exa 服务的基础地址；默认使用官方服务。不要附加 /search。 | `url` | `https://api.exa.ai` |
| `EXA_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `CONTEXT7_API_KEY` | 查开源库文档用。文档检索能力的另一个选项。 | `secret` | 未设置 |
| `CONTEXT7_BASE_URL` | Context7 服务基础地址；程序会补全库搜索和文档接口路径。 | `url` | `https://context7.com` |
| `CONTEXT7_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `ZHIPU_API_KEY` | 国内时效内容搜得比较好。属于可选增强，不配也能跑。 | `secret` | 未设置 |
| `ZHIPU_API_URL` | 智谱联网搜索基础地址；保留 /api，程序会补全搜索接口路径。 | `url` | `https://open.bigmodel.cn/api` |
| `ZHIPU_SEARCH_ENGINE` | search_std / search_pro / search_pro_sogou / search_pro_quark，或自定义。 | `text` | `search_std` |
| `ZHIPU_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `ZHIPU_MCP_API_KEY` | 一个 key 同时提供搜索和网页抓取，抓取那一路可以满足最低配置。 | `secret` | 未设置 |
| `ZHIPU_MCP_SEARCH_API_URL` | 智谱 Coding Plan 对应服务的完整 MCP 接口地址；保留末尾 /mcp，不要填官网首页。 | `url` | `https://open.bigmodel.cn/api/mcp/web_search_prime/mcp` |
| `ZHIPU_MCP_READER_API_URL` | 智谱 Coding Plan 对应服务的完整 MCP 接口地址；保留末尾 /mcp，不要填官网首页。 | `url` | `https://open.bigmodel.cn/api/mcp/web_reader/mcp` |
| `ZHIPU_MCP_ZREAD_API_URL` | 智谱 Coding Plan 对应服务的完整 MCP 接口地址；保留末尾 /mcp，不要填官网首页。 | `url` | `https://open.bigmodel.cn/api/mcp/zread/mcp` |
| `ZHIPU_MCP_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `JINA_API_KEY` | 把网页转成干净正文。注意没有 key 的匿名模式不算满足最低配置。 | `secret` | 未设置 |
| `JINA_READER_API_URL` | Jina Reader 的服务地址；程序会在后面附加要读取的网页 URL。 | `url` | `https://r.jina.ai` |
| `JINA_RESPOND_WITH` | 可留空。例如 readerlm-v2。 | `text` | 未设置 |
| `JINA_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `TAVILY_API_KEY` | 搜索和抓取都能做，一个 key 顶两类能力。 | `secret` | 未设置 |
| `TAVILY_API_URL` | Tavily 服务基础地址。使用官方服务时保留默认值，仅使用转发服务时修改。 | `url` | `https://api.tavily.com` |
| `TAVILY_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `TAVILY_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `FIRECRAWL_API_KEY` | 可选的搜索与抓取渠道。当前仅检查 Key 是否填写，不验证凭据或接口可用性。 | `secret` | 未设置 |
| `FIRECRAWL_API_URL` | Firecrawl 服务基础地址，包含版本路径 /v2；使用官方服务时保留默认值。 | `url` | `https://api.firecrawl.dev/v2` |
| `TINYFISH_API_KEY` | 一个 Key 支持搜索和网页抓取。测试会各发起一次真实请求。 | `secret` | 未设置 |
| `TINYFISH_SEARCH_API_URL` | TinyFish 搜索服务地址，与网页抓取地址不同；通常无需修改。 | `url` | `https://api.search.tinyfish.ai` |
| `TINYFISH_FETCH_API_URL` | TinyFish 网页抓取服务地址，与搜索地址不同；通常无需修改。 | `url` | `https://api.fetch.tinyfish.ai` |
| `TINYFISH_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `150` |
| `ANYSEARCH_API_KEY` | 垂直领域搜索，实验性。 | `secret` | 未设置 |
| `ANYSEARCH_API_URL` | AnySearch 的完整 MCP 接口地址，包含 /mcp；不是官网首页。 | `url` | `https://api.anysearch.com/mcp` |
| `ANYSEARCH_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `SCIVERSE_API_TOKEN` | 学术论文检索，实验性，只在明确指定时才会被用到。 | `secret` | 未设置 |
| `SCIVERSE_API_URL` | Sciverse 论文检索服务地址；使用官方服务时保留默认值。 | `url` | `https://api.sciverse.space` |
| `SCIVERSE_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `30` |
| `CONTEXT7_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `EXA_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `ZHIPU_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `ZHIPU_MCP_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `ZHIPU_MCP_READER_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `FIRECRAWL_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `TINYFISH_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `JINA_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `ANYSEARCH_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |
| `SCIVERSE_ENABLED` | 禁用后保留配置，不再发起请求。保存更改后生效。 | `bool` | `true` |

## 意图路由

| 配置键 | 用途及条件 | 类型 / 取值 | 默认值 |
| --- | --- | --- | --- |
| `SMART_SEARCH_INTENT_ROUTER` | jev 按语义选渠道并判断证据，需单独 Key；hybrid 结合规则和模型；rules 只用规则；off 关闭路由。 | `hybrid, jev, off, rules` | `hybrid` |
| `TYPESAFE_API_KEY` | 可选语义路由的独立凭据；填写不会自动切换路由模式。 | `secret` | 未设置 |
| `TYPESAFE_API_URL` | 仅 JEV 模式使用的 TypeSafe 基础地址；默认 https://api.typesafe.ai/v1，程序会补上 /systemone。不是搜索服务商地址。 | `url` | `https://api.typesafe.ai/v1` |
| `TYPESAFE_MODEL` | TypeSafe 用来判断渠道和证据的模型标识；与主搜索模型无关，通常保留默认值。 | `text` | `jev-latest` |
| `SMART_SEARCH_JEV_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `15` |
| `SMART_SEARCH_JEV_MAX_ROUNDS` | 最多进行几轮检索与证据判断；增加轮数可能提高耗时和费用。 | `int` | `3` |
| `SMART_SEARCH_JEV_MAX_CHANNELS` | 每轮最多调用多少个检索渠道；数值越大可能产生更多请求。 | `int` | `3` |
| `SMART_SEARCH_JEV_RESULTS_PER_CHANNEL` | 每个检索渠道请求的结果条数；通常保留默认值。 | `int` | `5` |
| `SMART_SEARCH_JEV_ROUTE_THRESHOLD` | 0 到 1。渠道适用概率达到此值时才选用；调高会减少选中的渠道。 | `float` | `0.5` |
| `SMART_SEARCH_JEV_SUFFICIENCY_THRESHOLD` | 0 到 1。证据充分概率达到此值时停止继续检索；调高要求更充分的证据。 | `float` | `0.75` |
| `SMART_SEARCH_JEV_FILTER_RESULTS` | 会增加判断请求；无法保证总费用减少。 | `bool` | `false` |
| `SMART_SEARCH_JEV_FILTER_THRESHOLD` | 0 到 1，仅启用证据过滤时生效；低于此相关性阈值的结果会被过滤。 | `float` | `0.1` |
| `SMART_SEARCH_JEV_SYNTHESIZE` | false 返回证据；auto 按需汇总；true 始终汇总。汇总只使用独立配置的模型。 | `false, auto, true` | `false` |
| `SMART_SEARCH_JEV_SYNTHESIS_API_URL` | 可选的独立 OpenAI 兼容接口。填写后还需提供 Key 和模型名。 | `url` | 未设置 |
| `SMART_SEARCH_JEV_SYNTHESIS_API_KEY` | 只用于 JEV 最终汇总，不用于检索或 JEV 判断。 | `secret` | 未设置 |
| `SMART_SEARCH_JEV_SYNTHESIS_MODEL` | 独立汇总模型名；地址、Key、模型名需要一起填写。 | `text` | 未设置 |
| `SMART_SEARCH_JEV_SYNTHESIS_API_MODE` | 选择独立汇总接口的调用模式：chat-completions 或 responses；需与服务商接口一致。 | `chat-completions, responses` | `chat-completions` |
| `INTENT_EMBEDDING_API_URL` | 可选的向量模型完整接口地址，须包含 /v1/embeddings；用来判断问题需要哪类能力，不负责生成搜索答案。hybrid 模式中与 Key、模型名配齐后启用。 | `url` | 未设置 |
| `INTENT_EMBEDDING_API_KEY` | 向量模型服务提供的 Key，需与上方接口地址和模型属于同一服务。留空则不启用向量判断。 | `secret` | 未设置 |
| `INTENT_EMBEDDING_MODEL` | 向量模型的准确名称，例如 BAAI/bge-m3；不是聊天模型。由接口服务商提供。 | `text` | 未设置 |
| `INTENT_EMBEDDING_THRESHOLD` | 0 到 1 之间。 | `float` | `0.74` |
| `INTENT_EMBEDDING_MARGIN` | 0 到 1 之间。 | `float` | `0.05` |
| `INTENT_CLASSIFIER_API_URL` | 可选分类模型的完整聊天接口地址，须包含 /v1/chat/completions；用来补充判断问题类型。hybrid 模式中与 Key、模型名配齐后启用，留空仍可按规则路由。 | `url` | 未设置 |
| `INTENT_CLASSIFIER_API_KEY` | 分类模型服务的 Key；与此处接口地址配套，不会自动沿用主搜索 Key。 | `secret` | 未设置 |
| `INTENT_CLASSIFIER_MODEL` | 用于输出分类结果的聊天模型名称；必须支持该接口的 JSON 输出，与主搜索模型分别配置。 | `text` | 未设置 |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | 等待此服务单次响应的最长秒数；超时会返回错误或按当前策略兜底，通常保留默认值。 | `float` | `8` |
| `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` | 逗号分隔的 provider id，深度研究时优先走这些。 | `csv` | 未设置 |
| `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` | 逗号分隔的 provider id，深度研究时完全不走这些。 | `csv` | 未设置 |

## 超时与兜底

| 配置键 | 用途及条件 | 类型 / 取值 | 默认值 |
| --- | --- | --- | --- |
| `SMART_SEARCH_VALIDATION_LEVEL` | strict 查得更严也更慢。 | `balanced, fast, strict` | `balanced` |
| `SMART_SEARCH_FALLBACK_MODE` | auto 会在一个数据源失败后自动换下一个。 | `auto, off` | `auto` |
| `SMART_SEARCH_MINIMUM_PROFILE` | standard 会在三类必需能力缺一时直接报错。关掉之后出问题更难查。 | `off, standard` | `standard` |
| `SMART_SEARCH_TIMEOUT_SECONDS` | 一整条搜索从开始到结束的上限。推理模型慢的时候需要调大。 | `float` | `300` |
| `SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS` | 一个数据源挂了之后多久不再尝试。填 0 关闭冷却。 | `float` | `900` |
| `SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD` | 连续失败几次才冷却。鉴权错误第一次就冷却，不看这个值。 | `int` | `2` |
| `SMART_SEARCH_RETRY_MAX_ATTEMPTS` | 单次请求最多尝试次数，包含首次请求；增大可能延长失败等待时间。 | `int` | `3` |
| `SMART_SEARCH_RETRY_MULTIPLIER` | 重试等待时间的退避系数；通常保留默认值，避免频繁重试触发限流。 | `float` | `1` |
| `SMART_SEARCH_RETRY_MAX_WAIT` | 两次重试之间最长等待秒数，不是整个搜索的总时限。 | `int` | `10` |

## 日志与调试

| 配置键 | 用途及条件 | 类型 / 取值 | 默认值 |
| --- | --- | --- | --- |
| `SMART_SEARCH_LANGUAGE` | 独立 CLI 的语言偏好；App 界面语言在设置中单独选择。 | `auto, zh, en` | `auto` |
| `SMART_SEARCH_DEBUG` | 输出更多排错信息；仅排查问题时开启，不会自动验证 API Key。 | `bool` | `false` |
| `SMART_SEARCH_LOG_LEVEL` | 日志详细程度：DEBUG、INFO、WARNING、ERROR。默认 INFO 适合日常使用。 | `text` | `INFO` |
| `SMART_SEARCH_LOG_DIR` | 启用写日志文件时使用的目录；可填绝对路径，相对路径相对于配置文件所在目录。 | `text` | `logs` |
| `SMART_SEARCH_LOG_TO_FILE` | 将运行日志写入日志目录；关闭时不写日志文件。 | `bool` | `false` |
| `SMART_SEARCH_OUTPUT_CLEANUP` | 整理输出文本中的多余标记；不删除配置、日志或结果文件。 | `bool` | `true` |
| `SSL_VERIFY` | 关掉只该是临时排查手段。 | `bool` | `true` |
