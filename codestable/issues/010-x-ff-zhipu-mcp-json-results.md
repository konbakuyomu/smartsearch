---
kind: issue
title: "智谱 MCP 搜索按 JSON 解析结果，不再只出一条坏链接（GitHub issue #84）"
type: ff
status: closed
created: 2026-11-24
---

# 智谱 MCP 搜索按 JSON 解析结果，不再只出一条坏链接（GitHub issue #84）

zhanglin9833 报告：`web_search_prime` 返回的是一行 JSON 字符串（Coding Plan 端点外面还多包一层引号），旧代码把它当 Markdown 逐行解析，只得到 1 条记录，URL 和标题后面拼着 `","content":"…`，后续抓取用不了。现在先按 JSON 解析（最多解两层），映射成正常结果；只有不像 JSON 的旧式文本才走 Markdown。

- 改动：`src/smart_search/providers/zhipu_mcp.py` — 新增 `_parse_json_results`，只给 `web_search_prime` 用：`link`（或 `url`）须是有效的 http(s) 地址，`content→description`、`publish_date→published_date`、`media→source`，保留 `refer`，与 `providers/zhipu.py` 的字段一致；空数组返回零条；损坏的 JSON 或未知结构报 `parse_error`，不再拼出假结果；Markdown 解析的两处 URL 正则遇到引号和反斜杠就停。两条新错误信息进了 `assets/i18n/messages.json` 和 macOS 的同一份副本。
- 验证：`tests/test_zhipu_mcp_provider.py` 新增 9 个用例（单层/双层 9 条、坏项与空白 link、空数组、损坏与未知 JSON、双层编码的错误、Markdown 与引号边界、Zread 仍走文本、JSON 包着的 Markdown、从普通搜索到 Jev 归一化拿到完整原 URL）；还原修复后 JSON 相关用例全部失败。全量 pytest 只剩 SpecStream 合入带来的 6 项已知失败，由 009 处理。
- codestable：无影响（现状规格没有写到智谱 MCP 的结果格式）

顺手发现：`ZhipuMCPProvider.web_search` 丢弃 `count`，智谱返回几条就给几条 — 已有行为，不在本次范围。
