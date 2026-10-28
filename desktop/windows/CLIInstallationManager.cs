using System.Diagnostics;
using System.Text.Json;
using System.Text.RegularExpressions;
using static SmartSearch.Desktop.Localization;

namespace SmartSearch.Desktop;

internal sealed record CLIInstallation(string Id, string Executable, string[] Arguments, string Version, string Source,
    bool Compatible, string[] Manager, string Prefix, Dictionary<string, string> Environment,
    string Note = "", string[]? ManagerOptions = null, string Distribution = "")
{
    internal bool CanManage => Source is "npm" or "mise" or "wsl" && Manager.Length > 0;
    internal bool InWsl => Distribution.Length > 0;
    internal string Place => InWsl ? "WSL " + Distribution : "Windows";
    public string Title => InWsl ? $"WSL {Distribution} · {Version}" : $"{Source} · {Version} · {Id}";
}

internal sealed record NpmEnvironment(string NpmPath, string NodePath, string Version, string Prefix, string Modules,
    string[] Command, Dictionary<string, string> Environment, string Distribution = "")
{
    internal string Identity => NodePath + "|" + string.Join("|", Command) + "|" + Prefix;
}

// An environment without a CLI. Npm is null when the App cannot install there, and Note says why.
internal sealed record CLIInstallTarget(string Id, string Place, NpmEnvironment? Npm, string Note = "");

internal sealed class CLIInstallationManager
{
    private const string Package = "@konbakuyomu/smart-search";
    internal const string WslIdPrefix = "wsl://";
    private const string WslPackageSuffix = "/lib/node_modules/" + Package;
    private const string WslWrapperSuffix = "/npm/bin/smart-search.js";
    // WSL prints UTF-16 unless asked otherwise; the Linux CLI's own output is UTF-8 either way.
    private static readonly Dictionary<string, string> WslEnvironment = new() { ["WSL_UTF8"] = "1" };
    // Ends with one JSON line for the CLI. A CLI from before 0.1.29 cannot say where it lives, so the
    // shell's Node.js and any npm-linked package come too; an old Python wrapper is reported, never run.
    // Line endings are normalized because a Windows checkout would hand bash CRLF.
    private static readonly string WslProbe = """
        node_line() { node -p process.execPath 2>/dev/null | sed 's/^/smart-search-node=/'; }
        p=$(command -v smart-search) || { node_line; echo '{"missing":true}'; exit 0; }
        t=$(readlink -f "$p"); r=${t%/npm/bin/smart-search.js}; c=
        if [ "$r" = "$t" ] || ! [ -f "$r/package.json" ] || grep -q smartSearchBinary "$r/package.json"; then
          c=$(smart-search --desktop-capabilities 2>/dev/null) || c=
          case $c in *launch_command*) echo "$c"; exit 0 ;; esac
        fi
        node_line; [ "$r" != "$t" ] && echo "smart-search-root=$r"
        [ -n "$c" ] && { echo "$c"; exit 0; }
        [ "$r" = "$t" ] && { echo '{"product":"smart-search","legacy":true}'; exit 0; }
        echo "{\"product\":\"smart-search\",\"legacy\":true,\"version\":\"$(sed -n 's/^ *"version": *"\([0-9.]*\)".*/\1/p' "$r/package.json" | head -n 1)\"}"
        """.ReplaceLineEndings("\n");
    // $1 is Node.js, $2 an existing CLI's npm prefix. Finds the npm that belongs to that Node.js,
    // whether the user can write the prefix (the App never uses sudo) and whether the package is there.
    private static readonly string WslNpmCheck = """
        n=$1; echo "smart-search-node-version=$("$n" -p process.versions.node 2>/dev/null)"
        c=$(readlink -f "$(dirname "$n")/npm")
        case $c in */npm-cli.js) ;; *) c=$(dirname "$(dirname "$n")")/lib/node_modules/npm/bin/npm-cli.js ;; esac
        [ -f "$c" ] || exit 0
        P=${2:-$("$n" "$c" prefix --global 2>/dev/null)}
        w=1
        for d in "$P/lib/node_modules" "$P/bin"; do
          if [ -e "$d" ]; then [ -w "$d" ] || w=0; elif ! [ -w "$P" ]; then w=0; fi
        done
        echo "smart-search-npm=$c"; echo "smart-search-prefix=$P"; echo "smart-search-writable=$w"
        [ -f "$P/lib/node_modules/@konbakuyomu/smart-search/package.json" ] && echo "smart-search-package=1"
        echo "smart-search-npm-version=$(sed -n 's/^ *"version": *"\([0-9.]*\)".*/\1/p' "${c%/bin/npm-cli.js}/package.json" | head -n 1)"
        """.ReplaceLineEndings("\n");
    // Runs Node.js + npm-cli.js as argv in the shell that found them, so profile settings such as
    // proxies apply. Version managers expose a new global command only after a reshim.
    private static readonly string WslNpmRun = """
        "$@" || exit
        [ "$3" = install ] || exit 0
        mise reshim >/dev/null 2>&1; asdf reshim nodejs >/dev/null 2>&1; exit 0
        """.ReplaceLineEndings("\n");
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
    private readonly string? _searchPath;
    private readonly string? _wslPath;
    private readonly string _stateFile;
    private readonly Func<Task<string>>? _versionLoader;
    private readonly Func<DateTimeOffset> _clock;
    private bool _checkedAtLaunch;
    private sealed record UpdateRecord(string Identity = "", string LatestVersion = "", bool SupportsBinary = false,
        DateTimeOffset? CheckedAt = null, DateTimeOffset? AttemptedAt = null, bool AutomaticallyChecks = true, string ManualNpmPath = "",
        string SelectedId = "", string ManualCliPath = "");
    private UpdateRecord _update = new();
    // What one detection found. Each detection fills a new one and shows it whole, so one running in the
    // background never shows half its results. The last one shown is kept for the next launch.
    private sealed class Detection
    {
        public List<CLIInstallation> Installations { get; set; } = [];
        public List<CLIInstallTarget> InstallTargets { get; set; } = [];
        public Dictionary<string, NpmEnvironment> WslNpm { get; set; } = [];
        public NpmEnvironment? Npm { get; set; }
        public string Message { get; set; } = "";
        public string[] WslDistributions { get; set; } = [];
        public string[] StoppedWslDistributions { get; set; } = [];
        public string SelectedId { get; set; } = "";
        // A detection made with other manual paths does not describe the current settings.
        public string ManualNpmPath { get; set; } = "";
        public string ManualCliPath { get; set; } = "";
    }
    private readonly string _detectionFile;
    private Detection _shown = new();
    private Detection? _held;
    private int _detections;

