# Agent Note: Responses 联网执行核验默认关闭，用 OPENAI_COMPATIBLE_REQUIRE_WEB_SEARCH 显式打开

Status: implemented

## Problem

`konbakuyomu/smartsearch#83` 想解决一个真问题：Responses 主搜索可能返回带引用的回答，模型其实没有调用 web_search。为此 PR 在配置了联网工具时一律发送 `tool_choice=required`，并且要求至少一个 `web_search_call` 状态为 completed，否则报 `quality_error`。复核找到三种会因此变坏的情况：

- 不接受 `tool_choice` 的中转站返回 400/422，原本能用的主搜索直接失败；
- 接受请求、返回正文和引用、但不回传工具项的中转站，从 main 上的成功变成 `quality_error`；
- 流里有带 id 的 `response.web_search_call.completed` 事件，终态却省略了工具项：main 接受，PR 拒绝。

这些中转在线上具体有哪几家，无法实测确认；但兼容通道的用户大多经中转访问。

## Decision

- 新增布尔配置 `OPENAI_COMPATIBLE_REQUIRE_WEB_SEARCH`，默认 false。
- **关闭时**：请求和 main 一样，不发 `tool_choice`，也不因缺少工具项拒绝回答。传输记录照样保留观察到的 `web_search_calls`，另给 `web_search_verified` 和 `web_search_required`，调用方能看出「工具执行未核实」。
- **打开时**：发送 `tool_choice=required`，并要求有执行证据。终态输出里状态为 completed 的 `web_search_call` 算；流式的 `response.web_search_call.completed` 事件也算，除非终态里同一 item id 是别的状态。缺失或失败报 `quality_error`。接口以 400/422 拒收时报 `parameter_error`，提示关闭此项。
- 打开它的前提是 `OPENAI_COMPATIBLE_API_MODE=responses` 且 `OPENAI_COMPATIBLE_TOOLS` 含 `web_search` 或 `web_search_preview`；组合不对时，保存、setup、搜索、`model` 和诊断都报参数错误，和现有的工具与接口模式校验一致。
- 总结、fetch、describe、rank 和连接测试照旧不带搜索工具，也不带强制选择项。

这是 [OpenAI 兼容通道用开关发送 Responses 的 web_search 工具](2026-11-01-openai-compatible-responses-web-search.md) 的后续：那篇定的是「默认不发工具，显式打开才发」，这篇沿用同一原则处理执行核验。

## Alternatives considered

- **沿用 #83，一律强制并核验**：最能防止「没搜就答」，#83 作者在自己的 Sol + Responses 环境里也实测通过（`docs/validation/responses-research-completion.md`）。但会让一部分原本能用的中转用户升级后直接失败，而这一部分人有多少无法实测。和 11-01 那篇「默认行为不变，现有中转用户无感」的承诺冲突。否掉。
- **按地址判断，只对 `api.openai.com` 强制**：官方用户零配置就能得到核验。可是很多人经中转访问 OpenAI 模型，换中转时同一份配置的行为会突变；11-01 已因同样的理由否掉按地址分支。否掉。
- **只记录、不提供强制选项**：最简单，不加配置项。但需要确定「真的搜过」的人（比如用官方 key 做研究）就没有办法让没搜就答的回复直接失败。否掉。
- **只发 `tool_choice`，不核验返回**：能提高官方端点调用工具的概率。但仍挡不住「带引用却没搜」，不发和发的中转兼容风险也一样。否掉。

## Consequences

- **收益**：现有中转用户升级后行为不变；需要强保证的人有明确开关；每次调用都能从 `web_search_verified` 看出这一点有没有核实。
- **代价与已知上限**：默认情况下，「带引用但没搜」的回答仍会被接受，只是标了未核实。多一个配置项，App、setup 和文档都要讲清它依赖接口模式和工具。哪天能确认主流中转都支持 `tool_choice` 并回传工具项，可以重新考虑默认打开。

## Verification

- `tests/test_openai_compatible_provider.py` 覆盖两种模式下的 JSON 和 SSE 返回：拒收参数、只有引用、只有 completed 事件、明确失败、完整工具项，以及默认请求不带 `tool_choice`。
- `codestable/issues/011-x-ff-responses-web-search-policy.md` 记录改动范围；现行行为写在 `codestable/spec/research-evidence.md`「Responses 主搜索」一节。
