---
kind: issue
title: "实测中顺带发现的四个小问题：限流误报、x_search 报错、strict 提示、导入循环"
type: ff
status: closed
created: 2026-11-01
---

# 实测中顺带发现的四个小问题：限流误报、x_search 报错、strict 提示、导入循环

2026-11-01 用 OpenAI 官方 key 实测时发现了四个问题：`diagnose openai-compatible` 把 HTTP 429 限流说成“请检查 API URL、API key、模型名和网络”；xAI 槽位指向 OpenAI 时，默认工具里的 `x_search` 只换来一段 400 原文；只配模型通道时 strict 失败只说“证据不够”，看不出缺的是独立检索的来源；先导入 `smart_search.sources` 会因为循环导入失败。四处都改成直接说出原因和改法。

- 改动：`src/smart_search/service.py` — 诊断遇到 429 报 `rate_limited`，说明是限流、建议稍后再试，不再附带联网工具建议；`src/smart_search/providers/xai_responses.py` — 400 且被拒的是 `x_search` 时报参数错误，指明把 `XAI_TOOLS` 改成 `web_search`；`src/smart_search/jev_search.py` — strict 只拿到模型自带引用时，说明要配 web_search 提供方或改用 balanced；`src/smart_search/utils.py` — `SearchResult` 只在类型检查时导入；消息目录补了中英文。
- 验证：新增 4 个用例，在修复前的代码上全部失败、修复后通过；全量 pytest 1264 passed、17 skipped。
- codestable：无影响（现状规格里还没有这几项）
