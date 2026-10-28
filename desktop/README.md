# Smart Search 桌面构建

脚本默认构建未做发行者签名的测试产物：macOS 本地默认使用 ad-hoc，固定证书签名与作者配置见 [macOS 签名](../docs/macos-signing.md)；Windows 显式使用 `-SigningMode Required` 时生成自签名产物，签名失败即停止。不创建 GitHub Release、不修改 PATH，也不会读取或删除共享配置、用户结果或外部 npm CLI。每次执行都会在 `.desktop-artifacts/` 新建独立目录；失败现场保留供排查。

独立 CLI 固定为 PyInstaller `onedir`：`smart-search.exe`（Windows）或 `smart-search`（macOS / Linux），并验证 `smart_search/assets` 全量存在、`smart-search` 包元数据存在。App 不包含 CLI 或 Python 运行环境；npm 平台包和独立 ZIP 各自携带对应架构的完整 CLI。`--smoke` 仅发送本机 `initialize` 与 `shutdown` 协议消息，使用本次运行目录中的空配置目录，不发真实服务商请求。

## 发布文件名与下载入口

以 `X.Y.Z` 为版本占位符，面向用户的产物如下：

| 系统 | 文件名 | 适用设备 |
| --- | --- | --- |
| macOS 通用版（推荐） | `SmartSearch-vX.Y.Z.dmg` | Apple Silicon 与 Intel |
| macOS Apple Silicon | `SmartSearch-vX.Y.Z-arm64.dmg` | M 系列 |
| macOS Intel | `SmartSearch-vX.Y.Z-x86_64.dmg` | Intel Mac |
| Windows x64 | `SmartSearch-vX.Y.Z-windows-Setup-x86_64.exe` | Intel / AMD |
| Windows ARM64 | `SmartSearch-vX.Y.Z-windows-Setup-arm64.exe` | ARM64 |

三种 Mac 产物分别配套同名 `-sparkle.zip` 和 `appcast-macos-{universal,arm64,x86_64}.xml`；通用版更新保持双架构。Windows 的包 ID、渠道、`.nupkg` 和 JSON feed 名称保持不变，`x86_64` 只用于用户下载的安装器文件名，内部运行时仍为 `win-x64`。

桌面发布工作流在全部安装包、更新包、校验清单和 feed 上传成功后，把中英双语下载表格放在已有 Release 正文顶部，保留原版本说明；重复运行会替换同一受标记管理的表格。npm 单独发布、尚无桌面附件时不会生成无效下载链接。旧版 Sparkle 包名仍可作为差分基线读取，不需要重命名已发布附件。

## Windows

在仓库根目录执行：

```powershell
mise run desktop:windows:build -Architecture x64
```

脚本先构建并验证独立 CLI，再阶段化 `desktop/windows` 源码并执行 `dotnet publish --self-contained true`。App 的 `publish` 目录不含 CLI、Python 或搜索引擎；CLI 单独发布为 `smart-search-cli-VERSION-windows-ARCH.zip`。保留原有的 Windows 架构、签名和资源校验；x64 构建不能代替 ARM64 实机验收。

安装包由仓库锁定的 Velopack `vpk` 工具生成，默认按当前用户安装；`-InstallerMode Skip` 只生成散包。生产安装身份为 `com.smartsearch.desktop.win-x64` 或 `com.smartsearch.desktop.win-arm64`，渠道为 `win-x64-stable` / `win-arm64-stable`。散包不能充当已安装的更新客户端，界面提示先完整安装。

首次从 Inno Setup 版迁移时，先完成写入并退出旧 App，再通过 Windows“已安装的应用”卸载旧 App，运行新的完整 Setup，并从新快捷方式启动。新包附带双语 `migration.txt`；App 只读识别旧安装，不自动卸载。共享配置、结果、独立 CLI、SmartSearchTools 和 Agent Skills 保留在原路径。后续版本由 Velopack 更新。

传入 `-PreviousReleaseDirectory` 可用已校验的同架构上一版完整包生成差分，目标完整包始终保留。没有框架基线是首版；已有基线下载或校验失败会阻止发布。`test_windows_updates.py <result.json>` 使用独立测试身份、目录和本地 feed，验证真实 SDK 差分安装及损坏差分后的完整包回退，不覆盖正式安装。

