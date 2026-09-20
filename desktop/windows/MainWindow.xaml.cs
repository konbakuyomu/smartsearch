using System.Runtime.InteropServices;
using System.Text.Json;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Input;
using Microsoft.UI.Xaml.Navigation;
using WinRT.Interop;
using Windows.ApplicationModel.DataTransfer;
using Windows.Storage;
using Windows.Storage.Pickers;
using Windows.System;

namespace SmartSearch.Desktop;

public sealed partial class MainWindow : Window
{
    private const int SwHide = 0;
    private const int SwRestore = 9;

    private readonly BackendClient _backend;
    private readonly Microsoft.UI.Dispatching.DispatcherQueueTimer _activityTimer;
    private readonly NativeTray _tray;
    private static Dictionary<string, string> _statusLabels = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, FieldEditor> _fieldEditors = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Control> _commandControls = new(StringComparer.Ordinal);
    private readonly List<CommandArgument> _commandArguments = [];
    private readonly HashSet<string> _ownedRuns = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _ownedRunStatus = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _ownedRunKinds = new(StringComparer.Ordinal);
    // provider.test is fire-and-forget: the call returns a run_id in milliseconds
    // while the probe itself takes up to 20 seconds. Without this the card shows
    // nothing at all for that whole window.
    private readonly Dictionary<string, string> _runProviders = new(StringComparer.Ordinal);
    private readonly HashSet<string> _testingProviders = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, JsonElement> _ownedRunResults = new(StringComparer.Ordinal);
    private readonly List<string> _extraActivityDirectories = [];
    private readonly Dictionary<string, string> _preferences = new(StringComparer.Ordinal);
    private JsonElement? _state;
    private AppWindow? _appWindow;
    private nint _windowHandle;
    private string _currentPage = "overview";
    private bool _started;
    private bool _activityRefreshing;
    private bool _settingActivityEnabled;
    private bool _allowClose;
    private bool _shuttingDown;
    private StackPanel? _activityRows;
    private ToggleSwitch? _activityEnabledSwitch;
    private StackPanel? _skillRows;
    private TextBlock? _cliSummary;
    private ComboBox? _commandPicker;
    private StackPanel? _commandFieldPanel;
    private TextBox? _resultText;
    private TextBox? _rawResult;
    private StackPanel? _sourceRows;
    private string _lastResultExport = string.Empty;
    private string? _selectedCommandId;
    private string? _selectedResultRunId;

    public MainWindow()
    {
        InitializeComponent();
        var backendLaunch = ReadBackendLaunch();
        _backend = new BackendClient(backendLaunch.Path, backendLaunch.Arguments);
        _backend.EventReceived += OnBackendEvent;
        _backend.Disconnected += OnBackendDisconnected;
        _activityTimer = DispatcherQueue.CreateTimer();
        _activityTimer.Interval = TimeSpan.FromSeconds(2);
        _activityTimer.Tick += async (_, _) => await RefreshActivityAsync(silent: true);
        LoadLocalPreferences();
        InitializeAppWindow();
        _tray = new NativeTray(_windowHandle, ShowMainWindow);
        Activated += OnWindowActivated;
        ApplyTheme(ReadSetting("theme") ?? "auto");
    }

