using static SmartSearch.Desktop.Localization;
using System.Globalization;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;
using Windows.System;

namespace SmartSearch.Desktop;

public sealed partial class MainWindow
{
    private const double PageInset = 24;
    private readonly Dictionary<string, double> _splitWidths = [];
    private string _noticeTitle = string.Empty;
    private bool _hasNotice;
    private bool _dialogOpen;
    private bool _navigationArtworkInitialized;

    private static StackPanel PagePanel() => new()
    {
        Spacing = PageInset, HorizontalAlignment = HorizontalAlignment.Left
    };

    private void OnNavigationDisplayModeChanged(NavigationView sender, NavigationViewDisplayModeChangedEventArgs args)
        => UpdateNavigationArtwork();

    private void OnNavigationLoaded(object sender, RoutedEventArgs args)
    {
        if (!_navigationArtworkInitialized)
        {
            RootNavigation.RegisterPropertyChangedCallback(NavigationView.IsPaneOpenProperty, (_, _) => UpdateNavigationArtwork());
            _navigationArtworkInitialized = true;
        }
        UpdateNavigationArtwork();
    }

    private void UpdateNavigationArtwork()
    {
        if (MascotFooter is null || MascotSpacer is null) return;
        var visibility = RootNavigation.DisplayMode == NavigationViewDisplayMode.Expanded && RootNavigation.IsPaneOpen
            ? Visibility.Visible : Visibility.Collapsed;
        MascotFooter.Visibility = MascotSpacer.Visibility = visibility;
        if (visibility == Visibility.Collapsed) ConnectionToolTip.IsOpen = false;
    }

    private ScrollViewer Scroll(UIElement content) => PaneScroll(content, _currentPage);

    private ScrollViewer PaneScroll(UIElement content, string key)
    {
        var scroll = new ScrollViewer
        {
            Content = content, Padding = new Thickness(PageInset),
            HorizontalContentAlignment = HorizontalAlignment.Left,
            VerticalContentAlignment = VerticalAlignment.Top,
            HorizontalScrollMode = ScrollMode.Disabled,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto
        };
        void FitContent()
        {
            if (content is FrameworkElement element && scroll.ActualWidth > 0)
                element.Width = Math.Min(element.MaxWidth, Math.Max(0, scroll.ActualWidth - PageInset * 2));
        }
        scroll.SizeChanged += (_, _) => FitContent();
        scroll.Loaded += (_, _) =>
        {
            FitContent();
            scroll.ChangeView(null, _pageOffsets.GetValueOrDefault(key), null, true);
        };
        scroll.ViewChanged += (_, _) => _pageOffsets[key] = scroll.VerticalOffset;
        return scroll;
    }

