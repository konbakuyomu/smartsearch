import Foundation

/// The desktop protocol intentionally carries dynamic business data.  Keeping it
/// as JSON here prevents the macOS client from inventing business rules owned by Python.
indirect enum JSONValue: Codable, Equatable, Hashable, Sendable {
    case object([String: JSONValue])
    case array([JSONValue])
    case string(String)
    case number(Double)
    case bool(Bool)
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Unsupported JSON value")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case let .object(value): try container.encode(value)
        case let .array(value): try container.encode(value)
        case let .string(value): try container.encode(value)
        case let .number(value): try container.encode(value)
        case let .bool(value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    var objectValue: [String: JSONValue]? {
        guard case let .object(value) = self else { return nil }
        return value
    }

    var arrayValue: [JSONValue]? {
        guard case let .array(value) = self else { return nil }
        return value
    }

    var stringValue: String? {
        guard case let .string(value) = self else { return nil }
        return value
    }

    var boolValue: Bool? {
        guard case let .bool(value) = self else { return nil }
        return value
    }

    var numberValue: Double? {
        guard case let .number(value) = self else { return nil }
        return value
    }

    var integerValue: Int? {
        guard let numberValue, numberValue.rounded() == numberValue else { return nil }
        return Int(numberValue)
    }

    var displayString: String {
        switch self {
        case let .string(value): return value
        case let .number(value): return value.rounded() == value ? String(Int(value)) : String(value)
        case let .bool(value): return value ? "true" : "false"
        case .null: return ""
        case .array, .object: return prettyPrinted()
        }
    }

    subscript(key: String) -> JSONValue? {
        objectValue?[key]
    }

    func prettyPrinted() -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        guard let data = try? encoder.encode(self),
              let string = String(data: data, encoding: .utf8) else {
            return ""
        }
        return string
    }

    /// Raw results and diagnostics must never turn a returned secret into UI text.
    func redacted() -> JSONValue {
        redactingSensitiveKeys()
    }

    func redactingSensitiveKeys() -> JSONValue {
        switch self {
        case let .object(values):
            var result: [String: JSONValue] = [:]
            for (key, value) in values {
                let normalized = key.lowercased()
                if ["key", "token", "secret", "password", "authorization", "credential"].contains(where: { normalized.contains($0) }) {
                    result[key] = .string("***")
                } else {
                    result[key] = value.redactingSensitiveKeys()
                }
            }
            return .object(result)
        case let .array(values):
            return .array(values.map { $0.redactingSensitiveKeys() })
        default:
            return self
        }
    }
}

extension Dictionary where Key == String, Value == JSONValue {
    func string(_ key: String) -> String? { self[key]?.stringValue ?? self[key]?.displayString }
    func bool(_ key: String) -> Bool? { self[key]?.boolValue }
    func array(_ key: String) -> [JSONValue] { self[key]?.arrayValue ?? [] }
    func object(_ key: String) -> [String: JSONValue] { self[key]?.objectValue ?? [:] }
}

enum Destination: String, CaseIterable, Identifiable, Hashable {
    case overview
    case providers
    case search
    case activity
    case integration
    case settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .overview: return L("概览")
        case .providers: return L("服务商")
        case .search: return L("搜索与研究")
        case .activity: return L("活动")
        case .integration: return L("更新 Skills")
        case .settings: return L("设置与关于")
        }
    }

    var symbol: String {
        switch self {
        case .overview: return "rectangle.3.group"
        case .providers: return "key.horizontal"
        case .search: return "magnifyingglass"
        case .activity: return "clock.arrow.circlepath"
        case .integration: return "terminal"
        case .settings: return "gearshape"
        }
    }
}

struct ConfigField: Identifiable, Hashable {
    let key: String
    let section: String
    let tier: String
    let kind: String
    let label: String
    let help: String
    let choices: [String]
    let provider: String?
    let capabilities: [String]
    let keyURL: String?
    let docsURL: String?
    let defaultValue: String
    let placeholder: String
    let isProviderToggle: Bool

    var id: String { key }
    var isAdvanced: Bool { tier == "advanced" || ["routing", "reliability", "diagnostics"].contains(section) }
    var isSecret: Bool {
        let normalized = kind.lowercased() + " " + key.lowercased()
        return normalized.contains("password") || normalized.contains("secret") || normalized.contains("api_key") || normalized.contains("token")
    }

    var inputPlaceholder: String { L("示例：{0}", exampleValue) }

