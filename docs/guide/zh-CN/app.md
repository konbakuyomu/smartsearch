[手册目录](../README.md) · [English](../en/app.md)

# App 配置与使用

App 用于配置、测试和安装 CLI/Skills，日常调用由独立 CLI 完成。以下步骤对应当前源码中的四页配置器；已发布旧版可能仍显示旧页面。

## 安装和打开

在[发行页](https://github.com/konbakuyomu/smartsearch/releases/latest)下载适合系统与架构的安装包。Windows 安装到当前用户目录。App 自带运行环境，使用 App 不需要先安装 Python、Node.js 或独立 CLI。

环境准备和完整 App/CLI 语言切换从 v0.1.21 起提供，“更新 Skills”页面从 v0.1.22 起提供，Windows 自签名和新透明图标从 v0.1.23 起提供。Windows 的 `-signed.exe` 包采用自签名，Windows 默认不信任该证书，仍可能弹出 SmartScreen 提示。先核对官方发行来源和[公开证书指纹](../../windows-signing.md)，再按系统允许的选项决定是否运行；这不等同永久信任证书，不需要关闭安全保护。旧 `-unsigned-test.exe` 包仍未签名；macOS 历史包使用 ad-hoc；配置作者证书后的包使用固定证书自签名，仍无 Developer ID 或公证，见 [macOS 签名](../../macos-signing.md)。macOS、Windows ARM64、干净机器完整使用和 DPI 矩阵尚未全部完成实机验收。

v0.1.24 首次提供正式 Velopack/Sparkle 更新源，并整合新的原生界面。旧安装无法更新时，见[排障](troubleshooting.md#app-更新失败或不可用)。首次框架发行提供完整更新包，后续发行可基于这一已验证基线生成差分。

从开始菜单或“应用程序”打开 **Smart Search**。默认打开“配置”，已有配置会被复用。

### macOS 安装与首次打开

1. 在发行页的下载表格中选择 Mac 安装包；通用版同时支持 Apple Silicon 和 Intel。
2. 打开 DMG，将 **Smart Search** 图标拖到 **Applications（应用程序）**，等待复制完成。
3. 从“应用程序”中双击 **Smart Search**，先尝试打开一次。
4. 若提示无法验证开发者或 Apple 无法检查此 App，在确认来源为本项目发行页后，打开 **苹果菜单 → 系统设置 → 隐私与安全性**，向下滚动到“安全性”，找到 Smart Search 的拦截提示，点击 **仍要打开**。
5. 按系统要求完成身份验证，再在确认窗口中点击 **打开**。系统会记住对这个 App 的允许，以后直接从“应用程序”启动。

如果没有“仍要打开”按钮，先再尝试启动 App，然后返回设置页面。由组织管理的 Mac 可能限制这项设置。具体入口参见 [Apple 的首次打开说明](https://support.apple.com/zh-cn/102445)。若提示“已损坏”或“将损坏你的电脑”，先按[macOS 排障步骤](troubleshooting.md#macos-提示已损坏或无法验证开发者)检查来源、完整性与签名，不直接套用开发者未验证时的放行步骤。

## 配置服务

1. 在“配置”选择服务商，填入地址、API Key 和模型。页面保留官方文档和申请 Key 的入口，详见[服务商与配置](configuration.md)。
2. 按需测试当前值或未保存草稿，再预览、保存。测试不会自动保存配置；正在运行时可就地取消。
3. 到“测试”选择搜索、网页读取、Context7 库/文档、路由预览或离线冒烟，查看、复制或导出结果。

服务商测试和联网测试可能消耗付费额度，打开 App 不会自动执行。草稿在保存前不写入配置；删除 Key 使用界面的清除操作并保存。环境变量提供的字段只读。切页、换语言或重新读取状态不会丢弃草稿。

## 安装独立 CLI 和 Skills

1. 打开“CLI 与 Skills”。CLI 未就绪时点击“安装 CLI”或“修复 CLI”；App 自动检查来源、复用健康组件、补齐依赖并验证实际版本。
2. 勾选需要安装或更新的 Agent，点击“安装/更新所选 Skills”。无需先检查或刷新；勾选至少一个目标即可提交，操作期间等待完成。
3. App 在此次操作内下载并校验官方 npm 最新正式版的 Skill 文件，备份不同内容后同步。没有变化时显示“所选 Skills 已是最新”，不重复写入。失败保留原文件，从同一按钮重试。
4. 重新打开 Agent 会话；Gemini 可用 `/skills reload`。让 Agent 先运行 `smart-search --version`，再按需要测试搜索。

勾选框只表示本次目标，取消勾选不会卸载。额外文件、未选目标和历史副本保留，备份路径显示在结果中。后台检查只提示，不自动写入。App/CLI 更新也不会自动同步 Skills。

CLI 安装在 `%LOCALAPPDATA%/SmartSearchTools` 或 `~/.local/share/smart-search-tools`，独立于 App；已有 npm/mise 安装保持原管理器。未知或冲突来源显示具体原因，不另建副本冒充修复。安装失败保留已成功组件，同一操作可重试；只有下载阶段可取消，包管理器写入期间需等待。

CLI 版本和 Skill 内容分别判断。CLI 未验证不阻止 Skill 正文同步，但实际调用前必须准备 CLI。已有本机调用信息在未验证时保留；验证后的独立调用路径会写入 Skill。Skill 文件一致不代表 Agent 已加载或实际调用成功。

支持 Codex、Claude Code、Cursor、Copilot、Gemini、OpenCode、Cline、Roo Code 等注册目标。Codex 使用 `~/.agents/skills/smart-search-cli`，其他兼容 Agent 也可能读取这个共享目录；旧 `.codex/skills` 副本保留。Claude 尊重绝对 `CLAUDE_CONFIG_DIR`；OpenCode 使用 `~/.config/opencode/skills`。WSL、远程主机和 Cloud Agent 需各自配置。

## 四个页面

| 页面 | 用途 |
| --- | --- |
| 配置 | 编辑服务商与路由、测试草稿、预览和保存 |
| 测试 | 运行一次配置验证，就地取消，读取和导出结果 |
| CLI 与 Skills | 安装/修复/更新独立 CLI；勾选并安装/更新 Agent Skills |
| 设置 | 语言、外观、配置目录、App 更新和关于 |

完整搜索和研究能力保留在[CLI](cli.md)。重要结论仍需核对来源正文，见[搜索、研究与证据](research.md)。

## 设置和更新

在“设置”选择跟随系统、简体中文或 English；App 与独立 CLI 分别保存语言偏好。切换保留草稿和运行中的测试，受保护写入需先完成。更改配置目录沿用草稿保护；自定义目录旁可恢复默认目录。

App 更新只需使用设置中的主按钮：检查更新、更新或重试。Windows 使用 Velopack，macOS 使用 Sparkle；框架负责下载、校验和安装，保留差分/完整包回退。重启前需保存或放弃草稿并结束当前操作，下载完成不代表安装完成。测试包不能自动更新时显示正式安装包链接。

App 更新不替换独立 CLI。CLI 的检查/更新留在“CLI 与 Skills”，只更新已确认来源的 Smart Search，读回实际版本后才显示完成。离线和签名失败不会显示已是最新。

## App 与 CLI 独立运行

App 的私有进程只用于配置、测试和安装管理，不能作为公开 CLI 搜索命令使用，也不会加入 PATH。终端和 Agent 使用独立 CLI，关闭、更新或卸载 App 后仍可运行。

两者选择同一配置目录可共享服务商设置。Windows 默认 `%LOCALAPPDATA%\smart-search`，也兼容旧 home 路径；用 `SMART_SEARCH_CONFIG_DIR` 或 App 目录选择可隔离配置。不同进程的环境变量仍可能产生不同有效值。

关闭有运行任务的 App 窗口时，可选择后台继续、取消自己的任务并退出或返回；后台窗口可从通知区域/菜单栏恢复。App 不强杀终端或 Agent 独立启动的 CLI。卸载 App 不清理共享配置、独立 CLI、Skills、研究证据或导出文件。

构建与协议说明见 [desktop README](../../../desktop/README.md) 和[桌面协议](../../../desktop/PROTOCOL.md)。安装、签名或旧版本更新问题见[排障](troubleshooting.md)。
