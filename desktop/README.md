# Smart Search 桌面构建

原生 App 是四页配置器：配置、测试、CLI 与 Skills、设置。私有配置/测试进程不公开为 CLI；终端和 Agent 使用 App 目录外的独立安装。

脚本默认构建未做发行者签名的测试产物：macOS 本地默认使用 ad-hoc，固定证书签名与作者配置见 [macOS 签名](../docs/macos-signing.md)；Windows 显式使用 `-SigningMode Required` 时生成自签名产物，签名失败即停止。不创建 GitHub Release、不修改 PATH，也不会读取或删除共享配置、用户结果或外部 npm CLI。每次执行都会在 `.desktop-artifacts/` 新建独立目录；失败现场保留供排查。

Python 后端固定为 PyInstaller `onedir`：`smart-search.exe`（Windows）或 `smart-search`（macOS），并验证 `smart_search/assets` 全量存在、`smart-search` 包元数据存在。Mac 通用版保留两套完整后端，由双架构启动器选择当前架构。`--smoke` 仅发送本机 `initialize` 与 `shutdown` 协议消息，使用本次运行目录中的空配置目录，不发真实服务商请求。

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

脚本先构建并验证后端，再把 `desktop/windows` 的源文件阶段化到本次 artifact 目录中执行 `dotnet publish --self-contained true`，最后把完整 onedir 后端复制到 `publish\backend\smart-search.exe`。阶段化会跳过工作树已有的 `bin`、`obj` 和 `.desktop-artifacts`，因此每次构建不依赖或清空旧中间文件。Windows x64 与 ARM64 必须在对应架构的 Windows 上分别构建和运行；脚本会拒绝 Python 架构与目标不一致的 PyInstaller 交叉构建。本机 x64 的成功不能代表 ARM64 已验证。

安装包由仓库锁定的 Velopack `vpk` 工具生成，默认按当前用户安装；`-InstallerMode Skip` 只生成散包。生产安装身份为 `com.smartsearch.desktop.win-x64` 或 `com.smartsearch.desktop.win-arm64`，渠道为 `win-x64-stable` / `win-arm64-stable`。散包不能充当已安装的更新客户端，界面提示先完整安装。

首次从 Inno Setup 版迁移时，先完成写入并退出旧 App，再通过 Windows“已安装的应用”卸载旧 App，运行新的完整 Setup，并从新快捷方式启动。新包附带双语 `migration.txt`；App 不再常驻显示旧安装迁移面板，也不自动卸载。共享配置、结果、独立 CLI、SmartSearchTools 和 Agent Skills 保留在原路径。后续版本由 Velopack 更新。

传入 `-PreviousReleaseDirectory` 可用已校验的同架构上一版完整包生成差分，目标完整包始终保留。没有框架基线是首版；已有基线下载或校验失败会阻止发布。`test_windows_updates.py <result.json>` 使用独立测试身份、目录和本地 feed，验证真实 SDK 差分安装及损坏差分后的完整包回退，不覆盖正式安装。

Windows 签名覆盖自有 App EXE/DLL、后端、Velopack Setup、启动包装器及负责更新/卸载的 Update.exe，使用固定公开证书、SHA-256 和 RFC3161 时间戳。第三方文件保持原字节，不修改用户信任库。说明及操作见 [Windows 签名](../docs/windows-signing.md)。

## macOS

在目标架构的 macOS 13+ 机器上执行：

```bash
mise install
mise run desktop:macos:install
mise run desktop:macos:build --architecture arm64
```

脚本要求 Python、宿主机和目标架构一致，避免把 PyInstaller 的原生二进制误当成交叉编译产物。它用 Xcode 提供的 Swift 工具链和独立 SwiftPM scratch 目录构建 `desktop/macos` 的 `SmartSearchDesktop`，将后端放入 `Smart Search.app/Contents/Resources/backend/smart-search`。Intel 构建使用 `--architecture x86_64`。

两种原生产物就绪后，使用同版本、同更新公钥的完整 App 生成通用版：

