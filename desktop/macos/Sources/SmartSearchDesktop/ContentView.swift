import AppKit
import SwiftUI

// THESIS: Show the next useful task first; move configuration and diagnostics to their own destinations.
// OWN-WORLD: Native macOS chrome, white semantic content surfaces, system type and restrained separators.
// STORY: Configure providers, test a request, then install the independent CLI and Agent Skills.
// FIRST VIEWPORT: Sidebar navigation plus a focused detail area with one primary action and concise status.
// FORM: User-pinned Apple desktop conventions and Codex Tweaks reference; no random concept selection.
// FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
struct ContentView: View {
    @ObservedObject var model: AppModel
    @State private var configurationSelection: ConfigurationRoute?
    @State private var showingFeedback = false

    private var hasFeedback: Bool { model.errorMessage != nil || model.noticeMessage != nil }

    var body: some View {
        NavigationSplitView {
            List(selection: Binding<Destination?>(
                get: { model.selectedDestination },
                set: { if let destination = $0 { model.selectedDestination = destination } }
            )) {
                ForEach(Destination.allCases) { destination in
                    Label(destination.title, systemImage: destination.symbol)
                        .tag(destination)
                }
            }
            .listStyle(.sidebar)
            .id(model.languagePreference)
            .navigationTitle("Smart Search")
            .navigationSplitViewColumnWidth(220)
            .safeAreaInset(edge: .bottom, spacing: 0) {
                ZStack(alignment: .bottomLeading) {
                    if let mascot = AppBranding.mascot {
                        Image(nsImage: mascot)
                            .resizable().scaledToFit()
                            .frame(width: 168, height: 168)
                            .offset(y: 16)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .frame(height: 160, alignment: .bottom)
                            .clipped()
                            .allowsHitTesting(false)
                            .accessibilityHidden(true)
                    }
                    ConnectionIndicator(state: model.connection, compact: true)
                        .frame(maxWidth: .infinity, alignment: .trailing)
                }
            }
        } detail: {
            destinationView
            // Refresh translated controls without replacing the native navigation container.
            .id(model.languagePreference)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(DesktopAppearance.contentBackground)
            .navigationTitle(model.selectedDestination.title)
        }
        .disabled(model.appUpdatePreparing)
        .navigationSplitViewStyle(.balanced)
        .toolbar { workspaceToolbar }
        .toolbarBackground(.visible, for: .windowToolbar)
        .groupBoxStyle(DesktopGroupBoxStyle())
        .toggleStyle(.switch)
        .disclosureGroupStyle(WholeRowDisclosureStyle())
        .environment(\.locale, model.interfaceLocale)
        .onChange(of: model.selectedDestination) { destination in
            Task { await model.enter(destination) }
        }
        .onChange(of: model.errorMessage) { message in
            if message != nil { showingFeedback = true }
        }
        .onChange(of: model.errorPresentationID) { _ in
            if model.errorMessage != nil { showingFeedback = true }
        }
        .onReceive(model.$noticeMessage) { message in
            // A repeated action (such as copying the same path) still gets feedback.
            if message != nil { showingFeedback = true }
        }
        .onChange(of: hasFeedback) { available in
            if !available { showingFeedback = false }
        }
        .task {
            if hasFeedback { showingFeedback = true }
            await model.enter(model.selectedDestination)
        }
    }

    @ToolbarContentBuilder
    private var workspaceToolbar: some ToolbarContent {
        ToolbarItem(id: "workspace-feedback", placement: .primaryAction) {
            Button { showingFeedback.toggle() } label: {
                Label(L("操作提示"), systemImage: model.errorMessage == nil ? "info.circle" : "exclamationmark.circle")
            }
            .help(L("查看操作提示"))
            .disabled(!hasFeedback)
            .popover(isPresented: $showingFeedback, arrowEdge: .bottom) {
                OperationFeedback(error: model.errorMessage, notice: model.noticeMessage) {
                    showingFeedback = false
                    model.errorMessage = nil
                    model.noticeMessage = nil
                }
            }
        }
        if model.selectedDestination == .providers || model.connection != .ready {
            ToolbarItem(id: "workspace-refresh", placement: .primaryAction) {
                Button { Task {
                    if model.connection == .ready { await model.refreshState() }
                    else { await model.reconnect() }
                } } label: {
                    Label(model.connection == .ready ? L("重新读取配置") : L("重新连接"), systemImage: "arrow.clockwise")
                }
                .disabled(model.configOperationBusy || model.isBusy.contains("connect"))
            }
        }
    }

    @ViewBuilder
    private var destinationView: some View {
        switch model.selectedDestination {
        case .providers: ProvidersView(model: model, selection: $configurationSelection)
        case .search: SearchResearchView(model: model)
        case .integration: IntegrationView(model: model)
        case .settings: SettingsAboutView(model: model)
        }
    }
}

