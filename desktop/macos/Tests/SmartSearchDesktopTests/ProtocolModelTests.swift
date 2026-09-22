import XCTest
@testable import SmartSearchDesktop

final class ProtocolModelTests: XCTestCase {
    private var previousLanguage: String?

    override func setUp() {
        super.setUp()
        previousLanguage = UserDefaults.standard.string(forKey: Localization.preferenceKey)
        UserDefaults.standard.set("zh", forKey: Localization.preferenceKey)
    }

    override func tearDown() {
        if let previousLanguage {
            UserDefaults.standard.set(previousLanguage, forKey: Localization.preferenceKey)
        } else {
            UserDefaults.standard.removeObject(forKey: Localization.preferenceKey)
        }
        super.tearDown()
    }

    func testBundledLanguagesKeepArgumentTextLiteral() {
        XCTAssertFalse(Localization.messages.isEmpty)
        XCTAssertEqual(L("Task cancelled."), "任务已取消。")
        UserDefaults.standard.set("en", forKey: Localization.preferenceKey)
        XCTAssertEqual(L("任务已取消。"), "Task cancelled.")
        XCTAssertEqual(L("HTTP {0}: {1}", "400", "upstream {0}"), "HTTP 400: upstream {0}")
        XCTAssertEqual(Localization.resolve("zh"), "zh")
        XCTAssertEqual(Localization.resolve("en"), "en")
    }

    func testDynamicResponsesUseTypedObjectFields() throws {
        let value = try JSONDecoder().decode(JSONValue.self, from: Data("""
        {"ok":true,"run_id":"owned-run","runs":[],"enabled":false}
        """.utf8))
        XCTAssertEqual(value["ok"]?.boolValue, true)
        XCTAssertEqual(value["run_id"]?.stringValue, "owned-run")
        XCTAssertEqual(value["runs"]?.arrayValue, [])
        XCTAssertEqual(value["enabled"]?.boolValue, false)
        XCTAssertNil(value["missing"]?.boolValue)
        XCTAssertNil(value["run_id"]?.boolValue)
    }

    func testNDJSONValueAndCatalogArgumentsKeepProtocolOrder() throws {
        let payload = Data("""
        {"id":"search","label":"Search","description":"","experimental":false,"fields":[
          {"name":"query","label":"Query","help":"","flags":[],"kind":"text","choices":[],"required":true,"multiple":false,"advanced":false},
          {"name":"tags","label":"Tags","help":"","flags":["--tag"],"kind":"text","choices":[],"required":false,"multiple":true,"advanced":true},
          {"name":"stream","label":"Stream","help":"","flags":["--stream"],"kind":"bool","choices":[],"required":false,"multiple":false}
        ]}
        """.utf8)
        let value = try JSONDecoder().decode(JSONValue.self, from: payload)
        let command = try XCTUnwrap(CommandCatalogEntry(value))

        XCTAssertEqual(
            CommandArgumentBuilder.arguments(
                for: command,
                values: ["query": "native search", "tags": "swift\nmacos"],
                booleans: ["stream": true]
            ),
            ["native search", "--tag", "swift", "--tag", "macos", "--stream"]
        )
        XCTAssertTrue(CommandArgumentBuilder.missingRequired(for: command, values: [:], booleans: [:]).contains { $0.name == "query" })
        XCTAssertFalse(command.fields[0].isAdvanced)
        XCTAssertTrue(command.fields[1].isAdvanced)
    }

    func testSensitiveOutputIsRedactedBeforeCopyOrExport() {
        let value: JSONValue = .object([
            "answer": .string("safe"),
            "api_key": .string("not-for-display"),
            "nested": .object(["authorization": .string("not-for-display")]),
        ])

        let redacted = value.redacted().objectValue
        XCTAssertEqual(redacted?["api_key"]?.stringValue, "***")
        XCTAssertEqual(redacted?["nested"]?["authorization"]?.stringValue, "***")
        XCTAssertEqual(redacted?["answer"]?.stringValue, "safe")
    }

    func testOwnedResultsStayAssociatedWithTheirRunAndRespectCapacity() {
        var store = OwnedRunResultStore(capacity: 2)
        store.register(runID: "search", kind: .business, label: "搜索")
        store.register(runID: "probe", kind: .providerTest, label: "测试草稿")
        store.register(runID: "skills", kind: .skillsInstall, label: "Skills 更新")

        XCTAssertEqual(store.cache(.object(["answer": .string("answer")]), for: "search")?.kind, .business)
        XCTAssertEqual(store.cache(.object(["error": .string("failed")]), for: "probe")?.kind, .providerTest)
        XCTAssertEqual(store.result(for: "search")?["answer"]?.stringValue, "answer")
        XCTAssertEqual(store.result(for: "probe")?["error"]?.stringValue, "failed")

        store.cache(.object(["ok": .bool(true)]), for: "skills")
        XCTAssertNil(store.result(for: "search"))
        XCTAssertNil(store.descriptor(for: "search"))
        XCTAssertEqual(store.result(for: "probe")?["error"]?.stringValue, "failed")
        XCTAssertEqual(store.result(for: "skills")?["ok"]?.boolValue, true)
    }

