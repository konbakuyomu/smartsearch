"""Private native-app stdio bridge. No listener, shell, or mandatory daemon."""
from __future__ import annotations

import asyncio
import contextlib
import json
import io
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid

from . import cli, service, ui_api
from .activity import ActivityStore, RETENTION_SECONDS
from .config import config
from .desktop_catalog import command_arguments, command_catalog
from .desktop_updates import Updates
from .desktop_cli import discover, managed_cli_info, package_root, path_entries, update_command
from .desktop_environment import Environment, cli_runtime_commands, depends_on_app, installer_environment
from .desktop_skills import Skills
from .i18n import render_messages, resolve, tr, use_language
from .provider_errors import sanitize_provider_error_message as sanitize_error_message
from .ui_metadata import CONFIG_FIELDS

PROTOCOL_VERSION = 1
MAX_LINE = 2 * 1024 * 1024
RELEASE_URL = "https://github.com/konbakuyomu/smartsearch/releases"


def engine_command(*arguments):
    if getattr(sys, "frozen", False):
        return [sys.executable, *arguments]
    return [sys.executable, "-m", "smart_search.desktop_entry", *arguments]


def absolute_directory(value):
    if not isinstance(value, str) or not value.strip() or not Path(value).expanduser().is_absolute():
        raise ValueError(tr('配置目录必须是绝对路径。'))
    return str(Path(value).expanduser().resolve())


def child_environment(directory):
    # Provider credentials travel only in the private worker's stdin snapshot.
    return {**{key: value for key, value in os.environ.items() if key not in config._CONFIG_KEYS},
            "SMART_SEARCH_CONFIG_DIR": directory, "PYTHONUTF8": "1"}


def manager_environment(directory):
    return {key: value for key, value in child_environment(directory).items()
            if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}}