    private void InitializeAppWindow()
    {
        _windowHandle = WindowNative.GetWindowHandle(this);
        _appWindow = AppWindow.GetFromWindowId(Microsoft.UI.Win32Interop.GetWindowIdFromWindow(_windowHandle));
        _appWindow.Closing += OnAppWindowClosing;
        _appWindow.Title = "Smart Search";
        _appWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "Assets", "smart-search.ico"));
    }

    private async void OnWindowActivated(object sender, WindowActivatedEventArgs args)
    {
        if (_started)
            return;
        _started = true;
        await ConnectAsync();
    }

    private async Task ConnectAsync()
    {
        ShowNotice("正在连接", "正在连接随 App 提供的本地后端。不会发起服务商请求。", InfoBarSeverity.Informational);
        try
        {
            var state = await _backend.StartAsync(configDirectory: null, CancellationToken.None);
            ApplyState(state);
            _activityTimer.Start();
            ShowNotice("已连接", "已读取本机配置状态。服务商验证仍需要你主动点击测试。", InfoBarSeverity.Success);
        }
        catch (Exception error)
        {
            ShowNotice("后端不可用", SafeMessage(error), InfoBarSeverity.Error);
        }
        RenderCurrentPage();
    }

    private async Task RefreshStateAsync(bool preserveDraft = false)
    {
        var draft = preserveDraft ? CaptureDraft() : null;
        var result = await RequestAsync("get_state", new { }, "无法刷新本机状态。");
        if (result is null)
            return;
        ApplyState(result.Value);
        RenderCurrentPage(draft);
    }

    private async Task<JsonElement?> RequestAsync(string method, object parameters, string failure)
    {
        try
        {
            return await _backend.CallAsync(method, parameters, CancellationToken.None);
        }
        catch (Exception error)
        {
            ShowNotice(failure, SafeMessage(error), InfoBarSeverity.Error);
            return null;
        }
    }

    private void ApplyState(JsonElement candidate)
    {
        var state = candidate.TryGetProperty("status", out var status) && status.ValueKind == JsonValueKind.Object
            ? status
            : candidate;
        if (state.ValueKind != JsonValueKind.Object)
            return;
        _state = state.Clone();
        CacheStatusLabels(_state.Value);
    }

    /// <summary>
    /// Keep the backend's status vocabulary so raw values such as `live`,
    /// `up_to_date` or `completed` never reach a Chinese window. Both frontends
    /// read the same table, so the wording only has to be maintained once.
    /// </summary>
    private static void CacheStatusLabels(JsonElement state)
    {
        var table = Property(Property(state, "metadata"), "status_labels");
        if (table.ValueKind != JsonValueKind.Object)
            return;
        var labels = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var entry in table.EnumerateObject())
        {
            var label = Text(entry.Value, "zh");
            if (!string.IsNullOrWhiteSpace(label))
                labels[entry.Name] = label;
        }
        if (labels.Count > 0)
            _statusLabels = labels;
    }

    /// <summary>Backend wording for a status value, or the value itself.</summary>
    private static string BackendStatusLabel(string status)
        => !string.IsNullOrWhiteSpace(status) && _statusLabels.TryGetValue(status.Trim(), out var label)
            ? label
            : status;

    private void OnNavigationSelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItem is NavigationViewItem item && item.Tag is string tag)
        {
            _currentPage = tag;
            RenderCurrentPage();
        }
    }

    private void RenderCurrentPage(Dictionary<string, FieldDraft>? preservedDraft = null)
    {
        if (_currentPage == "search" && _commandPicker?.SelectedItem is CommandOption selected)
            _selectedCommandId = selected.Id;
        ContentFrame.Content = _currentPage switch
        {
            "providers" => BuildProvidersPage(preservedDraft),
            "search" => BuildSearchPage(),
            "activity" => BuildActivityPage(),
            "ai" => BuildAiPage(),
            "settings" => BuildSettingsPage(),
            _ => BuildOverviewPage()
        };
    }

    private UIElement BuildOverviewPage()
    {
        var panel = PagePanel();
        panel.Children.Add(PageTitle("概览"));
        if (_state is not { } state)
        {
            panel.Children.Add(Body("后端尚未连接。请确认安装包中包含 backend\\smart-search.exe；开发调试可设置 SMART_SEARCH_BACKEND_PATH。"));
            panel.Children.Add(ActionButton("重新连接", ConnectAsync, primary: true));
            return Scroll(panel);
        }

        var minimum = Property(state, "minimum_profile");
        var profileOk = Bool(minimum, "ok");
        panel.Children.Add(Body(profileOk
            ? "当前配置已经满足最小使用条件。是否最近成功由服务商状态中的检查时间决定。"
            : "还缺少最小配置。先完成主搜索、文档检索或网页抓取中需要的一项服务商配置。"));
        panel.Children.Add(KeyValue("配置目录", Text(state, "config_dir", Text(state, "config_path", "未返回"))));
        panel.Children.Add(KeyValue("最小配置", profileOk ? "已满足" : MissingText(minimum), mono: false));
        var capabilityRows = CapabilityRows(state).ToList();
        if (capabilityRows.Count > 0)
            panel.Children.Add(Section("当前能力", capabilityRows));
        panel.Children.Add(Section("接下来做什么", profileOk
            ? [Body("你可以直接在“搜索与研究”中选择现有命令。服务商测试仍是手动操作。")]
            : [Body("先进入“服务商”，填写必要字段。密钥留空会保留原值，清除需要勾选明确选项。"), ActionButton("去配置服务商", () => NavigateToAsync("providers"), primary: true)]));
        panel.Children.Add(ActionButton("刷新本机状态", () => RefreshStateAsync()));
        panel.Children.Add(new Expander
        {
            Header = "高级状态",
            Content = KeyValue("配置 revision", Text(state, "revision", "未返回"))
        });
        return Scroll(panel);
    }

    private UIElement BuildProvidersPage(Dictionary<string, FieldDraft>? preservedDraft)
    {
        _fieldEditors.Clear();
        var panel = PagePanel();
        panel.Children.Add(PageTitle("服务商与高级配置"));
        panel.Children.Add(Body("先编辑草稿，再测试草稿，最后保存。空的密钥输入始终表示保留；只有勾选清除才会删除保存值。环境变量来源只读。"));
        if (_state is not { } state)
        {
            panel.Children.Add(OfflineHint());
            return Scroll(panel);
        }

        var fields = Items(Property(Property(state, "metadata"), "fields")).ToList();
        if (fields.Count == 0)
        {
            panel.Children.Add(Body("后端没有返回可编辑字段。请刷新状态或检查协议版本。"));
            return Scroll(panel);
        }

        var providerGroups = fields
            .Where(field => !IsAdvanced(field) && !string.IsNullOrWhiteSpace(Text(field, "provider")))
            .GroupBy(field => Text(field, "provider"))
            .OrderBy(group => group.Key, StringComparer.OrdinalIgnoreCase)
            .ToList();
        foreach (var group in providerGroups)
        {
            var content = new StackPanel { Spacing = 12 };
            foreach (var field in group)
                content.Children.Add(BuildFieldEditor(field, preservedDraft));
            content.Children.Add(BuildProviderStatus(state, group.Key));
            content.Children.Add(ActionButton("测试当前草稿", () => TestProviderDraftAsync(group.Key), primary: true));
            panel.Children.Add(new Expander
            {
                Header = string.IsNullOrWhiteSpace(group.Key) ? "服务商" : group.Key,
                IsExpanded = true,
                Content = content,
                HorizontalAlignment = HorizontalAlignment.Stretch,
                HorizontalContentAlignment = HorizontalAlignment.Stretch
            });
        }

        var advanced = fields.Where(field => IsAdvanced(field) || string.IsNullOrWhiteSpace(Text(field, "provider"))).ToList();
        if (advanced.Count > 0)
        {
            var content = new StackPanel { Spacing = 12 };
            foreach (var field in advanced)
                content.Children.Add(BuildFieldEditor(field, preservedDraft));
            panel.Children.Add(new Expander
            {
                Header = "高级与路由设置",
                Content = content,
                HorizontalAlignment = HorizontalAlignment.Stretch,
                HorizontalContentAlignment = HorizontalAlignment.Stretch
            });
        }

        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(ActionButton("预览保存", PreviewDraftAsync));
        actions.Children.Add(ActionButton("保存更改", SaveDraftAsync, primary: true));
        actions.Children.Add(ActionButton("刷新并保留草稿", () => RefreshStateAsync(preserveDraft: true)));
        panel.Children.Add(actions);
        return Scroll(panel);
    }

    private UIElement BuildFieldEditor(JsonElement field, Dictionary<string, FieldDraft>? preservedDraft)
    {
        var key = Text(field, "key");
        var source = Text(Property(_state!.Value, "sources"), key, "default");
        var value = DisplayValue(Property(_state!.Value, "values"), key);
        var initialValue = string.IsNullOrWhiteSpace(value) ? Text(field, "default") : value;
        var isSecret = IsSecret(field);
        var isLocked = source.Equals("environment", StringComparison.OrdinalIgnoreCase);
        var box = new StackPanel { Spacing = Theme.SpaceXS };
        box.Children.Add(Theme.CardTitle(Label(field)));
        var help = Text(field, "help_zh", Text(field, "help_en"));
        if (!string.IsNullOrWhiteSpace(help))
            box.Children.Add(Theme.Secondary(help));
        var saved = DisplayValue(Property(_state!.Value, "saved_values"), key);
        // Provenance is a value plus its source, so it reads as data with a
        // label rather than as another sentence competing with the help text.
        box.Children.Add(Theme.Row(Theme.SpaceXS,
            Theme.Hint("有效值"),
            Theme.MonoHint(string.IsNullOrWhiteSpace(initialValue) ? "未设置" : initialValue),
            Theme.Pill(SourceLabel(source), Theme.StatusKind.Neutral)));
        box.Children.Add(Theme.Row(Theme.SpaceXS,
            Theme.Hint("保存值"),
            Theme.MonoHint(string.IsNullOrWhiteSpace(saved) ? "未设置" : saved)));

        var input = CreateFieldInput(field, isSecret, initialValue, isLocked);
        box.Children.Add(input);
        CheckBox? clear = null;
        if (!isLocked)
        {
            clear = new CheckBox
            {
                Content = isSecret ? "清除已保存的密钥" : "移除此保存值，恢复默认/上层来源",
                IsEnabled = true
            };
            box.Children.Add(clear);
        }
        else
        {
            box.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Pill("环境变量接管", Theme.StatusKind.Warn),
                Theme.Hint("App 不会覆盖或清除它")));
        }

        var editor = new FieldEditor(field.Clone(), input, clear, ReadControl(input), isSecret, isLocked);
        _fieldEditors[key] = editor;
        if (preservedDraft is not null && preservedDraft.TryGetValue(key, out var draft))
            RestoreDraft(editor, draft);
        return box;
    }

    private static IEnumerable<UIElement> CapabilityRows(JsonElement state)
    {
        var capabilities = Property(state, "capability_status");
        if (capabilities.ValueKind != JsonValueKind.Object)
            yield break;
        foreach (var capability in capabilities.EnumerateObject().OrderBy(item => item.Name, StringComparer.OrdinalIgnoreCase))
        {
            var configured = Items(capability.Value, "configured")
                .Where(item => item.ValueKind == JsonValueKind.String)
                .Select(item => item.GetString())
                .Where(item => !string.IsNullOrWhiteSpace(item))
                .ToArray();
            var available = Bool(capability.Value, "ok");
            var status = available ? "可用" : configured.Length > 0 ? "已配置但当前能力未满足" : "未配置";
            var experimental = Bool(capability.Value, "experimental") ? "（实验性）" : string.Empty;
            yield return Body($"{CapabilityLabel(capability.Name)}{experimental}：{status}；已配置服务商：{(configured.Length == 0 ? "无" : string.Join("、", configured))}");
        }
    }

    /// <summary>Whether a provider.test run for this provider is still in flight.</summary>
    private bool HasRunningTestFor(string provider)
    {
        foreach (var entry in _runProviders)
        {
            if (!entry.Value.Equals(provider, StringComparison.OrdinalIgnoreCase))
                continue;
            if (!_ownedRunStatus.TryGetValue(entry.Key, out var status) || !IsTerminal(status))
                return true;
        }
        return false;
    }

    private UIElement BuildProviderStatus(JsonElement state, string provider)
    {
        var panel = new StackPanel { Spacing = Theme.SpaceXS };
        // Self-healing: a dropped run event must not strand a card on "testing".
        if (_testingProviders.Contains(provider) && !HasRunningTestFor(provider))
            _testingProviders.Remove(provider);
        if (_testingProviders.Contains(provider))
        {
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Spinner(),
                Theme.Pill("测试中", Theme.StatusKind.Neutral),
                Theme.Hint("最长等待 20 秒")));
        }
        var health = Property(state, "provider_health");
        var healthRow = Items(health, "providers").FirstOrDefault(item => Text(item, "provider").Equals(provider, StringComparison.OrdinalIgnoreCase));
        var healthState = Text(healthRow, "state");
        var cooling = healthState.Equals("cooldown", StringComparison.OrdinalIgnoreCase) ||
                      Items(health, "cooldown_providers").Any(item => item.ValueKind == JsonValueKind.String && item.GetString()!.Equals(provider, StringComparison.OrdinalIgnoreCase));
        if (!Bool(health, "enabled", true))
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Pill("健康记录未启用", Theme.StatusKind.Neutral),
                Theme.Hint("不能据此判断服务商是否可用")));
        else if (cooling)
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Pill($"冷却中 · 剩余 {CooldownText(healthRow)}", Theme.StatusKind.Warn),
                Theme.Hint("这是失败保护，不代表最近成功")));
        else if (healthState.Equals("closed", StringComparison.OrdinalIgnoreCase))
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Pill("未冷却", Theme.StatusKind.Ok),
                Theme.Hint("不代表最近探测成功")));
        else if (!string.IsNullOrWhiteSpace(healthState))
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.PillFor(BackendStatusLabel(healthState), healthState),
                Theme.Hint("不等同于一次草稿或已保存凭据测试")));
        else
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Pill("无健康记录", Theme.StatusKind.Neutral),
                Theme.Hint("不代表最近探测成功")));

        var check = Property(Property(state, "provider_checks"), provider);
        if (check.ValueKind != JsonValueKind.Object)
        {
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Hint("最近测试"),
                Theme.Pill("未测试", Theme.StatusKind.Neutral)));
            return panel;
        }
        var status = Text(check, "status", "unknown");
        var scope = Text(check, "scope");
        panel.Children.Add(Theme.Row(Theme.SpaceS,
            Theme.Hint("最近测试"),
            Theme.PillFor(ProviderCheckLabel(status), status),
            Theme.Hint(TimestampOrText(check, "checked_at"))));
        var probe = Text(check, "probe");
        if (!string.IsNullOrWhiteSpace(probe))
            panel.Children.Add(Theme.Row(Theme.SpaceS,
                Theme.Hint("检查方式"),
                Theme.Hint(BackendStatusLabel(probe))));
        if (!scope.Equals("draft", StringComparison.OrdinalIgnoreCase) && !string.IsNullOrWhiteSpace(scope))
            panel.Children.Add(Theme.Hint($"测试范围：{BackendStatusLabel(scope)}"));
        var message = Text(check, "message");
        if (!string.IsNullOrWhiteSpace(message))
            panel.Children.Add(Theme.Secondary(message));
        return panel;
    }

    private UIElement BuildSearchPage()
    {
        _commandControls.Clear();
        _commandArguments.Clear();
        var panel = PagePanel();
        panel.Children.Add(PageTitle("搜索与研究"));
        panel.Children.Add(Body("选择后端公布的完整命令目录。常用操作使用原生表单；高级 JSON 仅用于核对或复制，不是结果主视图。"));
        if (_state is not { } state)
        {
            panel.Children.Add(OfflineHint());
            return Scroll(panel);
        }

        _commandPicker = new ComboBox { Header = "工具", MinWidth = 360, HorizontalAlignment = HorizontalAlignment.Stretch };
        foreach (var command in Items(state, "commands"))
        {
            var id = Text(command, "id");
            if (!string.IsNullOrWhiteSpace(id))
                _commandPicker.Items.Add(new CommandOption(id, Text(command, "label", id), Text(command, "description"), Bool(command, "experimental"), command.Clone()));
        }
        _commandPicker.SelectionChanged += (_, _) => RenderCommandFields();
        panel.Children.Add(_commandPicker);
        _commandFieldPanel = new StackPanel { Spacing = 10 };
        panel.Children.Add(_commandFieldPanel);
        panel.Children.Add(ActionButton("运行", StartSelectedCommandAsync, primary: true));

        panel.Children.Add(WithTopGap(Theme.SectionTitle("结果")));
        _resultText = new TextBox
        {
            IsReadOnly = true,
            TextWrapping = TextWrapping.Wrap,
            AcceptsReturn = true,
            MinHeight = 160,
            PlaceholderText = "运行后会在这里显示可读结果和下一步。"
        };
        panel.Children.Add(_resultText);
        _sourceRows = new StackPanel { Spacing = 4 };
        panel.Children.Add(_sourceRows);
        var resultActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        resultActions.Children.Add(ActionButton("复制结果", CopyResult));
        resultActions.Children.Add(ActionButton("导出结果", ExportResultAsync));
        panel.Children.Add(resultActions);
        _rawResult = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, MinHeight = 120 };
        panel.Children.Add(new Expander { Header = "高级 JSON", Content = _rawResult });
        if (_commandPicker.Items.Count > 0)
        {
            _commandPicker.SelectedItem = _commandPicker.Items.OfType<CommandOption>()
                .FirstOrDefault(command => command.Id == _selectedCommandId) ?? _commandPicker.Items[0];
        }
        if (_selectedResultRunId is not null && _ownedRunResults.TryGetValue(_selectedResultRunId, out var cachedResult))
            RenderResult(cachedResult);
        return Scroll(panel);
    }

    private UIElement BuildActivityPage()
    {
        var panel = PagePanel();
        panel.Children.Add(PageTitle("实时活动"));
        panel.Children.Add(Body("每两秒刷新一次运行记录。只有当前 App 发起的任务会显示取消按钮；终端和 AI 的任务仅观察。没有事件不等于成功。"));
        _activityEnabledSwitch = new ToggleSwitch { Header = "记录活动", IsOn = Bool(Property(_state, "activity"), "enabled", true) };
        _activityEnabledSwitch.Toggled += async (_, _) =>
        {
            if (!_settingActivityEnabled)
                await SetActivityEnabledAsync(_activityEnabledSwitch.IsOn);
        };
        panel.Children.Add(_activityEnabledSwitch);
        var actions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        actions.Children.Add(ActionButton("立即刷新", () => RefreshActivityAsync(silent: false)));
        actions.Children.Add(ActionButton("清除已结束记录", ClearActivityAsync));
        panel.Children.Add(actions);
        _activityRows = new StackPanel { Spacing = 12, Margin = new Thickness(0, 12, 0, 0) };
        panel.Children.Add(_activityRows);
        _ = RefreshActivityAsync(silent: true);
        return Scroll(panel);
    }

    private UIElement BuildAiPage()
    {
        var panel = PagePanel();
        panel.Children.Add(PageTitle("AI 接入"));
        panel.Children.Add(Body("这里显示 App 内置 CLI 与外部同名 CLI 的实际路径和版本。默认不会修改 PATH；启用内置命令会先要求明确确认，若存在冲突则由后端拒绝覆盖。"));
        _cliSummary = Body("正在读取本机 CLI 状态…");
        panel.Children.Add(_cliSummary);
        var cliActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        cliActions.Children.Add(ActionButton("复制内置 CLI 调用", CopyBundledCli));
        cliActions.Children.Add(ActionButton("启用内置命令", EnableBundledCliAsync, primary: true));
        panel.Children.Add(cliActions);
        panel.Children.Add(WithTopGap(Theme.SectionTitle("Skills")));
        _skillRows = new StackPanel { Spacing = 8 };
        panel.Children.Add(_skillRows);
        var skillActions = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        skillActions.Children.Add(ActionButton("检查 Skills 状态", LoadSkillsAsync));
        skillActions.Children.Add(ActionButton("安装/更新选择项", InstallSelectedSkillsAsync, primary: true));
        panel.Children.Add(skillActions);
        _ = LoadCliStatusAsync();
        _ = LoadSkillsAsync();
        return Scroll(panel);
    }

    private UIElement BuildSettingsPage()
    {
        var panel = PagePanel();
        panel.Children.Add(PageTitle("设置与关于"));
        panel.Children.Add(KeyValue("当前配置目录", Text(_state, "config_dir", Text(_state, "config_path", "未连接"))));
        panel.Children.Add(ActionButton("选择配置目录", SelectConfigDirectoryAsync));

        var theme = new ComboBox { Header = "外观", MinWidth = 220 };
        theme.Items.Add("跟随系统");
        theme.Items.Add("浅色");
        theme.Items.Add("深色");
        theme.SelectedIndex = (ReadSetting("theme") ?? "auto") switch { "light" => 1, "dark" => 2, _ => 0 };
        theme.SelectionChanged += (_, _) =>
        {
            var value = theme.SelectedIndex switch { 1 => "light", 2 => "dark", _ => "auto" };
            SaveSetting("theme", value);
            ApplyTheme(value);
        };
        panel.Children.Add(theme);

        panel.Children.Add(WithTopGap(Theme.SectionTitle("附加活动目录")));
        panel.Children.Add(Body("默认观察当前配置目录。只有你选择加入的目录会额外纳入活动列表；App 不扫描整盘或其他用户目录。"));
        var directoryRows = new StackPanel { Spacing = 4 };
        RenderExtraDirectories(directoryRows);
        panel.Children.Add(directoryRows);
        panel.Children.Add(ActionButton("添加活动目录", async () =>
        {
            var folder = await PickFolderAsync();
            if (folder is not null && !_extraActivityDirectories.Contains(folder.Path, StringComparer.OrdinalIgnoreCase))
            {
                _extraActivityDirectories.Add(folder.Path);
                SaveExtraDirectories();
                RenderCurrentPage();
            }
        }));

        panel.Children.Add(WithTopGap(Theme.SectionTitle("版本与更新")));
        panel.Children.Add(KeyValue("App", "Smart Search Desktop / Windows App SDK 2.5.1", mono: false));
        panel.Children.Add(KeyValue("后端版本", Text(_state, "version", "未连接")));
        panel.Children.Add(KeyValue("协议", Text(_state, "protocol_version", "1")));
        panel.Children.Add(KeyValue("后端路径", _backend.BackendPath ?? "未启动"));
        panel.Children.Add(ActionButton("手动检查更新", CheckForUpdateAsync));
        panel.Children.Add(new Expander
        {
            Header = "诊断",
            Content = ActionButton("重置本地服务商健康状态", ResetProvidersAsync)
        });
        return Scroll(panel);
    }

    private void RenderCommandFields()
    {
        if (_commandFieldPanel is null || _commandPicker?.SelectedItem is not CommandOption command)
            return;
        _selectedCommandId = command.Id;
        _commandControls.Clear();
        _commandArguments.Clear();
        _commandFieldPanel.Children.Clear();
        _commandFieldPanel.Children.Add(Body(command.Experimental
            ? $"{command.Description}（实验性：只会在你点击运行后执行。）"
            : command.Description));
        var fields = Items(command.Definition, "fields").ToList();
        foreach (var field in fields.Where(field => !IsCommandAdvanced(field)))
            AddCommandField(field, _commandFieldPanel);
        var advanced = fields.Where(IsCommandAdvanced).ToList();
        if (advanced.Count > 0)
        {
            var advancedPanel = new StackPanel { Spacing = 10 };
            foreach (var field in advanced)
                AddCommandField(field, advancedPanel);
            _commandFieldPanel.Children.Add(new Expander { Header = "高级参数", Content = advancedPanel });
        }
    }

    private void AddCommandField(JsonElement field, Panel target)
    {
        var name = Text(field, "name");
        if (string.IsNullOrWhiteSpace(name))
            return;
        var kind = Text(field, "kind");
        var flags = Items(field, "flags").Select(value => value.ValueKind == JsonValueKind.String ? value.GetString()! : string.Empty).Where(flag => !string.IsNullOrWhiteSpace(flag)).ToList();
        _commandArguments.Add(new CommandArgument(name, flags, kind.Equals("bool", StringComparison.OrdinalIgnoreCase), Bool(field, "multiple"), Bool(field, "required")));
        var group = new StackPanel { Spacing = 4 };
        group.Children.Add(Theme.CardTitle(Text(field, "label", name)));
        var help = Text(field, "help");
        if (!string.IsNullOrWhiteSpace(help))
            group.Children.Add(Theme.Secondary(help));
        var input = CreateCommandInput(field);
        _commandControls[name] = input;
        group.Children.Add(input);
        target.Children.Add(group);
    }

    private async Task StartSelectedCommandAsync()
    {
        if (_commandPicker?.SelectedItem is not CommandOption command)
        {
            ShowNotice("请选择工具", "后端尚未提供命令目录。", InfoBarSeverity.Warning);
            return;
        }
        foreach (var argument in _commandArguments.Where(argument => argument.Required && !argument.IsBoolean))
        {
            if (string.IsNullOrWhiteSpace(ReadControl(argument.Name).Text))
            {
                ShowNotice("缺少必要参数", $"请填写“{argument.Name}”。", InfoBarSeverity.Warning);
                return;
            }
        }
        var arguments = ProtocolArguments.Build(_commandArguments, ReadControl).ToArray();
        var result = await RequestAsync("run.start", new { command = command.Id, arguments }, "无法启动该任务。");
        if (result is null)
            return;
        var runId = Text(result.Value, "run_id");
        RegisterOwnedRun(runId, command.Id);
        _selectedResultRunId = runId;
        _lastResultExport = string.Empty;
        if (_resultText is not null)
            _resultText.Text = "任务正在运行。完成后会显示可读结果和来源。";
        if (_rawResult is not null)
            _rawResult.Text = string.Empty;
        _sourceRows?.Children.Clear();
        ShowNotice("任务已开始", "运行状态会出现在“活动”页面；任务完成后可读结果会显示在本页。", InfoBarSeverity.Success);
    }

    private async Task PreviewDraftAsync()
    {
        var draft = CollectDraft();
        var result = await RequestAsync("config.preview", new { set = draft.Set, unset = draft.Unset }, "无法预览草稿。");
        if (result is null)
            return;
        var ready = Bool(result.Value, "minimum_profile_ok");
        ShowNotice("草稿预览", ready ? "草稿满足最小配置条件。可以先测试，再保存。" : $"草稿仍缺少：{MissingText(result.Value)}", ready ? InfoBarSeverity.Success : InfoBarSeverity.Warning);
    }

    private async Task SaveDraftAsync()
    {
        if (_state is not { } state)
            return;
        var draft = CollectDraft();
        if (draft.Set.Count == 0 && draft.Unset.Count == 0)
        {
            ShowNotice("没有更改", "尚未输入新值或选择清除。", InfoBarSeverity.Informational);
            return;
        }
        var result = await RequestAsync("config.apply", new { set = draft.Set, unset = draft.Unset, revision = Text(state, "revision") }, "无法保存配置。");
        if (result is null)
            return;
        if (!Bool(result.Value, "ok"))
        {
            var errorType = Text(result.Value, "error_type", "unknown_error");
            if (errorType.Contains("conflict", StringComparison.OrdinalIgnoreCase))
                ShowNotice("配置已变更", "检测到其他进程更新。你的草稿仍保留；点击“刷新并保留草稿”后重新确认。", InfoBarSeverity.Warning);
            else
                ShowNotice("未保存", $"{Text(result.Value, "error", $"后端拒绝了本次配置（{errorType}）。")} 原配置未被 App 覆盖。", InfoBarSeverity.Error);
            return;
        }
        await RefreshStateAsync();
        ShowNotice("已保存", "新配置会用于下一次任务；已经开始的任务继续使用它自己的配置快照。", InfoBarSeverity.Success);
    }

    private async Task TestProviderDraftAsync(string provider)
    {
        var draft = CollectDraft(provider);
        var overrides = draft.Set.ToDictionary(item => item.Key, item => Convert.ToString(item.Value, System.Globalization.CultureInfo.InvariantCulture) ?? string.Empty);
        foreach (var key in draft.Unset)
            overrides[key] = string.Empty;
        var result = await RequestAsync("provider.test", new { provider, overrides }, "无法启动草稿测试。");
        if (result is null)
            return;
        var testRunId = Text(result.Value, "run_id");
        RegisterOwnedRun(testRunId, "provider.test");
        if (!string.IsNullOrWhiteSpace(testRunId))
            _runProviders[testRunId] = provider;
        _testingProviders.Add(provider);
        RenderCurrentPage();
    }

    private async Task RefreshActivityAsync(bool silent)
    {
        if (_activityRefreshing || !_backend.IsConnected)
            return;
        _activityRefreshing = true;
        try
        {
            var result = await _backend.CallAsync("activity.list", new { directories = ActivityDirectories(), limit = 200 }, CancellationToken.None);
            RenderActivity(result);
        }
        catch (Exception error)
        {
            if (!silent)
                ShowNotice("活动记录不可用", SafeMessage(error), InfoBarSeverity.Error);
        }
        finally
        {
            _activityRefreshing = false;
        }
    }

    private void RenderActivity(JsonElement result)
    {
        if (_activityEnabledSwitch is not null)
        {
            _settingActivityEnabled = true;
            _activityEnabledSwitch.IsOn = Bool(result, "enabled", true);
            _settingActivityEnabled = false;
        }
        if (_activityRows is null)
            return;
        var expanded = _activityRows.Children.OfType<Expander>()
            .Where(row => row.IsExpanded).Select(row => row.Tag as string).ToHashSet();
        _activityRows.Children.Clear();
        var errors = Items(result, "errors").ToList();
        if (errors.Count > 0)
            _activityRows.Children.Add(Body("部分活动目录不可读取。请在设置中检查已添加的目录；这不表示没有活动。"));
        var runs = Items(result, "runs").OrderByDescending(run => Number(run, "updated_at")).ToList();
        if (runs.Count == 0)
        {
            _activityRows.Children.Add(Body("目前没有可见记录。旧 CLI、未启用观测或未添加的配置目录不会被伪造为“空闲”。"));
            return;
        }
        foreach (var run in runs)
        {
            var row = BuildActivityRow(run);
            row.IsExpanded = expanded.Contains(Text(run, "run_id"));
            _activityRows.Children.Add(row);
        }
    }

    private Expander BuildActivityRow(JsonElement run)
    {
        var runId = Text(run, "run_id");
        var status = Text(run, "status", "unknown");
        if (_ownedRuns.Contains(runId))
            _ownedRunStatus[runId] = status;
        var summary = new StackPanel { Spacing = 3 };
        summary.Children.Add(Theme.Row(Theme.SpaceS,
            Theme.Hint($"来源 {BackendStatusLabel(Text(run, "origin", "unknown"))}"),
            Theme.Hint($"阶段 {BackendStatusLabel(Text(run, "phase", "等待状态"))}"),
            Theme.Hint($"耗时 {Elapsed(run)}")));
        var provider = Text(run, "provider");
        var model = Text(run, "model");
        if (!string.IsNullOrWhiteSpace(provider) || !string.IsNullOrWhiteSpace(model))
            summary.Children.Add(Body($"服务商：{(string.IsNullOrWhiteSpace(provider) ? "未返回" : provider)}  模型：{(string.IsNullOrWhiteSpace(model) ? "未返回" : model)}"));
        summary.Children.Add(Body($"开始：{Timestamp(run, "started_at")}  配置目录：{Text(run, "config_dir", "未返回")}"));
        if (!string.IsNullOrWhiteSpace(Text(run, "config_revision")))
            summary.Children.Add(Body($"配置版本：{Text(run, "config_revision")}"));
        if (!string.IsNullOrWhiteSpace(Text(run, "error_type")))
            summary.Children.Add(Body($"错误类别：{Text(run, "error_type")}"));
        summary.Children.Add(ActionButton("运行详情", () => ShowActivityDetailsAsync(run)));
        if (_ownedRuns.Contains(runId) && !IsTerminal(status))
            summary.Children.Add(ActionButton("取消此 App 任务", () => CancelOwnedRunAsync(runId)));
        if (_ownedRuns.Contains(runId) && IsTerminal(status))
            summary.Children.Add(ActionButton("查看结果", () => ShowRunResultAsync(runId)));
        var header = Theme.Row(Theme.SpaceS,
            Theme.Mono(Text(run, "command", "任务")),
            Theme.PillFor(StatusLabel(status), status));
        return new Expander
        {
            Tag = runId,
            Header = header,
            Content = summary,
            // Auto width made every row size to its own text, so the list
            // rendered as a staircase of mismatched cards.
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Stretch
        };
    }

    private async Task ShowActivityDetailsAsync(JsonElement run)
    {
        var runId = Text(run, "run_id");
        var configDirectory = Text(run, "config_dir", Text(_state, "config_dir"));
        if (string.IsNullOrWhiteSpace(runId) || string.IsNullOrWhiteSpace(configDirectory))
        {
            ShowNotice("无法读取详情", "该活动记录缺少运行标识或配置目录。", InfoBarSeverity.Warning);
            return;
        }
        var details = await RequestAsync("activity.details", new { run_id = runId, config_dir = configDirectory }, "无法读取活动详情。");
        if (details is null)
            return;
        if (!Bool(details.Value, "ok"))
        {
            ShowNotice("活动详情不可用", Text(details.Value, "error", "后端没有保存这条活动记录。"), InfoBarSeverity.Warning);
            return;
        }

        var content = new StackPanel { Spacing = 8 };
        content.Children.Add(Body("这里只显示本地活动元数据和阶段事件，不包含查询、回答正文、请求头或密钥。"));
        var detailedRun = Property(details.Value, "run");
        content.Children.Add(Body($"状态：{StatusLabel(Text(detailedRun, "status", "unknown"))}  阶段：{Text(detailedRun, "phase", "未返回")}"));
        var detailProvider = Text(detailedRun, "provider");
        var detailModel = Text(detailedRun, "model");
        if (!string.IsNullOrWhiteSpace(detailProvider) || !string.IsNullOrWhiteSpace(detailModel))
            content.Children.Add(Body($"服务商：{(string.IsNullOrWhiteSpace(detailProvider) ? "未返回" : detailProvider)}  模型：{(string.IsNullOrWhiteSpace(detailModel) ? "未返回" : detailModel)}"));
        if (!string.IsNullOrWhiteSpace(Text(detailedRun, "config_revision")))
            content.Children.Add(Body($"配置版本：{Text(detailedRun, "config_revision")}"));
        if (!string.IsNullOrWhiteSpace(Text(details.Value, "note")))
            content.Children.Add(Body(Text(details.Value, "note")));

        content.Children.Add(Theme.CardTitle("阶段事件"));
        var events = Items(details.Value, "events").ToList();
        if (events.Count == 0)
            content.Children.Add(Body("没有可持久读取的事件；当前 App 自有任务仍可保留其内存状态。"));
        foreach (var activityEvent in events)
        {
            var eventProvider = Text(activityEvent, "provider");
            var eventModel = Text(activityEvent, "model");
            var suffix = string.IsNullOrWhiteSpace(eventProvider) && string.IsNullOrWhiteSpace(eventModel)
                ? string.Empty
                : $" · {eventProvider}{(string.IsNullOrWhiteSpace(eventModel) ? string.Empty : $" / {eventModel}")}";
            var error = Text(activityEvent, "error_type");
            content.Children.Add(Body($"{Timestamp(activityEvent, "timestamp")} · {Text(activityEvent, "phase", "等待状态")} · {StatusLabel(Text(activityEvent, "status", "unknown"))}{suffix}{(string.IsNullOrWhiteSpace(error) ? string.Empty : $" · {error}")}"));
        }
        var raw = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, MinHeight = 120, Text = JsonSerializer.Serialize(details.Value, new JsonSerializerOptions { WriteIndented = true }) };
        content.Children.Add(new Expander { Header = "高级 JSON（仅活动元数据）", Content = raw });
        var dialog = new ContentDialog
        {
            XamlRoot = DialogRoot,
            RequestedTheme = ((FrameworkElement)Content).ActualTheme,
            Title = $"运行详情：{Text(run, "command", runId)}",
            Content = new ScrollViewer { Content = content, MaxHeight = 620, VerticalScrollBarVisibility = ScrollBarVisibility.Auto },
            CloseButtonText = "关闭"
        };
        await dialog.ShowAsync();
    }

    private async Task SetActivityEnabledAsync(bool enabled)
    {
        var result = await RequestAsync("activity.enabled", new { enabled }, "无法更新活动记录设置。");
        if (result is not null)
            ShowNotice("活动记录设置已更新", enabled ? "新的可观测任务会记录活动元数据。" : "后端会停止新的活动记录；现有历史不受本操作删除。", InfoBarSeverity.Success);
    }

    private async Task ClearActivityAsync()
    {
        if (!await ConfirmAsync("清除已结束活动记录", "这只清除后端保存的已结束活动元数据，不会删除配置、研究证据或导出文件。", "清除"))
            return;
        var result = await RequestAsync("activity.clear", new { }, "无法清除活动记录。");
        if (result is not null)
        {
            ShowNotice("已清除", "已结束活动记录已清除；运行中的任务仍保留。", InfoBarSeverity.Success);
            await RefreshActivityAsync(silent: true);
        }
    }

    private async Task CancelOwnedRunAsync(string runId)
    {
        if (!_ownedRuns.Contains(runId))
            return;
        var result = await RequestAsync("run.cancel", new { run_id = runId }, "无法取消该任务。");
        if (result is not null)
        {
            _ownedRunStatus[runId] = Text(result.Value, "status", "cancelling");
            ShowNotice("正在取消", "取消请求已发送。最终状态会由后端运行事件确认。", InfoBarSeverity.Informational);
        }
    }

    private async Task LoadCliStatusAsync()
    {
        var result = await RequestAsync("cli.status", new { }, "无法读取 CLI 状态。");
        if (result is null || _cliSummary is null)
            return;
        var externalProtocol = Text(result.Value, "external_activity_protocol_version", "未返回");
        var observation = externalProtocol == "1" ? "已接入实时活动" : "尚未接入实时活动；升级后才能在活动页看到新的外部调用。";
        _cliSummary.Text = $"内置：{Text(result.Value, "bundled_path", "未返回")}（{Text(result.Value, "version", "版本未知")}）\n" +
                           $"外部：{Text(result.Value, "external_path", "未发现")}（{Text(result.Value, "external_version", "版本未知")}）\n" +
                           $"外部 CLI：{Text(result.Value, "external_status", "观测能力未知")}\n" +
                           $"活动观测：{observation}（协议：{externalProtocol}）";
    }

    private async Task LoadSkillsAsync()
    {
        var definitions = Items(Property(_state, "skill_targets"))
            .Where(item => !string.IsNullOrWhiteSpace(Text(item, "id")))
            .ToDictionary(item => Text(item, "id"), item => item, StringComparer.Ordinal);
        var parameters = new Dictionary<string, object?>();
        if (definitions.Count > 0)
            parameters["targets"] = definitions.Keys.ToArray();
        var result = await RequestAsync("skills.status", parameters, "无法读取 Skills 状态。");
        if (result is null || _skillRows is null)
            return;
        _skillRows.Children.Clear();
        foreach (var target in Items(result.Value, "targets"))
        {
            var id = Text(target, "target", Text(target, "id"));
            if (string.IsNullOrWhiteSpace(id))
                continue;
            definitions.TryGetValue(id, out var definition);
            var status = Text(target, "status", "unknown");
            _skillRows.Children.Add(new CheckBox
            {
                Content = $"{Text(target, "label", Text(definition, "label", id))}：{SkillStatusLabel(status)}",
                Tag = id,
                IsChecked = Bool(definition, "default")
            });
        }
        if (_skillRows.Children.Count == 0)
            _skillRows.Children.Add(Body("后端没有返回可管理的 Skill 目标。"));
    }

    private async Task InstallSelectedSkillsAsync()
    {
        if (_skillRows is null)
            return;
        var targets = _skillRows.Children.OfType<CheckBox>()
            .Where(check => check.IsChecked == true && check.Tag is string id && !string.IsNullOrWhiteSpace(id))
            .Select(check => (string)check.Tag)
            .ToArray();
        if (targets.Length == 0)
        {
            ShowNotice("请选择目标", "至少选择一个 Skill 后才能安装或更新。", InfoBarSeverity.Warning);
            return;
        }
        var result = await RequestAsync("skills.install", new { targets }, "无法启动 Skills 安装。");
        if (result is not null)
        {
            RegisterOwnedRun(Text(result.Value, "run_id"), "skills.install");
            ShowNotice("Skills 任务已开始", "安装或更新进度会出现在“活动”页面。", InfoBarSeverity.Success);
        }
    }

    private async Task CopyBundledCli()
    {
        var result = await RequestAsync("cli.status", new { }, "无法读取内置 CLI 路径。");
        if (result is null)
            return;
        var path = Text(result.Value, "bundled_path");
        if (string.IsNullOrWhiteSpace(path))
        {
            ShowNotice("没有可复制的路径", "后端没有报告内置 CLI 路径。", InfoBarSeverity.Warning);
            return;
        }
        CopyText($"& \"{path}\" --help");
        ShowNotice("已复制", "已复制不含密钥的 PowerShell 调用示例。", InfoBarSeverity.Success);
    }

    private async Task EnableBundledCliAsync()
    {
        if (!await ConfirmAsync("启用 App 内置命令", "此操作会让当前用户显式启用 App 内置命令。若发现同名外部 CLI，后端会拒绝覆盖；App 不会静默修改 PATH。", "启用"))
            return;
        var result = await RequestAsync("cli.enable", new { confirm = true }, "无法启用内置命令。");
        if (result is not null)
        {
            if (Bool(result.Value, "ok"))
                ShowNotice("已启用", "已按你的确认启用内置命令。", InfoBarSeverity.Success);
            else
                ShowNotice("未启用", Text(result.Value, "error", "后端拒绝了该操作，外部 CLI 未被覆盖。"), InfoBarSeverity.Warning);
            await LoadCliStatusAsync();
        }
    }

    private async Task SelectConfigDirectoryAsync()
    {
        var folder = await PickFolderAsync();
        if (folder is null)
            return;
        var result = await RequestAsync("profile.select", new { config_dir = folder.Path }, "无法切换配置目录。");
        if (result is not null)
        {
            ApplyState(result.Value);
            ShowNotice("已切换配置目录", "后端会以这个目录重新读取配置和活动状态。", InfoBarSeverity.Success);
            RenderCurrentPage();
        }
    }

    private async Task CheckForUpdateAsync()
    {
        var result = await RequestAsync("app.update-check", new { }, "无法检查更新。");
        if (result is null)
            return;
        if (!Bool(result.Value, "ok"))
        {
            ShowNotice("更新检查失败", Text(result.Value, "error", "请稍后手动重试。"), InfoBarSeverity.Warning);
            return;
        }
        var current = Text(result.Value, "current_version", "当前版本");
        var latest = Text(result.Value, "latest_version", current);
        var url = Text(result.Value, "url");
        if (string.IsNullOrWhiteSpace(url) || latest == current)
        {
            ShowNotice("更新检查完成", $"当前版本 {current} 已是可用版本，或后端未提供下载链接。", InfoBarSeverity.Success);
            return;
        }
        if (await ConfirmAsync("发现可用更新", $"当前版本：{current}\n可用版本：{latest}\n\n打开官方发布页后由你自行下载安装；不会自动覆盖运行中的资源。", "打开发布页"))
            await Launcher.LaunchUriAsync(new Uri(url));
    }

    private async Task ResetProvidersAsync()
    {
        if (!await ConfirmAsync("重置服务商健康状态", "这会清除本地保存的服务商健康记录，不能撤销。不会删除密钥或配置。", "重置"))
            return;
        var result = await RequestAsync("providers.reset", new { }, "无法重置服务商状态。");
        if (result is not null)
        {
            ShowNotice("已重置", "服务商健康状态已清除；下次用户主动测试或调用会建立新的状态。", InfoBarSeverity.Success);
            await RefreshStateAsync();
        }
    }

    private void OnBackendEvent(object? sender, BackendEvent backendEvent)
    {
        DispatcherQueue.TryEnqueue(async () =>
        {
            if (backendEvent.Name.Equals("run", StringComparison.OrdinalIgnoreCase))
            {
                var runId = Text(backendEvent.Data, "run_id");
                if (_ownedRuns.Contains(runId))
                {
                    _ownedRunStatus[runId] = Text(backendEvent.Data, "status", "running");
                    if (IsTerminal(_ownedRunStatus[runId]))
                    {
                        await LoadRunResultAsync(runId, backendEvent.Data);
                        if (_ownedRunKinds.TryGetValue(runId, out var kind) && kind == "provider.test")
                        {
                            if (_runProviders.TryGetValue(runId, out var testedProvider))
                            {
                                _testingProviders.Remove(testedProvider);
                                _runProviders.Remove(runId);
                            }
                            await RefreshProviderStateAfterTestAsync();
                        }
                    }
                }
            }
            if (_currentPage == "activity")
                await RefreshActivityAsync(silent: true);
        });
    }

    private async Task RefreshProviderStateAfterTestAsync()
    {
        var draft = _currentPage == "providers" ? CaptureDraft() : null;
        var refreshed = await RequestAsync("get_state", new { }, "无法刷新草稿测试状态。");
        if (refreshed is null)
            return;
        ApplyState(refreshed.Value);
        if (_currentPage == "providers")
            RenderCurrentPage(draft);
    }

    private void OnBackendDisconnected(object? sender, string message) =>
        DispatcherQueue.TryEnqueue(() =>
        {
            _activityTimer.Stop();
            ShowNotice("后端已断开", message, InfoBarSeverity.Error);
            RenderCurrentPage();
        });

    private async Task LoadRunResultAsync(string runId, JsonElement eventData)
    {
        JsonElement result;
        if (eventData.TryGetProperty("result", out var embedded) && embedded.ValueKind != JsonValueKind.Null)
            result = embedded.Clone();
        else
        {
            var response = await RequestAsync("run.result", new { run_id = runId }, "无法读取任务结果。");
            if (response is null || !response.Value.TryGetProperty("result", out var fetched) || fetched.ValueKind == JsonValueKind.Null)
                return;
            result = fetched.Clone();
        }
        _ownedRunResults[runId] = result.Clone();
        if (IsSearchRun(runId) && _resultText is not null)
        {
            _selectedResultRunId = runId;
            RenderResult(result);
        }
    }

    private async Task ShowRunResultAsync(string runId)
    {
        if (!_ownedRuns.Contains(runId))
            return;
        if (!_ownedRunResults.TryGetValue(runId, out var result))
        {
            var response = await RequestAsync("run.result", new { run_id = runId }, "无法读取任务结果。");
            if (response is null || !response.Value.TryGetProperty("result", out var fetched) || fetched.ValueKind == JsonValueKind.Null)
                return;
            result = fetched.Clone();
            _ownedRunResults[runId] = result;
        }
        _selectedResultRunId = runId;
        await NavigateToAsync("search");
        if (_resultText is not null)
            RenderResult(result);
    }

    private void RenderResult(JsonElement result)
    {
        if (_resultText is null || _rawResult is null || _sourceRows is null)
            return;
        _resultText.Text = ReadableResult(result);
        _rawResult.Text = JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
        _lastResultExport = _resultText.Text;
        _sourceRows.Children.Clear();
        foreach (var source in Items(result, "sources"))
        {
            var url = Text(source, "url", Text(source, "link"));
            if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
                _sourceRows.Children.Add(new HyperlinkButton { Content = Text(source, "title", Text(source, "name", url)), NavigateUri = uri });
        }
    }

    private Task CopyResult()
    {
        if (string.IsNullOrWhiteSpace(_resultText?.Text))
        {
            ShowNotice("没有可复制的结果", "先运行一个工具并等待结果。", InfoBarSeverity.Informational);
            return Task.CompletedTask;
        }
        CopyText(_resultText.Text);
        ShowNotice("已复制", "已复制当前可读结果。", InfoBarSeverity.Success);
        return Task.CompletedTask;
    }

    private async Task ExportResultAsync()
    {
        if (string.IsNullOrWhiteSpace(_lastResultExport))
        {
            ShowNotice("没有可导出的结果", "先运行一个工具并等待结果。", InfoBarSeverity.Informational);
            return;
        }
        var picker = new FileSavePicker();
        InitializeWithWindow.Initialize(picker, _windowHandle);
        picker.FileTypeChoices.Add("文本文件", [".txt"]);
        picker.SuggestedFileName = "smart-search-result";
        var file = await picker.PickSaveFileAsync();
        if (file is not null)
        {
            await FileIO.WriteTextAsync(file, _lastResultExport);
            ShowNotice("已导出", "结果已写入你选择的文件。", InfoBarSeverity.Success);
        }
    }

    private async Task<StorageFolder?> PickFolderAsync()
    {
        var picker = new FolderPicker();
        picker.FileTypeFilter.Add("*");
        InitializeWithWindow.Initialize(picker, _windowHandle);
        return await picker.PickSingleFolderAsync();
    }

    private async Task NavigateToAsync(string tag)
    {
        var target = RootNavigation.MenuItems.OfType<NavigationViewItem>().FirstOrDefault(item => item.Tag as string == tag);
        if (target is not null)
            RootNavigation.SelectedItem = target;
        await Task.CompletedTask;
    }

    private void RegisterOwnedRun(string runId, string kind)
    {
        if (string.IsNullOrWhiteSpace(runId))
            return;
        _ownedRuns.Add(runId);
        _ownedRunStatus[runId] = "running";
        _ownedRunKinds[runId] = kind;
    }

    private bool IsSearchRun(string runId) => _ownedRunKinds.TryGetValue(runId, out var kind) && kind is not "provider.test" and not "skills.install";

    private bool HasActiveOwnedRuns => _ownedRunStatus.Values.Any(status => !IsTerminal(status));

    private async void OnAppWindowClosing(AppWindow sender, AppWindowClosingEventArgs args)
    {
        if (_allowClose)
            return;
        args.Cancel = true;
        await RequestCloseAsync();
    }

    private async Task RequestCloseAsync()
    {
        if (_shuttingDown)
            return;
        if (HasActiveOwnedRuns)
        {
            var dialog = new ContentDialog
            {
                XamlRoot = DialogRoot,
                RequestedTheme = ((FrameworkElement)Content).ActualTheme,
                Title = "仍有 Smart Search 任务在运行",
                Content = "继续后台运行可从通知区域恢复；取消任务并退出只会取消本 App 发起的任务，不会终止外部 CLI。",
                PrimaryButtonText = "继续在后台",
                SecondaryButtonText = "取消任务并退出",
                CloseButtonText = "返回"
            };
            switch (await dialog.ShowAsync())
            {
                case ContentDialogResult.Primary:
                    HideToTray();
                    return;
                case ContentDialogResult.Secondary:
                    foreach (var runId in _ownedRunStatus.Where(entry => !IsTerminal(entry.Value)).Select(entry => entry.Key).ToArray())
                        await CancelOwnedRunAsync(runId);
                    await ShutdownAndCloseAsync();
                    return;
                default:
                    return;
            }
        }
        await ShutdownAndCloseAsync();
    }

    private void HideToTray()
    {
        ShowWindow(_windowHandle, SwHide);
        _tray.Show();
    }

    private void ShowMainWindow()
    {
        ShowWindow(_windowHandle, SwRestore);
        Activate();
        _tray.Hide();
    }

    internal void ActivateFromRedirect() => ShowMainWindow();

    private async void ExitFromTray()
    {
        ShowMainWindow();
        await RequestCloseAsync();
    }

    private async Task ShutdownAndCloseAsync()
    {
        if (_shuttingDown)
            return;
        _shuttingDown = true;
        _activityTimer.Stop();
        _tray.Hide();
        await _backend.DisposeAsync();
        _tray.Dispose();
        _allowClose = true;
        Close();
    }

    private async Task<bool> ConfirmAsync(string title, string content, string confirm)
    {
        var dialog = new ContentDialog
        {
            XamlRoot = DialogRoot,
            RequestedTheme = ((FrameworkElement)Content).ActualTheme,
            Title = title,
            Content = content,
            PrimaryButtonText = confirm,
            CloseButtonText = "取消",
            DefaultButton = ContentDialogButton.Close
        };
        return await dialog.ShowAsync() == ContentDialogResult.Primary;
    }

    private XamlRoot DialogRoot => ((FrameworkElement)Content).XamlRoot;

    private static StackPanel PagePanel() => new()
    {
        Spacing = Theme.SpaceM,
        MaxWidth = Theme.ContentMaxWidth,
        // Stretch combined with MaxWidth centres the column, which on a maximised
        // window leaves a wide dead margin on both sides of left-aligned text.
        HorizontalAlignment = HorizontalAlignment.Left
    };

    private static ScrollViewer Scroll(UIElement content) => new()
    {
        Content = content,
        Padding = new Thickness(24),
        HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
        VerticalScrollBarVisibility = ScrollBarVisibility.Auto
    };

    /// <summary>Separate a heading from the block above it without a margin literal.</summary>
    private static TextBlock WithTopGap(TextBlock block)
    {
        block.Margin = new Thickness(0, Theme.SpaceL, 0, 0);
        return block;
    }

    private static TextBlock PageTitle(string text) => Theme.PageTitle(text);

    private static TextBlock Body(string text) => Theme.Body(text);

    /// <summary>A value carried alongside its label. Identifiers, paths and
    /// versions render monospaced so they read as data.</summary>
    private static UIElement KeyValue(string label, string value, bool mono = true)
    {
        var caption = Theme.Hint(label);
        var body = mono ? Theme.Mono(value) : Theme.Body(value);
        return Theme.Stack(2, caption, body);
    }

    private static UIElement Section(string heading, IEnumerable<UIElement> children)
    {
        var panel = new StackPanel { Spacing = Theme.SpaceS, Margin = new Thickness(0, Theme.SpaceL, 0, 0) };
        panel.Children.Add(Theme.SectionTitle(heading));
        var body = new StackPanel { Spacing = Theme.SpaceS };
        foreach (var child in children)
            body.Children.Add(child);
        panel.Children.Add(Theme.Card(body));
        return panel;
    }

    private static UIElement OfflineHint() => Theme.Card(
        Theme.Row(Theme.SpaceS, Theme.Pill("未连接", Theme.StatusKind.Bad)),
        Theme.Secondary("本地后端未连接，因此不会显示猜测出来的状态。请先确认随包后端存在，再重新连接。"));

    private Button ActionButton(string text, Func<Task> action, bool primary = false, string? busyText = null)
    {
        var button = new Button
        {
            Content = text,
            Margin = new Thickness(0, Theme.SpaceXS, Theme.SpaceS, Theme.SpaceXS),
            MinWidth = 112
        };
        if (primary)
            button.Style = Application.Current.Resources["AccentButtonStyle"] as Style;

        var running = false;
        button.Click += async (_, _) =>
        {
            // The button used to stay live for the whole call. A provider probe
            // runs up to 20 seconds, so with nothing changing on screen a user
            // clicks again, and every extra click is another real, possibly
            // billable request. Every button in the app comes from this factory,
            // so disabling here covers save, preview, install, run and test.
            if (running)
                return;
            running = true;
            var original = button.Content;
            button.IsEnabled = false;
            button.Content = Theme.BusyContent(busyText ?? text + "中…", primary);
            try
            {
                await action();
            }
            finally
            {
                button.Content = original;
                button.IsEnabled = true;
                running = false;
            }
        };
        return button;
    }

    private Control CreateFieldInput(JsonElement field, bool secret, string value, bool isLocked)
    {
        if (isLocked)
            return new TextBox { Text = value, IsReadOnly = true, IsEnabled = false, TextWrapping = TextWrapping.Wrap };
        if (secret)
            return new PasswordBox { PlaceholderText = "留空将保留当前密钥", IsEnabled = true };
        if (Text(field, "kind").Equals("bool", StringComparison.OrdinalIgnoreCase))
            return new ToggleSwitch { IsOn = value.Equals("true", StringComparison.OrdinalIgnoreCase) || value.Equals("是", StringComparison.OrdinalIgnoreCase) };
        var choices = Items(field, "choices").Where(choice => choice.ValueKind == JsonValueKind.String).Select(choice => choice.GetString()!).ToList();
        if (choices.Count > 0)
        {
            var combo = new ComboBox { MinWidth = 280 };
            foreach (var choice in choices)
                combo.Items.Add(choice);
            combo.SelectedItem = choices.FirstOrDefault(choice => choice.Equals(value, StringComparison.OrdinalIgnoreCase)) ?? choices.FirstOrDefault();
            return combo;
        }
        return new TextBox { Text = value, PlaceholderText = Text(field, "default"), TextWrapping = TextWrapping.Wrap };
    }

    private Control CreateCommandInput(JsonElement field)
    {
        var kind = Text(field, "kind");
        if (kind.Equals("bool", StringComparison.OrdinalIgnoreCase))
            return new ToggleSwitch();
        var choices = Items(field, "choices").Where(choice => choice.ValueKind == JsonValueKind.String).Select(choice => choice.GetString()!).ToList();
        if (kind.Equals("choice", StringComparison.OrdinalIgnoreCase) && choices.Count > 0)
        {
            var combo = new ComboBox { MinWidth = 280 };
            foreach (var choice in choices)
                combo.Items.Add(choice);
            if (!string.IsNullOrWhiteSpace(Text(field, "default")))
                combo.SelectedItem = Text(field, "default");
            return combo;
        }
        return new TextBox
        {
            Text = Text(field, "default"),
            PlaceholderText = Bool(field, "multiple") ? "每行一个值" : string.Empty,
            AcceptsReturn = Bool(field, "multiple"),
            TextWrapping = TextWrapping.Wrap
        };
    }

    private DraftChange CollectDraft(string? provider = null)
    {
        var set = new Dictionary<string, object?>();
        var unset = new List<string>();
        foreach (var (key, editor) in _fieldEditors)
        {
            if (editor.Locked || (provider is not null && !Text(editor.Field, "provider").Equals(provider, StringComparison.OrdinalIgnoreCase)))
                continue;
            var value = ReadEditorValue(editor);
            if (!HasDraftChange(editor, value))
                continue;
            if (editor.Clear?.IsChecked == true)
            {
                unset.Add(key);
                continue;
            }
            set[key] = ConvertValue(editor, value);
        }
        return new DraftChange(set, unset);
    }

    private Dictionary<string, FieldDraft> CaptureDraft()
    {
        var captured = new Dictionary<string, FieldDraft>(StringComparer.Ordinal);
        foreach (var (key, editor) in _fieldEditors)
        {
            var value = ReadEditorValue(editor);
            if (!HasDraftChange(editor, value))
                continue;
            captured[key] = new FieldDraft(value.Text, value.IsChecked, editor.Clear?.IsChecked == true);
        }
        return captured;
    }

    private static bool HasDraftChange(FieldEditor editor, CommandValue value) =>
        !editor.Locked && (editor.Clear?.IsChecked == true ||
                           (editor.Secret ? !string.IsNullOrWhiteSpace(value.Text) : !ControlValueComparer.Equal(value, editor.Initial)));

    private static void RestoreDraft(FieldEditor editor, FieldDraft draft)
    {
        switch (editor.Input)
        {
            case TextBox textBox: textBox.Text = draft.Text ?? string.Empty; break;
            case PasswordBox passwordBox: passwordBox.Password = draft.Text ?? string.Empty; break;
            case ComboBox comboBox: comboBox.SelectedItem = draft.Text; break;
            case ToggleSwitch toggle: toggle.IsOn = draft.IsChecked; break;
        }
        if (editor.Clear is not null)
            editor.Clear.IsChecked = draft.Clear;
    }

    private static CommandValue ReadEditorValue(FieldEditor editor) => ReadControl(editor.Input);

    private CommandValue ReadControl(string name) => _commandControls.TryGetValue(name, out var control) ? ReadControl(control) : new CommandValue(null);

    private static CommandValue ReadControl(Control control) => control switch
    {
        TextBox textBox => new CommandValue(textBox.Text),
        PasswordBox passwordBox => new CommandValue(passwordBox.Password),
        ComboBox comboBox => new CommandValue(comboBox.SelectedItem?.ToString()),
        ToggleSwitch toggle => new CommandValue(null, toggle.IsOn),
        _ => new CommandValue(null)
    };

    private static object? ConvertValue(FieldEditor editor, CommandValue value)
    {
        var kind = Text(editor.Field, "kind").ToLowerInvariant();
        return kind switch
        {
            "bool" => value.IsChecked,
            "int" when int.TryParse(value.Text, out var integer) => integer,
            "float" when double.TryParse(value.Text, System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var number) => number,
            _ => value.Text
        };
    }

    private static bool IsAdvanced(JsonElement field)
    {
        var tier = Text(field, "tier");
        var section = Text(field, "section");
        return tier.Equals("advanced", StringComparison.OrdinalIgnoreCase) || tier.Equals("expert", StringComparison.OrdinalIgnoreCase) ||
               section.Equals("routing", StringComparison.OrdinalIgnoreCase) || section.Equals("reliability", StringComparison.OrdinalIgnoreCase) || section.Equals("diagnostics", StringComparison.OrdinalIgnoreCase);
    }

    private static bool IsCommandAdvanced(JsonElement field)
    {
        if (field.ValueKind == JsonValueKind.Object && field.TryGetProperty("advanced", out var advanced) && advanced.ValueKind is JsonValueKind.True or JsonValueKind.False)
            return advanced.GetBoolean();
        return Items(field, "flags").Any();
    }

    private static bool IsSecret(JsonElement field)
    {
        var kind = Text(field, "kind");
        var key = Text(field, "key");
        return kind.Equals("secret", StringComparison.OrdinalIgnoreCase) || kind.Equals("password", StringComparison.OrdinalIgnoreCase) ||
               key.Contains("KEY", StringComparison.OrdinalIgnoreCase) || key.Contains("TOKEN", StringComparison.OrdinalIgnoreCase) ||
               key.Contains("SECRET", StringComparison.OrdinalIgnoreCase) || key.Contains("PASSWORD", StringComparison.OrdinalIgnoreCase);
    }

    private static string Label(JsonElement field) => Text(field, "label_zh", Text(field, "label_en", Text(field, "key")));

    private static string SourceLabel(string source) => source.ToLowerInvariant() switch
    {
        "environment" => "环境变量",
        "config_file" => "配置文件",
        "default" => "默认值",
        _ => string.IsNullOrWhiteSpace(source) ? "未知" : BackendStatusLabel(source)
    };

    private static string MissingText(JsonElement value)
    {
        var missing = Items(value, "missing").Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString()).Where(item => !string.IsNullOrWhiteSpace(item));
        return string.Join("、", missing) is { Length: > 0 } text ? text : "后端未说明";
    }

    private static string CapabilityLabel(string capability) => capability switch
    {
        "main_search" => "主搜索",
        "web_search" => "网页搜索",
        "docs_search" => "文档检索",
        "web_fetch" => "网页读取",
        "vertical_search" => "垂直搜索",
        _ => capability
    };

    private static string ProviderCheckLabel(string status) => status.ToLowerInvariant() switch
    {
        "ok" or "passed" or "success" => "通过",
        "failed" or "error" => "未通过",
        "cancelled" => "已取消",
        "closed" => "已结束（不推断成功）",
        _ => string.IsNullOrWhiteSpace(status) ? "状态未知" : BackendStatusLabel(status)
    };

    private static string CooldownText(JsonElement health)
    {
        var seconds = Number(health, "cooldown_remaining_seconds");
        return seconds > 0 ? TimeSpan.FromSeconds(seconds).ToString(@"mm\:ss") : "未返回";
    }

    private static string StatusLabel(string status) => status.ToLowerInvariant() switch
    {
        "running" => "运行中",
        "finished" => "已完成",
        "failed" => "失败",
        "cancelled" => "已取消",
        "cancelling" => "正在取消",
        "stale" => "状态未更新",
        "interrupted" => "已中断",
        _ => string.IsNullOrWhiteSpace(status) ? "未知" : BackendStatusLabel(status)
    };

    private static string SkillStatusLabel(string status) => status.ToLowerInvariant() switch
    {
        "missing" => "未安装",
        "stale" => "可更新",
        "up_to_date" => "已是当前版本",
        _ => string.IsNullOrWhiteSpace(status) ? "状态未知" : BackendStatusLabel(status)
    };

    private static bool IsTerminal(string status) => status.Equals("finished", StringComparison.OrdinalIgnoreCase) ||
                                                    status.Equals("failed", StringComparison.OrdinalIgnoreCase) ||
                                                    status.Equals("cancelled", StringComparison.OrdinalIgnoreCase) ||
                                                    status.Equals("stale", StringComparison.OrdinalIgnoreCase) ||
                                                    status.Equals("interrupted", StringComparison.OrdinalIgnoreCase);

    private static string ReadableResult(JsonElement result)
    {
        foreach (var name in new[] { "display_text", "answer", "content", "text", "summary", "message", "error" })
        {
            var candidate = Text(result, name);
            if (!string.IsNullOrWhiteSpace(candidate))
                return candidate;
        }
        return "任务已返回结构化结果。展开“高级 JSON”可以查看完整字段；来源会列在本结果下方。";
    }

    private static string Elapsed(JsonElement run)
    {
        var milliseconds = Number(run, "elapsed_ms");
        return milliseconds <= 0 ? "未返回" : TimeSpan.FromMilliseconds(milliseconds).ToString(@"mm\:ss");
    }

    private static string Timestamp(JsonElement value, string property)
    {
        var seconds = Number(value, property);
        return seconds <= 0 ? "未返回" : DateTimeOffset.FromUnixTimeSeconds((long)seconds).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss");
    }

    private static string TimestampOrText(JsonElement value, string property)
    {
        var seconds = Number(value, property);
        return seconds > 0 ? DateTimeOffset.FromUnixTimeSeconds((long)seconds).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss") : Text(value, property, "未返回");
    }

    private static JsonElement Property(JsonElement? value, string property) => value is { } element ? Property(element, property) : default;

    private static JsonElement Property(JsonElement value, string property) => value.ValueKind == JsonValueKind.Object && value.TryGetProperty(property, out var item) ? item : default;

    private static IEnumerable<JsonElement> Items(JsonElement value, string property) => Items(Property(value, property));

    private static IEnumerable<JsonElement> Items(JsonElement value) => value.ValueKind == JsonValueKind.Array ? value.EnumerateArray().Select(item => item.Clone()) : Enumerable.Empty<JsonElement>();

    private static string Text(JsonElement? value, string property, string fallback = "") => value is { } element ? Text(element, property, fallback) : fallback;

    private static string Text(JsonElement value, string property, string fallback = "") => value.ValueKind == JsonValueKind.Object && value.TryGetProperty(property, out var item) ? Display(item, fallback) : fallback;

    private static string DisplayValue(JsonElement values, string key) => values.ValueKind == JsonValueKind.Object && values.TryGetProperty(key, out var value) ? Display(value) : string.Empty;

    private static string Display(JsonElement value, string fallback = "") => value.ValueKind switch
    {
        JsonValueKind.String => value.GetString() ?? fallback,
        JsonValueKind.Number => value.ToString(),
        JsonValueKind.True => "true",
        JsonValueKind.False => "false",
        JsonValueKind.Null or JsonValueKind.Undefined => fallback,
        _ => fallback
    };

    private static bool Bool(JsonElement? value, string property, bool fallback = false) => value is { } element && Bool(element, property, fallback);

    private static bool Bool(JsonElement value, string property, bool fallback = false) =>
        value.ValueKind == JsonValueKind.Object && value.TryGetProperty(property, out var item)
            ? item.ValueKind == JsonValueKind.True || (item.ValueKind == JsonValueKind.String && bool.TryParse(item.GetString(), out var parsed) && parsed)
            : fallback;

    private static double Number(JsonElement value, string property) =>
        value.ValueKind == JsonValueKind.Object && value.TryGetProperty(property, out var item) && item.TryGetDouble(out var result) ? result : 0;

    private IReadOnlyList<string> ActivityDirectories()
    {
        var directories = _extraActivityDirectories.ToList();
        var current = Text(_state, "config_dir", Text(_state, "config_path"));
        if (!string.IsNullOrWhiteSpace(current) && !directories.Contains(current, StringComparer.OrdinalIgnoreCase))
            directories.Insert(0, current);
        return directories;
    }

    private void RenderExtraDirectories(StackPanel rows)
    {
        if (_extraActivityDirectories.Count == 0)
        {
            rows.Children.Add(Body("没有额外目录。"));
            return;
        }
        foreach (var directory in _extraActivityDirectories.ToArray())
        {
            var item = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
            item.Children.Add(new TextBlock { Text = directory, TextWrapping = TextWrapping.Wrap, MaxWidth = 620, VerticalAlignment = VerticalAlignment.Center });
            item.Children.Add(ActionButton("移除", () =>
            {
                _extraActivityDirectories.Remove(directory);
                SaveExtraDirectories();
                RenderCurrentPage();
                return Task.CompletedTask;
            }));
            rows.Children.Add(item);
        }
    }

    private void LoadLocalPreferences()
    {
        try
        {
            if (File.Exists(PreferencesPath))
            {
                foreach (var (key, value) in JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(PreferencesPath)) ?? [])
                    _preferences[key] = value;
            }
            var raw = ReadSetting("activityDirectories");
            if (!string.IsNullOrWhiteSpace(raw))
                _extraActivityDirectories.AddRange(JsonSerializer.Deserialize<List<string>>(raw) ?? []);
        }
        catch (Exception error) when (error is JsonException or IOException or UnauthorizedAccessException)
        {
            // An unreadable local preference is ignored instead of scanning unexpected paths.
        }
    }

    private void SaveExtraDirectories() => SaveSetting("activityDirectories", JsonSerializer.Serialize(_extraActivityDirectories));

    private string? ReadSetting(string key) => _preferences.GetValueOrDefault(key);

    private void SaveSetting(string key, string value)
    {
        _preferences[key] = value;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(PreferencesPath)!);
            var temporary = PreferencesPath + ".tmp";
            File.WriteAllText(temporary, JsonSerializer.Serialize(_preferences));
            File.Move(temporary, PreferencesPath, overwrite: true);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            // The setting remains effective for this session even if its local persistence is unavailable.
        }
    }

    private static string PreferencesPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Smart Search", "desktop-preferences.json");

    private void ApplyTheme(string theme)
    {
        if (Content is FrameworkElement root)
        {
            root.RequestedTheme = theme switch
            {
                "light" => ElementTheme.Light,
                "dark" => ElementTheme.Dark,
                _ => ElementTheme.Default
            };
        }
    }

    private static BackendLaunch ReadBackendLaunch()
    {
        var arguments = Environment.GetCommandLineArgs();
        string? path = null;
        var backendArguments = new List<string>();
        for (var index = 0; index < arguments.Length - 1; index++)
        {
            if (arguments[index].Equals("--backend", StringComparison.OrdinalIgnoreCase))
                path = arguments[index + 1];
            if (arguments[index].Equals("--backend-arg", StringComparison.OrdinalIgnoreCase))
                backendArguments.Add(arguments[index + 1]);
        }
        return new BackendLaunch(path, backendArguments);
    }

    private static string SafeMessage(Exception error) => error switch
    {
        BackendRpcException rpc => rpc.Message,
        BackendDisconnectedException disconnected => disconnected.Message,
        OperationCanceledException => "本地后端在 30 秒内没有响应。请检查后端后手动重试。",
        _ => "本地后端没有返回可安全显示的详情。请检查安装包和本地诊断。"
    };

    private void ShowNotice(string title, string message, InfoBarSeverity severity)
    {
        NoticeBar.Title = title;
        NoticeBar.Message = message;
        NoticeBar.Severity = severity;
        NoticeBar.IsOpen = true;
    }

    private static void CopyText(string text)
    {
        var package = new DataPackage();
        package.SetText(text);
        Clipboard.SetContent(package);
    }

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(nint hWnd, int nCmdShow);

    private sealed record CommandOption(string Id, string Label, string Description, bool Experimental, JsonElement Definition)
    {
        public override string ToString() => Experimental ? $"{Label}（实验性）" : Label;
    }

    private sealed record FieldDraft(string? Text, bool IsChecked, bool Clear);

    private sealed record DraftChange(Dictionary<string, object?> Set, List<string> Unset);

    private sealed record FieldEditor(JsonElement Field, Control Input, CheckBox? Clear, CommandValue Initial, bool Secret, bool Locked);

    private sealed record BackendLaunch(string? Path, IReadOnlyList<string> Arguments);
}
