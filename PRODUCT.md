# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

Windows 和 macOS 使用原生桌面界面，保留系统控件和交互习惯。既有 Windows/macOS 原生界面基线沿用工程师实测记录；后续变更按对应提交单独验证。

## Stack

Windows：WinUI 3 / C#。macOS：SwiftUI / Swift。两端共用现有 Python 搜索业务核心，通过本机私有后端进程的版本化 JSON 协议通信。现有 `smart-search` CLI 继续直接调用同一核心。

## Users

- 普通用户：通过 App 配置服务、测试连接、安装独立 CLI 和 Agent Skills，不要求了解运行环境。
- 开发者及 AI 工具使用者：从终端或智能体调用独立 CLI，日常使用不依赖 App。

## Product Purpose

App 是 Smart Search 配置器：配置服务、显式测试、帮助安装和更新独立 CLI 与 Agent Skills。日常搜索和研究通过终端或 Agent 调用 CLI；关闭、更新或卸载 App 后仍能使用。App 默认进入配置，只有配置、测试、CLI 与 Skills、设置四页。

## Positioning

同一套搜索与配置规则支持原生 App 和 CLI。App 不自行重算服务商能力、密钥是否有效、回退或冷却结果；业务事实由共享 Python 核心提供。

## Operating Context

- 运行于用户自己的 Windows 或 macOS 桌面会话，本地优先。
- 测试结果、错误和取消操作在当前页面呈现，不提供常驻活动工作台。
- 第三方服务商仍使用现有 URL、Key、模型与网络配置；启动 App 和读取状态不等于发起计费探针。
- App 私有配置/测试辅助进程自带依赖，不作为公开 CLI 或加入 PATH。外部 CLI 安装在 App 目录之外；原配置不会因安装 App 而被静默迁移或覆盖。

## Capabilities and Constraints

- 桌面测试只提供搜索、网页读取、Context7 库与文档、路由预览、离线冒烟；完整搜索与研究能力保留在公开 CLI。
- 配置读取、有效值、环境变量来源、保存和草稿测试统一处理。
- Skills 勾选后用一个动作完成来源检查、备份及安装/更新；相同内容明确显示无变化。CLI 安装在内部完成依赖检测与验证。
- 保持 CLI 命令、参数、别名、输出及退出码兼容；观测消息不进入 CLI 业务标准输出。
- App 更新复用 Velopack/Sparkle，设置只显示一个随状态变化的操作；保留草稿、并发与安全重启保护。真实 API、干净机、多 DPI、正式签名和本轮 GUI 验收分别记录。

## Brand Commitments

名称为 Smart Search。普通用户界面使用清楚的任务名称与中文解释，保留英文服务商标识和高级命令详情。codex-tweaks 是结构和原生桌面体验参考，不继承其品牌、插件注入业务或全部实现。

项目图标采用维护者提供的深色放大镜和青色命令提示符。原图及平台资源生成说明位于 `assets/branding/`。

## Evidence on Hand

- 配置器改造基线：`0af19548b2df7e0e6bf2df64a831b909a1706cd3`。
- 现有入口：`src/smart_search/cli.py`、`service.py`、`config.py`、`ui_api.py`、`ui_metadata.py`、`skill_installer.py`。
- 上轮 Web UI 的 8 项问题已加入回归并修复；共享 Python 核心与 npm 安装保持兼容。
- Windows/macOS 历史实测范围见 `docs/windows-ui-parity.md` 与 `docs/macos-adaptation.md`；本轮范围见 `docs/comet/changes/desktop-configurator-simplification/`，构建不能替代新增界面实测。

## Product Principles

- 一套业务核心和有效配置语义，多个兼容入口。
- 配置器只保留完成配置和验证所需的操作；高级业务能力由公开 CLI 提供。
- 状态有来源和时间，未知不等于正常。
- 密钥与内容保留范围明确，操作失败不损坏旧配置。
- Windows 与 macOS 分别验证，发布时明确各自已验证的范围。

## Accessibility & Inclusion

遵循各平台的键盘导航、可见焦点、系统缩放和主题习惯；状态同时提供文字，不能只用颜色表达。
