using static SmartSearch.Desktop.Localization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Controls.Primitives;

namespace SmartSearch.Desktop;

public sealed partial class MainWindow
{
    private string _providerSelection = "section:routing";
    private string _providerFilter = string.Empty;
    private ListView? _providerList;
    private ContentControl? _providerDetail;
    private bool _refreshingProviderList;
    private bool _configSnapshotStale;
    private readonly Dictionary<string, TextBlock> _providerRowStatus = [];
    private static readonly string[] CapabilityOrder = ["main_search", "docs_search", "web_search", "web_fetch", "vertical_search", "site_map", "synthesis", "other"];

    private List<JsonElement> ConfigurationFields => Items(Property(Property(_state, "metadata"), "fields")).ToList();

    private Task NavigateToProvidersAsync(string? capability = null)
    {
        _providerFilter = capability is null ? string.Empty : CapabilityLabel(capability);
        if (capability is null) return NavigateToAsync("providers");
        var candidates = ConfigurationFields.Where(field => Text(field, "provider").Length > 0)
            .GroupBy(field => Text(field, "provider"))
            .Where(group => ProviderCapabilities(group.Key, group).Contains(capability))
            .Select(group => group.Key).ToList();
        var preferred = Items(Property(Property(_state, "capability_chains"), capability))
            .Select(item => item.GetString()).FirstOrDefault(id => id is not null && candidates.Contains(id));
        var provider = preferred ?? candidates.Order(StringComparer.OrdinalIgnoreCase).FirstOrDefault();
        _providerSelection = provider is null ? string.Empty : "provider:" + provider;
        return NavigateToAsync("providers");
    }

    private UIElement BuildProvidersPage(Dictionary<string, FieldDraft>? preservedDraft)
    {
        _fieldEditors.Clear();
        if (_state is null) return Scroll(Section(L("服务商"), [OfflineHint()]));
        var filter = new TextBox { PlaceholderText = L("查找服务商"), Text = _providerFilter, Margin = new Thickness(PageInset, PageInset, PageInset, 8) };
        AutomationProperties.SetName(filter, L("查找服务商"));
        filter.TextChanged += (_, _) => { _providerFilter = filter.Text; RenderProviderList(); };
        _providerList = new ListView { SelectionMode = ListViewSelectionMode.Single,
            Padding = new Thickness(12, 0, 12, 12), HorizontalContentAlignment = HorizontalAlignment.Stretch };
        AutomationProperties.SetName(_providerList, L("服务商"));
        _providerList.SelectionChanged += (_, _) =>
        {
            if (_refreshingProviderList || _providerList.SelectedItem is not ListViewItem { Tag: string route }) return;
            _providerDraft = CaptureDraft();
            _providerSelection = route;
            RenderProviderDetail();
        };
        var navigation = new Grid();
        navigation.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        navigation.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        navigation.Children.Add(filter);
        Grid.SetRow(_providerList, 1);
        navigation.Children.Add(_providerList);
        _providerDetail = new ContentControl { HorizontalContentAlignment = HorizontalAlignment.Stretch, VerticalContentAlignment = VerticalAlignment.Stretch };
        RenderProviderList();
        RenderProviderDetail();
        var split = SplitWorkspace("providers", navigation, _providerDetail, 240, 208, 300);
        _saveSummary = Secondary(string.Empty);
        var actions = ActionRow(
            ActionButton(L("放弃修改"), DiscardProviderDraftAsync, operationKey: "config-discard"),
            ActionButton(L("检查配置"), PreviewDraftAsync, operationKey: "config-preview", busyText: L("检查中…")),
            ActionButton(L("保存更改"), SaveDraftAsync, primary: true, operationKey: "config-save", busyText: L("保存中…")));
        var footer = WorkspaceFooter(_saveSummary, actions);
        var layout = new Grid();
        layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        layout.Children.Add(split);
        Grid.SetRow(footer, 1);
        layout.Children.Add(footer);
        return layout;
    }

