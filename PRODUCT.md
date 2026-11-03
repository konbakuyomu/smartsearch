# Product

<!-- impeccable:product-schema 1 -->

## Platform

adaptive

Windows 和 macOS 使用原生桌面界面，保留系统控件和交互习惯。Windows x64 已在本机实机验证；macOS 和 Windows ARM64 的完整实机验收仍待完成。每版各平台验证到哪一步，以 `.github/releases/` 下的发版说明为准。

## Stack

Windows：WinUI 3 / C#。macOS：SwiftUI / Swift。两端共用现有 Python 搜索业务核心，通过本机私有后端进程的版本化 JSON 协议通信。现有 `smart-search` CLI 继续直接调用同一核心。

## Users

- 普通用户：希望通过安装 App、填写配置、查看明确状态来使用 Smart Search，不要求终端或开发环境知识。
- 开发者及 AI 工具使用者：继续从终端或智能体调用 CLI，并从 App 观察调用进度、服务商和错误。

## Product Purpose

把 Smart Search 已有搜索、文档检索、网页抓取、深度研究、服务商配置与诊断能力整合为桌面产品，同时保持现有 CLI 与配置兼容。成功意味着用户能完成配置、执行任务、解释真实运行状态，并在 App 未打开时继续使用 CLI。

## Positioning

同一套搜索与配置规则支持原生 App 和 CLI。App 不自行重算服务商能力、密钥是否有效、回退或冷却结果；业务事实由共享 Python 核心提供。

## Operating Context

- 运行于用户自己的 Windows 或 macOS 桌面会话，本地优先。
- App 内操作与终端/AI 发起的新版 CLI 调用都属于实时观测范围。
- 第三方服务商仍使用现有 URL、Key、模型与网络配置；启动 App 和读取状态不等于发起计费探针。
- App 与 Smart Search CLI 分别安装和更新。概览负责发现已有 mise/npm 安装或引导准备独立 CLI；App 不捆绑 CLI。原配置不会因安装或移动 App 而被静默迁移或覆盖。

## Capabilities and Constraints

- 完整现有业务能力有桌面入口；实验性能力维持显式、实验性标识。
- 配置读取、有效值、环境变量来源、保存和草稿测试统一处理。
- 实时活动展示实际发生的阶段、耗时、尝试和失败，不伪造进度或健康状态。
- 保持 CLI 命令、参数、别名、输出及退出码兼容；观测消息不进入 CLI 业务标准输出。
- Windows x64 已完成本机功能及安装生命周期测试；真实 API、干净机、多 DPI 与其余平台分别保留未验边界。两端正式包沿用固定的自签名身份：Windows 自签名证书不等于系统默认信任，macOS 签名也不等于 Apple Developer ID 或公证。

## Brand Commitments

名称为 Smart Search。普通用户界面使用清楚的任务名称与中文解释，保留英文服务商标识和高级命令详情。codex-tweaks 是结构和原生桌面体验参考，不继承其品牌、插件注入业务或全部实现。

项目图标采用维护者提供的深色放大镜和青色命令提示符。原图及平台资源生成说明位于 `assets/branding/`。

## Evidence on Hand

- 调查代码基线：`a08df0ae032e0e9c1bcd9374e1c314519f16f665`。
- 现有入口：`src/smart_search/cli.py`、`service.py`、`config.py`、`ui_api.py`、`ui_metadata.py`、`skill_installer.py`。
- 上轮 Web UI 的 8 项问题已加入回归并修复；共享 Python 核心与 npm 安装保持兼容。
- Windows x64 已实测原生界面、安装升级卸载、独立 CLI、后台恢复和隔离活动；不以此替代其他平台或真实外部 API 验收。

## Product Principles

- 一套业务核心和有效配置语义，多个兼容入口。
- 常用路径易懂，高级能力完整保留。
- 状态有来源和时间，未知不等于正常。
- 密钥与内容保留范围明确，操作失败不损坏旧配置。
- Windows 与 macOS 分别验证，发布时明确各自已验证的范围。

## Accessibility & Inclusion

遵循各平台的键盘导航、可见焦点、系统缩放和主题习惯；状态同时提供文字，不能只用颜色表达。