    private var exampleValue: String {
        if !placeholder.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return placeholder }
        if !defaultValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return defaultValue }
        switch key {
        case "OPENAI_COMPATIBLE_MODEL", "INTENT_CLASSIFIER_MODEL": return "gpt-4o"
        case "OPENAI_COMPATIBLE_FALLBACK_MODELS": return "gpt-4o,deepseek-chat"
        case "JINA_RESPOND_WITH": return "readerlm-v2"
        case "INTENT_EMBEDDING_API_URL": return "https://api.siliconflow.cn/v1/embeddings"
        case "INTENT_EMBEDDING_MODEL": return "Qwen/Qwen3-Embedding-8B"
        case "INTENT_CLASSIFIER_API_URL": return "https://api.example.com/v1/chat/completions"
        case "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS": return "exa,tavily"
        case "SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS": return "anysearch,sciverse"
        default: break
        }
        if isSecret { return key.hasSuffix("TOKEN") ? "your-api-token" : "your-api-key" }
        switch kind {
        case "url": return "https://api.example.com/v1"
        case "int": return "3"
        case "float": return "0.5"
        case "csv": return "value1,value2"
        default: return "example"
        }
    }

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue, let key = raw.string("key") else { return nil }
        self.key = key
        section = raw.string("section") ?? "providers"
        tier = raw.string("tier") ?? "common"
        kind = raw.string("kind") ?? "text"
        label = raw.string("label_" + Localization.language) ?? raw.string("label_en") ?? key
        help = raw.string("help_" + Localization.language) ?? raw.string("help_en") ?? ""
        choices = raw.array("choices").compactMap(\.stringValue)
        provider = raw.string("provider")
        capabilities = raw.array("capabilities").compactMap(\.stringValue)
        keyURL = raw.string("key_url")
        docsURL = raw.string("docs_url")
        defaultValue = raw["default"]?.displayString ?? ""
        placeholder = raw.string("placeholder") ?? defaultValue
        isProviderToggle = raw.bool("provider_toggle") ?? false
    }
}

struct ConfigSection: Identifiable, Hashable {
    let id: String
    let order: Int
    let label: String
    let blurb: String

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue, let id = raw.string("id") else { return nil }
        self.id = id
        order = raw["order"]?.integerValue ?? Int.max
        label = raw.string("label_" + Localization.language) ?? raw.string("label_en") ?? id
        blurb = raw.string("blurb_" + Localization.language) ?? raw.string("blurb_en") ?? ""
    }
}

struct ProviderFieldGroup: Identifiable {
    let id: String
    let fields: [ConfigField]
    let profile: [String: JSONValue]

    var primaryCapability: String? { capabilities.first }

    var capabilities: [String] {
        // Runtime profiles own the classification. Field tiers describe setup
        // requirements, not a provider's primary role (for example, Tavily).
        let declared = ([profile.string("capability")].compactMap { $0 }
            + profile.array("capabilities").compactMap(\.stringValue)).filter { !$0.isEmpty }
        let available = declared.isEmpty ? fields.flatMap(\.capabilities) : declared
        var seen: Set<String> = []
        return available.filter { !$0.isEmpty && seen.insert($0).inserted }
    }

    var purposeDescriptions: [String] {
        localizedDescriptions("")
    }

    var purposeGuidance: [String] {
        localizedDescriptions("guidance_")
    }

    private func localizedDescriptions(_ prefix: String) -> [String] {
        let descriptions = profile["descriptions"]?.objectValue ?? [:]
        return ["search", "fetch", "site_map", "synthesis"].compactMap { operation in
            let translations = descriptions[operation]?.objectValue ?? [:]
            return translations[prefix + Localization.language]?.stringValue ?? translations[prefix + "en"]?.stringValue
        }
    }
    var isExperimental: Bool { profile.bool("experimental") == true }
    var isExplicitOnly: Bool { profile.bool("explicit_only") == true }
    var isRoutingDisabled: Bool { profile.bool("route_enabled") == false }
}

struct OperationState {
    private var requests: Set<String> = []
    private var runs: [String: Set<String>] = [:]
    var busyKeys: Set<String> { requests.union(runs.values.reduce(into: Set<String>()) { $0.formUnion($1) }) }

    mutating func begin(_ key: String) -> Bool {
        guard !busyKeys.contains(key) else { return false }
        return requests.insert(key).inserted
    }
    mutating func endRequest(_ key: String) { requests.remove(key) }
    mutating func track(_ runID: String, key: String) { runs[runID, default: []].insert(key) }
    mutating func finish(_ runID: String) { runs.removeValue(forKey: runID) }
    mutating func reset() { requests.removeAll(); runs.removeAll() }
}

struct CommandField: Identifiable, Hashable {
    let name: String
    let label: String
    let help: String
    let flags: [String]
    let kind: String
    let choices: [String]
    let required: Bool
    let defaultValue: JSONValue?
    let multiple: Bool
    let nargs: String?
    let advanced: Bool?

