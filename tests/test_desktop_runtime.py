"""Real process, journal and protocol checks with isolated synthetic settings."""
import asyncio
import json
import io
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from smart_search.i18n import use_language


@pytest.fixture(autouse=True)
def chinese_presentation():
    with use_language("zh"):
        yield

from smart_search import activity, cli
from smart_search.config import config
from smart_search.desktop_backend import Backend, child_environment
from smart_search import desktop_worker
from smart_search.desktop_catalog import command_catalog


@pytest.mark.parametrize("arguments", [[], ["search", "not executed"], ["--help"], ["--desktop-capabilities"]])
def test_app_helper_does_not_export_public_cli(monkeypatch, capsys, arguments):
    from smart_search import desktop_entry
    monkeypatch.setattr(sys, "argv", ["app-helper", *arguments])
    monkeypatch.setattr(cli, "main", lambda: pytest.fail("private App helper exposed CLI"))
    assert desktop_entry.main() == 2
    output = capsys.readouterr()
    assert not output.out and "Install the Smart Search CLI separately" in output.err


@pytest.mark.asyncio
async def test_app_no_longer_exposes_cli_or_publishes_bundled_path(tmp_path, monkeypatch):
    monkeypatch.setattr("smart_search.desktop_backend.shutil.which", lambda *args, **kwargs: None)
    monkeypatch.setattr("smart_search.desktop_backend.managed_cli_info", lambda *args: None)
    backend = Backend(lambda _: None)
    backend.initialized, backend.directory = True, str(tmp_path)
    assert "bundled_path" not in backend.cli_status()
    with pytest.raises(ValueError):
        await backend.handle("cli.enable", {"confirm": True})


def test_cli_observation_preserves_stdout_exit_and_privacy(tmp_path):
    query = "私密查询-do-not-store"
    env = dict(os.environ, SMART_SEARCH_CONFIG_DIR=str(tmp_path), SMART_SEARCH_MINIMUM_PROFILE="off")
    for arguments, exit_code in [(["route", query, "--router-mode", "rules"], 0), (["--help"], 0),
                                 (["config", "path"], 0), (["providers", "status"], 0),
                                 (["ui", "--check"], 0), (["invalid-private-argument"], 2)]:
        result = subprocess.run([sys.executable, "-m", "smart_search.cli", *arguments], env=env,
                                capture_output=True, text=True, encoding="utf-8", timeout=15)
        assert result.returncode == exit_code, result.stderr
        if arguments[0] not in {"--help", "invalid-private-argument"}:
            json.loads(result.stdout)
    store = activity.ActivityStore(tmp_path)
    rows = store.list_runs()
    assert len(rows) == 6
    assert all(row["status"] in {"finished", "failed"} for row in rows)
    for row in rows:
        detail = store.details(row["run_id"])
        assert len([e for e in detail["events"] if e["status"] != "running"]) == 1
    assert query.encode() not in store.path.read_bytes()
    assert b"invalid-private-argument" not in store.path.read_bytes()


