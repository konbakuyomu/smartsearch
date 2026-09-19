# Jev 多渠道路由

Jev 模式按用户问题、难度、时效要求、可用渠道和已有证据直接多选渠道，并行执行后再判断是否需要补搜。没有搜索前的第二轮复核。`hybrid`、`rules`、`off` 保持原有行为；默认仍是 `hybrid`。

## 配置

使用 `smart-search config set KEY VALUE` 写入用户配置文件；环境变量优先于配置文件。API key 只保存在用户配置中，常规配置输出会遮罩。至少需要 TypeSafe key 和一个检索渠道，Jev 模式不要求旧版 standard profile 的主模型、文档、抓取三类全部配置。

```sh
smart-search config set TYPESAFE_API_KEY '<your-key>'
smart-search config set SMART_SEARCH_INTENT_ROUTER jev
smart-search config set SMART_SEARCH_JEV_FILTER_RESULTS true
smart-search config set SMART_SEARCH_JEV_SYNTHESIZE false
smart-search route 'React useEffect cleanup 什么时候执行？' --router-mode jev
smart-search search 'React useEffect cleanup 什么时候执行？' --timeout 90
```

交互式 setup 的路由选项也提供 Jev、过滤和汇总开关。仅配置 Jev 与单一检索渠道时，可直接使用上面的 `config set`，不必完成旧版向导的三类主搜索配置。

| 配置项 | 默认值 | 行为 |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | 空 | Jev 必需凭据 |
| `TYPESAFE_API_URL` | `https://api.typesafe.ai/v1` | System One API base，也接受完整 `/systemone` 地址 |
| `TYPESAFE_MODEL` | `jev-latest` | 模型名；质量校准时可固定模型版本 |
| `SMART_SEARCH_JEV_TIMEOUT_SECONDS` | `15` | 单次 Jev 请求的总超时，包含有限重试 |
| `SMART_SEARCH_JEV_MAX_ROUNDS` | `3` | 最多搜索轮数，包含首次搜索；范围 1–10 |
| `SMART_SEARCH_JEV_MAX_CHANNELS` | `3` | 每轮最多执行的渠道操作数；范围 1–10 |
| `SMART_SEARCH_JEV_RESULTS_PER_CHANNEL` | `5` | 搜索结果条数，范围 1–20；提供方可能返回更少 |
| `SMART_SEARCH_JEV_ROUTE_THRESHOLD` | `0.5` | 多选渠道的 Noul 阈值 |
| `SMART_SEARCH_JEV_SUFFICIENCY_THRESHOLD` | `0.75` | 累积证据足够的阈值 |
| `SMART_SEARCH_JEV_FILTER_RESULTS` | `false` | 搜索完成后是否剔除无关证据 |
| `SMART_SEARCH_JEV_FILTER_THRESHOLD` | `0.1` | 仅低于此相关概率才删除；范围 0–0.49 |
| `SMART_SEARCH_JEV_SYNTHESIZE` | `false` | `true`：汇总；`false`：直接返回证据；`auto`：让 Jev 判断是否汇总 |

阈值是初始策略，并不保证判断正确，需要用实际问题校准。过滤关闭时仍然会判断是否需要补搜。

## 执行行为

1. 候选集合只包含已配置且启用的 provider，受 `--providers`、`TAVILY_ENABLED`、`SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` 和 provider cooldown 约束。传给 Jev 的只有能力描述、问题、结果和操作历史，没有渠道密钥。
2. Jev 对候选操作批量进行独立 Noul 判断；程序验证概率、排序并限制数量。不满足阈值时允许没有选择，不会强制执行最高分渠道。未知响应 ID 不会成为工具调用。
3. 同轮操作并发，单个渠道失败不丢弃其他渠道结果。Context7 会检索库、判断正确的库 ID，再获取实际文档，不把库介绍当成答案。
4. Jev 判断累计证据是否有用、是否足够，并标记直接答案、细节、时效、权威性、交叉验证等缺口。夹杂无关结果本身不会触发补搜。对于长文本，判断使用覆盖每条结果的显式截断预览，`preview_truncated` 会如实报告。
5. 不足时从未执行的操作中再次选择。问题保持原文，缺口和已执行操作作为补搜决策上下文。网页搜索发现的新 URL 可进入后续抓取候选；同一 provider 的搜索与抓取是不同操作。同一操作和 URL 不会重复执行。
6. 达到轮数、时间上限、没有新候选或 Jev 出错时结束，并保留已经取得的内容。`--fallback off` 禁用补搜；`--extra-sources N` 在 Jev 模式中设置每个搜索渠道的结果数量，上限 20。

