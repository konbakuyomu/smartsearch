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

    @Published var selectedDestination: Destination = .providers
    @Published private(set) var connection: ConnectionState = .disconnected
    @Published private(set) var state: DesktopState?
    @Published private(set) var lastStateRefresh: Date?
    @Published private(set) var currentResult: JSONValue?
    @Published private(set) var currentResultCommand: String?
    @Published private(set) var cliStatus: JSONValue?
    @Published private(set) var skillsState: JSONValue?
    private var skillSelectionInitialized = false
    @Published private(set) var updateResult: JSONValue? {
        didSet {
            if let installed = updateResult?["installed_cli"] { cliStatus = installed }
            appUpdater.synchronize(automaticallyChecks: updateResult?["auto_check"]?.boolValue ?? true,
                                   enabled: true)
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
    @Published private(set) var languagePreference: String

    @Published private(set) var appUpdatePreparing = false
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
        connection == .ready && configDraft.isEmpty && clearSecretKeys.isEmpty && !hasOwnedActiveRuns &&
        !isUpdatingCLI && !environmentBusy && !skillsBusy && !configOperationBusy && !appUpdatePreparing
    }
    private let backend = BackendClient()
    private var eventTask: Task<Void, Never>?
    private var ownedActiveRunIDs: Set<String> = []
    @Published private var ownedRunResults = OwnedRunResultStore(capacity: 100)
    private var selectedBusinessRunID: String?
    private var intentionalShutdown = false

    init() {
        let savedLanguage = UserDefaults.standard.string(forKey: Localization.preferenceKey) ?? "auto"
        let validLanguage = ["auto", "zh", "en"].contains(savedLanguage)
        languagePreference = validLanguage ? savedLanguage : "auto"
        Task {
            await connect()
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
    var isUpdatingCLI: Bool { isBusy.contains("cli.update") || updateResult?["cli_update"]?["status"]?.stringValue == "running" }
    var environmentBusy: Bool { isBusy.contains("environment.request") || environmentState?["busy"]?.boolValue == true }
    var skillsBusy: Bool { isBusy.contains("skills.update") || skillsState?["busy"]?.boolValue == true }
    var skillsChecking: Bool { isBusy.contains("skills.check") || isBusy.contains("skills.catalog") || skillsState?["checking"]?.boolValue == true }
    var selectedCommand: CommandCatalogEntry? {
        guard let selectedCommandID else { return nil }
        return state?.commands.first(where: { $0.id == selectedCommandID })
    }

    func connect() async {
        guard !isUpdatingCLI && !environmentBusy else { noticeMessage = L("环境操作或 CLI 更新正在进行，请等待完成。"); return }
        guard !isBusy.contains("connect") else { return }
        clearOperations()
        guard begin("connect") else { return }
        intentionalShutdown = false
        connection = .connecting
        errorMessage = nil
        let started = Date()
        do {
            let backendURL = try BackendLocator.resolvedURL(overridePath: "")
            await backend.setTimeout(seconds: 30)
            try await backend.start(backendURL: backendURL)
            startEventListener()
            let snapshot = try await backend.initialize(enableUpdateChecks: true, language: Localization.language)
            applyState(snapshot)
            connection = .ready
            connectionLog.info("Backend initialized in \(Int(Date().timeIntervalSince(started) * 1000), privacy: .public) ms")
            await refreshCLIStatus()
        } catch {
            connection = .failed
            connectionLog.error("Backend initialization failed")
            present(error)
        }
        end("connect")
    }

    func reconnect() async {
        await connect()
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
        } catch {
            present(error)
        }
    }

    func enter(_ destination: Destination) async {
        if destination == .integration {
            await refreshCLIStatus()
            await refreshSkillStatus()
        }
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
        } catch {
            present(error)
        }
    }

    func restoreDefaultConfigDirectory() async {
        guard let directory = state?.defaultConfigDirectory, !directory.isEmpty,
              state?.isDefaultConfigDirectory == false else { return }
        await selectProfile(directory)
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
        guard connection == .ready, !isSearchRunning, let command = selectedCommand else { return }
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
            noticeMessage = L("测试已开始，结果会显示在此页。")
            await recoverRun(runID)
        } catch {
            present(error)
        }
    }

    private func cancel(runID: String) async {
        guard ownedActiveRunIDs.contains(runID), connection == .ready else { return }
        guard begin("cancel:\(runID)") else { return }
        defer { end("cancel:\(runID)") }
        do {
            let result = try await backend.request(method: "run.cancel", params: .object(["run_id": .string(runID)]))
            if result["ok"]?.boolValue == true {
                if ownedActiveRunIDs.contains(runID) { trackRun(runID, key: "cancel:\(runID)") }
                await recoverRun(runID)
                noticeMessage = L("已请求取消，等待后端确认最终状态。")
            } else { showError(L("后端未接受取消请求；任务仍保持原状态。")) }
        } catch { present(error) }
    }

    func cancelCurrentTest() async {
        if let selectedBusinessRunID { await cancel(runID: selectedBusinessRunID) }
    }

    func cancelProviderTest(_ provider: String) async {
        for runID in operations.runIDs(for: "test:" + provider) { await cancel(runID: runID) }
    }

    func environmentAction(_ method: String, params: JSONValue = .object([:])) async {
        guard connection == .ready, !isUpdatingCLI else { return }
        if environmentBusy && method != "environment.cancel" { return }
        guard begin("environment.request") else { return }
        defer { end("environment.request") }
        do { environmentState = try await backend.request(method: method, params: params) }
        catch { present(error) }
    }

    var skillTargetsToUpdate: [String] {
        (skillsState?["targets"]?.arrayValue ?? []).compactMap { row in
            guard let id = row["target"]?.stringValue, selectedSkillTargets.contains(id) else { return nil }
            return id
        }.sorted()
    }

    var canUpdateSelectedSkills: Bool {
        SkillsSelectionPolicy.canUpdate(connected: connection == .ready, selectedCount: skillTargetsToUpdate.count,
                                       busy: environmentBusy || isUpdatingCLI || skillsBusy || skillsChecking)
    }

    func installSelectedSkills() async {
        guard canUpdateSelectedSkills else { return }
        await skillsAction("skills.update", params: .object([
            "targets": .array(skillTargetsToUpdate.map(JSONValue.string)), "confirm": .bool(true)]))
    }

    var cliReady: Bool {
        cliStatus?["external_runtime_verified"]?.boolValue == true && cliStatus?["manager"]?.stringValue != "bundled"
    }
    var cliActionLabel: String {
        if !cliReady { return (cliStatus?["external_path"]?.stringValue ?? "").isEmpty ? L("安装 CLI") : L("修复 CLI") }
        return updateResult?["cli"]?["available"]?.boolValue == true && cliStatus?["can_update"]?.boolValue == true ? L("更新 CLI") : L("检查更新")
    }
    func manageCLI() async {
        guard !environmentBusy, !isUpdatingCLI, !skillsBusy else { return }
        if !cliReady { await environmentAction("environment.prepare", params: .object(["confirm": .bool(true)])) }
        else if updateResult?["cli"]?["available"]?.boolValue == true, cliStatus?["can_update"]?.boolValue == true { await updateCLI() }
        else { await updateAction("cli.update-check") }
    }

    func updateAction(_ method: String, params: JSONValue = .object([:])) async {
        if environmentBusy && ["cli.update", "app.update-prepare"].contains(method) { return }
        guard connection == .ready, begin(method) else { return }
        defer { end(method) }
        do { updateResult = try await backend.request(method: method, params: params) }
        catch { present(error) }
    }

    func updateCLI() async {
        guard !isUpdatingCLI, !environmentBusy, cliStatus?["can_update"]?.boolValue == true,
              let version = updateResult?["cli"]?["latest_version"]?.stringValue else { return }
        await updateAction("cli.update", params: .object(["confirm": .bool(true), "version": .string(version)]))
    }

    private func prepareForAppUpdate() async -> Bool {
        guard canInstallAppUpdate else {
            noticeMessage = L("请先处理未保存配置，并等待 App 自有任务完成。")
            return false
        }
        appUpdatePreparing = true
        do {
            _ = try await backend.request(method: "app.update-prepare")
            await shutdownForQuit()
            return true
        } catch {
            appUpdatePreparing = false
            present(error)
            return false
        }
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
            if !skillsBusy, skillsState?["checking"]?.boolValue == true, event.data["checking"]?.boolValue == false,
               event.data["error"]?.stringValue == "", (event.data["targets"]?.arrayValue ?? []).contains(where: { $0["status"]?.stringValue == "stale" }) {
                noticeMessage = L("发现可更新的 Skills，请到“CLI 与 Skills”页选择目标。")
            }
            skillsState = event.data
        case "environment":
            environmentState = event.data
            if let installed = event.data["cli"] { cliStatus = installed }
        case "updates":
            updateResult = event.data
        case "tick":
            appUpdater.resumePromptIfPossible()
            Task { await reconcileRuns() }
        case "run":
            guard let runID = event.data["run_id"]?.stringValue, ownedActiveRunIDs.contains(runID) else { return }
            let status = event.data["status"]?.stringValue ?? "unknown"
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
            }
        case "backend.exited":
            clearOperations()
            environmentState = .object(["busy": .bool(false), "message": .string(L("连接已断开，安装结果尚未确认；请重新连接后重试。"))])
            if intentionalShutdown {
                connection = .disconnected
            } else {
                connection = .failed
                errorMessage = L("后端进程已退出；上次状态保留时间标记，不再表示当前正常。")
            }
        case "backend.protocol-error":
            clearOperations()
            environmentState = .object(["busy": .bool(false), "message": .string(L("连接异常，安装结果尚未确认；请重新连接后重试。"))])
            connection = .failed
            errorMessage = L("后端输出不符合桌面协议；没有把它当作正常状态读取。")
        default:
            break
        }
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