class Backend:
    def __init__(self, emit):
        self.emit = emit
        self.generation = uuid.uuid4().hex
        self.directory = ""
        self.initialized = False
        self.include_config_secrets = False
        self.language = "zh"  # Protocol v1 clients without a language keep their existing presentation.
        self.stopping = False
        self.app_update_pending = False
        self.runs = {}
        self.cli_info = None
        self.updates = Updates(self.event)
        self.environment = Environment(self.event)
        self.skills = Skills(self.event, self.environment)

    def event(self, name, data):
        self.emit(render_messages({"event": name, "generation": self.generation,
                                   "data": {**data, "generation": self.generation}}, self.language))

    def activity(self, params=None):
        params = params or {}
        directories = params.get("directories", [self.directory])
        if not isinstance(directories, list) or len(directories) > 20:
            raise ValueError(tr('最多可观察 20 个明确选择的配置目录。'))
        limit = params.get("limit", 100)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError(tr('limit 必须介于 1 与 1000。'))
        runs, errors, enabled = [], [], True
        directories = list(dict.fromkeys(absolute_directory(value) for value in directories))
        for directory in directories:
            try:
                store = ActivityStore(directory)
                runs.extend(store.list_runs(limit))
                if directory == self.directory:
                    enabled = store.enabled()
            except (OSError, ValueError, sqlite3.Error):
                errors.append({"config_dir": directory, "error": tr('活动记录不可读，当前状态未知。')})
        by_id = {row["run_id"]: row for row in runs}
        for run in self.runs.values():
            if run["directory"] not in directories or run.get("history_cleared") or time.time() - run.get("finished_at", time.time()) > RETENTION_SECONDS:
                continue
            row = by_id.get(run["run_id"])
            if row is None:
                by_id[run["run_id"]] = self.run_metadata(run)
            elif run["status"] not in {"running", "cancelling"}:
                row["status"] = run["status"]
        runs = list(by_id.values())
        return {"ok": not errors, "runs": sorted(runs, key=lambda row: row["started_at"], reverse=True)[:limit],
                "errors": errors, "enabled": enabled}

    @staticmethod
    def run_metadata(run):
        now = time.time()
        terminal = run["status"] not in {"running", "cancelling"}
        result = run["result"] or {}
        return {"run_id": run["run_id"], "command": run["command"], "origin": "app", "config_dir": run["directory"],
                "version": cli._get_version(), "pid": run["process"].pid if run["process"] else None,
                "status": run["status"], "phase": "completed" if terminal else "running",
                "provider": result.get("provider") or run.get("provider", ""), "model": result.get("model", ""),
                "started_at": run["started_at"], "updated_at": run.get("finished_at", now),
                "finished_at": run.get("finished_at"), "elapsed_ms": (run.get("finished_at", now) - run["started_at"]) * 1000,
                "sequence": 0, "error_type": (run["result"] or {}).get("error_type", ""), "config_revision": "",
                "recorded": False}

    def state(self):
        data = ui_api.state()
        default_directory = config._default_config_dir().resolve()
        data.update(protocol_version=PROTOCOL_VERSION, version=cli._get_version(), generation=self.generation,
                    config_dir=self.directory, default_config_dir=str(default_directory),
                    is_default_config_dir=config._same_config_dir(Path(self.directory), default_directory),
                    commands=command_catalog(), cli=self.cli_status(),
                    updates=self.updates.state, environment=self.environment.state, skills=self.skills.state, language=self.language)
        checks = {}
        for run in sorted(self.runs.values(), key=lambda item: item.get("finished_at", 0)):
            if run["command"] != "provider.test" or run["directory"] != self.directory or not run.get("finished_at"):
                continue
            result = run["result"] or {}
            checks[run["provider"]] = {"status": result.get("status", run["status"]), "checked_at": run["finished_at"],
                                       "source": "app", "scope": run["scope"], "probe": result.get("probe", "none"),
                                       "message": result.get("message", result.get("error", ""))}
        data["provider_checks"] = checks
        if self.include_config_secrets:
            # Only an opted-in native client receives editable credentials over
            # its private pipe. Shared Web/CLI status remains masked.
            effective = config.effective_values(masked=False)
            data["config_secrets"] = {
                field.key: effective.get(field.key, "")
                for field in CONFIG_FIELDS
                if field.kind == "secret" and config.get_config_source(field.key) != "environment"
            }
        return data

    def cli_status(self):
        if self.cli_info is not None:
            self.updates.refresh_installed(self.cli_info)
            return self.cli_info
        external = shutil.which("smart-search")
        managed = managed_cli_info(manager_environment(self.directory), self.environment.directory)
        if not external and managed:
            external = managed["external_path"]
        data = {"external_path": external, "version": cli._get_version(),
                "external_version": None, "activity_protocol_version": 1, "external_activity_protocol_version": None,
                "external_runtime_verified": False,
                "manager": "none", "manager_label": tr('未安装独立 CLI'), "can_update": False,
                "external_status": tr('未发现外部 CLI') if not external else tr('版本及观测能力尚未验证')}
        if external:
            external_path = Path(external).resolve()
            probe_command = None
            if getattr(sys, "frozen", False) and external_path == Path(sys.executable).resolve():
                probe_command = [str(external_path)]
                data.update(manager="bundled", manager_label=tr('随 App 更新'), can_update=False)
            else:
                # npm's public wrapper repairs a missing runtime on invocation. Discovery
                # must never trigger that installer; probe an existing private Python only.
                if managed and Path(external).resolve() == Path(managed["external_path"]).resolve():
                    data.update(managed)
                    data["other_paths"] = [str(path) for path in path_entries() if package_root(path)[0] != Path(managed["package_root"])]
                    if data["other_paths"]:
                        data.update(can_update=False, update_note=tr('PATH 中存在其他同名 CLI，请先处理冲突。'))
                else:
                    data.update(discover(external, manager_environment(self.directory)))
                if data.get("package_root"):
                    root = Path(data["package_root"])
                    python = root / ".smart-search-python" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                    if python.is_file():
                        probe_command = [str(python), "-m", "smart_search.cli"]
                    else:
                        data["external_status"] = tr('外部 npm CLI 的运行环境缺失；App 不会自动修复该安装。')
            if probe_command is None:
                self.cli_info = data
                self.updates.refresh_installed(data)
                return data
            env = {**manager_environment(self.directory), "SMART_SEARCH_ACTIVITY_ENABLED": "false"}
            try:
                version = subprocess.run([*probe_command, "--version"], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                         timeout=3, env=env, cwd=Path.home(), creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if version.returncode == 0 and version.stdout.strip().startswith("smart-search "):
                    reported_version = version.stdout.strip().split()[-1]
                    data["external_runtime_verified"] = data["external_version"] in {None, reported_version}
                    data["external_version"] = reported_version
                capabilities = subprocess.run([*probe_command, "--desktop-capabilities"], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                              timeout=3, env=env, cwd=Path.home(), creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if capabilities.returncode == 0:
                    parsed = json.loads(capabilities.stdout)
                    data["external_activity_protocol_version"] = parsed.get("activity_protocol_version")
                data["external_status"] = tr('支持实时活动') if data["external_activity_protocol_version"] == 1 else tr('该 CLI 尚未接入活动观测；升级后可见新调用。')
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                data["runtime_probe_error"] = "timeout" if isinstance(error, subprocess.TimeoutExpired) else "launch_failed" if isinstance(error, OSError) else "invalid_result"
                data["external_status"] = tr('外部 CLI 检查未完成；不能判断是否支持活动观测。')
        self.cli_info = data
        self.updates.refresh_installed(data)
        return data

    def update_cli(self, params):
        if params.get("confirm") is not True:
            raise ValueError(tr('只有明确点击更新 CLI 后才可执行。'))
        if self.environment.state["busy"]:
            raise ValueError(tr('环境准备或检查正在进行，请等待完成。'))
        if self.updates.cli_task and not self.updates.cli_task.done():
            return self.updates.state
        latest = self.updates.state["cli"]
        previous = dict(self.cli_status())
        self.cli_info = None
        current = self.cli_status()
        identity = ("external_path", "resolved_path", "external_version", "manager", "manager_command", "manager_options")
        if any(previous.get(key) != current.get(key) for key in identity):
            raise ValueError(tr('CLI 来源或版本刚刚发生变化，请刷新并重新检查更新。'))
        version = latest.get("latest_version")
        if latest.get("error") or not latest.get("available") or params.get("version") != version or latest.get("current_version") != current.get("external_version"):
            raise ValueError(tr('请先成功检查当前 CLI 的目标版本。'))
        if any(run["status"] in {"running", "cancelling"} for run in self.runs.values()):
            raise ValueError(tr('请先等待 App 自有任务完成，再更新 CLI。'))
        observed = self.activity().get("runs", [])
        if any(row.get("origin") == "cli" and row.get("status") in {"running", "cancelling"} for row in observed):
            raise ValueError(tr('当前配置目录有 CLI 正在运行，请等待它完成后更新。'))
        command = update_command(current, version)
        self.updates.state["cli_update"] = {"status": "running", "target_version": version, "error": "",
                                             "command": subprocess.list2cmdline(command), "log": tr('正在调用原管理器，请保持 App 打开。')}
        self.updates.changed()
        self.updates.cli_task = asyncio.create_task(self.execute_cli_update(command, version, current["manager"]))
        return self.updates.state

    async def execute_cli_update(self, command, version, manager):
        state = self.updates.state["cli_update"]
        log_path = self.updates.directory / "cli-update.log"
        tail = ""

        async def run(argv, env):
            nonlocal tail
            tail = sanitize_error_message(tail + "\n> " + subprocess.list2cmdline(argv) + "\n", limit=32000)[-16000:]
            state["log"] = tail
            self.updates.changed()
            process = await asyncio.create_subprocess_exec(*argv, cwd=Path.home(), env=env,
                stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            async def consume():
                nonlocal tail
                last_notice = 0
                while chunk := await process.stdout.read(4096):
                    tail = sanitize_error_message(tail + chunk.decode("utf-8", errors="replace"), limit=32000)[-16000:]
                    if time.monotonic() - last_notice >= .5:
                        state["log"] = tail
                        self.updates.changed()
                        last_notice = time.monotonic()
                return await process.wait()
            try:
                return await asyncio.wait_for(consume(), 1200)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()

        try:
            self.updates.directory.mkdir(parents=True, exist_ok=True)
            env = manager_environment(self.directory)
            info = self.cli_status()
            if info.get("managed_tools"):
                node = info["manager_command"][0]
                env["PATH"] = os.pathsep.join([str(Path(node).parent), str(Path(info["python_path"]).parent), env.get("PATH", "")])
                env["SMART_SEARCH_PYTHON"] = info["python_path"]
            exit_code = await run(command, env)
            self.cli_info = None
            current = self.cli_status()
            def same_install(current):
                return (current.get("external_version") == version and current.get("manager") == manager
                        and current.get("can_update") and all(current.get(key) == info.get(key)
                        for key in ("external_path", "manager_command", "manager_options", "manager_config")))
            if exit_code == 0 and same_install(current) and current.get("external_runtime_verified") is not True:
                root, package = package_root(current.get("resolved_path", ""))
                if root is None or str(root) != current.get("package_root") or package.get("version") != version or depends_on_app(root):
                    raise ValueError(tr('CLI 包的位置或版本已变化，未准备运行环境；请重新检查。'))
                python = await asyncio.to_thread(self.environment.probe_python, env)
                if not python.get("ready"):
                    raise ValueError(tr('CLI 包已更新，但缺少可用的独立 Python；请在“共用独立 CLI 环境”完成准备后重试。'))
                tail += "\n" + tr('正在修复独立 CLI 私有环境；保留原 npm/mise 安装与版本…') + "\n"
                state["log"] = tail
                self.updates.changed()
                clean = installer_environment(env, self.updates.directory / "cli-runtime")
                for argv in cli_runtime_commands(root, python["path"]):
                    if await run(argv, clean) != 0:
                        raise ValueError(tr('CLI 包已更新，但 Python 运行环境准备失败；请查看日志并重试。'))
                self.cli_info = None
                current = self.cli_status()
            verified = exit_code == 0 and same_install(current) and current.get("external_runtime_verified") is True
            state.update(status="finished" if verified else "failed", exit_code=exit_code, log=tail,
                         error="" if verified else tr('管理器执行失败，或 CLI 实际版本/运行环境未通过验证；请查看日志并重新检查。'),
                         actual_version=current.get("external_version"), log_path=str(log_path), cli=current)
            self.updates.refresh_installed(current)
        except ValueError as error:
            state.update(status="failed", error=sanitize_error_message(str(error)))
        except (OSError, asyncio.TimeoutError):
            state.update(status="failed", error=tr('CLI 更新或运行环境准备未完成，请查看日志并重试。'))
        finally:
            state.update(log=tail, log_path=str(log_path))
            with contextlib.suppress(OSError):
                log_path.write_text(tail, encoding="utf-8")
            self.updates.changed()

    def start(self, method, params):
        if method == "skills.install" and self.environment.state["busy"]:
            raise ValueError(tr('环境操作正在配置接入文件，请等待完成。'))
        if sum(run["status"] in {"running", "cancelling"} for run in self.runs.values()) >= 8:
            raise ValueError(tr('最多同时运行 8 个 App 任务。'))
        command = params.get("command") if method == "run.start" else method
        if method == "run.start":
            argv = command_arguments(command, params.get("arguments", []))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                try:
                    cli.build_parser().parse_args(argv)
                except SystemExit as error:
                    raise ValueError(tr('参数无效，请检查必填项和参数范围。')) from error
        elif method == "provider.test":
            if params.get("provider") not in service.PROBE_KIND:
                raise ValueError(tr('未知服务商。'))
            overrides = params.get("overrides", {})
            if not isinstance(overrides, dict) or any(not isinstance(v, str) for v in overrides.values()):
                raise ValueError(tr('overrides 必须是字符串键值对象。'))
            for key, value in overrides.items():
                if key not in config._CONFIG_KEYS:
                    raise ValueError(tr('未知配置键。'))
                if value:
                    config._validate_config_value(key, value)
        elif method == "skills.install":
            if not isinstance(params.get("targets"), list) or not params["targets"]:
                raise ValueError(tr('请选择要安装的 Skills 目标。'))
            ui_api._resolve_targets(params["targets"])
        values = config.effective_values(masked=False)
        if method == "provider.test":
            values.update(params.get("overrides", {}))
        run_id = uuid.uuid4().hex
        payload = {"method": method, "command": command, "params": params, "values": values,
                   "sources": config.get_config_sources(), "config_dir": self.directory, "run_id": run_id,
                   "language": self.language}
        run = {"run_id": run_id, "status": "running", "result": None, "process": None, "cancel_requested": False,
               "directory": self.directory, "command": command, "started_at": time.time(),
               "provider": params.get("provider", "") if method == "provider.test" else "",
               "scope": "draft" if params.get("overrides") else "current"}
        self.runs[run_id] = run
        run["task"] = asyncio.create_task(self.execute(run, payload))
        # Results contain user content only in memory; keep a bounded recent set.
        completed = [key for key, value in self.runs.items() if value["status"] not in {"running", "cancelling"}]
        for key in completed[:-100]:
            self.runs.pop(key)
        return {"ok": True, "run_id": run_id}

    async def execute(self, run, payload):
        try:
            process = await asyncio.create_subprocess_exec(*engine_command("--desktop-worker"),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
                env=child_environment(payload["config_dir"]),
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            run["process"] = process
            process.stdin.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
            await process.stdin.drain()
            if run["cancel_requested"]:
                process.stdin.write(b'{"cancel":true}\n')
                await process.stdin.drain()
            chunks, size = [], 0
            while chunk := await process.stdout.read(65536):
                size += len(chunk)
                if size > 32 * 1024 * 1024:
                    process.kill()
                    raise ValueError(tr('结果超过 32 MiB；请缩小请求或选择输出文件。'))
                chunks.append(chunk)
            output = b"".join(chunks)
            await process.wait()
            if not output or process.returncode:
                raise ValueError(tr('任务进程已中断。'))
            envelope = json.loads(output)
            run.update(status=envelope["status"], result=envelope["result"])
        except (Exception, asyncio.CancelledError):
            run.update(status="cancelled" if run["cancel_requested"] else "failed",
                       result={"ok": False, "error_type": "cancelled" if run["cancel_requested"] else "runtime_error",
                               "error": tr('任务已取消。') if run["cancel_requested"] else tr('任务进程中断或响应无效。')})
        finally:
            run["finished_at"] = time.time()
            process = run["process"]
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            with contextlib.suppress(Exception):
                ActivityStore(run["directory"]).finish(run["run_id"], 0 if run["status"] == "finished" else 5, run["status"],
                                                     error_type=run["result"].get("error_type", ""))
            self.event("run", self.run_result(run["run_id"]))

    def run_result(self, run_id):
        if run_id not in self.runs:
            raise ValueError(tr('该任务不属于当前 App 后端；外部 CLI 只能观察。'))
        run = self.runs[run_id]
        return {"ok": True, "run_id": run_id, "status": run["status"], "result": run["result"]}

    async def cancel(self, run_id):
        self.run_result(run_id)
        run = self.runs[run_id]
        if run["status"] not in {"running", "cancelling"}:
            return self.run_result(run_id)
        run["cancel_requested"], run["status"] = True, "cancelling"
        process = run["process"]
        if process is not None and process.returncode is None:
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                process.stdin.write(b'{"cancel":true}\n')
                await process.stdin.drain()
        asyncio.create_task(self.cancel_deadline(run))
        return {"ok": True, "run_id": run_id, "status": "cancelling"}

    async def cancel_deadline(self, run):
        try:
            await asyncio.wait_for(asyncio.shield(run["task"]), 3)
        except asyncio.TimeoutError:
            process = run["process"]
            if process is not None and process.returncode is None:
                process.kill()

    async def close(self):
        self.stopping = True
        await self.skills.close()
        await self.environment.close()
        await self.updates.close()
        for run_id in list(self.runs):
            await self.cancel(run_id)
        await asyncio.gather(*(run["task"] for run in self.runs.values()), return_exceptions=True)

    async def handle(self, method, params):
        if self.app_update_pending and method != "shutdown":
            with use_language(self.language):
                raise ValueError(tr("App 正在准备更新，请等待重启。"))
        if method == "initialize":
            with use_language(self.language):
                self.language = resolve(params.get("lang", "zh"))
        if method == "language.set":
            if not self.initialized:
                raise ValueError(tr("请先完成协议版本握手。"))
            if self.environment.state["busy"] or self.skills.state["busy"] or self.updates.state["cli_update"]["status"] == "running":
                with use_language(self.language):
                    raise ValueError(tr("环境操作或 CLI 更新正在进行，请等待完成。"))
            with use_language(self.language):
                self.language = resolve(params.get("lang", "auto"))
            self.cli_info = None
            method = "get_state"
        with use_language(self.language):
            return render_messages(await self._handle(method, params), self.language)

    async def _handle(self, method, params):
        if self.skills.state["busy"] and method in {"profile.select", "language.set", "cli.update", "environment.install", "environment.prepare", "environment.check", "environment.verify", "skills.install", "app.update-prepare", "shutdown"}:
            raise ValueError(tr('Skills 操作正在进行，请等待完成。'))
        if method == "ping":
            return {"protocol_version": 1, "version": cli._get_version(), "generation": self.generation}
        if method == "initialize":
            if type(params.get("protocol_version")) is not int or params["protocol_version"] != PROTOCOL_VERSION:
                raise ValueError(tr('App 与后端协议版本不匹配，请安装完整的同版本 App。'))
            self.directory = absolute_directory(params["config_dir"]) if params.get("config_dir") else str(config.config_file.parent)
            self.initialized = True
            self.include_config_secrets = params.get("include_config_secrets") is True
            self.updates.current_version = str(params.get("app_version", cli._get_version()))
            self.updates.state["app"]["current_version"] = self.updates.current_version
            self.updates.enabled = params.get("enable_update_checks") is True
        if not self.initialized:
            raise ValueError(tr('请先完成协议版本握手。'))
        if method == "profile.select":
            if self.environment.state["busy"]:
                raise ValueError(tr('环境操作正在进行，请完成后再切换配置目录。'))
            self.directory = absolute_directory(params.get("config_dir"))
            self.cli_info = None
            self.environment.state.update(plan_id="", can_install=False, checked_at=0, steps=[], targets=[], plan=[],
                                          invocation="", config_dir=self.directory,
                                          message=tr('配置目录已切换，请重新检测环境与接入状态。'))
        with config.snapshot(directory=self.directory):
            if method in {"initialize", "profile.select", "get_state"}:
                if method == "get_state":
                    self.cli_info = None
                return self.state()
            if method == "config.preview":
                values = dict(params.get("set", {}))
                values.update({key: "" for key in params.get("unset", [])})
                return ui_api.preview({"values": values})
            if method == "config.apply":
                if not isinstance(params.get("revision"), str):
                    raise ValueError(tr('保存必须带上当前配置 revision。'))
                return ui_api.apply_config(params)
            if method in {"run.start", "provider.test", "skills.install"}:
                return self.start(method, params)
            if method == "run.result":
                return self.run_result(params.get("run_id"))
            if method == "run.cancel":
                return await self.cancel(params.get("run_id"))
            if method == "providers.reset":
                return ui_api.reset_health(params)
            if method == "skills.status":
                return ui_api.skills_status(params.get("targets"))
            if method in {"skills.catalog", "skills.check", "skills.sync", "skills.update", "skills.auto"}:
                if method == "skills.auto":
                    if type(params.get("enabled")) is not bool:
                        raise ValueError(tr('enabled 必须为布尔值。'))
                    self.skills.state["auto_check"] = params["enabled"]
                    self.skills.save()
                    self.skills.changed()
                    return self.skills.state
                if method in {"skills.catalog", "skills.check", "skills.sync", "skills.update"}:
                    if self.environment.state["busy"] or self.updates.state["cli_update"]["status"] == "running":
                        raise ValueError(tr('环境操作或 CLI 更新正在进行，请等待完成。'))
                    self.cli_info = None
                    info = self.cli_status()
                    await asyncio.to_thread(self.skills.snapshot, manager_environment(self.directory), info, self.directory)
                if method in {"skills.sync", "skills.update"}:
                    if any(run["command"] == "skills.install" and run["status"] in {"running", "cancelling"} for run in self.runs.values()):
                        raise ValueError(tr('Skills 操作正在进行，请等待完成。'))
                    return self.skills.update(params) if method == "skills.update" else self.skills.sync(params)
                return self.skills.check() if method == "skills.check" else self.skills.state
            if method == "activity.list":
                return self.activity(params)
            if method == "activity.details":
                directory = absolute_directory(params.get("config_dir", self.directory))
                run_id = str(params.get("run_id", ""))
                own_run = self.runs.get(run_id)
                try:
                    details = ActivityStore(directory).details(run_id)
                except (OSError, sqlite3.Error):
                    if own_run is None:
                        raise
                    details = {"ok": False}
                if not details["ok"] and own_run is not None and own_run["directory"] == directory:
                    return {"ok": True, "run": self.run_metadata(own_run), "events": [], "events_truncated": False,
                            "note": tr('这次任务的活动未持久记录，当前状态来自 App 自有进程。')}
                return details
            if method == "activity.clear":
                ActivityStore(self.directory).clear()
                for run in self.runs.values():
                    if run["directory"] == self.directory and run["status"] not in {"running", "cancelling"}:
                        run["history_cleared"] = True
                return {"ok": True}
            if method == "activity.enabled":
                if type(params.get("enabled")) is not bool:
                    raise ValueError(tr('enabled 必须为布尔值。'))
                ActivityStore(self.directory).set_enabled(params["enabled"])
                return {"ok": True, "enabled": params["enabled"]}
            if method == "cli.status":
                self.cli_info = None
                current = self.cli_status()
                self.updates.changed()
                return current
            if method == "environment.status":
                return self.environment.state
            if method in {"environment.check", "environment.verify", "environment.install", "environment.prepare"}:
                if self.updates.state["cli_update"]["status"] == "running":
                    raise ValueError(tr('CLI 正在更新，请等待完成。'))
                self.cli_info = None
                info = self.cli_status()
                env = manager_environment(self.directory)
                minimum_ok = bool(ui_api.state().get("minimum_profile", {}).get("ok"))
                if method not in {"environment.install", "environment.prepare"}:
                    return self.environment.start_check(env, info, self.directory, minimum_ok, verify=method == "environment.verify")
                if any(run["status"] in {"running", "cancelling"} for run in self.runs.values()) or any(
                    row.get("origin") == "cli" and row.get("status") in {"running", "cancelling"} for row in self.activity().get("runs", [])):
                    raise ValueError(tr('请先等待 App 和当前配置目录的 CLI 任务完成，再准备环境。'))
                def refresh_cli():
                    self.cli_info = None
                    current = self.cli_status()
                    self.updates.changed()
                    return current
                action = self.environment.prepare if method == "environment.prepare" else self.environment.install
                return action(params, env, info, self.directory, minimum_ok, refresh_cli)
            if method == "environment.cancel":
                return await self.environment.cancel()
            if method == "cli.update":
                return self.update_cli(params)
            if method == "cli.update-check":
                self.cli_info = None
                return self.updates.check(self.cli_status())
            if method == "updates.state":
                return self.updates.state
            if method == "updates.auto":
                if type(params.get("enabled")) is not bool:
                    raise ValueError(tr('enabled 必须为布尔值。'))
                self.updates.state["auto_check"] = params["enabled"]
                self.updates.save()
                self.updates.changed()
                return self.updates.state
            if method == "app.update-prepare":
                if self.environment.state["busy"]:
                    raise ValueError(tr('环境准备正在进行，请等待完成后再升级 App。'))
                if any(run["status"] in {"running", "cancelling"} for run in self.runs.values()):
                    raise ValueError(tr('请先等待或取消 App 自有任务，再启动安装。'))
                if self.updates.state["cli_update"]["status"] == "running":
                    raise ValueError(tr('CLI 正在更新，请等待结果。'))
                self.app_update_pending = True
                return {"ok": True}
            if method == "shutdown":
                if self.environment.state["busy"] and self.environment.state["status"] == "installing" and not self.environment.state["can_cancel"]:
                    raise ValueError(tr('正在写入独立运行环境，请保持 App 打开直到完成。'))
                await self.close()
                return {"ok": True}
        raise ValueError(tr('未知协议方法。'))


async def serve():
    def emit(data):
        print(json.dumps(data, ensure_ascii=False, separators=(",", ":")), flush=True)

    backend = Backend(emit)

    async def poll():
        while not backend.stopping:
            await asyncio.sleep(1)
            if backend.initialized and not backend.app_update_pending:
                backend.event("tick", {})
                backend.updates.auto_check(backend.cli_status())
                if backend.updates.enabled:
                    backend.skills.auto_check(manager_environment(backend.directory), backend.cli_status(), backend.directory)

    poller = asyncio.create_task(poll())
    try:
        while not backend.stopping:
            line = await asyncio.to_thread(sys.stdin.buffer.readline, MAX_LINE + 1)
            if not line:
                break
            identifier = None
            try:
                if len(line) > MAX_LINE:
                    raise ValueError(tr('请求超过允许长度。'))
                request = json.loads(line)
                if not isinstance(request, dict) or type(request.get("id")) is not int or request["id"] <= 0:
                    raise ValueError(tr('请求必须包含正整数 id。'))
                identifier = request["id"]
                params = request.get("params", {})
                if not isinstance(params, dict):
                    raise ValueError(tr('params 必须是对象。'))
                result = await backend.handle(request.get("method"), params)
                emit({"id": identifier, "generation": backend.generation, "result": result})
            except Exception as error:
                with use_language(backend.language):
                    message = sanitize_error_message(str(error)) if isinstance(error, ValueError) else tr("本地操作失败，请检查目录权限或重新启动 App。")
                emit({"id": identifier, "generation": backend.generation, "error": {"code": "parameter_error" if isinstance(error, ValueError) else "runtime_error", "message": message}})
                if len(line) > MAX_LINE:
                    break
    finally:
        poller.cancel()
        await backend.close()


def main():
    asyncio.run(serve())
    return 0
