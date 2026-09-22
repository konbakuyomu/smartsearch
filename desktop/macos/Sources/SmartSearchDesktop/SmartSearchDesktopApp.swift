import AppKit
import SwiftUI

@main
struct SmartSearchDesktopApp: App {
    @NSApplicationDelegateAdaptor(ApplicationDelegate.self) private var applicationDelegate
    @StateObject private var model = AppModel()
    @AppStorage(AppearancePreference.defaultsKey) private var appearance = AppearancePreference.system

    var body: some Scene {
        Window("Smart Search", id: "main") {
            ContentView(model: model)
                .preferredColorScheme(appearance.colorScheme)
                .onAppear { appearance.applyToApplication() }
                .onChange(of: appearance) { $0.applyToApplication() }
                .frame(minWidth: 920, minHeight: 620)
                .background(WindowConfigurator { window in
                    applicationDelegate.configure(window: window, model: model)
                })
        }
        .defaultSize(width: 1080, height: 760)
        .commands {
            LocalizedCommands(model: model, showMainWindow: applicationDelegate.showMainWindow)
        }

        MenuBarExtra("Smart Search", systemImage: "magnifyingglass") {
            Group {
                Button(L("显示 Smart Search")) { applicationDelegate.showMainWindow() }
                if model.hasOwnedActiveRuns {
                    Text(L("有 App 任务正在后台运行"))
                }
                Divider()
                Button(L("退出")) { NSApp.terminate(nil) }
            }
            .id(model.languagePreference)
            .environment(\.locale, model.interfaceLocale)
        }
        .menuBarExtraStyle(.menu)
    }
}

@MainActor
private struct LocalizedCommands: Commands {
    @ObservedObject var model: AppModel
    let showMainWindow: () -> Void

    var body: some Commands {
        CommandGroup(replacing: .appSettings) {
            Button(L("设置")) {
                model.selectedDestination = .settings
                showMainWindow()
            }.keyboardShortcut(",", modifiers: .command)
            .id(model.languagePreference)
        }
        CommandMenu(L("导航")) {
            Group {
                Button(L("配置")) { model.selectedDestination = .providers }.keyboardShortcut("1", modifiers: .command)
                Button(L("测试")) { model.selectedDestination = .search }.keyboardShortcut("2", modifiers: .command)
                Button(L("CLI 与 Skills")) { model.selectedDestination = .integration }.keyboardShortcut("3", modifiers: .command)
                Button(L("设置")) { model.selectedDestination = .settings }.keyboardShortcut("4", modifiers: .command)
            }
            .id(model.languagePreference)
            .environment(\.locale, model.interfaceLocale)
        }
        CommandGroup(after: .appInfo) {
            Button(L("重新读取配置")) { Task { await model.refreshState() } }.keyboardShortcut("r", modifiers: .command)
            .id(model.languagePreference)
        }
    }
}

@MainActor
final class ApplicationDelegate: NSObject, NSApplicationDelegate {
    private let mainWindowDelegate = MainWindowDelegate()
    private weak var model: AppModel?
    private weak var mainWindow: NSWindow?

    func applicationWillFinishLaunching(_ notification: Notification) {
        // Packaged apps keep the system-rendered bundle icon and its macOS background.
        // Only bare SwiftPM launches need an explicit fallback icon.
        if Bundle.main.bundleURL.pathExtension != "app" {
            NSApp.applicationIconImage = AppBranding.icon
        }
    }

    func configure(window: NSWindow, model: AppModel) {
        self.model = model
        mainWindow = window
        mainWindowDelegate.model = model
        window.delegate = mainWindowDelegate
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { showMainWindow() }
        return true
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        if model?.terminationReady == true { return .terminateNow }
        if model?.appUpdatePreparing == true { return .terminateCancel }
        if let model, !model.configDraft.isEmpty || !model.clearSecretKeys.isEmpty {
            model.noticeMessage = L("请先保存或放弃未保存的配置，再退出或安装更新。")
            showMainWindow()
            return .terminateCancel
        }
        if let model, model.isUpdatingCLI || model.environmentBusy || model.skillsBusy {
            model.noticeMessage = L("环境或 Skills 操作正在进行，请等待完成后退出。")
            showMainWindow()
            return .terminateCancel
        }
        guard let model else { return .terminateNow }
        if !model.hasOwnedActiveRuns {
            Task {
                await model.shutdownForQuit()
                sender.reply(toApplicationShouldTerminate: true)
            }
            return .terminateLater
        }
        model.presentQuitChoice { choice in
            switch choice {
            case .background, .return:
                sender.reply(toApplicationShouldTerminate: false)
            case .stopAndQuit:
                Task {
                    await model.shutdownForQuit()
                    sender.reply(toApplicationShouldTerminate: true)
                }
            }
        }
        return .terminateLater
    }

    func showMainWindow() {
        NSApp.activate(ignoringOtherApps: true)
        if mainWindow?.isMiniaturized == true { mainWindow?.deminiaturize(nil) }
        mainWindow?.makeKeyAndOrderFront(nil)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        false
    }
}

@MainActor
private final class MainWindowDelegate: NSObject, NSWindowDelegate {
    weak var model: AppModel?

    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if model?.appUpdatePreparing == true { return false }
        if let model, model.isUpdatingCLI || model.environmentBusy || model.skillsBusy {
            model.noticeMessage = L("环境操作或 CLI 更新正在进行，请等待完成；可以最小化窗口。")
            return false
        }
        guard let model, model.hasOwnedActiveRuns else {
            sender.orderOut(nil)
            return false
        }
        model.presentWindowCloseChoice(for: sender)
        return false
    }
}

enum AppBranding {
    static let mascot: NSImage? = Bundle.main.url(forResource: "mascot", withExtension: "png")
        .flatMap { NSImage(contentsOf: $0) }

    static let icon: NSImage = {
        if let url = Bundle.main.url(forResource: "smart-search", withExtension: "png"),
           let image = NSImage(contentsOf: url) {
            return image
        }
        if let url = Bundle.main.url(forResource: "SmartSearch", withExtension: "icns"),
           let image = NSImage(contentsOf: url) {
            return image
        }
        return NSImage(systemSymbolName: "magnifyingglass", accessibilityDescription: "Smart Search")!
    }()
}

private struct WindowConfigurator: NSViewRepresentable {
    let configure: (NSWindow) -> Void

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            if let window = view.window { configure(window) }
        }
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        if let window = nsView.window { configure(window) }
    }
}
