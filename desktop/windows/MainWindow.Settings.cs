using static SmartSearch.Desktop.Localization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Media.Imaging;
using Windows.System;

namespace SmartSearch.Desktop;

public sealed partial class MainWindow
{
    private UIElement BuildSettingsPage()
    {
        var panel = PagePanel();
        var identity = new Grid { ColumnSpacing = 16 };
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        identity.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        identity.Children.Add(new Image { Source = new BitmapImage(new Uri("ms-appx:///Assets/smart-search.png")), Width = 48, Height = 48 });
        var product = new StackPanel { Spacing = 4, VerticalAlignment = VerticalAlignment.Center };
        product.Children.Add(SectionHeading("Smart Search"));
        product.Children.Add(Secondary(L("版本 {0}", Text(_state, "version", L("未连接")))));
        product.Children.Add(Secondary("konbakuyomu/smartsearch"));
        Grid.SetColumn(product, 1);
        identity.Children.Add(product);
        var project = new HyperlinkButton { Content = "GitHub", NavigateUri = new Uri("https://github.com/konbakuyomu/smartsearch"), VerticalAlignment = VerticalAlignment.Center };
        Grid.SetColumn(project, 2);
        identity.Children.Add(project);
        panel.Children.Add(Card(identity));

        var theme = new ComboBox { MinWidth = 144 };
        foreach (var label in new[] { L("跟随系统"), L("浅色"), L("深色") }) theme.Items.Add(label);
        theme.SelectedIndex = (ReadSetting("theme") ?? "auto") switch { "light" => 1, "dark" => 2, _ => 0 };
        theme.SelectionChanged += (_, _) =>
        {
            var value = theme.SelectedIndex switch { 1 => "light", 2 => "dark", _ => "auto" };
            SaveSetting("theme", value);
            ApplyTheme(value);
        };
        var preferences = new StackPanel { Spacing = 8 };
        preferences.Children.Add(SettingRow(L("界面语言"), string.Empty, BuildLanguagePicker()));
        preferences.Children.Add(Divider());
        preferences.Children.Add(SettingRow(L("外观"), string.Empty, theme));
        preferences.Children.Add(Divider());
        var directoryActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        directoryActions.Children.Add(ActionButton(L("选择配置目录…"), SelectConfigDirectoryAsync, operationKey: "profile", busyText: L("切换中…")));
        if (!Bool(_state, "is_default_config_dir")) directoryActions.Children.Add(ActionButton(L("恢复默认配置目录"), RestoreDefaultConfigDirectoryAsync,
            operationKey: "profile", busyText: L("切换中…"),
            enabled: () => Text(_state, "default_config_dir").Length > 0 && !Bool(_state, "is_default_config_dir")));
        preferences.Children.Add(SettingRow(L("当前配置目录"), Text(_state, "config_dir", Text(_state, "config_path", L("未连接"))),
            directoryActions));
        panel.Children.Add(SettingsSection(L("通用"), L("管理语言、外观和配置目录。"), Card(preferences)));

        _autoUpdateSwitch = CompactSwitch(L("自动检查更新"), Bool(_updates, "auto_check", true));
        _autoUpdateSwitch.Toggled += async (_, _) =>
        {
            if (!_settingAutoUpdate) await UpdateRequestAsync("updates.auto", new { enabled = _autoUpdateSwitch.IsOn });
        };
        _appUpdateSummary = Body(string.Empty);
        _downloadProgress = new ProgressBar { Minimum = 0, Maximum = 100, Visibility = Visibility.Collapsed };
        _appCancelButton = ActionButton(L("取消"), () => { _appDownloadCancellation?.Cancel(); return Task.CompletedTask; }, operationKey: "updates-cancel");
        var updates = new StackPanel { Spacing = 12 };
        updates.Children.Add(SettingRow(L("自动检查更新"), L("发现新版时提醒我"), _autoUpdateSwitch));
        updates.Children.Add(_appUpdateSummary);
        updates.Children.Add(_downloadProgress);
        updates.Children.Add(ActionRow(ActionButton(L("检查更新"), AppUpdateActionAsync, primary: true,
            operationKey: "app-update", busyText: L("处理中…"), label: AppUpdateActionLabel), _appCancelButton));
        panel.Children.Add(SettingsSection(L("App 更新"), string.Empty, updates));
        RenderUpdateState();
        return Scroll(panel);
    }

    private ComboBox BuildLanguagePicker()
    {
        var language = new ComboBox { MinWidth = 144,
            IsEnabled = !_operations.IsBusy("language") && !EnvironmentBusy && Text(Property(_updates, "cli_update"), "status") != "running" };
        foreach (var label in new[] { L("跟随系统"), L("简体中文"), "English" }) language.Items.Add(label);
        language.SelectedIndex = Localization.Preference switch { "zh" => 1, "en" => 2, _ => 0 };
        language.SelectionChanged += async (_, _) =>
        {
            if (!_operations.Begin("language")) return;
            language.IsEnabled = false;
            try
            {
                var preference = language.SelectedIndex switch { 1 => "zh", 2 => "en", _ => "auto" };
                var previous = Localization.Preference;
                Localization.Preference = preference;
                if (_backend.IsConnected)
                {
                    var state = await RequestAsync("language.set", new { lang = Localization.Language }, L("无法切换界面语言。"));
                    if (state is null) { Localization.Preference = previous; return; }
                    ApplyState(state.Value);
                }
                ClearNotice();
                if (!SaveSetting("language", preference))
                    ShowNotice(L("语言"), L("本次语言切换已生效，但无法保存；重新打开 App 后可能恢复原选择。"), InfoBarSeverity.Warning);
                ApplyNavigationLanguage();
            }
            finally
            {
                _operations.EndRequest("language");
                RenderCurrentPage();
            }
        };
        return language;
    }

}
