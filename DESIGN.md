---
name: Smart Search for macOS
description: 配置、测试与 CLI/Skills 安装优先的原生配置器。
---

# Design System: Smart Search for macOS

## Overview

**Creative North Star: "原生桌面配置器"**

使用系统窗口、字体与控件建立熟悉感。Codex Tweaks 提供结构参考，Smart Search 保留自己的名称和图标。先呈现主要任务、必要状态与下一步行动，技术细节按需进入。

**Key Characteristics:** 原生、清楚、克制；真实状态；稳定留白。

范围为 `desktop/macos` 及下方 Windows 适配，依据原生布局、主视图和导航实现。原生令牌保存在 sidecar 的 `extensions.native`。历史 Windows/macOS 实机检查记录保留；本轮四页配置器、勾选框与单一操作的新增视觉验收单独记录。

## Colors

- **Primary:** 系统强调色 `Color.accentColor`；绿表示完成，橙表示进行中或提醒，红表示失败。
- **Neutral:** `Color(nsColor: .textBackgroundColor)` 承载内容，浅色为白色、深色随系统解析；正文使用默认前景，辅助信息使用 `.secondary`。
- 面板边界为 `.separatorColor.opacity(0.7)`；状态标签底色透明度为 `0.12`。

**The 语义颜色 Rule.** 保留系统 API，不以固定 Hex 替代；状态必须有文字依据。

## Typography

系统字体负责全部普通内容。页面标题用 `.title2.weight(.semibold)`，分组用 `.headline`，正文用 `.body`，补充信息用 `.callout`／`.caption`。JSON、路径和日志使用系统等宽字体；耗时使用 `.monospacedDigit()`。可读结果额外行距为 4 pt。

## Layout

几何单位均为 macOS pt。`DesktopMetrics`：内容最大宽度 920、页面留白 24、章节间距 24、面板留白 16、圆角 12。服务商编辑区留白 16，搜索输入 20、结果 24；分栏外不叠加页面留白。设置采用单一滚动内容区，最大宽度 800、页面留白 24、章节间距 24、标题与内容间距 12；紧凑面板使用水平留白 16、垂直留白 12、内容间距 8，标签与辅助说明间距 4。

窗口默认 1080 × 760，最小 920 × 620。主侧栏固定 220，可用原生工具栏按钮隐藏，保留 SwiftUI Scene 管理的标题栏和工具栏。内部分栏通过 `NSSplitViewController` 明确初始位置，并按页面保存调整后的宽度；内容切换只更新 hosting controller 内部视图。左侧 holding priority 为 251，右侧 250，均低于原生分隔条拖动优先级 490。窗口缩小时临时收窄，不覆盖用户偏好。

| 分栏 | 左栏最小／初始／最大 | 右栏最小 |
| --- | --- | --- |
| 服务商 | 184／220／280 | 400 |
| 搜索 | 280／320／360 | 360 |

| 工作区 | 结构 |
| --- | --- |
| 配置（默认） | 搜索框下方是统一滚动列表，意图路由为第一行；按能力分组列出服务商，保留草稿、保存、预览与就地测试/取消 |
| 测试 | 左侧六类配置测试和输入、右侧结果；选项按需查看，测试就地取消；同一时间一个业务测试 |
| CLI 与 Skills | CLI 状态与安装/更新/重试动作；Agent 勾选框列表和底部安装/更新按钮。检查、备份、同步组成一次操作，错误和备份路径就地显示 |
| 设置 | 项目信息和 GitHub、语言、外观、配置目录、App 更新。一个 App 更新主操作随状态变化；无常驻迁移或开发连接面板 |

## Elevation & Depth

内容保持平整，无自定义投影。依靠留白、文字和分隔建立层次；sheet 与 popover 使用系统浮层。

## Shapes

面板采用连续圆角及 1 pt 细边界；状态用 Capsule。按钮、输入和开关沿用原生形状。普通 GroupBox 只组织标题与内容。

## Components

