<div align="center">

<img src="assets/branding/smart-search.png" alt="Smart Search" width="112">

# smart-search

**让 AI 和终端自己上网查资料，从一次搜索做到一份深度研究**

简体中文 | [English](README.md)

[![npm](https://img.shields.io/npm/v/@konbakuyomu/smart-search?label=npm&logo=npm&color=CB3837)](https://www.npmjs.com/package/@konbakuyomu/smart-search)
[![downloads](https://img.shields.io/npm/dm/@konbakuyomu/smart-search?label=downloads&logo=npm)](https://www.npmjs.com/package/@konbakuyomu/smart-search)
[![CI](https://github.com/konbakuyomu/smartsearch/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/konbakuyomu/smartsearch/actions/workflows/ci.yml)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![node](https://img.shields.io/badge/node-%3E%3D18-5FA04E?logo=node.js&logoColor=white)](package.json)
[![python](https://img.shields.io/badge/python-%3E%3D3.10-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![stars](https://img.shields.io/github/stars/konbakuyomu/smartsearch?style=flat&logo=github)](https://github.com/konbakuyomu/smartsearch/stargazers)

</div>

## 这是啥

AI 助手自己不会上网。你问它今天出了什么新闻、某个库的新 API 怎么写，它只能拿训练时记下的旧内容回答，有时候干脆编一个。

smart-search 替它去查，把查到的网页原文带回来。有两种用法。

- **桌面 App**：下载安装包，打开窗口，填完 Key 就能搜索、读网页，也能跑深度研究。不用装 Python 和 Node。
- **命令行 CLI**：装到系统里，Claude Code、Codex、Cursor 这类 AI 工具通过 skill 自动调用它。

两边共用同一份配置和同一套搜索内核，App 关着的时候 CLI 照样能用。

搜索能力来自第三方服务商，Key 要你自己申请，smart-search 不自带搜索额度。

## 怎么装

### 桌面 App

四个安装包都在 [v0.1.20 发行页](https://github.com/konbakuyomu/smartsearch/releases/tag/v0.1.20)，按自己的机器挑一个。

| 你的机器 | 下载哪个 |
| --- | --- |
| Windows（Intel / AMD） | [win-x64 安装器](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-win-x64-Setup-unsigned-test.exe) |
| Windows（ARM64） | [win-arm64 安装器](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-win-arm64-Setup-unsigned-test.exe) |
| macOS（M 系列芯片） | [macos-arm64 磁盘映像](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-macos-arm64-unsigned-test.dmg) |
| macOS（Intel 芯片） | [macos-x86_64 磁盘映像](https://github.com/konbakuyomu/smartsearch/releases/download/v0.1.20/SmartSearch-0.1.20-macos-x86_64-unsigned-test.dmg) |

安装包没有签名，macOS 也没有公证，所以系统会拦一下。Windows 弹 SmartScreen 时点「更多信息 → 仍要运行」，macOS 提示「无法验证开发者」时去「系统设置 → 隐私与安全性」点「仍要打开」。想核对文件有没有被改动，发行页的 `SHA256SUMS.txt` 里有每个包的哈希。

Windows x64 已经在真机上走完了从安装到卸载的整个流程，日常使用也跑过。macOS 和 Windows ARM64 的包由 CI 构建，实机验收还没做完。

### 命令行 CLI

```bash
npm install -g @konbakuyomu/smart-search@latest
smart-search --version
```

需要 Node.js（npm）和 Python 3.10 以上。安装过程会自己建一个独立的 Python 运行环境，之后你只用 `smart-search` 这一个命令。

## 怎么配置

配置就是填 API Key。三种能力各配一个 Key，日常就够用了。

| 能力 | 用来干嘛 | Key 去哪申请（任选一个） |
| --- | --- | --- |
| 主搜索 | 提问，拿到带来源的答案 | [xAI](https://console.x.ai/team/default/api-keys)，或任何 OpenAI 兼容接口（含中转站） |
| 文档检索 | 查库、框架、API 的官方文档 | [Context7](https://context7.com/)、[Exa](https://dashboard.exa.ai/api-keys) |
| 网页读取 | 把指定链接的正文抓回来 | [Tavily](https://app.tavily.com/home)、[Jina](https://jina.ai/)、[Firecrawl](https://www.firecrawl.dev/app/api-keys) |

常搜中文新闻和政策的话，再加一个[智谱 Web Search](https://open.bigmodel.cn/usercenter/apikeys) 会顺手很多。另外几家服务商都是可选的，列在[完整参考](docs/reference.zh-CN.md#api-和-key-申请入口)里。

**在 App 里配**：打开服务商页，填地址、Key 和模型，先测试草稿再保存。密钥框留空表示保留旧值。概览页会显示三种能力齐了没有。

**在浏览器里配**（CLI 用户）：

```bash
smart-search ui
```

它在 `127.0.0.1` 上开一个随机端口的临时页面，URL 带一次性 token，关掉标签页就自己退出。68 个配置项按服务商分好组，密钥打码显示，每个服务商有一个「测试」按钮。点一次测试就发一次真实请求，会算进服务商的用量，不点就不发。

终端向导 `smart-search setup` 效果一样。

**配完体检一下**：

```bash
smart-search doctor --format markdown
```

它打码显示当前配置，告诉你三种能力齐了没有、哪个 Key 连不上。

## 怎么用

### 用 App

App 有六个页面，常用的是这四个。

- **概览**：配置缺什么，下一步该配什么
- **搜索与研究**：搜索、读网页、查文档、生成离线计划或者跑在线研究，结果可以复制导出
- **活动**：正在跑哪一步、走的哪个服务商、花了多久、最后成没成
- **AI 接入**：查看 CLI 路径和版本，复制调用方式，选择把 skill 装到哪些工具

剩下两个页面，服务商页在上面那节讲过，设置与关于页管配置目录、主题和更新检查。细节见[桌面端使用说明](docs/desktop.md)。

### 用命令行

一个 Key 都没配的时候，这条也能跑通，它只判断一句话该走哪种搜索，不调任何服务商：

```bash
smart-search route "React useEffect 清理函数怎么写" --format markdown
```

配好之后，日常用得上的是这五条：

```bash
smart-search search "今天有什么重要的 AI 新闻" --format markdown        # 搜索并给出答案
smart-search fetch "https://example.com/post" --format markdown         # 抓这个链接的正文
smart-search deep "比特币最近的行情" --format markdown                  # 只拆解问题给计划，不联网
smart-search research "比特币最近的行情" --budget deep --format markdown # 联网跑完整研究流程
smart-search doctor --format markdown                                   # 体检
```

`--format markdown` 给人看，`--format json` 给程序读。完整命令表在[完整参考](docs/reference.zh-CN.md#常用命令)里。

### 让 AI 工具自动调用

```bash
smart-search setup --non-interactive --install-skills codex,claude,cursor
```

这会把 `smart-search-cli` skill 写进对应工具的用户目录，比如 `~/.claude/skills`。之后在 Claude Code 里正常提问，它需要查资料时会自己调 smart-search。支持 15 个工具目标，`smart-search skills status --format json` 能列全。

升级 CLI 之后同步一次 skill：

```bash
smart-search skills update --targets codex,claude,cursor --format json
```

## 卡住了怎么办

| 遇到的情况 | 先试这个 |
| --- | --- |
| `doctor` 报 `config_error` | `smart-search setup` 重新填，再跑一次 `doctor` |
| 搜索卡住不返回 | `smart-search diagnose openai-compatible --format markdown` |
| 搜索太慢 | 调小 `--extra-sources`，把大问题拆成几个小问题 |
| 某个服务商一直失败 | `smart-search providers status --format markdown` 看是不是进了冷却，用 `smart-search providers reset <名字>` 清掉 |
| 不确定装好没有 | `smart-search --version` 和 `smart-search regression` |

装 App 不会覆盖已有配置，卸载 App 也会保留配置、研究证据和导出结果。

## 还想看什么

| 想找的东西 | 去哪看 |
| --- | --- |
| 全部命令、服务商参数、路由规则、深度研究细节 | [完整参考](docs/reference.zh-CN.md) |
| 桌面端的页面、活动、更新和卸载 | [桌面端使用说明](docs/desktop.md) |
| JEV 语义路由和过滤 | [Jev routing](docs/jev-routing.md) |
| 这一版改了什么 | [v0.1.20 发行说明](https://github.com/konbakuyomu/smartsearch/releases/tag/v0.1.20) |

## 致谢

感谢 [LINUX DO](https://linux.do/) 社区的反馈和讨论。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=konbakuyomu/smartsearch&type=Date)](https://www.star-history.com/#konbakuyomu/smartsearch&Date)

## License

MIT
