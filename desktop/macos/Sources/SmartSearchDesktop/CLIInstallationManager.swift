import Combine
import Foundation

struct CLIInstallation: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var executable: String
    var arguments: [String] = []
    var version: String = ""
    var source: String
    var compatible = false
    var manager: [String] = []
    var prefix: String = ""
    var environment: [String: String] = [:]
    var note = ""
    var managerOptions: [String] = []
    var canManage: Bool { ["npm", "mise"].contains(source) && !manager.isEmpty }
    var title: String { "\(source) · \(version.isEmpty ? L("版本未知") : version) · \(id)" }
}

struct NpmEnvironment: Codable, Equatable, Sendable {
    var npmPath: String
    var nodePath: String
    var version: String
    var prefix: String
    var modules: String
    var command: [String]
    var environment: [String: String]
    var identity: String { nodePath + "|" + command.joined(separator: "|") + "|" + prefix }
}

private struct CLIUpdateRecord: Codable {
    var identity = ""
    var latestVersion = ""
    var supportsBinary = false
    var checkedAt: Date?
    var attemptedAt: Date?
}

// What one detection found. Each detection fills a new one and shows it whole, so one running in the
// background never shows half its results. The last one shown is kept for the next launch.
private struct CLIDetection: Codable {
    var installations: [CLIInstallation] = []
    var npm: NpmEnvironment?
    var message = ""
    var selectedID = ""
    // A detection made with other manual paths does not describe the current settings.
    var manualNpmPath = ""
    var manualCliPath = ""
}

enum CLIManagementError: LocalizedError {
    case failed(String)
    var errorDescription: String? { if case let .failed(message) = self { return message }; return nil }
}

@MainActor
final class CLIInstallationManager: ObservableObject {
    @Published private(set) var installations: [CLIInstallation] = []
    @Published private(set) var npm: NpmEnvironment?
    @Published private(set) var busy = false
    @Published private(set) var message = ""
    @Published private(set) var checking = false
    @Published private(set) var checkError = ""
    @Published private var update = CLIUpdateRecord()
    @Published var automaticallyChecks: Bool {
        didSet { preferences.set(automaticallyChecks, forKey: "SmartSearchDesktop.cliAutoCheck") }
    }
    @Published private(set) var manualNpmPath: String
    @Published private(set) var selectedID: String
    @Published private(set) var manualCliPath: String
    var selected: CLIInstallation? { selectedID.isEmpty ? installations.first : installations.first { $0.id == selectedID } }
    var canInstall: Bool { selected.map(\.canManage) ?? (npm != nil && selectedID.isEmpty) }
    var latestVersion: String { update.latestVersion }
    var latestSupportsBinary: Bool { update.supportsBinary }
    var checkedAt: Date? { update.checkedAt }
    var updateAvailable: Bool {
        guard let selected, Self.validVersion(selected.version), Self.validVersion(latestVersion) else { return false }
        return selected.version.compare(latestVersion, options: .numeric) == .orderedAscending
    }
    private static let package = "@konbakuyomu/smart-search"
    private let preferences: UserDefaults
    private let initialSearchPath: String?
    private let versionLoader: (() async throws -> String)?
    private let clock: () -> Date
    private var checkedAtLaunch = false
    private var automaticTask: Task<Void, Never>?
    private var held: CLIDetection?
    private var detections = 0
    private static let detectionKey = "SmartSearchDesktop.cliDetection"

    enum Redetection { case unchanged, changed, missing }

    init(searchPath: String? = nil, preferences: UserDefaults = .standard,
         versionLoader: (() async throws -> String)? = nil, clock: @escaping () -> Date = Date.init) {
        self.preferences = preferences
        self.initialSearchPath = searchPath
        self.manualNpmPath = preferences.string(forKey: "SmartSearchDesktop.npmPath") ?? ""
        self.selectedID = preferences.string(forKey: "SmartSearchDesktop.selectedCLI") ?? ""
        self.manualCliPath = preferences.string(forKey: "SmartSearchDesktop.manualCLI") ?? ""
        self.automaticallyChecks = preferences.object(forKey: "SmartSearchDesktop.cliAutoCheck") as? Bool ?? true
        self.versionLoader = versionLoader
        self.clock = clock
        if let data = preferences.data(forKey: "SmartSearchDesktop.cliUpdateState"),
           let record = try? JSONDecoder().decode(CLIUpdateRecord.self, from: data) { update = record }
    }