```bash
mise run desktop:macos:universal \
  --arm64-app '/path/to/arm64/Smart Search.app' \
  --x86_64-app '/path/to/x86_64/Smart Search.app' \
  --sparkle-tools /path/to/arm64/sparkle-tools
```

通用版通过 `lipo` 合并 Swift 主程序，并携带 `backend/arm64`、`backend/x86_64` 两套未经合并的 PyInstaller 分发目录。`backend/smart-search` 是一个 Universal 启动器，使用当前执行切片选择后端，通过 `execv` 保留参数、IPC 管道与进程生命周期。[PyInstaller 不支持用 lipo 合并两份冻结可执行文件](https://pyinstaller.org/en/stable/feature-notes.html#macos-multi-arch-support)。所有应用、引擎依赖和 Sparkle helper 都会检查目标架构；之后重新签署整个 App，再创建和挂载 DMG 验证。

构建原生界面需要选中带 macOS SDK 26 或更新版本的 Xcode，最低运行版本仍是 macOS 13。`compile-macos.sh` 将同一个实际 SDK 路径/版本同时传入编译和链接，避免 SwiftPM 将最低系统版本误记为 linked-on SDK，导致新版 macOS 仍显示旧控件样式。打包验证会读取真实 Mach-O 的 SDK 和最低版本，并拒绝旧 SDK 或与构建 SDK 不一致的产物。

所有资源组装完成后，脚本对完整 `.app` 签名，并强制执行 `codesign --verify --deep --strict`。固定证书模式从内向外签署嵌套程序、框架和后端库，记录证书指纹与稳定的身份规则；默认本地构建使用 ad-hoc。编译器为单个可执行文件生成的 linker signature 不能代替完整应用签名；修复前 v0.1.22 的应用会报 `code has no resources but signature indicates they must be present`。SHA-256 一致也无法发现这种打包错误。

DMG 沿用 Codex Tweaks / DJOneHub 的 660×440 安装窗口：中英双语提示、青色拖拽箭头、112pt 图标、Applications 链接，以及 1×/2× 背景。布局位于 `packaging/macos/dmg-settings.py`，修改 SVG 后运行 `mise run desktop:macos:background` 重新生成两个 PNG。打包不依赖 Finder 自动化，支持无界面的 CI。

构建最后会只读挂载实际 DMG，校验应用签名、版本、架构和安装资源，复制到临时 Applications 目录，再检查复制后的签名并执行隔离配置的后端启动/退出 smoke。也可单独检查：

```bash
mise run desktop:macos:verify /path/to/SmartSearch.dmg --architecture arm64 --version 0.1.22
mise run desktop:packaging:lint
```

文件名不再携带签名状态；`result.json`、`signing.json` 和发布说明区分本地 `ad-hoc-test`、一次性证书 `self-signed-test` 与维护者固定证书 `self-signed`。macOS 仍没有 Developer ID 发行者签名和 Apple 公证，ad-hoc 只修复包的完整性，不保证 Gatekeeper 默认放行；首次打开说明见[macOS 排障](../docs/guide/zh-CN/troubleshooting.md#macos-提示已损坏或无法验证开发者)。干净机器使用须另行验收。

完整 App 同时嵌入锁定版本的 Sparkle framework/helper，所有资源与更新公钥/feed 写入均在完整 bundle 签名之前完成。`result.json` 保存 App、DMG、架构及框架工具位置；原生 IPC、真实 SDK 标记、Icon Composer 资源和复制安装校验保持工程师 PR #51 的实现。

正式更新先通过 `mise run desktop:macos:with-signing --mode required --` 加载作者证书，再同时传入 `--release-updates --update-key-file <仓库外私钥文件> --update-public-key <公钥>`，由官方 `generate_appcast` 签署完整 ZIP、差分及 appcast；可用 `--previous-release-directory` 提供已验证的上一版。私钥缺失或公钥不匹配即停止，普通无密钥候选关闭 App 自动更新。`test_sparkle_updates.py <result.json>` 使用临时 EdDSA 身份、本地 feed 和官方 sparkle-cli 验证差分、回退及错误公钥拒绝，必须在 macOS 实际运行。首次从旧版迁移需关闭旧 App 并完整替换一次。

## CI 与发布边界

`.github/workflows/desktop-build.yml` 在 PR 或手动触发时分别构建 Windows x64/ARM64 与 macOS arm64/x86_64，并运行各平台的真实框架升级检查；PR 不获取发布 Secrets。Mac 使用 PR #51 已验证的 Xcode 26.3、mise 工具与 ensurepip 安装路径。手动开启 `sign_windows`、`sign_macos` 或 `sign_macos_updates` 可生成相应平台使用正式身份签名的候选；macOS PR 使用临时测试证书，不读取正式 Secrets；`release_tag` 为空时不会发布。`windows_only` 仅用于独立 Windows 候选，不能同时开启 `sign_macos`、`sign_macos_updates` 或填写 `release_tag`。

原生 Mac job 将 App 和 ARM job 的 Sparkle 工具封装为短期 tar artifact，保留可执行权限和符号链接。通用版 job 合并后在原生 ARM runner 上验证安装及 Sparkle 更新；随后原生 Intel runner 下载并验证同一个 DMG 的安装与后端启动。任何平台或通用版验证失败均阻止 Release 上传。

填写已有稳定 `release_tag` 属于显式发布：强制维护者的 Windows、macOS 代码签名和 Sparkle EdDSA 身份，四架构及通用版全部通过后，先上传安装器、完整包、差分包与校验清单，最后上传引用它们的 feed 和下载表格。发布源必须已经包含原生更新客户端，不能把旧下载器产品和新更新包拼成一个发行版。桌面工作流不会创建 Release/Tag；但仓库独立的 `publish-npm.yml` 会在 main 推送后自动发布 npm beta 并创建 GitHub 预发布，正式 latest 由稳定 tag 控制。

macOS 签名 CI 验证跨版本身份一致、复制安装、错误密码/证书、内容篡改拒绝及临时钥匙串清理。Windows 签名 CI 运行错误密码/证书、内容/签名/时间戳篡改及签名失败检查；真实隔离升级后验签落盘的 App、后端、启动包装器与 Update.exe，不启动 GUI。结果保存在构建 `result.json`、升级 `receipt.json` 与签名检查记录。构建、验签和隔离安装不能代替用户 GUI、干净机器或 SmartScreen 提示验收。

修复已有原生更新发行版的包装时，产品源码仍固定在 tag；Mac 打包脚本、成品校验、安装资源、mise 配置及发布资产校验器可取工作流提交。`replace_existing_assets` 仅用于明确批准的附件修复，不应重打同一已安装版本；正常更新提高版本号。后端携带固定路径的 `package.json` 清单，以实际版本读回确认升级。

Windows 新构建统一使用 `windows-Setup-{架构}.exe`，不以文件名判断签名状态；正式发布仍强制 self-signed 签名及验签，未签名候选不会进入发布上传步骤。Sparkle 更新签名不是 Apple Developer ID 或公证。正式 Sparkle 配置为 Secret `SMART_SEARCH_SPARKLE_EDDSA_PRIVATE_KEY`（Base64 编码的 32 字节 Ed25519 seed）与公开变量 `SMART_SEARCH_SPARKLE_PUBLIC_KEY`；公钥必须与 [仓库记录](packaging/macos/sparkle-public-key.json) 一致。后续发行复用这一身份，私钥只保存于受限加密备份与 GitHub Secrets，不进入仓库或构建附件。缺少正式密钥时仍能跑隔离更新测试，但不能上传正式 Sparkle 更新资产。 作者必须按 [macOS 证书生成与 Secrets 配置](../docs/macos-signing.md) 完成首次设置；此变更不提供正式证书。

## App 和 CLI 更新

设置只保留 App 更新；独立 CLI 在“CLI 与 Skills”页维护。Windows App 由 Velopack、macOS App 由 Sparkle 检查官方稳定源；启用时在到期后检查，间隔至少 24 小时，可关闭且保留手动检查。退出后没有检查服务。自动检查只取元数据，发现更新提示“更新/稍后”，同一会话不重复提示同一版本。

点击更新后由 SDK 下载和校验，优先使用适用差分，失败时按框架规则回退完整包。安装前保护草稿、自有任务、CLI 升级、环境和 Skills 写入，安全关闭 sidecar 后由框架安装重启。下载完成不代表安装完成，重启后核对 App 与内置引擎实际版本。不会强行停止外部 CLI。

独立 CLI 只在确认属于普通全局 npm 或全局 mise npm 时可更新。来源无法确认时显示原因；执行保留原管理器，补齐目标包私有 Python，读回实际运行结果后才成功。同版本未就绪可显式重试。复杂 mise 选项、项目范围、版本约束、未知或冲突来源保留手动说明，不改 PATH。普通探测只读；管理器写入期间保持 App 打开。

## 环境准备与 App/CLI 解耦

“CLI 与 Skills”用一个 CLI 安装/修复动作在内部完成检测、安装和验证。健康的 Node/npm、支持 venv/pip 的 Python 和明确来源的 CLI 优先复用。缺失时从 Node 官方 LTS 发行版和经校验的 uv/Astral CPython 准备运行环境，再安装锁定的 npm 稳定版 CLI；无需预装 mise，也不代装或登录 Codex/Claude Code。

新环境位于 `%LOCALAPPDATA%/SmartSearchTools` 或 `~/.local/share/smart-search-tools`，独立 npm prefix 在其 `cli` 子目录。它们不是 App 文件，关闭、更新或卸载 App 不会移除它们。AI 接入文件包含独立 Node 和 npm CLI 的绝对调用路径。Windows 为新安装补充自己的用户 PATH 项并提示重新打开 AI/终端；macOS 不修改 shell 配置，图形 AI 可以按技能中的完整路径调用。

“CLI 与 Skills”用勾选框统一列出所有 Agent 目标，区分 Skill 文件状态、独立 CLI 版本和实际 AI 调用。最新源是官方 npm 稳定包，下载通过 SHA512 与归档边界检查，只读取说明文件。默认每天检查并提示；用户勾选任一目标后主按钮可用，一次操作完成可信来源检查、目标复核、备份和同步。相同内容显示已是最新，不重复写入。备份路径在结果中显示，额外文件、未选目标与历史副本保留。Codex 使用 `.agents/skills`，Claude 尊重 `CLAUDE_CONFIG_DIR`，也支持 Cursor、Copilot、Gemini、OpenCode、Cline、Roo Code 等注册目标。更新会刷新独立 CLI 的本机调用说明。离线缓存不能冒充本次最新检查成功；CLI 未就绪不阻止正文同步，实际 AI 调用前仍需准备独立 CLI。检查不发收费请求，AI 内调用仍由用户验证。

安装失败保留已成功组件，从同一动作重试补缺。只有下载可取消；包管理器写入期间保持 App 打开。实现检查必须使用隔离配置、环境和技能目录；Windows x64 的实测不代表 macOS/ARM64 或真实 AI 会话已经验证。

## 双语界面与手册

App 在设置页选择自动、简体中文或 English，偏好独立于 CLI 保存。
App 将当前语言传给私有后端；切换保留草稿与任务，环境写入或 CLI 更新期间暂不可切换。
CLI 通过 `SMART_SEARCH_LANGUAGE` 和单次 `--lang` 选择语言，命令名、机器字段及来源原文不翻译。
共享语言资源位于 `src/smart_search/assets/i18n/messages.json`，Windows 直接嵌入，macOS 资源副本须保持字节一致。

用户入口见[双语手册](../docs/guide/README.md)，命令和配置参考通过
`python scripts/generate_references.py` 从当前实现更新。环境准备与完整语言切换从 v0.1.21 起提供；本地构建脚本不会覆盖已安装的 App。
