using static SmartSearch.Desktop.Localization;
using System.Diagnostics;

namespace SmartSearch.Desktop;

internal sealed record BackendEvent(string Name, System.Text.Json.JsonElement Data);

internal sealed class BackendRpcException(string code, string? message) : Exception(
    string.IsNullOrWhiteSpace(message) ? L("后端拒绝了请求（{0}）。", code) : message)
{
    public string Code { get; } = code;
}

internal sealed class BackendDisconnectedException(string reason) : Exception(reason);

internal sealed record CommandArgument(
    string Name,
    IReadOnlyList<string> Flags,
    bool IsBoolean,
    bool Multiple,
    bool Required);

internal sealed record CommandValue(string? Text, bool IsChecked = false);

internal static class SkillsSelectionPolicy
{
    public static bool CanUpdate(bool connected, int selectedCount, bool busy) => connected && selectedCount > 0 && !busy;
}

internal static class ControlValueComparer
{
    public static bool Equal(CommandValue first, CommandValue second) =>
        first.IsChecked == second.IsChecked && string.Equals(first.Text?.Trim(), second.Text?.Trim(), StringComparison.Ordinal);
}

internal sealed class OperationState
{
    private readonly HashSet<string> _requests = [];
    private readonly Dictionary<string, HashSet<string>> _runs = [];

    public bool IsBusy(string key) => _requests.Contains(key) || _runs.Values.Any(keys => keys.Contains(key));
    public bool Begin(string key)
    {
        if (IsBusy(key)) return false;
        return _requests.Add(key);
    }
    public void EndRequest(string key) => _requests.Remove(key);
    public void TrackRun(string key, string runId)
    {
        if (!_runs.TryGetValue(runId, out var keys)) _runs[runId] = keys = [];
        keys.Add(key);
    }
    public string[] RunsFor(string key) => _runs.Where(item => item.Value.Contains(key)).Select(item => item.Key).ToArray();
    public void EndRun(string runId) => _runs.Remove(runId);
    public void Clear() { _requests.Clear(); _runs.Clear(); }
}

internal static class ProtocolArguments
{
    public static IReadOnlyList<string> Build(
        IEnumerable<CommandArgument> fields,
        Func<string, CommandValue> valueFor)
    {
        var result = new List<string>();
        foreach (var field in fields)
        {
            var value = valueFor(field.Name);
            if (field.IsBoolean)
            {
                if (value.IsChecked && field.Flags.Count > 0)
                    result.Add(field.Flags[0]);
                continue;
            }

            var values = (value.Text ?? string.Empty)
                .Split('\n', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
            if (values.Length == 0)
                continue;

            if (field.Flags.Count == 0)
            {
                result.AddRange(field.Multiple ? values : values.Take(1));
                continue;
            }

            foreach (var item in field.Multiple ? values : values.Take(1))
            {
                result.Add(field.Flags[0]);
                result.Add(item);
            }
        }
        return result;
    }
}

internal static class ProtocolSelfTest
{
    [Conditional("DEBUG")]
    public static void Run()
    {
        var arguments = ProtocolArguments.Build(
            [
                new("query", [], false, false, true),
                new("limit", ["--limit"], false, false, false),
                new("verbose", ["--verbose"], true, false, false),
                new("tag", ["--tag"], false, true, false)
            ],
            name => name switch
            {
                "query" => new("Smart Search"),
                "limit" => new("5"),
                "verbose" => new(null, true),
                "tag" => new("docs\nweb"),
                _ => new(null)
            });
        Debug.Assert(arguments.SequenceEqual(["Smart Search", "--limit", "5", "--verbose", "--tag", "docs", "--tag", "web"]));
        Debug.Assert(ControlValueComparer.Equal(new CommandValue(null, false), new CommandValue(null, false)));
        Debug.Assert(!ControlValueComparer.Equal(new CommandValue(null, false), new CommandValue(null, true)));
        var operations = new OperationState();
        Debug.Assert(operations.Begin("test:exa"));
        Debug.Assert(!operations.Begin("test:exa"));
        operations.TrackRun("test:exa", "probe");
        operations.EndRequest("test:exa");
        Debug.Assert(operations.IsBusy("test:exa"));
        Debug.Assert(operations.Begin("test:context7"));
        operations.EndRun("probe");
        Debug.Assert(operations.Begin("test:exa"));
        operations.Clear();
        Debug.Assert(!operations.IsBusy("test:exa") && !operations.IsBusy("test:context7"));
    }
}
