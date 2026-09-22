using System.Reflection;
using System.Runtime.InteropServices;
using Velopack;
using Velopack.Sources;

namespace SmartSearch.Desktop;

internal sealed class AppUpdater
{
    internal const string Repository = "https://github.com/konbakuyomu/smartsearch";
    private readonly UpdateManager _manager;
    private UpdateInfo? _update;
    internal bool Installed => _manager.IsInstalled;
    internal string CurrentVersion => _manager.CurrentVersion?.ToString()
        ?? Assembly.GetEntryAssembly()?.GetName().Version?.ToString(3) ?? "";
    internal string? LatestVersion => _update?.TargetFullRelease.Version.ToString();
    internal bool Checking { get; private set; }
    internal bool Downloading { get; private set; }
    internal bool Ready { get; private set; }
    internal bool Available => _update is not null && Error.Length == 0;
    internal string Error { get; private set; } = "";
    internal int Progress { get; private set; }
    internal DateTimeOffset? CheckedAt { get; private set; }

    internal AppUpdater(UpdateManager? manager = null)
    {
        var architecture = RuntimeInformation.ProcessArchitecture == Architecture.Arm64 ? "arm64" : "x64";
        _manager = manager ?? new UpdateManager(new GithubSource(Repository, null, false),
            new UpdateOptions { ExplicitChannel = $"win-{architecture}-stable", AllowVersionDowngrade = false });
    }

    internal async Task CheckAsync()
    {
        if (!Installed || Checking || Downloading) return;
        Checking = true;
        Error = "";
        _update = null;
        Ready = false;
        try
        {
            _update = await _manager.CheckForUpdatesAsync();
            CheckedAt = DateTimeOffset.UtcNow;
        }
        catch (Exception)
        {
            Error = Localization.L("无法检查 App 更新，请稍后重试。");
        }
        finally { Checking = false; }
    }

    internal async Task DownloadAsync(Action changed, CancellationToken cancellationToken)
    {
        if (!Available || Checking || Downloading) return;
        Downloading = true;
        Progress = 0;
        Ready = false;
        try
        {
            await _manager.DownloadUpdatesAsync(_update!, value => { Progress = value; changed(); }, cancellationToken);
            cancellationToken.ThrowIfCancellationRequested();
            Ready = true;
        }
        catch (OperationCanceledException) { Error = Localization.L("下载已取消，请重新检查更新。"); }
        catch (Exception) { Error = Localization.L("更新下载或校验失败，原安装保持不变；请重新检查。"); }
        finally { Downloading = false; changed(); }
    }

    internal void ApplyAndRestart()
    {
        if (!Ready || _update is null) throw new InvalidOperationException("No verified App update is ready.");
        _manager.ApplyUpdatesAndRestart(_update);
    }

}