Windows 签名覆盖自有 App EXE/DLL、Velopack Setup、启动包装器及负责更新/卸载的 Update.exe，使用固定公开证书、SHA-256 和 RFC3161 时间戳。第三方文件保持原字节，不修改用户信任库。说明及操作见 [Windows 签名](../docs/windows-signing.md)。

## macOS

在目标架构的 macOS 13+ 机器上执行：

```bash
mise install
mise run desktop:macos:install
mise run desktop:macos:build --architecture arm64
```

脚本要求 Python、宿主机和目标架构一致。Swift 主程序与 Sparkle 构成 App，PyInstaller 产物作为独立 CLI ZIP 发布，不复制到 App 中。Intel 构建使用 `--architecture x86_64`。

两种原生产物就绪后，使用同版本、同更新公钥的完整 App 生成通用版：

```bash
mise run desktop:macos:universal \
  --arm64-app '/path/to/arm64/Smart Search.app' \
  --x86_64-app '/path/to/x86_64/Smart Search.app' \
  --sparkle-tools /path/to/arm64/sparkle-tools
```

通用版通过 `lipo` 合并 Swift 主程序，验证 framework/helper 的双架构后重新签名和生成 DMG。CLI 的 ZIP 可独立运行并由 App 手动选择；自动安装沿用已发现的 mise 或 npm，npm 会选择与 Node.js 进程架构匹配的平台包。

构建原生界面需要选中带 macOS SDK 26 或更新版本的 Xcode，最低运行版本仍是 macOS 13。`compile-macos.sh` 将同一个实际 SDK 路径/版本同时传入编译和链接，避免 SwiftPM 将最低系统版本误记为 linked-on SDK，导致新版 macOS 仍显示旧控件样式。打包验证会读取真实 Mach-O 的 SDK 和最低版本，并拒绝旧 SDK 或与构建 SDK 不一致的产物。

所有资源组装完成后，脚本对完整 `.app` 签名，并强制执行 `codesign --verify --deep --strict`。固定证书模式从内向外签署嵌套程序和框架，记录证书指纹与稳定的身份规则；默认本地构建使用 ad-hoc。编译器为单个可执行文件生成的 linker signature 不能代替完整应用签名；修复前 v0.1.22 的应用会报 `code has no resources but signature indicates they must be present`。SHA-256 一致也无法发现这种打包错误。

DMG 沿用 Codex Tweaks / DJOneHub 的 660×440 安装窗口：中英双语提示、青色拖拽箭头、112pt 图标、Applications 链接，以及 1×/2× 背景。布局位于 `packaging/macos/dmg-settings.py`，修改 SVG 后运行 `mise run desktop:macos:background` 重新生成两个 PNG。打包不依赖 Finder 自动化，支持无界面的 CI。

构建最后会只读挂载实际 DMG，校验应用签名、版本、架构和安装资源，复制到临时 Applications 目录，再检查复制后的签名，并确认 App 未捆绑 CLI；独立 CLI 的启动/退出 smoke 在 CLI 构建阶段执行。也可单独检查：

```bash
mise run desktop:macos:verify /path/to/SmartSearch.dmg --architecture arm64 --version 0.1.22
mise run desktop:packaging:lint
```

