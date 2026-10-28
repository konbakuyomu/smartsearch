import AppKit
import SwiftUI

struct CLIManagementView: View {
    @ObservedObject var model: AppModel
    @ObservedObject private var manager: CLIInstallationManager
    var firstStep: Bool
    @State private var npmPath = ""
    @State private var selectedID = ""
    @State private var showingSettings = false
    @State private var pendingAction: SettingsAction?

    private enum SettingsAction {
        case install, uninstall, reconnect, chooseCLI
        case selectCLI(String)
        case npmPath(String)
    }

    init(model: AppModel, firstStep: Bool = false) {
        self.model = model
        self.firstStep = firstStep
        manager = model.cliManager
    }

    // Until detection ends nothing is known to be missing, so nothing is offered to install or choose.
    private var detected: Bool { !manager.busy && model.connection != .connecting }

    var body: some View {
        DesktopPanel {
            DesktopStepHeader(title: firstStep ? L("1. 准备本地环境") : L("本地环境"), subtitle: model.environmentStatus) {
                // Only a version check the user asked for shows progress.
                if manager.busy || manager.checking && model.isBusy.contains("cli.check") { ProgressView().controlSize(.small) }
                if detected {
                    if manager.npm == nil && manager.selected == nil {
                        Link(L("安装 Node.js"), destination: URL(string: "https://nodejs.org/en/download")!)
                            .buttonStyle(.borderedProminent)
                    } else if manager.canInstall && (manager.selected?.compatible != true || manager.updateAvailable) {
                        Button(installTitle) { Task { await model.manageCLI() } }
                            .buttonStyle(.borderedProminent).disabled(blocked || releaseUnavailable)
                    }
                }
                if model.connection != .ready {
                    Button(L("重新检测")) { Task { await model.reconnect() } }.disabled(blocked)
                }
                Button(L("环境详情…")) {
                    npmPath = manager.manualNpmPath
                    selectedID = manager.selected?.id ?? ""
                    showingSettings = true
                }
            }
            Text(model.environmentExplanation).font(.callout).foregroundStyle(.secondary)
            if detected && manager.selected?.compatible != true {
                HStack {
                    Link(L("手动下载 CLI"), destination: URL(string: "https://github.com/konbakuyomu/smartsearch/releases/latest")!)
                    Button(L("选择已有 CLI…")) { chooseCLI() }.disabled(blocked)
                }
            }
            if !manager.message.isEmpty && model.environmentExplanation != manager.message {
                Text(manager.message).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
            }
            if !manager.checkError.isEmpty {
                Text(L("检查更新失败，请稍后重试。")).font(.callout).foregroundStyle(.orange)
            }
        }
        .sheet(isPresented: $showingSettings, onDismiss: performPendingAction) {
            DetailSheet(L("本地环境")) {
                DesktopStepHeader(title: L("Smart Search CLI"), subtitle: model.environmentStatus) {
                    Button(L("重新检测")) { deferAction(.reconnect) }.disabled(blocked)
                    Button(L("检查更新")) { Task { await model.checkCLIVersion() } }
                        .disabled(manager.npm == nil || blocked)
                }
                if !manager.installations.isEmpty {
                    Picker(L("已发现的安装"), selection: $selectedID) {
                        ForEach(manager.installations) { item in Text(item.title).tag(item.id) }
                    }.disabled(blocked)
                    Button(L("使用所选安装")) { deferAction(.selectCLI(selectedID)) }.disabled(blocked || selectedID.isEmpty)
                }
                HStack {
                    Button(L("选择已有 CLI…")) { deferAction(.chooseCLI) }.disabled(blocked)
                    Link(L("手动下载 CLI"), destination: URL(string: "https://github.com/konbakuyomu/smartsearch/releases/latest")!)
                }
                Text(L("独立下载包解压后选择 smart-search 可执行文件，并保留同目录的运行文件。手动安装由你自行更新。"))
                    .font(.callout).foregroundStyle(.secondary)
                Divider()
                VStack(alignment: .leading, spacing: 8) {
                    Text(L("npm 环境")).font(.headline)
                    if let npm = manager.npm {
                        Text(L("npm {0} · {1}", npm.version, npm.npmPath))
                            .font(.callout).textSelection(.enabled)
                        Text(L("安装目录：{0}", npm.prefix))
                            .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    } else {
                        Text(L("未找到 npm")).foregroundStyle(.secondary)
                    }
                    TextField(L("npm 路径（留空自动查找）"), text: $npmPath)
                        .textFieldStyle(.roundedBorder).disabled(blocked)
                    HStack(spacing: 8) {
                        Button(L("选择文件…")) { chooseNpm() }.disabled(blocked)
                        Button(L("应用路径")) { deferAction(.npmPath(npmPath)) }.disabled(blocked)
                        Button(L("自动查找")) { deferAction(.npmPath("")) }.disabled(blocked)
                    }
                }
                Divider()
                VStack(alignment: .leading, spacing: 8) {
                    Toggle(L("自动检查 CLI 更新"), isOn: $manager.automaticallyChecks)
                    Text(L("启动时及每 24 小时检查。")).font(.caption).foregroundStyle(.secondary)
                    if let date = manager.checkedAt {
                        Text(L("上次检查：{0}", date.formatted(date: .abbreviated, time: .shortened)))
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                Divider()
                HStack(spacing: 8) {
                    Button(installTitle) { deferAction(.install) }
                        .disabled(!manager.canInstall || blocked || releaseUnavailable)
                    if manager.selected?.source == "npm" {
                        Spacer()
                        Button(L("卸载 CLI"), role: .destructive) { deferAction(.uninstall) }.disabled(blocked)
                    }
                }
                if !manager.checkError.isEmpty {
                    DisclosureGroup(L("错误详情")) {
                        Text(manager.checkError).font(.caption).textSelection(.enabled)
                    }
                }
            }
        }
    }

    private var blocked: Bool { manager.busy || manager.checking || !model.canInstallAppUpdate }
    private var releaseUnavailable: Bool { !manager.latestVersion.isEmpty && !manager.latestSupportsBinary }
    private var installTitle: String {
        if manager.selected == nil { return L("安装 CLI") }
        if manager.updateAvailable { return L("更新 CLI") }
        return L("修复 CLI")
    }
    private func deferAction(_ action: SettingsAction) {
        pendingAction = action
        showingSettings = false
    }

    private func performPendingAction() {
        guard let action = pendingAction else { return }
        pendingAction = nil
        Task {
            switch action {
            case .install: await model.manageCLI()
            case .uninstall: await model.manageCLI(remove: true)
            case .reconnect: await model.reconnect()
            case .npmPath(let path): await model.setNpmPath(path)
            case .selectCLI(let id): await model.selectCLI(id)
            case .chooseCLI: chooseCLI()
            }
        }
    }

    private func chooseCLI() {
        guard !blocked else { return }
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.message = L("请选择独立下载包中的 smart-search 可执行文件。")
        if panel.runModal() == .OK, let path = panel.url?.path { Task { await model.selectCLI(path, manual: true) } }
    }

    private func chooseNpm() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.message = L("选择与你的 Node.js 配套的 npm 文件。")
        if panel.runModal() == .OK, let path = panel.url?.path { npmPath = path }
    }
}
