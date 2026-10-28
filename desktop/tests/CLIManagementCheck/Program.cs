using System.Text.Json;
using SmartSearch.Desktop;

Console.OutputEncoding = new System.Text.UTF8Encoding(false);
// A failed check exits at once; Windows Error Reporting would otherwise keep the executable locked.
AppDomain.CurrentDomain.UnhandledException += (_, error) => { Console.Error.WriteLine(error.ExceptionObject); Environment.Exit(1); };
if (args[0] == "--discover")
{
    var live = new CLIInstallationManager(Path.GetFullPath(args[1]));
    await live.DiscoverAsync(includeStoppedWsl: args.Contains("--include-stopped-wsl"));
    Console.WriteLine(JsonSerializer.Serialize(new { live.Message, npm = live.Npm?.NpmPath, selected = live.Selected?.Id,
        wsl = live.WslDistributions, stopped = live.StoppedWslDistributions,
        installations = live.Installations.Select(item => new { item.Id, item.Title, item.Source, item.Version, item.Compatible, item.CanManage, item.Note, item.Arguments, item.Manager, item.Prefix }),
        targets = live.InstallTargets.Select(item => new { item.Id, item.Place, item.Note, npm = item.Npm?.Command, prefix = item.Npm?.Prefix }) }));
    return;
}
// Installs or updates one installation or target on this machine, e.g. "wsl://Ubuntu-24.04", as the App would.
if (args[0] == "--manage")
{
    var live = new CLIInstallationManager(Path.GetFullPath(args[1]));
    await live.DiscoverAsync(includeStoppedWsl: true);
    await live.CheckVersionAsync();
    await live.InstallOrRepairAsync(live.LatestVersion, args[2]);
    Console.WriteLine(JsonSerializer.Serialize(new { live.Message, live.LatestVersion, selected = live.Selected?.Id,
        installations = live.Installations.Select(item => new { item.Id, item.Version, item.Compatible, item.CanManage }) }));
    return;
}
// The same executable doubles as a fake wsl.exe: listing, running state, the probe, the npm check and npm itself.
if (Environment.GetEnvironmentVariable("SMART_SEARCH_WSL_FIXTURE") is { } wslFixture && args[0] is "--list" or "-d")
{
    if (args[0] == "--list")
    {
        Console.Write(args.Contains("--running") ? "Debian\r\nOld\r\nArch\r\nFedora\r\nWrapped\r\n" : "Ubuntu-24.04\r\ndocker-desktop\r\nDebian\r\nOld\r\nArch\r\nFedora\r\nWrapped\r\n");
        return;
    }
    // Every command starts in the Linux home, then runs a script in bash with "smart-search" as $0.
    var (distribution, command) = (args[1], args[(Array.IndexOf(args, "--exec") + 1)..]);
    if (!args[2..4].SequenceEqual(["--cd", "~"]) || command[0] != "bash" || command[3] != "smart-search") Environment.Exit(9);
    var (mode, script) = (command[1], command[2]);
    // An install by the App leaves [node, prefix] behind; from then on the distribution has a current CLI.
    var installed = Path.Combine(wslFixture, "wsl-" + distribution + ".json");
    if (script.Contains("command -v smart-search"))
    {
        File.AppendAllText(Path.Combine(wslFixture, "wsl-probes.txt"), distribution + " " + mode + "\n");
        Console.WriteLine("profile noise {");
        if (File.Exists(installed) && JsonSerializer.Deserialize<string[]>(File.ReadAllText(installed)) is [var installedNode, var installedPrefix])
        {
            Console.WriteLine(JsonSerializer.Serialize(new { product = "smart-search", version = "1.2.4", desktop_protocol_version = 1,
                launch_command = new[] { installedNode, installedPrefix + "/lib/node_modules/@konbakuyomu/smart-search/npm/bin/smart-search.js" } }));
            return;
        }
        Console.WriteLine((distribution, mode) switch
        {
            ("Debian", "-lc") => """{"product":"smart-search","version":"1.2.3","desktop_protocol_version":1,"launch_command":["/usr/bin/node","/usr/lib/node_modules/@konbakuyomu/smart-search/npm/bin/smart-search.js"]}""",
            ("Ubuntu-24.04", "-ic") => """{"product":"smart-search","version":"1.2.4","desktop_protocol_version":1,"launch_command":["/home/u/.nvm/versions/node/v22.0.0/bin/node","/home/u/.nvm/versions/node/v22.0.0/lib/node_modules/@konbakuyomu/smart-search/npm/bin/smart-search.js"]}""",
            ("Old", _) => "smart-search-node=/home/o/node/bin/node\nsmart-search-root=/home/o/node/lib/node_modules/@konbakuyomu/smart-search\n" + """{"product":"smart-search","legacy":true,"version":"1.2.2"}""",
            ("Arch", "-ic") => "smart-search-node=/home/a/node/bin/node\n" + """{"missing":true}""",
            // A CLI from before launch_command, reached through a wrapper script rather than an npm link.
            ("Wrapped", _) => "smart-search-node=/home/w/node/bin/node\n" + """{"product":"smart-search","version":"1.2.3","desktop_protocol_version":1}""",
            _ => """{"missing":true}"""
        });
        return;
    }
    var node = command[4];
    var npm = node[..node.LastIndexOf("/bin/node", StringComparison.Ordinal)] + "/lib/node_modules/npm/bin/npm-cli.js";
    if (script.Contains("npm-cli.js"))
    {
        // A system Node.js under /usr cannot be written without sudo.
        var prefix = command.Length > 5 ? command[5] : distribution == "Arch" ? "/home/a/.npm-global" : node[..^"/bin/node".Length];
        Console.WriteLine($"smart-search-node-version=22.0.0\nsmart-search-npm={npm}\nsmart-search-prefix={prefix}\nsmart-search-writable={(prefix == "/usr" ? 0 : 1)}\nsmart-search-npm-version=10.9.1");
        if (distribution == "Wrapped" || File.Exists(installed)) Console.WriteLine("smart-search-package=1");
        return;
    }
    if (command[5] != npm) Environment.Exit(8);
    var operation = command[6..];
    if (operation[0] == "view") { Console.WriteLine("profile noise\n{\n  \"version\": \"1.2.4\",\n  \"smartSearchBinary\": true\n}"); return; }
    if (operation[0] != "install") Environment.Exit(7);
    File.WriteAllText(Path.Combine(wslFixture, "wsl-operations.json"), JsonSerializer.Serialize(args));
    File.WriteAllText(installed, JsonSerializer.Serialize(new[] { node, operation[Array.IndexOf(operation, "--prefix") + 1] }));
    return;
}
var miseInstall = Path.Combine("mise", "installs", "npm-konbakuyomu-smart-search", "1.2.3");
if (Environment.GetEnvironmentVariable("SMART_SEARCH_MISE_FIXTURE") is { } fixture && args[0] is "which" or "ls" or "config" or "use")
{
    var install = Path.Combine(fixture, miseInstall);
    var package = Path.Combine(install, "node_modules", "@konbakuyomu", "smart-search");
    var node = Path.Combine(fixture, "npm 2 & space", "node.exe");
    if (args[0] == "which") Console.WriteLine(args.Contains("--plugin") ? "npm:@konbakuyomu/smart-search" : args.Last() == "node" ? node : Path.Combine(package, "npm", "bin", "smart-search.js"));
    if (args[0] == "ls") Console.WriteLine(JsonSerializer.Serialize(new[] { new { version = "1.2.3", requested_version = "1.2.3", active = true, installed = true, install_path = install, source = new { type = "mise.toml", path = Path.Combine(fixture, "global.toml") } } }));
    if (args[0] == "config") Console.WriteLine("version = \"1.2.3\"\nallow_low_downloads = \"true\"");
    if (args[0] == "use")
    {
        File.WriteAllText(Path.Combine(fixture, "mise-operations.json"), JsonSerializer.Serialize(args));
        var manifest = Path.Combine(package, "package.json");
        File.WriteAllText(manifest, File.ReadAllText(manifest).Replace("1.2.3", "1.2.4"));
    }
    return;
}
var root = Path.GetFullPath(args[0]);
var first = Path.Combine(root, "npm 1 & space");
var second = Path.Combine(root, "npm 2 & space");
var now = DateTimeOffset.UtcNow;
var checks = 0;
var fail = false;
Task<string> Load() { checks++; return fail ? Task.FromException<string>(new IOException("offline")) : Task.FromResult("1.2.4"); }
var manager = new CLIInstallationManager(Path.Combine(root, "state"), first + Path.PathSeparator + second, Load, () => now);
await manager.DiscoverAsync();
Check(manager.Npm?.Prefix == first && manager.Selected is { Compatible: false, CanManage: true }, "Legacy installation detection");
Check(manager.Installations.Count == 2, "Discover all npm prefixes without silently replacing first selection");
Check(!File.Exists(Path.Combine(root, "legacy-executed")), "Must not run legacy Python wrapper");
manager.SelectInstallation(manager.Installations.Single(item => item.Prefix == second).Id);
await manager.DiscoverAsync();
Check(manager.Npm?.Prefix == second && manager.Selected?.Compatible == true, "Selecting an installation also selects its original npm environment");
manager.SetNpmPath(Path.Combine(root, "missing", "npm.cmd"));
await manager.DiscoverAsync();
Check(manager.Npm is null && manager.Selected is null, "Manual invalid path must not auto-fallback");
manager.SetNpmPath(Path.Combine(second, "npm.cmd"));
await manager.DiscoverAsync();
Check(manager.Npm?.Prefix == second && manager.Selected?.Compatible == true, "Manual path with spaces and ampersand must use trusted npm JS without cmd.exe");
// The last detection would start fine here, but it was made with the other npm path.
var otherSettings = Path.Combine(root, "other npm path state");
Directory.CreateDirectory(otherSettings);
foreach (var file in new[] { "cli-npm-state.json", "cli-detection.json" }) File.Copy(Path.Combine(root, "state", file), Path.Combine(otherSettings, file));
var otherNpm = new CLIInstallationManager(otherSettings, first + Path.PathSeparator + second, Load, () => now);
otherNpm.SetNpmPath(Path.Combine(first, "npm.cmd"));
Check(!otherNpm.RestoreLastDetection(), "A launch does not restore a detection made with another npm path");
await manager.CheckAutomaticallyAsync(onLaunch: true);
await manager.CheckAutomaticallyAsync(onLaunch: true);
Check(checks == 1 && manager.UpdateAvailable, "Startup/update notification");
now = now.AddSeconds(86399);
await manager.CheckAutomaticallyAsync();
Check(checks == 1, "Early periodic check");
now = now.AddSeconds(1);
await manager.CheckAutomaticallyAsync();
Check(checks == 2, "24 hour check");
var success = manager.CheckedAt;
fail = true;
now = now.AddHours(24);
await manager.CheckAutomaticallyAsync();
await manager.CheckAutomaticallyAsync();
Check(checks == 3 && manager.CheckedAt == success && manager.CheckError.Length > 0, "Failure cache and retry backoff");
manager.SetAutomaticChecks(false);
now = now.AddHours(24);
await manager.CheckAutomaticallyAsync();
Check(checks == 3, "Disabled preference");
fail = false;
await manager.CheckVersionAsync();
await manager.InstallOrRepairAsync("1.2.4");
Check(manager.Selected is { Compatible: true, Version: "1.2.4" }, "Postinstall verification");
var relaunched = new CLIInstallationManager(Path.Combine(root, "state"), first + Path.PathSeparator + second, Load, () => now);
Check(relaunched.RestoreLastDetection() && relaunched.Selected is { Compatible: true, Version: "1.2.4" } && relaunched.Npm?.Prefix == second && !relaunched.Busy,
    "A launch restores the last detection without detecting again");