def test_activity_failure_does_not_break_cli(tmp_path):
    (tmp_path / "activity.sqlite3").write_bytes(b"not-a-database")
    result = subprocess.run([sys.executable, "-m", "smart_search.cli", "config", "path"],
                            env=dict(os.environ, SMART_SEARCH_CONFIG_DIR=str(tmp_path)),
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert json.loads(result.stdout)["config_file"]
    assert result.stderr.count("activity recording unavailable") == 1


def test_cli_discovery_never_triggers_npm_runtime_repair(tmp_path, monkeypatch):
    wrapper = tmp_path / "node_modules/.bin/smart-search.cmd"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text("must never run")
    package = tmp_path / "node_modules/@konbakuyomu/smart-search"
    package.mkdir(parents=True)
    (package / "package.json").write_text(json.dumps({"name": "@konbakuyomu/smart-search", "version": "0.1.1"}))
    monkeypatch.setattr("smart_search.desktop_backend.shutil.which", lambda _, **kwargs: str(wrapper))
    monkeypatch.setattr("smart_search.desktop_backend.subprocess.run", lambda *a, **k: pytest.fail("public wrapper was executed"))
    result = Backend(lambda _: None).cli_status()
    assert result["external_version"] == "0.1.1"
    assert "缺失" in result["external_status"]


def test_worker_environment_excludes_credentials_but_snapshot_preserves_source(tmp_path, monkeypatch):
    monkeypatch.setenv("EXA_API_KEY", "environment-only-secret")
    env = child_environment(str(tmp_path))
    assert not set(config._CONFIG_KEYS) & env.keys()
    assert env["PATH"] == os.environ["PATH"]
    values, sources = config.effective_values(masked=False), config.get_config_sources()
    monkeypatch.delenv("EXA_API_KEY")
    with config.snapshot(values, merge=False, directory=str(tmp_path), source_overrides=sources):
        assert config.exa_api_key == "environment-only-secret"
        assert config.get_config_source("EXA_API_KEY") == "environment"


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", ["", '{"cancel":', "[]\n"])
async def test_worker_cancels_when_control_pipe_is_lost_or_malformed(monkeypatch, frame):
    async def slow(_):
        try:
            await asyncio.sleep(10)
            return {"status": "finished"}
        except asyncio.CancelledError:
            return {"status": "cancelled"}
    monkeypatch.setattr(desktop_worker, "execute", slow)
    monkeypatch.setattr(sys, "stdin", io.StringIO(frame))
    result = await asyncio.wait_for(desktop_worker._run({}), 1)
    assert result["status"] == "cancelled"


def test_journal_terminal_survives_brief_writer_contention(tmp_path):
    store = activity.ActivityStore(tmp_path)
    store.start("contended", "route", "cli", "test")
    locked = threading.Event()
    def writer():
        with store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            locked.set()
            time.sleep(.35)
    thread = threading.Thread(target=writer)
    thread.start()
    assert locked.wait(2)
    store.finish("contended", 0, "finished")
    thread.join(2)
    assert store.list_runs()[0]["status"] == "finished"


def test_phase_completion_preserves_provider_and_model(tmp_path):
    store = activity.ActivityStore(tmp_path)
    store.start("phase", "search", "app", "test")
    store.progress("phase", phase="main_search", provider="openai-compatible", model="test-model")
    store.progress("phase", phase="main_search:ok", provider="OpenAI-compatible")
    store.progress("phase", phase="main_search:ok")
    row = store.details("phase")["run"]
    assert (row["provider"], row["model"]) == ("OpenAI-compatible", "test-model")
    store.progress("phase", phase="docs_search", provider="exa")
    store.progress("phase", phase="docs_search:ok")
    store.finish("phase", 0, "finished")
    terminal = store.details("phase")["events"][-1]
    assert (terminal["provider"], terminal["model"]) == ("exa", "")


@pytest.mark.asyncio
@pytest.mark.parametrize("provider,key,model_key", [
    ("xai-responses", "XAI_API_KEY", "XAI_MODEL"),
    ("openai-compatible", "OPENAI_COMPATIBLE_API_KEY", "OPENAI_COMPATIBLE_MODEL"),
    ("firecrawl", "FIRECRAWL_API_KEY", None),
])
async def test_provider_worker_records_applicable_model_and_memory_fallback(tmp_path, monkeypatch, provider, key, model_key):
    model = "test-requested-model" if model_key else ""
    values = {key: "synthetic-key", "OPENAI_COMPATIBLE_API_URL": "https://example.invalid/v1"}
    if model_key:
        values[model_key] = model

    async def check_main(candidate):
        assert candidate["model"] == model
        return {"status": "ok", "message": "ok"}

    monkeypatch.setattr(desktop_worker.service, "_safe_test_main_provider_connection", check_main)
    run_id = uuid.uuid4().hex
    envelope = await desktop_worker.execute({"method": "provider.test", "command": "provider.test",
        "params": {"provider": provider}, "values": values, "config_dir": str(tmp_path), "run_id": run_id})
    row = activity.ActivityStore(tmp_path).details(run_id)["run"]
    assert (row["provider"], row["model"]) == (provider, model)
    assert row["status"] == "finished" and envelope["status"] == "finished"
    assert envelope["result"]["model"] == model
    if provider == "firecrawl":
        assert envelope["result"]["ok"] is False  # completed presence check, not a verified API
    memory = Backend.run_metadata({**row, "directory": str(tmp_path), "process": None,
                                   "result": envelope["result"]})
    assert (memory["provider"], memory["model"]) == (provider, model)
    assert not (tmp_path / "provider_health.json").exists()


def test_final_activity_uses_primary_metadata_without_corrupting_supplemental_events():
    with activity.observe("search", version="test") as run:
        activity.progress("main_search", "xai-responses", "grok-test")
        activity.progress("extra_sources", "exa")
        activity.result({"provider": "xai-responses", "model": "grok-test"})
    details = activity.ActivityStore().details(run.run_id)
    assert (details["run"]["provider"], details["run"]["model"]) == ("xai-responses", "grok-test")
    extra = next(event for event in details["events"] if event["phase"] == "extra_sources")
    assert (extra["provider"], extra["model"]) == ("exa", "")


def test_journal_terminal_retention_and_redaction(tmp_path, monkeypatch):
    secret = "synthetic-unique-key"
    config.set_config_value("EXA_API_KEY", secret)
    with activity.observe("search", version="test") as run:
        activity.progress("main_search", "exa", "model-" + secret)
        activity.result({"error_type": "raw " + secret, "sources": [1, 2], "content": "private-answer"})
        run.finish(5, "cancelled")
        run.finish(0)
    store = activity.ActivityStore()
    row = store.list_runs()[0]
    assert row["status"] == "cancelled" and row["sources_count"] == 2
    assert secret not in json.dumps(store.details(row["run_id"]))
    assert b"private-answer" not in store.path.read_bytes()
    store.start("running", "route", "cli", "test")
    monkeypatch.setattr(activity, "MAX_COMPLETED_RUNS", 1)
    store.start("new", "route", "cli", "test")
    store.finish("new", 0, "finished")
    assert {r["run_id"] for r in store.list_runs()} == {"running", "new"}
    store.clear()
    assert [r["run_id"] for r in store.list_runs()] == ["running"]
    assert config.exa_api_key == secret
    with store.connection() as db:
        db.execute("UPDATE runs SET updated_at=?", (time.time() - 60,))
    assert store.list_runs()[0]["status"] == "stale"


@pytest.mark.asyncio
async def test_backend_protocol_catalog_and_real_worker(tmp_path):
    events = []
    backend = Backend(events.append)
    backend.cli_info = {"version": "test"}
    with pytest.raises(ValueError, match="握手"):
        await backend.handle("config.apply", {"revision": "", "set": {}})
    for version in (999, True, 1.0):
        with pytest.raises(ValueError, match="不匹配"):
            await backend.handle("initialize", {"protocol_version": version})
    state = await backend.handle("initialize", {"protocol_version": 1, "config_dir": str(tmp_path)})
    catalog = {item["id"]: item for item in state["commands"]}
    assert set(catalog) == {"search", "fetch", "context7-library", "context7-docs", "route", "smoke"}
    assert not {"config/set", "skills/update", "setup", "ui"} & catalog.keys()
    fields = {f["name"] for f in catalog["search"]["fields"]}
    assert {"stream", "no_stream"} <= fields
    assert any("\u4e00" <= character <= "\u9fff" for character in catalog["search"]["description"])
    assert all(any("\u4e00" <= char <= "\u9fff" for char in item["description"]) for item in catalog.values())
    with pytest.raises(ValueError):
        await backend.handle("run.start", {"command": "config/set", "arguments": ["EXA_API_KEY", "no"]})
    launch = await backend.handle("run.start", {"command": "route", "arguments": ["中文路由", "--router-mode", "rules"]})
    await asyncio.wait_for(backend.runs[launch["run_id"]]["task"], 15)
    result = await backend.handle("run.result", {"run_id": launch["run_id"]})
    assert result["status"] == "finished", result
    assert result["result"]["ok"]
    assert result["result"]["display_text"] == cli._render("route", {key: value for key, value in result["result"].items() if key != "display_text"}, "markdown")
    assert len([event for event in events if event["event"] == "run"]) == 1
    assert events[0]["generation"] == backend.generation
    with pytest.raises(ValueError, match="只能观察"):
        await backend.handle("run.cancel", {"run_id": "external"})
    await backend.handle("activity.enabled", {"enabled": False})
    unrecorded = await backend.handle("run.start", {"command": "route", "arguments": ["无持久记录", "--router-mode", "rules"]})
    assert any(row["run_id"] == unrecorded["run_id"] for row in backend.activity()["runs"])
    await asyncio.wait_for(backend.runs[unrecorded["run_id"]]["task"], 15)
    detail = await backend.handle("activity.details", {"run_id": unrecorded["run_id"]})
    assert detail["run"]["status"] == "finished" and detail["run"]["recorded"] is False
    await backend.handle("activity.clear", {})
    assert backend.activity()["runs"] == []
    assert backend.run_result(unrecorded["run_id"])["result"]["ok"]
    await backend.close()


@pytest.mark.asyncio
async def test_private_tasks_snapshot_cancel_and_secret_echo(tmp_path):
    seen = []
    started = threading.Event()
    release = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            key = self.headers.get("x-api-key", "")
            seen.append(key)
            if key == "old-synthetic-secret":
                started.set()
                release.wait(10)
            self.send_response(401 if key == "echo-synthetic-secret" else 200)
            self.end_headers()
            try:
                self.wfile.write(("credential " + key).encode())
            except (BrokenPipeError, ConnectionError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config.update_config_values({"EXA_API_KEY": "old-synthetic-secret", "EXA_BASE_URL": f"http://127.0.0.1:{server.server_port}"})
    events = []
    backend = Backend(events.append)
    backend.cli_info = {}
    await backend.handle("initialize", {"protocol_version": 1, "config_dir": str(tmp_path)})
    try:
        slow = await backend.handle("provider.test", {"provider": "exa"})
        assert await asyncio.to_thread(started.wait, 10), backend.run_result(slow["run_id"])
        config.set_config_value("EXA_API_KEY", "new-synthetic-secret")
        fast = await backend.handle("provider.test", {"provider": "exa"})
        await asyncio.wait_for(backend.runs[fast["run_id"]]["task"], 10)
        await backend.handle("run.cancel", {"run_id": slow["run_id"]})
        await asyncio.wait_for(backend.runs[slow["run_id"]]["task"], 5)
        assert backend.run_result(slow["run_id"])["status"] == "cancelled"
        assert backend.run_result(fast["run_id"])["status"] == "finished"
        assert seen[:2] == ["old-synthetic-secret", "new-synthetic-secret"]
        check = (await backend.handle("get_state", {}))["provider_checks"]["exa"]
        assert check["scope"] == "current" and check["source"] == "app" and check["checked_at"] > 0
        echo = await backend.handle("provider.test", {"provider": "exa", "overrides": {"EXA_API_KEY": "echo-synthetic-secret"}})
        await asyncio.wait_for(backend.runs[echo["run_id"]]["task"], 10)
        assert "echo-synthetic-secret" not in json.dumps(backend.run_result(echo["run_id"]))
        echo_check = (await backend.handle("get_state", {}))["provider_checks"]["exa"]
        assert echo_check["status"] == "warning" and echo_check["scope"] == "draft"
        assert not (tmp_path / "provider_health.json").exists()
        assert config.exa_api_key == "new-synthetic-secret"
        journal = (tmp_path / "activity.sqlite3").read_bytes()
        assert all(secret.encode() not in journal for secret in seen)
    finally:
        release.set()
        await backend.close()
        server.shutdown()
        server.server_close()


def test_stdio_version_handshake_and_shutdown(tmp_path):
    messages = [{"id": 1, "method": "initialize", "params": {"protocol_version": 0}},
                {"id": 2, "method": "config.apply", "params": {"revision": "", "set": {"EXA_API_KEY": "no-write"}}},
                {"id": 3, "method": "initialize", "params": {"protocol_version": 1}},
                {"id": 4, "method": "shutdown"}]
    result = subprocess.run([sys.executable, "-m", "smart_search.desktop_entry", "--desktop-backend"],
                            input="".join(json.dumps(m) + "\n" for m in messages), capture_output=True, text=True,
                            encoding="utf-8", timeout=20, env=dict(os.environ, SMART_SEARCH_CONFIG_DIR=str(tmp_path), PATH=""))
    assert result.returncode == 0, result.stderr
    responses = {value["id"]: value for line in result.stdout.splitlines() if "id" in (value := json.loads(line))}
    assert "error" in responses[1] and "error" in responses[2]
    assert responses[3]["result"]["protocol_version"] == 1
    assert responses[4]["result"]["ok"]
    assert not (tmp_path / "config.json").exists()


@pytest.mark.parametrize("include_secrets", [None, False, True])
def test_native_config_secrets_require_opt_in_and_follow_selected_profile(tmp_path, include_secrets):
    secret = "synthetic-editable-credential"
    environment_secret = "synthetic-environment-credential"
    saved = {"EXA_API_KEY": secret, "OPENAI_COMPATIBLE_MODEL": "editable-model"}
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(saved), encoding="utf-8")
    empty_profile = tmp_path / "empty-profile"
    empty_profile.mkdir()
    params = {"protocol_version": 1, "enable_update_checks": False}
    if include_secrets is not None:
        params["include_config_secrets"] = include_secrets
    messages = [
        {"id": 1, "method": "initialize", "params": params},
        {"id": 2, "method": "get_state"},
        {"id": 3, "method": "profile.select", "params": {"config_dir": str(empty_profile)}},
        {"id": 4, "method": "shutdown"},
    ]
    env = {key: value for key, value in os.environ.items() if key not in config._CONFIG_KEYS}
    env.update(SMART_SEARCH_CONFIG_DIR=str(tmp_path), PATH="", TAVILY_API_KEY=environment_secret)
    result = subprocess.run(
        [sys.executable, "-m", "smart_search.desktop_entry", "--desktop-backend"],
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True, text=True, encoding="utf-8", timeout=20, env=env,
    )
    assert result.returncode == 0, result.stderr
    frames = [json.loads(line) for line in result.stdout.splitlines()]
    responses = {frame["id"]: frame["result"] for frame in frames if "id" in frame}
    for identifier in (1, 2, 3):
        state = responses[identifier]
        if include_secrets:
            credentials = state.pop("config_secrets")
            assert credentials["EXA_API_KEY"] == ("" if identifier == 3 else secret)
            assert "TAVILY_API_KEY" not in credentials
            assert "OPENAI_COMPATIBLE_MODEL" not in credentials
        else:
            assert "config_secrets" not in state
        if identifier != 3:
            assert state["values"]["OPENAI_COMPATIBLE_MODEL"] == "editable-model"
    assert secret not in json.dumps(frames)
    assert environment_secret not in result.stdout
    assert secret not in result.stderr
    assert json.loads(config_path.read_text(encoding="utf-8")) == saved
    assert not (empty_profile / "config.json").exists()


def test_native_update_prepare_preserves_pr51_private_state_contract(tmp_path):
    saved = {"EXA_API_KEY": "synthetic-pr51-key", "EXA_ENABLED": False}
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(saved), encoding="utf-8")
    messages = [
        {"id": 1, "method": "initialize", "params": {"protocol_version": 1,
         "include_config_secrets": True, "enable_update_checks": False}},
        {"id": 2, "method": "updates.state"},
        {"id": 3, "method": "app.update-prepare"},
        {"id": 4, "method": "get_state"},
        {"id": 5, "method": "shutdown"},
    ]
    env = {key: value for key, value in os.environ.items() if key not in config._CONFIG_KEYS}
    env.update(SMART_SEARCH_CONFIG_DIR=str(tmp_path), PATH="")
    result = subprocess.run(
        [sys.executable, "-m", "smart_search.desktop_entry", "--desktop-backend"],
        input="".join(json.dumps(message) + "\n" for message in messages),
        capture_output=True, text=True, encoding="utf-8", timeout=20, env=env,
    )
    assert result.returncode == 0, result.stderr
    frames = [json.loads(line) for line in result.stdout.splitlines()]
    replies = {frame["id"]: frame for frame in frames if "id" in frame}
    state = replies[1]["result"]
    assert state["config_secrets"]["EXA_API_KEY"] == saved["EXA_API_KEY"]
    assert state["values"]["EXA_ENABLED"].lower() == "false"
    assert state["default_config_dir"] and not state["is_default_config_dir"]
    assert "installed_cli" in replies[2]["result"]
    assert replies[3]["result"]["ok"] and replies[5]["result"]["ok"]
    assert "error" in replies[4] and "result" not in replies[4]
    assert json.loads(config_file.read_text(encoding="utf-8")) == saved