    deinit { automaticTask?.cancel() }

    func setNpmPath(_ path: String) {
        manualNpmPath = (path as NSString).expandingTildeInPath.trimmingCharacters(in: .whitespacesAndNewlines)
        preferences.set(manualNpmPath, forKey: "SmartSearchDesktop.npmPath")
        setCliPath("")
    }

    func selectInstallation(_ id: String) {
        guard installations.contains(where: { $0.id == id }) else { return }
        selectedID = id
        preferences.set(id, forKey: "SmartSearchDesktop.selectedCLI")
    }

    func setCliPath(_ path: String) {
        manualCliPath = (path as NSString).expandingTildeInPath.trimmingCharacters(in: .whitespacesAndNewlines)
        selectedID = manualCliPath
        preferences.set(manualCliPath, forKey: "SmartSearchDesktop.manualCLI")
        preferences.set(selectedID, forKey: "SmartSearchDesktop.selectedCLI")
    }

    func startAutomaticChecks() {
        guard automaticTask == nil else { return }
        automaticTask = Task { [weak self] in
            while !Task.isCancelled {
                do { try await Task.sleep(nanoseconds: 60_000_000_000) } catch { return }
                await self?.checkAutomatically()
            }
        }
    }

    func checkAutomatically(onLaunch: Bool = false) async {
        guard automaticallyChecks, npm != nil, !busy, !checking else { return }
        if !(onLaunch && !checkedAtLaunch) {
            if let date = update.checkedAt, clock().timeIntervalSince(date) < 86400 { return }
            if let date = update.attemptedAt, clock().timeIntervalSince(date) < 3600 { return }
        }
        checkedAtLaunch = true
        await checkVersion()
    }

    func discover() async {
        guard !busy, !checking else { return }
        busy = true
        defer { busy = false }
        if let detection = await detect() { show(detection) }
    }

    // Detects again while a CLI found earlier may be running; quietly, busy stays false and nothing shows
    // a detection in progress. What is shown keeps describing the running CLI: a detection that selects
    // another CLI waits for showRedetection (changed), and one without a CLI that can start is dropped (missing).
    func redetect(quietly: Bool) async -> Redetection {
        guard !busy, !checking else { return .unchanged }
        let before = selected
        if !quietly { busy = true }
        let detection = await detect()
        if !quietly { busy = false }
        guard let detection else { return .unchanged }
        guard let chosen = Self.find(detection, detection.selectedID), chosen.compatible else { return .missing }
        guard let before, Self.sameLaunch(before, chosen) else { held = detection; return .changed }
        show(detection)
        return .unchanged
    }

    // Shows the detection that selected another CLI, right before connecting to that CLI.
    func showRedetection() {
        if let held { show(held) }
    }

    // Shows the last detection when the CLI it selected can still start, so a launch can connect at once.
    func restoreLastDetection() -> Bool {
        guard let data = preferences.data(forKey: Self.detectionKey),
              let saved = try? JSONDecoder().decode(CLIDetection.self, from: data),
              saved.manualNpmPath == manualNpmPath, saved.manualCliPath == manualCliPath,
              let chosen = Self.find(saved, selectedID), chosen.compatible,
              FileManager.default.isExecutableFile(atPath: chosen.executable),
              chosen.arguments.allSatisfy({ FileManager.default.fileExists(atPath: $0) }) else { return false }
        installations = saved.installations
        npm = saved.npm
        message = saved.message
        return true
    }

    // The same CLI started the same way; any other version or argv would run something else.
    private static func sameLaunch(_ shown: CLIInstallation, _ detected: CLIInstallation) -> Bool {
        shown.id == detected.id && shown.executable == detected.executable && shown.arguments == detected.arguments &&
            shown.version == detected.version && shown.compatible == detected.compatible
    }

