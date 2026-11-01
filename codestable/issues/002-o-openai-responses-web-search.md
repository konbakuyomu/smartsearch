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

## 现状怎么工作

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

建议在兼容通道加 `OPENAI_COMPATIBLE_TOOLS`，默认空，只接受 `web_search`，只在 `api_mode=responses` 的 `search()` 上附带；`fetch()`、`describe_url()`、`rank_sources()`、`synthesize()` 不带工具。`diagnose openai-compatible` 的联网探测按同一配置发请求，连接测试照旧不带工具。这会改动 9 月“兼容通道不发搜索工具”的约定，动手前先写 `.agents/notes/` 决定笔记，并在这里链接。

另一条路是把 xAI 槽位改成通用的 Responses 槽位。它会牵动 Jev 里 “Grok search” 的含义和老配置迁移，影响面更大，放在笔记里一起比较。

## 验证

- 单测：开关关闭时请求和现在完全一样；打开后只有 Responses 模式的 `search()` 带 `tools`。
- 实测：官方 key 加 Sol 走兼容通道，balanced 搜索得到回答和带标题的来源；同时配置 Grok（xAI 槽位）和 OpenAI 兼容通道时两边都能用。
- 中转站：开关关闭时行为不变。

## 关闭时

- 回写到 project/epic spec 或 notes 的候选：
- 关闭判断与验证摘要：
- 遗留：
