using SmartSearch.Desktop;

Localization.Preference = "zh";
var selectedTargets = new HashSet<string>();
if (SkillsSelectionPolicy.CanUpdate(true, selectedTargets.Count, false))
    throw new Exception("An empty selection must not submit an update.");
selectedTargets.Add("opencode");
if (!SkillsSelectionPolicy.CanUpdate(true, selectedTargets.Count, false))
    throw new Exception("Selecting OpenCode must enable the action before a source check.");
if (SkillsSelectionPolicy.CanUpdate(true, selectedTargets.Count, true) || SkillsSelectionPolicy.CanUpdate(false, selectedTargets.Count, false))
    throw new Exception("A busy or disconnected app must not submit an update.");
selectedTargets.Clear();
if (SkillsSelectionPolicy.CanUpdate(true, selectedTargets.Count, false))
    throw new Exception("Clearing the last selection must disable submission.");
var operations = new OperationState();
operations.TrackRun("test:exa", "exa-run");
operations.TrackRun("test:context7", "docs-run");
if (!operations.RunsFor("test:exa").SequenceEqual(["exa-run"]))
    throw new Exception("Inline cancellation must target only the selected provider's own run.");
operations.EndRun("exa-run");
if (operations.RunsFor("test:exa").Length != 0 || operations.RunsFor("test:context7").Length != 1)
    throw new Exception("A completed test must not cancel another provider's task.");

// The same real client must reconnect after stopping for a failed installer
// launch. No UI, installer, package manager, or provider is invoked here.
if (args.Length != 2) throw new ArgumentException("Pass Python executable and an isolated config directory.");
await using var client = new BackendClient(args[0], ["-m", "smart_search.desktop_entry"]);
for (var attempt = 0; attempt < 2; attempt++)
{
    var state = await client.StartAsync(args[1], CancellationToken.None);
    if (state.GetProperty("protocol_version").GetInt32() != 1) throw new Exception("Handshake failed.");
    var pong = await client.CallAsync("ping", new { }, CancellationToken.None);
    if (pong.GetProperty("protocol_version").GetInt32() != 1) throw new Exception("Reconnect failed.");
    await client.StopAsync();
    if (client.IsConnected) throw new Exception("Stopped backend is still connected.");
}
Console.WriteLine("PASS: stop and reconnect preserve the private RPC client.");
