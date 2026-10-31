# App、CLI 与 Skill 的职责

App 只分发原生界面和原生安装管理器，不携带搜索引擎、Python 或 CLI。App 的版本更新由 Sparkle / Velopack 独立管理：每次启动检查一次；macOS 允许跳过指定版本，手动检查可重新发现；Windows 只有“立即更新”和“稍后”。

CLI 通过用户系统中的 npm 独立安装。首页第一步选择并连接 npm 管理的 CLI，之后配置服务商和 Skills。自动查找 npm 支持常见目录及 mise/nvm/Volta，允许手动指定；无效手动路径不回退。App 只读取所选 npm 的全局目录，不扫描或接管 PATH 中的 pip/uv 开发版。

App 在 CLI 缺失、损坏或协议不兼容时仍可通过选定的 npm 安装、修复、更新和卸载 CLI。绑定配套 Node.js 和原全局 prefix；更换或卸载 CLI 前停止 App 拥有的协议进程，保留配置和 Skills。App 不下载运行环境、不提权、不改全局 npm 配置或 PATH。

Skill 的目标清单、正文、状态、安装、备份和移除由 CLI 提供。安装的 Skill 使用稳定入口，完整使用说明通过 `smart-search agent-guide` 从当前 CLI 获取。自动维护仅针对用户已接入的目标，遇到个人修改保留文件并报告；CLI 升级后的首次使用与日常检查均不依赖 App。

App 与 CLI 通过 `--desktop-capabilities` 和 JSON 行协议协商兼容性，不比较两者产品版本是否相同。

Windows App 也可以连接 WSL 发行版里的 CLI：列出发行版不会启动它们，只自动探测正在运行或已被选中的发行版，未运行的需用户点击“检测 WSL”。探测用登录 shell、失败再用交互 shell 执行 `--desktop-capabilities`，记下其中的 `launch_command`，之后以 `wsl.exe -d <发行版> --cd ~ --exec <launch_command> --desktop-backend` 直接启动，通过标准输入输出通信。App 在 WSL 中执行的命令都从 Linux 主目录开始，以免 mise、npm 把 Windows 用户目录里的配置当作项目配置。WSL 安装与本机安装在同一列表中二选一，配置、Skills 和活动记录都属于所选的一边。WSL 里用 npm 安装的 CLI 由 App 通过该发行版自己的 Node.js 与 npm-cli.js 安装或更新：在找到它们的同一个 shell 中以参数数组运行（`bash -lc '"$@"' …`），不拼接命令行，装回 CLI 所在的前缀，新装时用 npm 的全局前缀，之后执行 mise/asdf 的 reshim。目录必须当前用户可写，App 不使用 sudo；root 拥有的前缀、mise 的 npm 后端和无法识别的安装只显示终端命令。没有 CLI 的 Windows npm 环境和已探测的发行版列为安装目标。App 不在 WSL 中卸载 CLI。

npm 主包通过精确版本 optionalDependencies 选择 macOS / Windows / Linux 的 x64 或 arm64 平台包。平台包携带冻结后的 Python 解释器、依赖及资源；启动器隔离外部 Python/venv/Conda/PyInstaller 环境。没有 postinstall，不回退到系统 Python。构建管线先验证六个平台包的真实 npm 安装，再发布平台包，最后发布主包；新平台包需配置 npm 发布权限。Linux 要求 glibc 2.35+。

CLI 默认启动时及每 24 小时检查 npm latest，只提示更新。成功时间、失败重试间隔、开关和 npm 环境身份独立持久化。更换 npm 环境清空旧检查缓存；失败不抹掉最近成功结果。App 只安装 npm 元数据声明了 `smartSearchBinary` 的版本，即自带运行时的平台包；没有这个声明的旧版 Python 安装包可能顺带引导 Python，App 既不安装也不探测。

自动维护回执还记录目标原先选择的 CLI 安装与配置目录。其他 CLI 副本不会改绑已接入的 Skill；切换绑定必须显式同步。
