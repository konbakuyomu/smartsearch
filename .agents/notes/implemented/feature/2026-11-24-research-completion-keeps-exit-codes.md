# Agent Note: 研究的答案状态放进 completion，不改退出码

Status: implemented

## Problem

`konbakuyomu/smartsearch#83` 给 research 加了 `completion`（retrieval、evidence、synthesis、answer），用来区分「检索成功」和「答案完整」，同时让单项实质缺口（分数达到 0.5）否决全局充分性。复核在离线用例里发现：

- 默认 deep 用 strict。同样的评分，退出码在 main 上是 0，PR 头上变成 4。脚本和 Agent 调用方按退出码分支，结果会静默改变。
- standard 研究总结失败时 ok=true、退出码 0、answer=partial，但 CLI Markdown 和桌面 App 都只显示「成功」，用户看不出答案不完整。
- 公开和打包的技能都没教调用方去读 `completion.answer`。

## Decision

ok 和退出码保持 main 的含义；答案是否完整只由 completion 表达，并在人能看到的地方明示：

- `jev.assess_evidence` 另给 `global_sufficient`，只看全局门槛；strict 的 ok 和退出码按它判断，和引入单项缺口之前一致（达到门槛就是 0，未达到就是 evidence_error，退出码 4）。
- 单项缺口仍让 sufficient=false、研究继续补缺，completion.evidence 降为 degraded、answer 降为 partial。
- `completion.reason` 取 cancelled、no_read_evidence、synthesis_failed、synthesis_decision_failed、synthesis_decision_skipped、evidence_gaps 之一，按这个顺序取第一个成立的。
- ok=true 且 answer=partial 时，CLI Markdown 的状态行写「成功（答案不完整：<原因>）」/「OK (answer partial: <reason>)」；App 的 display_text 用同一份 Markdown，任务状态仍是完成。
- 两份 smart-search-cli 技能告诉调用方：要完整答案就读 `completion.answer`、`reason`、`gap_check` 和 `synthesis`，不只看 ok。

现行行为写在 `codestable/spec/research-evidence.md`「完成与失败」一节。

## Alternatives considered

- **沿用 #83：单项缺口直接让 strict 失败，退出码 4**：答案不完整时调用方一定察觉，最保守。但同样的证据，升级后退出码会变，依赖退出码 0 的脚本会突然报错；而 deep 默认就是 strict，影响面是所有 deep 用户。否掉。
- **新增退出码表示「检索成功、答案不完整」**：机器可读，也不和现有码冲突。可是退出码是 CLI、App 和技能共同依赖的契约，新增一个码要同时改三方，旧调用方会把它当成未知错误。completion 字段已经能把这个信息交给需要的人。否掉。
- **只加 completion，不改展示**：改动最小。但 App 和终端用户只看状态行，partial 会被当成成功。否掉。

## Consequences

- **收益**：升级不改变任何调用方按退出码的分支；需要完整答案的调用方有明确字段可读；终端和 App 用户能直接看到「答案不完整」。
- **代价与已知上限**：只看退出码的调用方仍然察觉不到 partial，要靠技能文档引导它们读 completion。哪天需要让 CI 在答案不完整时失败，就得重开这个决定，比如加一个显式参数。

## Verification

- `tests/test_research_completion.py` 覆盖 CLI 和桌面 worker 的完成、部分、失败、取消四种结果，以及 strict 下单项缺口时退出码仍为 0。
- `codestable/issues/012-x-ff-research-completion-fixes.md` 记录复现过程和改动。