@pytest.mark.asyncio
@pytest.mark.parametrize("default_exists", [False, True])
async def test_restore_default_profile_reads_its_config_without_copying_or_overwriting(tmp_path, monkeypatch, default_exists):
    custom = tmp_path / "custom"
    custom.mkdir()
    custom_file = custom / "config.json"
    custom_contents = '{"OPENAI_COMPATIBLE_MODEL":"custom-model"}'
    custom_file.write_text(custom_contents, encoding="utf-8")
    default = tmp_path / "default"
    default_file = default / "config.json"
    default_contents = '{"OPENAI_COMPATIBLE_MODEL":"default-model"}'
    if default_exists:
        default.mkdir()
        default_file.write_text(default_contents, encoding="utf-8")
    monkeypatch.setattr(config, "_default_config_dir", lambda: default)
    monkeypatch.setenv("SMART_SEARCH_CONFIG_DIR", str(custom))
    monkeypatch.setattr("smart_search.desktop_backend.shutil.which", lambda _: None)
    backend = Backend(lambda _: None)
    try:
        initial = await backend.handle("initialize", {"protocol_version": 1, "config_dir": str(custom)})
        assert initial["default_config_dir"] == str(default)
        assert not initial["is_default_config_dir"]
        restored = await backend.handle("profile.select", {"config_dir": initial["default_config_dir"]})
        assert restored["config_dir"] == str(default)
        assert restored["is_default_config_dir"]
        assert restored["values"].get("OPENAI_COMPATIBLE_MODEL", "") == ("default-model" if default_exists else "")
        assert restored["environment"]["config_dir"] == str(default)
        assert os.environ["SMART_SEARCH_CONFIG_DIR"] == str(custom)
        assert custom_file.read_text(encoding="utf-8") == custom_contents
        if default_exists:
            assert default_file.read_text(encoding="utf-8") == default_contents
        else:
            assert not default_file.exists()
        switched_back = await backend.handle("profile.select", {"config_dir": str(custom)})
        assert not switched_back["is_default_config_dir"]
        assert switched_back["values"]["OPENAI_COMPATIBLE_MODEL"] == "custom-model"
    finally:
        await backend.close()
