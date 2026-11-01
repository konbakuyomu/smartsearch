---
kind: issue
title: "OpenAI 官方 Responses 联网：让 Sol / Astra 用 web_search 做主搜索"
type: feature
status: open
created: 2026-11-01
---

# OpenAI 官方 Responses 联网：让 Sol / Astra 用 web_search 做主搜索

## 做成以后是什么样

用 OpenAI 官方 key 的人，在 OpenAI 兼容通道里打开一个开关，就能让 `gpt-6.1-sol`、`gpt-6-astra` 这类只在 Responses 里联网的模型做主搜索，不用再借 xAI 槽位。

**范围：** 包含兼容通道 Responses 模式下可选的 `web_search` 工具，以及配置项、App 字段、诊断和文档；不包含 `x_search`、域名过滤等 web_search 高级参数，也不改深度研究模式。

## 为什么现在做

2026-11-01 用户反馈：OpenAI 官方 API 现在只能用 `gpt-5-search-api` 联网，调用不了 Sol 和 Astra。OpenAI 的 web search 指南只建议已有 Chat Completions 集成继续用 `gpt-5-search-api`，新接入走 Responses。实测 Sol 在 Chat Completions 里传 `web_search_options` 返回 400，只能在 Responses 里带 `tools: [{"type": "web_search"}]` 联网。`gpt-4o-search-preview` 已在 2026-07-23 下线，实测返回 404。

## 改动前怎么工作

- `OPENAI_COMPATIBLE_API_MODE=responses` 只发 model、instructions、input、stream，不发工具。这是 9 月加 Responses 模式时定的，免得弄坏不支持工具的中转站。Sol 走这里会照提示词回 `NO_WEB_SEARCH`，被本地检查拒掉。
- xAI 槽位把 `XAI_TOOLS` 原样作为 Responses 工具发出，解析的 `output_text` 加 `url_citation` 和 OpenAI 的格式一致，所以现在不改代码也能用：

```text
XAI_API_URL=https://api.openai.com/v1
XAI_API_KEY=<OpenAI 官方 key>
XAI_MODEL=gpt-6.1-sol
XAI_TOOLS=web_search      # 默认值里的 x_search 会让 OpenAI 返回 400
```

这条路的代价：占掉 xAI 槽位，同时有 Grok 的人只能二选一；名字和默认值都指向 xAI，用户想不到能这么用；连接测试显示的是“xAI Responses API 可用”；也用不上兼容通道的备用模型和熔断。

## 实测证据（2026-11-01，官方 key，Smart Search 0.1.32）

| 路径 | 结果 |
|---|---|
| xAI 槽位指向 OpenAI，Sol 或 Astra，`XAI_TOOLS=web_search` | balanced 下 ok，回答完整，来源带页面标题，中文问题也通过；流式和 `XAI_REASONING_EFFORT=low` 也拿到回答和来源；`doctor` 连接测试通过 |
| xAI 槽位，默认 `XAI_TOOLS` | HTTP 400：`Invalid value: 'x_search'` |
| 兼容通道 Responses 模式加 Sol | 模型回 `NO_WEB_SEARCH`，本地检查拒绝 |
| 兼容通道 Chat Completions 加 `gpt-5-search-api` | 能联网，但引用漏读、回答被拆分器吞掉，已由 `issues/001-x-ff-openai-search-citations.md` 修复 |

只配模型通道时 `--validation strict` 按设计不通过：模型自带的引用算 citation，strict 要独立检索得到的来源。这和引用解析无关，Sol 走 xAI 槽位也一样。

同题对比用 Smart Search 的提示词和请求形态，5 题：Python 最新版、Mamba 论文、统计局前三季度 GDP、Node.js 的 LTS 线、`gpt-4o-search-preview` 下线日期。三个模型全部答对。

| 模型 | 耗时 | 检索 | 每次估算 |
|---|---|---|---|
| `gpt-5-search-api` | 6–9 秒 | 次数不可见，约 16–17k 输入 token | 价格页上没找到单价；本账号 TPM 上限 45k，并发 4 个就 429 |
| `gpt-6.1-sol` | 7–16 秒 | 1–3 次 web_search，13–25k 输入 token | 约 $0.04–0.09 |
| `gpt-6-astra` | 12–20 秒 | 2 次 web_search，13–22k 输入 token | 约 $0.16–0.27 |