    var id: String { name }
    var isBoolean: Bool { kind.lowercased() == "bool" }
    var isPositional: Bool { flags.isEmpty }
    var acceptsMultipleValues: Bool { multiple || nargs != nil }
    var isAdvanced: Bool { advanced ?? !required }

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue, let name = raw.string("name") else { return nil }
        self.name = name
        label = L(raw.string("label") ?? name)
        help = L(raw.string("help") ?? "")
        flags = raw.array("flags").compactMap(\.stringValue)
        kind = raw.string("kind") ?? "text"
        choices = raw.array("choices").compactMap(\.stringValue)
        required = raw.bool("required") ?? false
        defaultValue = raw["default"]
        multiple = raw.bool("multiple") ?? false
        nargs = raw["nargs"]?.stringValue
        advanced = raw["advanced"]?.boolValue
    }
}

struct CommandCatalogEntry: Identifiable, Hashable {
    let id: String
    let label: String
    let description: String
    let experimental: Bool
    let fields: [CommandField]

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue, let id = raw.string("id") else { return nil }
        self.id = id
        label = L(raw.string("label") ?? id)
        description = L(raw.string("description") ?? "")
        experimental = raw.bool("experimental") ?? false
        fields = raw.array("fields").compactMap(CommandField.init)
    }
}

struct SkillTarget: Identifiable, Hashable {
    let id: String
    let label: String
    let isDefault: Bool
    let status: String?

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue, let id = raw.string("id") ?? raw.string("target") else { return nil }
        self.id = id
        label = raw.string("label") ?? id
        isDefault = raw.bool("default") ?? false
        status = raw.string("status")
    }
}

struct ActivityRun: Identifiable, Hashable {
    let runID: String
    let command: String
    let origin: String
    let configDirectory: String?
    let status: String
    let phase: String?
    let provider: String?
    let model: String?
    let configRevision: String?
    let elapsedMilliseconds: Int?
    let errorType: String?
    let sourcesCount: Int?
    let updatedAt: Date?
    let raw: JSONValue

    var id: String { runID }
    var isActive: Bool { status == "running" || status == "cancelling" }

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue, let runID = raw.string("run_id") else { return nil }
        self.runID = runID
        command = raw.string("command") ?? L("未知命令")
        origin = raw.string("origin") ?? "unknown"
        configDirectory = raw.string("config_dir")
        status = raw.string("status") ?? "unknown"
        phase = raw.string("phase")
        provider = raw.string("provider")
        model = raw.string("model")
        configRevision = raw.string("config_revision")
        elapsedMilliseconds = raw["elapsed_ms"]?.integerValue
        errorType = raw.string("error_type")
        sourcesCount = raw["sources_count"]?.integerValue
        updatedAt = raw["updated_at"]?.numberValue.map(Date.init(timeIntervalSince1970:))
        self.raw = value
    }

    var elapsedText: String {
        let milliseconds = elapsedMilliseconds ?? 0
        if milliseconds < 1_000 { return "\(milliseconds) ms" }
        return String(format: L("%.1f 秒"), Double(milliseconds) / 1_000)
    }
}

enum OwnedRunKind: Hashable {
    case business
    case providerTest
    case skillsInstall

    var updatesSearchResult: Bool { self == .business }
}

struct OwnedRunDescriptor: Hashable {
    let kind: OwnedRunKind
    let label: String
    var commandID: String? = nil
    var providerID: String? = nil
}

struct OwnedRunResultStore {
    let capacity: Int
    private(set) var descriptors: [String: OwnedRunDescriptor] = [:]
    private(set) var results: [String: JSONValue] = [:]
    private var resultOrder: [String] = []

    init(capacity: Int) {
        self.capacity = max(1, capacity)
    }

    mutating func register(runID: String, kind: OwnedRunKind, label: String,
                           commandID: String? = nil, providerID: String? = nil) {
        descriptors[runID] = OwnedRunDescriptor(kind: kind, label: label, commandID: commandID, providerID: providerID)
    }

    @discardableResult
    mutating func cache(_ result: JSONValue, for runID: String) -> OwnedRunDescriptor? {
        guard let descriptor = descriptors[runID] else { return nil }
        if results[runID] == nil { resultOrder.append(runID) }
        results[runID] = result
        // ponytail: mirrors the backend's 100 completed app-run cap; add paging only if it grows.
        while resultOrder.count > capacity {
            let expiredRunID = resultOrder.removeFirst()
            results.removeValue(forKey: expiredRunID)
            descriptors.removeValue(forKey: expiredRunID)
        }
        return descriptor
    }

    func descriptor(for runID: String) -> OwnedRunDescriptor? {
        descriptors[runID]
    }

    func result(for runID: String) -> JSONValue? {
        results[runID]
    }
}

