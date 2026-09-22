import AppKit
import Combine
import Foundation
import Sparkle

@MainActor
final class AppUpdater: NSObject, ObservableObject, SPUUpdaterDelegate, SPUStandardUserDriverDelegate {
    @Published private(set) var started = false
    @Published private(set) var checking = false
    @Published private(set) var latestVersion = ""
    @Published private(set) var statusMessage = ""
    @Published private(set) var waitingToRestart = false
    @Published private(set) var checkedAt: Date?
    var canInstall: () -> Bool = { false }
    var prepareInstall: () async -> Bool = { false }
    var recoverInstall: () async -> Void = {}
    private var resumeInstallation: (() -> Void)?
    private var preparing = false
    private var prepared = false
    private var deferredPrompt = false
    private var shownVersions: Set<String> = []
    private lazy var driver = SPUStandardUserDriver(hostBundle: .main, delegate: self)
    private lazy var updater = SPUUpdater(hostBundle: .main, applicationBundle: .main, userDriver: driver, delegate: self)

    var currentVersion: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "" }

    func synchronize(automaticallyChecks: Bool, enabled: Bool) {
        guard enabled else { if started { updater.automaticallyChecksForUpdates = false }; return }
        if !started {
            guard let key = Bundle.main.object(forInfoDictionaryKey: "SUPublicEDKey") as? String,
                  Data(base64Encoded: key)?.count == 32 else {
                statusMessage = L("此测试包尚未配置更新签名，App 自动更新不可用。")
                return
            }
            updater.automaticallyChecksForUpdates = automaticallyChecks
            updater.automaticallyDownloadsUpdates = false
            updater.updateCheckInterval = 86400
            do { try updater.start(); started = true }
            catch { statusMessage = L("App 更新配置无效，请使用完整安装包。"); return }
        }
        if updater.automaticallyChecksForUpdates != automaticallyChecks {
            updater.automaticallyChecksForUpdates = automaticallyChecks
        }
        if updater.automaticallyDownloadsUpdates { updater.automaticallyDownloadsUpdates = false }
    }

    func check() {
        if waitingToRestart { Task { await completePreparedUpdate() }; return }
        guard started, updater.canCheckForUpdates else { return }
        checking = true
        statusMessage = ""
        updater.checkForUpdates()
    }

    func resumePromptIfPossible() {
        guard deferredPrompt, started, updater.automaticallyChecksForUpdates, canInstall() else { return }
        deferredPrompt = false
        shownVersions.insert(latestVersion)
        updater.checkForUpdates() // Brings the already-fetched scheduled update into focus.
    }

    func updater(_ updater: SPUUpdater, didFindValidUpdate item: SUAppcastItem) {
        latestVersion = item.displayVersionString
        checkedAt = Date()
        checking = false
        statusMessage = L("有新版可下载")
    }

    func updaterDidNotFindUpdate(_ updater: SPUUpdater) {
        latestVersion = ""
        checkedAt = Date()
        statusMessage = L("没有更高的可安装版本")
    }

    func updater(_ updater: SPUUpdater, shouldProceedWithUpdate item: SUAppcastItem, updateCheck: SPUUpdateCheck) throws {
        if updateCheck == .updatesInBackground && shownVersions.contains(item.displayVersionString) {
            // SUNoUpdateError: a dismissed version is silent until a manual check or next launch.
            throw NSError(domain: SUSparkleErrorDomain, code: 1001, userInfo: [NSLocalizedDescriptionKey: L("稍后可在设置中更新。")])
        }
    }

    var supportsGentleScheduledUpdateReminders: Bool { true }

    func standardUserDriverShouldHandleShowingScheduledUpdate(_ update: SUAppcastItem, andInImmediateFocus immediateFocus: Bool) -> Bool {
        canInstall()
    }

    func standardUserDriverWillHandleShowingUpdate(_ handleShowingUpdate: Bool, forUpdate update: SUAppcastItem, state: SPUUserUpdateState) {
        deferredPrompt = !handleShowingUpdate
        if handleShowingUpdate { shownVersions.insert(update.displayVersionString) }
    }

    func updater(_ updater: SPUUpdater, shouldPostponeRelaunchForUpdate item: SUAppcastItem, untilInvokingBlock installHandler: @escaping () -> Void) -> Bool {
        resumeInstallation = installHandler
        waitingToRestart = true
        Task { await completePreparedUpdate() }
        return true
    }

    private func completePreparedUpdate() async {
        guard !preparing, let resume = resumeInstallation else { return }
        guard canInstall() else {
            statusMessage = L("请先保存修改并结束当前操作，再更新 App。")
            return
        }
        preparing = true
        defer { preparing = false }
        guard await prepareInstall() else { return }
        prepared = true
        resumeInstallation = nil
        waitingToRestart = false
        resume()
    }

    func updater(_ updater: SPUUpdater, didFinishUpdateCycleFor updateCheck: SPUUpdateCheck, error: Error?) {
        checking = false
        deferredPrompt = false
        resumeInstallation = nil
        waitingToRestart = false
        if let error = error as NSError?, !(error.domain == SUSparkleErrorDomain && error.code == 1001) {
            statusMessage = L("App 更新未完成，请重新检查或使用完整安装包。")
            if prepared { prepared = false; Task { await recoverInstall() } }
        }
    }
}