    private void RenderProviderList()
    {
        if (_providerList is null || _state is null) return;
        _refreshingProviderList = true;
        _providerList.Items.Clear();
        _providerRowStatus.Clear();
        var fields = ConfigurationFields;
        void AddItem(string route, string title, string? subtitle = null)
        {
            var label = new StackPanel { Spacing = 4 };
            label.Children.Add(Body(title));
            if (subtitle is not null)
            {
                var status = Secondary(subtitle);
                label.Children.Add(status);
                _providerRowStatus[route] = status;
            }
            var item = new ListViewItem { Content = label, Tag = route, Padding = new Thickness(12, 8, 12, 8), HorizontalContentAlignment = HorizontalAlignment.Stretch };
            AutomationProperties.SetName(item, title);
            _providerList.Items.Add(item);
            if (route == _providerSelection) _providerList.SelectedItem = item;
        }
        void AddHeading(string title) => _providerList.Items.Add(new ListViewItem
        {
            Content = Secondary(title), IsEnabled = false, IsTabStop = false, Padding = new Thickness(12, 16, 12, 4)
        });
        bool Matches(string text) => string.IsNullOrWhiteSpace(_providerFilter) || text.Contains(_providerFilter.Trim(), StringComparison.CurrentCultureIgnoreCase);
        if (Matches(L("意图路由")) && fields.Any(field => Text(field, "section") == "routing"))
            AddItem("section:routing", L("意图路由"), ChoiceLabel("SMART_SEARCH_INTENT_ROUTER", EffectiveConfigurationValue("SMART_SEARCH_INTENT_ROUTER")));
        var providers = fields.Where(field => Text(field, "provider").Length > 0).GroupBy(field => Text(field, "provider"))
            .Where(group => Matches(group.Key + " " + ProviderLabel(group.Key) + " " + ProviderPurpose(group.Key, group)
                + " " + string.Join(" ", ProviderCapabilities(group.Key, group))))
            .ToList();
        var categories = providers.Select(group => ProviderCapabilities(group.Key, group).FirstOrDefault() ?? "other").Distinct().ToList();
        foreach (var category in CapabilityOrder.Where(categories.Contains).Concat(categories.Except(CapabilityOrder).Order()))
        {
            AddHeading(CapabilityLabel(category));
            foreach (var group in providers.Where(group => (ProviderCapabilities(group.Key, group).FirstOrDefault() ?? "other") == category)
                         .OrderByDescending(group => group.Any(field => IsSecret(field) && HasSavedSecret(field))).ThenBy(group => group.Key))
                AddItem("provider:" + group.Key, ProviderLabel(group.Key), ProviderListStatus(group.Key, group));
        }
        var unassigned = fields.Where(field => Text(field, "provider").Length == 0).ToList();
        var sections = Items(Property(_state, "metadata"), "sections").OrderBy(section => Number(section, "order")).ToList();
        var sectionIds = sections.Select(section => Text(section, "id")).Concat(unassigned.Select(field => Text(field, "section"))).Distinct();
        var otherEntries = new List<(string Route, string Title)>();
        if (unassigned.Any(field => Text(field, "key").StartsWith("SMART_SEARCH_RESEARCH_")))
            otherEntries.Add(("research", L("研究数据源")));
        foreach (var id in sectionIds.Where(id => id != "routing" && unassigned.Any(field => Text(field, "section") == id)))
        {
            var section = sections.FirstOrDefault(section => Text(section, "id") == id);
            otherEntries.Add(("section:" + id, Text(section, "label_" + Localization.Language, id)));
        }
        otherEntries.Add(("routes", L("路由与回退")));
        var visible = otherEntries.Where(entry => Matches(entry.Title)).ToList();
        if (visible.Count > 0)
        {
            AddHeading(L("高级"));
            foreach (var entry in visible) AddItem(entry.Route, entry.Title);
        }
        _refreshingProviderList = false;
    }

    private string ProviderListStatus(string provider, IEnumerable<JsonElement> fields)
    {
        var status = fields.Any(field => IsSecret(field) && HasSavedSecret(field)) ? L("已配置") : L("未配置");
        var profile = Property(Property(_state, "provider_profiles"), provider);
        if (Property(profile, "enabled").ValueKind == JsonValueKind.False)
            status = L("已禁用");
        return _providerDraft.Keys.Any(key => fields.Any(field => Text(field, "key") == key)) ? status + " · " + L("未保存") : status;
    }

    private bool ProviderEnabled(string provider)
    {
        var key = Text(Property(Property(_state, "provider_profiles"), provider), "enabled_key");
        return key.Length == 0 || ConfigurationBoolean(EffectiveConfigurationValue(key));
    }