- **Buttons:** 当前主要动作使用 `.borderedProminent`；运行中显示进度与文字，冲突时禁用。危险动作声明对应 role。
- **Settings rows:** 设置面板使用 `DesktopPanel(compact: true)`；说明靠左、控件靠右。自动更新开关保持原生尺寸，长说明允许换行。
- **Configuration directory:** 当前配置目录右侧提供“选择配置目录…”，使用自定义目录时才显示“恢复默认配置目录”。后端提供默认路径，目录切换保留草稿保护。
- **Inputs:** 字段按 metadata 使用 TextField／SecureField 或 Picker；当前有效值直接填入控件，placeholder 只用于空字段的输入示例。只有实际修改进入草稿，清空普通字段也会保存为空值。现有 Toggle 使用 `.switch`，保留系统焦点与键盘交互，字段来源等详情进入 popover。
- **Secrets:** macOS 客户端显式请求后，私有后端管道提供可编辑 Key，实际值绑定 SecureField 并由系统显示密码圆点；未配置时才显示输入提示。清空或“清除 Key”在保存时删除密钥，“保留”和放弃修改恢复当前值。环境变量字段保持只读；Key 不进入通用状态、详情或诊断，Web／CLI 状态保持脱敏。
- **Navigation:** `NavigationSplitView` 与 sidebar；配置、测试共用 `DesktopSplitView` 原生分栏。设置不增加第二套导航。配置和 Skills 底部保留操作区；全局重新读取仅出现在配置页，断线时提供重连。
- **Skills selection:** 使用原生 checkbox，含义是本次写入目标；取消勾选不会卸载。非冲突状态下，任一选择都使主按钮可用，不以缓存或内容差异禁用。完成后保留选择，无变化明确显示已是最新。
- **Providers:** 分组顺序为主搜索、文档检索、网页搜索、网页抓取、垂直检索；依据后端 `provider_profiles.capability`，不以必填字段或是否配置推断类型。多能力服务商只出现一次，详情说明全部声明能力和用途；实验性与显式调用限制保持可见。搜索覆盖名称、用途及全部能力，过滤不清除选择或草稿。
- **Disclosure:** 整行使用真实 Button，最小高度 30，展开箭头旋转 90°；动画 `easeInOut(0.18s)`，减少动态效果开启时禁用。提供展开状态的可访问值。
- **Language:** 语言变化时刷新列表、详情控件和菜单，保留外层 `NavigationSplitView` 的身份；页面选择留在稳定的父视图，草稿与搜索参数保留在 AppModel。运行标题从稳定 ID 重新取词。分栏 hosting controllers 明确传递 locale、colorScheme 和共用控件样式。
- **Sheet:** 560 × 480，留白 20；标题、“完成”、分隔与滚动内容。
- **Feedback:** 操作消息通过工具栏固定入口和系统 popover 呈现，不插入页面或改变内容高度。浮层位于工具栏下方，正文宽 360 pt、留白 16 pt；正文超过 320 pt 时独立滚动。完整文字可选取，关闭后可重新查看，显式清除后入口禁用。错误使用警示标题，普通消息保留中性语义；重复的主动操作仍有反馈，未改变的后台轮询错误不反复弹出。
- **Result:** 正文和来源优先，脱敏 JSON 按需展开；文本可选取，复制和导出说明范围。

## Do's and Don'ts

### Do:

- **Do** 复用原生组件和统一间距，保持任务与返回上下文。
- **Do** 为状态提供文字、为图标提供名称，并验证浅深色、缩放和键盘焦点。

### Don't:

- **Don't** 用 CSS 仿制品、固定色值或额外阴影替代原生系统。
- **Don't** 让技术详情抢占主要任务，或将编译、打包视为视觉验收。

## Windows adaptation

Windows 使用 WinUI 保留同样的任务层级。主导航为系统 NavigationView，内容使用语义背景与系统字体；标题 26、分组 18、正文 14、说明 12。页面章节相隔 24，紧凑面板留白 16，设置行以左侧说明、右侧控件组织。保留 Windows 外观选项。

分栏使用固定范围的 Grid 列与可用鼠标／键盘调整的 Thumb，按页面保存偏好；紧凑宽度改为上下布局。操作反馈通过工具栏 Flyout 显示，独立滚动且不改变页面高度。次要说明进入 Flyout，需要完整编辑或阅读的选项进入 ContentDialog。原生编译与视觉验收分别记录在 `docs/windows-ui-parity.md`。
