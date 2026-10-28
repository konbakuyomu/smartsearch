import XCTest
@testable import SmartSearchDesktop

// The App launches from the last detection and detects again in the background. A fake standalone CLI
// (a script answering --desktop-capabilities) stands in for a real one; nothing else is searched.
final class CLIDetectionTests: XCTestCase {
    @MainActor
    func testLaunchRestoresTheLastDetectionOnlyWhileItsCLICanStart() async throws {
        let fixture = try Fixture(self)
        let cli = try fixture.makeCLI(version: "1.2.3")
        let first = fixture.manager()
        first.setCliPath(cli)
        await first.discover()
        XCTAssertEqual(first.selected?.version, "1.2.3")

        let relaunched = fixture.manager()
        XCTAssertTrue(relaunched.restoreLastDetection())
        XCTAssertEqual(relaunched.selected?.id, cli)
        XCTAssertFalse(relaunched.busy)

        try FileManager.default.removeItem(atPath: cli)
        XCTAssertFalse(fixture.manager().restoreLastDetection())
    }

    @MainActor
    func testADetectionMadeWithOtherPathsIsNotRestored() async throws {
        let fixture = try Fixture(self)
        let first = fixture.manager()
        first.setCliPath(try fixture.makeCLI(version: "1.2.3"))
        await first.discover()

        let relaunched = fixture.manager()
        relaunched.setNpmPath("/elsewhere/bin/npm")
        XCTAssertFalse(relaunched.restoreLastDetection())
    }

    @MainActor
    func testDetectingAgainNeverReplacesTheRunningCLIUntilTheAppSwitches() async throws {
        let fixture = try Fixture(self)
        let cli = try fixture.makeCLI(version: "1.2.3")
        let first = fixture.manager()
        first.setCliPath(cli)
        await first.discover()
        let relaunched = fixture.manager()
        XCTAssertTrue(relaunched.restoreLastDetection())

        let unchanged = await relaunched.redetect(quietly: true)
        XCTAssertEqual(unchanged, .unchanged)

        try fixture.makeCLI(version: "1.2.4")
        let changed = await relaunched.redetect(quietly: true)
        XCTAssertEqual(changed, .changed)
        XCTAssertEqual(relaunched.selected?.version, "1.2.3")
        relaunched.showRedetection()
        XCTAssertEqual(relaunched.selected?.version, "1.2.4")

        try FileManager.default.removeItem(atPath: cli)
        let missing = await relaunched.redetect(quietly: true)
        XCTAssertEqual(missing, .missing)
        XCTAssertEqual(relaunched.selected?.version, "1.2.4")
    }
}

private struct Fixture {
    let directory: URL
    let defaults: UserDefaults

    init(_ test: XCTestCase) throws {
        directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: directory.appendingPathComponent("empty"), withIntermediateDirectories: true)
        let suite = "SmartSearchDesktopTests." + UUID().uuidString
        defaults = UserDefaults(suiteName: suite)!
        let directory = directory
        test.addTeardownBlock {
            UserDefaults.standard.removePersistentDomain(forName: suite)
            try? FileManager.default.removeItem(at: directory)
        }
    }

    // An empty search path: no npm or mise is found, so only the chosen CLI is detected.
    @MainActor
    func manager() -> CLIInstallationManager {
        CLIInstallationManager(searchPath: directory.appendingPathComponent("empty").path, preferences: defaults)
    }

    // A standalone CLI download: smart-search beside package.json and _internal.
    @discardableResult
    func makeCLI(version: String) throws -> String {
        let root = directory.appendingPathComponent("cli")
        try FileManager.default.createDirectory(at: root.appendingPathComponent("_internal"), withIntermediateDirectories: true)
        try #"{"name":"@konbakuyomu/smart-search","version":"\#(version)"}"#
            .write(to: root.appendingPathComponent("package.json"), atomically: true, encoding: .utf8)
        try #"{"product":"smart-search","version":"\#(version)","desktop_protocol_version":1}"#
            .write(to: root.appendingPathComponent("capabilities.json"), atomically: true, encoding: .utf8)
        let executable = root.appendingPathComponent("smart-search")
        try "#!/bin/sh\ncat \"$(dirname \"$0\")/capabilities.json\"\n".write(to: executable, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)
        return executable.path
    }
}
