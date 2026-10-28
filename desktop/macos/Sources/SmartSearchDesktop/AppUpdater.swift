import AppKit
import Combine
import Foundation
import Sparkle

@MainActor
final class AppUpdater: NSObject, ObservableObject, SPUUpdaterDelegate {
    enum Phase { case idle, checking, available, upToDate, skipped, downloading, ready, failed }

    @Published private(set) var started = false
    @Published private(set) var automaticallyChecks = UserDefaults.standard.object(forKey: "SmartSearchDesktop.appAutoCheck") as? Bool ?? UserDefaults.standard.object(forKey: "SUEnableAutomaticChecks") as? Bool ?? true
    @Published private(set) var phase: Phase = .idle
    @Published private(set) var latestVersion = ""
    @Published private(set) var waitingToRestart = false
    @Published private(set) var checkedAt: Date?
    @Published private(set) var sessionInProgress = false
    @Published private var canShowUpdate = false
    @Published private var unavailableReason = ""
    private var observations: [NSKeyValueObservation] = []
    var canInstall: () -> Bool = { false }
    var prepareInstall: () async -> Bool = { false }
    var recoverInstall: () async -> Void = {}
    private var resumeInstallation: (() -> Void)?
    private var preparing = false
    private var prepared = false
    private lazy var driver = SPUStandardUserDriver(hostBundle: .main, delegate: nil)
    private lazy var updater = SPUUpdater(hostBundle: .main, applicationBundle: .main, userDriver: driver, delegate: self)

    var currentVersion: String { Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "" }
    var checking: Bool { phase == .checking }
    var available: Bool { !latestVersion.isEmpty && phase != .failed && phase != .skipped }
    var canCheck: Bool { started && !sessionInProgress && !checking && !waitingToRestart }
    var canInstallUpdate: Bool { started && !checking && (waitingToRestart || canShowUpdate) }
    var statusMessage: String {
        if !unavailableReason.isEmpty { return L(unavailableReason) }
        switch phase {
        case .idle: return L("尚未检查")
        case .checking: return L("正在检查 App 更新…")
        case .available: return L("发现新版本 {0}", latestVersion)
        case .upToDate: return L("暂无可安装的更新")
        case .skipped: return L("已跳过版本 {0}", latestVersion)
        case .downloading: return L("正在下载并准备更新…")
        case .ready: return L("更新已就绪")
        case .failed: return L("App 更新未完成，请重试。")
        }
    }

    func start() {
        guard !started else { return }
        unavailableReason = ""
        guard let key = Bundle.main.object(forInfoDictionaryKey: "SUPublicEDKey") as? String,
              Data(base64Encoded: key)?.count == 32 else {
            unavailableReason = "此副本尚未配置自动更新，请安装正式版。"
            return
        }
        // App owns the launch-only preference; Sparkle still owns verified installation.
        UserDefaults.standard.set(automaticallyChecks, forKey: "SmartSearchDesktop.appAutoCheck")
        updater.automaticallyChecksForUpdates = false
        updater.automaticallyDownloadsUpdates = false
        do { try updater.start(); started = true }
        catch { unavailableReason = "App 更新配置无效，请安装正式版后重试。"; return }
        observations = [
            updater.observe(\.sessionInProgress, options: [.initial, .new]) { [weak self] _, _ in
                Task { @MainActor in self?.refreshAvailability() }
            },
            updater.observe(\.canCheckForUpdates, options: [.initial, .new]) { [weak self] _, _ in
                Task { @MainActor in self?.refreshAvailability() }
            },
        ]
        // Checked once per launch; Sparkle shows its prompt (Install / Later / Skip) only when an update is found.
        if automaticallyChecks { updater.checkForUpdatesInBackground() }
        refreshAvailability()
    }

    func setAutomaticallyChecks(_ value: Bool) {
        guard started else { return }
        automaticallyChecks = value
        UserDefaults.standard.set(value, forKey: "SmartSearchDesktop.appAutoCheck")
        if value && canCheck { updater.checkForUpdateInformation() }
    }

    private func refreshAvailability() {
        sessionInProgress = updater.sessionInProgress
        canShowUpdate = updater.canCheckForUpdates
    }

    func check() {
        guard canCheck, !updater.sessionInProgress else { return }
        phase = .checking
        // Manual checks include skipped versions and expose Sparkle's Install / Later / Skip choices.
        updater.checkForUpdates()
        refreshAvailability()
    }

    func install() {
        guard canInstallUpdate else { return }
        if waitingToRestart { Task { await completePreparedUpdate() }; return }
        updater.checkForUpdates()
        refreshAvailability()
    }

    func updater(_ updater: SPUUpdater, mayPerform updateCheck: SPUUpdateCheck) throws {
        phase = .checking
    }

    func updater(_ updater: SPUUpdater, didFindValidUpdate item: SUAppcastItem) {
        latestVersion = item.displayVersionString
        checkedAt = Date()
        phase = .available
    }

    func updaterDidNotFindUpdate(_ updater: SPUUpdater) {
        latestVersion = ""
        checkedAt = Date()
        phase = .upToDate
    }

    func updater(_ updater: SPUUpdater, userDidMake choice: SPUUserUpdateChoice, forUpdate item: SUAppcastItem, state: SPUUserUpdateState) {
        if choice == .skip && state.stage != .installing { phase = .skipped }
    }

    func updater(_ updater: SPUUpdater, willDownloadUpdate item: SUAppcastItem, with request: NSMutableURLRequest) {
        phase = .downloading
    }

    func updater(_ updater: SPUUpdater, didExtractUpdate item: SUAppcastItem) {
        phase = .ready
    }

    func updater(_ updater: SPUUpdater, shouldPostponeRelaunchForUpdate item: SUAppcastItem, untilInvokingBlock installHandler: @escaping () -> Void) -> Bool {
        resumeInstallation = installHandler
        waitingToRestart = true
        phase = .ready
        Task { await completePreparedUpdate() }
        return true
    }

    private func completePreparedUpdate() async {
        guard !preparing, let resume = resumeInstallation else { return }
        guard canInstall() else { return }
        preparing = true
        defer { preparing = false }
        guard await prepareInstall() else { return }
        prepared = true
        resumeInstallation = nil
        waitingToRestart = false
        resume()
    }

    func updater(_ updater: SPUUpdater, didFinishUpdateCycleFor updateCheck: SPUUpdateCheck, error: Error?) {
        if let error = error as NSError?, !(error.domain == SUSparkleErrorDomain && error.code == 1001) {
            phase = .failed
            resumeInstallation = nil
            waitingToRestart = false
            if prepared { prepared = false; Task { await recoverInstall() } }
        } else if !waitingToRestart && phase != .upToDate && phase != .skipped {
            phase = latestVersion.isEmpty ? .idle : .available
        }
        refreshAvailability()
    }
}