    // An empty id stands for the first installation, as on a first detection.
    private static func find(_ detection: CLIDetection, _ id: String) -> CLIInstallation? {
        id.isEmpty ? detection.installations.first : detection.installations.first { $0.id == id }
    }

    // Nil when a later detection started meanwhile: that one is current.
    private func detect() async -> CLIDetection? {
        detections += 1
        let number = detections
        var scan = CLIDetection(manualNpmPath: manualNpmPath, manualCliPath: manualCliPath)
        var searchPath = initialSearchPath ?? ProcessInfo.processInfo.environment["PATH"] ?? "/usr/bin:/bin"
        if initialSearchPath == nil, let loginPath = try? await Self.command(["/bin/zsh", "-lc", "print -r -- $PATH"]) {
            searchPath = loginPath.trimmingCharacters(in: .whitespacesAndNewlines) + ":" + searchPath
        }
        let paths = manualNpmPath.isEmpty ? npmCandidates(searchPath: searchPath) : [manualNpmPath]
        var seen = Set<String>()
        var npmEnvironments: [NpmEnvironment] = []
        for path in paths {
            do {
                let candidate = try await resolveNpm(path, searchPath: searchPath)
                if scan.npm == nil { scan.npm = candidate }
                if seen.insert(candidate.identity).inserted { npmEnvironments.append(candidate); await addInstallation(candidate, into: &scan) }
            }
            catch { if !manualNpmPath.isEmpty { scan.message = error.localizedDescription } }
        }
        if manualNpmPath.isEmpty { await discoverMise(searchPath: searchPath, into: &scan) }
        if !manualCliPath.isEmpty { await discoverManual(into: &scan) }
        // mise installs each version separately; follow the same tool after upgrades outside the App.
        var chosenID = selectedID
        if !chosenID.isEmpty, Self.find(scan, chosenID) == nil, manualCliPath.isEmpty,
           let mise = scan.installations.first(where: { $0.source == "mise" }),
           let selectedTool = Self.miseToolDirectory(chosenID),
           let activeTool = Self.miseToolDirectory(mise.id), selectedTool == activeTool {
            chosenID = mise.id
        }
        if !chosenID.isEmpty && Self.find(scan, chosenID) == nil { scan.message = L("所选安装已不可用，请重新检测或选择其他安装。") }
        let chosen = Self.find(scan, chosenID)
        scan.selectedID = chosen?.id ?? chosenID
        if let chosen {
            scan.npm = npmEnvironments.first { chosen.source == "npm" ? $0.prefix == chosen.prefix && $0.command == chosen.manager : $0.nodePath == chosen.executable } ?? scan.npm
        }
        if scan.npm == nil && scan.message.isEmpty && chosen == nil { scan.message = L("未找到可用的 npm。请先安装 Node.js，或手动指定 npm 路径。") }
        return number == detections ? scan : nil
    }

    private func show(_ detection: CLIDetection) {
        held = nil
        installations = detection.installations
        npm = detection.npm
        message = detection.message
        if selectedID != detection.selectedID {
            selectedID = detection.selectedID
            preferences.set(selectedID, forKey: "SmartSearchDesktop.selectedCLI")
        }
        // Another npm starts its own update record.
        if let npm = detection.npm, update.identity != npm.identity {
            update = CLIUpdateRecord(identity: npm.identity)
            checkedAtLaunch = false
            checkError = ""
            saveUpdateState()
        }
        // Only a shortcut for the next launch, which otherwise detects again.
        if let data = try? JSONEncoder().encode(detection) { preferences.set(data, forKey: Self.detectionKey) }
    }

    private func npmCandidates(searchPath: String) -> [String] {
        var directories = searchPath.split(separator: ":").map(String.init)
        if initialSearchPath == nil {
            let home = FileManager.default.homeDirectoryForCurrentUser.path
            let mise = ProcessInfo.processInfo.environment["MISE_DATA_DIR"] ?? home + "/.local/share/mise"
            directories += ["/opt/homebrew/bin", "/usr/local/bin", home + "/.local/bin", home + "/.volta/bin", mise + "/shims"]
            for root in [mise + "/installs/node", home + "/.nvm/versions/node"] {
                let versions = (try? FileManager.default.contentsOfDirectory(atPath: root)) ?? []
                directories += versions.sorted { $0.compare($1, options: .numeric) == .orderedDescending }.map { root + "/" + $0 + "/bin" }
            }
        }
        var seen = Set<String>()
        return directories.filter { $0.hasPrefix("/") }.map { $0 + "/npm" }
            .filter { seen.insert($0).inserted && FileManager.default.isExecutableFile(atPath: $0) }
    }

