using static SmartSearch.Desktop.Localization;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;

namespace SmartSearch.Desktop;

public sealed partial class MainWindow
{
    private StackPanel? _commandOptions;
    private Button? _commandOptionsButton;
    private ContentControl? _searchResultHost;
    private ScrollViewer? _searchResultContent;

    private UIElement BuildSearchPage()
    {
        _commandControls.Clear();
        _commandArguments.Clear();
        if (_state is not { } state) return Scroll(Section(L("测试"), [OfflineHint()]));
        var form = new StackPanel { Spacing = PageInset };
        form.Children.Add(SectionHeading(L("输入")));
        form.Children.Add(Secondary(L("选择要测试的功能，填写输入后开始测试。")));
        _commandPicker = new ComboBox { HorizontalAlignment = HorizontalAlignment.Stretch };
        AutomationProperties.SetName(_commandPicker, L("测试项目"));
        foreach (var command in Items(state, "commands"))
        {
            var id = Text(command, "id");
            if (id.Length > 0) _commandPicker.Items.Add(new CommandOption(id, Text(command, "label", id), Text(command, "description"), Bool(command, "experimental"), command.Clone()));
        }
        _commandPicker.SelectionChanged += (_, _) => RenderCommandFields();
        form.Children.Add(_commandPicker);
        _commandFieldPanel = new StackPanel { Spacing = 16 };
        form.Children.Add(_commandFieldPanel);
        _commandOptionsButton = DetailsButton(L("测试选项…"), async () =>
        {
            if (_commandOptions is not null) await ShowDetailsAsync(L("测试选项…"), _commandOptions);
            CaptureCommandInputs();
        });
        _commandOptionsButton.Visibility = Visibility.Collapsed;
        form.Children.Add(ActionRow(
            ActionButton(L("运行"), StartSelectedCommandAsync, primary: true, busyText: L("运行中…"),
                dynamicKey: () => "run:" + _selectedCommandId, label: () => L("开始测试"), enabled: () => !SearchRunning),
            _commandOptionsButton));

        _searchResultHost = new ContentControl { HorizontalContentAlignment = HorizontalAlignment.Stretch, VerticalContentAlignment = VerticalAlignment.Stretch };
        _resultText = new TextBox
        {
            IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, MinHeight = 160,
            BorderThickness = new Thickness(0), Background = null, Padding = new Thickness(0)
        };
        AutomationProperties.SetName(_resultText, L("结果"));
        _sourceRows = new StackPanel { Spacing = 4 };
        _sourceDisclosure = Disclosure("result-sources", L("来源链接"), _sourceRows, expanded: true);
        _sourceDisclosure.Visibility = Visibility.Collapsed;
        _rawResult = new TextBox { IsReadOnly = true, TextWrapping = TextWrapping.Wrap, AcceptsReturn = true, MinHeight = 120 };
        var resultPanel = new StackPanel { Spacing = 20 };
        resultPanel.Children.Add(ActionRow(ActionButton(L("复制结果"), CopyResult, operationKey: "result-copy"),
            ActionButton(L("导出结果"), ExportResultAsync, operationKey: "result-export", busyText: L("导出中…")),
            DetailsButton(L("高级 JSON"), () => ShowDetailsAsync(L("高级 JSON"), DataText(_rawResult.Text)))));
        resultPanel.Children.Add(_resultText);
        resultPanel.Children.Add(_sourceDisclosure);
        _searchResultContent = PaneScroll(resultPanel, "search:result");
        ShowSearchState(L("选择测试项目，运行一次请求以确认配置。"), false);
        if (_commandPicker.Items.Count > 0)
            _commandPicker.SelectedItem = _commandPicker.Items.OfType<CommandOption>().FirstOrDefault(command => command.Id == _selectedCommandId) ?? _commandPicker.Items[0];
        if (_selectedResultRunId is not null)
        {
            if (_ownedRunResults.TryGetValue(_selectedResultRunId, out var cached)) RenderResult(cached);
            else if (!IsTerminal(_ownedRunStatus.GetValueOrDefault(_selectedResultRunId, "finished")))
                ShowSearchState(L("任务正在运行。完成后会显示可读结果和来源。"), true);
        }
        return SplitWorkspace("search", PaneScroll(form, "search:input"), _searchResultHost, 340, 296, 400, 360);
    }

    private void ShowSearchState(string message, bool running)
    {
        if (_searchResultHost is null) return;
        if (!running)
        {
            _searchResultHost.Content = EmptyState(L("结果会显示在这里"), message, Symbol.Find);
            return;
        }
        _searchResultHost.Content = new StackPanel
        {
            Spacing = 16, MaxWidth = 400, Margin = new Thickness(24),
            HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center,
            Children = { new ProgressRing { IsActive = true, Width = 32, Height = 32 }, Body(message),
                ActionButton(L("取消测试"), () => _selectedResultRunId is { } id ? CancelOwnedRunAsync(id) : Task.CompletedTask,
                    dynamicKey: () => "cancel:" + _selectedResultRunId, busyText: L("取消中…")) }
        };
    }

    private static Grid EmptyState(string title, string description, Symbol symbol)
    {
        var heading = SectionHeading(title);
        heading.TextAlignment = TextAlignment.Center;
        var explanation = Secondary(description);
        explanation.TextAlignment = TextAlignment.Center;
        var panel = new StackPanel
        {
            Spacing = 12, MaxWidth = 400, Margin = new Thickness(24),
            HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center,
            Children = { new SymbolIcon(symbol) { Width = 40, Height = 40 }, heading, explanation }
        };
        return new Grid { Children = { panel } };
    }
}
