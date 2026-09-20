using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;

namespace SmartSearch.Desktop;

/// <summary>
/// Every visual decision in one place.
///
/// The pages are built imperatively in C#, so without this the styling ends up as
/// literals scattered across MainWindow.xaml.cs — which is how the app arrived at
/// one colour, zero borders and three font sizes for seven kinds of information.
///
/// Anything that must follow a runtime theme switch is defined as a Style in
/// App.xaml and only looked up here by key: ApplyTheme sets RequestedTheme without
/// rebuilding pages, so a brush resolved in C# would keep the old theme's colour
/// until the user navigated away and back, while a ThemeResource inside a Style
/// updates in place.
///
/// Every lookup falls back to an explicit value. A resource key that a future
/// Windows App SDK renames then costs a little polish instead of throwing.
/// </summary>
internal static class Theme
{
    /// <summary>4pt grid. Use these instead of picking a number per call site.</summary>
    internal const double SpaceXS = 4;
    internal const double SpaceS = 8;
    internal const double SpaceM = 12;
    internal const double SpaceL = 16;
    internal const double SpaceXL = 24;

    /// <summary>Widest comfortable reading column. Pages align left, not centre.</summary>
    internal const double ContentMaxWidth = 1040;

    internal enum StatusKind
    {
        Neutral,
        Ok,
        Warn,
        Bad,
    }

    private static object? Resource(string key)
    {
        var resources = Application.Current?.Resources;
        if (resources is null)
            return null;
        return resources.TryGetValue(key, out var value) ? value : null;
    }

    private static Style? StyleFor(string key) => Resource(key) as Style;

    private static Brush? BrushFor(string key) => Resource(key) as Brush;

    private static TextBlock Text(string text, string styleKey, double fallbackSize)
    {
        var block = new TextBlock { Text = text, TextWrapping = TextWrapping.Wrap };
        var style = StyleFor(styleKey);
        if (style is not null)
            block.Style = style;
        else
            block.FontSize = fallbackSize;
        return block;
    }

    // ---- type scale -----------------------------------------------------
    // Built-in WinUI text styles carry both the size and the correct theme-aware
    // foreground, so the scale and the secondary-text colour come from one place.

    /// <summary>Page heading, once per page.</summary>
    internal static TextBlock PageTitle(string text) => Text(text, "TitleTextBlockStyle", 28);

    /// <summary>Heading for a group of cards.</summary>
    internal static TextBlock SectionTitle(string text) => Text(text, "SubtitleTextBlockStyle", 20);

    /// <summary>Heading inside a card; distinct from body without shouting.</summary>
    internal static TextBlock CardTitle(string text) => Text(text, "BodyStrongTextBlockStyle", 16);

    /// <summary>Ordinary prose.</summary>
    internal static TextBlock Body(string text) => Text(text, "BodyTextBlockStyle", 14);

    /// <summary>Explanations and provenance. Replaces Opacity = 0.75, which greys
    /// the glyphs instead of establishing a hierarchy.</summary>
    internal static TextBlock Secondary(string text) => Text(text, "SecondaryTextStyle", 14);

    /// <summary>Smallest tier: caveats, timestamps, counts.</summary>
    internal static TextBlock Hint(string text) => Text(text, "HintTextStyle", 12);

    /// <summary>Keys, URLs, paths, identifiers. A masked key in a proportional
    /// font renders its asterisks at uneven widths and reads as noise.</summary>
    internal static TextBlock Mono(string text) => Text(text, "MonoTextStyle", 14);

    /// <summary>Monospace at caption size, for provenance lines carrying a value.</summary>
    internal static TextBlock MonoHint(string text) => Text(text, "MonoCaptionTextStyle", 12);

    // ---- containers -----------------------------------------------------

    /// <summary>Evenly spaced vertical stack on the 4pt grid.</summary>
    internal static StackPanel Stack(double spacing, params UIElement?[] children)
    {
        var stack = new StackPanel { Spacing = spacing };
        foreach (var child in children)
        {
            if (child is not null)
                stack.Children.Add(child);
        }
        return stack;
    }