支持现有 xAI、OpenAI-compatible、Exa、Context7、Zhipu REST/MCP、Tavily、Jina、Firecrawl、AnySearch 的对应搜索或抓取操作，并兼容独立 TinyFish provider 合入后的搜索与抓取。候选目录以当前程序实际注册的渠道为准。没有已知 URL 时不提供抓取选项；每轮最多考虑 5 个已知 URL。Sciverse 保留原有 explicit-only 限制，仓库检索和 site map 仍通过独立命令执行。

默认直接返回组织好的证据给调用方模型。Grok 只有被选为搜索渠道，或配置开启最后汇总时才会调用。最后汇总使用现有主模型配置，例如 `OPENAI_COMPATIBLE_MODEL=grok-4.6`，请求只附证据，不附搜索工具；汇总失败时保留检索证据并返回 warning。

`SMART_SEARCH_JEV_SYNTHESIZE` 有三种模式，配置文件和环境变量都支持：

- `true`：获得有用证据后直接调用已配置主模型汇总，不额外询问 Jev。
- `false`：直接返回证据，不调用主模型汇总，也不做汇总必要性判断。仍是默认值。
- `auto`：在可选过滤结束后，Jev 根据原问题、问题难度、最终保留的证据和已有缺口判断汇总是否有价值。需要跨来源综合、解释、比较或用户明确要求总结时倾向汇总；只要链接、原文或证据已经直接回答问题时倾向直接返回。Noul 大于 0.5 才调用主模型，正好 0.5 时返回证据。

启用自动判断：`smart-search config set SMART_SEARCH_JEV_SYNTHESIZE auto`。原有 JSON 布尔值和 `1/0`、`yes/no`、`on/off` 仍兼容。自动模式没有可用主模型时直接返回证据；Jev 判断失败、超时或响应无效时也返回证据并记录原因，不自动升级为主模型调用。过滤未开启时，判断依据是最终未过滤的证据；长文使用带有截断标记的预览。

`research` 在 Jev 模式中使用同一执行流程；`--budget deep` 要求 strict 验证，其他 budget 使用 balanced。指定 `--evidence-dir` 时保存 `report.json`。`deep` 继续是离线规划器。

## 二分过滤

过滤只在至少已有部分有用证据时执行。长文按段落拆分；必须在段落内部切分时保留重叠上下文。每组判断“是否存在任何能帮助回答问题的片段”，只删除明确无关的整组，其余组继续二分。两半都判断，小组按单条批量判断。不确定、反例、限制条件和部分答案均允许保留。

过滤阶段检查完整片段，不用搜索判断阶段的截断预览。每次请求限制分组状态大小。调用失败、超时或整份证据被删除时返回原始证据；删除部分段落后保留来源、标题、日期等信息，并用 `[…]` 标记间隔。

`content` 只携带一次最终内容；`sources` 和路由记录仅含元数据，不重新附上被删文本。输出包括：

- `routing_decision.rounds`：各轮选中的渠道、概率、结果判断和停止原因。
- `evidence_assessment`：足够、部分、无用或判断未知。balanced 可返回部分成功；strict 必须达到证据足够。
- `result_filter`：过滤状态、前后字符数、删除片段 ID、失败保留原因。
- `synthesis`：配置的 `mode`、是否决定汇总的 `enabled`、执行状态，以及 auto 模式的判断来源、概率、阈值或跳过原因。此判断消耗计入 `jev_usage`，阶段记为 `synthesis_decision`。
- `jev_usage` / `jev_calls`：API 返回的真实 token 用量、请求数和耗时；没有用字符数冒充 token。
- `provider_attempts`、`warnings`、`partial_success`：渠道失败和降级信息。

二分最坏仍会检查所有片段，不能保证总成本降低。相关内容密集时可能不删除任何内容，却产生过滤开销；应结合 Jev 用量和下游模型的实际 tokenizer 评估收益。

## 开发验证

工具链由 `mise.toml` 管理。运行 `mise run install` 后，可执行 `mise run test` 与 `mise run check`。在 macOS 默认临时路径过长、触发旧有 CLI 表格截断断言时，可给 pytest 指定短目录，例如 `mise run test --basetemp /tmp/smart-search-jev-tests`。

`mise run python scripts/verify-jev-live.py` 会消耗已配置服务的实际 API 配额，测试 Tavily URL 抓取和真实 Jev 对固定混合样本的二分过滤。加 `--synthesis` 还会验证现有主模型的证据汇总。输出写入被 Git 忽略的 `.smart-search/jev-tests/live-report.json`；固定样本不会被冒充为实际搜索结果。

`mise run python scripts/verify-jev-live.py --auto-synthesis-only --synthesis` 使用固定证据验证真实 Jev 的“需要汇总”和“不需要汇总”两条分支，并仅在判断需要时调用主模型。

接口依据：[TypeSafe HTTP API](https://docs.typesafe.ai/api)、[Noul](https://docs.typesafe.ai/primitives/noul)、[检索重排示例](https://docs.typesafe.ai/cookbooks/rerank_typesafe)。
