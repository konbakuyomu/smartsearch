[手册目录](../README.md) · [English](../en/cli.md)

# CLI 使用指南

全部命令、别名、嵌套子命令和参数见[完整命令参考](cli-reference.md)。

## 语言和脚本调用

CLI 默认跟随系统 locale，中文环境使用简体中文，其他环境使用英文。CLI 的保存偏好与 App 分开。

```sh
smart-search config set SMART_SEARCH_LANGUAGE zh
smart-search --lang en --help
smart-search config list --lang zh
smart-search config set SMART_SEARCH_LANGUAGE auto
```

`--lang auto|zh|en` 可放在命令前或后，也适用于多级子命令及帮助；兼容 `zh-CN` 和 `en-US`。`--` 之后的文字按原始参数处理。优先级依次为单次参数、`SMART_SEARCH_LANGUAGE` 环境变量、当前配置文件和系统 locale。单次参数不写配置，App 的语言选择也不改变这些设置。无效的显式值返回退出码 `2`；保存的偏好无法读取时回退系统语言，并在 stderr 提示。

帮助、向导和本工具的状态/错误说明使用所选语言。命令名、参数名和 JSON 字段/枚举保持不变，服务商/模型 ID、输入问题、回答与来源原文也不翻译。第三方日志保留原语言。脚本使用 `--format json`，诊断警告进入 stderr；`--version` 的格式不受语言影响。

| 退出码 | 含义 |
| --- | --- |
| `0` | 结果成功；部分成功时，限制会写在返回内容中 |
| `2` | 命令或参数错误 |
| `3` | 配置缺失或无效 |
| `4` | 网络失败 |
| `5` | 其他运行错误 |

除退出码外，还要读取 `ok`、`partial_success`、状态和证据字段。离线研究计划成功不表示已经搜索。显式联网命令、服务商测试和远程路由可能消耗付费额度；帮助、版本、本地路由和模拟 smoke 不会。

## CLI 安装

稳定版：

```powershell
npm install -g @konbakuyomu/smart-search@latest
smart-search --version
smart-search setup
```

测试版：

```powershell
npm install -g @konbakuyomu/smart-search@next
smart-search --version
```

新版 npm 包按操作系统和 CPU 架构安装自带运行时的 CLI。Python 解释器和依赖已在发布时打包；安装或首次运行不会寻找、下载或配置用户 Python。CLI 启动时隔离 Python、venv、Conda 和 PyInstaller 环境变量。

npm 包自带运行环境，不使用本机 Python、虚拟环境或 Conda。偏好 uv 的用户可从源码安装：
```sh
uv tool install git+https://github.com/konbakuyomu/smartsearch.git
```
需要固定 Python 版本时，在安装命令后加 `--python 3.13`；uv 会自行下载该版本，与本机嵌入式 Python 无关。
升级使用 `uv tool upgrade smart-search`。这种方式不经过 npm，App 的 CLI 更新入口不会管理它。

前置条件：

- 已安装 Node.js 18+ / npm。
- macOS、Windows、Linux 的 x64 / arm64 平台。Linux 需要 glibc 2.35+，不支持 Alpine/musl。
- npm 安装时保留 optional dependencies（不要使用 `--omit=optional`）。允许 `--ignore-scripts`，无需执行安装脚本。

旧的 0.1.24 及更早 npm 包仍使用 Python 安装流程；上述方式在新的二进制 npm 版本发布后生效。

## CLI 快速开始

1. 配置 provider，浏览器或终端二选一：

```powershell
smart-search ui                  # 临时的本地配置页，见「在浏览器里配置」
smart-search setup               # 或者走终端交互向导
smart-search doctor --format json
```

2. 普通快速搜索：

```powershell
smart-search search "今天有什么值得关注的 AI 新闻？" --validation balanced --extra-sources 2 --format json
```

3. 只看意图路由，不调用 provider：

```powershell
smart-search route "React useEffect API docs" --format markdown
smart-search route "请核验这个链接里的说法 https://example.com/source" --format json
```

4. 抓取关键网页正文：

```powershell
smart-search fetch "https://example.com/source" --format markdown --output evidence.md
```

