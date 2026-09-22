"""Environment transitions and trust boundaries; never touch real installations."""
import asyncio
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import zipfile
from types import SimpleNamespace

import httpx
import pytest

from smart_search.i18n import use_language


@pytest.fixture(autouse=True)
def chinese_presentation():
    with use_language("zh"):
        yield

from smart_search import desktop_cli, desktop_environment as setup
from smart_search.desktop_backend import Backend


def isolated(tmp_path, monkeypatch):
    environment = setup.Environment(lambda *_: None, directory=tmp_path / "tools", home=tmp_path / "home")
    monkeypatch.setattr(environment, "probe_node", lambda _: {"ready": True, "path": str(tmp_path / "node"), "npm": str(tmp_path / "npm.js"), "version": "v24.0.0"})
    monkeypatch.setattr(environment, "probe_python", lambda _: {"ready": True, "path": str(tmp_path / "python"), "version": "3.13.1"})
    return environment


def test_detection_is_read_only_and_distinguishes_real_ai_from_files(tmp_path, monkeypatch):
    environment = isolated(tmp_path, monkeypatch)
    target = tmp_path / "home/.agents/skills/smart-search-cli"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("my custom instructions")
    legacy = tmp_path / "home/.codex/skills/smart-search-cli"
    legacy.mkdir(parents=True)
    info = {"external_path": "project/smart-search", "manager": "unknown", "can_update": False}
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = environment.inspect({"PATH": ""}, info, str(tmp_path / "config"), False)
    assert result["blocked"] and not result["independent"]
    assert result["targets"][0]["status"] == "stale"
    assert not result["targets"][0]["application_ready"]
    assert result["targets"][0]["legacy_path"] == str(legacy)
    assert "Key" in result["steps"][2]["message"]
    assert result["steps"][3]["status"] == "pending"
    assert not environment.directory.exists()
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.asyncio
async def test_check_coalesces_and_verify_cannot_repair_missing_runtime(tmp_path, monkeypatch):
    environment = isolated(tmp_path, monkeypatch)
    info = {"external_path": "independent", "package_root": str(tmp_path / "npm-package"), "manager": "npm",
            "can_update": True, "external_runtime_verified": True, "external_version": "0.1.20"}
    calls = []
    def read(argv, env):
        calls.append(argv)
        assert "smart-search.js" not in " ".join(argv), "readonly verification invoked repairing wrapper"
        raise FileNotFoundError("runtime removed after discovery")
    monkeypatch.setattr(setup, "read_command", read)
    environment.start_check({"PATH": ""}, info, str(tmp_path / "config"), False, verify=True)
    task = environment.task
    environment.start_check({"PATH": ""}, info, str(tmp_path / "config"), False)
    assert environment.task is task and environment.state["busy"]
    await task
    assert environment.state["status"] == "failed" and not environment.state["busy"]
    assert len(calls) == 1 and not environment.directory.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked", ["", "Unrecognized existing installation"])