    private List<string> ProviderCapabilities(string provider, IEnumerable<JsonElement> fields)
    {
        var profile = Property(Property(_state, "provider_profiles"), provider);
        var declared = new[] { Text(profile, "capability") }.Concat(Items(profile, "capabilities").Select(item => item.GetString() ?? string.Empty))
            .Where(value => value.Length > 0).Distinct().ToList();
        return declared.Count > 0 ? declared : fields.SelectMany(field => Items(field, "capabilities")).Select(item => item.GetString() ?? string.Empty)
            .Where(value => value.Length > 0).Distinct().ToList();
    }

    private string ProviderPurpose(string provider, IEnumerable<JsonElement> fields)
    {
        var profile = Property(Property(_state, "provider_profiles"), provider);
        var capabilities = string.Join(L("、"), ProviderCapabilities(provider, fields).Select(CapabilityLabel));
        var strengths = string.Join(L("、"), Items(profile, "strengths").Select(item => L(item.GetString() ?? string.Empty)));
        var sentences = new List<string>();
        if (capabilities.Length > 0) sentences.Add(strengths.Length > 0 ? L("用于{0}，侧重{1}。", capabilities, strengths) : L("用于{0}。", capabilities));
        if (Bool(profile, "experimental")) sentences.Add(L("实验性能力。"));
        if (Bool(profile, "explicit_only")) sentences.Add(L("仅在明确指定时调用。"));
        else if (Property(profile, "route_enabled").ValueKind == JsonValueKind.False) sentences.Add(L("不参与自动路由。"));
        return string.Join(" ", sentences);
    }