    /// <summary>Horizontal row, vertically centred.</summary>
    internal static StackPanel Row(double spacing, params UIElement?[] children)
    {
        var stack = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            Spacing = spacing,
            VerticalAlignment = VerticalAlignment.Center,
        };
        foreach (var child in children)
        {
            if (child is not null)
                stack.Children.Add(child);
        }
        return stack;
    }

    /// <summary>
    /// Wrap content in a card so it sits on a surface instead of directly on the
    /// window background. This is the app's only figure/ground separation.
    /// </summary>
    internal static Border Card(params UIElement?[] children)
    {
        var present = new List<UIElement>();
        foreach (var child in children)
        {
            if (child is not null)
                present.Add(child);
        }

        UIElement content = present.Count == 1 ? present[0] : Stack(SpaceS, present.ToArray());
        var border = new Border { Child = content };
        var style = StyleFor("SectionCardStyle");
        if (style is not null)
        {
            border.Style = style;
            return border;
        }
        border.BorderThickness = new Thickness(1);
        border.CornerRadius = new CornerRadius(8);
        border.Padding = new Thickness(SpaceL);
        border.HorizontalAlignment = HorizontalAlignment.Stretch;
        return border;
    }

    // ---- status ---------------------------------------------------------

    /// <summary>
    /// Map a backend status value onto one of four tints. Unknown values stay
    /// neutral rather than guessing at severity.
    /// </summary>
    internal static StatusKind KindOf(string? status) => (status ?? string.Empty).Trim().ToLowerInvariant() switch
    {
        "ok" or "finished" or "completed" or "up_to_date" or "closed" => StatusKind.Ok,
        "failed" or "error" or "auth_error" or "config_error" or "parameter_error"
            or "provider_error" or "runtime_error" or "parse_error" or "network_error" => StatusKind.Bad,
        "cooldown" or "timeout" or "warning" or "rate_limited" or "stale" or "interrupted"
            or "cancelled" or "cancelling" or "extra_files" or "configured" => StatusKind.Warn,
        _ => StatusKind.Neutral,
    };

    /// <summary>
    /// A status badge. One shape for every status in the app, so severity reads at
    /// a glance instead of being buried in a sentence.
    /// </summary>
    internal static Border Pill(string text, StatusKind kind)
    {
        var suffix = kind switch
        {
            StatusKind.Ok => "Ok",
            StatusKind.Warn => "Warn",
            StatusKind.Bad => "Bad",
            _ => "Neutral",
        };

        var label = new TextBlock { Text = text };
        var textStyle = StyleFor("StatusPillTextStyle");
        if (textStyle is not null)
            label.Style = textStyle;
        else
            label.FontSize = 12;
        var foreground = BrushFor("Status" + suffix + "Foreground");
        if (foreground is not null)
            label.Foreground = foreground;

        var border = new Border { Child = label };
        var style = StyleFor("StatusPillStyle");
        if (style is not null)
        {
            border.Style = style;
        }
        else
        {
            border.CornerRadius = new CornerRadius(10);
            border.Padding = new Thickness(SpaceS, 1, SpaceS, 2);
            border.VerticalAlignment = VerticalAlignment.Center;
            border.HorizontalAlignment = HorizontalAlignment.Left;
        }
        var background = BrushFor("Status" + suffix + "Background");
        if (background is not null)
            border.Background = background;
        return border;
    }

    /// <summary>Badge whose tint is derived from the status value itself.</summary>
    internal static Border PillFor(string text, string? status) => Pill(text, KindOf(status));

    /// <summary>The spinner shown next to a control while an operation is in flight.</summary>
    internal static ProgressRing Spinner(double size = 16) => new()
    {
        IsActive = true,
        Width = size,
        Height = size,
        VerticalAlignment = VerticalAlignment.Center,
    };
}
