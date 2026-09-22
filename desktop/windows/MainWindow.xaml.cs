using static SmartSearch.Desktop.Localization;
using System.Runtime.InteropServices;
using System.Text.Json;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Media;
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
    private readonly Microsoft.UI.Dispatching.DispatcherQueueTimer _maintenanceTimer;
    private readonly NativeTray _tray;
    private readonly Dictionary<string, FieldEditor> _fieldEditors = new(StringComparer.Ordinal);
    private readonly Dictionary<string, Control> _commandControls = new(StringComparer.Ordinal);
    private readonly List<CommandArgument> _commandArguments = [];
    private readonly HashSet<string> _ownedRuns = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _ownedRunStatus = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _ownedRunKinds = new(StringComparer.Ordinal);
    private readonly Dictionary<string, JsonElement> _ownedRunResults = new(StringComparer.Ordinal);
    private readonly Dictionary<string, string> _preferences = new(StringComparer.Ordinal);
    private readonly OperationState _operations = new();
    private readonly Dictionary<Button, ActionBinding> _actionButtons = [];
    private readonly Dictionary<string, StackPanel> _providerStatusPanels = [];
    private readonly Dictionary<string, bool> _disclosures = [];
    private readonly Dictionary<string, double> _pageOffsets = [];
    private readonly HashSet<string> _handlingRunResults = [];
    private readonly Dictionary<string, Dictionary<string, CommandValue>> _commandDrafts = [];
    private string? _renderedCommandId;
    private Dictionary<string, FieldDraft> _providerDraft = [];
    private TextBlock? _saveSummary;
    private bool _connecting;
    private JsonElement? _state;
    private JsonElement? _updates;
    private readonly AppUpdater _appUpdater = new();
    private CancellationTokenSource? _appDownloadCancellation;
    private bool _installingApp;
    private string? _promptedAppVersion;
    private bool AppInstallBlocked => _state is null || _dialogOpen || EnvironmentBusy || Bool(_skills, "busy") ||
        _providerDraft.Count > 0 || ConfigOperationBusy || HasActiveOwnedRuns ||
        Text(Property(_updates, "cli_update"), "status") == "running";
    private JsonElement? _environment;
    private JsonElement? _skills;
    private TextBlock? _skillSummary, _skillResult;
    private bool _skillSelectionInitialized;
    private readonly HashSet<string> _selectedSkillTargets = [];
    private ProgressBar? _environmentProgress;
    private bool EnvironmentBusy => Bool(_environment, "busy") || _operations.IsBusy("environment-request");
    private TextBlock? _appUpdateSummary, _cliUpdateSummary;
    private Button? _appCancelButton, _cliCancelButton;
    private ProgressBar? _downloadProgress;
    private ToggleSwitch? _autoUpdateSwitch;
    private bool _settingAutoUpdate;
    private AppWindow? _appWindow;
    private nint _windowHandle;
    private string _currentPage = "providers";
    private bool _started;
    private bool _connectionFailed;
    private bool _preferenceReadFailed;
    private bool _recoveringRuns;
    private bool _allowClose;
    private bool _shuttingDown;
    private StackPanel? _skillRows;
    private ComboBox? _commandPicker;
    private StackPanel? _commandFieldPanel;
    private TextBox? _resultText;
    private TextBox? _rawResult;
    private StackPanel? _sourceRows;
    private Expander? _sourceDisclosure;
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
        _maintenanceTimer = DispatcherQueue.CreateTimer();
        _maintenanceTimer.Interval = TimeSpan.FromSeconds(2);
        _maintenanceTimer.Tick += async (_, _) =>
        {
            await RefreshOwnedRunsAsync();
            await CheckAppAutomaticallyAsync();
        };
        LoadLocalPreferences();
        Localization.Preference = ReadSetting("language") ?? "auto";
        if (Localization.Preference is not ("auto" or "zh" or "en"))
        {
            Localization.Preference = "auto";
            _preferenceReadFailed = true;
        }
        ApplyNavigationLanguage();
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
        _appWindow.Title = Environment.GetCommandLineArgs().Contains("--backend") ? L("Smart Search · 测试窗口") : "Smart Search";
        _appWindow.SetIcon(Path.Combine(AppContext.BaseDirectory, "Assets", "smart-search.ico"));
    }

    private async void OnWindowActivated(object sender, WindowActivatedEventArgs args)
    {
        if (_started)
            return;
        _started = true;
        await RunOperationAsync("connect", ConnectAsync);
        if (_preferenceReadFailed && _backend.IsConnected)
            ShowNotice(L("本机偏好"), L("无法读取已保存的显示偏好，已使用默认设置。原配置文件未修改。"), InfoBarSeverity.Warning);
    }

    private async Task ConnectAsync()
    {
        if (EnvironmentBusy || _operations.IsBusy("updates-cli") || Text(Property(_updates, "cli_update"), "status") == "running") return;
        _connecting = true;
        _connectionFailed = false;
        RenderCurrentPage();
        try
        {
            var state = await _backend.StartAsync(configDirectory: null, CancellationToken.None);
            ApplyState(state);
            _maintenanceTimer.Start();
            ClearNotice();
        }
        catch (Exception error)
        {
            _connectionFailed = true;
            ShowNotice(L("后端不可用"), SafeMessage(error), InfoBarSeverity.Error);
        }
        _connecting = false;
        RenderCurrentPage();
    }

    private async Task<bool> RefreshStateAsync(bool preserveDraft = true)
    {
        var result = await RequestAsync("get_state", new { }, L("无法刷新本机状态。"));
        if (result is null)
            return false;
        ApplyState(result.Value);
        if (!preserveDraft) { _providerDraft.Clear(); _fieldEditors.Clear(); }
        RenderCurrentPage();
        return true;
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
        _updates = Property(state, "updates").Clone();
        _environment = Property(state, "environment").Clone();
        _skills = Property(state, "skills").Clone();
        _configSnapshotStale = false;
    }

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
        CaptureCommandInputs();
        UpdateWorkspaceHeader();
        _actionButtons.Clear();
        _providerStatusPanels.Clear();
        if (preservedDraft is not null) _providerDraft = preservedDraft;
        if (_commandPicker?.SelectedItem is CommandOption selected)
            _selectedCommandId = selected.Id;
        ContentFrame.Content = _currentPage switch
        {
            "providers" => BuildProvidersPage(_providerDraft),
            "search" => BuildSearchPage(),
            "ai" => BuildAiPage(),
            "settings" => BuildSettingsPage(),
            _ => BuildProvidersPage(_providerDraft)
        };
        RefreshActionButtons();
    }

    private StackPanel BuildProviderStatus(JsonElement state, string provider)
    {
        var panel = new StackPanel { Spacing = 6 };
        var busy = _operations.IsBusy("test:" + provider);
        var presence = Text(Property(state, "probe_kinds"), provider) == "presence";
        var check = Property(Property(state, "provider_checks"), provider);
        var status = Text(check, "status");
        panel.Children.Add(Badge(busy ? presence ? L("检查中") : L("测试中") : check.ValueKind == JsonValueKind.Object ? ProviderCheckLabel(status) : presence ? L("尚未检查") : L("尚未测试"),
            busy ? "Active" : StatusTone(status)));
        if (busy)
            panel.Children.Add(Secondary(presence ? L("正在检查配置是否填写。") : L("正在等待服务商响应…")));
        if (busy)
        {
            var cancel = new Button { Content = L("取消测试"), IsEnabled = !_operations.IsBusy("cancel-test:" + provider) };
            cancel.Click += async (_, _) => await RunOperationAsync("cancel-test:" + provider, async () =>
            {
                foreach (var runId in _operations.RunsFor("test:" + provider)) await CancelOwnedRunAsync(runId);
            });
            panel.Children.Add(cancel);
        }
        else if (check.ValueKind == JsonValueKind.Object)
        {
            var scope = Text(check, "scope");
            panel.Children.Add(Secondary($"{(scope == "draft" ? L("未保存修改的测试") : L("测试时的有效配置"))} · {TimestampOrText(check, "checked_at")}"));
            if (scope == "draft") panel.Children.Add(Secondary(L("此结果对应测试时尚未保存的修改；再次测试可确认当前配置。")));
            if (!string.IsNullOrWhiteSpace(Text(check, "probe")))
                panel.Children.Add(Secondary(L("检查方式：") + ProviderCheckLabel(Text(check, "probe"))));
            var message = Text(check, "message");
            if (!string.IsNullOrWhiteSpace(message)) panel.Children.Add(Disclosure("test-detail:" + provider, L("技术详情"), DataText(message)));
        }
        var health = Property(state, "provider_health");
        var healthRow = Items(health, "providers").FirstOrDefault(item => Text(item, "provider").Equals(provider, StringComparison.OrdinalIgnoreCase));
        var cooling = Text(healthRow, "state") == "cooldown" ||
            Items(health, "cooldown_providers").Any(item => item.ValueKind == JsonValueKind.String && item.GetString() == provider);
        if (cooling) panel.Children.Add(Badge(L("调用保护：冷却中 · {0}", CooldownText(healthRow)), "Warning"));
        return panel;
    }

    private void RenderEnvironmentState() => RenderCliState();

    private async Task EnvironmentRequestAsync(string method, object? parameters = null)
    {
        if (!_operations.Begin("environment-request")) return;
        RefreshActionButtons();
        try
        {
            var result = await RequestAsync(method, parameters ?? new { }, L("CLI 安装未完成。"));
            if (result is not null) _environment = result.Value.Clone();
        }
        finally { _operations.EndRequest("environment-request"); RenderEnvironmentState(); }
    }

    private void RenderCommandFields()
    {
        if (_commandFieldPanel is null || _commandPicker?.SelectedItem is not CommandOption command)
            return;
        CaptureCommandInputs();
        _selectedCommandId = _renderedCommandId = command.Id;
        _commandControls.Clear();
        _commandArguments.Clear();
        _commandFieldPanel.Children.Clear();
        _commandOptions = null;
        _commandFieldPanel.Children.Add(Body(command.Experimental
            ? L("{0}（实验性：只会在你点击运行后执行。）", command.Description)
            : command.Description));
        var fields = Items(command.Definition, "fields").ToList();
        foreach (var field in fields.Where(field => !IsCommandAdvanced(field)))
            AddCommandField(field, _commandFieldPanel);
        var advanced = fields.Where(IsCommandAdvanced).ToList();
        if (advanced.Count > 0)
        {
            _commandOptions = new StackPanel { Spacing = 16 };
            foreach (var field in advanced) AddCommandField(field, _commandOptions);
        }
        if (_commandOptionsButton is not null)
            _commandOptionsButton.Visibility = advanced.Count > 0 ? Visibility.Visible : Visibility.Collapsed;
        RefreshActionButtons();
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
        group.Children.Add(new TextBlock { Text = Text(field, "label", name), FontWeight = Microsoft.UI.Text.FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap });
        var help = Text(field, "help");
        if (!string.IsNullOrWhiteSpace(help))
            group.Children.Add(Secondary(help));
        var input = CreateCommandInput(field);
        AutomationProperties.SetName(input, Text(field, "label", name));
        if (_selectedCommandId is not null && _commandDrafts.TryGetValue(_selectedCommandId, out var draft) && draft.TryGetValue(name, out var saved))
            RestoreControl(input, saved);
        _commandControls[name] = input;
        group.Children.Add(input);
        target.Children.Add(group);
    }

    private async Task StartSelectedCommandAsync()
    {
        if (SearchRunning) return;
        if (_commandPicker?.SelectedItem is not CommandOption command)
        {
            ShowNotice(L("请选择工具"), L("后端尚未提供命令目录。"), InfoBarSeverity.Warning);
            return;
        }
        foreach (var argument in _commandArguments.Where(argument => argument.Required && !argument.IsBoolean))
        {
            if (string.IsNullOrWhiteSpace(ReadControl(argument.Name).Text))
            {
                ShowNotice(L("缺少必要参数"), L("请填写“{0}”。", argument.Name), InfoBarSeverity.Warning);
                return;
            }
        }
        var arguments = ProtocolArguments.Build(_commandArguments, ReadControl).ToArray();
        var result = await RequestAsync("run.start", new { command = command.Id, arguments }, L("无法启动该任务。"));
        if (result is null)
            return;
        var runId = Text(result.Value, "run_id");
        RegisterOwnedRun(runId, command.Id, "run:" + command.Id);
        _selectedResultRunId = runId;
        _lastResultExport = string.Empty;
        if (_resultText is not null)
            _resultText.Text = L("任务正在运行。完成后会显示可读结果和来源。");
        if (_rawResult is not null)
            _rawResult.Text = string.Empty;
        _sourceRows?.Children.Clear();
        if (_sourceDisclosure is not null) _sourceDisclosure.Visibility = Visibility.Collapsed;
        ShowSearchState(L("任务正在运行。完成后会显示可读结果和来源。"), true);
    }

    private async Task PreviewDraftAsync()
    {
        var draft = CollectDraft();
        var result = await RequestAsync("config.preview", new { set = draft.Set, unset = draft.Unset }, L("无法预览修改。"));
        if (result is null)
            return;
        var ready = Bool(result.Value, "minimum_profile_ok");
        ShowNotice(L("修改预览"), ready ? L("修改后满足基础配置条件。尚未保存。") : L("修改后仍缺少：{0}", MissingText(result.Value)), ready ? InfoBarSeverity.Success : InfoBarSeverity.Warning);
    }

    private async Task SaveDraftAsync()
    {
        if (_state is not { } state)
            return;
        var draft = CollectDraft();
        if (draft.Set.Count == 0 && draft.Unset.Count == 0)
        {
            ShowNotice(L("没有更改"), L("尚未输入新值或选择清除。"), InfoBarSeverity.Informational);
            return;
        }
        var result = await RequestAsync("config.apply", new { set = draft.Set, unset = draft.Unset, revision = Text(state, "revision") }, L("无法保存配置。"));
        if (result is null)
            return;
        if (!Bool(result.Value, "ok"))
        {
            var errorType = Text(result.Value, "error_type", "unknown_error");
            if (errorType.Contains("conflict", StringComparison.OrdinalIgnoreCase))
                ShowNotice(L("配置已变更"), L("其他进程更新了配置。你的修改已保留，请刷新后重新确认。"), InfoBarSeverity.Warning);
            else
                ShowNotice(L("未保存"), L("{0} 原配置未被 App 覆盖。", Text(result.Value, "error", L("后端拒绝了本次配置（{0}）。", errorType))), InfoBarSeverity.Error);
            return;
        }
        _providerDraft.Clear();
        _fieldEditors.Clear();
        _configSnapshotStale = true;
        RenderProviderDetail();
        if (await RefreshStateAsync(preserveDraft: false))
            ShowNotice(L("已保存"), L("新配置会用于下一次任务；已经开始的任务继续使用它自己的配置快照。"), InfoBarSeverity.Success);
        else
            ShowNotice(L("配置已保存"), L("配置已保存，但暂未读回最新状态。请刷新后继续编辑。"), InfoBarSeverity.Warning);
    }

    private async Task TestProviderDraftAsync(string provider)
    {
        var draft = CollectDraft(provider);
        var overrides = draft.Set.ToDictionary(item => item.Key, item => Convert.ToString(item.Value, System.Globalization.CultureInfo.InvariantCulture) ?? string.Empty);
        foreach (var key in draft.Unset)
            overrides[key] = string.Empty;
        var result = await RequestAsync("provider.test", new { provider, overrides }, L("无法启动测试。"));
        if (result is null)
            return;
        RegisterOwnedRun(Text(result.Value, "run_id"), "provider.test", "test:" + provider);
        if (overrides.Count > 0)
            ShowNotice(L("正在测试未保存的修改"), L("这次测试不会保存配置。结果会显示在对应服务商下方。"), InfoBarSeverity.Informational);
    }

    private async Task RefreshOwnedRunsAsync()
    {
        if (_recoveringRuns || !_backend.IsConnected) return;
        _recoveringRuns = true;
        try
        {
            foreach (var runId in _ownedRunStatus.Where(item => !IsTerminal(item.Value)).Select(item => item.Key).ToArray())
                await RecoverRunAsync(runId);
        }
        finally { _recoveringRuns = false; }
    }

    private async Task CancelOwnedRunAsync(string runId)
    {
        if (!_ownedRuns.Contains(runId))
            return;
        var result = await RequestAsync("run.cancel", new { run_id = runId }, L("无法取消该任务。"));
        if (result is not null)
        {
            _ownedRunStatus[runId] = Text(result.Value, "status", "cancelling");
            if (!IsTerminal(_ownedRunStatus[runId])) _operations.TrackRun("cancel:" + runId, runId);
            ShowNotice(L("正在取消"), L("取消请求已发送。最终状态会由后端运行事件确认。"), InfoBarSeverity.Informational);
        }
    }

    private async Task LoadCliStatusAsync()
    {
        var result = await RequestAsync("cli.status", new { }, L("无法读取 CLI 状态。"));
        if (result is { } cli && _state is { } state)
        {
            var snapshot = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(state.GetRawText())!;
            snapshot["cli"] = cli.Clone();
            _state = JsonSerializer.SerializeToElement(snapshot);
        }
        RenderCliState();
    }

    private async Task LoadSkillsAsync()
    {
        await SkillsRequestAsync("skills.catalog");
    }

    private async Task SkillsRequestAsync(string method, object? parameters = null)
    {
        var result = await RequestAsync(method, parameters ?? new { }, L("Skills 操作未完成。"));
        if (result is not null) { _skills = result.Value.Clone(); RenderSkillState(); }
    }

    private async Task InstallSelectedSkillsAsync()
    {
        var targets = SkillTargetsToUpdate();
        if (targets.Length == 0) return;
        await SkillsRequestAsync("skills.update", new { targets, confirm = true });
    }

    private async Task SelectConfigDirectoryAsync()
    {
        var folder = await PickFolderAsync();
        if (folder is not null) await SwitchConfigDirectoryAsync(folder.Path);
    }

    private Task RestoreDefaultConfigDirectoryAsync()
    {
        var directory = Text(_state, "default_config_dir");
        return directory.Length > 0 && !Bool(_state, "is_default_config_dir")
            ? SwitchConfigDirectoryAsync(directory) : Task.CompletedTask;
    }

    private async Task SwitchConfigDirectoryAsync(string directory)
    {
        if (_providerDraft.Count > 0 && !await ConfirmAsync(L("切换配置目录"), L("当前还有未保存的修改。切换目录将放弃这些修改。"), L("放弃并切换"))) return;
        var result = await RequestAsync("profile.select", new { config_dir = directory }, L("无法切换配置目录。"));
        if (result is not null)
        {
            _providerDraft.Clear();
            _fieldEditors.Clear();
            ApplyState(result.Value);
            ShowNotice(L("已切换配置目录"), L("已读取所选目录的配置。"), InfoBarSeverity.Success);
            RenderCurrentPage();
        }
    }

    private string AppUpdateActionLabel() => !_appUpdater.Installed ? L("下载安装版") :
        _appUpdater.Available ? L("更新") : _appUpdater.Error.Length > 0 ? L("重试") : L("检查更新");

    private async Task AppUpdateActionAsync()
    {
        if (!_appUpdater.Installed)
            await Launcher.LaunchUriAsync(new Uri(AppUpdater.Repository + "/releases/latest"));
        else if (_appUpdater.Available) await InstallUpdateAsync();
        else await CheckNativeAppAsync();
    }

    private async Task CheckNativeAppAsync()
    {
        if (_appUpdater.Checking || _appUpdater.Downloading || _installingApp) return;
        SaveSetting("appUpdateLastAttempt", DateTimeOffset.UtcNow.ToUnixTimeSeconds().ToString());
        var check = _appUpdater.CheckAsync();
        RenderUpdateState();
        await check;
        RenderUpdateState();
    }

    private async Task CheckAppAutomaticallyAsync()
    {
        if (_shuttingDown || _state is null || !_appUpdater.Installed || !Bool(_updates, "auto_check", true)) return;
        var now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        if (!long.TryParse(ReadSetting("appUpdateLastAttempt"), out var last) || last > now || now - last >= 86400)
            await CheckNativeAppAsync();
        if (_shuttingDown || !Bool(_updates, "auto_check", true)) return;
        if (_appUpdater.Available && !_appUpdater.Downloading && !_installingApp && !AppInstallBlocked &&
            !_dialogOpen && _promptedAppVersion != _appUpdater.LatestVersion)
        {
            _promptedAppVersion = _appUpdater.LatestVersion;
            ShowMainWindow();
            if (await ConfirmAsync(L("发现 App 新版本"), L("{0} → {1}。现在更新，或稍后在设置中处理。", _appUpdater.CurrentVersion, _appUpdater.LatestVersion), L("现在更新"), L("稍后")))
                await RunOperationAsync("updates-install", InstallUpdateAsync);
        }
    }

    private async Task UpdateRequestAsync(string method, object? parameters = null)
    {
        var result = await RequestAsync(method, parameters ?? new { }, L("更新操作未完成。"));
        if (result is not null) { _updates = result.Value.Clone(); RenderUpdateState(); }
    }

    private void RenderUpdateState()
    {
        RenderCliState();
        if (_currentPage == "settings" && _appUpdateSummary is not null)
        {
            _settingAutoUpdate = true;
            if (_autoUpdateSwitch is not null) _autoUpdateSwitch.IsOn = Bool(_updates, "auto_check", true);
            _settingAutoUpdate = false;
            _appUpdateSummary.Text = _appUpdater.Downloading ? L("正在更新：{0}%", _appUpdater.Progress) :
                _appUpdater.Error.Length > 0 ? _appUpdater.Error : _appUpdater.Checking ? L("正在检查更新…") :
                !_appUpdater.Installed ? L("当前是测试包，安装版可在 App 内更新。") :
                _appUpdater.Available ? L("可更新到 {0}", _appUpdater.LatestVersion) :
                _appUpdater.CheckedAt is null ? L("尚未检查更新") : L("已是最新版本");
            if (_appUpdater.Available && AppInstallBlocked && !_appUpdater.Downloading)
                _appUpdateSummary.Text += "\n" + L("请先保存修改并结束当前操作，再更新 App。");
            _downloadProgress!.Visibility = _appUpdater.Downloading ? Visibility.Visible : Visibility.Collapsed;
            _downloadProgress.Value = _appUpdater.Progress;
            if (_appCancelButton is not null) _appCancelButton.Visibility = _appUpdater.Downloading ? Visibility.Visible : Visibility.Collapsed;
        }
        RefreshActionButtons();
    }

    private async Task UpdateCliAsync()
    {
        if (EnvironmentBusy) return;
        await UpdateRequestAsync("cli.update", new { confirm = true, version = Text(Property(_updates, "cli"), "latest_version") });
    }

    private async Task InstallUpdateAsync()
    {
        if (_shuttingDown || _installingApp || _appUpdater.Downloading || !_appUpdater.Available) return;
        if (AppInstallBlocked)
        {
            ShowNotice(L("暂不能安装"), L("请先保存或处理配置修改，并等待或取消 App 自有任务。"), InfoBarSeverity.Warning);
            return;
        }
        if (!_appUpdater.Ready)
        {
            using var cancellation = new CancellationTokenSource();
            _appDownloadCancellation = cancellation;
            try
            {
                await _appUpdater.DownloadAsync(() => DispatcherQueue.TryEnqueue(RenderUpdateState), cancellation.Token);
            }
            finally { _appDownloadCancellation = null; }
            RenderUpdateState();
        }
        if (!_appUpdater.Ready) return;
        if (AppInstallBlocked)
        {
            ShowNotice(L("更新已就绪"), L("请先处理正在进行的任务或未保存修改，再点击更新重启。"), InfoBarSeverity.Informational);
            return;
        }
        _installingApp = true;
        RefreshActionButtons();
        var ready = await RequestAsync("app.update-prepare", new { }, L("暂不能安装"));
        if (ready is null) { _installingApp = false; RefreshActionButtons(); return; }
        _shuttingDown = true;
        _maintenanceTimer.Stop();
        try
        {
            if (_providerDraft.Count > 0) throw new InvalidOperationException(L("请先处理正在进行的任务或未保存修改，再点击更新重启。"));
            await _backend.StopAsync();
            App.ReleaseInstallerMutex();
            _appUpdater.ApplyAndRestart();
        }
        catch
        {
            App.RestoreInstallerMutex();
            _shuttingDown = false;
            _installingApp = false;
            await ConnectAsync();
            ShowNotice(L("更新未完成"), L("已恢复 App 连接，请重新检查更新。"), InfoBarSeverity.Error);
        }
    }

    private void OnBackendEvent(object? sender, BackendEvent backendEvent)
    {
        DispatcherQueue.TryEnqueue(async () =>
        {
            if (backendEvent.Name == "skills")
            {
                var completedCheck = Bool(_skills, "checking") && !Bool(backendEvent.Data, "checking");
                _skills = backendEvent.Data.Clone();
                RenderSkillState();
                if (completedCheck && !Bool(_skills, "busy") && Text(_skills, "error").Length == 0 && Items(Property(_skills, "targets")).Any(item => Text(item, "status") == "stale"))
                    ShowNotice(L("Skills 可同步"), L("Skills 有可用更新，可在“CLI 与 Skills”中安装。"), InfoBarSeverity.Informational);
            }
            if (backendEvent.Name == "environment")
            {
                _environment = backendEvent.Data.Clone();
                if (_state is { } current && Property(_environment, "cli").ValueKind == JsonValueKind.Object)
                {
                    var snapshot = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(current.GetRawText())!;
                    snapshot["cli"] = Property(_environment, "cli").Clone();
                    _state = JsonSerializer.SerializeToElement(snapshot);
                }
                RenderEnvironmentState();
            }
            if (backendEvent.Name == "updates")
            {
                _updates = backendEvent.Data.Clone();
                var installed = Property(_updates, "installed_cli");
                if (_state is { } state && installed.ValueKind == JsonValueKind.Object)
                {
                    var snapshot = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(state.GetRawText())!;
                    snapshot["cli"] = installed.Clone();
                    _state = JsonSerializer.SerializeToElement(snapshot);
                }
                RenderUpdateState();
            }
            if (backendEvent.Name.Equals("run", StringComparison.OrdinalIgnoreCase))
                await FinishOwnedRunAsync(backendEvent.Data);
        });
    }

    private async Task FinishOwnedRunAsync(JsonElement data)
    {
        var runId = Text(data, "run_id");
        if (!_ownedRuns.Contains(runId) || !_handlingRunResults.Add(runId)) return;
        try
        {
            var status = Text(data, "status", "running");
            _ownedRunStatus[runId] = status;
            if (!IsTerminal(status)) return;
            await LoadRunResultAsync(runId, data);
            _operations.EndRun(runId);
            if (_noticeTitle == L("正在测试未保存的修改") &&
                !_ownedRunStatus.Any(item => _ownedRunKinds.GetValueOrDefault(item.Key) == "provider.test" && !IsTerminal(item.Value)))
                ClearNotice();
            if (_ownedRunKinds.GetValueOrDefault(runId) == "provider.test")
                await RefreshProviderStateAfterTestAsync();
            else if (_ownedRunKinds.GetValueOrDefault(runId) == "skills.install" && _currentPage == "ai")
                await RunOperationAsync("skills-status", LoadSkillsAsync);
            RefreshActionButtons();
        }
        finally { _handlingRunResults.Remove(runId); }
    }

    private async Task RefreshProviderStateAfterTestAsync()
    {
        var refreshed = await RequestAsync("get_state", new { }, L("无法刷新测试结果。"));
        if (refreshed is null) return;
        if (_state is { } current)
        {
            var snapshot = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(current.GetRawText())!;
            snapshot["provider_checks"] = Property(refreshed.Value, "provider_checks").Clone();
            snapshot["provider_health"] = Property(refreshed.Value, "provider_health").Clone();
            _state = JsonSerializer.SerializeToElement(snapshot);
        }
        // Keep the live editors, focus, disclosure state and scroll position intact.
        RefreshActionButtons();
    }

    private void OnBackendDisconnected(object? sender, string message) =>
        DispatcherQueue.TryEnqueue(() =>
        {
            if (_shuttingDown) return;
            _connectionFailed = true;
            _maintenanceTimer.Stop();
            _operations.Clear();
            _environment = JsonSerializer.SerializeToElement(new { status = "failed", busy = false, can_cancel = false,
                message = L("连接已断开，操作结果尚未确认；请重新打开 App 后重试。") });
            foreach (var runId in _ownedRunStatus.Keys.ToArray())
                if (!IsTerminal(_ownedRunStatus[runId])) _ownedRunStatus[runId] = "interrupted";
            _state = null;
            ShowNotice(L("本地引擎已断开"), message, InfoBarSeverity.Error);
            RenderCurrentPage();
        });

    private async Task LoadRunResultAsync(string runId, JsonElement eventData)
    {
        JsonElement result;
        if (eventData.TryGetProperty("result", out var embedded) && embedded.ValueKind != JsonValueKind.Null)
            result = embedded.Clone();
        else
        {
            var response = await RequestAsync("run.result", new { run_id = runId }, L("无法读取任务结果。"));
            if (response is null || !response.Value.TryGetProperty("result", out var fetched) || fetched.ValueKind == JsonValueKind.Null)
                return;
            result = fetched.Clone();
        }
        _ownedRunResults[runId] = result.Clone();
        if (IsSearchRun(runId) && _selectedResultRunId == runId && _resultText is not null)
        {
            _selectedResultRunId = runId;
            RenderResult(result);
        }
    }

    private void RenderResult(JsonElement result)
    {
        if (_currentPage != "search" || _resultText is null || _rawResult is null || _sourceRows is null)
            return;
        if (_searchResultHost is not null) _searchResultHost.Content = _searchResultContent;
        _resultText.Text = ReadableResult(result);
        _rawResult.Text = JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
        _lastResultExport = _resultText.Text;
        _sourceRows.Children.Clear();
        foreach (var source in Items(result, "sources"))
        {
            var url = Text(source, "url", Text(source, "link"));
            if (Uri.TryCreate(url, UriKind.Absolute, out var uri) && (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
            {
                var title = Text(source, "title", Text(source, "name", uri.Host));
                var label = title == uri.Host ? title : $"{title} · {uri.Host}";
                var link = new HyperlinkButton
                {
                    Content = new TextBlock { Text = label, TextWrapping = TextWrapping.Wrap }, NavigateUri = uri,
                    HorizontalAlignment = HorizontalAlignment.Stretch, HorizontalContentAlignment = HorizontalAlignment.Left
                };
                ToolTipService.SetToolTip(link, uri.AbsoluteUri);
                _sourceRows.Children.Add(link);
            }
        }
        _sourceDisclosure!.Header = L("来源链接（{0}）", _sourceRows.Children.Count);
        _sourceDisclosure.Visibility = _sourceRows.Children.Count == 0 ? Visibility.Collapsed : Visibility.Visible;
        RefreshActionButtons();
    }

    private Task CopyResult()
    {
        if (string.IsNullOrWhiteSpace(_resultText?.Text))
        {
            ShowNotice(L("没有可复制的结果"), L("先运行一个工具并等待结果。"), InfoBarSeverity.Informational);
            return Task.CompletedTask;
        }
        CopyText(_resultText.Text);
        ShowNotice(L("已复制"), L("已复制当前可读结果。"), InfoBarSeverity.Success);
        return Task.CompletedTask;
    }

    private async Task ExportResultAsync()
    {
        if (string.IsNullOrWhiteSpace(_lastResultExport))
        {
            ShowNotice(L("没有可导出的结果"), L("先运行一个工具并等待结果。"), InfoBarSeverity.Informational);
            return;
        }
        var picker = new FileSavePicker();
        InitializeWithWindow.Initialize(picker, _windowHandle);
        picker.FileTypeChoices.Add(L("文本文件"), [".txt"]);
        picker.SuggestedFileName = "smart-search-result";
        var file = await picker.PickSaveFileAsync();
        if (file is not null)
        {
            await FileIO.WriteTextAsync(file, _lastResultExport);
            ShowNotice(L("已导出"), L("结果已写入你选择的文件。"), InfoBarSeverity.Success);
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

    private void RegisterOwnedRun(string runId, string kind, string operationKey)
    {
        if (string.IsNullOrWhiteSpace(runId)) return;
        _ownedRuns.Add(runId);
        _ownedRunStatus[runId] = "running";
        _ownedRunKinds[runId] = kind;
        _operations.TrackRun(operationKey, runId);
        RefreshActionButtons();
        _ = RecoverRunAsync(runId);
    }

    private async Task RecoverRunAsync(string runId)
    {
        // A very fast worker can finish before the start response reaches the UI.
        var response = await RequestAsync("run.result", new { run_id = runId }, L("无法读取任务状态。"));
        if (response is { } data) await FinishOwnedRunAsync(data);
    }

    private bool SearchRunning => _selectedResultRunId is { } id && !IsTerminal(_ownedRunStatus.GetValueOrDefault(id, "finished"));
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
        if (_shuttingDown || _installingApp || _dialogOpen)
            return;
        if (_appUpdater.Downloading)
        {
            ShowNotice(L("更新下载中"), L("请先取消更新下载或等待完成，再退出。"), InfoBarSeverity.Warning);
            return;
        }
        if (EnvironmentBusy || Bool(_skills, "busy") || _operations.IsBusy("updates-cli") || Text(Property(_updates, "cli_update"), "status") == "running")
        {
            ShowNotice(L("安装或检查正在进行"), L("环境或 Skills 操作正在进行，请等待完成后退出。"), InfoBarSeverity.Warning);
            return;
        }
        if (HasActiveOwnedRuns)
        {
            var dialog = new ContentDialog
            {
                XamlRoot = DialogRoot,
                RequestedTheme = ((FrameworkElement)Content).ActualTheme,
                Title = L("仍有 Smart Search 任务在运行"),
                Content = L("继续后台运行可从通知区域恢复；取消任务并退出只会取消本 App 发起的任务，不会终止外部 CLI。"),
                PrimaryButtonText = L("继续在后台"),
                SecondaryButtonText = L("取消任务并退出"),
                CloseButtonText = L("返回")
            };
            _dialogOpen = true;
            ContentDialogResult choice;
            try { choice = await dialog.ShowAsync(); }
            finally { _dialogOpen = false; }
            switch (choice)
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
        _maintenanceTimer.Stop();
        _tray.Hide();
        await _backend.DisposeAsync();
        _tray.Dispose();
        _allowClose = true;
        Close();
    }

    private async Task<bool> ConfirmAsync(string title, string content, string confirm, string? cancel = null)
    {
        if (_dialogOpen) return false;
        var dialog = new ContentDialog
        {
            XamlRoot = DialogRoot,
            RequestedTheme = ((FrameworkElement)Content).ActualTheme,
            Title = title,
            Content = content,
            PrimaryButtonText = confirm,
            CloseButtonText = cancel ?? L("取消"),
            DefaultButton = ContentDialogButton.Close
        };
        _dialogOpen = true;
        try { return await dialog.ShowAsync() == ContentDialogResult.Primary; }
        finally { _dialogOpen = false; }
    }

    private XamlRoot DialogRoot => ((FrameworkElement)Content).XamlRoot;

    private static Style UiStyle(string key) => (Style)Application.Current.Resources[key];

    private static TextBlock PageTitle(string text) => new() { Text = text, Style = UiStyle("PageHeadingStyle") };
    private static TextBlock SectionHeading(string text) => new() { Text = text, Style = UiStyle("SectionHeadingStyle") };
    private static TextBlock Body(string text) => new() { Text = text, Style = UiStyle("BodyCopyStyle") };
    private static TextBlock Secondary(string text) => new() { Text = text, Style = UiStyle("SecondaryCopyStyle") };
    private static TextBlock DataText(string text) => new() { Text = text, Style = UiStyle("DataCopyStyle") };
    private static ContentControl Card(UIElement content) => new() { Content = content, Style = UiStyle("SurfaceCardStyle") };
    private static ContentControl Badge(string text, string tone) => new() { Content = text, Style = UiStyle("Status" + tone + "Style") };

    private static UIElement HeadingWithStatus(string heading, string status, string tone)
    {
        var row = new Grid { ColumnSpacing = 16 };
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        row.Children.Add(SectionHeading(heading));
        var badge = Badge(status, tone);
        Grid.SetColumn(badge, 1);
        row.Children.Add(badge);
        return row;
    }

    private static UIElement KeyValue(string label, string value) => new StackPanel
    {
        Spacing = 6, Children = { Secondary(label), DataText(value) }
    };

    private static UIElement Section(string heading, IEnumerable<UIElement> children)
    {
        var panel = new StackPanel { Spacing = 12 };
        panel.Children.Add(SectionHeading(heading));
        foreach (var child in children) panel.Children.Add(child);
        return panel;
    }

    private Expander Disclosure(string key, string heading, UIElement content, bool expanded = false)
    {
        var expander = new Expander
        {
            Header = heading, Content = content, IsExpanded = _disclosures.GetValueOrDefault(key, expanded),
            HorizontalAlignment = HorizontalAlignment.Stretch, HorizontalContentAlignment = HorizontalAlignment.Stretch
        };
        expander.Expanding += (_, _) => _disclosures[key] = true;
        expander.Collapsed += (_, _) => _disclosures[key] = false;
        return expander;
    }

    private static UIElement FieldRow(UIElement label, UIElement input)
    {
        var row = new Grid { ColumnSpacing = 20 };
        row.ColumnDefinitions.Add(new ColumnDefinition());
        row.ColumnDefinitions.Add(new ColumnDefinition());
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        row.Children.Add(label);
        row.Children.Add(input);
        row.SizeChanged += (_, args) =>
        {
            var wide = args.NewSize.Width >= 640;
            row.RowSpacing = wide ? 0 : 8;
            row.ColumnDefinitions[0].Width = wide ? new GridLength(220) : new GridLength(1, GridUnitType.Star);
            row.ColumnDefinitions[1].Width = wide ? new GridLength(1, GridUnitType.Star) : new GridLength(0);
            Grid.SetColumn((FrameworkElement)input, wide ? 1 : 0);
            Grid.SetRow((FrameworkElement)input, wide ? 0 : 1);
        };
        return row;
    }

    private static Panel ActionRow(params UIElement[] children)
    {
        var row = new ActionPanel();
        foreach (var child in children) row.Children.Add(child);
        return row;
    }

    private static IEnumerable<UIElement> CapabilityChains(JsonElement state)
    {
        var chains = Property(state, "capability_chains");
        if (chains.ValueKind != JsonValueKind.Object) yield break;
        foreach (var chain in chains.EnumerateObject())
            yield return KeyValue(CapabilityLabel(chain.Name) + L("回退顺序"), string.Join(" → ", Items(chain.Value).Select(value => ProviderLabel(value.GetString() ?? ""))));
    }

    private static TextBlock OfflineHint() => Secondary(L("本地引擎未连接。请先重新连接，再读取配置和运行任务。"));

    private Button ActionButton(string text, Func<Task> action, bool primary = false, string? operationKey = null,
        string? busyText = null, Func<string>? label = null, Func<string>? dynamicKey = null, Func<bool>? enabled = null)
    {
        busyText ??= L("处理中…");
        var button = new Button { MinHeight = 36, HorizontalAlignment = HorizontalAlignment.Left };
        if (primary) button.Style = UiStyle("AccentButtonStyle");
        var actionKey = operationKey ?? "ui:" + Guid.NewGuid().ToString("N");
        var binding = new ActionBinding(dynamicKey ?? (() => actionKey), label ?? (() => text), busyText, enabled);
        _actionButtons[button] = binding;
        button.Loaded += (_, _) => { _actionButtons[button] = binding; UpdateActionButton(button, binding); };
        button.Unloaded += (_, _) => _actionButtons.Remove(button);
        UpdateActionButton(button, binding);
        button.Click += async (_, _) => await RunOperationAsync(binding.Key(), action);
        return button;
    }

    private async Task RunOperationAsync(string key, Func<Task> action)
    {
        if (_installingApp || _shuttingDown) return;
        if (new[] { "state", "config-save", "config-preview", "config-discard", "profile" }.Contains(key) && ConfigOperationBusy) return;
        if (!_operations.Begin(key)) return;
        RefreshActionButtons();
        try { await action(); }
        catch (Exception error) { ShowNotice(L("操作未完成"), SafeMessage(error), InfoBarSeverity.Error); }
        finally { _operations.EndRequest(key); RefreshActionButtons(); }
    }

    private bool ConfigOperationBusy => new[] { "state", "config-save", "config-preview", "config-discard", "profile" }.Any(_operations.IsBusy);

    private string[] SkillTargetsToUpdate() => Items(Property(_skills, "targets"))
        .Where(item => _selectedSkillTargets.Contains(Text(item, "target")))
        .Select(item => Text(item, "target")).ToArray();

    private void UpdateActionButton(Button button, ActionBinding binding)
    {
        var key = binding.Key();
        var downloading = _appUpdater.Downloading;
        var updatingCli = Text(Property(_updates, "cli_update"), "status") == "running";
        var busy = _operations.IsBusy(key) ||
            key == "skills-install" && (Bool(_skills, "busy") || Bool(_skills, "checking")) ||
            key == "cli-manage" && (EnvironmentBusy || updatingCli || Bool(_updates, "checking")) ||
            key is "app-update" or "updates-install" && (_appUpdater.Checking || downloading);
        var allowed = key switch
        {
            "profile" => _backend.IsConnected,
            "config-save" or "config-discard" => _backend.IsConnected && !_configSnapshotStale && _providerDraft.Count > 0,
            "config-preview" => _backend.IsConnected && !_configSnapshotStale,
            "result-copy" or "result-export" => !string.IsNullOrWhiteSpace(_lastResultExport),
            "skills-install" => SkillsSelectionPolicy.CanUpdate(_state is not null, SkillTargetsToUpdate().Length,
                Bool(_skills, "busy") || Bool(_skills, "checking") || EnvironmentBusy || updatingCli),
            "skills-status" => _state is not null && !Bool(_skills, "busy") && !EnvironmentBusy && !updatingCli,
            "cli-manage" => _state is not null && !Bool(_skills, "busy") && !EnvironmentBusy && !updatingCli,
            "environment-cancel" => Bool(_environment, "can_cancel"),
            "updates-cancel" => downloading,
            "app-update" => !_appUpdater.Available || !AppInstallBlocked,
            "updates-install" => _appUpdater.Available && !AppInstallBlocked,
            _ => true
        };
        if (EnvironmentBusy && new[] { "cli-manage", "app-update", "updates-install", "connect", "profile", "skills-install" }.Contains(key)) allowed = false;
        if (Bool(_skills, "busy") && new[] { "cli-manage", "app-update", "updates-install", "connect", "profile" }.Contains(key)) allowed = false;
        button.IsEnabled = !_installingApp && allowed && (binding.Enabled?.Invoke() ?? true) && !busy && !(new[] { "state", "config-save", "config-preview", "config-discard", "profile" }.Contains(key) && ConfigOperationBusy);
        var label = busy ? binding.BusyText : binding.Label();
        if (busy)
            button.Content = new StackPanel
            {
                Orientation = Orientation.Horizontal, Spacing = 8,
                Children = { new ProgressRing { IsActive = true, Width = 16, Height = 16 }, new TextBlock { Text = label } }
            };
        else button.Content = label;
        AutomationProperties.SetName(button, label);
    }

    private void RefreshActionButtons()
    {
        RootNavigation.IsEnabled = !_installingApp && !_shuttingDown;
        foreach (var (button, binding) in _actionButtons.ToArray()) UpdateActionButton(button, binding);
        if (_currentPage == "providers")
        {
            var changes = CollectDraft();
            var count = changes.Set.Count + changes.Unset.Count;
            if (_saveSummary is not null)
                _saveSummary.Text = count > 0 ? L("有 {0} 项未保存修改 · 密钥留空会保留原值", count) : L("没有未保存的修改 · 测试不会自动保存配置");
            foreach (var group in ConfigurationFields.Where(field => Text(field, "provider").Length > 0).GroupBy(field => Text(field, "provider")))
                if (_providerRowStatus.TryGetValue("provider:" + group.Key, out var status)) status.Text = ProviderListStatus(group.Key, group);
            if (_providerRowStatus.TryGetValue("section:routing", out var routingStatus))
                routingStatus.Text = ChoiceLabel("SMART_SEARCH_INTENT_ROUTER", EffectiveConfigurationValue("SMART_SEARCH_INTENT_ROUTER"));
            foreach (var editor in _fieldEditors.Values)
            {
                editor.Input.IsEnabled = !_operations.IsBusy("config-save") && !(editor.Locked && editor.Input is ToggleSwitch);
                if (editor.Clear is not null) editor.Clear.IsEnabled = !_operations.IsBusy("config-save");
            }
            if (_state is { } state)
                foreach (var (provider, host) in _providerStatusPanels)
                {
                    var updated = BuildProviderStatus(state, provider);
                    var children = updated.Children.ToArray();
                    updated.Children.Clear();
                    host.Children.Clear();
                    foreach (var child in children) host.Children.Add(child);
                }
        }
    }

    private string ProviderTestLabel(string provider)
    {
        var draft = CollectDraft(provider);
        if (Text(Property(_state, "probe_kinds"), provider) == "presence")
            return draft.Set.Count + draft.Unset.Count > 0 ? L("检查未保存的配置") : L("检查配置");
        return draft.Set.Count + draft.Unset.Count > 0 ? L("用未保存的修改测试") : L("测试");
    }

    private Control CreateFieldInput(JsonElement field, bool secret, string value, bool isLocked)
    {
        if (isLocked)
            return new TextBox { Text = secret ? (HasSavedSecret(field) ? "••••••••" : L("未设置")) : value, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, FontFamily = new FontFamily("Consolas") };
        if (secret)
            return new PasswordBox { PlaceholderText = L("留空将保留当前密钥"), IsEnabled = true };
        if (Text(field, "kind").Equals("bool", StringComparison.OrdinalIgnoreCase))
            return new ToggleSwitch { IsOn = value.Equals("true", StringComparison.OrdinalIgnoreCase) || value.Equals(L("是"), StringComparison.OrdinalIgnoreCase) };
        var choices = Items(field, "choices").Where(choice => choice.ValueKind == JsonValueKind.String).Select(choice => choice.GetString()!).ToList();
        if (choices.Count > 0)
        {
            var combo = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
            foreach (var choice in choices)
                combo.Items.Add(new ConfigurationChoice(choice, ChoiceLabel(Text(field, "key"), choice)));
            combo.SelectedItem = combo.Items.OfType<ConfigurationChoice>().FirstOrDefault(choice => choice.Value.Equals(value, StringComparison.OrdinalIgnoreCase)) ?? combo.Items.FirstOrDefault();
            return combo;
        }
        return new TextBox { Text = value, PlaceholderText = Text(field, "placeholder", Text(field, "default")), TextWrapping = TextWrapping.Wrap, FontFamily = new FontFamily("Consolas") };
    }

    private Control CreateCommandInput(JsonElement field)
    {
        var kind = Text(field, "kind");
        if (kind.Equals("bool", StringComparison.OrdinalIgnoreCase))
            return new ToggleSwitch();
        var choices = Items(field, "choices").Where(choice => choice.ValueKind == JsonValueKind.String).Select(choice => choice.GetString()!).ToList();
        if (kind.Equals("choice", StringComparison.OrdinalIgnoreCase) && choices.Count > 0)
        {
            var combo = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
            foreach (var choice in choices)
                combo.Items.Add(choice);
            if (!string.IsNullOrWhiteSpace(Text(field, "default")))
                combo.SelectedItem = Text(field, "default");
            return combo;
        }
        return new TextBox
        {
            Text = Text(field, "default"),
            PlaceholderText = Bool(field, "multiple") ? L("每行一个值") : string.Empty,
            AcceptsReturn = Bool(field, "multiple"),
            TextWrapping = TextWrapping.Wrap
        };
    }

    private DraftChange CollectDraft(string? provider = null)
    {
        _providerDraft = CaptureDraft();
        var set = new Dictionary<string, object?>();
        var unset = new List<string>();
        foreach (var field in ConfigurationFields)
        {
            var key = Text(field, "key");
            if (!_providerDraft.TryGetValue(key, out var draft) ||
                Text(Property(_state, "sources"), key).Equals("environment", StringComparison.OrdinalIgnoreCase) ||
                (provider is not null && Text(field, "provider") != provider)) continue;
            if (draft.Clear) unset.Add(key);
            else set[key] = ConvertValue(field, new CommandValue(draft.Text, draft.IsChecked));
        }
        return new DraftChange(set, unset);
    }

    private Dictionary<string, FieldDraft> CaptureDraft()
    {
        // Editors represent only the selected detail. Other drafts belong to the page model.
        var captured = new Dictionary<string, FieldDraft>(_providerDraft, StringComparer.Ordinal);
        foreach (var (key, editor) in _fieldEditors)
        {
            var value = ReadEditorValue(editor);
            if (HasDraftChange(editor, value)) captured[key] = new FieldDraft(value.Text, value.IsChecked, editor.Clear?.IsOn == true);
            else captured.Remove(key);
        }
        return captured;
    }

    private static bool HasDraftChange(FieldEditor editor, CommandValue value) =>
        !editor.Locked && (editor.Clear?.IsOn == true ||
                           (editor.Secret ? !string.IsNullOrWhiteSpace(value.Text) : !ControlValueComparer.Equal(value, editor.Initial)));

    private static void RestoreDraft(FieldEditor editor, FieldDraft draft)
    {
        var value = draft.Clear && !editor.Secret
            ? new CommandValue(Text(editor.Field, "default"), ConfigurationBoolean(Text(editor.Field, "default")))
            : new CommandValue(draft.Text, draft.IsChecked);
        RestoreControl(editor.Input, value);
        if (editor.Clear is not null) editor.Clear.IsOn = draft.Clear;
    }

    private void CaptureCommandInputs()
    {
        if (_renderedCommandId is not null && _commandControls.Count > 0)
            _commandDrafts[_renderedCommandId] = _commandControls.ToDictionary(item => item.Key, item => ReadControl(item.Value));
    }

    private static void RestoreControl(Control input, CommandValue value)
    {
        switch (input)
        {
            case TextBox textBox: textBox.Text = value.Text ?? string.Empty; break;
            case PasswordBox passwordBox: passwordBox.Password = value.Text ?? string.Empty; break;
            case ComboBox comboBox:
                comboBox.SelectedItem = comboBox.Items.OfType<ConfigurationChoice>().FirstOrDefault(choice => choice.Value == value.Text) ?? (object?)value.Text;
                break;
            case ToggleSwitch toggle: toggle.IsOn = value.IsChecked; break;
        }
    }

    private static CommandValue ReadEditorValue(FieldEditor editor) => ReadControl(editor.Input);

    private CommandValue ReadControl(string name) => _commandControls.TryGetValue(name, out var control) ? ReadControl(control) : new CommandValue(null);

    private static CommandValue ReadControl(Control control) => control switch
    {
        TextBox textBox => new CommandValue(textBox.Text),
        PasswordBox passwordBox => new CommandValue(passwordBox.Password),
        ComboBox comboBox => new CommandValue(comboBox.SelectedItem is ConfigurationChoice choice ? choice.Value : comboBox.SelectedItem?.ToString()),
        ToggleSwitch toggle => new CommandValue(null, toggle.IsOn),
        _ => new CommandValue(null)
    };

    private static object? ConvertValue(JsonElement field, CommandValue value)
    {
        var kind = Text(field, "kind").ToLowerInvariant();
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

    private static string Label(JsonElement field) => Text(field, "label_" + Localization.Language, Text(field, "label_en", Text(field, "key")));

    private static string SourceLabel(string source) => source.ToLowerInvariant() switch
    {
        "environment" => L("环境变量"),
        "config_file" => L("配置文件"),
        "default" => L("默认值"),
        _ => string.IsNullOrWhiteSpace(source) ? L("未知") : source
    };

    private static string MissingText(JsonElement value)
    {
        var missing = Items(value, "missing").Where(item => item.ValueKind == JsonValueKind.String).Select(item => item.GetString()).Where(item => !string.IsNullOrWhiteSpace(item));
        return string.Join("、", missing.Select(value => CapabilityLabel(value!))) is { Length: > 0 } text ? text : L("未说明");
    }

    private static string CapabilityLabel(string capability) => capability switch
    {
        "main_search" => L("主搜索"),
        "web_search" => L("网页搜索"),
        "docs_search" => L("文档检索"),
        "web_fetch" => L("网页抓取"),
        "vertical_search" => L("垂直检索"),
        "site_map" => L("站点地图"), "synthesis" => L("结果汇总"), "other" => L("其他能力"),
        _ => capability
    };

    private string ProviderCheckLabel(string status)
    {
        var label = Text(Property(Property(Property(_state, "metadata"), "status_labels"), status.ToLowerInvariant()), Localization.Language);
        if (!string.IsNullOrWhiteSpace(label)) return label;
        return status.ToLowerInvariant() switch
        {
            "ok" or "passed" or "success" => L("通过"),
            "failed" or "error" => L("未通过"),
            "cancelled" => L("已取消"),
            "timeout" => L("超时"),
            "not_configured" => L("未配置"),
            "config_error" or "parameter_error" => L("配置需调整"),
            "auth_error" => L("凭据不可用"),
            "rate_limit" or "rate_limited" => L("请求受限"),
            "network_error" => L("网络异常"),
            "warning" => L("需要确认"),
            "runtime_error" or "interrupted" => L("已中断"),
            "running" => L("测试中"),
            "closed" => L("已结束（不推断成功）"),
            _ => L("状态未知")
        };
    }

    private static string StatusTone(string status) => status.ToLowerInvariant() switch
    {
        "ok" or "passed" or "success" or "finished" or "up_to_date" => "Success",
        "running" or "cancelling" => "Active",
        "timeout" or "warning" or "stale" or "rate_limit" or "rate_limited" or "configured" or "not_configured" => "Warning",
        "error" or "failed" or "interrupted" => "Error",
        _ when status.EndsWith("_error", StringComparison.OrdinalIgnoreCase) => "Error",
        _ => "Neutral"
    };

    private static string ProviderLabel(string provider) => provider switch
    {
        "openai-compatible" => L("OpenAI 兼容接口"), "xai-responses" => "xAI", "exa" => "Exa",
        "context7" => "Context7", "tavily" => "Tavily", "jina" => "Jina", "firecrawl" => "Firecrawl",
        "zhipu" => L("智谱"), "zhipu-mcp" => L("智谱 Coding Plan"), "zhipu-mcp-reader" => L("智谱网页阅读"),
        "anysearch" => L("AnySearch · 实验性"), "sciverse" => L("SciVerse · 实验性"), _ => provider
    };

    private string CommandLabel(string command) => command switch
    {
        "provider.test" => L("服务商测试"), "skills.install" => L("安装 / 更新 Skills"), "version" => L("版本查询"),
        "config" => L("配置管理"), "skills" => L("Skills 管理"), "providers" => L("服务商检查"), "model" => L("模型设置"),
        _ => Items(Property(_state, "commands")).Where(item => Text(item, "id") == command).Select(item => Text(item, "label")).FirstOrDefault() ?? L("其他任务")
    };

    private static string PhaseLabel(string phase) => phase switch
    {
        "started" or "starting" => L("已启动"), "running" => L("运行中"), "completed" or "finished" => L("已完成"),
        "failed" => L("失败"), "cancelled" => L("已取消"), "cancelling" => L("取消中"),
        "provider.test" => L("测试连接"), "search" or "main_search" => L("搜索"), "fetch" or "web_fetch" => L("读取网页"),
        "routing" or "route" => L("选择检索方式"), "planning" or "deep" => L("制定计划"), "research" => L("研究"),
        _ => L("处理请求")
    };

    private static string CooldownText(JsonElement health)
    {
        var seconds = Number(health, "cooldown_remaining_seconds");
        return seconds > 0 ? TimeSpan.FromSeconds(seconds).ToString(@"mm\:ss") : L("未返回");
    }

    private static string StatusLabel(string status) => status.ToLowerInvariant() switch
    {
        "running" => L("运行中"),
        "finished" => L("已完成"),
        "failed" => L("失败"),
        "cancelled" => L("已取消"),
        "cancelling" => L("正在取消"),
        "stale" => L("状态未更新"),
        "interrupted" => L("已中断"),
        _ => L("未知")
    };

    private static string SkillStatusLabel(string status) => status.ToLowerInvariant() switch
    {
        "missing" => L("未安装"),
        "stale" => L("文件内容与来源不同"),
        "up_to_date" or "extra_files" => L("与来源一致"),
        "error" => L("读取失败"),
        _ => L("状态未知")
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
        return L("任务已返回结构化结果。展开“高级 JSON”可以查看完整字段；来源会列在本结果下方。");
    }

    private static string Elapsed(JsonElement run)
    {
        var milliseconds = Number(run, "elapsed_ms");
        return milliseconds <= 0 ? L("未返回") : TimeSpan.FromMilliseconds(milliseconds).ToString(@"mm\:ss");
    }

    private static string Timestamp(JsonElement value, string property)
    {
        var seconds = Number(value, property);
        return seconds <= 0 ? L("未返回") : DateTimeOffset.FromUnixTimeSeconds((long)seconds).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss");
    }

    private static string TimestampOrText(JsonElement value, string property)
    {
        var seconds = Number(value, property);
        return seconds > 0 ? DateTimeOffset.FromUnixTimeSeconds((long)seconds).ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss") : Text(value, property, L("未返回"));
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

    private void LoadLocalPreferences()
    {
        try
        {
            if (File.Exists(PreferencesPath))
            {
                foreach (var (key, value) in JsonSerializer.Deserialize<Dictionary<string, string>>(File.ReadAllText(PreferencesPath)) ?? [])
                    _preferences[key] = value;
            }
        }
        catch (Exception error) when (error is JsonException or IOException or UnauthorizedAccessException)
        {
            // An unreadable local preference is ignored instead of scanning unexpected paths.
            _preferenceReadFailed = true;
        }
    }

    private string? ReadSetting(string key) => _preferences.GetValueOrDefault(key);

    private bool SaveSetting(string key, string value)
    {
        _preferences[key] = value;
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(PreferencesPath)!);
            var temporary = PreferencesPath + ".tmp";
            File.WriteAllText(temporary, JsonSerializer.Serialize(_preferences));
            File.Move(temporary, PreferencesPath, overwrite: true);
            return true;
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException)
        {
            // The setting remains effective for this session even if its local persistence is unavailable.
            return false;
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

    private void ApplyNavigationLanguage()
    {
        RootNavigation.Language = Localization.Language == "zh" ? "zh-CN" : "en-US";
        AutomationProperties.SetName(AppLogo, L("Smart Search 图标"));
        var titles = new Dictionary<string, string>
        {
            ["providers"] = L("配置"), ["search"] = L("测试"),
            ["ai"] = L("CLI 与 Skills"), ["settings"] = L("设置")
        };
        foreach (var item in RootNavigation.MenuItems.OfType<NavigationViewItem>())
            if (item.Tag is string key && titles.TryGetValue(key, out var title)) item.Content = title;
        if (_appWindow is not null)
            _appWindow.Title = Environment.GetCommandLineArgs().Contains("--backend") ? L("Smart Search · 测试窗口") : "Smart Search";
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
        OperationCanceledException => L("本地后端在 30 秒内没有响应。请检查后端后手动重试。"),
        _ => L("操作未完成。请检查连接或文件权限后重试。")
    };

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
        public override string ToString() => Experimental ? L("{0}（实验性）", Label) : Label;
    }

    private sealed record FieldDraft(string? Text, bool IsChecked, bool Clear);
    private sealed record ActionBinding(Func<string> Key, Func<string> Label, string BusyText, Func<bool>? Enabled);

    private sealed record DraftChange(Dictionary<string, object?> Set, List<string> Unset);

    private sealed record FieldEditor(JsonElement Field, Control Input, ToggleSwitch? Clear, CommandValue Initial, bool Secret, bool Locked);

    private sealed record BackendLaunch(string? Path, IReadOnlyList<string> Arguments);
}
