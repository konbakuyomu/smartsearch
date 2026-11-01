# Agent Note: OpenAI 兼容通道用开关发送 Responses 的 web_search 工具

Status: implemented

## Problem

OpenAI 的新模型（`gpt-6.1-sol`、`gpt-6-astra`）只能在 Responses 接口里带 `tools: [{"type": "web_search"}]` 联网，在 Chat Completions 里传 `web_search_options` 会返回 400。2026-09 加 `OPENAI_COMPATIBLE_API_MODE=responses` 时定下「兼容通道不发搜索工具」，免得弄坏不支持工具的中转站。结果用官方 key 的人在兼容通道里只能靠 `gpt-5-search-api` 联网。能发工具的 `XAI_*` 槽位名字和默认值都指向 xAI，用户发现不了；把它指向 OpenAI 时，默认工具里的 `x_search` 还会触发 400。2026-11-01 用官方 key 的实测记录在 `codestable/issues/002-o-openai-responses-web-search.md`。

## Decision

兼容通道有 `OPENAI_COMPATIBLE_TOOLS`：逗号分隔，允许 `web_search` 和 `web_search_preview`，默认空。

- 只有 `OPENAI_COMPATIBLE_API_MODE=responses` 的 `search()` 请求附带 `tools`；`fetch()`、`describe_url()`、`rank_sources()`、`synthesize()` never 带工具。
- 默认空时请求和以前完全一样，不支持工具的中转站不受影响。
- 设置了工具而接口模式是 `chat-completions` 时，读配置就报参数错误（`parameter_error`），提示把接口模式改成 `responses` 或清空工具，不悄悄忽略。
- `diagnose openai-compatible` 的两个真实 search 形态探测和联网探测按同一配置发工具；轻量连接测试和 `doctor` 照旧不带工具，不产生计费的搜索。
- 备用模型（`OPENAI_COMPATIBLE_FALLBACK_MODELS`）沿用同一组工具。

## 配置契约

| 键 | 取值 | 默认 | 生效条件 |
|---|---|---|---|
| `OPENAI_COMPATIBLE_TOOLS` | `web_search`、`web_search_preview`，逗号分隔 | 空 | `OPENAI_COMPATIBLE_API_MODE=responses` |

`web_search_preview` 给只实现了旧版工具名的中转站用；OpenAI 官方两个名字都接受。

## Alternatives considered

- **Responses 模式自动带上 `web_search`**：配置最少，用官方 key 的人切到 responses 就能联网。但 9 月的约定正是为了不让不支持工具的中转站收到工具字段，已经在用 responses 模式的中转用户升级后会直接失败。否掉。
- **按地址判断，只对 `api.openai.com` 带工具**：官方用户零配置。可很多用户经中转访问 OpenAI 模型，按地址判断覆盖不到他们，换中转时同一份配置的行为还会突变。否掉。
- **把 `XAI_*` 槽位改成通用的 Responses 槽位**：现成代码已经会发工具、解析引用。但改名会牵动 Jev 里「Grok search」的含义、老配置迁移和 App 文案，同时有 Grok 和 OpenAI 的人仍然只能用一个槽位。否掉。
- **布尔开关 `OPENAI_COMPATIBLE_WEB_SEARCH=true`**：App 里只有一个勾，最直观。但只能表达一个工具名，接不了只认 `web_search_preview` 的中转，写法也和 `XAI_TOOLS` 不一致。选逗号分隔的工具列表。

## Consequences

- 收益：用官方 key 的人在兼容通道填 `gpt-6.1-sol`，再设两项配置就能联网，不再占用 xAI 槽位；Grok 和 OpenAI 可以同时配置，xAI 失败时照常回退到兼容通道。
- 收益：默认行为不变，现有中转用户无感。
- 代价：多一个配置项，命令行 `setup`、App 和文档都要讲清它依赖接口模式；组合配错时搜索直接报参数错误，不降级继续搜。
- 代价：推理模型带 web_search 一次可能搜好几轮。2026-11-01 实测 Sol 每次 7–16 秒、约 $0.04–0.09，比 `gpt-5-search-api` 慢；用哪个模型由用户自己权衡。
- 9 月「兼容通道不发搜索工具」的约定改为「默认不发，显式打开才发」。
