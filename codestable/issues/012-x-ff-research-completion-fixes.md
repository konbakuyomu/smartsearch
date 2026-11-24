---
kind: issue
title: "研究调度与完成状态修正：重复读取、限定来源、交付预算、退出码与取消"
type: ff
status: closed
created: 2026-11-24
---

# 研究调度与完成状态修正：重复读取、限定来源、交付预算、退出码与取消

合并 #83 之后，复核在离线受控用例里复现了六处问题。本地路由给同一 URL 选了 Tavily、Firecrawl 两个读取名额时，Tavily 返回空正文，Firecrawl 被调用两次（main 是各调一次）；换读取器重试时，回退链也可能回到已用过的提供方。“Only use <URL>”没被识别成限定来源，“Use only official sources”反而会把研究锁到问题里出现的某个 URL。可选过滤用完发现阶段的预算后，Jev 被整体判为不可用：1.2 秒的用例里还剩约 0.48 秒，却跳过了自动总结判断，同时报 completion.answer=complete。单项缺口否决全局充分性以后，默认 deep（strict）下同样的评分会把退出码从 0 变成 4。standard 研究总结失败时 ok=true、退出码 0、answer=partial，CLI Markdown 和 App 却只显示“状态：成功”。只发现了网址就取消时，partial_success 从 main 的 true 被改成 false，降级原因还声称返回了摘录。公开和打包技能也没告诉调用方要看 completion.answer。

- 改动：`src/smart_search/service.py` 的抓取回退链接收已用读取器集合；`src/smart_search/jev_search.py` 在一次研究内按 URL 记录已用读取器，同轮名额、回退链和后续轮次都不重复调用，跳过的名额不记尝试；限定来源改为必须落在 URL 上（限定词后直接跟 URL 或一组 URL、URL 后跟 only / 为唯一来源、指代语和“不要替换”指全部 URL）；过滤到点超时不再停用 Jev，过滤后的重新评估与交付阶段照常用预留时间；auto 在有证据、有总结模型时跳过决策记为 partial；completion 增加 reason；取消时如实说明返回内容并保留 partial_success。`src/smart_search/jev.py` 的评估另给 global_sufficient，strict 的 ok 按它判断，退出码映射与 main 相同。`src/smart_search/cli.py` 的研究报告状态行在答案不完整时写成「成功（答案不完整：原因）」，App 的 display_text 用同一份 Markdown；新增文案的中英文对照写进 `src/smart_search/assets/i18n/messages.json` 并同步 macOS 的 Localization.json。两份 smart-search-cli 技能（SKILL.md、cli-core、deep-research-mode）补上“看 completion.answer、reason、gap_check、synthesis，不只看 ok”。
- 验证：新增 `tests/test_research_scheduling.py` 与 `tests/test_research_completion.py` 共 36 项离线回归（CLI 和桌面 worker 覆盖完成、部分、失败、取消四种结果），在合并基线 4b32e1d 上其中 22 项失败，修复后全部通过；另在 main 1969e4f 上确认单项缺口用例的退出码本来就是 0。全量 pytest：1344 passed、17 skipped、6 failed，失败的 6 项是 SpecStream 引起、由另一处修复的已知用例（test_guide、test_i18n、test_ui_api、test_ui_metadata ×2、test_ui_server），本次没有新增失败；技能一致性检查 9 个文件一致。
- codestable：已同步 `spec/research-evidence.md`