    internal enum Redetection { Unchanged, Changed, Missing }

    internal CLIInstallationManager(string? toolsDirectory = null, string? searchPath = null,
        Func<Task<string>>? versionLoader = null, Func<DateTimeOffset>? clock = null, string? wslPath = null)
    {
        _searchPath = searchPath;
        // An explicit search path is an isolated check; it reaches WSL only when given a wsl.exe.
        _wslPath = wslPath ?? (searchPath is null ? Path.Combine(Environment.SystemDirectory, "wsl.exe") : null);
        _stateFile = Path.Combine(toolsDirectory ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SmartSearchTools"), "cli-npm-state.json");
        _detectionFile = Path.Combine(Path.GetDirectoryName(_stateFile)!, "cli-detection.json");
        _versionLoader = versionLoader;
        _clock = clock ?? (() => DateTimeOffset.UtcNow);
        try
        {
            if (File.Exists(_stateFile)) _update = JsonSerializer.Deserialize<UpdateRecord>(File.ReadAllText(_stateFile), JsonOptions) ?? new();
        }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException) { }
    }

    internal List<CLIInstallation> Installations => _shown.Installations;
    internal List<CLIInstallTarget> InstallTargets => _shown.InstallTargets;
    internal CLIInstallation? Selected => Find(_shown, _update.SelectedId);
    internal NpmEnvironment? Npm => _shown.Npm;
    internal bool WslAvailable => _wslPath is not null && File.Exists(_wslPath);
    internal IReadOnlyList<string> WslDistributions => _shown.WslDistributions;
    internal IReadOnlyList<string> StoppedWslDistributions => _shown.StoppedWslDistributions;
    internal string ManualNpmPath => _update.ManualNpmPath;
    internal string ManualCliPath => _update.ManualCliPath;
    internal bool CanInstall => Selected is { } selected ? selected.CanManage : InstallTargets.Any(target => target.Npm is not null);
    internal string LatestVersion => _update.LatestVersion;
    internal bool LatestSupportsBinary => _update.SupportsBinary;
    internal DateTimeOffset? CheckedAt => _update.CheckedAt;
    internal bool AutomaticallyChecks => _update.AutomaticallyChecks;
    internal bool UpdateAvailable => Selected is { } selected && UpdateAvailableFor(selected);
    internal bool UpdateAvailableFor(CLIInstallation installation) => ValidVersion(installation.Version)
        && ValidVersion(LatestVersion) && Version.Parse(LatestVersion) > Version.Parse(installation.Version);
    internal bool Checking { get; private set; }
    internal string CheckError { get; private set; } = "";
    internal bool Busy { get; private set; }
    internal string Message { get; private set; } = "";

    internal void SetNpmPath(string path)
    {
        _update = _update with { ManualNpmPath = Environment.ExpandEnvironmentVariables(path.Trim().Trim('"')), SelectedId = "", ManualCliPath = "" };
        SaveUpdateState();
    }

    internal void SelectInstallation(string id)
    {
        if (!Installations.Any(item => item.Id == id)) throw new InvalidOperationException(L("所选安装已不可用，请重新检测。"));
        _update = _update with { SelectedId = id };
        SaveUpdateState();
    }

    internal void SetCliPath(string path)
    {
        path = Environment.ExpandEnvironmentVariables(path.Trim().Trim('"'));
        _update = _update with { ManualCliPath = path, SelectedId = path };
        SaveUpdateState();
    }

    // wslDistribution is probed even when stopped, for an operation on that distribution.
    internal async Task DiscoverAsync(bool includeStoppedWsl = false, string? wslDistribution = null)
    {
        if (Busy || Checking) return;
        Busy = true;
        try { if (await DetectAsync(includeStoppedWsl, wslDistribution) is { } detection) Show(detection); }
        finally { Busy = false; }
    }

    // Detects again while a CLI found earlier may be running; quietly, Busy stays false and nothing shows
    // a detection in progress. What is shown keeps describing the running CLI: a detection that selects
    // another CLI waits for ShowRedetection (Changed), and one without a CLI that can start is dropped (Missing).
    internal async Task<Redetection> RedetectAsync(bool quietly)
    {
        if (Busy || Checking) return Redetection.Unchanged;
        var before = Selected;
        if (!quietly) Busy = true;
        Detection? detection;
        try { detection = await DetectAsync(includeStoppedWsl: false, wslDistribution: null); }
        finally { if (!quietly) Busy = false; }
        if (detection is null) return Redetection.Unchanged;
        if (Find(detection, detection.SelectedId) is not { Compatible: true } selected) return Redetection.Missing;
        if (before is null || !SameLaunch(before, selected)) { _held = detection; return Redetection.Changed; }
        Show(detection);
        return Redetection.Unchanged;
    }

    // Shows the detection that selected another CLI, right before connecting to that CLI.
    internal void ShowRedetection()
    {
        if (_held is { } held) Show(held);
    }

