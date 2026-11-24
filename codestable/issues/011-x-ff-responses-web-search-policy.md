---
kind: issue
title: "Responses 联网核验改为显式开关，Context7 从自然问句取库名"
type: ff
status: closed
created: 2026-11-24
---

# Responses 联网核验改为显式开关，Context7 从自然问句取库名

合并的 #83 有三处评审意见。其一，配了 Responses 联网工具就一律发 `tool_choice=required`，并要求返回完成的 `web_search_call`：不接受 tool_choice 的中转站直接 400/422；返回正文和引用但不给工具记录的中转站，从 main 上的成功变成 quality_error；流式发了 `response.web_search_call.completed`、终态却不带工具项的回答，main 接受而 #83 拒绝。维护者定为显式开关，默认与 main 一致（原功能见 `issues/002-o-openai-responses-web-search.md`）。其二，Context7 取问句里第一个非通用词当库名，"How do I use useEffect in React?" 取到 `do`，没有 Jev 时连 Context7 返回的 React 也被拒；匹配落空还按软失败记入提供方健康，两次就让 Context7 冷却。其三，429 重试提示的共用解析缺少契约测试，补测时发现 `Retry-After: 1e12` 会让提供方冷却 1e12 秒。

- 改动：新增 `OPENAI_COMPATIBLE_REQUIRE_WEB_SEARCH`，默认 false。关闭时不发 tool_choice，也不因缺少工具记录拒绝回答，传输记录照常保留 web_search_calls，并加上 web_search_verified 和 web_search_required；开启时发 tool_choice=required，只有终态里的完成项、或终态没有否定同一 item id 的 completed 事件才算核验通过，否则 quality_error；400/422 拒绝 tool_choice 时报 parameter_error 并提示关闭该项。开启却没有 responses 模式和 web_search 工具时，保存、setup、搜索、model 和 diagnose 都报参数错误。总结请求仍不带搜索工具。Context7 库名改为候选排序：跳过疑问词和请求用语，React、Next.js 这类专有名称优先于 useEffect 这类 API 成员，介词后的词再优先；没有 Jev 时由第一个有匹配的候选决定，唯一才读。取不到名、不相关、有歧义以及 Jev 判为不相关，都记为带原因的空结果，不计入健康。带提示的限流冷却不再超过配置的冷却时长。
- 涉及：OpenAI 兼容适配器、配置校验与 setup 参数、诊断与 model 输出、App 字段、中英文消息及 macOS 副本、配置与命令参考（重新生成时只取本次条目，SpecStream 的漂移留给它自己的修复）、中英文配置指南、公开与打包两份技能参考；Context7 选库与提供方健康；#83 按常开写的测试改为覆盖两种模式。
- 验证：新增和改写的测试覆盖 JSON、非流式里的 SSE 回退和流式三种传输下的仅引用、仅完成事件、显式失败、完成事件后出现失败项、完整完成项，tool_choice 被 400/422 拒绝，默认不发、开启才发 tool_choice；英文和中文自然问句、没有库名的问句、歧义和相似包名、匹配落空不进健康；首次 429 的冷却截止时间、无效提示回退、等待不越过截止时间、超大提示截断。隔离配置下全量 pytest 1396 passed、17 skipped，剩下 6 个失败都是 SpecStream 的已知问题（test_guide、test_i18n、test_ui_api、test_ui_metadata 两项、test_ui_server），由另一项修复处理；技能双份一致。
- codestable：已同步 `spec/research-evidence.md`
