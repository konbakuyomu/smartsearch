import AppKit
import SwiftUI

// THESIS: Show the next useful task first; move configuration and diagnostics to their own destinations.
// OWN-WORLD: Native macOS chrome, white semantic content surfaces, system type and restrained separators.
// STORY: Configure a provider, run a tool, read its result, and inspect real activity without losing context.
// FIRST VIEWPORT: Sidebar navigation plus a focused detail area with one primary action and concise status.
// FORM: User-pinned Apple desktop conventions and Codex Tweaks reference; no random concept selection.
// FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
struct ContentView: View {
    @ObservedObject var model: AppModel
    @State private var configurationSelection: ConfigurationRoute?
    @State private var configurationSearch = ""
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
        ToolbarItem(id: "workspace-refresh", placement: .primaryAction) {
            Button {
                Task { await model.refreshState() }
            } label: {
                ZStack {
                    Image(systemName: "arrow.clockwise")
                        .opacity(model.isBusy.contains("state") ? 0 : 1)
                    if model.isBusy.contains("state") {
                        ProgressView().controlSize(.small)
                    }
                }
                .frame(width: 16, height: 16)
                .accessibilityLabel(L("刷新状态"))
            }
            .help(L("刷新状态"))
            .disabled(model.connection != .ready || model.configOperationBusy)
        }
    }

    private func configureProviders(for capability: String?) {
        configurationSearch = capability.map(capabilityName) ?? ""
        if let capability, let state = model.state {
            let candidates = state.providerGroups.filter { $0.capabilities.contains(capability) }.map(\.id)
            let preferred = state.capabilityChains[capability, default: []].first { candidates.contains($0) }
            configurationSelection = (preferred ?? candidates.sorted().first).map(ConfigurationRoute.provider)
        }
        model.selectedDestination = .providers
    }

    @ViewBuilder
    private var destinationView: some View {
        switch model.selectedDestination {
        case .overview: OverviewView(model: model, configureProviders: configureProviders)
        case .providers: ProvidersView(model: model, selection: $configurationSelection, filter: $configurationSearch)
        case .search: SearchResearchView(model: model)
        case .activity: ActivityView(model: model)
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
            if model.connection == .connecting { ProgressView().controlSize(.large) }
            DesktopPanel {
                Text(L("先准备本地环境")).font(.headline)
                Text(model.environmentStatus)
                Text(model.environmentExplanation).font(.callout).foregroundStyle(.secondary)
                Button(L("准备环境")) { model.selectedDestination = .overview }.buttonStyle(.borderedProminent)
            }
        }
        .padding(DesktopMetrics.pagePadding)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
    }
}

private struct OverviewView: View {
    @ObservedObject var model: AppModel
    let configureProviders: (String?) -> Void
    @State private var showingDetails = false
    @State private var showingMoreCapabilities = false

