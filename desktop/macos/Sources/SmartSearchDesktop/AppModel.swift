import AppKit
import Foundation
import OSLog
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
    private let connectionLog = Logger(subsystem: "com.smartsearch.desktop", category: "BackendConnection")
    enum ExitChoice {
        case background
        case stopAndQuit
        case `return`
    }

    enum ConnectionState: Equatable {
        case disconnected
        case connecting
        case ready
        case failed

        var title: String {
            switch self {
            case .disconnected: return L("未连接")
            case .connecting: return L("正在连接")
            case .ready: return L("已连接")
            case .failed: return L("后端失联")
            }
        }

        var symbol: String {
            switch self {
            case .disconnected: return "circle"
            case .connecting: return "arrow.triangle.2.circlepath"
            case .ready: return "checkmark.circle.fill"
            case .failed: return "exclamationmark.triangle.fill"
            }
        }
    }

    @Published var selectedDestination: Destination = .overview
    @Published private(set) var connection: ConnectionState = .disconnected
    @Published private(set) var state: DesktopState?
    @Published private(set) var lastStateRefresh: Date?
    @Published private(set) var activityRuns: [ActivityRun] = []
    @Published private(set) var activityErrors: [String] = []
    @Published private(set) var currentResult: JSONValue?
    @Published private(set) var currentResultCommand: String?
    @Published private(set) var activityDetails: JSONValue?
    @Published private(set) var activityResultRunID: String?
    @Published private(set) var activityResult: JSONValue?
    @Published var selectedActivity: ActivityRun?
    @Published private(set) var cliStatus: JSONValue?
    @Published private(set) var skillStatuses: [String: String] = [:]
    @Published private(set) var skillsState: JSONValue?
    private var skillSelectionInitialized = false
    @Published private(set) var updateResult: JSONValue? {
        didSet {
            if let installed = updateResult?["installed_cli"] { cliStatus = installed }
        }
    }
    @Published private(set) var environmentState: JSONValue?
    @Published var errorMessage: String?
    @Published private(set) var errorPresentationID = UUID()
    @Published var noticeMessage: String?
    @Published private(set) var isBusy: Set<String> = []
    private var operations = OperationState()

    @Published var configDraft: [String: String] = [:]
    private var configSecrets: [String: String] = [:]
    @Published var clearSecretKeys: Set<String> = []
    @Published private(set) var configPreview: JSONValue?
    @Published var selectedCommandID: String?
    @Published var commandValues: [String: String] = [:]
    @Published var commandBooleans: [String: Bool] = [:]
    @Published var selectedSkillTargets: Set<String> = []
    @Published var activityEnabled = true
    @Published var observedDirectories: [String]
    @Published var backendPathOverride: String
    @Published var requestTimeoutSeconds: Double
    @Published private(set) var languagePreference: String

    @Published private(set) var appUpdatePreparing = false
    @Published private(set) var managingCLI = false
    let cliManager = CLIInstallationManager()
    private(set) var terminationReady = false
    lazy var appUpdater: AppUpdater = {
        let updates = AppUpdater()
        updates.canInstall = { [weak self] in self?.canInstallAppUpdate == true }
        updates.prepareInstall = { [weak self] in await self?.prepareForAppUpdate() ?? false }
        updates.recoverInstall = { [weak self] in
            guard let self else { return }
            self.appUpdatePreparing = false
            self.terminationReady = false
            await self.connect()
        }
        return updates
    }()
    var canInstallAppUpdate: Bool {
        configDraft.isEmpty && clearSecretKeys.isEmpty && !hasOwnedActiveRuns &&
        !isUpdatingCLI && !isBusy.contains("connect") && !environmentBusy && !skillsBusy && !configOperationBusy && !appUpdatePreparing
    }
    private let backend = BackendClient()
    private var eventTask: Task<Void, Never>?
    private var ownedActiveRunIDs: Set<String> = []
    @Published private var ownedRunResults = OwnedRunResultStore(capacity: 100)
    private var selectedBusinessRunID: String?
    private var intentionalShutdown = false

    private enum DefaultsKey {
        static let backendPath = "SmartSearchDesktop.backendPathOverride"
        static let timeout = "SmartSearchDesktop.requestTimeoutSeconds"
        static let observedDirectories = "SmartSearchDesktop.observedDirectories"
    }

    init() {
        let savedLanguage = UserDefaults.standard.string(forKey: Localization.preferenceKey) ?? "auto"
        let validLanguage = ["auto", "zh", "en"].contains(savedLanguage)
        languagePreference = validLanguage ? savedLanguage : "auto"
        backendPathOverride = UserDefaults.standard.string(forKey: DefaultsKey.backendPath) ?? ""
        let storedTimeout = UserDefaults.standard.double(forKey: DefaultsKey.timeout)
        requestTimeoutSeconds = storedTimeout == 0 ? 30 : min(max(storedTimeout, 5), 300)
        observedDirectories = UserDefaults.standard.stringArray(forKey: DefaultsKey.observedDirectories) ?? []
        appUpdater.start()
        cliManager.startAutomaticChecks()
        Task {
            // The last detection connects at once; the environment is detected again in the background later.
            let restored = backendPathOverride.isEmpty && cliManager.restoreLastDetection()
            if restored { await connect(detect: false) }
            // Without one, or when its CLI no longer starts, detection runs in view.
            let detectedInView = !restored || connection != .ready
            if detectedInView { await connect() }
            if !detectedInView && connection == .ready { await redetectEnvironment(quietly: true) }
            await cliManager.checkAutomatically(onLaunch: true)
            if !validLanguage { noticeMessage = L("无法读取已保存的显示偏好，已使用默认设置。原配置文件未修改。") }
        }
    }

    deinit {
        eventTask?.cancel()
    }

    var hasOwnedActiveRuns: Bool { !ownedActiveRunIDs.isEmpty }
    var isSearchRunning: Bool {
        guard let selectedBusinessRunID else { return false }
        return ownedActiveRunIDs.contains(selectedBusinessRunID)
    }
    var interfaceLocale: Locale { Locale(identifier: Localization.resolve(languagePreference)) }
    var isUpdatingCLI: Bool { managingCLI || isBusy.contains("cli.update") || updateResult?["cli_update"]?["status"]?.stringValue == "running" }
    var environmentBusy: Bool { isBusy.contains("environment.request") || environmentState?["busy"]?.boolValue == true }
    var skillsBusy: Bool { isBusy.contains("skills.sync") || skillsState?["busy"]?.boolValue == true }
    var skillsChecking: Bool { isBusy.contains("skills.check") || isBusy.contains("skills.catalog") || skillsState?["checking"]?.boolValue == true }
    var selectedCommand: CommandCatalogEntry? {
        guard let selectedCommandID else { return nil }
        return state?.commands.first(where: { $0.id == selectedCommandID })
    }

    // detect: false connects to the CLI already selected, without detecting the environment first.
    func connect(detect: Bool = true) async {
        guard !isUpdatingCLI && !environmentBusy else { noticeMessage = L("环境操作或 CLI 更新正在进行，请等待完成。"); return }
        guard !isBusy.contains("connect") else { return }
        clearOperations()
        guard begin("connect") else { return }
        defer { end("connect") }
        intentionalShutdown = false
        connection = .connecting
        errorMessage = nil
        let started = Date()
        do {
            await backend.setTimeout(seconds: requestTimeoutSeconds)
            if backendPathOverride.isEmpty {
                if detect { await cliManager.discover() }
                guard let installation = cliManager.selected, installation.compatible else {
                    intentionalShutdown = true
                    await backend.shutdown()
                    connection = .disconnected
                    state = nil
                    return
                }
                try await backend.start(backendURL: URL(fileURLWithPath: installation.executable), arguments: installation.arguments, environment: installation.environment)
            } else {
                try await backend.start(backendURL: BackendLocator.resolvedURL(overridePath: backendPathOverride))
            }
            startEventListener()
            let snapshot = try await backend.initialize(enableUpdateChecks: false, language: Localization.language, independentCLI: backendPathOverride.isEmpty)
            applyState(snapshot)
            connection = .ready
            connectionLog.info("Backend initialized in \(Int(Date().timeIntervalSince(started) * 1000), privacy: .public) ms")
            await refreshActivity()
            await refreshCLIStatus()
        } catch {
            connection = .failed
            connectionLog.error("Backend initialization failed")
            present(error)
        }
    }

    var environmentStatus: String {
        if cliManager.busy || connection == .connecting && cliManager.selected == nil { return L("正在检测本地环境…") }
        guard let installation = cliManager.selected else {
            return cliManager.npm == nil ? L("尚未找到 Node.js/npm 或可用的 Smart Search CLI") : L("Node.js/npm 已就绪，等待准备 Smart Search CLI")
        }
        if !installation.compatible { return L("{0} · {1} · 需要更新或修复", installation.source, installation.version) }
        if cliManager.updateAvailable { return L("{0} · 可更新至 {1}", installation.version, cliManager.latestVersion) }
        return connection == .ready ? L("{0} · 已就绪", installation.version)
            : connection == .connecting ? L("{0} · 正在连接", installation.version) : L("{0} · 尚未连接", installation.version)
    }

    var environmentExplanation: String {
        let unavailable = !cliManager.latestVersion.isEmpty && !cliManager.latestSupportsBinary
        if let selected = cliManager.selected, !selected.compatible {
            return selected.note + (unavailable ? "\n" + L("npm 上尚未发布兼容版本。可手动下载独立 CLI，或稍后重新检查。") : "")
        }
        if !cliManager.message.isEmpty { return cliManager.message }
        if let selected = cliManager.selected, !selected.note.isEmpty { return selected.note }
        if connection == .failed { return L("Smart Search CLI 已找到，但连接失败。请重新检测；错误详情显示在上方。") }
        if unavailable && cliManager.selected == nil { return L("npm 上尚未发布兼容版本。可手动下载独立 CLI，或稍后重新检查。") }
        return L("App 通过本机独立安装的 Smart Search CLI 读取配置并运行搜索，两者分别安装和更新。检测会复用已有的 mise 或 npm 安装。")
    }

    func selectCLI(_ id: String, manual: Bool = false) async {
        guard canInstallAppUpdate, !cliManager.busy, !cliManager.checking else { return }
        intentionalShutdown = true
        await backend.shutdown()
        state = nil
        if manual { cliManager.setCliPath(id) } else { cliManager.selectInstallation(id) }
        backendPathOverride = ""
        UserDefaults.standard.removeObject(forKey: DefaultsKey.backendPath)
        await connect()
    }

    func setNpmPath(_ path: String) async {
        guard canInstallAppUpdate, !cliManager.busy, !cliManager.checking else { return }
        intentionalShutdown = true
        await backend.shutdown()
        state = nil
        cliManager.setNpmPath(path)
        backendPathOverride = ""
        UserDefaults.standard.removeObject(forKey: DefaultsKey.backendPath)
        await connect()
        await cliManager.checkAutomatically(onLaunch: true)
    }

    func manageCLI(remove: Bool = false) async {
        guard canInstallAppUpdate, !cliManager.busy, !cliManager.checking else { return }
        if !remove {
            await cliManager.checkVersion()
            guard !cliManager.latestVersion.isEmpty, cliManager.checkError.isEmpty else { noticeMessage = cliManager.checkError; return }
            guard cliManager.latestSupportsBinary else {
                noticeMessage = L("npm 上尚未发布自带运行时的 CLI，请等待新版发布后再安装。")
                return
            }
        }
        let alert = NSAlert()
        alert.messageText = remove ? L("卸载所选 CLI？") : L("安装或更新独立 CLI？")
        alert.informativeText = (cliManager.selected?.id ?? cliManager.npm?.prefix ?? "") + (remove ? "" : "\n" + L("CLI 最新版本：{0}", cliManager.latestVersion)) + "\n\n" + L("只处理所选 CLI；配置和 Skills 保留。App 自身不会更新。")
        alert.addButton(withTitle: remove ? L("卸载 CLI") : L("继续"))
        alert.addButton(withTitle: L("取消"))
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        managingCLI = true
        intentionalShutdown = true
        eventTask?.cancel()
        await backend.shutdown()
        connection = .disconnected
        state = nil
        var failure: Error?
        do {
            if remove { try await cliManager.uninstall() } else { try await cliManager.installOrRepair(expectedVersion: cliManager.latestVersion) }
            noticeMessage = cliManager.message
        } catch { failure = error }
        managingCLI = false
        await connect()
        if let failure { present(failure) }
    }

    func reconnect() async {
        await connect()
    }

    // Detects the local environment again while connected. Another CLI is connected at once unless that would
    // interrupt work; a CLI that is no longer found never replaces the working connection.
    func redetectEnvironment(quietly: Bool) async {
        switch await cliManager.redetect(quietly: quietly) {
        case .unchanged:
            return
        case .missing:
            noticeMessage = L("再次检测没有找到正在使用的 Smart Search CLI，当前连接保持不变。如已卸载或移动，请在“环境详情…”中重新检测。")
        case .changed:
            // Switching restarts the backend, so it waits for the same moments as an App update.
            guard canInstallAppUpdate else {
                noticeMessage = L("Smart Search CLI 有变化。完成当前任务后，点击右上角的刷新即可切换。")
                return
            }
            cliManager.showRedetection()
            await connect(detect: false)
            if connection == .ready, let selected = cliManager.selected {
                noticeMessage = L("Smart Search CLI 有变化，已切换到 {0}。", selected.version)
            }
        }
    }

    // A manual refresh also detects the local environment again, in view.
    func refreshWorkspace() async {
        await refreshState()
        guard backendPathOverride.isEmpty, connection == .ready, begin("environment.detect") else { return }
        defer { end("environment.detect") }
        await redetectEnvironment(quietly: false)
    }

    // Only a version check the user asked for shows progress; automatic ones report just their result.
    func checkCLIVersion() async {
        guard begin("cli.check") else { return }
        defer { end("cli.check") }
        await cliManager.checkVersion()
    }

    func setLanguage(_ preference: String) async {
        guard !environmentBusy && !skillsBusy && !isUpdatingCLI && !isBusy.contains("language") else { return }
        guard begin("language") else { return }
        defer { end("language") }
        do {
            var snapshot: JSONValue?
            if connection == .ready {
                snapshot = try await backend.request(method: "language.set", params: .object(["lang": .string(Localization.resolve(preference))]))
            }
            UserDefaults.standard.set(preference, forKey: Localization.preferenceKey)
            languagePreference = preference
            errorMessage = nil
            noticeMessage = nil
            if let snapshot {
                applyState(snapshot)
            } else if let cached = state?.raw {
                // Offline language changes still rebuild the cached field labels.
                // Keep the last refresh time: this did not read a new backend state.
                state = DesktopState(cached)
                if let selectedBusinessRunID, let descriptor = ownedRunResults.descriptor(for: selectedBusinessRunID) {
                    currentResultCommand = localizedLabel(descriptor)
                }
            }
        } catch { present(error) }
    }

    func refreshState() async {
        guard connection == .ready else { return }
        guard begin("state") else { return }
        defer { end("state") }
        do {
            applyState(try await backend.request(method: "get_state"))
        } catch {
            present(error)
        }
    }

    func refreshActivity(repeatFeedback: Bool = false) async {
        guard connection == .ready, !isBusy.contains("activity") else { return }
        guard begin("activity") else { return }
        defer { end("activity") }
        var params: [String: JSONValue] = [:]
        let directories = Array(Set(([state?.configDirectory].compactMap { $0 }) + observedDirectories)).sorted()
        if !directories.isEmpty {
            params["directories"] = .array(directories.map(JSONValue.string))
        }
        params["limit"] = .number(1_000)
        do {
            let result = try await backend.request(method: "activity.list", params: .object(params))
            activityRuns = (result["runs"]?.arrayValue ?? []).compactMap(ActivityRun.init).sorted { lhs, rhs in
                (lhs.updatedAt ?? .distantPast) > (rhs.updatedAt ?? .distantPast)
            }
            activityErrors = (result["errors"]?.arrayValue ?? []).compactMap { item in
                let directory = item["config_dir"]?.displayString ?? ""
                let message = item["error"]?.displayString ?? L("活动记录不可读，当前状态未知。")
                return directory.isEmpty ? message : "\(directory)：\(message)"
            }
            activityEnabled = result["enabled"]?.boolValue ?? activityEnabled
            if result["ok"]?.boolValue == false {
                let message = L("一个或多个配置目录的活动记录不可读；可读取的记录仍已显示，其他状态未知。")
                if repeatFeedback { showError(message) } else { errorMessage = message }
            }
            await refreshSelectedActivity(repeatFeedback: repeatFeedback)
        } catch {
            present(error, repeatFeedback: repeatFeedback)
        }
    }

    func refreshCLIStatus() async {
        guard connection == .ready else { return }
        guard begin("cli.status") else { return }
        defer { end("cli.status") }
        do {
            cliStatus = try await backend.request(method: "cli.status")
        } catch {
            present(error)
        }
    }

    func refreshSkillStatus() async {
        await skillsAction("skills.catalog")
    }

    func skillsAction(_ method: String, params: JSONValue = .object([:])) async {
        guard connection == .ready, !skillsBusy else { return }
        guard begin(method) else { return }
        defer { end(method) }
        do {
            let result = try await backend.request(method: method, params: params)
            skillsState = result
            skillStatuses = Dictionary(uniqueKeysWithValues: (result["targets"]?.arrayValue ?? []).compactMap { value in
                guard let target = SkillTarget(value), let status = target.status else { return nil }
                return (target.id, status)
            })
        } catch {
            present(error)
        }
    }

    func enter(_ destination: Destination) async {
        switch destination {
        case .activity:
            await refreshActivity()
        case .integration:
            await refreshCLIStatus()
            await refreshSkillStatus()
        case .overview, .providers, .search, .settings:
            await refreshState()
        }
    }

    func applyTimeout() {
        requestTimeoutSeconds = min(max(requestTimeoutSeconds, 5), 300)
        UserDefaults.standard.set(requestTimeoutSeconds, forKey: DefaultsKey.timeout)
        Task { await backend.setTimeout(seconds: requestTimeoutSeconds) }
        noticeMessage = L("后续请求将使用 {0} 秒超时。", "\(Int(requestTimeoutSeconds))")
    }

    func saveBackendOverride(_ path: String) {
        backendPathOverride = path.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(backendPathOverride, forKey: DefaultsKey.backendPath)
    }

    func chooseBackendExecutable() {
        let panel = NSOpenPanel()
        panel.title = L("选择开发环境后端")
        panel.prompt = L("选择")
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        saveBackendOverride(url.path)
    }

    func chooseConfigDirectory() {
        let panel = NSOpenPanel()
        panel.title = L("选择 Smart Search 配置目录")
        panel.prompt = L("使用此目录")
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        Task { await selectProfile(url.path) }
    }

    func selectProfile(_ directory: String) async {
        guard connection == .ready else { return }
        guard configDraft.isEmpty && clearSecretKeys.isEmpty else {
            showError(L("还有未保存的修改，请先保存或放弃，再切换配置目录。"))
            return
        }
        guard begin("profile") else { return }
        defer { end("profile") }
        do {
            applyState(try await backend.request(method: "profile.select", params: .object(["config_dir": .string(directory)])))
            await refreshActivity()
        } catch {
            present(error)
        }
    }

    func restoreDefaultConfigDirectory() async {
        guard let directory = state?.defaultConfigDirectory, !directory.isEmpty,
              state?.isDefaultConfigDirectory == false else { return }
        await selectProfile(directory)
    }

    func addObservedDirectory() {
        let panel = NSOpenPanel()
        panel.title = L("添加要观察的配置目录")
        panel.prompt = L("添加")
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        guard !observedDirectories.contains(url.path) else { return }
        observedDirectories.append(url.path)
        persistObservedDirectories()
        Task { await refreshActivity() }
    }

    func removeObservedDirectory(_ directory: String) {
        observedDirectories.removeAll { $0 == directory }
        persistObservedDirectories()
        Task { await refreshActivity() }
    }

    func draftBinding(for field: ConfigField) -> Binding<String> {
        Binding(
            get: {
                if self.clearSecretKeys.contains(field.key) { return "" }
                return self.configDraft[field.key] ?? self.currentConfigValue(for: field)
            },
            set: { self.setDraft($0, for: field) }
        )
    }

    private func currentConfigValue(for field: ConfigField) -> String {
        if field.isSecret { return configSecrets[field.key] ?? "" }
        return state?.effectiveValue(for: field) ?? field.defaultValue
    }

    func setDraft(_ value: String, for field: ConfigField) {
        guard !isEnvironmentReadOnly(field), !isBusy.contains("save") else { return }
        configPreview = nil
        if field.isSecret && value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            if state?.hasSecretValue(for: field) == true {
                clearSecret(field)
            } else {
                keepSecret(field)
            }
            return
        }
        clearSecretKeys.remove(field.key)
        if value == currentConfigValue(for: field) {
            configDraft.removeValue(forKey: field.key)
        } else {
            configDraft[field.key] = value
        }
    }

    func clearSecret(_ field: ConfigField) {
        guard field.isSecret, !isEnvironmentReadOnly(field), !isBusy.contains("save") else { return }
        configPreview = nil
        configDraft.removeValue(forKey: field.key)
        clearSecretKeys.insert(field.key)
    }

    func keepSecret(_ field: ConfigField) {
        guard !isBusy.contains("save") else { return }
        configPreview = nil
        clearSecretKeys.remove(field.key)
        configDraft.removeValue(forKey: field.key)
    }

    func isEnvironmentReadOnly(_ field: ConfigField) -> Bool {
        state?.source(for: field) == "environment"
    }

    func draftStatus(for field: ConfigField) -> String {
        if isEnvironmentReadOnly(field) { return L("由环境变量提供，只读") }
        if clearSecretKeys.contains(field.key) { return L("将在保存时清除") }
        if configDraft[field.key] != nil {
            return field.isSecret ? L("将在保存时替换") : L("将在保存时更新")
        }
        if field.isSecret {
            return state?.hasSecretValue(for: field) == true ? L("保持当前密钥") : L("未配置")
        }
        return L("未修改")
    }

    func resetConfigDraft() {
        configDraft.removeAll()
        clearSecretKeys.removeAll()
        configPreview = nil
    }

    func previewConfig() async {
        guard connection == .ready else { return }
        guard begin("preview") else { return }
        defer { end("preview") }
        configPreview = nil
        let parameters = configMutationParameters(includeRevision: false)
        do {
            let preview = try await backend.request(method: "config.preview", params: parameters)
            if parameters == configMutationParameters(includeRevision: false) { configPreview = preview }
        } catch {
            present(error)
        }
    }

    func saveConfig() async {
        guard connection == .ready else { return }
        guard let revision = state?.revision else {
            showError(L("没有可用的配置版本，请先刷新后再保存。"))
            return
        }
        guard begin("save") else { return }
        defer { end("save") }
        var params = configMutationParameters(includeRevision: false).objectValue ?? [:]
        params["revision"] = revision
        do {
            let result = try await backend.request(method: "config.apply", params: .object(params))
            guard result["ok"]?.boolValue == true else {
                showError(result["error_type"]?.stringValue == "conflict"
                    ? L("配置已被其他进程修改；你改的内容还在，请刷新后核对。")
                    : L("后端没有保存配置；你改的内容还在。"))
                return
            }
            // config.apply returns a compact status snapshot; get_state restores the
            // metadata and command catalog that the native form needs.
            applyState(try await backend.request(method: "get_state"))
            resetConfigDraft()
            noticeMessage = L("配置已保存。后续新任务会使用新版本；正在运行的任务不受影响。")
        } catch {
            present(error)
        }
    }

    func testProvider(_ provider: String) async {
        guard connection == .ready, let state else { return }
        guard begin("test:\(provider)") else { return }
        defer { end("test:\(provider)") }
        let providerKeys = Set(state.fields.filter { $0.provider == provider }.map(\.key))
        var overrides = configDraft.reduce(into: [String: JSONValue]()) { partial, item in
            if providerKeys.contains(item.key) {
                partial[item.key] = .string(item.value)
            }
        }
        // An explicit Clear is a draft value too; an empty string is never a masked placeholder.
        for key in clearSecretKeys where providerKeys.contains(key) {
            overrides[key] = .string("")
        }
        do {
            let result = try await backend.request(method: "provider.test", params: .object([
                "provider": .string(provider),
                "overrides": .object(overrides),
            ]))
            guard result["ok"]?.boolValue == true, let runID = result["run_id"]?.stringValue else {
                showError(L("后端未能开始测试；配置没有改变。"))
                return
            }
            ownedActiveRunIDs.insert(runID)
            ownedRunResults.register(runID: runID, kind: .providerTest, label: L("测试 {0}", "\(provider)"), providerID: provider)
            trackRun(runID, key: "test:\(provider)")
            await recoverRun(runID)
            await refreshActivity()
        } catch {
            present(error)
        }
    }

    func selectCommand(_ id: String?) {
        selectedCommandID = id
        commandValues.removeAll()
        commandBooleans.removeAll()
        guard let command = selectedCommand else { return }
        for field in command.fields {
            if field.isBoolean {
                commandBooleans[field.name] = field.defaultValue?.boolValue ?? false
            } else if let defaultValue = field.defaultValue?.stringValue, !defaultValue.isEmpty {
                commandValues[field.name] = defaultValue
            }
        }
    }

    func commandBinding(for field: CommandField) -> Binding<String> {
        Binding(
            get: { self.commandValues[field.name] ?? "" },
            set: { self.commandValues[field.name] = $0 }
        )
    }

    func booleanBinding(for field: CommandField) -> Binding<Bool> {
        Binding(
            get: { self.commandBooleans[field.name] ?? false },
            set: { value in
                self.commandBooleans[field.name] = value
                if value, field.name == "stream" { self.commandBooleans["no_stream"] = false }
                if value, field.name == "no_stream" { self.commandBooleans["stream"] = false }
            }
        )
    }

    func startSelectedCommand() async {
        guard connection == .ready, let command = selectedCommand else { return }
        let missing = CommandArgumentBuilder.missingRequired(for: command, values: commandValues, booleans: commandBooleans)
        guard missing.isEmpty else {
            showError(L("请填写必填项：{0}。", "\(missing.map(\.label).joined(separator: "、"))"))
            return
        }
        guard begin("run:\(command.id)") else { return }
        defer { end("run:\(command.id)") }
        do {
            let arguments = CommandArgumentBuilder.arguments(for: command, values: commandValues, booleans: commandBooleans)
            let result = try await backend.request(method: "run.start", params: .object([
                "command": .string(command.id),
                "arguments": .array(arguments.map(JSONValue.string)),
            ]))
            guard result["ok"]?.boolValue == true, let runID = result["run_id"]?.stringValue else {
                showError(L("后端未能开始此操作。"))
                return
            }
            ownedActiveRunIDs.insert(runID)
            ownedRunResults.register(runID: runID, kind: .business, label: command.label, commandID: command.id)
            trackRun(runID, key: "run:\(command.id)")
            selectedBusinessRunID = runID
            currentResult = nil
            currentResultCommand = state?.commands.first { $0.id == command.id }?.label ?? command.label
            noticeMessage = L("操作已开始，进度会显示在活动页。")
            await recoverRun(runID)
            await refreshActivity()
        } catch {
            present(error)
        }
    }

    func cancel(_ run: ActivityRun) async {
        guard ownedActiveRunIDs.contains(run.runID), run.isActive, connection == .ready else { return }
        guard begin("cancel:\(run.runID)") else { return }
        defer { end("cancel:\(run.runID)") }
        do {
            let result = try await backend.request(method: "run.cancel", params: .object(["run_id": .string(run.runID)]))
            if result["ok"]?.boolValue == true {
                if ownedActiveRunIDs.contains(run.runID) { trackRun(run.runID, key: "cancel:\(run.runID)") }
                await recoverRun(run.runID)
                noticeMessage = L("已请求取消，等待后端确认最终状态。")
            } else {
                showError(L("后端未接受取消请求；任务仍保持原状态。"))
            }
        } catch {
            present(error)
        }
    }

    func canCancel(_ run: ActivityRun) -> Bool {
        ownedActiveRunIDs.contains(run.runID) && run.isActive
    }

    private func refreshSelectedActivity(repeatFeedback: Bool) async {
        guard selectedDestination == .activity, let selected = selectedActivity else { return }
        guard let current = activityRuns.first(where: { $0.runID == selected.runID }) else {
            selectedActivity = nil
            activityDetails = nil
            activityResultRunID = nil
            activityResult = nil
            return
        }
        await showActivityDetails(current, preservingContent: true, repeatFeedback: repeatFeedback)
    }

    func showActivityDetails(_ run: ActivityRun, preservingContent: Bool = false, repeatFeedback: Bool = true) async {
        let selectionChanged = selectedActivity?.runID != run.runID
        selectedActivity = run
        if selectionChanged || !preservingContent {
            activityDetails = nil
            activityResultRunID = nil
            activityResult = nil
        }
        guard connection == .ready else { return }
        guard begin("details:\(run.runID)") else { return }
        defer { end("details:\(run.runID)") }
        var params: [String: JSONValue] = ["run_id": .string(run.runID)]
        if let directory = run.configDirectory { params["config_dir"] = .string(directory) }
        do {
            // activity.details carries only protocol-approved, redacted metadata.
            let result = try await backend.request(method: "activity.details", params: .object(params))
            guard selectedActivity?.runID == run.runID else { return }
            activityDetails = result.redacted()
        } catch {
            guard selectedActivity?.runID == run.runID else { return }
            activityDetails = .object(["ok": .bool(false), "error": .string(error.localizedDescription)])
            present(error, repeatFeedback: repeatFeedback)
        }
    }

    var skillTargetsToUpdate: [String] {
        (skillsState?["targets"]?.arrayValue ?? []).compactMap { row in
            guard let id = row["target"]?.stringValue, selectedSkillTargets.contains(id),
                  row["needs_update"]?.boolValue == true else { return nil }
            return id
        }.sorted()
    }

    func installSelectedSkills() async {
        let targets = skillTargetsToUpdate
        guard !environmentBusy, !isUpdatingCLI, !skillsBusy, !skillsChecking,
              !targets.isEmpty, skillsState?["can_sync"]?.boolValue == true else { return }
        let plan = skillsState?["plan_id"]?.stringValue ?? ""
        let paths = (skillsState?["targets"]?.arrayValue ?? []).filter { targets.contains($0["target"]?.stringValue ?? "") }
            .map { ($0["label"]?.displayString ?? "") + "\n" + ($0["path"]?.displayString ?? "") }.joined(separator: "\n\n")
        let alert = NSAlert()
        alert.messageText = L("更新所选 Skills")
        alert.informativeText = L("来源版本：{0}\n{1}\n将同步所选目标的托管文件；不同内容先备份，额外文件保留。", skillsState?["source"]?["version"]?.displayString ?? "", paths)
        alert.addButton(withTitle: L("备份并更新"))
        alert.addButton(withTitle: L("取消"))
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        await skillsAction("skills.sync", params: .object(["targets": .array(targets.map(JSONValue.string)), "confirm": .bool(true), "plan_id": .string(plan)]))
    }

    func removeSelectedSkills() async {
        guard !skillsBusy, !skillsChecking, !isUpdatingCLI, !selectedSkillTargets.isEmpty else { return }
        let alert = NSAlert()
        alert.messageText = L("移除所选 Skills？")
        alert.informativeText = L("所选 Skill 文件会移入备份目录，CLI 和配置保留。")
        alert.addButton(withTitle: L("移除 Skills"))
        alert.addButton(withTitle: L("取消"))
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        await skillsAction("skills.remove", params: .object(["targets": .array(selectedSkillTargets.sorted().map(JSONValue.string)), "confirm": .bool(true)]))
    }

    func setActivityEnabled(_ enabled: Bool) async {
        guard connection == .ready else { return }
        guard begin("activity-setting") else { return }
        defer { end("activity-setting") }
        let priorValue = activityEnabled
        activityEnabled = enabled
        do {
            let result = try await backend.request(method: "activity.enabled", params: .object(["enabled": .bool(enabled)]))
            if result["ok"]?.boolValue != true {
                activityEnabled = priorValue
                showError(L("活动记录设置没有改变。"))
            }
        } catch {
            activityEnabled = priorValue
            present(error)
        }
    }

    func clearActivityHistory() async {
        guard connection == .ready else { return }
        guard begin("clear-activity") else { return }
        defer { end("clear-activity") }
        do {
            let result = try await backend.request(method: "activity.clear")
            if result["ok"]?.boolValue == true {
                noticeMessage = L("已清除已结束任务的活动元数据；配置和用户导出未受影响。")
                await refreshActivity()
            } else {
                showError(L("活动历史没有被清除。"))
            }
        } catch {
            present(error)
        }
    }

    private func prepareForAppUpdate() async -> Bool {
        guard canInstallAppUpdate else {
            noticeMessage = L("请先处理未保存配置，并等待 App 自有任务完成。")
            return false
        }
        appUpdatePreparing = true
        do {
            if connection == .ready { _ = try await backend.request(method: "app.update-prepare") }
            await shutdownForQuit()
            return true
        } catch {
            appUpdatePreparing = false
            present(error)
            return false
        }
    }

    func copyCLIUpdateCommand() {
        guard let command = updateResult?["cli"]?["command"]?.stringValue else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(command, forType: .string)
        noticeMessage = L("已复制此安装的单工具更新命令。")
    }

    func copyCurrentResult() {
        guard let currentResult else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(currentResult.redacted().prettyPrinted(), forType: .string)
        noticeMessage = L("已复制脱敏的结构化结果。")
    }

    func exportCurrentResult() {
        guard let currentResult else { return }
        let panel = NSSavePanel()
        panel.title = L("导出结果")
        panel.nameFieldStringValue = "smart-search-result.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let data = try JSONEncoder().encode(currentResult.redacted())
            try data.write(to: url, options: .atomic)
            noticeMessage = L("已导出脱敏结果。")
        } catch {
            showError(L("无法写入所选导出文件。"))
        }
    }

    func copyBundledCLIPath() {
        guard let status = cliStatus, let path = status["bundled_path"]?.stringValue else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(path, forType: .string)
        noticeMessage = L("已复制内置 CLI 路径。")
    }

    func shutdownForQuit() async {
        appUpdatePreparing = true
        intentionalShutdown = true
        eventTask?.cancel()
        for runID in ownedActiveRunIDs {
            _ = try? await backend.request(method: "run.cancel", params: .object(["run_id": .string(runID)]))
        }
        ownedActiveRunIDs.removeAll()
        clearOperations()
        await backend.shutdown()
        connection = .disconnected
        terminationReady = true
    }

    func displayLabel(for run: ActivityRun) -> String {
        ownedRunResults.descriptor(for: run.runID).map(localizedLabel)
            ?? state?.commands.first { $0.id == run.command }?.label
            ?? ["provider.test": L("服务商测试"), "version": L("版本查询"), "skills.install": L("安装 / 更新 Skills")][run.command]
            ?? L("其他任务")
    }

    private func localizedLabel(_ descriptor: OwnedRunDescriptor) -> String {
        switch descriptor.kind {
        case .business:
            return state?.commands.first { $0.id == descriptor.commandID }?.label ?? descriptor.label
        case .providerTest:
            return descriptor.providerID.map { L("测试 {0}", $0) } ?? L("服务商测试")
        case .skillsInstall:
            return L("安装 / 更新 Skills")
        }
    }

    func hasOwnedResult(for run: ActivityRun) -> Bool {
        ownedRunResults.result(for: run.runID) != nil
    }

    func activityResult(for run: ActivityRun) -> JSONValue? {
        guard activityResultRunID == run.runID else { return nil }
        return activityResult
    }

    func showOwnedResult(_ run: ActivityRun) {
        guard let descriptor = ownedRunResults.descriptor(for: run.runID),
              let result = ownedRunResults.result(for: run.runID) else { return }
        activityResultRunID = run.runID
        activityResult = result
        if descriptor.kind.updatesSearchResult {
            selectedBusinessRunID = run.runID
            currentResult = result
            currentResultCommand = localizedLabel(descriptor)
        }
    }

    func presentWindowCloseChoice(for window: NSWindow) {
        presentExitChoice(for: window) { [weak self] choice in
            guard let self else { return }
            switch choice {
            case .background:
                NSApp.hide(nil)
            case .stopAndQuit:
                Task {
                    await self.shutdownForQuit()
                    NSApp.terminate(nil)
                }
            case .return:
                break
            }
        }
    }

    func presentQuitChoice(completion: @escaping (ExitChoice) -> Void) {
        presentExitChoice(for: nil, completion: completion)
    }

    private func configMutationParameters(includeRevision: Bool) -> JSONValue {
        var params: [String: JSONValue] = [
            "set": .object(configDraft.mapValues(JSONValue.string)),
            "unset": .array(clearSecretKeys.sorted().map(JSONValue.string)),
        ]
        if includeRevision, let revision = state?.revision { params["revision"] = revision }
        return .object(params)
    }

    private func applyState(_ raw: JSONValue) {
        let incoming = raw["state"]?.objectValue == nil ? raw : (raw["state"] ?? raw)
        var payload = incoming.objectValue
        // Credentials belong only to the form binding, never to raw state or diagnostics.
        let secrets = payload?.removeValue(forKey: "config_secrets")?.objectValue ?? [:]
        guard let payload, let parsed = DesktopState(.object(payload)) else {
            errorMessage = L("后端状态格式无法读取；没有使用旧状态覆盖它。")
            return
        }
        let snapshot = parsed.raw
        configSecrets = secrets.compactMapValues(\.stringValue)
        state = parsed
        if let selectedBusinessRunID, let descriptor = ownedRunResults.descriptor(for: selectedBusinessRunID) {
            currentResultCommand = localizedLabel(descriptor)
        }
        updateResult = snapshot["updates"]
        cliStatus = snapshot["cli"]
        environmentState = snapshot["environment"]
        skillsState = snapshot["skills"]
        lastStateRefresh = Date()
        if !parsed.activityRuns().isEmpty {
            activityRuns = parsed.activityRuns()
        }
        if selectedCommandID == nil || !parsed.commands.contains(where: { $0.id == selectedCommandID }) {
            selectCommand(parsed.commands.first?.id)
        }
        if !skillSelectionInitialized {
            selectedSkillTargets = Set(parsed.skillTargets.filter(\.isDefault).map(\.id))
            skillSelectionInitialized = true
        }
    }

    private func startEventListener() {
        eventTask?.cancel()
        eventTask = Task { [weak self, backend] in
            let stream = await backend.eventStream()
            for await event in stream {
                guard !Task.isCancelled else { break }
                await self?.receive(event)
            }
        }
    }

    private func receive(_ event: BackendEvent) {
        switch event.name {
        case "skills":
            if skillsState?["checking"]?.boolValue == true, event.data["checking"]?.boolValue == false,
               event.data["error"]?.stringValue == "", (event.data["targets"]?.arrayValue ?? []).contains(where: { $0["status"]?.stringValue == "stale" }) {
                noticeMessage = L("发现内容不同的 Smart Search Skill，请到“更新 Skills”页选择目标。")
            }
            skillsState = event.data
        case "environment":
            environmentState = event.data
            if let installed = event.data["cli"] { cliStatus = installed }
        case "updates":
            updateResult = event.data
        case "activity":
            Task { await reconcileRuns() }
            // Backend push events cover its active profile.  With user-added directories,
            // refresh the explicitly scoped aggregate instead of silently dropping rows.
            if !observedDirectories.isEmpty {
                Task { await refreshActivity() }
                return
            }
            if let runs = event.data["runs"]?.arrayValue {
                activityRuns = runs.compactMap(ActivityRun.init).sorted { lhs, rhs in
                    (lhs.updatedAt ?? .distantPast) > (rhs.updatedAt ?? .distantPast)
                }
                activityErrors = event.data["errors"]?.arrayValue?.compactMap { item in
                    let directory = item["config_dir"]?.displayString ?? ""
                    let message = item["error"]?.displayString ?? L("活动记录不可读，当前状态未知。")
                    return directory.isEmpty ? message : "\(directory)：\(message)"
                } ?? []
                activityEnabled = event.data["enabled"]?.boolValue ?? activityEnabled
            } else if let run = ActivityRun(event.data) {
                upsert(run)
            }
        case "run":
            guard let runID = event.data["run_id"]?.stringValue, ownedActiveRunIDs.contains(runID) else { return }
            let status = event.data["status"]?.stringValue ?? "unknown"
            if event.data["command"] != nil, let run = ActivityRun(event.data) { upsert(run) }
            if ["finished", "failed", "cancelled", "stale", "interrupted"].contains(status) {
                ownedActiveRunIDs.remove(runID)
                operations.finish(runID)
                isBusy = operations.busyKeys
                let descriptor = ownedRunResults.descriptor(for: runID)
                if let result = event.data["result"], result != .null,
                   let descriptor = ownedRunResults.cache(result.redacted(), for: runID) {
                    if descriptor.kind.updatesSearchResult, selectedBusinessRunID == runID {
                        currentResult = result.redacted()
                        currentResultCommand = localizedLabel(descriptor)
                    }
                }
                if descriptor?.kind == .providerTest {
                    // get_state carries only this backend's in-memory draft check map;
                    // applying it leaves the user's unsaved native draft and destination intact.
                    Task { await refreshProviderChecks() }
                }
                if descriptor?.kind == .skillsInstall { Task { await refreshSkillStatus() } }
                Task { await refreshActivity() }
            }
        case "backend.exited":
            clearOperations()
            environmentState = .object(["busy": .bool(false), "message": .string(L("连接已断开，安装结果尚未确认；重新连接后请检测环境。"))])
            if intentionalShutdown {
                connection = .disconnected
            } else {
                connection = .failed
                errorMessage = L("后端进程已退出；上次状态保留时间标记，不再表示当前正常。")
            }
        case "backend.protocol-error":
            clearOperations()
            environmentState = .object(["busy": .bool(false), "message": .string(L("连接异常，安装结果尚未确认；请重新检测环境。"))])
            connection = .failed
            errorMessage = L("后端输出不符合桌面协议；没有把它当作正常状态读取。")
        default:
            break
        }
    }

    private func upsert(_ run: ActivityRun) {
        if let index = activityRuns.firstIndex(where: { $0.runID == run.runID }) {
            activityRuns[index] = run
        } else {
            activityRuns.insert(run, at: 0)
        }
        activityRuns.sort { ($0.updatedAt ?? .distantPast) > ($1.updatedAt ?? .distantPast) }
    }

    private func persistObservedDirectories() {
        UserDefaults.standard.set(observedDirectories, forKey: DefaultsKey.observedDirectories)
    }

    var configOperationBusy: Bool { !isBusy.isDisjoint(with: ["state", "save", "preview", "profile"]) }

    private func begin(_ identifier: String) -> Bool {
        if appUpdatePreparing { return false }
        if ["state", "save", "preview", "profile"].contains(identifier), configOperationBusy { return false }
        guard operations.begin(identifier) else { return false }
        isBusy = operations.busyKeys
        return true
    }

    private func end(_ identifier: String) {
        operations.endRequest(identifier)
        isBusy = operations.busyKeys
    }

    private func trackRun(_ runID: String, key: String) {
        operations.track(runID, key: key)
        isBusy = operations.busyKeys
    }

    private func clearOperations() {
        operations.reset()
        isBusy = []
        ownedActiveRunIDs.removeAll()
    }

    private func recoverRun(_ runID: String) async {
        guard connection == .ready, ownedActiveRunIDs.contains(runID) else { return }
        let generation = state?.generation
        if let result = try? await backend.request(method: "run.result", params: .object(["run_id": .string(runID)])),
           state?.generation == generation {
            receive(BackendEvent(name: "run", data: result, generation: generation))
        }
    }

    private func reconcileRuns() async {
        guard begin("reconcile") else { return }
        defer { end("reconcile") }
        for runID in Array(ownedActiveRunIDs) { await recoverRun(runID) }
    }

    private func refreshProviderChecks() async {
        guard connection == .ready else { return }
        let directory = state?.configDirectory
        let generation = state?.generation
        do {
            let result = try await backend.request(method: "get_state")
            guard state?.configDirectory == directory, state?.generation == generation,
                  result["config_dir"]?.stringValue == directory,
                  var snapshot = state?.raw.objectValue else { return }
            snapshot["provider_checks"] = result["provider_checks"]
            snapshot["provider_health"] = result["provider_health"]
            // Probe completion must not silently adopt another process's config revision.
            state = DesktopState(.object(snapshot))
        } catch { present(error) }
    }

    func providerTestLabel(_ provider: String) -> String {
        let keys = Set(state?.fields.filter { $0.provider == provider }.map(\.key) ?? [])
        let changed = keys.contains { configDraft[$0] != nil || clearSecretKeys.contains($0) }
        if state?.raw["probe_kinds"]?[provider]?.stringValue == "presence" {
            return changed ? L("检查未保存的配置") : L("检查配置")
        }
        return changed ? L("用未保存的修改测试") : L("测试")
    }

    func showError(_ message: String) {
        errorMessage = message
        errorPresentationID = UUID()
    }

    private func present(_ error: Error, repeatFeedback: Bool = true) {
        let message = (error as? LocalizedError)?.errorDescription ?? L("操作未完成。")
        if repeatFeedback {
            showError(message)
        } else {
            errorMessage = message
        }
    }

    private func presentExitChoice(for window: NSWindow?, completion: @escaping (ExitChoice) -> Void) {
        let alert = NSAlert()
        alert.messageText = L("仍有 Smart Search 任务在运行")
        alert.informativeText = L("这些任务属于本 App。你可以让它们继续在后台运行，取消后退出，或返回继续查看。")
        alert.addButton(withTitle: L("继续在后台"))
        alert.addButton(withTitle: L("取消任务并退出"))
        alert.addButton(withTitle: L("返回"))
        let resolve: (NSApplication.ModalResponse) -> Void = { response in
            switch response {
            case .alertFirstButtonReturn: completion(.background)
            case .alertSecondButtonReturn: completion(.stopAndQuit)
            default: completion(.return)
            }
        }
        if let window {
            alert.beginSheetModal(for: window, completionHandler: resolve)
        } else {
            resolve(alert.runModal())
        }
    }
}