struct DesktopState {
    let raw: JSONValue
    let revision: JSONValue?
    let configPath: String?
    let configDirectory: String?
    let defaultConfigDirectory: String?
    let isDefaultConfigDirectory: Bool
    let generation: String?
    let version: String?
    let values: [String: JSONValue]
    let savedValues: [String: JSONValue]
    let sources: [String: JSONValue]
    let fields: [ConfigField]
    let sections: [ConfigSection]
    let commands: [CommandCatalogEntry]
    let skillTargets: [SkillTarget]
    let minimumProfile: JSONValue?
    let capabilityStatus: JSONValue?
    let capabilityChains: [String: [String]]
    let statusLabels: [String: String]
    let providerHealth: JSONValue?
    let providerChecks: JSONValue?
    let cli: JSONValue?

    init?(_ value: JSONValue) {
        guard let raw = value.objectValue else { return nil }
        self.raw = value
        revision = raw["revision"]
        configPath = raw.string("config_path")
        configDirectory = raw.string("config_dir")
        defaultConfigDirectory = raw.string("default_config_dir")
        isDefaultConfigDirectory = raw.bool("is_default_config_dir") ?? false
        generation = raw.string("generation")
        version = raw.string("version")
        values = raw.object("values")
        savedValues = raw.object("saved_values")
        sources = raw.object("sources")
        fields = raw.object("metadata").array("fields").compactMap(ConfigField.init)
        sections = raw.object("metadata").array("sections").compactMap(ConfigSection.init).sorted { $0.order < $1.order }
        commands = raw.array("commands").compactMap(CommandCatalogEntry.init)
        skillTargets = raw.array("skill_targets").compactMap(SkillTarget.init)
        minimumProfile = raw["minimum_profile"]
        capabilityStatus = raw["capability_status"]
        capabilityChains = raw.object("capability_chains").mapValues { $0.arrayValue?.compactMap(\.stringValue) ?? [] }
        statusLabels = raw.object("metadata").object("status_labels").mapValues { $0[Localization.language]?.stringValue ?? L("状态未知") }
        providerHealth = raw["provider_health"]
        providerChecks = raw["provider_checks"]
        cli = raw["cli"]
    }

    var minimumProfileOK: Bool? {
        if let value = minimumProfile?.boolValue { return value }
        return minimumProfile?["ok"]?.boolValue
    }

    var minimumMissing: [String] {
        minimumProfile?["missing"]?.arrayValue?.map(\.displayString) ?? []
    }

    func effectiveValue(for field: ConfigField) -> String {
        values[field.key]?.displayString ?? field.defaultValue
    }

    func hasSecretValue(for field: ConfigField) -> Bool {
        raw["secret_presence"]?[field.key]?.boolValue ?? !effectiveValue(for: field).isEmpty
    }

    func savedValue(for field: ConfigField) -> String {
        savedValues[field.key]?.displayString ?? ""
    }

    func source(for field: ConfigField) -> String {
        sources[field.key]?.displayString ?? "unknown"
    }

    func phaseLabel(_ phase: String) -> String {
        ["provider.test": L("服务商测试"), "version": L("版本查询"), "skills.install": L("安装 / 更新 Skills"),
         "started": L("已启动"), "planning": L("制定计划")][phase]
            ?? commands.first { $0.id == phase }?.label
            ?? statusLabels[phase]
            ?? L("处理中")
    }

    func activityRuns() -> [ActivityRun] {
        raw["activity"]?["runs"]?.arrayValue?.compactMap(ActivityRun.init) ?? []
    }

    var providerGroups: [ProviderFieldGroup] {
        var seen: Set<String> = []
        return fields.compactMap { field in
            guard let provider = field.provider, !provider.isEmpty, seen.insert(provider).inserted else { return nil }
            return ProviderFieldGroup(id: provider, fields: fields.filter { $0.provider == provider },
                                      profile: raw["provider_profiles"]?[provider]?.objectValue ?? [:])
        }
    }
}

enum CommandArgumentBuilder {
    static func arguments(
        for command: CommandCatalogEntry,
        values: [String: String],
        booleans: [String: Bool]
    ) -> [String] {
        var arguments: [String] = []
        for field in command.fields {
            if field.isBoolean {
                if booleans[field.name] == true, let flag = field.flags.first {
                    arguments.append(flag)
                }
                continue
            }

            let raw = values[field.name]?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            guard !raw.isEmpty else { continue }
            let entries = field.acceptsMultipleValues
                ? raw.split(whereSeparator: { $0.isNewline }).map(String.init)
                : [raw]
            for entry in entries where !entry.isEmpty {
                if let flag = field.flags.first {
                    arguments += [flag, entry]
                } else {
                    arguments.append(entry)
                }
            }
        }
        return arguments
    }

    static func missingRequired(
        for command: CommandCatalogEntry,
        values: [String: String],
        booleans: [String: Bool]
    ) -> [CommandField] {
        command.fields.filter { field in
            guard field.required else { return false }
            if field.isBoolean { return booleans[field.name] != true }
            return (values[field.name] ?? "").trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }
}