    var body: some View {
        DesktopPage(L("概览"), subtitle: L("配置、运行与结果，都在这台电脑上管理。")) {
            VStack(alignment: .leading, spacing: 16) {
                CLIManagementView(model: model, firstStep: true)
                DesktopPanel {
                    DesktopStepHeader(title: L("2. 配置服务商"), subtitle: providerSummary) {
                        Button(L("配置服务商")) { configureProviders(nil) }
                            .disabled(model.state == nil)
                        if model.state?.minimumProfileOK == true {
                            Button(L("开始搜索")) { model.selectedDestination = .search }
                                .buttonStyle(.borderedProminent)
                        }
                    }
                    if let details = model.state?.capabilityStatus?.objectValue, !details.isEmpty {
                        let primary = ["main_search", "docs_search", "web_fetch"].filter { details[$0] != nil }
                        let additional = details.keys.filter { !primary.contains($0) }.sorted()
                        Divider()
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(primary, id: \.self) { key in
                                CapabilityStatusRow(capability: key, status: details[key] ?? .object([:])) {
                                    configureProviders(key)
                                }
                                if key != primary.last { Divider() }
                            }
                        }
                        HStack(spacing: 16) {
                            if !additional.isEmpty {
                                Button {
                                    showingMoreCapabilities.toggle()
                                } label: {
                                    HStack(spacing: 6) {
                                        Text(L("更多能力"))
                                        Image(systemName: showingMoreCapabilities ? "chevron.up" : "chevron.down")
                                            .font(.caption)
                                    }
                                }
                                .buttonStyle(.plain)
                                .accessibilityValue(showingMoreCapabilities ? L("已展开") : L("已收起"))
                            }
                            Spacer(minLength: 0)
                            Button(L("配置详情…")) { showingDetails = true }
                                .fixedSize()
                        }
                        if showingMoreCapabilities {
                            ForEach(additional, id: \.self) { key in
                                Divider()
                                CapabilityStatusRow(capability: key, status: details[key] ?? .object([:])) {
                                    configureProviders(key)
                                }
                            }
                        }
                    }
                }
                DesktopPanel {
                    DesktopStepHeader(title: L("3. 测试连接"), subtitle: L("在服务商页面点击“测试”，确认地址和密钥可用后开始搜索。")) {
                        Button(L("去测试服务商")) { configureProviders(nil) }.disabled(model.state == nil)
                    }
                }
                DesktopPanel {
                    DesktopStepHeader(title: L("4. 接入 Skills（可选）"), subtitle: L("添加 Skills，让 Agent 使用搜索。")) {
                        Button(L("管理 Skills")) { model.selectedDestination = .integration }
                            .disabled(model.state == nil)
                    }
                }
            }
        }
        .sheet(isPresented: $showingDetails) {
            if let state = model.state {
                DetailSheet(L("配置与路由详情")) {
                    KeyValueLine(label: L("配置文件"), value: state.configPath ?? L("后端未提供"))
                    KeyValueLine(label: L("配置目录"), value: state.configDirectory ?? L("后端未提供"))
                    KeyValueLine(label: L("CLI 版本"), value: state.version ?? L("后端未提供"))
                    KeyValueLine(label: L("协议 generation"), value: state.generation ?? L("后端未提供"))
                    KeyValueLine(label: L("最后读取"), value: model.lastStateRefresh?.formatted(date: .abbreviated, time: .standard) ?? L("尚未读取"))
                    ForEach(state.capabilityChains.keys.sorted(), id: \.self) { key in
                        KeyValueLine(label: capabilityName(key), value: state.capabilityChains[key, default: []].joined(separator: " → "))
                    }
                    Button(L("选择配置目录")) {
                        showingDetails = false
                        model.selectedDestination = .settings
                    }
                }
            }
        }
    }

    private var providerSummary: String {
        guard let state = model.state else { return L("选择搜索服务，填写 API Key。") }
        if state.minimumProfileOK == true { return L("基础配置已完成，可以开始搜索。") }
        if state.minimumMissing.isEmpty { return L("选择搜索服务，填写 API Key。") }
        return L("待配置：{0}", state.minimumMissing.map(capabilityName).joined(separator: "、"))
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
    @Binding var filter: String

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
                            if matches(L("意图路由")), let field = state.fields.first(where: { $0.key == "SMART_SEARCH_INTENT_ROUTER" }) {
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
                            if hasAdvancedEntries(state) {
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
                                    secondarySubtitle: group.purposeGuidance.joined(separator: " "),
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

    private func hasAdvancedEntries(_ state: DesktopState) -> Bool {
        (!researchSourceFields(state).isEmpty && matches(L("研究数据源")))
            || !advancedSectionIDs(state).isEmpty || matches(L("冷却与路由详情"))
    }

    private func groups(_ state: DesktopState) -> [ProviderFieldGroup] {
        state.providerGroups
            .filter { group in
                matches(group.id) || matches(providerPurpose(group)) ||
                    matches(group.purposeGuidance.joined(separator: " ")) || group.capabilities.contains { matches($0) }
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
        let query = filter.trimmingCharacters(in: .whitespacesAndNewlines)
        return query.isEmpty || text.localizedCaseInsensitiveContains(query)
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
    var secondarySubtitle: String = ""
    let fields: [ConfigField]
    let section: String

    var body: some View {
        if let state = model.state {
            DesktopPage(title, subtitle: subtitle, secondarySubtitle: secondarySubtitle) {
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
    var sentences = group.purposeDescriptions
    if sentences.isEmpty {
        let capabilities = group.capabilities.map(capabilityName).joined(separator: L("、"))
        if !capabilities.isEmpty {
            sentences.append(L("用于{0}。", capabilities))
        } else if let help = group.fields.first(where: { !$0.help.isEmpty })?.help {
            sentences.append(help)
        }
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
struct BusyLabel: View {
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
    let configure: () -> Void

    private var configuredProviders: [String] {
        status["configured"]?.arrayValue?.map(\.displayString).filter { !$0.isEmpty } ?? []
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(capabilityName(capability)).fontWeight(.medium)
                    if status["experimental"]?.boolValue == true {
                        Text(L("实验性")).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Text(configuredProviders.isEmpty ? L("没有已配置的服务商") : configuredProviders.joined(separator: " · "))
                    .font(.caption).foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 8)
            if status["ok"]?.boolValue == false {
                Button(action: configure) {
                    HStack(spacing: 4) {
                        Text(configurationLabel)
                        Image(systemName: "chevron.right").font(.caption)
                    }
                }
                .buttonStyle(.plain).foregroundStyle(Color.accentColor).fixedSize()
                .accessibilityLabel(L("配置{0}", capabilityName(capability)))
                .accessibilityValue(configurationLabel)
            } else {
                Text(configurationLabel).font(.callout).foregroundStyle(.secondary).fixedSize()
            }
        }
    }

    private var configurationLabel: String {
        switch status["ok"]?.boolValue {
        case .some(true): return L("已配置")
        case .some(false): return configuredProviders.isEmpty ? L("未配置") : L("需要调整")
        case nil: return L("状态未报告")
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
                Button { showingInfo = true } label: { Image(systemName: "questionmark.circle") }
                    .buttonStyle(.borderless).help(field.help)
                    .accessibilityLabel(L("字段说明：{0}", field.label)).accessibilityHint(field.help)
                    .popover(isPresented: $showingInfo) { fieldDetails.padding(20).frame(width: 360) }
            }
            Text(model.draftStatus(for: field)).font(.caption).foregroundStyle(.secondary)

            if model.isEnvironmentReadOnly(field) {
                Text(readOnlyValue)
                    .textSelection(.enabled)
            } else if field.isSecret {
                HStack {
                    SecureField(field.label, text: model.draftBinding(for: field), prompt: Text(field.inputPlaceholder))
                        .accessibilityLabel(field.label)
                        .help(field.inputPlaceholder)
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
                TextField(field.label, text: model.draftBinding(for: field), prompt: Text(field.inputPlaceholder))
                    .accessibilityLabel(field.label)
                    .help(field.inputPlaceholder)
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
            if !field.isSecret {
                Text(L("有效值：{0}", state.effectiveValue(for: field).isEmpty ? L("未设置") : state.effectiveValue(for: field)))
                    .font(.caption).textSelection(.enabled)
                if state.savedValue(for: field) != state.effectiveValue(for: field) {
                    Text(L("配置文件：{0}", state.savedValue(for: field).isEmpty ? L("未设置") : state.savedValue(for: field)))
                        .font(.caption).textSelection(.enabled)
                }
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
                                Picker(L("工具"), selection: Binding(get: { model.selectedCommandID ?? "" }, set: { model.selectCommand($0) })) {
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
                            Button(L("查看活动")) { model.selectedDestination = .activity }
                        } else {
                            Image(systemName: "doc.text.magnifyingglass").font(.system(size: 36)).foregroundStyle(.secondary)
                            Text(L("结果会显示在这里")).font(.headline)
                            Text(L("先选择工具并运行一次请求。")).foregroundStyle(.secondary)
                        }
                    }
                    .multilineTextAlignment(.center).padding(DesktopMetrics.pagePadding)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .sheet(isPresented: $showOptions) {
                DetailSheet(L("搜索选项")) {
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
        .disabled(model.connection != .ready || model.isBusy.contains("run:\(command.id)"))
        if command.fields.contains(where: \.isAdvanced) {
            Button(L("搜索选项…")) { showOptions = true }
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

private struct ActivityView: View {
    @ObservedObject var model: AppModel
    @State private var confirmClear = false
    @State private var showPreferences = false
    @State private var filter = "all"

    private var runs: [ActivityRun] {
        model.activityRuns.filter { run in
            switch filter {
            case "running": return run.isActive
            case "failed": return run.status == "failed" || run.status == "interrupted"
            default: return true
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Text(L("活动筛选"))
                Picker(L("活动筛选"), selection: $filter) {
                    Text(L("全部")).tag("all")
                    Text(L("运行中")).tag("running")
                    Text(L("失败")).tag("failed")
                }.labelsHidden().pickerStyle(.segmented).frame(width: 190)
                Spacer()
                Button(L("刷新")) { Task { await model.refreshActivity(repeatFeedback: true) } }.disabled(model.isBusy.contains("activity"))
                Menu {
                    Button(L("观察设置…")) { showPreferences = true }
                    Button(L("清除已结束历史"), role: .destructive) { confirmClear = true }
                        .disabled(model.isBusy.contains("clear-activity"))
                } label: { Image(systemName: "ellipsis.circle") }
                .menuStyle(.borderlessButton).fixedSize().help(L("活动选项"))
            }.padding(DesktopMetrics.pagePadding)
            if !model.activityEnabled || !model.activityErrors.isEmpty {
                HStack {
                    Label(model.activityErrors.isEmpty ? L("活动记录已暂停") : L("部分活动目录无法读取"), systemImage: "exclamationmark.circle")
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button(L("查看设置")) { showPreferences = true }
                }.font(.callout).padding(.horizontal, DesktopMetrics.pagePadding).padding(.bottom, 12)
            }
            Divider()
            DesktopSplitView("activity", leadingWidths: 224...320, initialLeadingWidth: 260, detailMinimumWidth: 360) {
                List(selection: Binding<String?>(
                    get: { model.selectedActivity?.runID },
                    set: { id in
                        if let run = runs.first(where: { $0.runID == id }) {
                            Task { await model.showActivityDetails(run) }
                        }
                    })) {
                    ForEach(runs) { run in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(model.displayLabel(for: run)).fontWeight(.medium).lineLimit(2)
                            Text([run.origin, run.phase.map { model.state?.phaseLabel($0) ?? $0 }]
                                .compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · "))
                                .font(.caption).foregroundStyle(.secondary).lineLimit(1)
                            HStack {
                                StatusTag(status: run.status, label: model.state?.statusLabels[run.status])
                                Spacer()
                                Text(run.elapsedText).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                            }
                        }.padding(.vertical, 6).tag(run.runID)
                    }
                }.listStyle(.inset).scrollContentBackground(.hidden)
                    .padding(.horizontal, DesktopMetrics.insetListPadding)
            } detail: {
                if let run = model.selectedActivity {
                    VStack(alignment: .leading, spacing: 0) {
                        if model.canCancel(run) {
                            HStack {
                                Spacer()
                                Button(L("取消任务"), role: .destructive) { Task { await model.cancel(run) } }
                                    .disabled(model.isBusy.contains("cancel:\(run.runID)"))
                            }.padding([.horizontal, .top], DesktopMetrics.pagePadding)
                        }
                        ActivityDetailView(model: model, run: run, embedded: true)
                    }.frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    VStack(spacing: 10) {
                        Image(systemName: "clock").font(.system(size: 34)).foregroundStyle(.secondary)
                        Text(runs.isEmpty ? L("没有可显示的活动记录") : L("选择一条活动查看详情")).font(.headline)
                        Text(L("这里显示当前观察范围内的任务。")).foregroundStyle(.secondary)
                    }.frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .onChange(of: runs) { visibleRuns in
            if let selected = model.selectedActivity, !visibleRuns.contains(where: { $0.runID == selected.runID }) {
                model.selectedActivity = nil
            }
        }
        .task {
            while !Task.isCancelled {
                await model.refreshActivity()
                try? await Task.sleep(nanoseconds: 2_000_000_000)
            }
        }
        .alert(L("清除活动历史？"), isPresented: $confirmClear) {
            Button(L("取消"), role: .cancel) {}
            Button(L("清除已结束记录"), role: .destructive) { Task { await model.clearActivityHistory() } }
        } message: { Text(L("仅清除已结束任务的活动元数据，不会删除配置、研究证据或你导出的文件。")) }
        .sheet(isPresented: $showPreferences) {
            DetailSheet(L("观察设置")) {
                Toggle(L("记录活动"), isOn: Binding(get: { model.activityEnabled }, set: { value in Task { await model.setActivityEnabled(value) } }))
                    .disabled(model.isBusy.contains("activity-setting"))
                Text(L("没有记录不代表外部 CLI 一定空闲。")).font(.caption).foregroundStyle(.secondary)
                Button(L("添加配置目录"), action: model.addObservedDirectory)
                ForEach(model.observedDirectories, id: \.self) { directory in
                    HStack {
                        Text(directory).font(.caption).textSelection(.enabled)
                        Spacer()
                        Button(L("移除")) { model.removeObservedDirectory(directory) }
                    }
                }
                ForEach(model.activityErrors, id: \.self) { Text($0).foregroundStyle(.orange) }
            }
        }
    }
}

private struct ActivityDetailView: View {
    @ObservedObject var model: AppModel
    let run: ActivityRun
    var embedded = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text(L("活动详情")).font(.title2.weight(.semibold))
                Spacer()
                if !embedded { Button(L("完成")) { dismiss() } }
            }
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(model.displayLabel(for: run)).font(.headline)
                    HStack {
                        StatusTag(status: run.status, label: model.state?.statusLabels[run.status])
                        Text(run.elapsedText).monospacedDigit().foregroundStyle(.secondary)
                        Spacer()
                        Text(run.origin).foregroundStyle(.secondary)
                    }
                    if let phase = run.phase {
                        KeyValueLine(label: L("当前阶段"), value: model.state?.phaseLabel(phase) ?? phase)
                    }
                    let provider = [run.provider, run.model].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: " · ")
                    if !provider.isEmpty { KeyValueLine(label: L("服务商与模型"), value: provider) }
                    if let error = run.errorType, !error.isEmpty {
                        Label(error, systemImage: "exclamationmark.circle").foregroundStyle(.red)
                    }
                    Text(L("配置版本：{0}", run.configRevision ?? L("活动记录未提供")))
                        .font(.caption).foregroundStyle(.secondary).textSelection(.enabled)
                    Divider()
                    if model.hasOwnedResult(for: run) {
                        Button(L("查看结果")) { model.showOwnedResult(run) }
                    }
                    if let result = model.activityResult(for: run) {
                        ActivityResultView(result: result)
                    }
                    if let details = model.activityDetails {
                        let events = details["events"]?.arrayValue ?? []
                        if details["ok"]?.boolValue == false {
                            Text(details["error"]?.stringValue ?? L("活动详情当前不可读取。"))
                                .foregroundStyle(.red)
                        } else if !events.isEmpty {
                              VStack(alignment: .leading, spacing: 12) {
                                ForEach(events.indices, id: \.self) { index in
                                    ActivityEventRow(event: events[index], phaseLabel: model.state?.phaseLabel(events[index]["phase"]?.displayString ?? "") ?? L("未知阶段"))
                                    if index != events.indices.last { Divider() }
                                }
                            }
                        } else {
                            Text(L("后端没有返回额外的脱敏阶段元数据。"))
                                .foregroundStyle(.secondary)
                        }
                        DisclosureGroup(L("高级详情")) {
                            Text(details.redacted().prettyPrinted())
                                .font(.system(.body, design: .monospaced))
                                .textSelection(.enabled)
                        }
                    } else {
                        ProgressView(L("正在读取脱敏活动详情…"))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(DesktopMetrics.pagePadding)
        .frame(minWidth: embedded ? 300 : 560, maxWidth: .infinity, minHeight: 360, maxHeight: .infinity)
    }
}

private struct ActivityResultView: View {
    let result: JSONValue

    var body: some View {
        GroupBox(L("任务结果")) {
            VStack(alignment: .leading, spacing: 8) {
                if let text = result.readableText, !text.isEmpty {
                    Text(text).textSelection(.enabled)
                } else {
                    Text(L("后端没有提供可直接阅读的结果文本。"))
                        .foregroundStyle(.secondary)
                }
                DisclosureGroup(L("高级 JSON")) {
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
    let phaseLabel: String

    var body: some View {
        HStack(spacing: 10) {
            VStack(alignment: .leading, spacing: 3) {
                Text(phaseLabel)
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
    var label: String? = nil

    var body: some View {
        Text(label ?? ["running": L("运行中"), "finished": L("已完成"), "failed": L("失败"), "cancelled": L("已取消"), "cancelling": L("正在取消"), "stale": L("状态未更新"), "interrupted": L("已中断")][status] ?? L("状态未知"))
            .font(.caption.weight(.medium))
            .foregroundStyle(color)
            .padding(.horizontal, 8).padding(.vertical, 3)
            .background(color.opacity(0.12), in: Capsule())
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

private enum SkillsSheet: Identifiable {
    case preferences, files(JSONValue)
    var id: String {
        switch self {
        case .preferences: return "preferences"
        case .files(let target): return target["target"]?.stringValue ?? "files"
        }
    }
}

private struct IntegrationView: View {
    @ObservedObject var model: AppModel
    @State private var sheet: SkillsSheet?
    private var skills: JSONValue { model.skillsState ?? .object([:]) }
    private var unavailable: Bool { model.connection != .ready || model.environmentBusy || model.isUpdatingCLI || model.skillsBusy || model.skillsChecking }

    var body: some View {
        if model.state != nil {
            DesktopPage(L("更新 Skills"), subtitle: L("选择要接入的 Agent，再更新对应的技能文件。")) {
                DesktopPanel {
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(L("技能来源")).font(.headline)
                            Text(skills["source"]?["version"]?.stringValue.map { "CLI " + $0 } ?? L("尚未检查"))
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        Button { Task { await model.skillsAction("skills.check") } } label: {
                            BusyLabel(text: L("刷新 CLI 提供的 Skills"), busyText: L("检查中…"), busy: model.skillsChecking)
                        }.disabled(unavailable)
                        Button { sheet = .preferences } label: { Image(systemName: "gearshape") }
                            .help(L("检查偏好"))
                    }
                    if skills["cached"]?.boolValue == true {
                        Text(L("显示上次缓存；请检查最新 Skills 后再更新。")).font(.callout).foregroundStyle(.secondary)
                    }
                    if let error = skills["error"]?.stringValue, !error.isEmpty { Text(error).foregroundStyle(.red) }
                    if let compatibility = skills["compatibility"]?.stringValue, !compatibility.isEmpty {
                        Text(compatibility).font(.callout).foregroundStyle(.secondary)
                    }
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text(L("选择 Agent")).font(.headline)
                    Text(L("状态只表示 Smart Search Skill 内容。Codex 使用的 .agents/skills 也可能被其他兼容 Agent 读取。"))
                        .font(.callout).foregroundStyle(.secondary)
                }
                VStack(spacing: 0) {
                    ForEach(skills["targets"]?.arrayValue ?? [], id: \.self) { target in
                        let id = target["target"]?.stringValue ?? ""
                        let name = target["label"]?.displayString ?? id
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(name).font(.body.weight(.medium))
                                Text(skillStatus(target)).font(.caption).foregroundStyle(.secondary)
                                if let error = target["error"]?.stringValue, !error.isEmpty {
                                    Text(error).font(.caption).foregroundStyle(.red)
                                }
                            }
                            Spacer()
                            Button { sheet = .files(target) } label: { Image(systemName: "info.circle") }
                                .buttonStyle(.borderless).help(L("查看 {0} 的文件详情", name))
                            Toggle(name, isOn: Binding(
                                get: { model.selectedSkillTargets.contains(id) },
                                set: { if $0 { model.selectedSkillTargets.insert(id) } else { model.selectedSkillTargets.remove(id) } }))
                                .labelsHidden().disabled(model.skillsBusy)
                        }.padding(.vertical, 14)
                        if target != skills["targets"]?.arrayValue?.last { Divider() }
                    }
                }
                .desktopPanel(verticalPadding: 0)
                ForEach(skills["result"]?["installed"]?.arrayValue ?? [], id: \.self) { receipt in
                    Label((receipt["target"]?.displayString ?? "") + L("：已同步"), systemImage: "checkmark.circle").foregroundStyle(.green)
                    if let backup = receipt["backup"]?.stringValue, !backup.isEmpty {
                        Text(L("备份：{0}", backup)).font(.caption).textSelection(.enabled)
                    }
                }
                ForEach(skills["result"]?["removed"]?.arrayValue ?? [], id: \.self) { receipt in
                    Label(L("{0}：已移除", receipt["target"]?.displayString ?? ""), systemImage: "checkmark.circle").foregroundStyle(.green)
                    if let backup = receipt["backup"]?.stringValue, !backup.isEmpty {
                        Text(L("备份：{0}", backup)).font(.caption).textSelection(.enabled)
                    }
                }
                ForEach((skills["maintenance"]?.arrayValue ?? []).filter { ["personal_changes", "needs_attention"].contains($0["status"]?.stringValue ?? "") }, id: \.self) { item in
                    Text(L("{0}：保留个人修改或缺失文件，请查看文件详情。", item["target"]?.displayString ?? ""))
                        .font(.callout).foregroundStyle(.secondary)
                }
                ForEach(skills["result"]?["failed"]?.arrayValue ?? [], id: \.self) { failure in
                    Text((failure["target"]?.displayString ?? "") + ": " + (failure["error"]?.displayString ?? "")).foregroundStyle(.red)
                }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                VStack(spacing: 0) {
                    Divider()
                    HStack {
                        Text(L("已选择 {0} 个 Agent", "\(model.selectedSkillTargets.count)"))
                            .font(.callout).foregroundStyle(.secondary)
                        Spacer()
                        Button(L("移除 Skills"), role: .destructive) { Task { await model.removeSelectedSkills() } }
                            .disabled(unavailable || model.selectedSkillTargets.isEmpty)
                        Button { Task { await model.refreshSkillStatus() } } label: {
                            BusyLabel(text: L("刷新本机状态"), busyText: L("刷新中…"), busy: model.isBusy.contains("skills.catalog"))
                        }.disabled(unavailable || model.isBusy.contains("skills.catalog"))
                        Button { Task { await model.installSelectedSkills() } } label: {
                            BusyLabel(text: L("更新所选 Skills"), busyText: L("更新中…"), busy: model.skillsBusy)
                        }.buttonStyle(.borderedProminent)
                            .disabled(unavailable || model.skillTargetsToUpdate.isEmpty || skills["can_sync"]?.boolValue != true)
                    }.padding(.horizontal, DesktopMetrics.pagePadding).padding(.vertical, 12)
                }.background(DesktopAppearance.contentBackground)
            }
            .sheet(item: $sheet) { selected in
                switch selected {
                case .preferences:
                    DetailSheet(L("检查偏好")) {
                        Toggle(L("自动维护已接入的 Skills，保留个人修改"), isOn: Binding(
                            get: { skills["auto_check"]?.boolValue ?? true },
                            set: { enabled in Task { await model.skillsAction("skills.auto", params: .object(["enabled": .bool(enabled)])) } }))
                        if let checked = skills["source"]?["checked_at"]?.numberValue {
                            KeyValueLine(label: L("最近成功检查"), value: Date(timeIntervalSince1970: checked).formatted())
                        }
                        Text(L("不同内容会先备份；额外文件与未选目标保持原样。更新后重新打开 Agent 会话；Gemini 可运行 /skills reload。实际调用仍需在 Agent 中验证。"))
                            .font(.callout).foregroundStyle(.secondary)
                    }
                case .files(let target):
                    DetailSheet(target["label"]?.displayString ?? L("文件详情")) {
                        KeyValueLine(label: L("安装位置"), value: target["path"]?.displayString ?? L("未发现"))
                        Text(L("状态只表示 Smart Search Skill 内容。Codex 使用的 .agents/skills 也可能被其他兼容 Agent 读取。"))
                            .font(.callout).foregroundStyle(.secondary)
                        ForEach(["missing_files", "content_stale_files"], id: \.self) { key in
                            let files = target[key]?.arrayValue ?? []
                            if !files.isEmpty {
                                Text(key == "missing_files" ? L("待安装的文件") : L("内容不同的文件")).font(.headline)
                                Text(files.map(\.displayString).joined(separator: "\n"))
                                    .font(.system(.callout, design: .monospaced)).textSelection(.enabled)
                            }
                        }
                        if target["invocation_changed"]?.boolValue == true {
                            Text(L("本机 CLI 调用信息需要刷新。")).font(.callout).foregroundStyle(.secondary)
                        }
                        Text(L("这里只查看文件状态。点击“更新所选 Skills”后才会安装或更新文件。"))
                            .font(.callout).foregroundStyle(.secondary)
                        ForEach(target["legacy_locations"]?.arrayValue ?? [], id: \.self) { legacy in
                            Text(L("历史副本，保留：{0}", legacy["path"]?.displayString ?? "")).font(.caption)
                        }
                    }
                }
            }
        } else { BackendUnavailableView(model: model) }
    }

    private func skillStatus(_ value: JSONValue) -> String {
        if value["invocation_changed"]?.boolValue == true,
           (value["content_stale_files"]?.arrayValue ?? []).isEmpty,
           (value["missing_files"]?.arrayValue ?? []).isEmpty { return L("调用信息需刷新") }
        switch value["status"]?.stringValue {
        case "missing": return L("未安装")
        case "stale": return L("内容不同，可同步")
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
                settingsSection(L("App 更新"), subtitle: L("独立更新 App，不改变 CLI 安装。")) {
                    AppUpdatesView(model: model)
                }
                settingsSection(L("高级"), subtitle: L("配置连接参数和诊断选项。")) {
                    DisclosureGroup(L("诊断与维护")) { advancedSettings }
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
                    Text(L("保存服务商配置和本地记录的文件夹；移动 App 不会改变此目录。"))
                        .font(.callout).foregroundStyle(.secondary)
                    Text(model.state?.configDirectory ?? L("后端尚未提供"))
                        .font(.system(.callout, design: .monospaced))
                        .foregroundStyle(.secondary).textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                HStack(spacing: 8) {
                    Button(model.isBusy.contains("profile") ? L("切换中…") : L("选择配置目录…"), action: model.chooseConfigDirectory)
                    if model.state?.defaultConfigDirectory != nil && model.state?.isDefaultConfigDirectory == false {
                        Button(L("恢复默认配置目录")) { Task { await model.restoreDefaultConfigDirectory() } }
                    }
                }
                .fixedSize()
                .frame(minWidth: 168, alignment: .trailing)
                .disabled(model.connection != .ready || model.configOperationBusy || model.environmentBusy || model.skillsBusy)
            }
        }
    }

    private var advancedSettings: some View {
        VStack(alignment: .leading, spacing: 12) {
            DesktopPanel(L("后端连接"), compact: true) {
                VStack(alignment: .leading, spacing: 8) {
                    DisclosureGroup(L("开发选项")) {
                        VStack(alignment: .leading, spacing: 8) {
                            TextField(L("开发环境后端路径（可选）"), text: $model.backendPathOverride)
                            HStack {
                                Button(L("选择…"), action: model.chooseBackendExecutable)
                                Button(L("恢复 CLI 自动检测")) { model.saveBackendOverride("") }
                            }
                            Text(L("默认连接所选独立 CLI。开发路径只在明确选择后使用。"))
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    HStack {
                        Stepper(L("请求超时：{0} 秒", "\(Int(model.requestTimeoutSeconds))"), value: $model.requestTimeoutSeconds, in: 5...300, step: 5)
                        Button(L("应用超时"), action: model.applyTimeout)
                    }
                    HStack {
                        ConnectionIndicator(state: model.connection)
                        Spacer()
                        Button(model.isBusy.contains("connect") ? L("连接中…") : L("重新连接")) { model.saveBackendOverride(model.backendPathOverride); Task { await model.reconnect() } }.disabled(model.isBusy.contains("connect"))
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
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
