import AppKit
import SwiftUI

struct ContentView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        NavigationSplitView {
            List {
                HStack(spacing: 10) {
                    Image(nsImage: NSApp.applicationIconImage)
                        .resizable().scaledToFit().frame(width: 36, height: 36)
                        .padding(3)
                        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 6))
                        .accessibilityLabel("Smart Search 图标")
                    Text("Smart Search").font(.headline)
                }
                Section("Smart Search") {
                    ForEach(Destination.allCases) { destination in
                        Button {
                            model.selectedDestination = destination
                        } label: {
                            HStack {
                                Label(destination.title, systemImage: destination.symbol)
                                Spacer()
                                if model.selectedDestination == destination {
                                    Image(systemName: "checkmark")
                                        .foregroundStyle(.tint)
                                }
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .listStyle(.sidebar)
            .navigationTitle("Smart Search")
        } detail: {
            VStack(spacing: 0) {
                if let error = model.errorMessage {
                    MessageBanner(message: error, symbol: "exclamationmark.triangle.fill", tint: .red) {
                        model.errorMessage = nil
                    }
                }
                if let notice = model.noticeMessage {
                    MessageBanner(message: notice, symbol: "checkmark.circle.fill", tint: .green) {
                        model.noticeMessage = nil
                    }
                }
                destinationView
            }
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        Task { await model.refreshState() }
                    } label: {
                        Label("刷新状态", systemImage: "arrow.clockwise")
                    }
                    .disabled(model.connection == .connecting)
                }
                ToolbarItem(placement: .automatic) {
                    ConnectionIndicator(state: model.connection)
                }
            }
        }
        .onChange(of: model.selectedDestination) { destination in
            Task { await model.enter(destination) }
        }
        .task {
            await model.enter(model.selectedDestination)
        }
    }

    @ViewBuilder
    private var destinationView: some View {
        switch model.selectedDestination {
        case .overview: OverviewView(model: model)
        case .providers: ProvidersView(model: model)
        case .search: SearchResearchView(model: model)
        case .activity: ActivityView(model: model)
        case .integration: IntegrationView(model: model)
        case .settings: SettingsAboutView(model: model)
        }
    }
}

private struct MessageBanner: View {
    let message: String
    let symbol: String
    let tint: Color
    let dismiss: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: symbol).foregroundStyle(tint)
            Text(message).fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 8)
            Button(action: dismiss) { Image(systemName: "xmark") }
                .buttonStyle(.borderless)
                .accessibilityLabel("关闭提示")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(tint.opacity(0.10))
    }
}

private struct ConnectionIndicator: View {
    let state: AppModel.ConnectionState

    var body: some View {
        Label(state.title, systemImage: state.symbol)
            .foregroundStyle(tint)
            .accessibilityLabel("后端状态：\(state.title)")
    }

    private var tint: Color {
        switch state {
        case .ready: return .green
        case .connecting: return .orange
        case .failed: return .red
        case .disconnected: return .secondary
        }
    }
}

private struct BackendUnavailableView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: model.connection == .failed ? "bolt.horizontal.circle" : "desktopcomputer")
                .font(.system(size: 42))
                .foregroundStyle(.secondary)
            Text(model.connection == .failed ? "后端目前不可用" : "正在连接本机后端")
                .font(.title2.weight(.semibold))
            Text("页面没有显示模拟数据。连接后会读取当前配置、工具目录和活动记录。")
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("重新连接") { Task { await model.reconnect() } }
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }
}

