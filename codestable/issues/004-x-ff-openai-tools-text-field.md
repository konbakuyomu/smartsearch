---
kind: issue
title: "联网工具改成普通文本框：Windows App 的下拉框显示不出“空”，也存不进 web_search"
type: ff
status: closed
created: 2026-11-01
---

# 联网工具改成普通文本框：Windows App 的下拉框显示不出“空”，也存不进 web_search

0.1.33 里 `OPENAI_COMPATIBLE_TOOLS` 带了 `choices`。Windows App 把所有带选项的字段画成封闭下拉框：已保存的值不在选项里（空值永远不在）就预选第一项，并把这次预选当作“没改”（`BuildFieldEditor` 用控件刚建好时读到的值当初始值，`HasDraftChange` 拿它比较）。结果真实为空的联网工具显示成 `web_search`；想选 `web_search` 时和初始显示相同，不会保存，只有 `web_search_preview` 存得进去。2026-11-01 在维护者的 Windows 电脑上装好 0.1.33 后，用 App 看到并确认：下拉里只有这两项，没有“空”。只改页面上别的字段再保存不会误写这一项。macOS 的选择器在值不在选项里时会多出“当前：未设置”，网页界面对 csv 字段本来就是文本框，所以只有 Windows 受影响。

- 改动：`src/smart_search/ui_metadata.py` — 去掉该字段的 `choices`，保留占位符 `web_search`，帮助文字补上“留空表示不发送工具”；`tests/test_ui_metadata.py` — 钉住这个字段是文本框，并新增通用守卫：带 choices 的字段默认值必须是其中一项（已有的 `XAI_TOOLS` 记为例外）；`docs/guide/*/configuration-reference.md` 重新生成。
- 验证：新增 2 个测试，还原修复后都会失败；全量 pytest 1266 passed、17 skipped；App 收到的字段数据 `choices` 为空、占位符 `web_search`，和“备用模型”同一形态。
- codestable：无影响（现状规格里还没有这一项）

顺手发现：`XAI_TOOLS` 在 Windows App 里有同样的预选问题（默认值是两个工具的组合，显示成第一项）— 已有行为，不在本次范围。