Check(await relaunched.RedetectAsync(quietly: true) == CLIInstallationManager.Redetection.Unchanged && relaunched.Selected?.Version == "1.2.4",
    "Detecting again in the background finds the same CLI");
var secondManifest = Path.Combine(second, "node_modules", "@konbakuyomu", "smart-search", "package.json");
File.WriteAllText(secondManifest, File.ReadAllText(secondManifest).Replace("1.2.4", "1.2.5"));
Check(await relaunched.RedetectAsync(quietly: true) == CLIInstallationManager.Redetection.Changed && relaunched.Selected?.Version == "1.2.4",
    "A CLI changed outside the App is held back while the old one still runs");
relaunched.ShowRedetection();
Check(relaunched.Selected?.Version == "1.2.5", "Switching shows the changed CLI");
var secondPackage = Path.GetDirectoryName(secondManifest)!;
Directory.Move(secondPackage, secondPackage + ".moved");
Check(await relaunched.RedetectAsync(quietly: true) == CLIInstallationManager.Redetection.Missing && relaunched.Selected?.Version == "1.2.5",
    "A CLI that is no longer found never replaces the running one");
Directory.Move(secondPackage + ".moved", secondPackage);
File.WriteAllText(secondManifest, File.ReadAllText(secondManifest).Replace("1.2.5", "1.2.4"));
var restored = new CLIInstallationManager(Path.Combine(root, "state"), first + Path.PathSeparator + second, Load, () => now);
await restored.DiscoverAsync();
Check(restored.ManualNpmPath == manager.ManualNpmPath && !restored.AutomaticallyChecks && restored.CheckedAt == manager.CheckedAt, "Persisted preferences");
await manager.UninstallAsync();
Check(!new CLIInstallationManager(Path.Combine(root, "state"), first + Path.PathSeparator + second, Load, () => now).RestoreLastDetection(),
    "A launch does not restore a detection whose CLI is gone");