文件名不再携带签名状态；`result.json`、`signing.json` 和发布说明区分本地 `ad-hoc-test`、一次性证书 `self-signed-test` 与维护者固定证书 `self-signed`。macOS 仍没有 Developer ID 发行者签名和 Apple 公证，ad-hoc 只修复包的完整性，不保证 Gatekeeper 默认放行；首次打开说明见[macOS 排障](../docs/guide/zh-CN/troubleshooting.md#macos-提示已损坏或无法验证开发者)。干净机器使用须另行验收。

完整 App 同时嵌入锁定版本的 Sparkle framework/helper，所有资源与更新公钥/feed 写入均在完整 bundle 签名之前完成。`result.json` 保存 App、DMG、架构及框架工具位置；原生 IPC、真实 SDK 标记、Icon Composer 资源和复制安装校验保持工程师 PR #51 的实现。

正式更新先通过 `mise run desktop:macos:with-signing --mode required --` 加载作者证书，再同时传入 `--release-updates --update-key-file <仓库外私钥文件> --update-public-key <公钥>`，由官方 `generate_appcast` 签署完整 ZIP、差分及 appcast；可用 `--previous-release-directory` 提供已验证的上一版。私钥缺失或公钥不匹配即停止，普通无密钥候选关闭 App 自动更新。`test_sparkle_updates.py <result.json>` 使用临时 EdDSA 身份、本地 feed 和官方 sparkle-cli 验证差分、回退及错误公钥拒绝，必须在 macOS 实际运行。首次从旧版迁移需关闭旧 App 并完整替换一次。

## CI 与发布边界

`.github/workflows/desktop-build.yml` 在 PR 或手动触发时分别构建 Windows x64/ARM64 与 macOS arm64/x86_64，并运行各平台的真实框架升级检查；PR 不获取发布 Secrets。Mac 使用 PR #51 已验证的 Xcode 26.3、mise 工具与 ensurepip 安装路径。手动开启 `sign_windows`、`sign_macos` 或 `sign_macos_updates` 可生成相应平台使用正式身份签名的候选；macOS PR 使用临时测试证书，不读取正式 Secrets；`release_tag` 为空时不会发布。`windows_only` 仅用于独立 Windows 候选，不能同时开启 `sign_macos`、`sign_macos_updates` 或填写 `release_tag`。

原生 Mac job 将 App 和 ARM job 的 Sparkle 工具封装为短期 tar artifact，保留可执行权限和符号链接。通用版 job 合并后在原生 ARM runner 上验证安装及 Sparkle 更新；随后原生 Intel runner 下载并验证同一个 DMG 的安装、签名与架构。任何平台或通用版验证失败均阻止 Release 上传。

填写已有稳定 `release_tag` 属于显式发布：强制维护者的 Windows、macOS 代码签名和 Sparkle EdDSA 身份，四架构及通用版全部通过后，先上传安装器、完整包、差分包与校验清单，最后上传引用它们的 feed 和下载表格。发布源必须已经包含原生更新客户端，不能把旧下载器产品和新更新包拼成一个发行版。桌面工作流不会创建 Release/Tag；但仓库独立的 `publish-npm.yml` 会在 main 推送后自动发布 npm beta 并创建 GitHub 预发布，正式 latest 由稳定 tag 控制。

macOS 签名 CI 验证跨版本身份一致、复制安装、错误密码/证书、内容篡改拒绝及临时钥匙串清理。Windows 签名 CI 运行错误密码/证书、内容/签名/时间戳篡改及签名失败检查；真实隔离升级后验签落盘的 App、启动包装器与 Update.exe，不启动 GUI。结果保存在构建 `result.json`、升级 `receipt.json` 与签名检查记录。构建、验签和隔离安装不能代替用户 GUI、干净机器或 SmartScreen 提示验收。

修复已有原生更新发行版的包装时，产品源码仍固定在 tag；Mac 打包脚本、成品校验、安装资源、mise 配置及发布资产校验器可取工作流提交。`replace_existing_assets` 仅用于明确批准的附件修复，不应重打同一已安装版本；正常更新提高版本号。独立 CLI 携带 `package.json` 清单；App 与 CLI 分别读回实际版本。

Windows 新构建统一使用 `windows-Setup-{架构}.exe`，不以文件名判断签名状态；正式发布仍强制 self-signed 签名及验签，未签名候选不会进入发布上传步骤。Sparkle 更新签名不是 Apple Developer ID 或公证。正式 Sparkle 配置为 Secret `SMART_SEARCH_SPARKLE_EDDSA_PRIVATE_KEY`（Base64 编码的 32 字节 Ed25519 seed）与公开变量 `SMART_SEARCH_SPARKLE_PUBLIC_KEY`；公钥必须与 [仓库记录](packaging/macos/sparkle-public-key.json) 一致。后续发行复用这一身份，私钥只保存于受限加密备份与 GitHub Secrets，不进入仓库或构建附件。缺少正式密钥时仍能跑隔离更新测试，但不能上传正式 Sparkle 更新资产。 作者必须按 [macOS 证书生成与 Secrets 配置](../docs/macos-signing.md) 完成首次设置；此变更不提供正式证书。

## App 和 CLI 更新

设置只管理 App 更新，本地环境统一进入概览。App 使用 Sparkle / Velopack，启用自动检查时每次进程启动检查，不再周期轮询。主要按钮从“检查更新”变为“下载更新”；下载进度、取消、原生安装确认和草稿保护保留。启动检查发现新版本时弹窗：Windows 在连接后弹出“立即更新 / 稍后”对话框，macOS 由 Sparkle 后台检查并显示更新提示；手动操作沿用框架交互。CLI 缺失或损坏不影响 App 检查更新。

App 更新由 SDK 下载和校验，优先使用适用差分，失败时按框架规则回退完整包。安装前保护草稿、自有任务和 CLI/Skills 写入，关闭 App 自己的协议进程后安装重启。App 更新不替换独立 CLI。

CLI 不可用时，App 原生环境管理仍可操作。自动检测枚举 npm prefix，并通过 mise 的全局解析找到独立工具安装；固定所选安装、Node 和原管理器，多安装不静默切换。mise 更新保留简单工具选项，复杂约束转为原终端手动更新，不接管 pip/uv 开发版。CLI 默认启动时及每 24 小时检查，只提示，不自动安装。配置和 Skills 保留。

## 环境准备与 App/CLI 解耦

App 不内置 CLI，也不负责搜索或 Skill 规则。概览按“本地环境 → 服务商 → 测试 → 可选 Skills”引导；先复用已发现的安装，环境路径和更新偏好集中在“环境详情”中。启动时用上次检测结果（Windows 为 SmartSearchTools 下的 `cli-detection.json`，macOS 为偏好设置）直接连接，所选 CLI 文件仍在才采用，随后在后台再检测一次；变化只在需要时提示或切换。右上角刷新和“重新检测”显示检测过程。缺失时提供 Node.js 下载、重新检测、手动指定 npm 和选择独立 CLI 的入口。独立 ZIP 解压后保留完整目录，再选择 smart-search 可执行文件；这条路径不依赖 Node/npm，由用户管理更新。CLI 平台包自带 Python 解释器和依赖，并隔离用户 Python 环境；App 不下载或配置 Node/Python。

`npm-binaries.yml` 为 macOS、Windows、Linux 的 x64/arm64 构建平台包，真实执行 npm tarball 安装与无 Python 环境验证。发布管线待六个平台通过后，先发布平台包，再发布 npm 主包。首次发布需要在 npm 为六个 scoped 平台包配置发布权限/可信发布者；旧 0.1.24 不能覆盖，需使用新版本号。

本地通过 `mise run desktop:cli:build --result-file <manifest>` 构建 CLI，再用 `mise run npm:binary:package --manifest <manifest> --output <新目录>` 和 `mise run npm:binary:smoke <新目录>` 检查 npm 分发。

普通 npm 安装写入所选全局 prefix；mise 安装由 mise 管理。CLI 入口由原管理器创建。App 不修改 PATH 或 npm 配置；卸载 App 不影响 CLI、搜索配置和已接入的 Skills。历史 SmartSearchTools 目录保留，不自动迁移或删除。

“更新 Skills”的清单、内容、状态、写入、备份和移除全部来自当前 CLI。安装的 Skill 是短入口，通过 `smart-search agent-guide [relative-path]` 获取当前 CLI 的完整说明。手动同步只处理确认的目标；默认自动维护已接入目标，在 CLI 升级后的首次使用及后续每日检查执行，不依赖 App 打开。个人修改和额外文件保留；缺失文件或冲突需要手动处理。移除先备份并取消维护。

npm 操作失败后显示错误，重新检测可读回当前安装状态。包管理器写入期间保持 App 打开。实现检查必须使用隔离配置、环境和技能目录；Windows x64 的实测不代表 macOS/ARM64 或真实 AI 会话已经验证。

## 双语界面与手册

App 在设置页选择自动、简体中文或 English，偏好独立于 CLI 保存。
App 将当前语言传给所选 CLI 的协议进程；切换保留草稿与任务，环境写入或 CLI 更新期间暂不可切换。
CLI 通过 `SMART_SEARCH_LANGUAGE` 和单次 `--lang` 选择语言，命令名、机器字段及来源原文不翻译。
共享语言资源位于 `src/smart_search/assets/i18n/messages.json`，Windows 直接嵌入，macOS 资源副本须保持字节一致。

用户入口见[双语手册](../docs/guide/README.md)，命令和配置参考通过
`python scripts/generate_references.py` 从当前实现更新。环境准备与完整语言切换从 v0.1.21 起提供；本地构建脚本不会覆盖已安装的 App。