private struct OverviewView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        guard let state = model.state else { return AnyView(BackendUnavailableView(model: model)) }
        return AnyView(ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("概览").font(.largeTitle.weight(.bold))
                    Text("查看实际配置状态，决定下一步操作。打开此页不会发起服务商探针。")
                        .foregroundStyle(.secondary)
                }

                GroupBox("首次配置") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text("主搜索用于回答问题；文档检索用于查库文档；网页抓取用于读取链接。配好之后请自己点一次测试，App 不会自动发起计费探针。")
                            .foregroundStyle(.secondary)
                        if state.minimumProfileOK == true {
                            Label("基础能力已配置", systemImage: "checkmark.circle.fill")
                                .foregroundStyle(.green)
                            Text("这表示后端已根据当前配置计算出基础条件；它不代表刚刚进行了真实服务商测试。")
                                .foregroundStyle(.secondary)
                        } else if state.minimumProfileOK == false {
                            Label("还需要补齐配置", systemImage: "exclamationmark.circle.fill")
                                .foregroundStyle(.orange)
                            if state.minimumMissing.isEmpty {
                                Text("后端未列出缺失能力。请在服务商页查看当前字段。")
                                    .foregroundStyle(.secondary)
                            } else {
                                ForEach(state.minimumMissing, id: \.self) { item in
                                    Label(item, systemImage: "circle")
                                }
                            }
                            HStack {
                                Button("打开服务商配置") { model.selectedDestination = .providers }
                                    .buttonStyle(.borderedProminent)
                                Button("选择配置目录") { model.selectedDestination = .settings }
                            }
                        } else {
                            Text("后端尚未报告基础配置状态。")
                                .foregroundStyle(.secondary)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("当前环境") {
                    Grid(alignment: .leading, horizontalSpacing: 20, verticalSpacing: 10) {
                        GridRow {
                            Text("配置文件").foregroundStyle(.secondary)
                            Text(state.configPath ?? "后端未提供")
                                .textSelection(.enabled)
                        }
                        GridRow {
                            Text("配置目录").foregroundStyle(.secondary)
                            Text(state.configDirectory ?? "后端未提供")
                                .textSelection(.enabled)
                        }
                        GridRow {
                            Text("内置引擎").foregroundStyle(.secondary)
                            Text(state.version ?? "后端未提供")
                        }
                        GridRow {
                            Text("协议 generation").foregroundStyle(.secondary)
                            Text(state.generation ?? "后端未提供")
                                .textSelection(.enabled)
                        }
                        GridRow {
                            Text("最后读取").foregroundStyle(.secondary)
                            Text(model.lastStateRefresh?.formatted(date: .abbreviated, time: .standard) ?? "尚未读取")
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                if let capabilityStatus = state.capabilityStatus, let details = capabilityStatus.objectValue, !details.isEmpty {
                    GroupBox("能力状态") {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("此处是当前配置是否满足路由条件，不是刚刚完成的联网验证。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            ForEach(details.keys.sorted(), id: \.self) { key in
                                CapabilityStatusRow(capability: key, status: details[key] ?? .object([:]))
                            }
                        }
                    }
                }
            }
            .padding(24)
            .frame(maxWidth: 940, alignment: .leading)
        })
    }
}

private struct ProvidersView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        guard let state = model.state else { return AnyView(BackendUnavailableView(model: model)) }
        let sections = state.fields.reduce(into: [String: [ConfigField]]()) { $0[$1.section, default: []].append($1) }
        return AnyView(ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("服务商与配置").font(.largeTitle.weight(.bold))
                    Text("改完可以先测试再保存。来源是环境变量的项目只读，保存会带上当前 revision。")
                        .foregroundStyle(.secondary)
                }

                HStack(spacing: 10) {
                    Button {
                        Task { await model.previewConfig() }
                    } label: {
                        BusyLabel(text: "检查这样够不够", busyText: "检查中…", busy: model.isBusy.contains("preview"))
                    }
                    .disabled(model.connection != .ready || model.isBusy.contains("preview"))
                    Button {
                        Task { await model.saveConfig() }
                    } label: {
                        BusyLabel(text: "保存配置", busyText: "保存中…", busy: model.isBusy.contains("save"))
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.connection != .ready || model.isBusy.contains("save")
                              || (model.configDraft.isEmpty && model.clearSecretKeys.isEmpty))
                    Button("放弃修改", role: .cancel) { model.resetConfigDraft() }
                        .disabled(model.configDraft.isEmpty && model.clearSecretKeys.isEmpty)
                    Spacer()
                    Text("revision：\(state.revision?.displayString ?? "后端未提供")")
                        .foregroundStyle(.secondary)
                        .textSelection(.enabled)
                }

                if let preview = model.configPreview {
                    ConfigPreviewView(preview: preview)
                }

                ProviderHealthView(health: state.providerHealth)
                ProviderDraftChecksView(checks: state.providerChecks)

                if sections.isEmpty {
                    GroupBox("配置字段") {
                        Text("后端没有提供可编辑字段。")
                            .foregroundStyle(.secondary)
                    }
                }

                // Follow the backend's declared order. Sorting the raw ids
                // alphabetically put `diagnostics` first, so a new user met the
                // log level and the SSL switch before "start here".
                ForEach(orderedSectionIDs(state: state, present: Set(sections.keys)), id: \.self) { section in
                    let fields = sections[section] ?? []
                    ProviderSection(
                        model: model,
                        state: state,
                        section: section,
                        title: state.sections.first { $0.id == section }?.label,
                        blurb: state.sections.first { $0.id == section }?.blurb ?? "",
                        fields: fields)
                }
            }
            .padding(24)
            .frame(maxWidth: 980, alignment: .leading)
        })
    }
}

/// Section ids in backend order, with anything the backend did not describe
/// appended alphabetically so a new section never vanishes from the page.
private func orderedSectionIDs(state: DesktopState, present: Set<String>) -> [String] {
    var ordered = state.sections.map(\.id).filter(present.contains)
    let described = Set(ordered)
    ordered.append(contentsOf: present.subtracting(described).sorted())
    return ordered
}

/// A button label that turns into a spinner while its operation runs. Without it
/// a 20-second probe looks identical to a click that did nothing.
private struct BusyLabel: View {
    let text: String
    let busyText: String
    let busy: Bool