    private Grid SplitWorkspace(string key, FrameworkElement leading, FrameworkElement detail,
        double initialWidth, double minimumWidth, double maximumWidth, double detailMinimum = 400)
    {
        const double dividerWidth = 8;
        if (!_splitWidths.ContainsKey(key))
            _splitWidths[key] = double.TryParse(ReadSetting("split:" + key), NumberStyles.Float,
                CultureInfo.InvariantCulture, out var saved) ? Math.Clamp(saved, minimumWidth, maximumWidth) : initialWidth;
        var layout = new Grid();
        layout.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(_splitWidths[key]) });
        layout.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(dividerWidth) });
        layout.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(0) });
        var divider = new Thumb { Style = UiStyle("PaneDividerStyle") };
        AutomationProperties.SetName(divider, L("调整分栏宽度"));
        ToolTipService.SetToolTip(divider, L("拖动调整宽度；方向键微调"));
        layout.Children.Add(leading);
        layout.Children.Add(divider);
        layout.Children.Add(detail);
        var compact = false;
        void Arrange()
        {
            if (layout.ActualWidth <= 0) return;
            compact = layout.ActualWidth < minimumWidth + detailMinimum + dividerWidth;
            layout.ColumnDefinitions[0].Width = compact ? new GridLength(1, GridUnitType.Star) :
                new GridLength(Math.Clamp(_splitWidths[key], minimumWidth,
                    Math.Min(maximumWidth, layout.ActualWidth - detailMinimum - dividerWidth)));
            layout.ColumnDefinitions[1].Width = new GridLength(compact ? 0 : dividerWidth);
            layout.ColumnDefinitions[2].Width = compact ? new GridLength(0) : new GridLength(1, GridUnitType.Star);
            layout.RowDefinitions[0].Height = new GridLength(compact ? 0.36 : 1, GridUnitType.Star);
            layout.RowDefinitions[1].Height = compact ? new GridLength(0.64, GridUnitType.Star) : new GridLength(0);
            Grid.SetColumn(divider, 1);
            Grid.SetColumn(detail, compact ? 0 : 2);
            Grid.SetRow(detail, compact ? 1 : 0);
            divider.Visibility = compact ? Visibility.Collapsed : Visibility.Visible;
        }
        void Resize(double delta)
        {
            if (compact || layout.ActualWidth <= 0) return;
            _splitWidths[key] = Math.Clamp(layout.ColumnDefinitions[0].ActualWidth + delta, minimumWidth,
                Math.Min(maximumWidth, layout.ActualWidth - detailMinimum - dividerWidth));
            Arrange();
        }
        void Persist() => SaveSetting("split:" + key, _splitWidths[key].ToString(CultureInfo.InvariantCulture));
        divider.DragDelta += (_, args) => Resize(args.HorizontalChange);
        divider.DragCompleted += (_, _) => Persist();
        divider.KeyDown += (_, args) =>
        {
            if (args.Key is not (VirtualKey.Left or VirtualKey.Right)) return;
            Resize(args.Key == VirtualKey.Left ? -16 : 16);
            Persist();
            args.Handled = true;
        };
        layout.SizeChanged += (_, _) => Arrange();
        return layout;
    }

    private static Border Divider() => new() { Style = UiStyle("SectionDividerStyle") };

    private static Border WorkspaceFooter(TextBlock summary, FrameworkElement actions)
    {
        var row = new Grid { ColumnSpacing = 24 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        summary.VerticalAlignment = VerticalAlignment.Center;
        Grid.SetColumn(actions, 1);
        row.Children.Add(summary);
        row.Children.Add(actions);
        row.SizeChanged += (_, args) =>
        {
            var stacked = args.NewSize.Width < 640;
            row.RowSpacing = stacked ? 8 : 0;
            Grid.SetColumn(actions, stacked ? 0 : 1);
            Grid.SetRow(actions, stacked ? 1 : 0);
            actions.HorizontalAlignment = stacked ? HorizontalAlignment.Left : HorizontalAlignment.Right;
        };
        return new Border { Style = UiStyle("WorkspaceFooterStyle"), Child = row };
    }

    private static UIElement SettingRow(string title, string description, UIElement control)
    {
        var label = new StackPanel { Spacing = 4, VerticalAlignment = VerticalAlignment.Center };
        label.Children.Add(new TextBlock { Text = title, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap });
        if (description.Length > 0) label.Children.Add(Secondary(description));
        var row = new Grid { ColumnSpacing = 20 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.Children.Add(label);
        row.Children.Add(control);
        if (control is FrameworkElement input)
        {
            Grid.SetColumn(input, 1);
            input.VerticalAlignment = VerticalAlignment.Center;
            AutomationProperties.SetName(input, title);
            row.SizeChanged += (_, args) =>
            {
                var stacked = args.NewSize.Width < 460 && control is not ToggleSwitch;
                row.RowSpacing = stacked ? 8 : 0;
                Grid.SetColumn(input, stacked ? 0 : 1);
                Grid.SetRow(input, stacked ? 1 : 0);
                input.HorizontalAlignment = stacked ? HorizontalAlignment.Left : HorizontalAlignment.Right;
            };
        }
        return row;
    }

    private static ToggleSwitch CompactSwitch(string label, bool value)
    {
        // WinUI reserves a 12 px gap for the On/Off label even when both labels are empty.
        // Cancel that trailing gap so the visible switch meets the card's content edge.
        var toggle = new ToggleSwitch
        {
            IsOn = value, OnContent = string.Empty, OffContent = string.Empty,
            MinWidth = 0, Margin = new Thickness(0, 0, -12, 0)
        };
        AutomationProperties.SetName(toggle, label);
        return toggle;
    }

    private static StackPanel SettingsSection(string title, string subtitle, params UIElement[] content)
    {
        var section = new StackPanel { Spacing = 12 };
        var heading = new StackPanel { Spacing = 4, Children = { SectionHeading(title) } };
        if (subtitle.Length > 0) heading.Children.Add(Secondary(subtitle));
        section.Children.Add(heading);
        foreach (var child in content) section.Children.Add(child);
        return section;
    }

    private Button DetailsButton(string text, Func<Task> action)
    {
        var button = new Button { Content = text, MinHeight = 36, HorizontalAlignment = HorizontalAlignment.Left };
        button.Click += async (_, _) =>
        {
            try { await action(); }
            catch (Exception error) { ShowNotice(L("操作未完成"), SafeMessage(error), InfoBarSeverity.Error); }
        };
        return button;
    }

    private async Task ShowDetailsAsync(string title, UIElement content)
    {
        if (_dialogOpen) return;
        var dialog = new ContentDialog
        {
            XamlRoot = DialogRoot, RequestedTheme = ((FrameworkElement)Content).ActualTheme,
            Title = title, CloseButtonText = L("完成"),
            Content = new ScrollViewer { Content = content, MaxHeight = 540, HorizontalContentAlignment = HorizontalAlignment.Stretch,
                HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled, VerticalScrollBarVisibility = ScrollBarVisibility.Auto }
        };
        _dialogOpen = true;
        try { await dialog.ShowAsync(); }
        finally
        {
            if (dialog.Content is ScrollViewer scroll) scroll.Content = null;
            dialog.Content = null;
            _dialogOpen = false;
        }
    }

    private void OnClearFeedbackClick(object sender, RoutedEventArgs args) => ClearNotice();

    private void ClearNotice()
    {
        FeedbackFlyout.Hide();
        _hasNotice = false;
        _noticeTitle = string.Empty;
        FeedbackTitle.Text = FeedbackMessage.Text = string.Empty;
        FeedbackButton.IsEnabled = false;
    }

    private async void OnRefreshWorkspaceClick(object sender, RoutedEventArgs args)
    {
        await RunOperationAsync(_backend.IsConnected ? "state" : "connect",
            _backend.IsConnected ? () => RefreshStateAsync() : ConnectAsync);
    }

    private void ShowNotice(string title, string message, InfoBarSeverity severity)
    {
        _hasNotice = true;
        _noticeTitle = title;
        FeedbackTitle.Text = title;
        FeedbackMessage.Text = message;
        FeedbackIcon.Symbol = severity is InfoBarSeverity.Error or InfoBarSeverity.Warning ? Symbol.Important : Symbol.Message;
        FeedbackButton.IsEnabled = true;
        if (FeedbackButton.IsLoaded) FeedbackFlyout.ShowAt(FeedbackButton);
        else DispatcherQueue.TryEnqueue(() => { if (_hasNotice && FeedbackButton.IsLoaded) FeedbackFlyout.ShowAt(FeedbackButton); });
    }

    private void UpdateWorkspaceHeader()
    {
        if (WorkspaceTitle is null) return;
        UpdateConnectionStatus();
        WorkspaceTitle.Text = _currentPage switch
        {
            "providers" => L("配置"), "search" => L("测试"),
            "ai" => L("CLI 与 Skills"), "settings" => L("设置"), _ => L("配置")
        };
        FeedbackHeading.Text = L("操作提示");
        ClearFeedbackButton.Content = L("清除提示");
        AutomationProperties.SetName(FeedbackButton, L("操作提示"));
        ToolTipService.SetToolTip(FeedbackButton, L("查看操作提示"));
        RefreshWorkspaceButton.Visibility = _currentPage == "providers" || !_backend.IsConnected ? Visibility.Visible : Visibility.Collapsed;
        AutomationProperties.SetName(RefreshWorkspaceButton, _backend.IsConnected ? L("重新读取配置") : L("重新连接"));
        ToolTipService.SetToolTip(RefreshWorkspaceButton, _backend.IsConnected ? L("重新读取配置") : L("重新连接"));
    }

    private void UpdateConnectionStatus()
    {
        if (_backend is null || ConnectionIndicator is null) return;
        var connected = _backend.IsConnected && _state is not null;
        var label = L("未连接");
        var style = "ConnectionIdleStyle";
        if (_connecting)
        {
            label = L("正在连接");
            style = "ConnectionPendingStyle";
        }
        else if (connected)
        {
            label = L("已连接");
            style = "ConnectionReadyStyle";
        }
        else if (_connectionFailed)
        {
            label = L("后端失联");
            style = "ConnectionFailedStyle";
        }
        ConnectionDot.Style = UiStyle(style);
        AutomationProperties.SetName(ConnectionIndicator, L("后端状态：{0}", label));
        ConnectionToolTip.Content = L("后端状态：{0}", label);
    }

    private void OnConnectionPointerEntered(object sender, Microsoft.UI.Xaml.Input.PointerRoutedEventArgs args)
        => ShowConnectionToolTip();

    private void OnConnectionPointerExited(object sender, Microsoft.UI.Xaml.Input.PointerRoutedEventArgs args)
        => ConnectionToolTip.IsOpen = false;

    private void OnConnectionIndicatorClick(object sender, RoutedEventArgs args)
        => ShowConnectionToolTip();

    private void ShowConnectionToolTip()
    {
        ConnectionToolTip.PlacementTarget = ConnectionIndicator;
        ConnectionToolTip.IsOpen = true;
    }
}