    private void RenderProviderDetail()
    {
        if (_providerDetail is null || _state is not { } state) return;
        _fieldEditors.Clear();
        _providerStatusPanels.Clear();
        if (_configSnapshotStale)
        {
            _providerDetail.Content = PaneScroll(Section(L("配置已保存"),
                [Body(L("配置已保存，但暂未读回最新状态。请刷新后继续编辑。")),
                 ActionButton(L("刷新本机状态"), () => RefreshStateAsync(), operationKey: "state")]), "providers:refresh");
            return;
        }
        var fields = ConfigurationFields;
        var panel = PagePanel();
        void AddFields(string title, IEnumerable<JsonElement> selected)
        {
            var entries = selected.ToList();
            if (entries.Count == 0) return;
            var form = new StackPanel { Spacing = 8 };
            foreach (var field in entries)
            {
                if (form.Children.Count > 0) form.Children.Add(Divider());
                form.Children.Add(BuildFieldEditor(field, _providerDraft));
            }
            panel.Children.Add(SettingsSection(title, string.Empty, Card(form)));
        }
        if (_providerSelection.StartsWith("provider:"))
        {
            var provider = _providerSelection[9..];
            var selected = fields.Where(field => Text(field, "provider") == provider).ToList();
            panel.Children.Add(PageTitle(ProviderLabel(provider)));
            panel.Children.Add(Secondary(ProviderPurpose(provider, selected)));
            foreach (var enableField in selected.Where(field => Bool(field, "provider_toggle")))
                panel.Children.Add(Card(BuildFieldEditor(enableField, _providerDraft)));
            AddFields(L("连接设置"), selected.Where(field => !Bool(field, "provider_toggle") && !IsAdvanced(field)));
            AddFields(L("高级参数"), selected.Where(field => !Bool(field, "provider_toggle") && IsAdvanced(field)));
            var status = BuildProviderStatus(state, provider);
            _providerStatusPanels[provider] = status;
            panel.Children.Add(status);
            panel.Children.Add(ActionButton(L("测试"), () => TestProviderDraftAsync(provider), operationKey: "test:" + provider,
                busyText: Text(Property(state, "probe_kinds"), provider) == "presence" ? L("检查中…") : L("测试中…"),
                label: () => ProviderTestLabel(provider), enabled: () => ProviderEnabled(provider)));
        }
        else if (_providerSelection == "section:routing")
        {
            panel.Children.Add(PageTitle(L("意图路由")));
            panel.Children.Add(Secondary(L("先选择路由方式，再填写该模式使用的参数。")));
            var routing = fields.Where(field => Text(field, "section") == "routing").ToList();
            var mode = EffectiveConfigurationValue("SMART_SEARCH_INTENT_ROUTER");
            AddFields(L("路由模式"), routing.Where(field => Text(field, "key") == "SMART_SEARCH_INTENT_ROUTER"));
            panel.Children.Add(Secondary(mode switch
            {
                "hybrid" => L("以规则为基础，可按需配置向量模型和分类模型增强判断。未配置的模型不会被调用。"),
                "jev" => L("使用 JEV 选择检索渠道并判断证据是否充分，需要单独配置 TypeSafe 凭据。"),
                "rules" => L("仅使用本地规则判断意图，无需填写模型接口或密钥。"),
                "off" => L("关闭自动意图路由，无需填写路由参数。"), _ => L("请选择一种路由模式。")
            }));
            if (mode == "hybrid")
            {
                AddFields(L("向量模型"), routing.Where(field => Text(field, "key").StartsWith("INTENT_EMBEDDING_")));
                AddFields(L("分类模型"), routing.Where(field => Text(field, "key").StartsWith("INTENT_CLASSIFIER_")));
                AddFields(L("请求设置"), routing.Where(field => Text(field, "key") == "INTENT_ROUTER_TIMEOUT_SECONDS"));
            }
            else if (mode == "jev")
            {
                string[] processing = ["SMART_SEARCH_JEV_FILTER_RESULTS", "SMART_SEARCH_JEV_FILTER_THRESHOLD", "SMART_SEARCH_JEV_SYNTHESIZE",
                    "SMART_SEARCH_JEV_SYNTHESIS_API_URL", "SMART_SEARCH_JEV_SYNTHESIS_API_KEY",
                    "SMART_SEARCH_JEV_SYNTHESIS_MODEL", "SMART_SEARCH_JEV_SYNTHESIS_API_MODE"];
                AddFields(L("JEV 连接"), routing.Where(field => Text(field, "key").StartsWith("TYPESAFE_")));
                AddFields(L("检索与判断"), routing.Where(field => Text(field, "key").StartsWith("SMART_SEARCH_JEV_") && !processing.Contains(Text(field, "key"))));
                AddFields(L("结果处理"), routing.Where(field => processing.Contains(Text(field, "key")) &&
                    (Text(field, "key") != "SMART_SEARCH_JEV_FILTER_THRESHOLD" || ConfigurationBoolean(EffectiveConfigurationValue("SMART_SEARCH_JEV_FILTER_RESULTS")))));
            }
        }
        else if (_providerSelection == "routes")
        {
            panel.Children.Add(PageTitle(L("路由与回退")));
            foreach (var chain in CapabilityChains(state)) panel.Children.Add(chain);
        }
        else
        {
            var id = _providerSelection.StartsWith("section:") ? _providerSelection[8..] : "routing";
            var section = Items(Property(state, "metadata"), "sections").FirstOrDefault(section => Text(section, "id") == id);
            var title = _providerSelection == "research" ? L("研究数据源") : Text(section, "label_" + Localization.Language, id);
            panel.Children.Add(PageTitle(title));
            if (_providerSelection != "research") panel.Children.Add(Secondary(Text(section, "blurb_" + Localization.Language)));
            AddFields(L("参数"), fields.Where(field => Text(field, "provider").Length == 0 &&
                (_providerSelection == "research" ? Text(field, "key").StartsWith("SMART_SEARCH_RESEARCH_") : Text(field, "section") == id)));
        }
        _providerDetail.Content = PaneScroll(panel, "provider:" + _providerSelection);
        RefreshActionButtons();
    }

    private bool HasSavedSecret(JsonElement field)
    {
        var key = Text(field, "key");
        var presence = Property(Property(_state, "secret_presence"), key);
        if (presence.ValueKind is JsonValueKind.True or JsonValueKind.False) return presence.GetBoolean();
        var value = DisplayValue(Property(_state, "values"), key);
        return value.Length > 0 && value != "***";
    }

    private string EffectiveConfigurationValue(string key)
    {
        var field = ConfigurationFields.FirstOrDefault(field => Text(field, "key") == key);
        if (_providerDraft.TryGetValue(key, out var draft))
            return draft.Clear ? Text(field, "default") : Text(field, "kind") == "bool" ? draft.IsChecked.ToString().ToLowerInvariant() : draft.Text ?? string.Empty;
        var value = DisplayValue(Property(_state, "values"), key);
        return string.IsNullOrEmpty(value) ? Text(field, "default") : value;
    }