5. 生成 Deep Research 计划：

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --budget standard --format json
```

6. 让 CLI 直接执行 live Deep Research：

```powershell
smart-search research "深度搜索一下最近的比特币行情" --budget deep --format markdown
```

7. 把 skill 安装给 AI 工具：

```powershell
smart-search setup --non-interactive --install-skills codex,claude,cursor,hermes
```

Skill 安装会把内置 `smart-search-cli` 写入用户级工具目录，例如 `~/.agents/skills`、
`~/.claude/skills`、`~/.cursor/skills`、`~/.hermes/skills`，以及 OpenCode 的
`~/.config/opencode/skills/smart-search-cli`。它不会初始化 Trellis、hooks、agents 或 commands。`--skills-root PATH`
是便携安装或测试时的合成 home 根目录覆盖；OpenCode 在根目录 `T` 下会写到
`T/.config/opencode/skills/smart-search-cli`。

8. 升级 CLI 后，同步已经安装到全局 AI 工具里的 skill：

```powershell
smart-search skills status --targets codex --format json
smart-search skills update --targets codex --format json
```

`setup --install-skills` 仍然保留给第一次配置使用。平时升级包以后，优先用 `skills status` 和
`skills update`；它们只检查或覆盖 `smart-search-cli` 托管文件，不会改 provider key，也不会创建
Trellis、hooks、agents 或 commands。OpenCode status 会将已发现的旧路径
`~/.opencode/skills/smart-search-cli` 作为只读 `legacy_locations` 元数据报告，绝不会自动移动或删除它。Setup 和 update 只会向规范的
OpenCode 路径写入托管内置文件，旧树和其他额外文件都会保持不变。

## 本地浏览器配置

68 个配置项堆成文字墙很难读。`smart-search ui` 会开一个临时的本地页面，按用途分好组：

```powershell
smart-search ui
```

它绑在 `127.0.0.1` 的随机端口上，打印一个带一次性 token 的地址，关掉页面就自己退出。不留常驻服务，也不用额外安装。服务端使用 Python 标准库，页面是单个 HTML 文件。

它能做什么：

- 按用途配置渠道，至少一个可用渠道即可，Jev 可选
- 所有配置项按服务商分组，密钥一律掩码显示，明文不会发给浏览器
- 每个服务商一个「测试」按钮，验证已保存的 key 是否还有效。每点一次都是一次真实 API 请求，所以不点就不测
- 哪些服务商在冷却中，以及一键解除
- 15 个 agent 目标的 skill 安装状态

常用参数：

| 参数 | 作用 |
| --- | --- |
| `--no-browser` | 只打印地址，不自动开浏览器 |
| `--port N` | 绑定固定端口 |
| `--idle-timeout SEC` | 空闲多少秒后退出（默认 `900`，`0` 表示不退出） |
| `--lang zh\|en` | 界面语言 |
| `--check` | 检查页面资源是否装好，然后退出 |

远程机器上不会自动开浏览器，转发端口即可：

```bash
smart-search ui --no-browser --port 8765
ssh -L 8765:127.0.0.1:8765 用户@主机      # 然后在本地打开打印出来的地址
```

在本地 UI 的查询页，「本次搜索服务商」默认保持「自动选择」，沿用现有选路。单次查找公开软件文档时，可选择「Parallel（公开软件文档，仅本次）」，输入如 `Python pathlib Path documentation` 的公开查询，再点击「跑一次真实搜索」并确认。请勿包含私人内容。Parallel Unified MCP 无需 API key 即可使用，但限流较低，详见 [Parallel MCP setup](https://docs.parallel.ai/integrations/mcp/quickstart)。

该选择只向 Parallel 的 `web_search` 工具发送输入的查询和固定的文档检索目标，本次不会调用 Jev 或其他服务商。现有 JSON 结果视图保留原始来源 URL 和摘录；摘录不代表已读取完整页面。空结果、工具不可用及超时会明确返回，不会切换服务商。该选择不保存，也不加入自动搜索、研究、服务商测试或 `doctor`。「看它走哪些能力」仍是自动选路的离线预览。

在 WSL 中会打开 Windows 默认浏览器；`networkingMode=mirrored` 下页面打不开时，见[在 WSL 或 Linux 上使用](troubleshooting.md#在-wsl-或-linux-上使用)。

用环境变量设置的 key 会显示为锁定且不可编辑，因为环境变量在每次读取时都覆盖 `config.json`。页面会告诉你该执行哪条 `unset`。

命令行的方式仍然可用：`smart-search setup`、`smart-search config set KEY VALUE`、`smart-search providers test PROVIDER`。

## 命令与示例

| 命令 | 简写 | 用途 |
| --- | --- | --- |
| `search` | `s` | 快速联网搜索和综合回答 |
| `route` | `rt` | 只解释需要哪些 capability，不调用 provider |
| `deep` | `dr` | Deep Research 离线计划 |
| `research` | `rs` | live Deep Research 执行 |
| `fetch` | `f` | 抓一个 URL 正文 |
| `map` | `m` | 读取站点结构 |
| `exa-search` | `exa`、`x` | Exa 来源发现 |
| `exa-similar` | `xs` | 从一个 URL 找相似页面 |
| `zhipu-search` | `z`、`zp` | 智谱 Web Search API |
| `zhipu-mcp-search` | `zmcp-search` | 智谱 Coding Plan MCP `web_search_prime` |
| `zhipu-mcp-reader` | `zmcp-reader` | 智谱 Coding Plan MCP `webReader` |
| `zhipu-mcp-search-doc` | `zmcp-doc` | 通过 zread MCP 搜开源仓库文档 |
| `zhipu-mcp-repo-structure` | `zmcp-tree` | 通过 zread MCP 读仓库结构 |
| `zhipu-mcp-read-file` | `zmcp-file` | 通过 zread MCP 读单个仓库文件 |
| `anysearch-domains` | `as-domains` | 实验 AnySearch 域名/能力发现 |
| `anysearch-search` | `as-search`、`as` | 实验 AnySearch 垂直/通用搜索 |
| `anysearch-extract` | `as-extract` | 实验 AnySearch URL 抽取 |
| `anysearch-batch` | `as-batch` | 实验 AnySearch 批量搜索，最多 5 条 |
| `sciverse-catalog` | `sv-catalog` | 实验 Sciverse 学术字段 catalog |
| `sciverse-search` | `sv-search`、`sv` | 实验 Sciverse 结构化学术检索 |
| `sciverse-semantic` | `sv-semantic` | 实验 Sciverse 语义论文检索 |
| `sciverse-read` | `sv-read` | 用 `doc_id` 读取 Sciverse 正文片段 |
| `sciverse-relations` | `sv-relations` | 用 `unique_id` 查询 Sciverse 引用/参考文献/相关工作 |
| `context7-library` | `c7`、`ctx7` | 查 Context7 库候选 |
| `context7-docs` | `c7d`、`c7docs`、`ctx7-docs` | 抓 Context7 文档 |
| `route-calibrate` | `route-cal`、`rcal` | 退役兼容命令，不发远程请求 |
| `doctor` | `d` | 配置和连通性检查 |
| `setup` | `init` | 配置向导 |
| `config` | `cfg` | 本机配置读写 |
| `model` | `mdl` | 查看显式 provider 模型；修改请用 `config set XAI_MODEL` 或 `OPENAI_COMPATIBLE_MODEL` |
| `providers` | `prov` | 查看（`status`）或清除（`reset`）可选 provider 的失败冷却记录 |
| `smoke` | `sm` | provider 路由冒烟测试 |
| `regression` | `reg` | 离线回归测试 |

`smoke` 输出会给出 `status`（`healthy`、`degraded` 或 `failed`）和明确的 `skipped_cases`。健康或降级报告仍为 `ok: true`、退出码 `0`；只有失败才非零。

`search` 返回 `error_type: "timeout"` 时，先查看 `timeout_phase` 和 `provider_attempts`。同一条搜索最多再试 1 次，并加上 `--extra-sources 1`；再次超时就改用 `exa-search` 等 source-first 命令，抓取相关页面，并用 `source_mode: "fallback"` 或等价文字标注证据模式。调用 smart-search 的 Agent 必须把命令执行超时设得比 smart-search 的总时限长至少 30 秒（默认 300 秒时至少 330 秒），或放到后台执行，否则 Agent 可能在 smart-search 返回结构化结果前将它终止。

示例：

```powershell
smart-search search "query" --validation balanced --extra-sources 3 --timeout 300 --format json --output result.json
smart-search route "React useEffect API docs" --format markdown
smart-search research "query" --budget deep --fallback auto --format json --output research.json
smart-search search "query" --stream --format json
smart-search search "query" --no-stream --format json
smart-search search "nba战报" --format content
smart-search exa-search "OpenAI Responses API documentation" --include-domains platform.openai.com developers.openai.com --num-results 5 --include-text --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/reactjs/react.dev" "useEffect cleanup" --format json
smart-search zhipu-search "今天国内 AI 新闻" --search-engine search_pro_sogou --count 5 --format json
smart-search zhipu-mcp-search "今天国内 AI 新闻" --count 5 --format json
smart-search zhipu-mcp-reader "https://example.com/source" --format json
smart-search zhipu-mcp-search-doc "owner/repo" "install" --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --param type=cve --param value=CVE-2024-3094 --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --max-length 12000 --format json
smart-search sciverse-search "transformer retrieval" --year-from 2020 --page-size 5 --format json
smart-search sciverse-relations "unique-id-from-search" --relation CITATIONS --format json
smart-search exa-similar "https://example.com/source" --num-results 5 --format json
smart-search fetch "https://example.com/source" --format markdown --output page.md
smart-search map "https://docs.example.com" --instructions "Find API reference pages" --max-depth 1 --limit 50 --format json
smart-search doctor --format markdown
smart-search providers status --format markdown
smart-search providers reset zhipu --format json
smart-search smoke --mock --format json
smart-search regression
```

## 不联网的首次检查

`route` 只做能力路由判断，一个 provider 都不会调，所以在什么都没配的新装环境里也能跑通，退出码 `0`：

```powershell
smart-search route "React useEffect cleanup function docs" --format markdown
```

```text
# Intent Route

Status: OK
Query: `React useEffect cleanup function docs`
Mode: `jev`
Executed search: NO
Required capabilities: `docs_search`
Confidence: `0.82`
Engines: `rules`
Degraded: YES
Executed search: NO; provider_selection: not_executed

## Reasons
- rules matched docs/API/library terms
```

同一条命令换成 `--format json`，就是 agent 实际读到的东西：

```json
{
  "ok": true,
  "query": "今天 OpenAI 发布了什么",
  "executed_search": false,
  "provider_selection": "not_executed",
  "required_capabilities": ["docs_search", "web_search"],
  "confidence": 0.84,
  "router_engines_used": ["rules"],
  "reasons": [
    "rules matched docs/API/library terms",
    "rules matched current/locale/news terms"
  ]
}
```