async def test_prepare_cli_builds_its_plan_and_never_selects_skills(tmp_path, monkeypatch, blocked):
    environment = isolated(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(environment, "inspect", lambda *args: {"plan_id": "fresh-plan", "blocked": blocked})

    async def install(plan, targets, replace, *args):
        calls.append((plan, targets, replace))
        environment.changed(status="ready", busy=False)

    monkeypatch.setattr(environment, "_install", install)
    with pytest.raises(ValueError):
        environment.prepare({}, {}, {}, str(tmp_path), False, lambda: {})
    environment.prepare({"confirm": True}, {}, {}, str(tmp_path), False, lambda: {})
    task = environment.task
    environment.prepare({"confirm": True}, {}, {}, str(tmp_path), False, lambda: {})
    assert environment.task is task and environment.state["busy"]
    await task
    assert not environment.state["busy"]
    assert calls == ([] if blocked else [("fresh-plan", [], False)])
    assert not environment.directory.exists()
    if blocked:
        assert environment.state["status"] == "failed" and environment.state["error"] == blocked


@pytest.mark.asyncio
async def test_prepare_completion_publishes_refreshed_cli_update_state(tmp_path, monkeypatch):
    events = []
    backend = Backend(events.append)
    backend.directory, backend.initialized = str(tmp_path), True
    info = {"external_version": "0.1.22", "external_runtime_verified": False, "can_update": True,
            "manager": "npm", "manager_command": ["npm"]}
    backend.updates.state["cli"].update(latest_version="0.1.22", checked_at=1, cached=False, error="")

    def current():
        backend.updates.refresh_installed(info)
        return info

    def prepare(params, env, cli_info, config_dir, minimum_ok, refresh_cli):
        assert backend.updates.state["cli"]["available"]  # Same-version runtime repair.
        info["external_runtime_verified"] = True
        refresh_cli()
        return {"status": "ready"}

    monkeypatch.setattr(backend, "cli_status", current)
    monkeypatch.setattr(backend, "activity", lambda: {"runs": []})
    monkeypatch.setattr(backend.environment, "prepare", prepare)
    await backend.handle("environment.prepare", {"confirm": True})
    published = [event["data"] for event in events if event["event"] == "updates"]
    assert published and not published[-1]["cli"]["available"]
    assert published[-1]["installed_cli"]["external_runtime_verified"]


@pytest.mark.asyncio
async def test_skill_conflicts_keep_custom_content_and_back_up_explicit_replace(tmp_path, monkeypatch):
    environment = isolated(tmp_path, monkeypatch)
    node = environment.probe_node({})
    info = {"package_root": str(tmp_path / "independent npm")}
    config_dir = str(tmp_path / "配置")
    target = environment.target_path("codex", {})
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("custom", encoding="utf-8")
    (target / "extra.md").write_text("keep", encoding="utf-8")
    notes = await environment.install_skills(["codex"], False, node, info, {}, config_dir)
    assert notes and (target / "SKILL.md").read_text() == "custom"
    assert not environment.target_path("claude", {}).exists()
    await environment.install_skills(["codex"], True, node, info, {}, config_dir)
    backups = list((environment.directory / "skill-backups").glob("codex-*/SKILL.md"))
    assert len(backups) == 1 and backups[0].read_text() == "custom"
    text = (target / "SKILL.md").read_text(encoding="utf-8")
    assert str(tmp_path / "independent npm") in text and config_dir in text
    assert (target / "extra.md").read_text() == "keep"
    assert environment.target_path("claude", {"CLAUDE_CONFIG_DIR": str(tmp_path / "claude-custom")}) == tmp_path / "claude-custom/skills/smart-search-cli"
    before = (target / "SKILL.md").stat().st_mtime_ns
    await environment.install_skills(["codex"], False, node, info, {}, config_dir)
    assert (target / "SKILL.md").stat().st_mtime_ns == before


@pytest.mark.asyncio
async def test_changed_plan_and_invalid_targets_never_start_installers(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "platform_target", lambda: ("windows", "x64"))
    environment = isolated(tmp_path, monkeypatch)
    env, info = {"PATH": ""}, {"external_path": None}
    environment.state.update(environment.inspect(env, info, str(tmp_path), False))
    with pytest.raises(ValueError):
        environment.install({"confirm": True, "targets": ["untrusted"], "plan_id": environment.state["plan_id"]}, env, info, str(tmp_path), False, lambda: info)
    monkeypatch.setattr(environment, "probe_node", lambda _: {"ready": False})
    environment.install({"confirm": True, "targets": [], "plan_id": environment.state["plan_id"]}, env, info, str(tmp_path), False, lambda: info)
    task = environment.task
    environment.install({}, env, info, str(tmp_path), False, lambda: info)
    assert environment.task is task
    await task
    assert environment.state["status"] == "failed" and "变化" in environment.state["error"]
    assert not environment.directory.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_hash,redirect", [(True, False), (False, True)])
async def test_download_rejects_corruption_and_untrusted_redirects(tmp_path, bad_hash, redirect):
    environment = setup.Environment(lambda *_: None, directory=tmp_path / "tools")
    seen = []
    def handler(request):
        seen.append(str(request.url))
        if redirect:
            return httpx.Response(302, headers={"Location": "http://localhost/execute"})
        return httpx.Response(200, content=b"wrong")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError):
            await environment.download(client, {"name": "fixture.zip", "url": "https://nodejs.org/dist/v24.0.0/fixture.zip", "size": 5,
                                               "sha256": hashlib.sha256(b"right").hexdigest()})
    assert len(seen) == 1
    assert not (environment.directory / "runtimes").exists()
    assert not (environment.directory / "cache/fixture.zip").exists()


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "dir\\..\\escape"])
def test_archive_rejects_unsafe_paths_before_writing(tmp_path, name):
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as package:
        package.writestr("safe.txt", "safe")
        package.writestr(name, "bad")
    dest = tmp_path / "unpack"
    dest.mkdir()
    with pytest.raises(ValueError):
        setup.extract_archive(archive, dest)
    assert not list(dest.iterdir())


def test_tar_rejects_link_escape_but_keeps_npm_relative_links(tmp_path):
    archive = tmp_path / "fixture.tar.gz"
    with tarfile.open(archive, "w:gz") as package:
        item = tarfile.TarInfo("bin/npm")
        item.type, item.linkname = tarfile.SYMTYPE, "../../outside"
        package.addfile(item)
    dest = tmp_path / "unpack"
    dest.mkdir()
    with pytest.raises(ValueError):
        setup.extract_archive(archive, dest)


def test_installer_env_strips_secrets_and_does_not_reuse_npm_config(tmp_path):
    clean = setup.installer_environment({"PATH": "safe", "EXA_API_KEY": "private", "GH_TOKEN": "private", "PYTHONPATH": "wrong",
                                         "UV_PYTHON_INSTALL_MIRROR": "http://untrusted", "npm_config_userconfig": "private-file"}, tmp_path)
    assert not {"EXA_API_KEY", "GH_TOKEN", "PYTHONPATH", "UV_PYTHON_INSTALL_MIRROR"} & clean.keys()
    assert clean["npm_config_userconfig"] != clean["npm_config_globalconfig"]
    assert clean["UV_PYTHON_INSTALL_DIR"] == str(tmp_path / "python")
    assert clean["SMART_SEARCH_ACTIVITY_ENABLED"] == "false"