    private static bool ConfigurationBoolean(string value) => value.ToLowerInvariant() is "true" or "1" or "yes" or "on";

    private Task DiscardProviderDraftAsync()
    {
        _providerDraft.Clear();
        _fieldEditors.Clear();
        RenderProviderDetail();
        RenderProviderList();
        return Task.CompletedTask;
    }

    private UIElement BuildFieldEditor(JsonElement field, Dictionary<string, FieldDraft>? preservedDraft)
    {
        var key = Text(field, "key");
        var source = Text(Property(_state, "sources"), key, "default");
        var value = DisplayValue(Property(_state, "values"), key);
        var initialValue = string.IsNullOrWhiteSpace(value) ? Text(field, "default") : value;
        var secret = IsSecret(field);
        var locked = source.Equals("environment", StringComparison.OrdinalIgnoreCase);
        var providerToggle = Bool(field, "provider_toggle");
        var input = providerToggle ? CompactSwitch(Label(field), ConfigurationBoolean(initialValue)) : CreateFieldInput(field, secret, initialValue, locked);
        if (input is TextBox or PasswordBox) ToolTipService.SetToolTip(input, ConfigurationPlaceholder(field));
        if (providerToggle) input.IsEnabled = !locked;
        AutomationProperties.SetName(input, Label(field));
        input.HorizontalAlignment = HorizontalAlignment.Stretch;
        ToggleSwitch? clear = locked || providerToggle ? null : CompactSwitch(secret ? L("清除已保存的密钥") : L("恢复默认值"), false);
        var editor = new FieldEditor(field.Clone(), input, clear, ReadControl(input), secret, locked);
        _fieldEditors[key] = editor;
        if (preservedDraft is not null && preservedDraft.TryGetValue(key, out var draft)) RestoreDraft(editor, draft);
        var updating = false;
        void UpdatePlaceholder()
        {
            if (input is PasswordBox password)
                password.PlaceholderText = HasSavedSecret(field) && clear?.IsOn != true ? "••••••••" : ConfigurationPlaceholder(field);
        }
        void Changed(bool edited = false)
        {
            if (updating) return;
            if (edited && clear?.IsOn == true)
            {
                updating = true;
                clear.IsOn = false;
                updating = false;
            }
            UpdatePlaceholder();
            _providerDraft = CaptureDraft();
            RefreshActionButtons();
            if (_providerSelection == "section:routing" && key is "SMART_SEARCH_INTENT_ROUTER" or "SMART_SEARCH_JEV_FILTER_RESULTS")
                DispatcherQueue.TryEnqueue(() => { if (_currentPage == "providers" && _providerSelection == "section:routing") RenderProviderDetail(); });
        }
        switch (input)
        {
            case TextBox text: text.TextChanged += (_, _) => Changed(true); break;
            case PasswordBox password: password.PasswordChanged += (_, _) => Changed(true); break;
            case ComboBox combo: combo.SelectionChanged += (_, _) => Changed(true); break;
            case ToggleSwitch toggle: toggle.Toggled += (_, _) => Changed(true); break;
        }
        if (clear is not null) clear.Toggled += (_, _) =>
        {
            if (updating) return;
            updating = true;
            var reset = new CommandValue(secret ? string.Empty : Text(field, "default"), ConfigurationBoolean(Text(field, "default")));
            RestoreControl(input, clear.IsOn ? reset : editor.Initial);
            updating = false;
            Changed();
        };
        UpdatePlaceholder();

        var help = Text(field, "help_" + Localization.Language, Text(field, "help_en"));
        if (providerToggle)
            return SettingRow(Label(field), locked ? help + "\n" + L("由环境变量提供，在此处只读。") : help, input);
        var details = new StackPanel { Spacing = 12, MaxWidth = 360 };
        if (help.Length > 0) details.Children.Add(Body(help));
        details.Children.Add(KeyValue(L("来源"), SourceLabel(source)));
        details.Children.Add(DataText(key));
        if (!secret) details.Children.Add(KeyValue(L("当前生效"), initialValue));
        if (clear is not null) details.Children.Add(SettingRow(secret ? L("清除已保存的密钥") : L("恢复默认值"), L("保存更改后生效。"), clear));
        if (locked) details.Children.Add(Secondary(L("由环境变量提供，在此处只读。")));
        var info = new Button { Content = new FontIcon { Glyph = "\uE897", FontSize = 14 }, Style = UiStyle("FieldHelpButtonStyle"),
            Flyout = new Flyout { Content = new ScrollViewer { Content = details, MaxHeight = 360, VerticalScrollBarVisibility = ScrollBarVisibility.Auto } } };
        AutomationProperties.SetName(info, L("字段说明：{0}", Label(field)));
        AutomationProperties.SetHelpText(info, help);
        var tooltip = new ToolTip { Content = Body(help), MaxWidth = 360 };
        ToolTipService.SetToolTip(info, tooltip);
        info.GotFocus += (_, _) => { if (info.FocusState == FocusState.Keyboard) tooltip.IsOpen = true; };
        info.LostFocus += (_, _) => tooltip.IsOpen = false;
        info.Click += (_, _) => tooltip.IsOpen = false;
        var title = new Grid { ColumnSpacing = 12 };
        title.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        title.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        title.Children.Add(new TextBlock { Text = Label(field), TextWrapping = TextWrapping.Wrap, VerticalAlignment = VerticalAlignment.Center, FontWeight = Microsoft.UI.Text.FontWeights.SemiBold });
        Grid.SetColumn(info, 1);
        title.Children.Add(info);
        var row = new StackPanel { Spacing = 8, Children = { title, input } };
        if (locked) row.Children.Add(Secondary(L("由环境变量提供，在此处只读。")));
        var links = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 8 };
        foreach (var (property, label) in new[] { ("key_url", L("申请 Key")), ("docs_url", L("文档")) })
            if (Uri.TryCreate(Text(field, property), UriKind.Absolute, out var uri) && uri.Scheme is "https" or "http")
                links.Children.Add(new HyperlinkButton { Content = label, NavigateUri = uri, Padding = new Thickness(0) });
        if (links.Children.Count > 0) row.Children.Add(links);
        return row;
    }

    private static string ConfigurationPlaceholder(JsonElement field) => L("示例：{0}", ConfigurationExample(field));

    private static string ConfigurationExample(JsonElement field)
    {
        var placeholder = Text(field, "placeholder");
        if (!string.IsNullOrWhiteSpace(placeholder)) return placeholder;
        var defaultValue = Text(field, "default");
        if (!string.IsNullOrWhiteSpace(defaultValue)) return defaultValue;
        var key = Text(field, "key");
        switch (key)
        {
            case "OPENAI_COMPATIBLE_MODEL":
            case "INTENT_CLASSIFIER_MODEL": return "gpt-4o";
            case "OPENAI_COMPATIBLE_FALLBACK_MODELS": return "gpt-4o,deepseek-chat";
            case "JINA_RESPOND_WITH": return "readerlm-v2";
            case "INTENT_EMBEDDING_API_URL": return "https://api.siliconflow.cn/v1/embeddings";
            case "INTENT_EMBEDDING_MODEL": return "Qwen/Qwen3-Embedding-8B";
            case "INTENT_CLASSIFIER_API_URL": return "https://api.example.com/v1/chat/completions";
            case "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS": return "exa,tavily";
            case "SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS": return "anysearch,sciverse";
        }
        if (IsSecret(field)) return key.EndsWith("TOKEN", StringComparison.Ordinal) ? "your-api-token" : "your-api-key";
        return Text(field, "kind") switch
        {
            "url" => "https://api.example.com/v1",
            "int" => "3",
            "float" => "0.5",
            "csv" => "value1,value2",
            _ => "example"
        };
    }

    private static string ChoiceLabel(string key, string value) => key switch
    {
        "SMART_SEARCH_INTENT_ROUTER" => value switch { "hybrid" => L("混合路由"), "jev" => L("JEV 语义路由"), "rules" => L("规则路由"), "off" => L("关闭路由"), _ => value },
        "SMART_SEARCH_JEV_SYNTHESIZE" => value switch { "false" => L("直接返回证据"), "auto" => L("按需汇总"), "true" => L("始终汇总"), _ => value },
        _ => value
    };

    private sealed record ConfigurationChoice(string Value, string Label)
    {
        public override string ToString() => Label;
    }
}
