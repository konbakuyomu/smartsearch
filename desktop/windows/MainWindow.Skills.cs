using static SmartSearch.Desktop.Localization;
using System.Text.Json;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;

namespace SmartSearch.Desktop;

public sealed partial class MainWindow
{
    private readonly Dictionary<string, SkillTargetRow> _skillTargetRows = [];
    private TextBlock? _skillSelectionSummary;
    private bool _updatingSkillRows;

    private UIElement BuildAiPage()
    {
        var panel = PagePanel();
        _cliUpdateSummary = Body(string.Empty);
        _environmentProgress = new ProgressBar { Minimum = 0, Maximum = 100, Visibility = Visibility.Collapsed };
        _cliCancelButton = ActionButton(L("取消"), () => EnvironmentRequestAsync("environment.cancel"), operationKey: "environment-cancel");
        panel.Children.Add(SectionHeading("CLI"));
        panel.Children.Add(_cliUpdateSummary);
        panel.Children.Add(_environmentProgress);
        panel.Children.Add(ActionRow(ActionButton(L("安装 CLI"), ManageCliAsync, primary: true,
            operationKey: "cli-manage", busyText: L("处理中…"), label: CliActionLabel), _cliCancelButton));
        panel.Children.Add(Divider());
        panel.Children.Add(SectionHeading("Skills"));
        panel.Children.Add(Secondary(L("勾选要安装或更新的 Agent。取消勾选不会卸载文件。")));
        _skillSummary = Secondary(string.Empty);
        _skillResult = Body(string.Empty);
        _skillRows = new StackPanel { Spacing = 8 };
        _skillTargetRows.Clear();
        panel.Children.Add(_skillRows);
        panel.Children.Add(_skillSummary);
        panel.Children.Add(_skillResult);
        _skillSelectionSummary = Secondary(string.Empty);
        var footer = WorkspaceFooter(_skillSelectionSummary,
            ActionButton(L("安装/更新所选 Skills"), InstallSelectedSkillsAsync, primary: true,
                operationKey: "skills-install", busyText: L("处理中…")));
        var layout = new Grid();
        layout.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        layout.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        layout.Children.Add(Scroll(panel));
        Grid.SetRow(footer, 1);
        layout.Children.Add(footer);
        RenderCliState();
        RenderSkillState();
        _ = RunOperationAsync("skills-status", LoadSkillsAsync);
        _ = RunOperationAsync("cli-status", LoadCliStatusAsync);
        return layout;
    }

    private bool CliReady => Bool(Property(_state, "cli"), "external_runtime_verified") && Text(Property(_state, "cli"), "manager") != "bundled";

    private string CliActionLabel() => !CliReady
        ? Text(Property(_state, "cli"), "external_path").Length == 0 ? L("安装 CLI") : L("修复 CLI")
        : Bool(Property(_updates, "cli"), "available") && Bool(Property(_state, "cli"), "can_update") ? L("更新 CLI") : L("检查更新");

    private async Task ManageCliAsync()
    {
        if (!CliReady) await EnvironmentRequestAsync("environment.prepare", new { confirm = true });
        else if (Bool(Property(_updates, "cli"), "available") && Bool(Property(_state, "cli"), "can_update")) await UpdateCliAsync();
        else await UpdateRequestAsync("cli.update-check");
    }

    private void RenderCliState()
    {
        if (_currentPage != "ai" || _cliUpdateSummary is null) return;
        var info = Property(_state, "cli");
        var update = Property(_updates, "cli");
        var operation = Property(_updates, "cli_update");
        var message = EnvironmentBusy ? Text(_environment, "message", L("正在准备 CLI…")) :
            Text(operation, "status") == "running" ? L("正在更新 CLI…") :
            !CliReady ? L("CLI 未就绪，安装时会自动准备所需组件。") : L("已安装 {0}", Text(info, "external_version"));
        if (CliReady && Bool(update, "available")) message += "\n" + L("可更新到 {0}", Text(update, "latest_version"));
        else if (CliReady && Number(update, "checked_at") > 0 && !Bool(update, "cached") && Text(update, "error").Length == 0)
            message += " · " + L("已是最新版本");
        if (!Bool(info, "can_update") && Text(info, "update_note").Length > 0) message += "\n" + Text(info, "update_note");
        if (Text(_environment, "status") == "ready" && Text(_environment, "message").Length > 0) message += "\n" + Text(_environment, "message");
        var error = Text(_environment, "error");
        if (error.Length == 0) error = Text(operation, "error");
        if (error.Length == 0) error = Text(update, "error");
        if (error.Length > 0) message += "\n" + error;
        _cliUpdateSummary.Text = message;
        var total = Number(_environment ?? default, "total");
        _environmentProgress!.Visibility = EnvironmentBusy && total > 0 ? Visibility.Visible : Visibility.Collapsed;
        _environmentProgress.Value = total > 0 ? 100 * Number(_environment ?? default, "received") / total : 0;
        if (_cliCancelButton is not null) _cliCancelButton.Visibility = Bool(_environment, "can_cancel") ? Visibility.Visible : Visibility.Collapsed;
        RefreshActionButtons();
    }

