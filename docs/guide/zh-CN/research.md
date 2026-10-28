[手册目录](../README.md) · [English](../en/research.md)

# 搜索与研究

`search` 和 `research` 是两种联网搜索模式，共用渠道目录、执行器、总时限和证据记录。

- `search`：一次 Jev 选路，选择一个适合的渠道，返回结果与来源。Context7 查库后读文档等必要依赖调用，以及同能力故障兜底继续保留，模型回答与网页搜索互为兜底。不会执行充分性评估、自动补搜、过滤或汇总。`--extra-sources N` 只限制所选渠道的结果数量（最多 20），不增加渠道。`evidence_assessment.status=not_evaluated` 表示尚未评估，检索成功不等于事实核验成功。`--validation strict` 要求来源证据，不满足时可保留部分内容并返回证据错误。
- `research`：Jev 选择互补动作并发执行，读取发现的网页，判断证据缺口，必要时继续。原问题、子问题和有限缺口查询由程序提供，Jev 只选择候选，不生成任意查询或工具调用。只有实际 fetched/read 的内容进入 `citations`。可选过滤和 `SMART_SEARCH_JEV_SYNTHESIZE=false|auto|true` 只影响深入搜索。
- `deep` 继续离线生成计划，`steps[].command` 是供人或 AI 手动编排的建议。`research` 实际执行记录单独保存在 `routing_decision.rounds` 和 `stage_results` 中。

默认 `SMART_SEARCH_INTENT_ROUTER=jev`。没有 TypeSafe key 或无法得到有效判断时，`--fallback auto` 使用本地能力规则并标记降级，`--fallback off` 明确失败。没有 TypeSafe key 时，`research` 读到第一批网页正文就停止（`judgment_unavailable`），结果总是标记降级；`deep` 使用 strict，需要 Jev 判断证据充分，所以不会返回 `ok=true`。`SMART_SEARCH_JEV_SYNTHESIZE=true` 仍会汇总读到的证据，`auto` 需要 Jev。需要稳定的深入搜索时请配置 TypeSafe key。显式 `local` 从不调用 Jev。旧 `hybrid` 映射为 `jev`，`rules` 和 `off` 映射为 `local`。旧 embedding/classifier 字段和 Key 保留但不使用，`route-calibrate` 是不联网的退役兼容命令。

`route` 默认只预览本地能力，不调用模型或检索服务；显式 `--remote` 才进行可能计费的 Jev 诊断。直接 provider 命令保持明确的调用语义。

只有已配置、启用、允许且不在冷却期的渠道可以执行。`--providers`、各 provider 开关、`SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` 和 explicit-only 限制在选路与派发前检查。普通渠道失败可在同能力内兜底，模型回答与网页搜索互为兜底，不能扩展成深研循环；用户偏好也不能绕过这些边界。

总时限默认 300 秒（`SMART_SEARCH_TIMEOUT_SECONDS`，`search --timeout` 可覆盖）。深研 quick/standard/deep 的上限分别是 2/3/10 轮、每轮 1/2/10 渠道、每渠道 3/5/20 个结果，以及 45/120/配置秒数，并受用户 Jev 预算进一步限制。证据充分、候选耗尽、无新证据或期限到达时停止；可选判断、过滤、汇总失败仍保留已完成的结果。

## 能力与服务商

| 能力 | 主要命令 | Provider | 负责什么 |
| --- | --- | --- | --- |
| `main_search` | `search` | xAI Responses、OpenAI-compatible Chat Completions 或 Responses | 综合回答、快速搜索、初步总结 |
| `docs_search` | `context7-library`、`context7-docs`、`exa-search` | Context7、Exa | 官方文档、SDK、API、框架/库文档 |
| `web_search` | `zhipu-search`、`zhipu-mcp-search`、由 `search` 选中执行 | 智谱 Web Search API、智谱 Coding Plan MCP、Tavily、Firecrawl、TinyFish、DeepSeek、元宝搜索 | 中文、国内、时效、域名过滤、补充来源 |
| `web_fetch` | `fetch`、`zhipu-mcp-reader` | Tavily、Jina Reader、智谱 Coding Plan MCP Reader、Firecrawl、TinyFish、DeepSeek | 已知 URL 正文抓取、证据提取 |
| `vertical_search` | `anysearch-domains`、`anysearch-search`、`anysearch-extract`、`anysearch-batch`、`sciverse-catalog`、`sciverse-search`、`sciverse-semantic`、`sciverse-read`、`sciverse-relations` | AnySearch 和 Sciverse（实验） | 显式结构化垂直域；Sciverse 覆盖学术文献检索、语义搜索、正文片段和引用关系 |
| `site_map` | `map` | Tavily | 文档站、产品站、目录型站点结构 |
| `deep_planner` | `deep` / `dr` | 本地 planner | 离线生成 Deep Research 计划，不默认联网 |
| `research_executor` | `research` / `rs` | 按 capability 注册的 provider | 共享 Jev 循环与正文证据 |

```powershell
smart-search search "React useEffect API docs" --format json
smart-search research "Compare the documented limitations" --budget deep --evidence-dir "./evidence" --format json
smart-search deep "Plan a comparison" --budget standard --format json
smart-search route "React useEffect API docs" --format markdown
smart-search fetch "https://example.com/source" --format markdown
```

页面实际读取前，`sources` 是发现元数据；选中模型渠道时，`primary_sources` 保留模型引用。旧 `extra_sources` 列表保持为空。深研在 `evidence_dir` 保存计划、证据 Markdown、`summary.json` 和 `report.json`；下结论前检查 `gap_check`、`provider_attempts`、`warnings` 与 `partial_success`。Sciverse 保持 explicit-only，需直接调用 `sciverse-*`。详见[配置](configuration.md)与 [Jev 说明](../../jev-routing.md)。

## 离线计划与证据字段

Deep Research 不是固定题材配方。计划包含 `intent_signals`、`decomposition`、`capability_plan` 和 `usage_boundary`；`doctor` 只是配置预检，不是研究取证步骤。实际执行结合 provider 优势，报告保留 `route_policy_version`、`intent_router_mode`、`required_capabilities` 和 `degraded_reason`。没有 fetch 的来源标为未验证候选。

AnySearch 和 Sciverse 不进入 `web_search` 兜底链，也不是 `standard` 最低配置要求。Sciverse 不是 `docs_search`，保持显式调用；AnySearch 配置后可用于合适的垂直问题。

显式取消会终止未完成工作，并返回 `error_type=cancelled`，保留已完成内容、来源、引用和 `partial_success`。App 任务状态仍为已取消，部分证据也会写入研究报告。