def test_app_owned_programs_cannot_be_classified_as_independent(tmp_path, monkeypatch):
    environment = isolated(tmp_path, monkeypatch)
    app = tmp_path / "App"
    monkeypatch.setattr(setup.sys, "frozen", True, raising=False)
    monkeypatch.setattr(setup.sys, "executable", str(app / "backend/smart-search.exe"))
    assert setup.depends_on_app(app / "node.exe")
    assert not setup.depends_on_app(tmp_path / "tools/node.exe")
    info = {"external_path": str(app / "cli/smart-search"), "package_root": str(app / "cli/package"),
            "manager": "npm", "can_update": True, "external_runtime_verified": True}
    result = environment.inspect({"PATH": ""}, info, str(tmp_path / "config"), False)
    assert not result["independent"] and result["blocked"]


def test_owned_npm_survives_app_absence_and_updates_its_own_prefix(tmp_path):
    base = tmp_path / "independent tools"
    prefix = base / "cli"
    root = prefix / ("node_modules" if os.name == "nt" else "lib/node_modules") / desktop_cli.PACKAGE
    root.mkdir(parents=True)
    node, npm = base / "node", base / "npm.js"
    node.write_text("node")
    npm.write_text("npm")
    (root / "package.json").write_text(json.dumps({"name": desktop_cli.PACKAGE, "version": "0.1.20"}))
    (base / "environment.json").write_text(json.dumps({"node": str(node), "npm": str(npm), "python": str(base / "python")}))
    info = desktop_cli.managed_cli_info({}, base)
    assert info["can_update"] and info["manager"] == "npm"
    assert desktop_cli.update_command(info, "0.1.21") == [str(node), str(npm), "install", "--global", "--prefix", str(prefix), "@konbakuyomu/smart-search@0.1.21"]


@pytest.mark.asyncio
async def test_backend_blocks_conflicting_mutations_during_setup(tmp_path):
    backend = Backend(lambda *_: None)
    backend.directory, backend.initialized = str(tmp_path), True
    backend.environment.state.update(busy=True, status="installing", can_cancel=False)
    for method, params in [("cli.update", {"confirm": True}), ("skills.update", {"confirm": True, "targets": ["codex"]}), ("app.update-prepare", {}),
                            ("profile.select", {"config_dir": str(tmp_path / "other")}), ("skills.install", {"targets": ["codex"]}), ("shutdown", {})]:
        with pytest.raises(ValueError, match="环境|安装|准备"):
            await backend.handle(method, params)
    backend.environment.state["busy"] = False


@pytest.mark.asyncio
async def test_process_failure_restores_controls_and_bounds_redacted_log(tmp_path):
    environment = setup.Environment(lambda *_: None, directory=tmp_path)
    script = tmp_path / "manager.py"
    script.write_text("import sys;print('api_key=synthetic-private-secret ' * 1000);sys.exit(2)")
    with pytest.raises(ValueError):
        await environment.run([sys.executable, str(script)], setup.installer_environment(os.environ, tmp_path))
    assert "synthetic-private-secret" not in environment.state["log"]
    assert len(environment.state["log"]) <= 12000


@pytest.mark.skipif(os.name != "nt", reason="Windows user PATH and npm shim contract")
def test_windows_publishes_only_owned_path_and_node_without_overwriting_custom_file(tmp_path, monkeypatch):
    import ctypes
    environment = setup.Environment(lambda *_: None, directory=tmp_path / "tools")
    prefix = environment.directory / "cli"
    prefix.mkdir(parents=True)
    node = tmp_path / "node source/node.exe"
    node.parent.mkdir()
    node.write_bytes(b"independent-node")
    saved_path = [r"C:\Existing;%MY_TOOL%"]
    class Key:
        def __enter__(self): return self
        def __exit__(self, *_): pass
    registry = SimpleNamespace(HKEY_CURRENT_USER=1, REG_EXPAND_SZ=2, CreateKey=lambda *_: Key(),
                               QueryValueEx=lambda *_: (saved_path[0], 2),
                               SetValueEx=lambda *args: saved_path.__setitem__(0, args[-1]))
    monkeypatch.setitem(sys.modules, "winreg", registry)
    def notify(*args): return 1
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=SimpleNamespace(SendMessageTimeoutW=notify)))
    info = {"managed_tools": str(environment.directory)}
    environment.expose_cli({"path": str(node)}, info)
    environment.expose_cli({"path": str(node)}, info)
    assert saved_path[0] == r"C:\Existing;%MY_TOOL%" + ";" + str(prefix)
    assert (prefix / "node.exe").read_bytes() == node.read_bytes()
    # Break the test hardlink before simulating an unrelated file in our prefix.
    (prefix / "node.exe").unlink()
    (prefix / "node.exe").write_bytes(b"custom")
    with pytest.raises(ValueError, match="未覆盖"):
        environment.expose_cli({"path": str(node)}, info)
    assert (prefix / "node.exe").read_bytes() == b"custom"