    // Shows the last detection when the CLI it selected can still start, so a launch can connect at once.
    internal bool RestoreLastDetection()
    {
        try
        {
            var saved = JsonSerializer.Deserialize<Detection>(File.ReadAllText(_detectionFile), JsonOptions);
            if (saved is null || saved.ManualNpmPath != ManualNpmPath || saved.ManualCliPath != ManualCliPath ||
                Find(saved, _update.SelectedId) is not { Compatible: true } selected || !CanStart(selected)) return false;
            _shown = saved;
            Message = saved.Message;
            return true;
        }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException) { return false; }
    }

    // Only starting a WSL distribution could tell, and connecting starts it anyway.
    private static bool CanStart(CLIInstallation installation) =>
        File.Exists(installation.Executable) && (installation.InWsl || installation.Arguments.All(File.Exists));

    // The same CLI started the same way; any other version or argv would run something else.
    private static bool SameLaunch(CLIInstallation shown, CLIInstallation detected) =>
        shown.Id.Equals(detected.Id, StringComparison.OrdinalIgnoreCase) && shown.Executable == detected.Executable &&
        shown.Arguments.SequenceEqual(detected.Arguments) && shown.Version == detected.Version && shown.Compatible == detected.Compatible;

    // An empty id stands for the first installation, as on a first detection.
    private static CLIInstallation? Find(Detection detection, string id) => id.Length > 0
        ? detection.Installations.FirstOrDefault(item => item.Id.Equals(id, StringComparison.OrdinalIgnoreCase)) : detection.Installations.FirstOrDefault();

    // Null when a later detection started meanwhile: that one is current.
    private async Task<Detection?> DetectAsync(bool includeStoppedWsl, string? wslDistribution)
    {
        var number = ++_detections;
        var scan = new Detection { ManualNpmPath = ManualNpmPath, ManualCliPath = ManualCliPath };
        var searchPath = _searchPath ?? string.Join(Path.PathSeparator,
            Environment.GetEnvironmentVariable("PATH"), Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.User),
            Environment.GetEnvironmentVariable("PATH", EnvironmentVariableTarget.Machine));
        var paths = ManualNpmPath.Length > 0 ? [ManualNpmPath] : NpmCandidates(searchPath);
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var npmEnvironments = new List<NpmEnvironment>();
        foreach (var path in paths)
        {
            try
            {
                var npm = await ResolveNpmAsync(path, searchPath);
                scan.Npm ??= npm;
                if (seen.Add(npm.Identity)) { npmEnvironments.Add(npm); await AddInstallationAsync(scan, npm); }
            }
            catch (Exception error) when (error is IOException or InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception)
            { if (ManualNpmPath.Length > 0) scan.Message = error.Message; }
        }
        if (ManualNpmPath.Length == 0) await DiscoverMiseAsync(scan, searchPath);
        if (ManualCliPath.Length > 0) await DiscoverManualAsync(scan);
        // WSL entries come after Windows ones, so a first run keeps the local CLI.
        if (ManualNpmPath.Length == 0 && ManualCliPath.Length == 0) await DiscoverWslAsync(scan, includeStoppedWsl, wslDistribution);
        if (ManualCliPath.Length == 0 && npmEnvironments.FirstOrDefault() is { } local && scan.Installations.All(item => item.InWsl))
            scan.InstallTargets.Insert(0, new(Path.Combine(local.Modules, "@konbakuyomu", "smart-search"), "Windows", local));
        // mise installs each version separately; follow the same tool after upgrades outside the App.
        var selectedId = _update.SelectedId;
        if (selectedId.Length > 0 && Find(scan, selectedId) is null && ManualCliPath.Length == 0 &&
            !selectedId.StartsWith(WslIdPrefix, StringComparison.Ordinal) &&
            scan.Installations.FirstOrDefault(item => item.Source == "mise") is { } mise &&
            MiseToolDirectory(selectedId) is { } selectedTool &&
            selectedTool.Equals(MiseToolDirectory(mise.Id), StringComparison.OrdinalIgnoreCase))
            selectedId = mise.Id;
        if (selectedId.Length > 0 && Find(scan, selectedId) is null)
            scan.Message = L("所选安装已不可用，请重新检测或选择其他安装。");
        var selected = Find(scan, selectedId);
        scan.SelectedId = selected?.Id ?? selectedId;
        // Versions are checked with the npm that would install them.
        if (selected is { InWsl: true } wsl) scan.Npm = scan.WslNpm.GetValueOrDefault(wsl.Id) ?? scan.Npm;
        else if (selected is { } chosen)
            scan.Npm = npmEnvironments.FirstOrDefault(item => chosen.Source == "npm"
                ? item.Prefix == chosen.Prefix && item.Command.SequenceEqual(chosen.Manager)
                : item.NodePath == chosen.Executable) ?? scan.Npm;
        else scan.Npm ??= scan.InstallTargets.FirstOrDefault(target => target.Npm is not null)?.Npm;
        if (scan.Npm is null && scan.Message.Length == 0 && selected is null)
            scan.Message = L("未找到可用的 npm。请先安装 Node.js，或手动指定 npm 路径。");
        return number == _detections ? scan : null;
    }

    private void Show(Detection detection)
    {
        _shown = detection;
        _held = null;
        Message = detection.Message;
        var update = _update with { SelectedId = detection.SelectedId };
        // Another npm starts its own update record.
        if (detection.Npm is { } npm && update.Identity != npm.Identity)
        {
            update = update with { Identity = npm.Identity, LatestVersion = "", SupportsBinary = false, CheckedAt = null, AttemptedAt = null };
            _checkedAtLaunch = false;
            CheckError = "";
        }
        if (update != _update) { _update = update; SaveUpdateState(); }
        // Only a shortcut for the next launch, which otherwise detects again.
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_detectionFile)!);
            var temporary = _detectionFile + ".tmp";
            File.WriteAllText(temporary, JsonSerializer.Serialize(detection, JsonOptions));
            File.Move(temporary, _detectionFile, overwrite: true);
        }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
    }

    private string[] NpmCandidates(string searchPath)
    {
        var directories = searchPath.Split(Path.PathSeparator).Where(Path.IsPathFullyQualified).ToList();
        if (_searchPath is null)
        {
            var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            directories.AddRange([Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "nodejs"), Path.Combine(local, "nodejs")]);
            var miseRoots = new[] { Environment.GetEnvironmentVariable("MISE_DATA_DIR"), Path.Combine(local, "mise") };
            foreach (var mise in miseRoots.Where(root => !string.IsNullOrEmpty(root)).Distinct())
            {
                directories.Add(Path.Combine(mise!, "shims"));
                var installs = Path.Combine(mise!, "installs", "node");
                if (Directory.Exists(installs)) directories.AddRange(Directory.GetDirectories(installs).OrderByDescending(VersionFromDirectory));
            }
            var nvm = Environment.GetEnvironmentVariable("NVM_HOME");
            if (!string.IsNullOrEmpty(nvm) && Directory.Exists(nvm))
                directories.AddRange(Directory.GetDirectories(nvm, "v*").OrderByDescending(VersionFromDirectory));
            var volta = Environment.GetEnvironmentVariable("VOLTA_HOME") ?? Path.Combine(local, "Volta");
            directories.Add(Path.Combine(volta, "bin"));
            var nvmLink = Environment.GetEnvironmentVariable("NVM_SYMLINK");
            if (!string.IsNullOrEmpty(nvmLink)) directories.Add(nvmLink);
        }
        // mise may expose native npm.exe shims; prefer them to .cmd.
        return directories.Distinct(StringComparer.OrdinalIgnoreCase)
            .SelectMany(directory => new[] { Path.Combine(directory, "npm.exe"), Path.Combine(directory, "npm.cmd") })
            .Where(File.Exists).ToArray();
    }

    private static Version VersionFromDirectory(string path) => Version.TryParse(Path.GetFileName(path).TrimStart('v'), out var version) ? version : new Version();

    private static async Task<NpmEnvironment> ResolveNpmAsync(string path, string searchPath)
    {
        if (!Path.IsPathFullyQualified(path) || !File.Exists(path)) throw new InvalidOperationException(L("npm 路径无效，请选择可执行的 npm 文件。"));
        var directory = Path.GetDirectoryName(path)!;
        var node = Path.Combine(directory, "node.exe");
        if (!File.Exists(node)) throw new InvalidOperationException(L("npm 同目录下未找到 Node.js，请选择完整的 Node.js 安装。"));
        var environment = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase) { ["PATH"] = directory + Path.PathSeparator + searchPath };
        var actualNode = (await CommandAsync([node, "-p", "process.execPath"], environment)).Trim();
        if (!Path.IsPathFullyQualified(actualNode) || !File.Exists(actualNode)) throw new InvalidOperationException(L("无法确认 Node.js 的实际路径。"));
        environment["PATH"] = Path.GetDirectoryName(actualNode) + Path.PathSeparator + searchPath;
        var nodeVersion = (await CommandAsync([actualNode, "-p", "process.versions.node"], environment)).Trim();
        if (!Version.TryParse(nodeVersion, out var parsed) || parsed.Major < 18) throw new InvalidOperationException(L("请使用 Node.js 18 或更新版本。"));
        string[] command;
        var bundledNpm = Path.Combine(Path.GetDirectoryName(actualNode)!, "node_modules", "npm", "bin", "npm-cli.js");
        if (File.Exists(bundledNpm) && !File.GetAttributes(bundledNpm).HasFlag(FileAttributes.ReparsePoint)) command = [actualNode, bundledNpm];
        else
        {
            // Do not run npm.cmd through cmd.exe. Fixed Node + trusted npm-cli.js
            // preserves paths with spaces, quotes, and metacharacters as argv.
            var script = Path.Combine(directory, "node_modules", "npm", "bin", "npm-cli.js");
            if (!Path.GetExtension(path).Equals(".cmd", StringComparison.OrdinalIgnoreCase) || !File.Exists(script) || File.GetAttributes(script).HasFlag(FileAttributes.ReparsePoint))
                throw new InvalidOperationException(L("无法找到与 Node.js 配套的 npm，请重新选择 npm 路径。"));
            command = [actualNode, script];
        }
        var version = (await CommandAsync([.. command, "--version"], environment)).Trim();
        var prefix = (await CommandAsync([.. command, "prefix", "--global"], environment)).Trim();
        var modules = (await CommandAsync([.. command, "root", "--global", "--prefix", prefix], environment)).Trim();
        if (!ValidVersion(version) || !Path.IsPathFullyQualified(prefix) || !Path.IsPathFullyQualified(modules) || prefix.Contains('\n') || modules.Contains('\n'))
            throw new InvalidOperationException(L("npm 返回了无效的版本或安装目录。"));
        return new(path, actualNode, version, prefix, modules, command, environment);
    }

    private async Task AddInstallationAsync(Detection scan, NpmEnvironment npm, string? packageRoot = null, string source = "npm",
        string[]? manager = null, string note = "", string[]? options = null)
    {
        var root = packageRoot ?? Path.Combine(npm.Modules, "@konbakuyomu", "smart-search");
        var manifest = Path.Combine(root, "package.json");
        if (!File.Exists(manifest)) return;
        try
        {
            using var package = JsonDocument.Parse(await File.ReadAllTextAsync(manifest));
            var metadata = package.RootElement;
            if (String(metadata, "name") != Package) return;
            var environment = new Dictionary<string, string>(npm.Environment, StringComparer.OrdinalIgnoreCase)
                { ["SMART_SEARCH_PACKAGE_ROOT"] = root, ["SMART_SEARCH_NODE_PATH"] = npm.NodePath };
            var installation = new CLIInstallation(root, npm.NodePath, [Path.Combine(root, "npm", "bin", "smart-search.js")], String(metadata, "version"), source, false, manager ?? npm.Command, npm.Prefix, environment, note, options);
            // Legacy wrappers can bootstrap Python as a side effect. Never probe them.
            if (metadata.TryGetProperty("smartSearchBinary", out var binary) && binary.ValueKind == JsonValueKind.True)
            {
                try
                {
                    using var result = JsonDocument.Parse(await CommandAsync([installation.Executable, .. installation.Arguments, "--desktop-capabilities"], environment, 45));
                    var info = result.RootElement;
                    installation = installation with { Compatible = String(info, "product") == "smart-search" && String(info, "version") == installation.Version
                        && info.TryGetProperty("desktop_protocol_version", out var protocol) && protocol.TryGetInt32(out var number) && number == 1 };
                }
                catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception) { }
            }
            if (!installation.Compatible && installation.Note.Length == 0)
                installation = installation with { Note = L("已找到 Smart Search CLI，但此版本不支持当前 App。请更新 CLI，或选择兼容的独立下载版。") };
            scan.Installations.RemoveAll(item => item.Id.Equals(root, StringComparison.OrdinalIgnoreCase));
            scan.Installations.Add(installation);
        }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException) { scan.Message = L("CLI 安装信息损坏，请更新或修复。"); }
    }

    private async Task DiscoverMiseAsync(Detection scan, string searchPath)
    {
        var mise = searchPath.Split(Path.PathSeparator).Where(Path.IsPathFullyQualified)
            .Select(directory => Path.Combine(directory, "mise.exe")).FirstOrDefault(File.Exists);
        if (mise is null) return;
        try
        {
            const string tool = "npm:" + Package;
            var env = new Dictionary<string, string> { ["PATH"] = searchPath };
            using var installed = JsonDocument.Parse(await CommandAsync([mise, "ls", "--global", "--json", tool], env));
            var rows = installed.RootElement.ValueKind == JsonValueKind.Array ? installed.RootElement : installed.RootElement.GetProperty(tool);
            if (rows.GetArrayLength() == 0) return;
            if ((await CommandAsync([mise, "which", "--plugin", "smart-search"], env)).Trim() != tool) return;
            var entry = (await CommandAsync([mise, "which", "smart-search"], env)).Trim();
            foreach (var row in rows.EnumerateArray())
            {
                if (!row.TryGetProperty("active", out var active) || active.ValueKind != JsonValueKind.True ||
                    !row.TryGetProperty("installed", out var present) || present.ValueKind != JsonValueKind.True) continue;
                var install = String(row, "install_path");
                if (!Path.IsPathFullyQualified(install) || !Path.IsPathFullyQualified(entry) ||
                    !Path.GetFullPath(entry).StartsWith(Path.GetFullPath(install) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) continue;
                var node = (await CommandAsync([mise, "which", "node"], env)).Trim();
                if (!Path.IsPathFullyQualified(node) || !File.Exists(node)) continue;
                node = (await CommandAsync([node, "-p", "process.execPath"], env)).Trim();
                if (!Path.IsPathFullyQualified(node) || !File.Exists(node)) continue;
                var version = (await CommandAsync([node, "-p", "process.versions.node"], env)).Trim();
                if (!Version.TryParse(version, out var nodeVersion) || nodeVersion.Major < 18) continue;
                env["PATH"] = Path.GetDirectoryName(node) + Path.PathSeparator + searchPath;
                var owner = row.GetProperty("source");
                var global = Environment.GetEnvironmentVariable("MISE_GLOBAL_CONFIG_FILE") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".config", "mise", "config.toml");
                var owned = String(owner, "type") == "mise.toml" && Path.IsPathFullyQualified(String(owner, "path")) &&
                    Path.GetFullPath(String(owner, "path")).Equals(Path.GetFullPath(global), StringComparison.OrdinalIgnoreCase) &&
                    string.IsNullOrEmpty(Environment.GetEnvironmentVariable("MISE_CONFIG_FILE")) && string.IsNullOrEmpty(Environment.GetEnvironmentVariable("MISE_ENV"));
                var options = owned ? MiseOptions((await CommandAsync([mise, "config", "get", "--global", "tools." + tool], env)).Trim(), String(row, "requested_version")) : null;
                var modules = Path.Combine(install, "node_modules");
                var context = new NpmEnvironment("", node, "", install, modules, [], env);
                await AddInstallationAsync(scan, context, Path.Combine(modules, "@konbakuyomu", "smart-search"), "mise", options is null ? [] : [mise],
                    options is null ? L("此 mise 安装有环境覆盖或复杂版本约束，请在原终端更新。") : "", options);
                // Prefer the active global mise tool over unrelated Node npm prefixes on first discovery.
                var match = scan.Installations.FindIndex(item => item.Source == "mise");
                if (match >= 0) { var item = scan.Installations[match]; scan.Installations.RemoveAt(match); scan.Installations.Insert(0, item); }
            }
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception or KeyNotFoundException or ArgumentException)
        { scan.Message = L("mise 环境检测未完成，请重新检测或手动选择 CLI。") + "\n" + error.Message; }
    }

    private async Task DiscoverWslAsync(Detection scan, bool includeStopped, string? requested)
    {
        if (!WslAvailable) return;
        string[] distributions, running;
        try
        {
            // Listing never starts a distribution; probing one does (about 4 s from cold).
            distributions = WslNames(await CommandAsync([_wslPath!, "--list", "--quiet"], WslEnvironment));
            running = WslNames(await CommandAsync([_wslPath!, "--list", "--running", "--quiet"], WslEnvironment));
        }
        catch (Exception error) when (error is InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception) { return; }
        scan.WslDistributions = distributions;
        var selected = _update.SelectedId.StartsWith(WslIdPrefix, StringComparison.Ordinal) ? _update.SelectedId[WslIdPrefix.Length..] : "";
        var stopped = new List<string>();
        var found = false;
        foreach (var distribution in distributions)
        {
            if (!includeStopped && !running.Contains(distribution, StringComparer.OrdinalIgnoreCase) &&
                !distribution.Equals(selected, StringComparison.OrdinalIgnoreCase) && !distribution.Equals(requested, StringComparison.OrdinalIgnoreCase))
            { stopped.Add(distribution); continue; }
            found |= await AddWslInstallationAsync(scan, distribution);
        }
        scan.StoppedWslDistributions = [.. stopped];
        // A probed distribution without a CLI becomes an install target, which explains itself.
        if (includeStopped && !found && scan.Message.Length == 0 && !scan.InstallTargets.Any(target => target.Id.StartsWith(WslIdPrefix, StringComparison.Ordinal)))
            scan.Message = distributions.Length == 0 ? L("没有找到 WSL 发行版。")
                : L("没有在 WSL 中找到 smart-search。请先在 WSL 中安装 CLI，并确认 bash 能直接运行 smart-search。");
    }

    // Older WSL ignores WSL_UTF8 and prints UTF-16; dropping NULs recovers the ASCII names.
    private static string[] WslNames(string output) => output.Replace("\0", "").Split('\n', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)
        .Where(name => !name.StartsWith("docker-desktop", StringComparison.OrdinalIgnoreCase)).ToArray();

    // Everything starts in the Linux home. From the App's Windows profile directory, mise and npm
    // would read the Windows config files there as project settings, and mise refuses them.
    private static string[] WslArguments(string distribution, IEnumerable<string> command) => ["-d", distribution, "--cd", "~", "--exec", .. command];

    private Task<string> WslAsync(string distribution, string mode, string script, params string[] arguments) =>
        CommandAsync([_wslPath!, .. WslArguments(distribution, ["bash", mode, script, "smart-search", .. arguments])], WslEnvironment, 45);

    // The probe scripts report facts as "smart-search-<name>=<value>" lines between any profile output.
    private static Dictionary<string, string> WslFacts(string output) => output.Split('\n')
        .Select(line => line.TrimEnd('\r')).Where(line => line.StartsWith("smart-search-", StringComparison.Ordinal) && line.Contains('='))
        .Select(line => (Name: line["smart-search-".Length..line.IndexOf('=')], Value: line[(line.IndexOf('=') + 1)..]))
        .GroupBy(fact => fact.Name).ToDictionary(group => group.Key, group => group.Last().Value);

    private async Task<bool> AddWslInstallationAsync(Detection scan, string distribution)
    {
        var id = WslIdPrefix + distribution;
        (string Mode, string Node)? shell = null;
        var probed = false;
        // A login shell reads ~/.profile (mise shims, ~/.local/bin); nvm loads only in an interactive ~/.bashrc.
        foreach (var mode in new[] { "-lc", "-ic" })
        {
            JsonElement info;
            Dictionary<string, string> facts;
            try
            {
                var output = await WslAsync(distribution, mode, WslProbe);
                using var result = JsonDocument.Parse(output.Split('\n').Select(line => line.Trim()).LastOrDefault(line => line.StartsWith('{')) ?? "");
                info = result.RootElement.Clone();
                facts = WslFacts(output);
            }
            catch (Exception error) when (error is InvalidOperationException or TimeoutException or JsonException or System.ComponentModel.Win32Exception) { continue; }
            probed = true;
            var shellNode = facts.GetValueOrDefault("node", "");
            if (String(info, "product") != "smart-search")
            {
                if (shellNode.StartsWith('/')) shell ??= (mode, shellNode);
                continue;
            }
            var launch = info.TryGetProperty("launch_command", out var command) && command.ValueKind == JsonValueKind.Array
                ? command.EnumerateArray().Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() ?? "" : "").ToArray() : [];
            // The App starts this argv directly with --exec, so it must be absolute inside the distribution.
            var compatible = info.TryGetProperty("desktop_protocol_version", out var protocol) && protocol.TryGetInt32(out var number) && number == 1 &&
                launch.Length > 0 && launch[0].StartsWith('/') && launch.All(item => item.Length > 0);
            // The npm package that owns this CLI: the launch command's wrapper, or the old wrapper's package.
            var (node, root) = compatible
                ? (launch[0], launch.Length == 2 && launch[1].EndsWith(WslWrapperSuffix, StringComparison.Ordinal) ? launch[1][..^WslWrapperSuffix.Length] : "")
                : (shellNode, facts.GetValueOrDefault("root", ""));
            var prefix = root.EndsWith(WslPackageSuffix, StringComparison.Ordinal) ? root[..^WslPackageSuffix.Length] : "";
            NpmEnvironment? npm = null;
            var problem = "unknown";
            // mise and asdf keep npm tools in versioned directories that only they may change.
            if (prefix.StartsWith('/') && node.StartsWith('/'))
                (npm, problem, _) = prefix.Contains("/installs/npm-", StringComparison.Ordinal) ? (null, "mise", false) : await WslNpmAsync(distribution, mode, node, prefix);
            // An older CLI behind a wrapper script: the shell's npm may still hold the package globally.
            else if (!compatible && root.Length == 0 && node.StartsWith('/'))
            {
                (npm, problem, var global) = await WslNpmAsync(distribution, mode, node, null);
                if (!global) (npm, problem) = (null, "unknown");
            }
            if (npm is not null) scan.WslNpm[id] = npm;
            var note = Sentences(compatible ? L("位于 WSL {0}，使用该发行版中的配置和 Skills。", distribution) : L("WSL {0} 中的 CLI 版本过旧，App 无法连接。", distribution),
                npm is not null ? "" : problem switch
                {
                    "mise" => L("此 CLI 由 mise 管理，请在 WSL 终端更新：mise use -g npm:@konbakuyomu/smart-search@latest"),
                    "permission" => L("npm 全局目录需要管理员权限，请在 WSL 终端更新：sudo npm install -g @konbakuyomu/smart-search@latest"),
                    _ => L("App 无法确定它的安装方式，请在 WSL 终端用原安装方式更新。")
                });
            var version = String(info, "version");
            scan.Installations.Add(new(id, _wslPath!, WslArguments(distribution, launch), version.Length > 0 ? version : L("旧版"),
                "wsl", compatible, npm?.Command ?? [], npm?.Prefix ?? "", new(WslEnvironment), note, Distribution: distribution));
            return true;
        }
        if (!probed) return false;
        var (target, reason, _) = shell is { } found ? await WslNpmAsync(distribution, found.Mode, found.Node, null) : (null, "node", false);
        scan.InstallTargets.Add(new(id, "WSL " + distribution, target, target is not null ? "" : reason switch
        {
            "permission" => L("WSL {0} 的 npm 全局目录需要管理员权限，App 不使用 sudo。请在 WSL 终端运行：sudo npm install -g @konbakuyomu/smart-search@latest", distribution),
            "npm" => L("WSL {0} 中的 Node.js 没有配套的 npm。请重新安装 Node.js，再点击“检测 WSL”。", distribution),
            _ => L("WSL {0} 中没有找到 Node.js 18 或更新版本。请先在 WSL 中安装 Node.js，再点击“检测 WSL”。", distribution)
        }));
        return false;
    }

    // The npm of this Node.js and the prefix it installs into: an existing CLI's, or npm's global one.
    // Package says whether that prefix already holds the CLI package.
    private async Task<(NpmEnvironment? Npm, string Problem, bool Package)> WslNpmAsync(string distribution, string mode, string node, string? prefix)
    {
        Dictionary<string, string> facts;
        try { facts = WslFacts(await WslAsync(distribution, mode, WslNpmCheck, prefix is null ? [node] : [node, prefix])); }
        catch (Exception error) when (error is InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception) { return (null, "npm", false); }
        if (!Version.TryParse(facts.GetValueOrDefault("node-version", ""), out var nodeVersion) || nodeVersion.Major < 18) return (null, "node", false);
        var npm = facts.GetValueOrDefault("npm", "");
        var root = facts.GetValueOrDefault("prefix", "");
        var package = facts.GetValueOrDefault("package") == "1";
        if (!npm.StartsWith('/') || !root.StartsWith('/')) return (null, "npm", false);
        if (facts.GetValueOrDefault("writable") != "1") return (null, "permission", package);
        return (new(npm, node, facts.GetValueOrDefault("npm-version", ""), root, root + "/lib/node_modules",
            [_wslPath!, .. WslArguments(distribution, ["bash", mode, WslNpmRun, "smart-search", node, npm])], new(WslEnvironment), distribution), "", package);
    }

    private static string Sentences(params string[] parts) => string.Join(Localization.Language == "zh" ? "" : " ", parts.Where(part => part.Length > 0));

    internal static string? MiseToolDirectory(string packageRoot)
    {
        var package = new DirectoryInfo(packageRoot);
        var scope = package.Parent;
        var modules = scope?.Parent;
        var tool = modules?.Parent?.Parent;
        return package.Name.Equals("smart-search", StringComparison.OrdinalIgnoreCase)
            && string.Equals(scope?.Name, "@konbakuyomu", StringComparison.OrdinalIgnoreCase)
            && string.Equals(modules?.Name, "node_modules", StringComparison.OrdinalIgnoreCase)
            && string.Equals(tool?.Name, "npm-konbakuyomu-smart-search", StringComparison.OrdinalIgnoreCase)
            ? tool?.FullName : null;
    }

    internal static string[]? MiseOptions(string config, string requested)
    {
        if (!ValidVersion(requested) && requested != "latest") return null;
        if (config == requested || config == "\"" + requested + "\"") return [];
        var lines = config.Split('\n', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries);
        if (!lines.Contains("version = \"" + requested + "\"")) return null;
        var options = new List<string>();
        foreach (var line in lines.Where(line => !line.StartsWith("version = ")))
        {
            var match = Regex.Match(line, "^allow_low_downloads = (true|false|\"true\"|\"false\")$");
            if (!match.Success) return null;
            options.AddRange(["--tool-option", "allow_low_downloads=" + match.Groups[1].Value]);
        }
        return options.ToArray();
    }

    private async Task DiscoverManualAsync(Detection scan)
    {
        try
        {
            if (!Path.IsPathFullyQualified(ManualCliPath) || !File.Exists(ManualCliPath) || !Path.GetExtension(ManualCliPath).Equals(".exe", StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException(L("请选择独立下载包中的 smart-search.exe。"));
            var root = Path.GetDirectoryName(ManualCliPath)!;
            using var manifest = JsonDocument.Parse(await File.ReadAllTextAsync(Path.Combine(root, "package.json")));
            if (String(manifest.RootElement, "name") != Package || !Directory.Exists(Path.Combine(root, "_internal")))
                throw new InvalidOperationException(L("请选择完整独立下载包中的 CLI，不要选择全局 shim 或脚本。"));
            using var result = JsonDocument.Parse(await CommandAsync([ManualCliPath, "--desktop-capabilities"], timeoutSeconds: 45));
            var info = result.RootElement;
            if (String(info, "product") != "smart-search" || String(info, "version") != String(manifest.RootElement, "version") ||
                !info.TryGetProperty("desktop_protocol_version", out var protocol) || !protocol.TryGetInt32(out var number) || number != 1)
                throw new InvalidOperationException(L("所选 CLI 与当前 App 不兼容。"));
            scan.Installations.Add(new(ManualCliPath, ManualCliPath, [], String(info, "version"), "manual", true, [], "", []));
        }
        catch (Exception error) when (error is IOException or JsonException or InvalidOperationException or TimeoutException or System.ComponentModel.Win32Exception)
        { scan.Message = error.Message; }
    }

    internal void SetAutomaticChecks(bool enabled)
    {
        _update = _update with { AutomaticallyChecks = enabled };
        SaveUpdateState();
    }

    internal async Task CheckAutomaticallyAsync(bool onLaunch = false)
    {
        if (!AutomaticallyChecks || Npm is null || Busy || Checking) return;
        if (!(onLaunch && !_checkedAtLaunch))
        {
            if (CheckedAt is { } checkedAt && _clock() - checkedAt < TimeSpan.FromHours(24)) return;
            if (_update.AttemptedAt is { } attemptedAt && _clock() - attemptedAt < TimeSpan.FromHours(1)) return;
        }
        _checkedAtLaunch = true;
        await CheckVersionAsync();
    }

    internal async Task CheckVersionAsync()
    {
        if (Npm is not { } npm || Busy || Checking) return;
        Checking = true;
        _update = _update with { AttemptedAt = _clock() };
        SaveUpdateState();
        try
        {
            string version;
            bool supportsBinary;
            if (_versionLoader is not null) { version = await _versionLoader(); supportsBinary = true; }
            else
            {
                using var metadata = JsonDocument.Parse(JsonText(await CommandAsync([.. npm.Command, "view", Package + "@latest", "--json"], npm.Environment, 60)));
                version = String(metadata.RootElement, "version");
                supportsBinary = metadata.RootElement.TryGetProperty("smartSearchBinary", out var binary) && binary.ValueKind == JsonValueKind.True;
            }
            if (!ValidVersion(version)) throw new InvalidOperationException(L("无法确认 CLI 的最新版本。"));
            _update = _update with { LatestVersion = version, SupportsBinary = supportsBinary, CheckedAt = _clock() };
            CheckError = "";
            SaveUpdateState();
        }
        catch (Exception error) { CheckError = error.Message; }
        finally { Checking = false; }
    }

    private void SaveUpdateState()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(_stateFile)!);
        var temporary = _stateFile + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(_update, JsonOptions));
        File.Move(temporary, _stateFile, overwrite: true);
    }

    // id names an installation or an install target; without one, the selected installation,
    // or the first target that can take a CLI when nothing is installed.
    internal async Task InstallOrRepairAsync(string expectedVersion, string? id = null)
    {
        if (Busy || Checking) return;
        var selectedBefore = Selected?.Id;
        id ??= selectedBefore ?? InstallTargets.FirstOrDefault(target => target.Npm is not null)?.Id;
        var distribution = id?.StartsWith(WslIdPrefix, StringComparison.Ordinal) == true ? id[WslIdPrefix.Length..] : null;
        var previous = Installations.FirstOrDefault(item => item.Id == id);
        await DiscoverAsync(wslDistribution: distribution);
        var current = Installations.FirstOrDefault(item => item.Id == id);
        if (previous is not null && (current is null || previous.Source != current.Source ||
            previous.Version != current.Version || !previous.Manager.SequenceEqual(current.Manager) ||
            !(previous.ManagerOptions ?? []).SequenceEqual(current.ManagerOptions ?? [])))
            throw new InvalidOperationException(L("CLI 来源或版本刚刚发生变化，请重新检查后再更新。"));
        var target = current is null ? InstallTargets.FirstOrDefault(item => item.Id == id)?.Npm : null;
        if (current is not { CanManage: true } && target is null) throw new InvalidOperationException(L("请在原管理器中更新，或选择其他安装。"));
        if (!ValidVersion(expectedVersion) || expectedVersion != LatestVersion || CheckError.Length > 0) throw new InvalidOperationException(L("请先成功检查 CLI 更新。"));
        if (!LatestSupportsBinary) throw new InvalidOperationException(L("npm 上尚未发布自带运行时的 CLI，请等待新版发布后再安装。"));
        Busy = true;
        Message = L("正在通过原管理器安装或更新 CLI…");
        try
        {
            var mise = current?.Source == "mise";
            if (mise)
            {
                await CommandAsync([.. current!.Manager, "use", "--global", "--pin", .. current.ManagerOptions ?? [], "npm:" + Package + "@" + expectedVersion], current.Environment, 1800);
                // The new version lives in a new directory; follow it only if it was in use.
                if (current.Id == selectedBefore) _update = _update with { SelectedId = "" };
            }
            else
                await CommandAsync([.. current?.Manager ?? target!.Command, "install", "--global", "--prefix", current?.Prefix ?? target!.Prefix,
                    "--include=optional", Package + "@" + expectedVersion], current?.Environment ?? target!.Environment, 1800);
            Busy = false;
            await DiscoverAsync(wslDistribution: distribution);
            var installed = mise ? Installations.FirstOrDefault(item => item.Source == "mise") : Installations.FirstOrDefault(item => item.Id == id);
            if (installed is not { Compatible: true } || installed.Version != expectedVersion) throw new InvalidOperationException(L("CLI 已安装，但运行验证未通过，请更新或修复。"));
            // Installing where nothing was in use starts using it; another environment keeps the current choice.
            if (selectedBefore is null) SelectInstallation(installed.Id);
            Message = selectedBefore is null || installed.Id == Selected?.Id ? L("CLI 安装完成，正在重新连接。") : L("{0} 中的 CLI 已安装或更新为 {1}。", installed.Place, expectedVersion);
        }
        finally { Busy = false; }
    }

    internal async Task UninstallAsync()
    {
        if (Busy || Checking || Selected is not { CanManage: true, Source: "npm" } selected) return;
        Busy = true;
        try
        {
            await CommandAsync([.. selected.Manager, "uninstall", "--global", "--prefix", selected.Prefix, Package], selected.Environment, 600);
            _shown.Installations = [];
            _update = _update with { SelectedId = "" };
            SaveUpdateState();
            Message = L("CLI 已卸载，配置和 Skills 已保留。");
        }
        finally { Busy = false; }
    }

    private static bool ValidVersion(string version) => Regex.IsMatch(version, @"^[0-9]+\.[0-9]+\.[0-9]+$");
    // A WSL shell profile may print before npm does; npm's JSON starts on a line of its own.
    private static string JsonText(string output) => output.StartsWith('{') || !output.Contains("\n{") ? output : output[(output.IndexOf("\n{", StringComparison.Ordinal) + 1)..];
    private static string String(JsonElement value, string name) => value.ValueKind == JsonValueKind.Object && value.TryGetProperty(name, out var property) && property.ValueKind == JsonValueKind.String ? property.GetString() ?? "" : "";

    internal static async Task<string> CommandAsync(IEnumerable<string> arguments, Dictionary<string, string>? environment = null, int timeoutSeconds = 15)
    {
        var command = arguments.ToArray();
        var start = new ProcessStartInfo(command[0]) { UseShellExecute = false, CreateNoWindow = true,
            WorkingDirectory = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile),
            RedirectStandardOutput = true, RedirectStandardError = true, RedirectStandardInput = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8, StandardErrorEncoding = System.Text.Encoding.UTF8 };
        foreach (var argument in command.Skip(1)) start.ArgumentList.Add(argument);
        if (environment is not null) foreach (var (key, value) in environment) start.Environment[key] = value;
        using var process = Process.Start(start) ?? throw new InvalidOperationException(L("CLI 操作未完成，请检查 npm 或重试。"));
        process.StandardInput.Close();
        var output = process.StandardOutput.ReadToEndAsync();
        var diagnostics = process.StandardError.ReadToEndAsync();
        try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(timeoutSeconds)); }
        catch { if (!process.HasExited) process.Kill(entireProcessTree: true); throw; }
        var detail = await diagnostics;
        if (process.ExitCode != 0) throw new InvalidOperationException(L("CLI 操作未完成，请检查 npm 或重试。") + "\n" + detail[^Math.Min(detail.Length, 2000)..]);
        return await output;
    }
}
