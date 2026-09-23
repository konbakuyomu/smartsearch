import AppKit
import SwiftUI

// Codex Tweaks: MainWindowView, UpdateView and BackendPresentationTokens.
// Keep the reference layout values local; no dependency on its backend contract.
enum DesktopMetrics {
    static let pagePadding: CGFloat = 24
    static let insetListPadding: CGFloat = 8
    static let sectionSpacing: CGFloat = 24
    static let cardPadding: CGFloat = 16
    static let cardRadius: CGFloat = 12
}

enum DesktopAppearance {
    // White in light appearance; use the matching native surface in dark appearance.
    static let contentBackground = Color(nsColor: .textBackgroundColor)
    // Shared with Windows: the green from the approved macOS indicator (#35C759).
    static let connectionReady = NSColor(srgbRed: 53.0 / 255, green: 199.0 / 255, blue: 89.0 / 255, alpha: 1)
}

struct DesktopPage<Content: View>: View {
    let title: String
    let subtitle: String
    let secondarySubtitle: String
    let content: Content

    init(_ title: String, subtitle: String, secondarySubtitle: String = "",
         @ViewBuilder content: () -> Content) {
        self.title = title
        self.subtitle = subtitle
        self.secondarySubtitle = secondarySubtitle
        self.content = content()
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: DesktopMetrics.sectionSpacing) {
                VStack(alignment: .leading, spacing: 7) {
                    Text(title).font(.title2.weight(.semibold))
                    Text(subtitle)
                        .font(.body)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    if !secondarySubtitle.isEmpty {
                        Text(secondarySubtitle)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                content
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(DesktopMetrics.pagePadding)
            .frame(maxWidth: .infinity, alignment: .topLeading)
        }
        .background(DesktopAppearance.contentBackground)
        .scrollIndicators(.visible)
        .textFieldStyle(.roundedBorder)
    }
}

struct DesktopPanel<Content: View>: View {
    let title: String?
    let compact: Bool
    let content: Content

    init(_ title: String? = nil, compact: Bool = false, @ViewBuilder content: () -> Content) {
        self.title = title
        self.compact = compact
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: compact ? 8 : 12) {
            if let title { Text(title).font(.headline) }
            content
        }
        .desktopPanel(verticalPadding: compact ? 12 : DesktopMetrics.cardPadding)
    }
}

struct DesktopStepHeader<Actions: View>: View {
    let title: String
    let subtitle: String
    @ViewBuilder let actions: Actions

    private var heading: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.headline)
            Text(subtitle).foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            HStack(spacing: 16) {
                heading.fixedSize(horizontal: true, vertical: false)
                Spacer(minLength: 16)
                HStack(spacing: 8) { actions }.fixedSize()
            }
            VStack(alignment: .leading, spacing: 12) {
                heading
                HStack(spacing: 8) { actions }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct DesktopGroupBoxStyle: GroupBoxStyle {
    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            configuration.label.font(.headline)
            configuration.content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct WholeRowDisclosureStyle: DisclosureGroupStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Button {
                withAnimation(reduceMotion ? nil : .easeInOut(duration: 0.18)) {
                    configuration.isExpanded.toggle()
                }
            } label: {
                HStack(spacing: 8) {
                    configuration.label
                    Spacer(minLength: 8)
                    Image(systemName: "chevron.right")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .rotationEffect(.degrees(configuration.isExpanded ? 90 : 0))
                }
                .frame(maxWidth: .infinity, minHeight: 30, alignment: .leading)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityValue(configuration.isExpanded ? L("已展开") : L("已收起"))
            if configuration.isExpanded { configuration.content }
        }
    }
}

struct DetailSheet<Content: View>: View {
    let title: String
    let content: Content
    @Environment(\.dismiss) private var dismiss

    init(_ title: String, @ViewBuilder content: () -> Content) {
        self.title = title
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title).font(.headline)
                Spacer()
                Button(L("完成")) { dismiss() }.keyboardShortcut(.defaultAction)
            }.padding(20)
            Divider()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) { content }
                    .frame(maxWidth: .infinity, alignment: .leading).padding(20)
            }
        }
        .frame(width: 560, height: 480)
        .disclosureGroupStyle(WholeRowDisclosureStyle())
        .toggleStyle(.switch)
    }
}

extension View {
    func desktopPanel(verticalPadding: CGFloat = DesktopMetrics.cardPadding) -> some View {
        padding(.horizontal, DesktopMetrics.cardPadding)
            .padding(.vertical, verticalPadding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(DesktopAppearance.contentBackground)
            .clipShape(RoundedRectangle(cornerRadius: DesktopMetrics.cardRadius, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: DesktopMetrics.cardRadius, style: .continuous)
                    .stroke(Color(nsColor: .separatorColor).opacity(0.7), lineWidth: 1)
            }
    }
}