    private func resolveNpm(_ path: String, searchPath: String) async throws -> NpmEnvironment {
        guard path.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: path) else {
            throw CLIManagementError.failed(L("npm 路径无效，请选择可执行的 npm 文件。"))
        }
        let entry = URL(fileURLWithPath: path)
        let resolved = entry.resolvingSymlinksInPath()
        let node = entry.deletingLastPathComponent().appendingPathComponent("node").path
        guard FileManager.default.isExecutableFile(atPath: node) else {
            throw CLIManagementError.failed(L("npm 同目录下未找到 Node.js，请选择完整的 Node.js 安装。"))
        }
        var environment = ["PATH": entry.deletingLastPathComponent().path + ":" + searchPath]
        // Resolve version-manager shims once, then bind every operation to this
        // Node installation, independent of the App working directory.
        let actualNode = try await Self.command([node, "-p", "process.execPath"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
        guard actualNode.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: actualNode) else {
            throw CLIManagementError.failed(L("无法确认 Node.js 的实际路径。"))
        }
        let nodeDirectory = URL(fileURLWithPath: actualNode).deletingLastPathComponent()
        environment["PATH"] = nodeDirectory.path + ":" + searchPath
        let nodeVersion = try await Self.command([actualNode, "-p", "process.versions.node"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
        guard (Int(nodeVersion.split(separator: ".").first ?? "") ?? 0) >= 18 else {
            throw CLIManagementError.failed(L("请使用 Node.js 18 或更新版本。"))
        }
        let bundledScript = nodeDirectory.deletingLastPathComponent().appendingPathComponent("lib/node_modules/npm/bin/npm-cli.js")
        let script = resolved.lastPathComponent == "npm-cli.js" ? resolved : bundledScript
        guard FileManager.default.fileExists(atPath: script.path) else {
            throw CLIManagementError.failed(L("无法找到与 Node.js 配套的 npm，请重新选择 npm 路径。"))
        }
        let command = [actualNode, script.path]
        let version = try await Self.command(command + ["--version"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
        let prefix = try await Self.command(command + ["prefix", "--global"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
        let modules = try await Self.command(command + ["root", "--global", "--prefix", prefix], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
        guard Self.validVersion(version), prefix.hasPrefix("/"), modules.hasPrefix("/"), !prefix.contains("\n"), !modules.contains("\n") else {
            throw CLIManagementError.failed(L("npm 返回了无效的版本或安装目录。"))
        }
        return NpmEnvironment(npmPath: path, nodePath: actualNode, version: version, prefix: prefix, modules: modules, command: command, environment: environment)
    }

    private func addInstallation(_ npm: NpmEnvironment, into scan: inout CLIDetection, packageRoot: URL? = nil, source: String = "npm",
                                 manager: [String]? = nil, note: String = "", options: [String] = []) async {
        let root = packageRoot ?? URL(fileURLWithPath: npm.modules).appendingPathComponent(Self.package)
        guard let data = try? Data(contentsOf: root.appendingPathComponent("package.json")),
              let package = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              package["name"] as? String == Self.package else { return }
        var environment = npm.environment
        environment["SMART_SEARCH_PACKAGE_ROOT"] = root.path
        environment["SMART_SEARCH_NODE_PATH"] = npm.nodePath
        var installed = CLIInstallation(id: root.path, executable: npm.nodePath, arguments: [root.appendingPathComponent("npm/bin/smart-search.js").path],
            version: package["version"] as? String ?? "", source: source, manager: manager ?? npm.command, prefix: npm.prefix, environment: environment, note: note, managerOptions: options)
        // Never execute a legacy wrapper during detection: it may install Python.
        if package["smartSearchBinary"] as? Bool == true,
           let output = try? await Self.command([installed.executable] + installed.arguments + ["--desktop-capabilities"], environment: environment, timeout: 45),
           let info = try? JSONSerialization.jsonObject(with: Data(output.utf8)) as? [String: Any] {
            installed.compatible = info["product"] as? String == "smart-search" && info["desktop_protocol_version"] as? Int == 1 && info["version"] as? String == installed.version
        }
        if !installed.compatible && installed.note.isEmpty {
            installed.note = L("已找到 Smart Search CLI，但此版本不支持当前 App。请更新 CLI，或选择兼容的独立下载版。")
        }
        scan.installations.removeAll { $0.id == root.path }
        scan.installations.append(installed)
    }

    private func discoverMise(searchPath: String, into scan: inout CLIDetection) async {
        let directories = searchPath.split(separator: ":").map(String.init)
        guard let mise = directories.map({ $0 + "/mise" }).first(where: { $0.hasPrefix("/") && FileManager.default.isExecutableFile(atPath: $0) }) else { return }
        do {
            let tool = "npm:" + Self.package
            var environment = ["PATH": searchPath]
            let output = try await Self.command([mise, "ls", "--global", "--json", tool], environment: environment)
            let data = try JSONSerialization.jsonObject(with: Data(output.utf8))
            let rows = (data as? [[String: Any]]) ?? ((data as? [String: Any])?[tool] as? [[String: Any]]) ?? []
            if rows.isEmpty { return }
            guard try await Self.command([mise, "which", "--plugin", "smart-search"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines) == tool else { return }
            let entry = try await Self.command([mise, "which", "smart-search"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
            for row in rows {
                guard entry.hasPrefix("/"), row["active"] as? Bool == true, row["installed"] as? Bool == true,
                      let install = row["install_path"] as? String, install.hasPrefix("/"),
                      URL(fileURLWithPath: entry).standardized.path.hasPrefix(URL(fileURLWithPath: install).standardized.path + "/") else { continue }
                var node = try await Self.command([mise, "which", "node"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
                guard node.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: node) else { continue }
                node = try await Self.command([node, "-p", "process.execPath"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
                guard node.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: node) else { continue }
                let version = try await Self.command([node, "-p", "process.versions.node"], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
                guard (Int(version.split(separator: ".").first ?? "") ?? 0) >= 18 else { continue }
                environment["PATH"] = URL(fileURLWithPath: node).deletingLastPathComponent().path + ":" + searchPath
                let owner = row["source"] as? [String: String] ?? [:]
                let processEnv = ProcessInfo.processInfo.environment
                let global = processEnv["MISE_GLOBAL_CONFIG_FILE"] ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".config/mise/config.toml").path
                let owned = owner["type"] == "mise.toml" && owner["path"].map { URL(fileURLWithPath: $0).standardized.path } == URL(fileURLWithPath: global).standardized.path &&
                    (processEnv["MISE_CONFIG_FILE"] ?? "").isEmpty && (processEnv["MISE_ENV"] ?? "").isEmpty
                var options: [String]?
                if owned {
                    let config = try await Self.command([mise, "config", "get", "--global", "tools." + tool], environment: environment).trimmingCharacters(in: .whitespacesAndNewlines)
                    options = Self.miseOptions(config, requested: row["requested_version"] as? String ?? "")
                }
                let modules = URL(fileURLWithPath: install).appendingPathComponent("node_modules")
                let context = NpmEnvironment(npmPath: "", nodePath: node, version: "", prefix: install, modules: modules.path, command: [], environment: environment)
                await addInstallation(context, into: &scan, packageRoot: modules.appendingPathComponent(Self.package), source: "mise", manager: options == nil ? [] : [mise],
                    note: options == nil ? L("此 mise 安装有环境覆盖或复杂版本约束，请在原终端更新。") : "", options: options ?? [])
                if let index = scan.installations.firstIndex(where: { $0.source == "mise" }) { let chosen = scan.installations.remove(at: index); scan.installations.insert(chosen, at: 0) }
            }
        } catch { scan.message = L("mise 环境检测未完成，请重新检测或手动选择 CLI。") + "\n" + error.localizedDescription }
    }

    static func miseToolDirectory(_ packageRoot: String) -> String? {
        let package = URL(fileURLWithPath: packageRoot)
        let scope = package.deletingLastPathComponent()
        let modules = scope.deletingLastPathComponent()
        let tool = modules.deletingLastPathComponent().deletingLastPathComponent()
        guard package.lastPathComponent == "smart-search", scope.lastPathComponent == "@konbakuyomu",
              modules.lastPathComponent == "node_modules", tool.lastPathComponent == "npm-konbakuyomu-smart-search" else { return nil }
        return tool.standardized.path
    }

    static func miseOptions(_ config: String, requested: String) -> [String]? {
        guard validVersion(requested) || requested == "latest" else { return nil }
        if config == requested || config == "\"" + requested + "\"" { return [] }
        let lines = config.split(separator: "\n").map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }.filter { !$0.isEmpty }
        guard lines.contains("version = \"" + requested + "\"") else { return nil }
        var options: [String] = []
        for line in lines where !line.hasPrefix("version = ") {
            guard line.range(of: #"^allow_low_downloads = (true|false|"true"|"false")$"#, options: .regularExpression) != nil else { return nil }
            options += ["--tool-option", "allow_low_downloads=" + String(line.dropFirst("allow_low_downloads = ".count))]
        }
        return options
    }

    private func discoverManual(into scan: inout CLIDetection) async {
        do {
            guard manualCliPath.hasPrefix("/"), FileManager.default.isExecutableFile(atPath: manualCliPath) else {
                throw CLIManagementError.failed(L("请选择独立下载包中的 smart-search 可执行文件。"))
            }
            let root = URL(fileURLWithPath: manualCliPath).deletingLastPathComponent()
            let data = try Data(contentsOf: root.appendingPathComponent("package.json"))
            guard let manifest = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                  manifest["name"] as? String == Self.package, FileManager.default.fileExists(atPath: root.appendingPathComponent("_internal").path) else {
                throw CLIManagementError.failed(L("请选择完整独立下载包中的 CLI，不要选择全局 shim 或脚本。"))
            }
            let output = try await Self.command([manualCliPath, "--desktop-capabilities"], timeout: 45)
            guard let info = try JSONSerialization.jsonObject(with: Data(output.utf8)) as? [String: Any],
                  info["product"] as? String == "smart-search", info["desktop_protocol_version"] as? Int == 1, info["version"] as? String == manifest["version"] as? String else {
                throw CLIManagementError.failed(L("所选 CLI 与当前 App 不兼容。"))
            }
            scan.installations.append(CLIInstallation(id: manualCliPath, executable: manualCliPath, version: info["version"] as? String ?? "", source: "manual", compatible: true))
        } catch { scan.message = error.localizedDescription }
    }

    func checkVersion() async {
        guard let npm, !busy, !checking else { return }
        checking = true
        update.attemptedAt = clock()
        saveUpdateState()
        defer { checking = false }
        do {
            let version: String
            let supportsBinary: Bool
            if let versionLoader { version = try await versionLoader(); supportsBinary = true }
            else {
                let output = try await Self.command(npm.command + ["view", Self.package + "@latest", "--json"], environment: npm.environment, timeout: 60)
                guard let metadata = try JSONSerialization.jsonObject(with: Data(output.utf8)) as? [String: Any] else {
                    throw CLIManagementError.failed(L("无法读取 CLI 发行信息，请稍后重试。"))
                }
                version = metadata["version"] as? String ?? ""
                supportsBinary = metadata["smartSearchBinary"] as? Bool == true
            }
            guard Self.validVersion(version) else { throw CLIManagementError.failed(L("无法确认 CLI 的最新版本。")) }
            update.latestVersion = version
            update.supportsBinary = supportsBinary
            update.checkedAt = clock()
            checkError = ""
            saveUpdateState()
        } catch { checkError = error.localizedDescription }
    }

    private func saveUpdateState() {
        if let data = try? JSONEncoder().encode(update) { preferences.set(data, forKey: "SmartSearchDesktop.cliUpdateState") }
    }

    func installOrRepair(expectedVersion: String) async throws {
        guard !busy, !checking else { return }
        let previous = selected
        await discover()
        if let previous, previous.id != selected?.id || previous.source != selected?.source || previous.version != selected?.version || previous.manager != selected?.manager || previous.managerOptions != selected?.managerOptions {
            throw CLIManagementError.failed(L("CLI 来源或版本刚刚发生变化，请重新检查后再更新。"))
        }
        guard canInstall else { throw CLIManagementError.failed(L("请在原管理器中更新，或选择其他安装。")) }
        guard Self.validVersion(expectedVersion), expectedVersion == latestVersion, checkError.isEmpty else {
            throw CLIManagementError.failed(L("请先成功检查 CLI 更新。"))
        }
        guard latestSupportsBinary else { throw CLIManagementError.failed(L("npm 上尚未发布自带运行时的 CLI，请等待新版发布后再安装。")) }
        busy = true
        message = L("正在通过原管理器安装或更新 CLI…")
        defer { busy = false }
        if let selected, selected.source == "mise" {
            _ = try await Self.command(selected.manager + ["use", "--global", "--pin"] + selected.managerOptions + ["npm:" + Self.package + "@" + expectedVersion], environment: selected.environment, timeout: 1800)
            selectedID = ""
        } else {
            let command = selected?.manager ?? npm!.command
            let prefix = selected?.prefix ?? npm!.prefix
            _ = try await Self.command(command + ["install", "--global", "--prefix", prefix, "--include=optional", Self.package + "@" + expectedVersion], environment: selected?.environment ?? npm!.environment, timeout: 1800)
        }
        busy = false
        await discover()
        guard selected?.version == expectedVersion, selected?.compatible == true else {
            throw CLIManagementError.failed(L("CLI 已安装，但运行验证未通过，请更新或修复。"))
        }
        message = L("CLI 安装完成，正在重新连接。")
    }

    func uninstall() async throws {
        guard let selected, selected.canManage, selected.source == "npm", !busy, !checking else { return }
        busy = true
        defer { busy = false }
        _ = try await Self.command(selected.manager + ["uninstall", "--global", "--prefix", selected.prefix, Self.package], environment: selected.environment, timeout: 600)
        installations = []
        selectedID = ""
        preferences.set(selectedID, forKey: "SmartSearchDesktop.selectedCLI")
        message = L("CLI 已卸载，配置和 Skills 已保留。")
    }

    private static func validVersion(_ value: String) -> Bool { value.range(of: #"^[0-9]+\.[0-9]+\.[0-9]+$"#, options: .regularExpression) != nil }

    nonisolated static func command(_ arguments: [String], environment: [String: String] = [:], timeout: TimeInterval = 15) async throws -> String {
        try await Task.detached {
            let process = Process(), output = Pipe(), diagnostics = Pipe()
            process.executableURL = URL(fileURLWithPath: arguments[0])
            process.arguments = Array(arguments.dropFirst())
            process.currentDirectoryURL = FileManager.default.homeDirectoryForCurrentUser
            process.environment = ProcessInfo.processInfo.environment.merging(environment) { _, value in value }
            process.standardInput = FileHandle.nullDevice
            process.standardOutput = output
            process.standardError = diagnostics
            try process.run()
            let errors = Task.detached { diagnostics.fileHandleForReading.readDataToEndOfFile() }
            let stop = DispatchWorkItem { if process.isRunning { process.terminate() } }
            DispatchQueue.global().asyncAfter(deadline: .now() + timeout, execute: stop)
            let data = output.fileHandleForReading.readDataToEndOfFile()
            process.waitUntilExit()
            stop.cancel()
            let detail = String(decoding: await errors.value, as: UTF8.self)
            guard process.terminationStatus == 0 else { throw CLIManagementError.failed(L("CLI 操作未完成，请检查 npm 或重试。") + "\n" + detail.suffix(2000)) }
            return String(decoding: data, as: UTF8.self)
        }.value
    }
}
