import AppKit
import Foundation
import SwiftUI

@MainActor
final class AppModel: ObservableObject {
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
            case .disconnected: return "未连接"
            case .connecting: return "正在连接"
            case .ready: return "已连接"
            case .failed: return "后端失联"
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
    @Published private(set) var updateResult: JSONValue?
    @Published var errorMessage: String?
    @Published var noticeMessage: String?
    @Published private(set) var isBusy: Set<String> = []
    /// Operations still running, keyed as "test:<provider>". provider.test is
    /// fire-and-forget — the call returns a run id in milliseconds while the probe
    /// itself takes up to 20 seconds — so isBusy, which clears when the function
    /// returns, cannot drive the spinner on its own.
    @Published private(set) var inFlight: Set<String> = []
    private var runOperationKeys: [String: String] = [:]

    @Published var configDraft: [String: String] = [:]
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
        backendPathOverride = UserDefaults.standard.string(forKey: DefaultsKey.backendPath) ?? ""
        let storedTimeout = UserDefaults.standard.double(forKey: DefaultsKey.timeout)
        requestTimeoutSeconds = storedTimeout == 0 ? 30 : min(max(storedTimeout, 5), 300)
        observedDirectories = UserDefaults.standard.stringArray(forKey: DefaultsKey.observedDirectories) ?? []
        Task { await connect() }
    }

    deinit {
        eventTask?.cancel()
    }

    var hasOwnedActiveRuns: Bool { !ownedActiveRunIDs.isEmpty }

    var selectedCommand: CommandCatalogEntry? {
        guard let selectedCommandID else { return nil }
        return state?.commands.first(where: { $0.id == selectedCommandID })
    }

    func connect() async {
        guard !isBusy.contains("connect") else { return }
        begin("connect")
        intentionalShutdown = false
        connection = .connecting
        errorMessage = nil
        do {
            let backendURL = try BackendLocator.resolvedURL(overridePath: backendPathOverride)
            await backend.setTimeout(seconds: requestTimeoutSeconds)
            try await backend.start(backendURL: backendURL)
            startEventListener()
            let snapshot = try await backend.initialize()
            applyState(snapshot)
            connection = .ready
            await refreshActivity()
            await refreshCLIStatus()
        } catch {
            connection = .failed
            present(error)
        }
        end("connect")
    }

    func reconnect() async {
        await connect()
    }

    func refreshState() async {
        guard connection == .ready else { return }
        begin("state")
        defer { end("state") }
        do {
            applyState(try await backend.request(method: "get_state"))
        } catch {
            present(error)
        }
    }

    func refreshActivity() async {
        guard connection == .ready, !isBusy.contains("activity") else { return }
        begin("activity")
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
                let message = item["error"]?.displayString ?? "活动记录不可读，当前状态未知。"
                return directory.isEmpty ? message : "\(directory)：\(message)"
            }
            activityEnabled = result["enabled"]?.boolValue ?? activityEnabled
            if result["ok"]?.boolValue == false {
                errorMessage = "一个或多个配置目录的活动记录不可读；可读取的记录仍已显示，其他状态未知。"
            }
        } catch {
            present(error)
        }
    }

    func refreshCLIStatus() async {
        guard connection == .ready else { return }
        do {
            cliStatus = try await backend.request(method: "cli.status")
        } catch {
            present(error)
        }
    }

    func refreshSkillStatus() async {
        guard connection == .ready else { return }
        do {
            let result = try await backend.request(method: "skills.status")
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
        noticeMessage = "后续请求将使用 \(Int(requestTimeoutSeconds)) 秒超时。"
    }

    func saveBackendOverride(_ path: String) {
        backendPathOverride = path.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(backendPathOverride, forKey: DefaultsKey.backendPath)
    }

    func chooseBackendExecutable() {
        let panel = NSOpenPanel()
        panel.title = "选择开发环境后端"
        panel.prompt = "选择"
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        saveBackendOverride(url.path)
    }

    func chooseConfigDirectory() {
        let panel = NSOpenPanel()
        panel.title = "选择 Smart Search 配置目录"
        panel.prompt = "使用此目录"
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        Task { await selectProfile(url.path) }
    }

    func selectProfile(_ directory: String) async {
        guard connection == .ready else { return }
        begin("profile")
        defer { end("profile") }
        do {
            applyState(try await backend.request(method: "profile.select", params: .object(["config_dir": .string(directory)])))
            await refreshActivity()
        } catch {
            present(error)
        }
    }

    func addObservedDirectory() {
        let panel = NSOpenPanel()
        panel.title = "添加要观察的配置目录"
        panel.prompt = "添加"
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
            get: { self.configDraft[field.key] ?? "" },
            set: { self.setDraft($0, for: field) }
        )
    }

    func setDraft(_ value: String, for field: ConfigField) {
        guard !isEnvironmentReadOnly(field) else { return }
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            configDraft.removeValue(forKey: field.key) // Empty secret input means KEEP.
        } else {
            configDraft[field.key] = value
            clearSecretKeys.remove(field.key)
        }
    }

    func clearSecret(_ field: ConfigField) {
        guard field.isSecret, !isEnvironmentReadOnly(field) else { return }
        configDraft.removeValue(forKey: field.key)
        clearSecretKeys.insert(field.key)
    }

    func keepSecret(_ field: ConfigField) {
        clearSecretKeys.remove(field.key)
        configDraft.removeValue(forKey: field.key)
    }

    func isEnvironmentReadOnly(_ field: ConfigField) -> Bool {
        state?.source(for: field) == "environment"
    }

    func draftStatus(for field: ConfigField) -> String {
        if isEnvironmentReadOnly(field) { return "由环境变量提供，只读" }
        if clearSecretKeys.contains(field.key) { return "将在保存时清除" }
        if configDraft[field.key]?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false {
            return field.isSecret ? "将在保存时替换" : "将在保存时更新"
        }
        return field.isSecret ? "保持当前密钥" : "未修改"
    }

    func resetConfigDraft() {
        configDraft.removeAll()
        clearSecretKeys.removeAll()
        configPreview = nil
    }

    func previewConfig() async {
        guard connection == .ready else { return }
        begin("preview")
        defer { end("preview") }
        do {
            configPreview = try await backend.request(method: "config.preview", params: configMutationParameters(includeRevision: false))
        } catch {
            present(error)
        }
    }

    func saveConfig() async {
        guard connection == .ready else { return }
        guard let revision = state?.revision else {
            errorMessage = "没有可用的配置版本，请先刷新后再保存。"
            return
        }
        begin("save")
        defer { end("save") }
        var params = configMutationParameters(includeRevision: false).objectValue ?? [:]
        params["revision"] = revision
        do {
            let result = try await backend.request(method: "config.apply", params: .object(params))
            guard result["ok"]?.boolValue == true else {
                errorMessage = result["error_type"]?.stringValue == "conflict"
                    ? "配置已被其他进程修改；你改的内容还在，请刷新后核对。"
                    : "后端没有保存配置；你改的内容还在。"
                return
            }
            // config.apply returns a compact status snapshot; get_state restores the
            // metadata and command catalog that the native form needs.
            await refreshState()
            resetConfigDraft()
            noticeMessage = "配置已保存。后续新任务会使用新版本；正在运行的任务不受影响。"
        } catch {
            present(error)
        }
    }

    func testProvider(_ provider: String) async {
        guard connection == .ready, let state else { return }
        begin("test:\(provider)")
        defer { end("test:\(provider)") }
        let providerKeys = Set(state.fields.filter { $0.provider == provider }.map(\.key))
        var overrides = configDraft.reduce(into: [String: JSONValue]()) { partial, item in
            if providerKeys.contains(item.key), !item.value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
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
                errorMessage = "后端未能开始测试；配置没有改变。"
                return
            }
            ownedActiveRunIDs.insert(runID)
            ownedRunResults.register(runID: runID, kind: .providerTest, label: "测试 \(provider)")
            inFlight.insert("test:\(provider)")
            runOperationKeys[runID] = "test:\(provider)"
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
            errorMessage = "请填写必填项：\(missing.map(\.label).joined(separator: "、"))。"
            return
        }
        begin("run:\(command.id)")
        defer { end("run:\(command.id)") }
        do {
            let arguments = CommandArgumentBuilder.arguments(for: command, values: commandValues, booleans: commandBooleans)
            let result = try await backend.request(method: "run.start", params: .object([
                "command": .string(command.id),
                "arguments": .array(arguments.map(JSONValue.string)),
            ]))
            guard result["ok"]?.boolValue == true, let runID = result["run_id"]?.stringValue else {
                errorMessage = "后端未能开始此操作。"
                return
            }
            ownedActiveRunIDs.insert(runID)
            ownedRunResults.register(runID: runID, kind: .business, label: command.label)
            selectedBusinessRunID = runID
            currentResult = nil
            currentResultCommand = command.label
            noticeMessage = "操作已开始，进度会显示在活动页。"
            await refreshActivity()
        } catch {
            present(error)
        }
    }

    func cancel(_ run: ActivityRun) async {
        guard ownedActiveRunIDs.contains(run.runID), run.isActive, connection == .ready else { return }
        begin("cancel:\(run.runID)")
        defer { end("cancel:\(run.runID)") }
        do {
            let result = try await backend.request(method: "run.cancel", params: .object(["run_id": .string(run.runID)]))
            if result["ok"]?.boolValue == true {
                noticeMessage = "已请求取消，等待后端确认最终状态。"
            } else {
                errorMessage = "后端未接受取消请求；任务仍保持原状态。"
            }
        } catch {
            present(error)
        }
    }

    func canCancel(_ run: ActivityRun) -> Bool {
        ownedActiveRunIDs.contains(run.runID) && run.isActive
    }

    func showActivityDetails(_ run: ActivityRun) async {
        selectedActivity = run
        activityDetails = nil
        activityResultRunID = nil
        activityResult = nil
        guard connection == .ready else { return }
        begin("details:\(run.runID)")
        defer { end("details:\(run.runID)") }
        var params: [String: JSONValue] = ["run_id": .string(run.runID)]
        if let directory = run.configDirectory { params["config_dir"] = .string(directory) }
        do {
            // activity.details carries only protocol-approved, redacted metadata.
            let result = try await backend.request(method: "activity.details", params: .object(params))
            activityDetails = result.redacted()
        } catch {
            present(error)
        }
    }

    func installSelectedSkills() async {
        guard connection == .ready, !selectedSkillTargets.isEmpty else {
            errorMessage = "请至少选择一个目标后再安装或更新。"
            return
        }
        begin("skills")
        defer { end("skills") }
        do {
            let result = try await backend.request(method: "skills.install", params: .object([
                "targets": .array(selectedSkillTargets.sorted().map(JSONValue.string)),
            ]))
            guard result["ok"]?.boolValue == true, let runID = result["run_id"]?.stringValue else {
                errorMessage = "后端没有开始 Skills 安装或更新。"
                return
            }
            ownedActiveRunIDs.insert(runID)
            ownedRunResults.register(
                runID: runID,
                kind: .skillsInstall,
                label: "Skills 安装或更新（\(selectedSkillTargets.count) 个目标）"
            )
            noticeMessage = "Skills 安装或更新已开始。"
            await refreshActivity()
        } catch {
            present(error)
        }
    }

    func enableBundledCLI() async {
        guard connection == .ready else { return }
        begin("cli.enable")
        defer { end("cli.enable") }
        do {
            let result = try await backend.request(method: "cli.enable", params: .object(["confirm": .bool(true)]))
            if result["ok"]?.boolValue == true {
                noticeMessage = "已按你的确认启用内置 CLI。"
                await refreshCLIStatus()
            } else {
                errorMessage = "内置 CLI 未启用；已有同名外部 CLI 不会被覆盖。"
            }
        } catch {
            present(error)
        }
    }

    func setActivityEnabled(_ enabled: Bool) async {
        guard connection == .ready else { return }
        let priorValue = activityEnabled
        activityEnabled = enabled
        do {
            let result = try await backend.request(method: "activity.enabled", params: .object(["enabled": .bool(enabled)]))
            if result["ok"]?.boolValue != true {
                activityEnabled = priorValue
                errorMessage = "活动记录设置没有改变。"
            }
        } catch {
            activityEnabled = priorValue
            present(error)
        }
    }

    func clearActivityHistory() async {
        guard connection == .ready else { return }
        begin("clear-activity")
        defer { end("clear-activity") }
        do {
            let result = try await backend.request(method: "activity.clear")
            if result["ok"]?.boolValue == true {
                noticeMessage = "已清除已结束任务的活动元数据；配置和用户导出未受影响。"
                await refreshActivity()
            } else {
                errorMessage = "活动历史没有被清除。"
            }
        } catch {
            present(error)
        }
    }

    func checkForUpdates() async {
        guard connection == .ready else { return }
        begin("update")
        defer { end("update") }
        do {
            updateResult = try await backend.request(method: "app.update-check")
        } catch {
            present(error)
        }
    }

    func copyCurrentResult() {
        guard let currentResult else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(currentResult.redacted().prettyPrinted(), forType: .string)
        noticeMessage = "已复制脱敏的结构化结果。"
    }

    func exportCurrentResult() {
        guard let currentResult else { return }
        let panel = NSSavePanel()
        panel.title = "导出结果"
        panel.nameFieldStringValue = "smart-search-result.json"
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let data = try JSONEncoder().encode(currentResult.redacted())
            try data.write(to: url, options: .atomic)
            noticeMessage = "已导出脱敏结果。"
        } catch {
            errorMessage = "无法写入所选导出文件。"
        }
    }

    func copyBundledCLIPath() {
        guard let status = cliStatus, let path = status["bundled_path"]?.stringValue else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(path, forType: .string)
        noticeMessage = "已复制内置 CLI 路径。"
    }

    func shutdownForQuit() async {
        intentionalShutdown = true
        eventTask?.cancel()
        for runID in ownedActiveRunIDs {
            _ = try? await backend.request(method: "run.cancel", params: .object(["run_id": .string(runID)]))
        }
        ownedActiveRunIDs.removeAll()
        inFlight.removeAll()
        runOperationKeys.removeAll()
        await backend.shutdown()
        connection = .disconnected
    }

    func displayLabel(for run: ActivityRun) -> String {
        ownedRunResults.descriptor(for: run.runID)?.label ?? run.command
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
            currentResultCommand = descriptor.label
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
            "set": .object(configDraft.compactMapValues { value in
                value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : .string(value)
            }),
            "unset": .array(clearSecretKeys.sorted().map(JSONValue.string)),
        ]
        if includeRevision, let revision = state?.revision { params["revision"] = revision }
        return .object(params)
    }

    private func applyState(_ raw: JSONValue) {
        let snapshot = raw["state"]?.objectValue == nil ? raw : (raw["state"] ?? raw)
        guard let parsed = DesktopState(snapshot) else {
            errorMessage = "后端状态格式无法读取；没有使用旧状态覆盖它。"
            return
        }
        state = parsed
        lastStateRefresh = Date()
        if !parsed.activityRuns().isEmpty {
            activityRuns = parsed.activityRuns()
        }
        if selectedCommandID == nil || !parsed.commands.contains(where: { $0.id == selectedCommandID }) {
            selectCommand(parsed.commands.first?.id)
        }
        if selectedSkillTargets.isEmpty {
            selectedSkillTargets = Set(parsed.skillTargets.filter(\.isDefault).map(\.id))
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
        case "activity":
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
                    let message = item["error"]?.displayString ?? "活动记录不可读，当前状态未知。"
                    return directory.isEmpty ? message : "\(directory)：\(message)"
                } ?? []
                activityEnabled = event.data["enabled"]?.boolValue ?? activityEnabled
            } else if let run = ActivityRun(event.data) {
                upsert(run)
            }
        case "run":
            guard let runID = event.data["run_id"]?.stringValue else { return }
            let status = event.data["status"]?.stringValue ?? "unknown"
            if let run = ActivityRun(event.data) { upsert(run) }
            if ["finished", "failed", "cancelled", "stale", "interrupted"].contains(status) {
                ownedActiveRunIDs.remove(runID)
                if let operationKey = runOperationKeys.removeValue(forKey: runID) {
                    inFlight.remove(operationKey)
                }
                let descriptor = ownedRunResults.descriptor(for: runID)
                if let result = event.data["result"], result != .null,
                   let descriptor = ownedRunResults.cache(result.redacted(), for: runID) {
                    if descriptor.kind.updatesSearchResult, selectedBusinessRunID == runID {
                        currentResult = result.redacted()
                        currentResultCommand = descriptor.label
                    }
                }
                if descriptor?.kind == .providerTest {
                    // get_state carries only this backend's in-memory draft check map;
                    // applying it leaves the user's unsaved native draft and destination intact.
                    Task { await refreshState() }
                }
                Task { await refreshActivity() }
            }
        case "backend.exited":
            if intentionalShutdown {
                connection = .disconnected
            } else {
                connection = .failed
                errorMessage = "后端进程已退出；上次状态保留时间标记，不再表示当前正常。"
            }
        case "backend.protocol-error":
            connection = .failed
            errorMessage = "后端输出不符合桌面协议；没有把它当作正常状态读取。"
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

    private func begin(_ identifier: String) { isBusy.insert(identifier) }
    private func end(_ identifier: String) { isBusy.remove(identifier) }

    private func present(_ error: Error) {
        errorMessage = (error as? LocalizedError)?.errorDescription ?? "操作未完成。"
    }

    private func presentExitChoice(for window: NSWindow?, completion: @escaping (ExitChoice) -> Void) {
        let alert = NSAlert()
        alert.messageText = "仍有 Smart Search 任务在运行"
        alert.informativeText = "这些任务属于本 App。你可以让它们继续在后台运行，取消后退出，或返回继续查看。"
        alert.addButton(withTitle: "继续在后台")
        alert.addButton(withTitle: "取消任务并退出")
        alert.addButton(withTitle: "返回")
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