估算按官方价格页：Sol 每 1M 输入 / 输出 token $2 / $10，Astra $10 / $50，web search 每 1000 次 $10，检索到的内容按模型输入价计。Sol 和 Astra 的引用更贴近一手页面（Node.js 的 `schedule.json`、OpenAI 的 deprecations 页），还会补充背景；Astra 贵约 5 倍，这几题看不出比 Sol 好。`gpt-5-search-api` 和 Sol 都引用过镜像或测试站（`psfhosted.net`、`test.python.org`、aapanel 镜像）。

## 方案与实现安排

采用兼容通道上的 `OPENAI_COMPATIBLE_TOOLS`：逗号分隔，允许 `web_search` 和 `web_search_preview`，默认空，只在 `OPENAI_COMPATIBLE_API_MODE=responses` 的 `search()` 上附带；`fetch()`、`describe_url()`、`rank_sources()`、`synthesize()` 和 `doctor` 连接测试不带工具。设置了工具而接口模式不是 `responses` 时，保存和搜索前都报参数错误。为什么这样选、否掉了哪几条路，见 `.agents/notes/implemented/feature/2026-11-01-openai-compatible-responses-web-search.md`。

## 验证

- 单测：开关关闭时请求和以前完全一样；打开后只有 Responses 模式的 `search()` 带 `tools`；配置写入、`setup`、搜索、`diagnose`、`model` 都拦下“有工具但不是 responses”的组合；备用模型沿用同一组工具。
- 实测：官方 key 加 Sol 走兼容通道，balanced 搜索得到回答和带标题的来源。
- 中转站：开关关闭时行为不变。
- 没做：同时配置 Grok（xAI 槽位）和兼容通道的实测，本机没有 xAI key；两条通道的配置互不相干，由单测覆盖。

## 执行记录

2026-11-01，分支 `claude/focused-bardeen-ihd6hm`：

- `5900c25`：`OPENAI_COMPATIBLE_TOOLS` 全链路——配置与校验、Responses `search()` 附带工具、诊断探测按配置发工具并给出新的建议、`setup --openai-compatible-tools`、App 字段、中英文消息、指南和技能文档、生成的参考页；决定笔记同提交。
- `a211d22`：实测里顺带发现的四个小问题（限流误报、`x_search` 报错、strict 提示、导入循环），见 `issues/003-x-ff-diagnostics-say-the-real-cause.md`。
- 全量 pytest 1264 passed、17 skipped；技能双份一致；决定笔记三项校验通过。

在 Windows 电脑上用分支代码和官方 key 实测，每个场景用独立的空配置目录：

| 场景 | 结果 |
|---|---|
| 兼容通道 + Sol + `OPENAI_COMPATIBLE_TOOLS=web_search` | ok，回答完整，来源带页面标题，10.3 秒；流式 9.5 秒；中文问题 8.4 秒，来源是统计局页面 |
| 同上换 Astra | ok，11.7 秒 |
| 主模型写错（404），备用模型 Sol | 主模型失败后备用模型带着工具成功 |
| 设置工具但接口模式是 chat-completions | 0.4 秒内报参数错误，没有发请求 |
| `config set` 先设工具再设模式、或有工具时改回 chat-completions | 都被拒绝并说明原因；先设 responses 再设工具成功 |
| `doctor` | 配置完整，`OPENAI_COMPATIBLE_TOOLS` 显示 `web_search`，连接测试通过 |
| `diagnose openai-compatible` | 五项检查全过，`web_search_capable: true` |
| 兼容通道 + `gpt-5-search-api`，4 次（含中文、流式） | 每次都保留回答，来源 1–3 个且带页面标题（0.1.32 上 5 次里 3 次回答被吞） |

## 关闭时

- 回写到 project/epic spec 或 notes 的候选：主搜索两条通道各自会发什么工具（xAI 槽位发 `XAI_TOOLS`；兼容通道只在 responses 模式按 `OPENAI_COMPATIBLE_TOOLS` 发，且只随搜索请求）；只配模型通道时 strict 不会通过。现状规格还是空模板，收尾时建「主搜索」一页写进去。决定笔记里引用的本 Issue 路径在改名为 `-x-` 时要同步。
- 关闭判断与验证摘要：上面的单测和实测都已通过，等发版后把官方 key 的配置写法回给反馈的人。
- 遗留：模型偶尔引用测试站或镜像（`test.python.org`、`psfhosted.net`），这是检索结果本身的问题，Smart Search 没有过滤。