    func testStateKeepsCooldownAndDraftChecksAsSeparateFacts() throws {
        let snapshot: JSONValue = .object([
            "provider_health": .object([
                "providers": .array([
                    .object(["provider": .string("exa"), "state": .string("closed"), "configured": .bool(true)]),
                ]),
            ]),
            "provider_checks": .object([
                "exa": .object([
                    "status": .string("ok"),
                    "checked_at": .number(1_700_000_000),
                    "source": .string("app"),
                    "scope": .string("draft"),
                ]),
            ]),
        ])
        let state = try XCTUnwrap(DesktopState(snapshot))

        XCTAssertEqual(state.providerHealth?["providers"]?.arrayValue?.first?["state"]?.stringValue, "closed")
        XCTAssertEqual(state.providerChecks?["exa"]?["scope"]?.stringValue, "draft")
        XCTAssertEqual(state.providerChecks?["exa"]?["source"]?.stringValue, "app")
    }
    func testOperationsStayBusyUntilWorkerFinishesAndResetAfterDisconnect() {
        var state = OperationState()
        XCTAssertTrue(state.begin("test:exa"))
        XCTAssertFalse(state.begin("test:exa"))
        state.track("probe", key: "test:exa")
        state.track("docs", key: "test:context7")
        XCTAssertEqual(state.runIDs(for: "test:exa"), ["probe"])
        state.endRequest("test:exa")
        XCTAssertTrue(state.busyKeys.contains("test:exa"))
        XCTAssertFalse(state.begin("test:exa"))
        XCTAssertFalse(state.begin("test:context7"))
        state.track("probe", key: "cancel:probe")
        state.finish("probe")
        XCTAssertTrue(state.runIDs(for: "test:exa").isEmpty)
        XCTAssertEqual(state.runIDs(for: "test:context7"), ["docs"])
        XCTAssertFalse(state.busyKeys.contains("test:exa"))
        XCTAssertFalse(state.busyKeys.contains("cancel:probe"))
        state.reset()
        XCTAssertTrue(state.busyKeys.isEmpty)
    }

    func testSkillsSelectionEnablesOneActionBeforeSourceCheck() {
        var selected: Set<String> = []
        XCTAssertFalse(SkillsSelectionPolicy.canUpdate(connected: true, selectedCount: selected.count, busy: false))
        selected.insert("opencode")
        XCTAssertTrue(SkillsSelectionPolicy.canUpdate(connected: true, selectedCount: selected.count, busy: false))
        XCTAssertFalse(SkillsSelectionPolicy.canUpdate(connected: true, selectedCount: selected.count, busy: true))
        XCTAssertFalse(SkillsSelectionPolicy.canUpdate(connected: false, selectedCount: selected.count, busy: false))
        selected.removeAll()
        XCTAssertFalse(SkillsSelectionPolicy.canUpdate(connected: true, selectedCount: selected.count, busy: false))
    }

    func testConfigurationMetadataPreservesOrderAndHints() throws {
        let payload = Data("""
        {"metadata":{"sections":[{"id":"diagnostics","order":8},{"id":"getting_started","order":1}],
          "status_labels":{"closed":{"zh":"未冷却"}},
          "fields":[{"key":"OPENAI_COMPATIBLE_MODEL","section":"getting_started","tier":"advanced",
            "provider":"openai-compatible","default":"model-default","placeholder":"模型名称","capabilities":["main_search"]}]},
          "capability_chains":{"main_search":["openai-compatible"]}}
        """.utf8)
        let state = try XCTUnwrap(DesktopState(try JSONDecoder().decode(JSONValue.self, from: payload)))
        XCTAssertEqual(state.sections.map(\.id), ["getting_started", "diagnostics"])
        XCTAssertTrue(state.fields[0].isAdvanced)
        XCTAssertEqual(state.fields[0].placeholder, "模型名称")
        XCTAssertEqual(state.effectiveValue(for: state.fields[0]), "model-default")
        XCTAssertEqual(state.capabilityChains["main_search"], ["openai-compatible"])
        XCTAssertEqual(state.statusLabels["closed"], "未冷却")
    }
    func testActivityPhasesUseCommandLabelsWhileRawEventsRemainAvailable() throws {
        let value: JSONValue = .object([
            "commands": .array([.object(["id": .string("regression"), "label": .string("离线回归检查")])]),
            "metadata": .object(["status_labels": .object(["finished": .object(["zh": .string("已完成")])])])
        ])
        let state = try XCTUnwrap(DesktopState(value))
        XCTAssertEqual(state.phaseLabel("provider.test"), "服务商测试")
        XCTAssertEqual(state.phaseLabel("version"), "版本查询")
        XCTAssertEqual(state.phaseLabel("regression"), "离线回归检查")
        XCTAssertEqual(state.phaseLabel("finished"), "已完成")
        XCTAssertEqual(state.phaseLabel("new_internal_phase"), "处理中")
    }
}