private struct OperationFeedback: View {
    let error: String?
    let notice: String?
    let clear: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text(L("操作提示")).font(.headline)
                Spacer()
                Button(L("清除提示"), action: clear)
            }
            Divider()
            ViewThatFits(in: .vertical) {
                messages.fixedSize(horizontal: false, vertical: true)
                ScrollView { messages }
            }
            .frame(maxHeight: 320)
        }
        .frame(width: 360, alignment: .leading)
        .padding(16)
    }

    private var messages: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let error {
                Label(L("操作未完成。"), systemImage: "exclamationmark.triangle")
                    .font(.headline).foregroundStyle(.red)
                Text(error).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if error != nil && notice != nil { Divider() }
            if let notice {
                Text(notice).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct ConnectionIndicator: View {
    let state: AppModel.ConnectionState
    var compact = false
    @State private var showingStatus = false

    private var statusDescription: String { L("后端状态：{0}", state.title) }

    var body: some View {
        if compact {
            Button { showingStatus = true } label: {
                Circle()
                    .fill(Color(nsColor: nativeTint))
                    .frame(width: 8, height: 8)
                    .frame(width: 24, height: 24)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(statusDescription)
            .onHover { showingStatus = $0 }
            .popover(isPresented: $showingStatus, arrowEdge: .bottom) {
                Text(statusDescription)
                    .font(.caption)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
            }
            .onDisappear { showingStatus = false }
        } else {
            Label {
                Text(state.title).foregroundStyle(.secondary)
            } icon: {
                Image(systemName: state.symbol).foregroundStyle(Color(nsColor: nativeTint))
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(statusDescription)
            .help(statusDescription)
        }
    }

    private var nativeTint: NSColor {
        switch state {
        case .ready: return DesktopAppearance.connectionReady
        case .connecting: return .systemOrange
        case .failed: return .systemRed
        case .disconnected: return .secondaryLabelColor
        }
    }
}

private struct BackendUnavailableView: View {
    @ObservedObject var model: AppModel

    var body: some View {
        VStack(spacing: 16) {
            if model.connection == .connecting {
                ProgressView().controlSize(.large)
            } else {
                Image(systemName: "bolt.horizontal.circle")
                    .font(.system(size: 42))
                    .foregroundStyle(.secondary)
            }
            Text(model.connection == .failed ? L("后端目前不可用") : L("正在连接本机后端"))
                .font(.title2.weight(.semibold))
            Text(L("连接后会读取当前配置、工具目录和活动记录。"))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            if model.connection != .connecting {
                Button(L("重新连接")) { Task { await model.reconnect() } }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isBusy.contains("connect"))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(40)
    }
}

private enum ConfigurationRoute: Hashable {
    case provider(String)
    case section(String)
    case researchSources
    case routing
}

private struct ProvidersView: View {
    @ObservedObject var model: AppModel
    @Binding var selection: ConfigurationRoute?
    @State private var filter = ""

    var body: some View {
        if let state = model.state {
            let providers = groups(state)
            VStack(spacing: 0) {
                DesktopSplitView("providers") {
                    VStack(spacing: 0) {
                        TextField(L("查找服务商"), text: $filter)
                            .textFieldStyle(.roundedBorder)
                            .padding([.horizontal, .top], DesktopMetrics.pagePadding)
                            .padding(.bottom, 12)
                        List(selection: $selection) {
                            if let field = state.fields.first(where: { $0.key == "SMART_SEARCH_INTENT_ROUTER" }) {
                                navigationRow(L("意图路由"), subtitle: configurationChoiceLabel(
                                    model.configDraft[field.key] ?? state.effectiveValue(for: field), for: field))
                                    .tag(ConfigurationRoute.section("routing"))
                                    .listRowSeparator(.hidden)
                            }
                            ForEach(providerCategories(providers), id: \.self) { capability in
                                Section(capabilityName(capability)) {
                                    ForEach(providers.filter { ($0.primaryCapability ?? "other") == capability }) { group in
                                        providerRow(group, state: state)
                                            .tag(ConfigurationRoute.provider(group.id))
                                            .listRowSeparator(.hidden)
                                    }
                                }
                            }
                            Section(L("高级配置")) {
                                if !researchSourceFields(state).isEmpty && matches(L("研究数据源")) {
                                    Text(L("研究数据源")).padding(.vertical, 5)
                                        .tag(ConfigurationRoute.researchSources)
                                }
                                ForEach(advancedSectionIDs(state), id: \.self) { id in
                                    Text(state.sections.first { $0.id == id }?.label ?? id)
                                        .padding(.vertical, 5)
                                        .tag(ConfigurationRoute.section(id))
                                }
                                if matches(L("冷却与路由详情")) {
                                    Text(L("冷却与路由详情")).padding(.vertical, 5)
                                        .tag(ConfigurationRoute.routing)
                                }
                            }
                        }
                        .listStyle(.inset)
                        .scrollContentBackground(.hidden)
                        .padding(.horizontal, DesktopMetrics.insetListPadding)
                        if providers.isEmpty && !filter.isEmpty {
                            Text(L("没有匹配的服务商")).font(.caption)
                                .foregroundStyle(.secondary).padding(DesktopMetrics.pagePadding)
                        }
                    }
                } detail: {
                    configurationDetail(state)
                }
                ConfigActions(model: model)
            }
            .onAppear { reconcileSelection(state) }
            .onChange(of: availableRoutes(state)) { _ in reconcileSelection(state) }
        } else {
            BackendUnavailableView(model: model)
        }
    }

    private func providerRow(_ group: ProviderFieldGroup, state: DesktopState) -> some View {
        let enabled = group.fields.first(where: \.isProviderToggle).map { configurationBooleanValue(state.effectiveValue(for: $0)) } ?? true
        let status = providerIsConfigured(group, state: state) ? L("已配置") : L("未配置")
        return navigationRow(group.id, subtitle: enabled ? status : L("已禁用"),
                      hasDraft: group.fields.contains { model.configDraft[$0.key] != nil || model.clearSecretKeys.contains($0.key) })
    }

    private func navigationRow(_ title: String, subtitle: String, hasDraft: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 6) {
                Text(title).fontWeight(.medium)
                if hasDraft {
                    Image(systemName: "pencil.circle")
                        .foregroundStyle(.orange).help(L("有未保存修改"))
                        .accessibilityLabel(L("有未保存修改"))
                }
            }
            Text(subtitle)
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(.vertical, 5)
    }

    @ViewBuilder
    private func configurationDetail(_ state: DesktopState) -> some View {
        switch selection {
        case .provider(let id):
            if let group = state.providerGroups.first(where: { $0.id == id }) {
                ConfigurationEditor(model: model, title: id, subtitle: providerPurpose(group),
                                    fields: group.fields, section: id)
                    .id(ConfigurationRoute.provider(id))
            }
        case .section(let id):
            if id == "routing" {
                IntentRoutingEditor(model: model, state: state)
            } else {
                ConfigurationEditor(model: model, title: state.sections.first { $0.id == id }?.label ?? id,
                                    fields: state.fields.filter { $0.provider?.isEmpty != false && $0.section == id }, section: id)
                    .id(ConfigurationRoute.section(id))
            }
        case .researchSources:
            ConfigurationEditor(model: model, title: L("研究数据源"),
                                fields: researchSourceFields(state), section: "routing")
                .id(ConfigurationRoute.researchSources)
        case .routing:
            DesktopPage(L("冷却与路由详情"), subtitle: L("查看路由顺序和最近请求状态。")) {
                ProviderHealthView(health: state.providerHealth)
                ForEach(state.capabilityChains.keys.sorted(), id: \.self) { key in
                    KeyValueLine(label: capabilityName(key), value: state.capabilityChains[key, default: []].joined(separator: " → "))
                }
            }
        case nil:
            Text(L("从左侧选择服务商或配置项目。"))
                .foregroundStyle(.secondary).padding(24)
        }
    }

    private func availableRoutes(_ state: DesktopState) -> [ConfigurationRoute] {
        state.providerGroups.map { .provider($0.id) } + sectionIDs(state).map { .section($0) }
            + (researchSourceFields(state).isEmpty ? [] : [.researchSources]) + [.routing]
    }

    private func reconcileSelection(_ state: DesktopState) {
        if let selection, availableRoutes(state).contains(selection) { return }
        // Filtering does not switch away from the field currently being edited.
        if state.fields.contains(where: { $0.key == "SMART_SEARCH_INTENT_ROUTER" }) {
            selection = .section("routing")
        } else {
            selection = groups(state).first.map { .provider($0.id) }
        }
    }

    private func sectionIDs(_ state: DesktopState) -> [String] {
        let sections = Set(state.fields.filter { $0.provider?.isEmpty != false }.map(\.section))
        return orderedSectionIDs(state: state, present: sections)
    }

    private func advancedSectionIDs(_ state: DesktopState) -> [String] {
        sectionIDs(state).filter { id in
            id != "routing" && (matches(id) || matches(state.sections.first { $0.id == id }?.label ?? id))
        }
    }

    private func researchSourceFields(_ state: DesktopState) -> [ConfigField] {
        state.fields.filter { $0.section == "routing" && $0.key.hasPrefix("SMART_SEARCH_RESEARCH_") }
    }

    private func groups(_ state: DesktopState) -> [ProviderFieldGroup] {
        state.providerGroups
            .filter { group in
                matches(group.id) || matches(providerPurpose(group)) || group.capabilities.contains { matches($0) }
            }
            .sorted {
                let left = providerIsConfigured($0, state: state)
                let right = providerIsConfigured($1, state: state)
                return left == right ? $0.id < $1.id : left
            }
    }

    private func providerCategories(_ groups: [ProviderFieldGroup]) -> [String] {
        let order = ["main_search", "docs_search", "web_search", "web_fetch", "vertical_search", "site_map", "synthesis"]
        let present = Set(groups.map { $0.primaryCapability ?? "other" })
        return order.filter(present.contains) + present.subtracting(order).sorted()
    }

    private func matches(_ text: String) -> Bool {
        filter.isEmpty || text.localizedCaseInsensitiveContains(filter)
    }
}

private struct IntentRoutingEditor: View {
    @ObservedObject var model: AppModel
    let state: DesktopState

    private var fields: [ConfigField] { state.fields.filter { $0.section == "routing" } }
    private var modeField: ConfigField? { fields.first { $0.key == "SMART_SEARCH_INTENT_ROUTER" } }
    private var mode: String { modeField.map(selectedValue) ?? "" }
    private let resultProcessingKeys: Set<String> = [
        "SMART_SEARCH_JEV_FILTER_RESULTS", "SMART_SEARCH_JEV_FILTER_THRESHOLD", "SMART_SEARCH_JEV_SYNTHESIZE",
    ]
    private var filteringEnabled: Bool {
        guard let field = fields.first(where: { $0.key == "SMART_SEARCH_JEV_FILTER_RESULTS" }) else { return false }
        return configurationBooleanValue(selectedValue(field))
    }

    var body: some View {
        DesktopPage(L("意图路由"), subtitle: L("先选择路由方式，再填写该模式使用的参数。")) {
            if let modeField {
                DesktopPanel {
                    ConfigFieldEditor(model: model, state: state, field: modeField)
                    Text(modeDescription).font(.callout).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            switch mode {
            case "hybrid":
                fieldPanel(L("向量模型"), fields: fields.filter { $0.key.hasPrefix("INTENT_EMBEDDING_") })
                fieldPanel(L("分类模型"), fields: fields.filter { $0.key.hasPrefix("INTENT_CLASSIFIER_") })
                fieldPanel(L("请求设置"), fields: fields.filter { $0.key == "INTENT_ROUTER_TIMEOUT_SECONDS" })
            case "jev":
                fieldPanel(L("JEV 连接"), fields: fields.filter { $0.key.hasPrefix("TYPESAFE_") })
                fieldPanel(L("检索与判断"), fields: fields.filter {
                    $0.key.hasPrefix("SMART_SEARCH_JEV_") && !resultProcessingKeys.contains($0.key)
                })
                fieldPanel(L("结果处理"), fields: fields.filter {
                    resultProcessingKeys.contains($0.key)
                        && ($0.key != "SMART_SEARCH_JEV_FILTER_THRESHOLD" || filteringEnabled)
                })
            default: EmptyView()
            }
        }
    }

    private var modeDescription: String {
        switch mode {
        case "hybrid": return L("以规则为基础，可按需配置向量模型和分类模型增强判断。未配置的模型不会被调用。")
        case "jev": return L("使用 JEV 选择检索渠道并判断证据是否充分，需要单独配置 TypeSafe 凭据。")
        case "rules": return L("仅使用本地规则判断意图，无需填写模型接口或密钥。")
        case "off": return L("关闭自动意图路由，无需填写路由参数。")
        default: return L("请选择一种路由模式。")
        }
    }

    private func selectedValue(_ field: ConfigField) -> String {
        (model.configDraft[field.key] ?? state.effectiveValue(for: field))
            .trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    @ViewBuilder
    private func fieldPanel(_ title: String, fields: [ConfigField]) -> some View {
        if !fields.isEmpty {
            DesktopPanel(title) {
                ForEach(fields) { field in
                    ConfigFieldEditor(model: model, state: state, field: field)
                    if field.id != fields.last?.id { Divider() }
                }
            }
        }
    }
}

private func configurationBooleanValue(_ value: String) -> Bool {
    ["true", "1", "yes", "on"].contains(value.lowercased())
}

private func configurationChoiceLabel(_ choice: String, for field: ConfigField) -> String {
    if field.key == "SMART_SEARCH_INTENT_ROUTER" {
        switch choice {
        case "hybrid": return L("混合路由")
        case "jev": return L("JEV 语义路由")
        case "rules": return L("规则路由")
        case "off": return L("关闭路由")
        default: return choice
        }
    }
    if field.key == "SMART_SEARCH_JEV_SYNTHESIZE" {
        switch choice {
        case "false": return L("直接返回证据")
        case "auto": return L("按需汇总")
        case "true": return L("始终汇总")
        default: return choice
        }
    }
    return choice
}

private struct ConfigActions: View {
    @ObservedObject var model: AppModel
    @State private var showingPreview = false
    private var count: Int { model.configDraft.count + model.clearSecretKeys.count }
    var body: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                Text(count == 0 ? L("所有修改已保存") : L("未保存修改：{0} 项", "\(count)"))
                    .font(.caption).foregroundStyle(.secondary)
                Spacer()
                Button(L("放弃修改")) { model.resetConfigDraft() }.disabled(count == 0 || model.configOperationBusy)
                Button {
                    Task {
                        await model.previewConfig()
                        showingPreview = model.configPreview != nil
                    }
                } label: {
                    BusyLabel(text: L("检查配置"), busyText: L("检查中…"), busy: model.isBusy.contains("preview"))
                }
                .disabled(model.connection != .ready || model.configOperationBusy)
                Button { Task { await model.saveConfig() } } label: {
                    BusyLabel(text: L("保存更改"), busyText: L("保存中…"), busy: model.isBusy.contains("save"))
                }
                .buttonStyle(.borderedProminent)
                .disabled(count == 0 || model.connection != .ready || model.configOperationBusy)
            }.padding(.horizontal, DesktopMetrics.pagePadding).padding(.vertical, 12)
        }.background(DesktopAppearance.contentBackground)
        .sheet(isPresented: $showingPreview) {
            DetailSheet(L("配置检查")) {
                if let preview = model.configPreview { ConfigPreviewView(preview: preview) }
                Text(L("检查使用当前草稿，不会保存或发起服务商请求。"))
                    .foregroundStyle(.secondary)
            }
        }
    }
}

private struct ConfigurationEditor: View {
    @ObservedObject var model: AppModel
    let title: String
    var subtitle: String = L("修改先保留为草稿；测试使用当前填写的值。")
    let fields: [ConfigField]
    let section: String

    var body: some View {
        if let state = model.state {
            DesktopPage(title, subtitle: subtitle) {
                ProviderSection(model: model, state: state, section: section, fields: fields)
            }
        }
    }
}

private func capabilityName(_ value: String) -> String {
    ["main_search": L("主搜索"), "docs_search": L("文档检索"), "web_fetch": L("网页抓取"),
     "web_search": L("网页搜索"), "vertical_search": L("垂直检索"), "site_map": L("站点地图"),
     "synthesis": L("结果汇总"), "other": L("其他能力")][value] ?? value
}

private func providerPurpose(_ group: ProviderFieldGroup) -> String {
    let capabilities = group.capabilities.map(capabilityName).joined(separator: L("、"))
    let strengths = group.strengths.map { L($0) }.joined(separator: L("、"))
    var sentences: [String] = []
    if !capabilities.isEmpty {
        let purpose = strengths.isEmpty
            ? L("用于{0}。", capabilities)
            : L("用于{0}，侧重{1}。", capabilities, strengths)
        sentences.append(purpose)
    } else if let help = group.fields.first(where: { !$0.help.isEmpty })?.help {
        sentences.append(help)
    }
    if group.isExperimental { sentences.append(L("实验性能力。")) }
    if group.isExplicitOnly {
        sentences.append(L("仅在明确指定时调用。"))
    } else if group.isRoutingDisabled {
        sentences.append(L("不参与自动路由。"))
    }
    return sentences.joined(separator: " ")
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
        GroupBox(L("配置检查")) {
            VStack(alignment: .leading, spacing: 6) {
                if preview.boolValue == false || preview["ok"]?.boolValue == false {
                    Label(L("这样还不够用，尚未保存。"), systemImage: "xmark.circle.fill")
                        .foregroundStyle(.red)
                } else if preview["minimum_profile_ok"]?.boolValue == true {
                    Label(L("这样配就够用了。"), systemImage: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                } else {
                    Text(L("检查已完成；请根据还缺的能力决定是否保存。"))
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
                Text(configuredProviders.isEmpty ? L("没有已配置的服务商") : L("已配置：{0}", "\(configuredProviders.joined(separator: "、"))"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            Label {
                Text(configurationLabel).font(.callout)
            } icon: {
                Image(systemName: configurationSymbol).foregroundStyle(configurationColor)
            }
            if status["experimental"]?.boolValue == true {
                Text(L("实验性")).font(.caption).foregroundStyle(.orange)
            }
        }
        .padding(.vertical, 3)
    }

    private var capabilityTitle: String {
        switch capability {
        case "main_search": return L("主搜索")
        case "web_search": return L("网页搜索")
        case "docs_search": return L("文档检索")
        case "web_fetch": return L("网页抓取")
        case "vertical_search": return L("垂直检索")
        default: return capability
        }
    }

    private var configurationLabel: String {
        switch status["ok"]?.boolValue {
        case .some(true): return L("配置条件已满足")
        case .some(false): return L("缺少配置")
        case nil: return L("状态未报告")
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
        GroupBox(L("服务商冷却状态")) {
            VStack(alignment: .leading, spacing: 9) {
                Text(L("冷却仅影响本机是否暂时跳过重试。无冷却不等于服务商刚刚联网成功。"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let providers = health?["providers"]?.arrayValue {
                    if providers.isEmpty {
                        Text(L("后端没有需要显示的冷却记录。"))
                            .foregroundStyle(.secondary)
                    } else {
                        ForEach(providers.indices, id: \.self) { index in
                            ProviderHealthRow(health: providers[index])
                        }
                    }
                } else {
                    Text(L("后端未报告冷却状态。"))
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
                Text(health["provider"]?.displayString ?? L("未知服务商")).fontWeight(.medium)
                Spacer()
                if state == "cooldown" {
                    Label(L("冷却中（剩余 {0}）", "\(cooldownText)"), systemImage: "pause.circle")
                        .foregroundStyle(.orange)
                } else {
                    Label(L("无冷却"), systemImage: "minus.circle")
                        .foregroundStyle(.secondary)
                }
            }
            if health["configured"]?.boolValue == false {
                Text(L("当前配置未包含此服务商。"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if state == "closed" {
                Text(L("无冷却只表示当前不会因本机冷却被跳过，不代表联网验证成功。"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            if let errorType = health["error_type"]?.stringValue, !errorType.isEmpty {
                Text(L("最近一次请求异常，可主动测试确认。"))
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
        if remainingSeconds >= 60 { return L("{0} 分钟", "\(Int((remainingSeconds / 60).rounded(.up)))") }
        return L("{0} 秒", "\(Int(remainingSeconds.rounded(.up)))")
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
            Text(L("时间：{0} · 来源：{1} · 范围：{2}", "\(checkedAtText)", "\(source)", "\(scope)"))
                .font(.caption)
                .foregroundStyle(.secondary)
            if let probe = check["probe"]?.stringValue, !probe.isEmpty {
                Text(L("方式：{0}", "\(["live": L("真实请求"), "main": L("主搜索请求"), "presence": L("仅检查已填写"), "shared": L("共用凭据")][probe] ?? L("本机检查"))")).font(.caption).foregroundStyle(.secondary)
            }
            if let message = check["message"]?.stringValue, !message.isEmpty {
                DisclosureGroup(L("技术详情")) { Text(message).font(.system(.caption, design: .monospaced)).textSelection(.enabled) }
            }
        }
        .padding(.vertical, 3)
    }

    private var status: String { check["status"]?.stringValue ?? "unknown" }
    private var source: String { check["source"]?.stringValue == "app" ? L("本次 App 会话") : L("本机测试") }
    private var scope: String { check["scope"]?.stringValue == "draft" ? L("未保存的修改") : L("当前有效配置") }

    private var statusLabel: String {
        switch status {
        case "ok": return L("测试通过")
        case "cancelled": return L("测试已取消")
        case "not_configured": return L("未配置")
        case "timeout": return L("测试超时")
        case "warning": return L("需要确认")
        case "configured": return L("已填写，未验证")
        default: return L("测试未通过")
        }
    }

    private var statusColor: Color {
        switch status {
        case "ok": return .green
        case "cancelled": return .secondary
        case "not_configured", "timeout", "warning", "configured": return .orange
        default: return .red
        }
    }

    private var checkedAtText: String {
        guard let seconds = check["checked_at"]?.numberValue else { return L("后端未提供") }
        return Date(timeIntervalSince1970: seconds).formatted(date: .abbreviated, time: .standard)
    }
}

private func providerIsConfigured(_ group: ProviderFieldGroup, state: DesktopState) -> Bool {
    group.fields.contains { $0.isSecret && state.hasSecretValue(for: $0) }
}

private struct ProviderSection: View {
    @ObservedObject var model: AppModel
    let state: DesktopState
    let section: String
    let fields: [ConfigField]

    private var provider: String? {
        let providers = Set(fields.compactMap(\.provider).filter { !$0.isEmpty })
        return providers.count == 1 ? providers.first : nil
    }

    private var testKey: String { "test:" + (provider ?? section) }
    private var enableField: ConfigField? { fields.first(where: \.isProviderToggle) }
    private var parameterFields: [ConfigField] { fields.filter { !$0.isProviderToggle } }
    private var connectionFields: [ConfigField] { parameterFields.filter { !$0.isAdvanced } }
    private var advancedFields: [ConfigField] { parameterFields.filter(\.isAdvanced) }

    private var providerEnabled: Bool {
        enableField.map { configurationBooleanValue(model.configDraft[$0.key] ?? state.effectiveValue(for: $0)) } ?? true
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let enableField {
                DesktopPanel {
                    HStack(spacing: 16) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(enableField.label).fontWeight(.semibold)
                            Text(enableField.help).font(.caption).foregroundStyle(.secondary)
                            if model.isEnvironmentReadOnly(enableField) {
                                Text(L("由环境变量提供，在此处只读。")).font(.caption).foregroundStyle(.secondary)
                            }
                        }
                        Spacer(minLength: 8)
                        Toggle(enableField.label, isOn: Binding(
                            get: { providerEnabled },
                            set: { model.setDraft($0 ? "true" : "false", for: enableField) }))
                            .labelsHidden()
                            .disabled(model.configOperationBusy || model.isEnvironmentReadOnly(enableField))
                    }
                }
            }
            if !connectionFields.isEmpty && !advancedFields.isEmpty {
                Text(L("连接设置")).font(.headline)
                fieldEditors(connectionFields)
                Text(L("高级参数")).font(.headline).padding(.top, 10)
                fieldEditors(advancedFields)
            } else {
                fieldEditors(parameterFields)
            }
            if let provider, let check = state.providerChecks?[provider] {
                ProviderDraftCheckRow(provider: provider, check: check)
            }
            HStack {
                if let provider {
                    Button {
                        Task { await model.testProvider(provider) }
                    } label: {
                        if model.isBusy.contains(testKey) {
                            HStack(spacing: 6) {
                                ProgressView().controlSize(.small)
                                Text(model.state?.raw["probe_kinds"]?[provider]?.stringValue == "presence" ? L("检查中…") : L("测试中…"))
                            }
                        } else {
                            Text(model.providerTestLabel(provider))
                        }
                    }
                    .disabled(!providerEnabled || model.connection != .ready || model.isBusy.contains(testKey))
                    if model.isBusy.contains(testKey) {
                        Button(L("取消测试")) { Task { await model.cancelProviderTest(provider) } }
                    }
                }
                Spacer()
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func fieldEditors(_ fields: [ConfigField]) -> some View {
        ForEach(fields) { field in
            ConfigFieldEditor(model: model, state: state, field: field)
            if field.id != fields.last?.id { Divider() }
        }
    }
}

private struct ConfigFieldEditor: View {
    @ObservedObject var model: AppModel
    let state: DesktopState
    let field: ConfigField
    @State private var showingInfo = false

    private var readOnlyValue: String {
        let value = state.effectiveValue(for: field)
        if field.isSecret { return state.hasSecretValue(for: field) ? "••••••••" : L("未配置") }
        if value.isEmpty { return L("后端未提供有效值") }
        return configurationChoiceLabel(value, for: field)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .firstTextBaseline) {
                Text(field.label).fontWeight(.medium)
                Spacer()
                Button { showingInfo = true } label: { Image(systemName: "info.circle") }
                    .buttonStyle(.borderless).help(L("字段说明"))
                    .popover(isPresented: $showingInfo) { fieldDetails.padding(20).frame(width: 360) }
            }
            Text(model.draftStatus(for: field)).font(.caption).foregroundStyle(.secondary)

            if model.isEnvironmentReadOnly(field) {
                Text(readOnlyValue)
                    .textSelection(.enabled)
            } else if field.isSecret {
                HStack {
                    SecureField(field.label, text: model.draftBinding(for: field), prompt: Text(L("输入 API Key")))
                        .accessibilityLabel(field.label)
                    if model.clearSecretKeys.contains(field.key) {
                        Button(L("保留")) { model.keepSecret(field) }
                    } else {
                        Button(L("清除 Key"), role: .destructive) { model.clearSecret(field) }
                    }
                }
            } else if !field.choices.isEmpty {
                Picker(field.label, selection: model.draftBinding(for: field)) {
                    if !field.choices.contains(state.effectiveValue(for: field)) {
                        Text(L("当前：{0}", state.effectiveValue(for: field).isEmpty ? L("未设置") : configurationChoiceLabel(state.effectiveValue(for: field), for: field)))
                            .tag(state.effectiveValue(for: field))
                    }
                    ForEach(field.choices, id: \.self) { choice in
                        Text(configurationChoiceLabel(choice, for: field)).tag(choice)
                    }
                }
                .labelsHidden()
            } else if field.kind == "bool" {
                Toggle(field.label, isOn: Binding(
                    get: { configurationBooleanValue(model.configDraft[field.key] ?? state.effectiveValue(for: field)) },
                    set: { model.setDraft($0 ? "true" : "false", for: field) }))
                    .labelsHidden()
            } else {
                TextField(field.label, text: model.draftBinding(for: field), prompt: Text(field.placeholder))
                    .accessibilityLabel(field.label)
            }

            if let keyURL = field.keyURL, let url = URL(string: keyURL) {
                Link(L("申请 Key"), destination: url).font(.caption)
            }
        }
        .disabled(model.isBusy.contains("save"))
        .accessibilityElement(children: .contain)
    }
    private var fieldDetails: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(field.label).font(.headline)
            if !field.help.isEmpty { Text(field.help).font(.callout) }
            Text(field.key).font(.system(.caption, design: .monospaced)).textSelection(.enabled)
            KeyValueLine(label: L("来源"), value: state.statusLabels[state.source(for: field)] ?? L("未知来源"))
            Text(L("有效值：{0}", state.effectiveValue(for: field).isEmpty ? L("未设置") : state.effectiveValue(for: field)))
                .font(.caption).textSelection(.enabled)
            if state.savedValue(for: field) != state.effectiveValue(for: field) {
                Text(L("配置文件：{0}", state.savedValue(for: field).isEmpty ? L("未设置") : state.savedValue(for: field)))
                    .font(.caption).textSelection(.enabled)
            }
            if let docs = field.docsURL, let url = URL(string: docs) { Link(L("文档"), destination: url) }
        }
    }

}

private struct SearchResearchView: View {
    @ObservedObject var model: AppModel
    @State private var showOptions = false

    var body: some View {
        if let state = model.state {
            DesktopSplitView("search", leadingWidths: 280...360, initialLeadingWidth: 320, detailMinimumWidth: 360) {
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) {
                        Text(L("输入")).font(.title2.weight(.semibold))
                        if state.commands.isEmpty {
                            Text(L("后端尚未提供可运行的工具目录。"))
                        } else {
                            VStack(alignment: .leading, spacing: 8) {
                                Picker(L("测试项目"), selection: Binding(get: { model.selectedCommandID ?? "" }, set: { model.selectCommand($0) })) {
                                    ForEach(state.commands) { command in
                                        Text(command.experimental ? L("{0}（实验性）", command.label) : command.label).tag(command.id)
                                    }
                                }
                                .labelsHidden().frame(maxWidth: .infinity, alignment: .leading)
                                if let command = model.selectedCommand {
                                    Text(command.description).font(.callout).foregroundStyle(.secondary)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                            if let command = model.selectedCommand {
                                if command.experimental {
                                    Label(L("实验性工具：只在明确选择后调用。"), systemImage: "flask")
                                        .font(.callout).foregroundStyle(.orange)
                                }
                                VStack(alignment: .leading, spacing: 16) {
                                    ForEach(command.fields.filter { !$0.isAdvanced }) { field in
                                        CommandFieldEditor(model: model, field: field)
                                    }
                                }
                                ViewThatFits(in: .horizontal) {
                                    HStack(spacing: 12) { requestActions(command) }
                                    VStack(alignment: .leading, spacing: 12) { requestActions(command) }
                                }
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(DesktopMetrics.pagePadding)
                }
            } detail: {
                if let result = model.currentResult {
                    ScrollView {
                        ReadableResultView(result: result, command: model.currentResultCommand,
                                           copy: model.copyCurrentResult, export: model.exportCurrentResult)
                            .padding(DesktopMetrics.pagePadding)
                    }
                } else {
                    VStack(spacing: 12) {
                        if model.isSearchRunning {
                            ProgressView().controlSize(.large)
                            Text(model.currentResultCommand ?? L("任务正在运行")).font(.headline)
                            Text(L("任务正在运行")).foregroundStyle(.secondary)
                            Button(L("取消测试")) { Task { await model.cancelCurrentTest() } }
                        } else {
                            Image(systemName: "doc.text.magnifyingglass").font(.system(size: 36)).foregroundStyle(.secondary)
                            Text(L("结果会显示在这里")).font(.headline)
                            Text(L("选择测试项目，运行一次请求以确认配置。")).foregroundStyle(.secondary)
                        }
                    }
                    .multilineTextAlignment(.center).padding(DesktopMetrics.pagePadding)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .sheet(isPresented: $showOptions) {
                DetailSheet(L("测试选项")) {
                    if let command = model.selectedCommand {
                        ForEach(command.fields.filter(\.isAdvanced)) { field in
                            CommandFieldEditor(model: model, field: field)
                        }
                    }
                }
            }
        } else { BackendUnavailableView(model: model) }
    }

    @ViewBuilder
    private func requestActions(_ command: CommandCatalogEntry) -> some View {
        Button { Task { await model.startSelectedCommand() } } label: {
            BusyLabel(text: L("开始 {0}", command.label), busyText: L("运行中…"), busy: model.isBusy.contains("run:\(command.id)"))
        }
        .buttonStyle(.borderedProminent)
        .keyboardShortcut(.return, modifiers: .command)
        .disabled(model.connection != .ready || model.isSearchRunning || model.isBusy.contains("run:\(command.id)"))
        if command.fields.contains(where: \.isAdvanced) {
            Button(L("测试选项…")) { showOptions = true }
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
                    if !field.required { Text(L("未指定")).tag("") }
                    ForEach(field.choices, id: \.self) { choice in Text(choice).tag(choice) }
                }
            } else if field.acceptsMultipleValues {
                Text(field.label + (field.required ? L("（必填）") : ""))
                TextEditor(text: model.commandBinding(for: field))
                    .font(.body)
                    .frame(minHeight: 58)
                    .overlay(RoundedRectangle(cornerRadius: 5).stroke(.quaternary))
                Text(L("每行一个值。"))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text(field.label + (field.required ? L("（必填）") : ""))
                TextField(field.label, text: model.commandBinding(for: field), axis: .vertical)
                    .labelsHidden()
                    .lineLimit(field.name == "query" ? 3...8 : 1...6)
                    .textFieldStyle(.roundedBorder)
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
        VStack(alignment: .leading, spacing: 16) {
            Text(command.map { L("结果：{0}", $0) } ?? L("结果")).font(.title2.weight(.semibold))
            ViewThatFits(in: .horizontal) {
                HStack { resultActions }.fixedSize(horizontal: true, vertical: false)
                VStack(alignment: .leading, spacing: 8) { resultActions }
            }
            Divider()
            if let text = result.readableText, !text.isEmpty {
                Text(text).textSelection(.enabled)
                    .lineSpacing(4)
                    .frame(maxWidth: .infinity, alignment: .leading)
            } else {
                Text(L("后端返回了结构化结果，但没有可直接阅读的文本字段。可在高级详情查看脱敏结构。"))
                    .foregroundStyle(.secondary)
            }
            let sources = result.sourceLinks
            if !sources.isEmpty {
                Divider()
                Text(L("来源")).font(.headline)
                ForEach(sources, id: \.absoluteString) { url in
                    Link(destination: url) {
                        VStack(alignment: .leading, spacing: 3) {
                            Text(url.host ?? url.absoluteString).font(.callout.weight(.medium))
                            Text(url.absoluteString).font(.caption).foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
            DisclosureGroup(L("高级 JSON")) {
                Text(result.redacted().prettyPrinted())
                    .font(.system(.body, design: .monospaced))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    @ViewBuilder
    private var resultActions: some View {
        Button(L("复制脱敏 JSON"), action: copy)
        Button(L("导出脱敏结果"), action: export)
    }
}

private struct CLIStatusView: View {
    @ObservedObject var model: AppModel
    private var environment: JSONValue { model.environmentState ?? .object([:]) }
    private var update: JSONValue { model.updateResult?["cli"] ?? .object([:]) }
    private var operation: JSONValue { model.updateResult?["cli_update"] ?? .object([:]) }
    private var busy: Bool { model.environmentBusy || model.isUpdatingCLI || model.isBusy.contains("cli.update-check") }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("CLI").font(.title2.weight(.semibold))
            if model.environmentBusy {
                Text(environment["message"]?.stringValue ?? L("正在准备 CLI…"))
                if let total = environment["total"]?.numberValue, total > 0 {
                    ProgressView(value: environment["received"]?.numberValue ?? 0, total: total)
                }
            } else if model.isUpdatingCLI { Text(L("正在更新 CLI…")) }
            else if model.cliReady {
                Text(L("已安装 {0}", model.cliStatus?["external_version"]?.stringValue ?? ""))
                if update["available"]?.boolValue == true {
                    Text(L("可更新到 {0}", update["latest_version"]?.stringValue ?? ""))
                } else if (update["checked_at"]?.numberValue ?? 0) > 0, update["cached"]?.boolValue != true,
                          (update["error"]?.stringValue ?? "").isEmpty { Text(L("已是最新版本")) }
            } else { Text(L("CLI 未就绪，安装时会自动准备所需组件。")) }
            if model.cliStatus?["can_update"]?.boolValue == false,
               let note = model.cliStatus?["update_note"]?.stringValue, !note.isEmpty {
                Text(note).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
            }
            if environment["status"]?.stringValue == "ready", let message = environment["message"]?.stringValue, !message.isEmpty {
                Text(message).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
            }
            if let error = [environment, operation, update].compactMap({ $0["error"]?.stringValue }).first(where: { !$0.isEmpty }) {
                Text(error).foregroundStyle(.red).textSelection(.enabled)
            }
            HStack {
                Button { Task { await model.manageCLI() } } label: {
                    BusyLabel(text: model.cliActionLabel, busyText: L("处理中…"), busy: busy)
                }.buttonStyle(.borderedProminent)
                    .disabled(model.connection != .ready || busy || model.skillsBusy)
                if environment["can_cancel"]?.boolValue == true {
                    Button(L("取消")) { Task { await model.environmentAction("environment.cancel") } }
                }
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct IntegrationView: View {
    @ObservedObject var model: AppModel
    private var skills: JSONValue { model.skillsState ?? .object([:]) }
    private var installed: [JSONValue] { skills["result"]?["installed"]?.arrayValue ?? [] }
    private var failed: [JSONValue] { skills["result"]?["failed"]?.arrayValue ?? [] }

    var body: some View {
        if model.state != nil {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    CLIStatusView(model: model)
                    Divider()
                    Text("Skills").font(.title2.weight(.semibold))
                    Text(L("勾选要安装或更新的 Agent。取消勾选不会卸载文件。"))
                        .foregroundStyle(.secondary)
                    VStack(spacing: 8) {
                        ForEach(skills["targets"]?.arrayValue ?? [], id: \.self) { target in
                            let id = target["target"]?.stringValue ?? ""
                            HStack(spacing: 16) {
                                Toggle(target["label"]?.stringValue ?? id, isOn: Binding(
                                    get: { model.selectedSkillTargets.contains(id) },
                                    set: { if $0 { model.selectedSkillTargets.insert(id) } else { model.selectedSkillTargets.remove(id) } }))
                                    .toggleStyle(.checkbox).disabled(model.skillsBusy)
                                Spacer()
                                Text(skillStatus(target)).font(.callout).foregroundStyle(.secondary)
                            }.frame(minHeight: 40)
                            if let error = target["error"]?.stringValue, !error.isEmpty {
                                Text(error).font(.caption).foregroundStyle(.red).textSelection(.enabled)
                            }
                        }
                    }
                    Text(model.skillsChecking ? L("正在检查最新 Skills…") : L("点击安装/更新后自动检查最新内容；已有修改会先备份。"))
                        .font(.callout).foregroundStyle(.secondary)
                    if let error = skills["error"]?.stringValue, !error.isEmpty {
                        Text(error).foregroundStyle(.red).textSelection(.enabled)
                    }
                    if model.skillsBusy && !model.skillsChecking { Text(L("正在安装/更新 Skills…")) }
                    else if !installed.isEmpty || !failed.isEmpty {
                        let changed = installed.filter { ($0["changed_files"]?.integerValue ?? 0) > 0 }.count
                        Text(changed == 0 && failed.isEmpty ? L("所选 Skills 已是最新。") : L("已更新 {0} 个，失败 {1} 个。", "\(changed)", "\(failed.count)"))
                    }
                    ForEach(failed, id: \.self) { failure in
                        Text((failure["target"]?.stringValue ?? "") + ": " + (failure["error"]?.stringValue ?? ""))
                            .foregroundStyle(.red).textSelection(.enabled)
                    }
                    ForEach(installed, id: \.self) { receipt in
                        if let backup = receipt["backup"]?.stringValue, !backup.isEmpty {
                            Text(L("备份：{0}", backup)).font(.caption).textSelection(.enabled)
                        }
                    }
                }.frame(maxWidth: .infinity, alignment: .leading).padding(DesktopMetrics.pagePadding)
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                VStack(spacing: 0) {
                    Divider()
                    HStack {
                        Text(model.selectedSkillTargets.isEmpty ? L("请选择要安装或更新的 Agent") : L("已选择 {0} 个 Agent", "\(model.selectedSkillTargets.count)"))
                            .font(.callout).foregroundStyle(.secondary)
                        Spacer()
                        Button { Task { await model.installSelectedSkills() } } label: {
                            BusyLabel(text: L("安装/更新所选 Skills"), busyText: L("处理中…"), busy: model.skillsBusy)
                        }.buttonStyle(.borderedProminent).disabled(!model.canUpdateSelectedSkills)
                    }.padding(.horizontal, DesktopMetrics.pagePadding).padding(.vertical, 12)
                }.background(DesktopAppearance.contentBackground)
            }
        } else { BackendUnavailableView(model: model) }
    }

    private func skillStatus(_ value: JSONValue) -> String {
        if value["needs_update"]?.boolValue == true, value["status"]?.stringValue != "missing" { return L("可更新") }
        switch value["status"]?.stringValue {
        case "missing": return L("未安装")
        case "up_to_date", "extra_files": return L("与来源一致")
        case "error": return L("读取失败")
        default: return L("状态未知")
        }
    }
}

private struct SettingsAboutView: View {
    @ObservedObject var model: AppModel
    @AppStorage(AppearancePreference.defaultsKey) private var appearance = AppearancePreference.system

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                applicationInfo
                settingsSection(L("通用"), subtitle: L("管理语言、外观和配置目录。")) {
                    generalSettings
                }
                settingsSection(L("App 更新"), subtitle: L("检查并安装 App 的新版本。")) {
                    AppUpdateView(model: model, updater: model.appUpdater)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(DesktopMetrics.pagePadding)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(DesktopAppearance.contentBackground)
        .textFieldStyle(.roundedBorder)
    }

    private func settingsSection<Content: View>(_ title: String, subtitle: String,
                                                @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(.title2.weight(.semibold))
                Text(subtitle).foregroundStyle(.secondary)
            }
            content()
        }
    }

    private var applicationInfo: some View {
        DesktopPanel(compact: true) {
            HStack(spacing: 12) {
                Image(nsImage: AppBranding.icon).resizable().frame(width: 48, height: 48)
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 4) {
                    Text("Smart Search").font(.title2.weight(.semibold))
                    Text(L("版本 {0}", Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? L("尚未读取")))
                        .foregroundStyle(.secondary)
                    Text("konbakuyomu/smartsearch").font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 12)
                Link(destination: URL(string: "https://github.com/konbakuyomu/smartsearch")!) {
                    Label("GitHub", systemImage: "arrow.up.right")
                }
                .buttonStyle(.bordered)
                .help(L("项目主页"))
            }
        }
    }

    private var generalSettings: some View {
        DesktopPanel(compact: true) {
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L("界面语言")).fontWeight(.medium)
                    Text(L("App 与独立 CLI 分别保存语言选择。环境写入期间请等待操作完成。"))
                        .font(.callout).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Picker(L("界面语言"), selection: Binding(
                    get: { model.languagePreference },
                    set: { value in Task { await model.setLanguage(value) } })) {
                        Text(L("跟随系统")).tag("auto")
                        Text(L("简体中文")).tag("zh")
                        Text("English").tag("en")
                }
                .labelsHidden().frame(width: 168, alignment: .trailing)
                .disabled(model.skillsBusy || model.environmentBusy || model.isUpdatingCLI || model.isBusy.contains("language"))
            }
            Divider()
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L("外观")).fontWeight(.medium)
                    Text(L("跟随系统外观，或单独选择浅色、深色模式。"))
                        .font(.callout).foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Picker(L("外观"), selection: $appearance) {
                    ForEach(AppearancePreference.allCases) { preference in
                        Text(preference.title).tag(preference)
                    }
                }
                .labelsHidden().frame(width: 168, alignment: .trailing)
            }
            Divider()
            HStack(alignment: .top, spacing: 16) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L("当前配置目录")).fontWeight(.medium)
                    Text(model.state?.configDirectory ?? L("后端尚未提供"))
                        .font(.system(.callout, design: .monospaced))
                        .foregroundStyle(.secondary).textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 8) {
                    Button(model.isBusy.contains("profile") ? L("切换中…") : L("选择配置目录…"), action: model.chooseConfigDirectory)
                    if model.state?.isDefaultConfigDirectory == false {
                        Button(L("恢复默认配置目录")) { Task { await model.restoreDefaultConfigDirectory() } }
                    }
                }
                .fixedSize()
                .frame(minWidth: 168, alignment: .trailing)
                .disabled(model.connection != .ready || model.configOperationBusy || model.environmentBusy || model.skillsBusy)
            }
        }
    }

}

private struct KeyValueLine: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label).foregroundStyle(.secondary).frame(width: 130, alignment: .leading)
            Text(value).textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
    }
}

private struct AppUpdateView: View {
    @ObservedObject var model: AppModel
    @ObservedObject var updater: AppUpdater

    var body: some View {
        DesktopPanel(compact: true) {
            Toggle(L("每天自动检查更新"), isOn: Binding(
                get: { model.updateResult?["auto_check"]?.boolValue ?? true },
                set: { enabled in Task { await model.updateAction("updates.auto", params: .object(["enabled": .bool(enabled)])) } }))
                .disabled(model.connection != .ready)
            if !updater.statusMessage.isEmpty { Text(updater.statusMessage).textSelection(.enabled) }
            if updater.started {
                Button(action: updater.check) {
                    BusyLabel(text: updater.waitingToRestart || !updater.latestVersion.isEmpty ? L("更新 App") : L("检查更新"),
                              busyText: L("检查中…"), busy: updater.checking)
                }.buttonStyle(.borderedProminent)
                    .disabled(updater.checking || model.connection != .ready || (updater.waitingToRestart && !model.canInstallAppUpdate))
            } else {
                Link(L("下载正式版"), destination: URL(string: "https://github.com/konbakuyomu/smartsearch/releases/latest")!)
                    .buttonStyle(.bordered)
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
