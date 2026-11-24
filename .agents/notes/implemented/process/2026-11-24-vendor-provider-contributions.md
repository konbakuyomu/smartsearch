# Agent Note: 服务商本人提交自家接入的 PR 按统一标准接收

Status: implemented

## Problem

2026-11 先后来了两个服务商本人提交的 PR：

- `konbakuyomu/smartsearch#85`（Parallel 员工）：在本地 Web UI 查询页加一个固定的「Parallel」下拉项，走匿名端点；
- `konbakuyomu/smartsearch#86`（SpecStream 创始人）：新增搜索加抓取，说明里写的是接在回退链末尾。

两个 PR 都自己披露了身份，单测写得也认真，但评审发现的问题出在项目层面，单测看不出来：

- #85 让零配置用户的 `providers status` 和 `doctor` 常驻「parallel configured: true」；为了这一个入口，还在 `service.py`、`jev_search.py`、`ui_api.py`、`index.html` 四层加了 `foreground_*` 一整套特例，页面和接口白名单都写死成 auto/parallel 两项。
- #86 声称排在末位，实际在 `PROVIDER_PROFILES` 和抓取回退里插在 tinyfish 前面，本地规则选路会先选它；Jev 用来选路的描述里写着 "verified source excerpts"；只跑了几个挑出来的测试文件，全量测试有 6 项失败。

没有成文标准时，每个厂商 PR 都要从头争论一遍；厂商之间也会互相攀比曝光位置。

## Decision

接收标准写在仓库根目录的 `CONTRIBUTING.md`，中英两份，对每家服务商一视同仁：

- 必须披露提交者和服务商的关系，以及是否借助 AI 准备。
- 用户自带 key，并且有 `*_ENABLED` 开关。没有用户凭据时 `_provider_configured()` 必须返回 false，`providers status`、`doctor` 和界面都不能显示为已配置。不接受专属入口、默认推荐或界面上的固定位置。
- 只接在所属能力回退链的末尾。`PROVIDER_PROFILES`、`RESEARCH_PROFILE_ORDER`、抓取回退和能力状态四处的顺序必须一致。Jev 仍然按描述在已配置的服务商里公平选择，文档照实写，不承诺「永不首选」。
- `provider_descriptions.py` 的描述保持中立，写清每项操作适合什么、不适合什么；不写代码证明不了的话（「已核验」「最准确」、和别家比较）。现有条目的 "Best for …" 只是说明用途，可以沿用。
- 接线要完整：探针覆盖声明的全部能力，遵守 `ssl_verify`，带凭据的请求不跟随重定向，覆盖异常路径的测试，文档、技能两份副本和 `codestable/` 都要跟上；全量测试必须通过。
- 维护者用免费额度或临时测试 key 实测并记下日期和结果之前，服务商标为 `experimental`。
- 免 key 或匿名端点只能做成按名显式调用的命令（参照 sciverse 的专用命令）：每次经用户确认，只发送本次查询，不进入自动选路。
- 提交者留接口变更的联系人。上游失效 30 天没人修，维护者可以降级、移出回退链或删除。

据此：#85 按现形态拒绝，邀请对方按第 7 条重提；#86 由维护者合入并补齐阻断项，先标 `experimental`，等对方提供测试 key 再转正。

## Alternatives considered

- **逐个 PR 个案评审，不立成文规则**：最灵活，不给贡献者设门槛。但 #85 和 #86 暴露的问题（零配置显示已配置、声明顺序和实际不符、营销式描述）都是结构性的，下一家很可能重犯；没有规则时，拒绝其中一家像是厚此薄彼。否掉。
- **接受 #85 的前台单次选择，只改掉 `configured=true`**：astra 第一轮支持这个方案。理由是匿名端点零门槛，有试用价值，逐次确认也解决了查询外发的授权问题。但页面和接口白名单写死单一厂商的格局不变，接第二家还得再改核心四层；`smart-search ui` 本来就定位为临时配置页，主力入口是 CLI 和 App。第二轮两位评审一致否掉。
- **禁止厂商本人提交自家服务商**：中立性最强。可是最了解接口的人正是厂商自己，项目也一直靠社区补服务商；有披露和统一门槛就够了。否掉。
- **厂商 PR 一律默认关闭，连 Jev 都不让选**：不做公平选路，只在规则回退时兜底。这需要新增一套降权机制，而用户主动配了 key，本身就表示愿意用它。否掉；真有需要时再单独评估。

## Consequences

- **收益**：评审有成文依据，拒绝和要求修改时可以直接引用条款；新服务商的实际顺序和声明一致；零配置用户看不到任何厂商的「已配置」。
- **代价与已知上限**：门槛变高，小厂商可能不愿意提供测试 key，`experimental` 标签可能长期挂着。第 3 条依赖 Jev 只看中立描述选路，以后如果出现按厂商降权的需求，要重开这个决定。

## Verification

- `CONTRIBUTING.md` 的「Adding a provider you work for」节就是这份规则的现行文本。
- SpecStream 按这份规则合入：`codestable/issues/` 的 009 号记录写明补齐的阻断项，`tests/test_specstream_provider.py` 钉住顺序、重定向和脱敏。