    private void RenderSkillState()
    {
        if (_currentPage != "ai" || _skillRows is null || _skillSummary is null) { RefreshActionButtons(); return; }
        _skillSummary.Text = Bool(_skills, "checking") ? L("正在检查最新 Skills…") :
            L("点击安装/更新后自动检查最新内容；已有修改会先备份。");
        var targets = Items(Property(_skills, "targets")).ToList();
        if (!_skillSelectionInitialized && targets.Count > 0)
        {
            foreach (var definition in Items(Property(_state, "skill_targets")))
                if (Bool(definition, "default")) _selectedSkillTargets.Add(Text(definition, "id"));
            _skillSelectionInitialized = true;
        }
        var ids = targets.Select(target => Text(target, "target")).ToHashSet();
        foreach (var id in _skillTargetRows.Keys.Where(id => !ids.Contains(id)).ToArray())
        {
            _skillRows.Children.Remove(_skillTargetRows[id].Container);
            _skillTargetRows.Remove(id);
        }
        _updatingSkillRows = true;
        foreach (var target in targets)
        {
            var id = Text(target, "target");
            if (id.Length == 0) continue;
            if (!_skillTargetRows.TryGetValue(id, out var row))
            {
                row = CreateSkillTargetRow(id);
                _skillTargetRows[id] = row;
                _skillRows.Children.Add(row.Container);
            }
            row.Update(target);
        }
        _updatingSkillRows = false;
        var installed = Items(Property(_skills, "result"), "installed").ToList();
        var failed = Items(Property(_skills, "result"), "failed").ToList();
        var changed = installed.Count(item => Number(item, "changed_files") > 0);
        var lines = new List<string>();
        if (Text(_skills, "error").Length > 0) lines.Add(Text(_skills, "error"));
        if (Bool(_skills, "busy") && !Bool(_skills, "checking")) lines.Add(L("正在安装/更新 Skills…"));
        else if (installed.Count + failed.Count > 0)
            lines.Add(changed == 0 && failed.Count == 0 ? L("所选 Skills 已是最新。") : L("已更新 {0} 个，失败 {1} 个。", changed, failed.Count));
        foreach (var failure in failed) lines.Add(Text(failure, "target") + ": " + Text(failure, "error"));
        foreach (var receipt in installed.Where(item => Text(item, "backup").Length > 0)) lines.Add(L("备份：{0}", Text(receipt, "backup")));
        _skillResult!.Text = string.Join("\n", lines);
        _skillResult.Visibility = lines.Count == 0 ? Visibility.Collapsed : Visibility.Visible;
        RefreshSkillSelection();
        RefreshActionButtons();
    }

    private SkillTargetRow CreateSkillTargetRow(string id)
    {
        var choice = new CheckBox { IsChecked = _selectedSkillTargets.Contains(id), VerticalAlignment = VerticalAlignment.Center };
        var status = Secondary(string.Empty);
        status.VerticalAlignment = VerticalAlignment.Center;
        choice.Click += (_, _) =>
        {
            if (_updatingSkillRows) return;
            if (choice.IsChecked == true) _selectedSkillTargets.Add(id); else _selectedSkillTargets.Remove(id);
            RefreshSkillSelection();
            RefreshActionButtons();
        };
        var line = new Grid { ColumnSpacing = 16, MinHeight = 40 };
        line.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
        line.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        line.Children.Add(choice);
        Grid.SetColumn(status, 1);
        line.Children.Add(status);
        return new SkillTargetRow(line, target =>
        {
            var label = Text(target, "label", id);
            choice.Content = label;
            AutomationProperties.SetName(choice, label);
            choice.IsChecked = _selectedSkillTargets.Contains(id);
            choice.IsEnabled = !Bool(_skills, "busy");
            status.Text = Bool(target, "needs_update") && Text(target, "status") != "missing" ? L("可更新") : SkillStatusLabel(Text(target, "status"));
        });
    }

    private void RefreshSkillSelection()
    {
        if (_skillSelectionSummary is not null) _skillSelectionSummary.Text = _selectedSkillTargets.Count > 0
            ? L("已选择 {0} 个 Agent", _selectedSkillTargets.Count) : L("请选择要安装或更新的 Agent");
    }

    private sealed record SkillTargetRow(Grid Container, Action<JsonElement> Update);
}