var arguments = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(second, "operations.json")))!;
Check(arguments.SequenceEqual(["uninstall", "--global", "--prefix", second, "@konbakuyomu/smart-search"]), "Scoped uninstall arguments");
Check(File.Exists(Path.Combine(first, "node_modules", "@konbakuyomu", "smart-search", "package.json")), "Other npm installation changed");

// Run the real manager against a native fake mise process, without touching global tools.
var fakeBin = Path.Combine(root, "mise bin");
Directory.CreateDirectory(fakeBin);
foreach (var file in Directory.GetFiles(AppContext.BaseDirectory, "CLIManagementCheck.*"))
    File.Copy(file, Path.Combine(fakeBin, Path.GetFileName(file)), overwrite: true);
File.Copy(Path.Combine(AppContext.BaseDirectory, "CLIManagementCheck.exe"), Path.Combine(fakeBin, "mise.exe"), overwrite: true);
var misePackage = Path.Combine(root, miseInstall, "node_modules", "@konbakuyomu", "smart-search");
var savedPackage = Path.Combine(second, "node_modules", "@konbakuyomu", "smart-search.uninstalled");
foreach (var file in Directory.GetFiles(savedPackage, "*", SearchOption.AllDirectories))
{
    var destination = Path.Combine(misePackage, Path.GetRelativePath(savedPackage, file));
    Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
    File.Copy(file, destination);
}
var manifestPath = Path.Combine(misePackage, "package.json");
File.WriteAllText(manifestPath, File.ReadAllText(manifestPath).Replace("1.2.4", "1.2.3"));
var oldGlobal = Environment.GetEnvironmentVariable("MISE_GLOBAL_CONFIG_FILE");
try
{
    Environment.SetEnvironmentVariable("SMART_SEARCH_MISE_FIXTURE", root);
    Environment.SetEnvironmentVariable("MISE_GLOBAL_CONFIG_FILE", Path.Combine(root, "global.toml"));
    var upgradedState = Path.Combine(root, "mise upgraded state");
    Directory.CreateDirectory(upgradedState);
    File.WriteAllText(Path.Combine(upgradedState, "cli-npm-state.json"), JsonSerializer.Serialize(new
    {
        selectedId = Path.Combine(root, "mise", "installs", "npm-konbakuyomu-smart-search", "1.2.2", "node_modules", "@konbakuyomu", "smart-search")
    }));
    var upgraded = new CLIInstallationManager(upgradedState, fakeBin + Path.PathSeparator + second, Load);
    await upgraded.DiscoverAsync();
    using var upgradedRecord = JsonDocument.Parse(File.ReadAllText(Path.Combine(upgradedState, "cli-npm-state.json")));
    Check(upgraded.Selected is { Source: "mise", Version: "1.2.3", Compatible: true } && upgraded.Message.Length == 0 &&
        upgradedRecord.RootElement.GetProperty("selectedId").GetString() == misePackage,
        "Follow the active mise version after an upgrade outside the App");
    var unrelatedState = Path.Combine(root, "unrelated stale state");
    Directory.CreateDirectory(unrelatedState);
    File.WriteAllText(Path.Combine(unrelatedState, "cli-npm-state.json"), JsonSerializer.Serialize(new
    {
        selectedId = Path.Combine(root, "elsewhere", "node_modules", "@konbakuyomu", "smart-search")
    }));
    var unrelated = new CLIInstallationManager(unrelatedState, fakeBin + Path.PathSeparator + second, Load);
    await unrelated.DiscoverAsync();
    Check(unrelated.Selected is null && unrelated.Message.Length > 0, "An unrelated stale selection must not silently switch to mise");
    var mise = new CLIInstallationManager(Path.Combine(root, "mise state"), fakeBin + Path.PathSeparator + second, Load);
    await mise.DiscoverAsync();
    Check(mise.Selected is { Source: "mise", Compatible: true, CanManage: true }, "Resolve active mise tool outside npm prefix: " + mise.Message + " " + JsonSerializer.Serialize(mise.Installations));
    Check(mise.Selected!.ManagerOptions!.SequenceEqual(["--tool-option", "allow_low_downloads=\"true\""]), "Preserve mise tool options");
    await mise.CheckVersionAsync();
    await mise.InstallOrRepairAsync("1.2.4");
    Check(mise.Selected is { Source: "mise", Version: "1.2.4", Compatible: true }, "Mise update and reconnect");
    var use = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(root, "mise-operations.json")))!;
    Check(use.SequenceEqual(["use", "--global", "--pin", "--tool-option", "allow_low_downloads=\"true\"", "npm:@konbakuyomu/smart-search@1.2.4"]), "Mise owns updates");
    mise.SetCliPath(Path.Combine(root, "missing", "smart-search.exe"));
    await mise.DiscoverAsync();
    Check(mise.Selected is null && !mise.CanInstall && mise.Message.Length > 0, "Missing explicit CLI must not silently switch to mise/npm");
}
finally
{
    Environment.SetEnvironmentVariable("SMART_SEARCH_MISE_FIXTURE", null);
    Environment.SetEnvironmentVariable("MISE_GLOBAL_CONFIG_FILE", oldGlobal);
}
var fakeWsl = Path.Combine(fakeBin, "wsl.exe");
File.Copy(Path.Combine(AppContext.BaseDirectory, "CLIManagementCheck.exe"), fakeWsl, overwrite: true);
var probes = Path.Combine(root, "wsl-probes.txt");
try
{
    Environment.SetEnvironmentVariable("SMART_SEARCH_WSL_FIXTURE", root);
    var wslOnly = new CLIInstallationManager(Path.Combine(root, "wsl state"), "", Load, wslPath: fakeWsl);
    await wslOnly.DiscoverAsync();
    Check(wslOnly.Installations.Select(item => item.Id).SequenceEqual(["wsl://Debian", "wsl://Old", "wsl://Wrapped"]), "Probe only running distributions: " + JsonSerializer.Serialize(wslOnly.Installations.Select(item => item.Id)));
    Check(!File.ReadAllText(probes).Contains("Ubuntu") && !File.ReadAllText(probes).Contains("docker"), "Never start a stopped or Docker distribution on ordinary discovery");
    Check(wslOnly.StoppedWslDistributions.SequenceEqual(["Ubuntu-24.04"]) && wslOnly.WslDistributions.Count == 6, "Report stopped distributions without probing them");
    Check(wslOnly.Selected is { Id: "wsl://Debian", Compatible: true, CanManage: false, InWsl: true } debian &&
        debian.Executable == fakeWsl && debian.Arguments.SequenceEqual(["-d", "Debian", "--cd", "~", "--exec", "/usr/bin/node", "/usr/lib/node_modules/@konbakuyomu/smart-search/npm/bin/smart-search.js"]) &&
        debian.Environment["WSL_UTF8"] == "1" && debian.Title == "WSL Debian · 1.2.3" && debian.Note.Contains("sudo"), "Use the only CLI found, in WSL, launched without a shell; a root-owned npm prefix is left to the terminal");
    Check(wslOnly.Installations.Single(item => item.Id == "wsl://Old") is { Compatible: false, CanManage: true, Version: "1.2.2", Prefix: "/home/o/node", Note.Length: > 0 },
        "An old npm CLI in WSL is shown as needing an update, and the App can update it");
    Check(wslOnly.Installations.Single(item => item.Id == "wsl://Wrapped") is { Compatible: false, CanManage: true, Version: "1.2.3", Prefix: "/home/w/node" },
        "A CLI from before launch_command behind a wrapper is found in its npm's global directory");
    Check(wslOnly.InstallTargets is [{ Id: "wsl://Arch", Npm: { Prefix: "/home/a/.npm-global", Distribution: "Arch" } arch }, { Id: "wsl://Fedora", Npm: null, Note.Length: > 0 }] &&
        arch.Command[7] == "-ic" && arch.Command[10..].SequenceEqual(["/home/a/node/bin/node", "/home/a/node/lib/node_modules/npm/bin/npm-cli.js"]),
        "Distributions without a CLI become install targets, using the shell that has Node.js; without Node.js they explain why: " + JsonSerializer.Serialize(wslOnly.InstallTargets.Select(item => new { item.Id, item.Note })));
    File.Delete(probes);
    var relaunchedWsl = new CLIInstallationManager(Path.Combine(root, "wsl state"), "", Load, wslPath: fakeWsl);
    Check(relaunchedWsl.RestoreLastDetection() && relaunchedWsl.Selected?.Id == "wsl://Debian" && relaunchedWsl.InstallTargets.Count == 2 && !File.Exists(probes),
        "A launch restores a CLI in WSL without probing any distribution");
    await wslOnly.DiscoverAsync(includeStoppedWsl: true);
    Check(wslOnly.Installations.Single(item => item.Id == "wsl://Ubuntu-24.04") is { Version: "1.2.4", Compatible: true, CanManage: true } ubuntu && ubuntu.Manager[7] == "-ic" &&
        File.ReadAllText(probes).Contains("Ubuntu-24.04 -lc") && File.ReadAllText(probes).Contains("Ubuntu-24.04 -ic"), "Explicit detection starts stopped distributions and falls back to an interactive shell for nvm");
    wslOnly.SelectInstallation("wsl://Ubuntu-24.04");
    File.Delete(probes);
    var restoredWsl = new CLIInstallationManager(Path.Combine(root, "wsl state"), "", Load, wslPath: fakeWsl);
    await restoredWsl.DiscoverAsync();
    Check(restoredWsl.Selected is { Id: "wsl://Ubuntu-24.04", Compatible: true } && File.ReadAllText(probes).Contains("Ubuntu-24.04"), "A chosen stopped distribution is reconnected");
    var both = new CLIInstallationManager(Path.Combine(root, "both state"), first, Load, wslPath: fakeWsl);
    await both.DiscoverAsync();
    Check(both.Selected is { InWsl: false } && both.Installations.Any(item => item.InWsl), "A first run with both keeps the Windows CLI and lists WSL");
    File.Delete(probes);
    both.SetNpmPath(Path.Combine(first, "npm.cmd"));
    await both.DiscoverAsync();
    Check(!File.Exists(probes) && both.Installations.All(item => !item.InWsl), "A manual npm path does not reach into WSL");
    var noWsl = new CLIInstallationManager(Path.Combine(root, "no wsl state"), "", Load, wslPath: Path.Combine(root, "missing", "wsl.exe"));
    await noWsl.DiscoverAsync(includeStoppedWsl: true);
    Check(!noWsl.WslAvailable && noWsl.Installations.Count == 0, "No wsl.exe means no WSL entries");

    // Updates and installs in WSL go through that distribution's own Node.js and npm.
    var wslManaged = new CLIInstallationManager(Path.Combine(root, "wsl managed state"), "", wslPath: fakeWsl);
    await wslManaged.DiscoverAsync();
    wslManaged.SelectInstallation("wsl://Old");
    await wslManaged.DiscoverAsync();
    await wslManaged.CheckVersionAsync();
    Check(wslManaged.Npm is { Distribution: "Old" } && wslManaged.LatestVersion == "1.2.4" && wslManaged.UpdateAvailable && wslManaged.CanInstall,
        "The selected WSL CLI is checked with its own npm, past profile output: " + wslManaged.CheckError);
    await wslManaged.InstallOrRepairAsync("1.2.4");
    var wslInstall = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(root, "wsl-operations.json")))!;
    Check(wslManaged.Selected is { Id: "wsl://Old", Version: "1.2.4", Compatible: true } &&
        wslInstall[..7].SequenceEqual(["-d", "Old", "--cd", "~", "--exec", "bash", "-lc"]) && wslInstall[8..].SequenceEqual(["smart-search", "/home/o/node/bin/node",
            "/home/o/node/lib/node_modules/npm/bin/npm-cli.js", "install", "--global", "--prefix", "/home/o/node", "--include=optional", "@konbakuyomu/smart-search@1.2.4"]),
        "Update an old WSL CLI in its own prefix, without a shell parsing the arguments: " + JsonSerializer.Serialize(wslInstall));
    await wslManaged.InstallOrRepairAsync("1.2.4", "wsl://Arch");
    wslInstall = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(root, "wsl-operations.json")))!;
    Check(wslManaged.Selected?.Id == "wsl://Old" && wslManaged.Installations.Single(item => item.Id == "wsl://Arch") is { Version: "1.2.4", Compatible: true } &&
        wslManaged.InstallTargets.All(item => item.Id != "wsl://Arch") && wslInstall[6] == "-ic" && wslInstall[^4..].SequenceEqual(["--prefix", "/home/a/.npm-global", "--include=optional", "@konbakuyomu/smart-search@1.2.4"]),
        "Install into another distribution with npm's own global prefix and keep the current choice");
    await wslManaged.InstallOrRepairAsync("1.2.4", "wsl://Wrapped");
    wslInstall = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(root, "wsl-operations.json")))!;
    Check(wslManaged.Installations.Single(item => item.Id == "wsl://Wrapped") is { Version: "1.2.4", Compatible: true } &&
        wslInstall[^4..].SequenceEqual(["--prefix", "/home/w/node", "--include=optional", "@konbakuyomu/smart-search@1.2.4"]), "Update a wrapped older CLI in place");

    // Windows without a CLI is a target too, while a CLI in WSL stays selected.
    var windowsTarget = new CLIInstallationManager(Path.Combine(root, "windows target state"), second, Load, wslPath: fakeWsl);
    await windowsTarget.DiscoverAsync();
    var windowsRoot = Path.Combine(second, "node_modules", "@konbakuyomu", "smart-search");
    Check(windowsTarget.Selected is { InWsl: true } && windowsTarget.InstallTargets.FirstOrDefault() is { Place: "Windows", Npm.Prefix: var windowsPrefix } windowsInstall &&
        windowsInstall.Id == windowsRoot && windowsPrefix == second, "Offer Windows when only WSL has a CLI");
    await windowsTarget.CheckVersionAsync();
    await windowsTarget.InstallOrRepairAsync("1.2.4", windowsRoot);
    Check(windowsTarget.Selected is { InWsl: true } && windowsTarget.Installations.Any(item => item.Id == windowsRoot && item is { Version: "1.2.4", Compatible: true, InWsl: false }) &&
        windowsTarget.Message.Contains("Windows"), "Install on Windows without switching away from WSL");
}
finally { Environment.SetEnvironmentVariable("SMART_SEARCH_WSL_FIXTURE", null); }
Check(CLIInstallationManager.MiseOptions("version = \"1.2.3\"\npostinstall = \"custom\"", "1.2.3") is null, "Complex mise options are read-only");
Check(CLIInstallationManager.MiseOptions("version = \"^1\"", "^1") is null, "Do not broaden mise constraints");
Check(CLIInstallationManager.MiseToolDirectory(misePackage) == Path.Combine(root, "mise", "installs", "npm-konbakuyomu-smart-search"), "Recognize versioned mise tool directories");
Check(CLIInstallationManager.MiseToolDirectory(@"C:\x\node_modules\@konbakuyomu\smart-search") is null, "Global npm prefixes are not mise tools");
Check(CLIInstallationManager.MiseToolDirectory(@"C:\x\smart-search.exe") is null, "Manual CLI paths are not mise tools");
Console.WriteLine("PASS: npm/mise/WSL discovery and ownership, multiple installations, legacy isolation, explicit selection, startup/24h checks, failure backoff and persistence, launch from the last detection and background re-detection");
static void Check(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }
