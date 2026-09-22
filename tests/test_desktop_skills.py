"""Official source, explicit Agent writes and invocation consistency in isolated homes."""
import asyncio
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import httpx
import pytest

from smart_search import desktop_skills as update, skill_installer as skills
from smart_search.desktop_backend import Backend
from smart_search.desktop_environment import Environment


def bundle(*, extra=(), version="0.1.22"):
    contents = [("package/package.json", json.dumps({"name": update.PACKAGE, "version": version}).encode()),
                ("package/skills/smart-search-cli/SKILL.md", b"---\nname: smart-search-cli\ndescription: Search\n---\nCurrent skill\n"),
                ("package/skills/smart-search-cli/references/setup.md", b"Setup instructions"), *extra]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name, content in contents:
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    data = stream.getvalue()
    release = {"version": version, "integrity": "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode(), "checked_at": 1}
    return data, release


def isolated(tmp_path, monkeypatch):
    environment = Environment(lambda *_: None, directory=tmp_path / "tools", home=tmp_path / "home")
    monkeypatch.setattr(environment, "probe_node", lambda _: {"ready": True, "path": str(tmp_path / "node")})
    manager = update.Skills(lambda *_: None, environment, directory=tmp_path / "cache")
    data, source = bundle()
    manager.files = update.unpack_skills(data, source)
    manager.state.update(source=source, cached=False)
    info = {"external_runtime_verified": True, "manager": "npm", "package_root": str(tmp_path / "npm-0.1.22"), "external_version": "0.1.22"}
    manager.snapshot({}, info, str(tmp_path / "config"))
    return manager, info


def test_snapshot_all_agents_is_readonly_and_uses_custom_claude_root(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    state = manager.snapshot({"CLAUDE_CONFIG_DIR": str(tmp_path / "custom")}, info, str(tmp_path / "config"))
    rows = {row["target"]: row for row in state["targets"]}
    assert set(rows) == set(skills.SKILL_TARGET_BY_ID)
    assert {"cline", "roo", "codex", "claude", "gemini", "copilot", "cursor", "opencode"} <= rows.keys()
    assert rows["claude"]["path"] == str(tmp_path / "custom/skills/smart-search-cli")
    assert rows["cline"]["path"].endswith(str(Path(".cline/skills/smart-search-cli")))
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_explicit_sync_updates_old_invocation_and_preserves_unselected_extras_and_backup(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    target = skills.target_path("codex", manager.environment.home, {})
    target.mkdir(parents=True)
    original = b"My instructions\n\n## Independent CLI on this computer\nold-0.1.20\n"
    (target / "SKILL.md").write_bytes(original)
    (target / "personal.txt").write_text("keep")
    legacy = manager.environment.home / ".codex/skills/smart-search-cli"
    legacy.mkdir(parents=True)
    (legacy / "SKILL.md").write_text("historical")
    manager.refresh()
    with pytest.raises(ValueError):
        manager.sync({"targets": ["codex"], "plan_id": manager.state["plan_id"]})
    manager.sync({"targets": ["codex"], "confirm": True, "plan_id": manager.state["plan_id"]})
    assert manager.state["busy"]
    with pytest.raises(ValueError):
        manager.sync({})
    await manager.task
    result = manager.state["result"]
    assert result["ok"] and len(result["installed"]) == 1
    assert (Path(result["installed"][0]["backup"]) / "SKILL.md").read_bytes() == original
    assert "npm-0.1.22" in (target / "SKILL.md").read_text() and "old-0.1.20" not in (target / "SKILL.md").read_text()
    assert (target / "personal.txt").read_text() == "keep"
    assert (legacy / "SKILL.md").read_text() == "historical"
    assert not skills.target_path("claude", manager.environment.home, {}).exists()
    assert next(r for r in manager.state["targets"] if r["target"] == "codex")["status"] == "extra_files"
    before = (target / "SKILL.md").stat().st_mtime_ns
    manager.sync({"targets": ["codex"], "confirm": True, "plan_id": manager.state["plan_id"]})
    await manager.task
    assert manager.state["result"]["installed"][0]["backup"] == ""
    assert (target / "SKILL.md").stat().st_mtime_ns == before
    canonical = skills.status_skill_targets(["codex"], project_root=manager.environment.home, files=manager.files)
    assert canonical["targets"][0]["status"] == "extra_files", "Generic status must recognize the local invocation note"
    assert not canonical["targets"][0]["managed_hash_match"], "Content equivalence must not claim equal byte hashes"


@pytest.mark.parametrize("name", ["../escape", "package/skills/smart-search-cli/../../escape", "C:/escape", "package/skills/smart-search-cli/CON", "package/skills/smart-search-cli/a/../x", "package/skills/smart-search-cli/SKILL.md", "package/skills/smart-search-cli/skill.md", "package/skills/smart-search-cli/./SKILL.md"])
def test_archive_rejects_unsafe_and_duplicate_paths(name):
    data, release = bundle(extra=[(name, b"bad")])
    with pytest.raises(ValueError):
        update.unpack_skills(data, release)


def test_archive_integrity_and_manifest_must_match():
    data, release = bundle()
    with pytest.raises(ValueError):
        update.unpack_skills(data + b"tamper", release)
    with pytest.raises(ValueError):
        update.unpack_skills(data, {**release, "version": "0.1.23"})


@pytest.mark.asyncio
async def test_official_fetch_never_follows_tarball_redirects_or_executes_package(tmp_path):
    data, release = bundle()
    url = f"https://registry.npmjs.org/{update.PACKAGE}/-/smart-search-{release['version']}.tgz"
    calls = []
    def response(request):
        calls.append(str(request.url))
        if str(request.url) == update.NPM_URL:
            return httpx.Response(200, json={"name": update.PACKAGE, "version": release["version"], "dist": {"integrity": release["integrity"], "tarball": url}})
        return httpx.Response(302, headers={"Location": "http://localhost/unsafe"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response), follow_redirects=False) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await update.fetch_skills(client)
    assert calls == [update.NPM_URL, url]
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_auto_check_downloads_only_and_failed_check_blocks_sync(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    data, source = bundle()
    calls = []
    async def fetch(_):
        calls.append(1)
        return source, data, update.unpack_skills(data, source)
    monkeypatch.setattr(update, "fetch_skills", fetch)
    manager.auto_check({}, info, str(tmp_path / "config"))
    task = manager.task
    manager.auto_check({}, info, str(tmp_path / "config"))
    assert manager.task is task
    await task
    assert calls == [1] and not manager.environment.home.exists() and manager.state["can_sync"]
    assert (manager.directory / "0.1.22.tgz").exists()
    reloaded = update.Skills(lambda *_: None, manager.environment, directory=manager.directory)
    assert reloaded.state["cached"] and reloaded.files == manager.files
    async def fail(_):
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(update, "fetch_skills", fail)
    manager.check()
    await manager.task
    assert manager.state["error"] and manager.state["cached"] and not manager.state["can_sync"]
    assert not manager.environment.home.exists()
    manager.state.update(auto_check=False, last_attempt=0)
    manager.auto_check({}, info, str(tmp_path / "config"))
    assert manager.task.done()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "offline", "target-changed"])
async def test_single_update_checks_cold_cache_then_updates_only_selection(tmp_path, monkeypatch, failure):
    manager, _ = isolated(tmp_path, monkeypatch)
    manager.state.update(cached=True, can_sync=False)
    destination = skills.target_path("opencode", manager.environment.home, {})
    data, source = bundle()
    calls = []

    async def fetch(_):
        calls.append(1)
        if failure == "offline":
            raise httpx.ConnectError("offline")
        if failure == "target-changed":
            destination.mkdir(parents=True)
            (destination / "SKILL.md").write_bytes(b"edited while checking")
        return source, data, update.unpack_skills(data, source)

    monkeypatch.setattr(update, "fetch_skills", fetch)
    manager.update({"confirm": True, "targets": ["opencode"]})
    assert manager.state["busy"] and manager.state["checking"]
    with pytest.raises(ValueError):
        manager.update({"confirm": True, "targets": ["claude"]})
    await manager.task
    assert calls == [1] and not manager.state["busy"] and not manager.state["checking"]
    assert not skills.target_path("claude", manager.environment.home, {}).exists()
    if failure:
        assert manager.state["error"]
        if failure == "offline":
            assert not destination.exists()
        else:
            assert (destination / "SKILL.md").read_bytes() == b"edited while checking"
        async def retry_fetch(_):
            return source, data, update.unpack_skills(data, source)
        monkeypatch.setattr(update, "fetch_skills", retry_fetch)
        manager.update({"confirm": True, "targets": ["opencode"]})
        await manager.task
        assert manager.state["result"]["ok"] and not manager.state["error"]
        if failure == "target-changed":
            backup = Path(manager.state["result"]["installed"][0]["backup"])
            assert (backup / "SKILL.md").read_bytes() == b"edited while checking"
    else:
        assert manager.state["result"]["ok"]
        original_time = (destination / "SKILL.md").stat().st_mtime_ns
        manager.update({"confirm": True, "targets": ["opencode"]})
        await manager.task
        assert manager.state["result"]["installed"][0]["changed_files"] == 0
        assert (destination / "SKILL.md").stat().st_mtime_ns == original_time


def test_changed_files_invalidate_confirmation_but_cli_version_does_not(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    plan = manager.state["plan_id"]
    target = skills.target_path("codex", manager.environment.home, {})
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("changed after preview")
    with pytest.raises(ValueError):
        manager.sync({"targets": ["codex"], "confirm": True, "plan_id": plan})
    manager.snapshot({}, {**info, "external_version": "0.1.20"}, str(tmp_path))
    assert manager.state["can_sync"] and not manager.state["compatibility"]
    manager.snapshot({}, {**info, "external_runtime_verified": False}, str(tmp_path))
    assert manager.state["can_sync"] and not manager.state["cli_ready"] and manager.state["compatibility"]


@pytest.mark.asyncio
async def test_patch_release_with_identical_skills_has_no_content_or_write_changes(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    manager.sync({"targets": ["codex"], "confirm": True, "plan_id": manager.state["plan_id"]})
    await manager.task
    target = skills.target_path("codex", manager.environment.home, {}) / "SKILL.md"
    original = target.read_bytes().replace(b"\n", b"\r\n") + b"\r\n"
    target.write_bytes(original)
    before = target.stat().st_mtime_ns
    manager.state["source"]["version"] = "0.1.23"
    manager.snapshot({}, info, str(tmp_path / "config"))  # Installed CLI is still 0.1.22.
    row = next(row for row in manager.state["targets"] if row["target"] == "codex")
    assert manager.state["can_sync"] and row["status"] == "up_to_date" and not row["needs_update"]
    assert not row["content_stale_files"] and not row["invocation_changed"]
    monkeypatch.setattr(skills, "write_skill_files", lambda *a, **k: pytest.fail("An identical target must not be written or locked"))
    manager.sync({"targets": ["codex"], "confirm": True, "plan_id": manager.state["plan_id"]})
    await manager.task
    assert manager.state["result"]["installed"][0]["changed_files"] == 0
    assert target.read_bytes() == original and target.stat().st_mtime_ns == before


@pytest.mark.asyncio
async def test_unverified_cli_can_sync_body_preserving_each_targets_local_note(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    notes = {}
    for name in ("codex", "claude"):
        target = skills.target_path(name, manager.environment.home, {})
        target.mkdir(parents=True)
        notes[name] = f"\n## Independent CLI on this computer\n{name}-existing-command\n".encode()
        (target / "SKILL.md").write_bytes(b"Old skill\n" + notes[name])
    manager.state["source"]["version"] = "0.1.23"
    manager.snapshot({}, {**info, "external_runtime_verified": False}, str(tmp_path / "config"))
    assert manager.state["can_sync"] and not manager.state["cli_ready"]
    manager.sync({"targets": ["codex", "claude", "roo"], "confirm": True, "plan_id": manager.state["plan_id"]})
    await manager.task
    assert manager.state["result"]["ok"]
    for name, note in notes.items():
        actual = (skills.target_path(name, manager.environment.home, {}) / "SKILL.md").read_bytes()
        assert actual == manager.files["SKILL.md"].rstrip() + b"\n" + note
        row = next(row for row in manager.state["targets"] if row["target"] == name)
        assert row["status"] == "up_to_date" and not row["needs_update"]
    assert (skills.target_path("roo", manager.environment.home, {}) / "SKILL.md").read_bytes() == manager.files["SKILL.md"]


@pytest.mark.asyncio
async def test_invocation_only_change_is_distinct_from_upstream_skill_content(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    manager.sync({"targets": ["codex"], "confirm": True, "plan_id": manager.state["plan_id"]})
    await manager.task
    manager.snapshot({}, {**info, "package_root": str(tmp_path / "npm-0.1.23")}, str(tmp_path / "config"))
    row = next(row for row in manager.state["targets"] if row["target"] == "codex")
    assert row["needs_update"] and row["invocation_changed"] and row["stale_files"] == ["SKILL.md"]
    assert not row["content_stale_files"] and not row["missing_files"]


def test_write_failure_restores_old_files_and_keeps_backup(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    (target / "SKILL.md").write_bytes(b"original")
    (target / "b.md").write_bytes(b"original-b")
    replace = Path.replace
    def failing_replace(path, destination):
        if Path(destination).name == "b.md":
            raise PermissionError("fixture denial")
        return replace(path, destination)
    monkeypatch.setattr(Path, "replace", failing_replace)
    with pytest.raises(ValueError):
        skills.write_skill_files(target, {"SKILL.md": b"new", "b.md": b"new-b"}, tmp_path / "backups")
    assert (target / "SKILL.md").read_bytes() == b"original"
    assert (target / "b.md").read_bytes() == b"original-b"
    assert next((tmp_path / "backups").glob("*/SKILL.md")).read_bytes() == b"original"


def test_symlink_target_is_refused_before_writes(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS did not permit a test symlink")
    with pytest.raises(ValueError):
        skills.write_skill_files(link / "skill", {"SKILL.md": b"bad"}, tmp_path / "backups")
    assert not list(outside.iterdir())


def test_link_guard_without_os_symlink_privileges(tmp_path, monkeypatch):
    parent = tmp_path / "redirected-parent"
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == parent)
    with pytest.raises(ValueError):
        skills.write_skill_files(parent / "skill", {"SKILL.md": b"bad"}, tmp_path / "backups")
    assert not list(tmp_path.iterdir())


@pytest.mark.skipif(os.name != "nt", reason="Windows reparse point contract")
def test_real_junction_is_rejected_without_python312_pathlib(tmp_path, monkeypatch):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    assert shell, "Windows junction test requires the system PowerShell"
    outside, junction = tmp_path / "outside", tmp_path / "junction"
    outside.mkdir()
    result = subprocess.run([shell, "-NoProfile", "-Command",
        "New-Item -ItemType Junction -Path $env:SMART_SEARCH_TEST_JUNCTION -Target $env:SMART_SEARCH_TEST_OUTSIDE | Out-Null"],
        env=dict(os.environ, SMART_SEARCH_TEST_JUNCTION=str(junction), SMART_SEARCH_TEST_OUTSIDE=str(outside)),
        capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr
    monkeypatch.delattr(Path, "is_junction", raising=False)
    with pytest.raises(ValueError):
        skills.write_skill_files(junction / "skill", {"SKILL.md": b"must not escape"}, tmp_path / "backups")
    assert not list(outside.iterdir())


def test_invalid_claude_root_is_one_target_error_not_a_broken_catalog(tmp_path, monkeypatch):
    manager, info = isolated(tmp_path, monkeypatch)
    state = manager.snapshot({"CLAUDE_CONFIG_DIR": "relative"}, info, str(tmp_path))
    rows = {row["target"]: row for row in state["targets"]}
    assert rows["claude"]["status"] == "error" and rows["codex"]["status"] == "missing"


@pytest.mark.asyncio
async def test_cache_write_failure_leaves_controls_retryable(tmp_path, monkeypatch):
    manager, _ = isolated(tmp_path, monkeypatch)
    def denied():
        raise PermissionError("fixture")
    monkeypatch.setattr(manager, "save", denied)
    manager.check()
    assert not manager.state["checking"] and not manager.state["can_sync"] and manager.state["error"]


@pytest.mark.asyncio
async def test_backend_serializes_skill_and_runtime_mutations(tmp_path, monkeypatch):
    backend = Backend(lambda *_: None)
    backend.directory, backend.initialized = str(tmp_path), True
    backend.skills.state["busy"] = True
    for method in ("profile.select", "cli.update", "environment.prepare", "environment.install", "skills.install", "app.update-prepare", "shutdown", "language.set"):
        with pytest.raises(ValueError):
            await backend.handle(method, {"lang": "en"})
    backend.skills.state["busy"] = False
    backend.environment.state["busy"] = True
    with pytest.raises(ValueError):
        await backend.handle("skills.sync", {})


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["skills.sync", "skills.update"])
async def test_native_protocol_catalog_and_sync_share_latest_bytes(tmp_path, monkeypatch, method):
    manager, info = isolated(tmp_path, monkeypatch)
    events = []
    backend = Backend(events.append)
    backend.directory, backend.initialized = str(tmp_path / "config"), True
    backend.skills, backend.environment = manager, manager.environment
    manager.emit = backend.event
    monkeypatch.setattr(backend, "cli_status", lambda: info)
    catalog = await backend.handle("skills.catalog", {})
    assert catalog["source"]["version"] == "0.1.22" and len(catalog["targets"]) == len(skills.SKILL_TARGETS)
    async def fetch(_):
        data, source = bundle()
        return source, data, update.unpack_skills(data, source)
    monkeypatch.setattr(update, "fetch_skills", fetch)
    if method == "skills.update":
        manager.state.update(cached=True, can_sync=False)
    await backend.handle(method, {"targets": ["roo"], "confirm": True, "plan_id": catalog["plan_id"]})
    await manager.task
    assert events[-1]["event"] == "skills" and events[-1]["data"]["result"]["ok"]
    refreshed = await backend.handle("skills.catalog", {})
    assert next(row for row in refreshed["targets"] if row["target"] == "roo")["status"] == "up_to_date"
