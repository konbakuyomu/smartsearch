---
kind: issue
title: "OpenAI 搜索模型的引用不再漏读，回答不再被当成来源吞掉"
type: ff
status: closed
created: 2026-11-01
---

# OpenAI 搜索模型的引用不再漏读，回答不再被当成来源吞掉

OpenAI 兼容通道走 Chat Completions 用 `gpt-5-search-api` 时，引用在 `message.annotations` / `delta.annotations` 的 `url_citation` 里，Smart Search 只读 `citations`，结构化来源为空。模型又在每句或每条末尾写 `([站点](url))`，拆分器把这些行当成“尾部链接块”，回答被整段或大半吞掉，搜索仍报 ok。2026-11-01 用官方 key 跑 0.1.32 的 5 次 balanced 搜索：3 次只剩来源列表，1 次来源为空。现在两处都修了。

- 改动：`src/smart_search/providers/openai_compatible.py` — 非流式和流式都读嵌套的 `url_citation`，和 Responses 路径一样追加 `sources(...)`；`src/smart_search/sources.py` — 以括号引用结尾的句子不再算“只有链接的行”，真正的尾部链接列表照旧拆出。
- 验证：新增 6 个用例，用的是真实回答原文；全量 pytest 1248 passed、17 skipped。用官方 key 实录的 6 个 `gpt-5-search-api` 回答回放：修前回答保留 0%–100%、来源 0–2 个（标题只有域名），修后回答全部保留、来源 1–4 个且带页面标题。
- codestable：无影响（现状规格里还没有来源解析这一项）

顺手发现：`tests/test_sources.py` 单独运行会撞上 `smart_search.utils` 的循环导入，和 provider 测试一起跑才正常 — 不在本次范围。Sol / Astra 联网的适配见 `issues/002-o-openai-responses-web-search.md`。