    var body: some View {
        if busy {
            HStack(spacing: 6) {
                ProgressView().controlSize(.small)
                Text(busyText)
            }
        } else {
            Text(text)
        }
    }
}

private struct ConfigPreviewView: View {
    let preview: JSONValue

    var body: some View {
        GroupBox("配置检查") {
            VStack(alignment: .leading, spacing: 6) {
                if preview.boolValue == false || preview["ok"]?.boolValue == false {
                    Label("这样还不够用，尚未保存。", systemImage: "xmark.circle.fill")
                        .foregroundStyle(.red)
                } else if preview["minimum_profile_ok"]?.boolValue == true {
                    Label("这样配就够用了。", systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Text("检查已完成；请根据还缺的能力决定是否保存。")
                        .foregroundStyle(.secondary)
                }
                ForEach(preview["missing"]?.arrayValue?.map(\.displayString) ?? [], id: \.self) { item in
                    Text(item).foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct CapabilityStatusRow: View {
    let capability: String
    let status: JSONValue

    private var configuredProviders: [String] {
        status["configured"]?.arrayValue?.map(\.displayString).filter { !$0.isEmpty } ?? []
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                Text(capabilityTitle).fontWeight(.medium)
                Text(configuredProviders.isEmpty ? "没有已配置的服务商" : "已配置：\(configuredProviders.joined(separator: "、"))")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Label(configurationLabel, systemImage: configurationSymbol)
                .foregroundStyle(configurationColor)
            if status["experimental"]?.boolValue == true {
                Text("实验性").font(.caption).foregroundStyle(.orange)
            }
        }
        .padding(.vertical, 3)
    }

    private var capabilityTitle: String {
        switch capability {
        case "main_search": return "主搜索"
        case "web_search": return "网页搜索"
        case "docs_search": return "文档检索"
        case "web_fetch": return "网页抓取"
        case "vertical_search": return "垂直检索"
        default: return capability
        }
    }

    private var configurationLabel: String {
        switch status["ok"]?.boolValue {
        case .some(true): return "配置条件已满足"
        case .some(false): return "缺少配置"
        case nil: return "状态未报告"
        }
    }

    private var configurationSymbol: String {
        switch status["ok"]?.boolValue {
        case .some(true): return "checkmark.circle"
        case .some(false): return "exclamationmark.circle"
        case nil: return "questionmark.circle"
        }
    }

    private var configurationColor: Color {
        switch status["ok"]?.boolValue {
        case .some(true): return .green
        case .some(false): return .orange
        case nil: return .secondary
        }
    }
}

private struct ProviderHealthView: View {
    let health: JSONValue?

    var body: some View {
        GroupBox("服务商冷却状态") {
            VStack(alignment: .leading, spacing: 9) {
                Text("冷却仅影响本机是否暂时跳过重试。无冷却不等于服务商刚刚联网成功。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let providers = health?["providers"]?.arrayValue {
                    if providers.isEmpty {
                        Text("后端没有需要显示的冷却记录。")
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(providers.indices, id: \.self) { index in
                            ProviderHealthRow(health: providers[index])
                        }
                    }
                } else {
                    Text("后端未报告冷却状态。")
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct ProviderHealthRow: View {
    let health: JSONValue

    private var state: String { health["state"]?.stringValue ?? "unknown" }
    private var remainingSeconds: Double { health["cooldown_remaining_seconds"]?.numberValue ?? 0 }

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(health["provider"]?.displayString ?? "未知服务商").fontWeight(.medium)
                Spacer()
                if state == "cooldown" {
                    Label("冷却中（剩余 \(cooldownText)）", systemImage: "pause.circle")
                        .foregroundStyle(.orange)
                } else {
                    Label("无冷却", systemImage: "minus.circle")
                        .foregroundStyle(.secondary)
                }
            }
            if health["configured"]?.boolValue == false {
                Text("当前配置未包含此服务商。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if state == "closed" {
                Text("无冷却只表示当前不会因本机冷却被跳过，不代表联网验证成功。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if let errorType = health["error_type"]?.stringValue, !errorType.isEmpty {
                Text("最近错误类型：\(errorType)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if let message = health["error"]?.stringValue, !message.isEmpty {
                Text(message).font(.caption).foregroundStyle(.secondary)
            }
        }
        .padding(.vertical, 3)
    }

    private var cooldownText: String {
        if remainingSeconds >= 60 { return "\(Int((remainingSeconds / 60).rounded(.up))) 分钟" }
        return "\(Int(remainingSeconds.rounded(.up))) 秒"
    }
}

private struct ProviderDraftChecksView: View {
    let checks: JSONValue?

    var body: some View {
        GroupBox("本 App 最近的测试") {
            VStack(alignment: .leading, spacing: 9) {
                Text("只显示本 App 主动发起的测试。测试的是当前表单里的值，包含还没保存的修改；不写入冷却记录。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                let entries = checks?.objectValue ?? [:]
                if entries.isEmpty {
                    Text("本 App 还没测试过。")
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(entries.keys.sorted(), id: \.self) { provider in
                        ProviderDraftCheckRow(provider: provider, check: entries[provider] ?? .object([:]))
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct ProviderDraftCheckRow: View {
    let provider: String
    let check: JSONValue

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(provider).fontWeight(.medium)
                Spacer()
                Text(statusLabel).foregroundStyle(statusColor)
            }
            Text("时间：\(checkedAtText) · 来源：\(source) · 范围：\(scope)")
                .font(.caption)
                .foregroundStyle(.secondary)
            if let probe = check["probe"]?.stringValue, !probe.isEmpty {
                Text("探针：\(probe)").font(.caption).foregroundStyle(.secondary)
            }
            if let message = check["message"]?.stringValue, !message.isEmpty {
                Text(message).font(.caption).foregroundStyle(statusColor)
            }
        }
        .padding(.vertical, 3)
    }

    private var status: String { check["status"]?.stringValue ?? "unknown" }
    private var source: String { check["source"]?.stringValue ?? "后端未提供" }
    private var scope: String { check["scope"]?.stringValue ?? "后端未提供" }

    private var statusLabel: String {
        switch status {
        case "ok": return "测试通过"
        case "cancelled": return "测试已取消"
        case "not_configured": return "未配置"
        case "timeout": return "测试超时"
        default: return "测试：\(status)"
        }
    }

    private var statusColor: Color {
        switch status {
        case "ok": return .green
        case "cancelled": return .secondary
        case "not_configured", "timeout": return .orange
        default: return .red
        }
    }

    private var checkedAtText: String {
        guard let seconds = check["checked_at"]?.numberValue else { return "后端未提供" }
        return Date(timeIntervalSince1970: seconds).formatted(date: .abbreviated, time: .standard)
    }
}

private struct ProviderSection: View {
    @ObservedObject var model: AppModel
    let state: DesktopState
    let section: String
    let title: String?
    let blurb: String
    let fields: [ConfigField]

    private var provider: String? {
        let providers = Set(fields.compactMap(\.provider))
        return providers.count == 1 ? providers.first : nil
    }

    /// Of the 68 keys, 55 are advanced and 9 are essential. Showing them at equal
    /// weight is what makes this page read as a wall; `tier` was already parsed
    /// and simply never consulted.
    private var upfront: [ConfigField] { fields.filter { $0.tier != "advanced" } }
    private var advanced: [ConfigField] { fields.filter { $0.tier == "advanced" } }

    private var testKey: String { "test:" + (provider ?? section) }

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 14) {
                if !blurb.isEmpty {
                    Text(blurb).font(.caption).foregroundStyle(.secondary)
                }
                let visible = upfront.isEmpty ? advanced : upfront
                ForEach(visible) { field in
                    ConfigFieldEditor(model: model, state: state, field: field)
                    if field.id != visible.last?.id { Divider() }
                }
                if !upfront.isEmpty, !advanced.isEmpty {
                    DisclosureGroup("更多设置（\(advanced.count)）") {
                        VStack(alignment: .leading, spacing: 14) {
                            ForEach(advanced) { field in
                                ConfigFieldEditor(model: model, state: state, field: field)
                                if field.id != advanced.last?.id { Divider() }
                            }
                        }
                        .padding(.top, 8)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        } label: {
            HStack {
                Text(title ?? section)
                Spacer()
                if let provider {
                    Button {
                        Task { await model.testProvider(provider) }
                    } label: {
                        if model.inFlight.contains(testKey) {
                            HStack(spacing: 6) {
                                ProgressView().controlSize(.small)
                                Text("测试中…")
                            }
                        } else {
                            Text("测试")
                        }
                    }
                    .disabled(model.connection != .ready || model.inFlight.contains(testKey))
                }
            }
        }
    }
}

private struct ConfigFieldEditor: View {
    @ObservedObject var model: AppModel
    let state: DesktopState
    let field: ConfigField

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .firstTextBaseline) {
                Text(field.label).fontWeight(.medium)
                if model.isEnvironmentReadOnly(field) {
                    Text("环境变量").foregroundStyle(.secondary)
                }
                Spacer()
                if let provider = field.provider, !model.isEnvironmentReadOnly(field) {
                    Button("测试") { Task { await model.testProvider(provider) } }
                        .buttonStyle(.borderless)
                }
                Text(model.draftStatus(for: field)).foregroundStyle(.secondary)
            }

            if model.isEnvironmentReadOnly(field) {
                Text(state.effectiveValue(for: field).isEmpty ? "后端未提供有效值" : state.effectiveValue(for: field))
                    .textSelection(.enabled)
            } else if field.isSecret {
                HStack {
                    SecureField("输入新值以替换；留空表示保持", text: model.draftBinding(for: field))
                    if model.clearSecretKeys.contains(field.key) {
                        Button("保留") { model.keepSecret(field) }
                    } else {
                        Button("清除 Key", role: .destructive) { model.clearSecret(field) }
                    }
                }
            } else if !field.choices.isEmpty {
                Picker(field.label, selection: model.draftBinding(for: field)) {
                    Text("保持当前值").tag("")
                    ForEach(field.choices, id: \.self) { choice in Text(choice).tag(choice) }
                }
                .labelsHidden()
            } else {
                TextField(field.label, text: model.draftBinding(for: field))
            }

            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text("保存值：\(state.savedValue(for: field).isEmpty ? "后端未提供" : state.savedValue(for: field))")
                    .foregroundStyle(.secondary)
                Text("有效值：\(state.effectiveValue(for: field).isEmpty ? "后端未提供" : state.effectiveValue(for: field))")
                    .foregroundStyle(.secondary)
                Text("来源：\(state.source(for: field))")
                    .foregroundStyle(.secondary)
                if let docs = field.docsURL, let url = URL(string: docs) { Link("文档", destination: url) }
                if let keyURL = field.keyURL, let url = URL(string: keyURL) { Link("申请 Key", destination: url) }
            }
            .font(.caption)
            if !field.help.isEmpty { Text(field.help).font(.caption).foregroundStyle(.secondary) }
        }
        .accessibilityElement(children: .contain)
    }
}

private struct SearchResearchView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        guard let state = model.state else { return AnyView(BackendUnavailableView(model: model)) }
        return AnyView(ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("搜索与研究").font(.largeTitle.weight(.bold))
                    Text("工具目录和参数来自后端。实验性工具保持明确标注，结果先以可读内容和来源展示。")
                        .foregroundStyle(.secondary)
                }

                if state.commands.isEmpty {
                    GroupBox("工具目录") {
                        Text("后端尚未提供可运行的工具目录。")
                            .foregroundStyle(.secondary)
                    }
                } else {
                    CommandFormView(model: model, commands: state.commands)
                }

                if let result = model.currentResult {
                    ReadableResultView(
                        result: result,
                        command: model.currentResultCommand,
                        copy: model.copyCurrentResult,
                        export: model.exportCurrentResult
                    )
                }
            }
            .padding(24)
            .frame(maxWidth: 980, alignment: .leading)
        })
    }
}

private struct CommandFormView: View {
    @ObservedObject var model: AppModel
    let commands: [CommandCatalogEntry]

    var body: some View {
        GroupBox("执行工具") {
            VStack(alignment: .leading, spacing: 14) {
                Picker("工具", selection: Binding(get: { model.selectedCommandID ?? "" }, set: { model.selectCommand($0) })) {
                    ForEach(commands) { command in
                        Text(command.experimental ? "\(command.label)（实验性）" : command.label).tag(command.id)
                    }
                }
                if let command = model.selectedCommand {
                    if !command.description.isEmpty { Text(command.description).foregroundStyle(.secondary) }
                    if command.experimental {
                        Label("实验性工具：只在明确选择后调用。", systemImage: "flask")
                            .foregroundStyle(.orange)
                    }
                    let primaryFields = command.fields.filter { !$0.isAdvanced }
                    let advancedFields = command.fields.filter(\.isAdvanced)
                    ForEach(primaryFields) { field in CommandFieldEditor(model: model, field: field) }
                    if !advancedFields.isEmpty {
                        DisclosureGroup("高级参数") {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(advancedFields) { field in CommandFieldEditor(model: model, field: field) }
                            }
                            .padding(.top, 8)
                        }
                    }
                    HStack {
                        Button("开始 \(command.label)") { Task { await model.startSelectedCommand() } }
                            .buttonStyle(.borderedProminent)
                            .disabled(model.connection != .ready)
                        Text("运行后可在活动页查看真实阶段并取消本 App 的任务。")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct CommandFieldEditor: View {
    @ObservedObject var model: AppModel
    let field: CommandField

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            if field.isBoolean {
                Toggle(field.label, isOn: model.booleanBinding(for: field))
            } else if !field.choices.isEmpty {
                Picker(field.label, selection: model.commandBinding(for: field)) {
                    if !field.required { Text("未指定").tag("") }
                    ForEach(field.choices, id: \.self) { choice in Text(choice).tag(choice) }
                }
            } else if field.acceptsMultipleValues {
                Text(field.label + (field.required ? "（必填）" : ""))
                TextEditor(text: model.commandBinding(for: field))
                    .font(.body)
                    .frame(minHeight: 58)
                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(.quaternary))
                Text("每行一个值。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                TextField(field.label + (field.required ? "（必填）" : ""), text: model.commandBinding(for: field))
            }
            if !field.help.isEmpty { Text(field.help).font(.caption).foregroundStyle(.secondary) }
        }
    }
}

private struct ReadableResultView: View {
    let result: JSONValue
    let command: String?
    let copy: () -> Void
    let export: () -> Void

    var body: some View {
        GroupBox(command.map { "结果：\($0)" } ?? "结果") {
            VStack(alignment: .leading, spacing: 12) {
                if let text = result.readableText, !text.isEmpty {
                    Text(text).textSelection(.enabled)
                } else {
                    Text("后端返回了结构化结果，但没有可直接阅读的文本字段。可在高级详情查看脱敏结构。")
                        .foregroundStyle(.secondary)
                }
                let sources = result.sourceLinks
                if !sources.isEmpty {
                    Divider()
                    Text("来源").font(.headline)
                    ForEach(sources, id: \.absoluteString) { url in
                        Link(url.absoluteString, destination: url)
                            .lineLimit(1)
                    }
                }
                HStack {
                    Button("复制脱敏 JSON", action: copy)
                    Button("导出脱敏结果", action: export)
                    Spacer()
                }
                DisclosureGroup("高级 JSON") {
                    Text(result.redacted().prettyPrinted())
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct ActivityView: View {
    @ObservedObject var model: AppModel
    @State private var confirmClear = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 6) {
                Text("活动").font(.largeTitle.weight(.bold))
                Text("显示本机当前配置目录和你主动添加目录中的真实活动。没有记录不代表外部 CLI 一定空闲。")
                    .foregroundStyle(.secondary)
            }
            HStack {
                Button("刷新") { Task { await model.refreshActivity() } }
                Button("添加配置目录", action: model.addObservedDirectory)
                Button("清除已结束历史", role: .destructive) { confirmClear = true }
                Spacer()
                Toggle("记录活动", isOn: Binding(
                    get: { model.activityEnabled },
                    set: { value in Task { await model.setActivityEnabled(value) } }
                ))
            }
            if !model.observedDirectories.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack {
                        ForEach(model.observedDirectories, id: \.self) { directory in
                            HStack(spacing: 5) {
                                Text(directory).lineLimit(1)
                                Button { model.removeObservedDirectory(directory) } label: { Image(systemName: "xmark.circle.fill") }
                                    .buttonStyle(.borderless)
                                    .accessibilityLabel("移除观察目录")
                            }
                            .padding(.horizontal, 8).padding(.vertical, 4)
                            .background(.quaternary, in: Capsule())
                        }
                    }
                }
            }
            if !model.activityErrors.isEmpty {
                GroupBox("观察状态") {
                    VStack(alignment: .leading, spacing: 5) {
                        ForEach(model.activityErrors, id: \.self) { error in
                            Label(error, systemImage: "exclamationmark.triangle.fill")
                                .foregroundStyle(.orange)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            GroupBox {
                if model.activityRuns.isEmpty {
                    VStack(spacing: 8) {
                        Image(systemName: "clock")
                            .font(.title2).foregroundStyle(.secondary)
                        Text("没有可显示的活动记录")
                        Text("这可能是没有接入观测的新任务、记录被关闭，或当前目录没有历史；它不表示全部服务商正常。")
                            .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity).padding(28)
                } else {
                    List(model.activityRuns) { run in
                        ActivityRow(model: model, run: run)
                    }
                    .frame(minHeight: 360)
                }
            }
        }
        .padding(24)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
        .task {
            while !Task.isCancelled {
                await model.refreshActivity()
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
        .alert("清除活动历史？", isPresented: $confirmClear) {
            Button("取消", role: .cancel) {}
            Button("清除已结束记录", role: .destructive) { Task { await model.clearActivityHistory() } }
        } message: {
            Text("仅清除已结束任务的活动元数据，不会删除配置、研究证据或你导出的文件。")
        }
        .sheet(item: Binding(get: { model.selectedActivity }, set: { if $0 == nil { model.selectedActivity = nil } })) { run in
            ActivityDetailView(model: model, run: run)
        }
    }
}

private struct ActivityRow: View {
    @ObservedObject var model: AppModel
    let run: ActivityRun

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(model.displayLabel(for: run)).fontWeight(.medium)
                    StatusTag(status: run.status)
                    Text(run.origin.uppercased()).font(.caption).foregroundStyle(.secondary)
                }
                Text([run.phase, run.provider, run.model].compactMap { $0 }.joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary)
                    .lineLimit(1)
                if let error = run.errorType { Text(error).font(.caption).foregroundStyle(.red) }
            }
            Spacer()
            Text(run.elapsedText).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
            Button("详情") { Task { await model.showActivityDetails(run) } }
            if model.canCancel(run) {
                Button("取消", role: .destructive) { Task { await model.cancel(run) } }
            }
        }
        .padding(.vertical, 4)
    }
}

private struct ActivityDetailView: View {
    @ObservedObject var model: AppModel
    let run: ActivityRun
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("活动详情").font(.title2.weight(.semibold))
                Spacer()
                Button("完成") { dismiss() }
            }
            Text(model.displayLabel(for: run)).font(.headline)
            KeyValueLine(label: "配置版本", value: run.configRevision ?? "活动记录未提供")
            if model.hasOwnedResult(for: run) {
                Button("查看结果") { model.showOwnedResult(run) }
            }
            if let result = model.activityResult(for: run) {
                ActivityResultView(result: result)
            }
            if let details = model.activityDetails {
                let events = details["events"]?.arrayValue ?? []
                if details["ok"]?.boolValue == false {
                    Text(details["error"]?.stringValue ?? "活动详情当前不可读取。")
                        .foregroundStyle(.red)
                } else if !events.isEmpty {
                    List(events.indices, id: \.self) { index in
                        ActivityEventRow(event: events[index])
                    }
                } else {
                    Text("后端没有返回额外的脱敏阶段元数据。")
                        .foregroundStyle(.secondary)
                }
                DisclosureGroup("高级详情") {
                    Text(details.redacted().prettyPrinted())
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                }
            } else {
                ProgressView("正在读取脱敏活动详情…")
            }
            Spacer()
        }
        .padding(20)
        .frame(minWidth: 560, minHeight: 360)
    }
}

private struct ActivityResultView: View {
    let result: JSONValue

    var body: some View {
        GroupBox("任务结果") {
            VStack(alignment: .leading, spacing: 8) {
                if let text = result.readableText, !text.isEmpty {
                    Text(text).textSelection(.enabled)
                } else {
                    Text("后端没有提供可直接阅读的结果文本。")
                        .foregroundStyle(.secondary)
                }
                DisclosureGroup("高级 JSON") {
                    Text(result.redacted().prettyPrinted())
                        .font(.system(.body, design: .monospaced))
                        .textSelection(.enabled)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }
}

private struct ActivityEventRow: View {
    let event: JSONValue

    var body: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(event["phase"]?.displayString ?? "未知阶段")
                Text([event["provider"]?.stringValue, event["model"]?.stringValue]
                    .compactMap { $0 }
                    .filter { !$0.isEmpty }
                    .joined(separator: " · "))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            StatusTag(status: event["status"]?.displayString ?? "unknown")
        }
        .padding(.vertical, 3)
    }
}

private struct StatusTag: View {
    let status: String

    var body: some View {
        Text(status)
            .font(.caption.weight(.medium))
            .foregroundStyle(color)
    }

    private var color: Color {
        switch status {
        case "finished", "up_to_date": return .green
        case "failed", "interrupted": return .red
        case "running", "cancelling": return .orange
        case "cancelled", "stale": return .secondary
        default: return .secondary
        }
    }
}

private struct IntegrationView: View {
    @ObservedObject var model: AppModel
    @State private var confirmEnableCLI = false

    var body: some View {
        guard let state = model.state else { return AnyView(BackendUnavailableView(model: model)) }
        return AnyView(ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("AI 接入").font(.largeTitle.weight(.bold))
                    Text("查看实际 CLI 路径和 Skills 状态。安装或更新只作用于你选中的目标。")
                        .foregroundStyle(.secondary)
                }

                GroupBox("CLI") {
                    VStack(alignment: .leading, spacing: 10) {
                        KeyValueLine(label: "内置路径", value: model.cliStatus?["bundled_path"]?.displayString ?? "尚未读取")
                        KeyValueLine(label: "外部路径", value: model.cliStatus?["external_path"]?.displayString ?? "未发现或尚未读取")
                        KeyValueLine(label: "内置版本", value: model.cliStatus?["version"]?.displayString ?? "尚未读取")
                        HStack {
                            Button("复制内置路径", action: model.copyBundledCLIPath)
                            Button("刷新 CLI 状态") { Task { await model.refreshCLIStatus() } }
                            Spacer()
                        }
                        Divider()
                        Text("默认只显示路径和版本。启用内置 CLI 是明确动作；若已有同名外部 CLI，后端会拒绝覆盖。")
                            .font(.caption).foregroundStyle(.secondary)
                        Button("启用内置 CLI…") { confirmEnableCLI = true }
                            .disabled(model.connection != .ready)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("Skills") {
                    VStack(alignment: .leading, spacing: 12) {
                        if state.skillTargets.isEmpty {
                            Text("后端尚未提供可管理的 Skills 目标。")
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(state.skillTargets) { target in
                                Toggle(isOn: Binding(
                                    get: { model.selectedSkillTargets.contains(target.id) },
                                    set: { selected in
                                        if selected { model.selectedSkillTargets.insert(target.id) }
                                        else { model.selectedSkillTargets.remove(target.id) }
                                    }
                                )) {
                                    HStack {
                                        Text(target.label)
                                        Spacer()
                                        StatusTag(status: model.skillStatuses[target.id] ?? target.status ?? "unknown")
                                    }
                                }
                            }
                            HStack {
                                Button("刷新状态") { Task { await model.refreshSkillStatus() } }
                                Button("安装或更新所选目标") { Task { await model.installSelectedSkills() } }
                                    .buttonStyle(.borderedProminent)
                                    .disabled(model.selectedSkillTargets.isEmpty || model.connection != .ready)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(24)
            .frame(maxWidth: 900, alignment: .leading)
        }
        .alert("启用内置 CLI？", isPresented: $confirmEnableCLI) {
            Button("取消", role: .cancel) {}
            Button("确认启用") { Task { await model.enableBundledCLI() } }
        } message: {
            Text("这会要求后端创建用户级 CLI 链接；它不会覆盖已存在的同名外部 CLI。")
        })
    }
}

private struct SettingsAboutView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("设置与关于").font(.largeTitle.weight(.bold))
                    Text("本页只调整 App 自身连接和观察范围；不会改写外部 npm 或 Python 安装。")
                        .foregroundStyle(.secondary)
                }

                GroupBox("当前配置目录") {
                    VStack(alignment: .leading, spacing: 10) {
                        Text(model.state?.configDirectory ?? "后端尚未提供")
                            .textSelection(.enabled)
                        Button("选择配置目录…", action: model.chooseConfigDirectory)
                            .disabled(model.connection != .ready)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("后端连接") {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            TextField("开发环境后端路径（可选）", text: $model.backendPathOverride)
                            Button("选择…", action: model.chooseBackendExecutable)
                            Button("使用内置后端") { model.saveBackendOverride("") }
                        }
                        Text("发布包默认使用 Contents/Resources/backend/smart-search。仅显式选择时才会使用开发路径。")
                            .font(.caption).foregroundStyle(.secondary)
                        HStack {
                            Stepper("请求超时：\(Int(model.requestTimeoutSeconds)) 秒", value: $model.requestTimeoutSeconds, in: 5...300, step: 5)
                            Button("应用超时", action: model.applyTimeout)
                            Button("重新连接") { model.saveBackendOverride(model.backendPathOverride); Task { await model.reconnect() } }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }

                GroupBox("版本与更新") {
                    VStack(alignment: .leading, spacing: 10) {
                        KeyValueLine(label: "App 协议", value: "v\(BackendClient.protocolVersion)")
                        KeyValueLine(label: "引擎版本", value: model.state?.version ?? "尚未读取")
                        Button("检查更新") { Task { await model.checkForUpdates() } }
                            .disabled(model.connection != .ready)
                        if let update = model.updateResult {
                            UpdateResultView(result: update)
                        }
                        Text("检查更新仅在此处由你主动触发；安装由你从官方发行产物完成。")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            .padding(24)
            .frame(maxWidth: 900, alignment: .leading)
        }
    }
}

private struct KeyValueLine: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label).foregroundStyle(.secondary).frame(minWidth: 90, alignment: .leading)
            Text(value).textSelection(.enabled)
            Spacer(minLength: 0)
        }
    }
}

private struct UpdateResultView: View {
    let result: JSONValue

    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            if let error = result.stringValue ?? result["error"]?.stringValue, !error.isEmpty {
                Text("更新检查未完成：\(error)").foregroundStyle(.red)
            } else {
                KeyValueLine(label: "当前版本", value: result["current_version"]?.displayString ?? "后端未提供")
                KeyValueLine(label: "最新版本", value: result["latest_version"]?.displayString ?? "后端未提供")
                if let urlString = result["url"]?.stringValue, let url = URL(string: urlString) {
                    Link("打开官方发行页面", destination: url)
                }
            }
        }
    }
}

private extension JSONValue {
    var readableText: String? {
        let preferredKeys = ["display_text", "answer", "content", "text", "summary", "message", "output", "error"]
        if let object = objectValue {
            for key in preferredKeys {
                if let text = object[key]?.stringValue, !text.isEmpty { return text }
            }
            for key in ["result", "data"] {
                if let text = object[key]?.readableText, !text.isEmpty { return text }
            }
        }
        return stringValue
    }

    var sourceLinks: [URL] {
        var links: Set<URL> = []
        collectSourceLinks(into: &links)
        return links.sorted { $0.absoluteString < $1.absoluteString }
    }

    private func collectSourceLinks(into links: inout Set<URL>) {
        switch self {
        case let .object(object):
            for key in ["url", "link", "source_url", "href"] {
                if let value = object[key]?.stringValue,
                   let url = URL(string: value),
                   let scheme = url.scheme?.lowercased(),
                   ["http", "https"].contains(scheme) {
                    links.insert(url)
                }
            }
            for value in object.values { value.collectSourceLinks(into: &links) }
        case let .array(values):
            for value in values { value.collectSourceLinks(into: &links) }
        default:
            break
        }
    }
}
