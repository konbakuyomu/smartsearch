"""User-owned npm environment. Nothing installed here depends on the App bundle."""
from __future__ import annotations
from .i18n import tr

import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import time
from urllib.parse import urlsplit
import uuid
import zipfile

import httpx

from . import desktop_cli, skill_installer
from .desktop_updates import NPM_URL, PACKAGE, platform_target, stable_version, verified_file
from .provider_errors import sanitize_provider_error_message

TARGETS = {"codex": "Codex", "claude": "Claude Code"}
MAX_ARCHIVE = 256 * 1024 * 1024


def depends_on_app(path):
    if not path or not getattr(sys, "frozen", False):
        return False
    backend = Path(sys.executable).resolve().parent
    app = next((parent for parent in backend.parents if parent.suffix == ".app"),
               backend.parent if backend.name == "backend" else backend)
    return Path(path).resolve().is_relative_to(app)


def read_command(argv, env, timeout=8):
    result = subprocess.run(argv, env=env, cwd=Path.home(), stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise ValueError(tr('程序检查未通过。'))
    return result.stdout.strip()


def actual_command(name, env):
    entry = shutil.which(name, path=env.get("PATH", ""))
    if entry and Path(entry).parent.name == "shims" and "mise" in entry.lower():
        mise = shutil.which("mise", path=env.get("PATH", ""))
        if not mise:
            return None
        entry = read_command([mise, "which", name], env)
    # Windows Store aliases can install on first invocation; detection must not.
    if not entry or "windowsapps" in str(entry).lower() or not Path(entry).is_file():
        return None
    return str(Path(entry).resolve())


def installer_environment(env, base):
    # Do not give package lifecycle scripts provider credentials or arbitrary tokens.
    allowed = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "HOME", "USERPROFILE", "APPDATA",
               "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "TEMP", "TMP", "TMPDIR", "LANG",
               "LC_ALL", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY", "SSL_CERT_FILE", "SMART_SEARCH_CONFIG_DIR"}
    clean = {key: value for key, value in env.items() if key.upper() in allowed}
    clean.update(PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1", PIP_CONFIG_FILE=os.devnull,
                 PIP_INDEX_URL="https://pypi.org/simple", PIP_DISABLE_PIP_VERSION_CHECK="1",
                 UV_NO_CONFIG="1", UV_PYTHON_INSTALL_DIR=str(base / "python"), UV_CACHE_DIR=str(base / "cache/uv"),
                 UV_PYTHON_BIN_DIR=str(base / "bin"), UV_NO_PROGRESS="1", NO_COLOR="1", SMART_SEARCH_ACTIVITY_ENABLED="false",
                 npm_config_userconfig=str(base / "npm-user.config"), npm_config_globalconfig=str(base / "npm-global.config"),
                 npm_config_cache=str(base / "cache/npm"), npm_config_registry="https://registry.npmjs.org")
    return clean


def cli_runtime_commands(root, python):
    private = root / ".smart-search-python"
    executable = private / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return ([python, "-m", "venv", str(private)],
            [str(executable), "-m", "pip", "install", "--disable-pip-version-check", str(root)])


def command_text(argv):
    if os.name == "nt":
        return "& " + " ".join("'" + str(arg).replace("'", "''") + "'" for arg in argv)
    return shlex.join(argv)


def trusted_url(url, redirected=False):
    parsed = urlsplit(str(url))
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in {None, 443} or parsed.fragment:
        return False
    if parsed.hostname == "nodejs.org":
        return parsed.path.startswith("/dist/")
    if parsed.hostname == "github.com":
        return parsed.path.startswith("/astral-sh/uv/releases/download/")
    return redirected and parsed.hostname in {"release-assets.githubusercontent.com", "objects.githubusercontent.com"}


async def asset_response(client, url, method="GET"):
    for hop in range(6):
        if not trusted_url(url, hop > 0):
            raise ValueError(tr('运行环境下载地址不受信任。'))
        response = await client.send(client.build_request(method, url), stream=True)
        if response.is_redirect:
            url = str(response.url.join(response.headers.get("location", "")))
            await response.aclose()
            continue
        response.raise_for_status()
        return response
    raise ValueError(tr('下载跳转次数过多。'))


async def metadata(client, url):
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        data = bytearray()
        async for chunk in response.aiter_bytes():
            data.extend(chunk)
            if len(data) > 4 * 1024 * 1024:
                raise ValueError(tr('发行信息过大。'))
        return bytes(data)


def extract_archive(archive, destination):
    """Validate the whole archive before extracting into a fresh owned directory."""
    def check(name, size):
        path = PurePosixPath(name.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or ":" in name or size < 0:
            raise ValueError(tr('归档包含越界路径。'))
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            if len(entries) > 50000 or sum(item.file_size for item in entries) > 2 * 1024**3:
                raise ValueError(tr('归档解压大小超限。'))
            for item in entries:
                check(item.filename, item.file_size)
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError(tr('ZIP 中的链接不受支持。'))
            package.extractall(destination)
    else:
        with tarfile.open(archive, "r:gz") as package:
            entries = package.getmembers()
            if len(entries) > 50000 or sum(item.size for item in entries) > 2 * 1024**3:
                raise ValueError(tr('归档解压大小超限。'))
            for item in entries:
                check(item.name, item.size)
                if not (item.isfile() or item.isdir() or item.issym() or item.islnk()):
                    raise ValueError(tr('归档包含特殊设备文件。'))
                if item.issym() or item.islnk():
                    # npm's relative links stay inside the extracted tree.
                    resolved = (destination / item.name).parent / item.linkname if item.issym() else destination / item.linkname
                    if not resolved.resolve().is_relative_to(destination.resolve()):
                        raise ValueError(tr('归档链接越界。'))
            if not hasattr(tarfile, "data_filter"):
                raise ValueError(tr('当前 App 后端不支持安全解压，请更新 App。'))
            package.extractall(destination, filter="data")


class Environment:
    def __init__(self, emit, *, directory=None, home=None):
        self.emit = emit
        self.directory = Path(directory) if directory else desktop_cli.tools_directory()
        self.home = Path(home) if home else Path.home()
        self.task = None
        self.state = {"status": "idle", "busy": False, "can_cancel": False, "message": tr('先检测环境，查看需要准备的组件。'),
                      "steps": [], "targets": [], "plan": [], "plan_id": "", "checked_at": 0, "error": ""}

    def changed(self, **values):
        self.state.update(values)
        self.emit("environment", self.state)

    def saved(self):
        try:
            data = json.loads((self.directory / "environment.json").read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self, **values):
        saved = {**self.saved(), **values}
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.directory / "environment.json.tmp"
        temporary.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.directory / "environment.json")

    def probe_node(self, env):
        candidates = [self.saved().get("node")]
        with contextlib.suppress(OSError, ValueError, subprocess.TimeoutExpired):
            candidates.append(actual_command("node", env))
        for entry in dict.fromkeys(candidates):
            if not entry:
                continue
            try:
                node = Path(entry)
                data = json.loads(read_command([str(node), "-p", "JSON.stringify({version:process.version,path:process.execPath,arch:process.arch})"], env))
                version = stable_version(data["version"])
                node = Path(data["path"])
                if depends_on_app(node):
                    continue
                npm = node.parent / ("node_modules/npm/bin/npm-cli.js" if os.name == "nt" else "../lib/node_modules/npm/bin/npm-cli.js")
                if version is None or version < (18, 0, 0) or not npm.is_file():
                    continue
                npm_version = read_command([str(node), str(npm.resolve()), "--version"], env)
                return {"ready": True, "path": str(node), "npm": str(npm.resolve()), "version": data["version"], "npm_version": npm_version}
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                continue
        return {"ready": False, "message": tr('未找到兼容且可运行的 Node/npm；将准备独立用户环境。')}

    def probe_python(self, env):
        candidates = [self.saved().get("python")]
        for name in ("python3", "python"):
            with contextlib.suppress(OSError, ValueError, subprocess.TimeoutExpired):
                candidates.append(actual_command(name, env))
        if os.name == "nt":
            candidates.extend(str(path) for path in (self.home / "AppData/Local/Programs/Python").glob("Python*/python.exe"))
        else:
            candidates.extend(str(path) for path in Path("/Library/Frameworks/Python.framework/Versions").glob("3.*/bin/python3"))
        probe = "import json,sys,venv,ensurepip; print(json.dumps({'version':list(sys.version_info[:3]),'path':sys.executable,'base':sys.base_prefix,'prefix':sys.prefix}))"
        for entry in dict.fromkeys(candidates):
            if not entry:
                continue
            try:
                data = json.loads(read_command([entry, "-I", "-B", "-c", probe], env))
                if tuple(data["version"]) < (3, 10, 0) or data["prefix"] != data["base"]:
                    continue
                if depends_on_app(data["path"]):
                    continue
                return {"ready": True, "path": data["path"], "version": ".".join(map(str, data["version"]))}
            except (OSError, ValueError, KeyError, subprocess.TimeoutExpired):
                continue
        return {"ready": False, "message": tr('未找到支持 venv/pip 的独立 Python；将准备 Astral CPython。')}

    def invocation(self, node, info):
        root = info.get("package_root")
        if node.get("ready") and root:
            return [node["path"], str(Path(root) / "npm/bin/smart-search.js")]
        return []

    def skill_files(self, node, info, config_dir):
        source = Path(info["package_root"]) / "skills/smart-search-cli" if info.get("package_root") else None
        files = dict(skill_installer._load_skill_files(source if source and source.is_dir() else None))
        return skill_installer.with_invocation(files, self.invocation(node, info), config_dir)

    def target_path(self, target, env):
        return skill_installer.target_path(target, self.home, env)

    def target_status(self, target, files, env):
        dest = self.target_path(target, env)
        row = skill_installer._describe_installed_skill(dest, source_by_path=files,
                                                       bundled_digest=skill_installer._skill_digest(list(files.items())))
        row.update(target=target, label=TARGETS[target], application=tr('未发现可运行命令；可能未安装或不在当前环境中'), application_ready=False)
        row["action"] = "review" if row["stale_files"] else "install" if row["missing_files"] else "none"
        try:
            entry = actual_command("claude" if target == "claude" else "codex", env)
            if entry:
                argv = [entry]
                if Path(entry).suffix.lower() in {".cmd", ".bat", ".ps1"}:
                    module = "@openai/codex/bin/codex.js" if target == "codex" else "@anthropic-ai/claude-code/cli.js"
                    script = Path(entry).parent / "node_modules" / module
                    node = actual_command("node", env)
                    argv = [node, str(script)] if node and script.is_file() else []
                if argv:
                    version = read_command([*argv, "--version"], env)
                    row.update(application=tr('已发现可运行命令：') + version[:120], application_ready=True)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            row["application"] = tr('命令检查未通过；请检查安装或重新打开 App。')
        legacy = self.home / ".codex/skills/smart-search-cli"
        if target == "codex" and legacy.exists():
            row["legacy_path"] = str(legacy)
        return row

    def inspect(self, env, cli_info, config_dir, minimum_ok):
        node, python = self.probe_node(env), self.probe_python(env)
        files = self.skill_files(node, cli_info, config_dir)
        targets = [self.target_status(target, files, env) for target in TARGETS]
        installed = bool(cli_info.get("package_root"))
        cli_ready = bool(cli_info.get("external_runtime_verified")) and cli_info.get("manager") != "bundled"
        blocked = ""
        if cli_info.get("external_path") and not cli_ready:
            if cli_info.get("manager") == "bundled":
                blocked = tr('当前同名命令指向 App 内置引擎。请先移除该旧入口，再准备独立 CLI。')
            elif not cli_info.get("can_update") or not stable_version(cli_info.get("external_version")):
                blocked = cli_info.get("update_note") or tr('CLI 来源无法确认，请先处理已有安装。')
        if cli_info.get("other_paths"):
            blocked = tr('检测到多个同名 CLI，请先明确保留的安装后重新检测。')
        if cli_info.get("external_path") and cli_info.get("manager") == "unknown":
            blocked = tr('CLI 属于未知来源或项目环境，请使用原环境处理后重新检测；不会另装副本覆盖。')
        if depends_on_app(cli_info.get("package_root")) or depends_on_app(cli_info.get("external_path")):
            cli_ready = False
            blocked = tr('当前 CLI 位于 App 程序目录，不能作为独立安装；请先处理旧入口后重新检测。')
        if platform_target()[0] == "unsupported":
            blocked = tr('自动准备目前支持 Windows 和 macOS。')
        plan = []
        if not node["ready"]:
            plan.append(tr('安装 Node.js LTS 和 npm（当前用户独立目录）'))
        if not python["ready"]:
            plan.append(tr('安装 Python（Astral CPython，当前用户独立目录）'))
        if not cli_ready:
            plan.append(tr('修复原来源 Smart Search CLI') if installed else tr('安装 npm 稳定版 Smart Search CLI（独立目录）'))
        if cli_info.get("managed_tools") and os.name == "nt" and not self.command_entry_ready():
            plan.append(tr('配置独立命令入口（补充当前用户 PATH）'))
        steps = [{"name": tr('运行环境'), "status": "ready" if node["ready"] and python["ready"] else "missing",
                  "status_label": tr('已就绪') if node["ready"] and python["ready"] else tr('待安装'),
                  "message": tr('Node/npm 与 Python 可用') if node["ready"] and python["ready"] else tr('将自动补齐缺少或不兼容的组件')},
                 {"name": tr('独立 CLI'), "status": "ready" if cli_ready else "missing", "status_label": tr('可运行') if cli_ready else tr('待安装或修复'),
                  "message": tr('本地引擎可运行；点击验证重新检查可用性') if cli_ready else tr('尚未通过本地运行检查')},
                 {"name": tr('搜索配置'), "status": "ready" if minimum_ok else "pending", "status_label": tr('已配置') if minimum_ok else tr('待配置'),
                  "message": tr('App 当前配置满足最低要求；AI 所处环境与服务连通性仍需验证') if minimum_ok else tr('请填写服务商 Key；这一步不需要安装软件')},
                 {"name": tr('AI 内实际调用'), "status": "pending", "status_label": tr('待验证'),
                  "message": tr('把测试指引粘贴到 Agent 中执行；这一步不需要安装软件')}]
        fingerprint = {"node": node, "python": python, "cli": {k: cli_info.get(k) for k in
                       ("external_path", "resolved_path", "external_version", "manager", "can_update", "external_runtime_verified")},
                       "skills": [(t["target"], t["installed_hash"], t["path"]) for t in targets], "plan": plan, "config_dir": config_dir}
        plan_id = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
        return {"node": node, "python": python, "cli": cli_info, "targets": targets, "steps": steps,
                "plan": plan, "plan_id": plan_id, "blocked": blocked, "can_install": not blocked,
                "checked_at": time.time(), "config_dir": config_dir, "tools_dir": str(self.directory),
                "independent": cli_ready, "invocation": command_text(self.invocation(node, cli_info)) if installed else "",
                "message": blocked or tr('检测完成。可按清单准备共用独立 CLI。')}

    def command_entry_ready(self):
        if os.name != "nt":
            return True  # macOS uses the verified absolute invocation in the skill.
        import winreg
        prefix = self.directory / "cli"
        if not (prefix / "node.exe").is_file():
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, "Path")
            return any(Path(os.path.expandvars(part)).resolve() == prefix.resolve() for part in value.split(";") if part)
        except OSError:
            return False

    def start_check(self, env, cli_info, config_dir, minimum_ok, *, verify=False):
        if self.state["busy"]:
            return self.state
        self.changed(status="checking", operation="verify" if verify else "check", busy=True, can_cancel=False, error="", message=tr('正在验证可用性…') if verify else tr('正在检测环境…'))
        self.task = asyncio.create_task(self._check(env, cli_info, config_dir, minimum_ok, verify))
        return self.state

    async def _check(self, env, cli_info, config_dir, minimum_ok, verify):
        try:
            result = await asyncio.to_thread(self.inspect, env, cli_info, config_dir, minimum_ok)
            if verify and result["independent"] and result["node"]["ready"]:
                # Older npm wrappers repair on invocation. Read-only verification must
                # never run them, even if a runtime disappears after discovery.
                private_python = Path(cli_info["package_root"]) / ".smart-search-python" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
                argv = [str(private_python), "-m", "smart_search.cli"]
                clean = installer_environment(env, self.directory)
                clean["SMART_SEARCH_CONFIG_DIR"] = config_dir
                output = await asyncio.to_thread(read_command, [*argv, "--version"], clean)
                if output != "smart-search " + str(cli_info.get("external_version")):
                    raise ValueError(tr('独立 CLI 完整启动链的版本读回不一致。'))
                result["steps"][1].update(status="ready", message=tr('独立 CLI 引擎与 Node 运行检查通过；未触发自动修复'))
                result["message"] = tr('本机验证完成；AI 内实际调用仍待验证。')
            self.changed(**result, status="ready", busy=False)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            self.changed(status="failed", busy=False, error=sanitize_provider_error_message(str(error)), message=tr('检查未完成，请重新检测。'))

    def install(self, params, env, cli_info, config_dir, minimum_ok, refresh_cli):
        if self.state["busy"]:
            return self.state
        targets = params.get("targets", [])
        if params.get("confirm") is not True or not isinstance(targets, list) or any(t not in TARGETS for t in targets):
            raise ValueError(tr('请明确确认安装计划并选择有效的 AI 目标。'))
        if not self.state.get("can_install") or not params.get("plan_id") or params["plan_id"] != self.state["plan_id"]:
            raise ValueError(tr('请先检测环境并确认当前安装计划。'))
        replace = params.get("replace_modified", False)
        if type(replace) is not bool:
            raise ValueError(tr('replace_modified 必须是布尔值。'))
        self.changed(status="installing", operation="install", busy=True, can_cancel=False, error="", message=tr('正在复核安装计划…'), log="")
        self.task = asyncio.create_task(self._install(params["plan_id"], list(dict.fromkeys(targets)), replace,
                                                     env, cli_info, config_dir, minimum_ok, refresh_cli))
        return self.state

    def prepare(self, params, env, cli_info, config_dir, minimum_ok, refresh_cli):
        if params.get("confirm") is not True:
            raise ValueError(tr('请点击安装或修复 CLI 后重试。'))
        if self.state["busy"]:
            return self.state
        self.changed(status="installing", operation="install", busy=True, can_cancel=False,
                     error="", message=tr('正在准备 CLI…'), log="")
        self.task = asyncio.create_task(self._prepare(env, cli_info, config_dir, minimum_ok, refresh_cli))
        return self.state

    async def _prepare(self, env, cli_info, config_dir, minimum_ok, refresh_cli):
        try:
            current = await asyncio.to_thread(self.inspect, env, cli_info, config_dir, minimum_ok)
            if current["blocked"]:
                raise ValueError(current["blocked"])
            await self._install(current["plan_id"], [], False, env, cli_info, config_dir, minimum_ok, refresh_cli)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            message = sanitize_provider_error_message(str(error))
            self.changed(status="failed", busy=False, can_cancel=False, error=message, message=message)

    async def run(self, argv, env):
        process = await asyncio.create_subprocess_exec(*argv, cwd=self.directory, env=env,
            stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        async def consume():
            tail = ""
            while chunk := await process.stdout.read(4096):
                tail = sanitize_provider_error_message((tail + chunk.decode("utf-8", errors="replace"))[-12000:], limit=12000)
                self.changed(log=tail)
            await process.wait()
            return tail
        try:
            output = await asyncio.wait_for(consume(), 1200)
        except BaseException:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        if process.returncode:
            raise ValueError(tr('安装程序未成功完成。已完成的组件保留，请查看详情并重新检测。'))
        return output.strip()

    async def download(self, client, asset):
        if not 0 < asset["size"] <= MAX_ARCHIVE or not re.fullmatch("[0-9a-f]{64}", asset["sha256"]):
            raise ValueError(tr('运行环境的大小或校验信息无效。'))
        target = self.directory / "cache" / asset["name"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if not await asyncio.to_thread(verified_file, target, asset):
            self.changed(can_cancel=True, message=tr('正在下载 ') + asset["name"], received=0, total=asset["size"])
            response = await asset_response(client, asset["url"])
            partial = target.with_suffix(target.suffix + ".part")
            try:
                digest, received, notice, started = hashlib.sha256(), 0, 0, time.monotonic()
                with partial.open("wb") as stream:
                    async for chunk in response.aiter_bytes(65536):
                        received += len(chunk)
                        if received > asset["size"] or time.monotonic() - started > 1800:
                            raise ValueError(tr('下载大小不符或超过时限。'))
                        stream.write(chunk)
                        digest.update(chunk)
                        if time.monotonic() - notice > .3:
                            self.changed(received=received)
                            notice = time.monotonic()
                if received != asset["size"] or digest.hexdigest() != asset["sha256"]:
                    raise ValueError(tr('运行环境 SHA256 或大小校验失败；未执行安装。'))
                partial.replace(target)
            finally:
                await response.aclose()
                partial.unlink(missing_ok=True)
        self.changed(can_cancel=False, received=0, total=0, message=tr('正在解压已校验的运行环境…'))
        dest = self.directory / "runtimes" / uuid.uuid4().hex
        dest.mkdir(parents=True)
        await asyncio.to_thread(extract_archive, target, dest)
        return dest

    async def install_node(self, client, env):
        releases = json.loads(await metadata(client, "https://nodejs.org/dist/index.json"))
        releases = [r for r in releases if r.get("lts") and stable_version(r.get("version")) and stable_version(r["version"]) >= (22, 0, 0)]
        release = max(releases, key=lambda r: stable_version(r["version"]))
        system, arch = platform_target()
        arch = "x64" if arch == "x86_64" else arch
        version = release["version"]
        name = f"node-{version}-{'win' if system == 'windows' else 'darwin'}-{arch}.{'zip' if system == 'windows' else 'tar.gz'}"
        base = f"https://nodejs.org/dist/{version}/"
        sums = (await metadata(client, base + "SHASUMS256.txt")).decode()
        matches = re.findall(r"^([0-9a-f]{64})\s+" + re.escape(name) + r"\s*$", sums, re.M)
        if len(matches) != 1:
            raise ValueError(tr('Node 发行版缺少目标平台校验信息。'))
        response = await asset_response(client, base + name, "HEAD")
        try:
            size = int(response.headers.get("content-length", "0"))
        finally:
            await response.aclose()
        dest = await self.download(client, {"name": name, "url": base + name, "sha256": matches[0], "size": size})
        node = dest / name.removesuffix(".zip").removesuffix(".tar.gz") / ("node.exe" if system == "windows" else "bin/node")
        self.save(node=str(node))
        result = await asyncio.to_thread(self.probe_node, env)
        if not result["ready"] or result["version"] != version:
            raise ValueError(tr('新安装的 Node/npm 未通过运行验证。'))
        self.save(node=result["path"], npm=result["npm"])
        return result

    async def install_python(self, client, env):
        release = json.loads(await metadata(client, "https://api.github.com/repos/astral-sh/uv/releases/latest"))
        if release.get("draft") or release.get("prerelease") or stable_version(release.get("tag_name")) is None:
            raise ValueError(tr('Python 安装辅助工具的稳定发行信息无效。'))
        system, arch = platform_target()
        triple = ("aarch64" if arch == "arm64" else "x86_64") + ("-pc-windows-msvc.zip" if system == "windows" else "-apple-darwin.tar.gz")
        name = "uv-" + triple
        assets = [a for a in release["assets"] if a.get("name") == name]
        if len(assets) != 1 or not re.fullmatch(r"sha256:[0-9a-f]{64}", assets[0].get("digest") or ""):
            raise ValueError(tr('Python 安装辅助工具缺少目标平台校验信息。'))
        asset = assets[0]
        dest = await self.download(client, {"name": release["tag_name"] + "-" + name, "url": asset["browser_download_url"],
                                          "size": asset["size"], "sha256": asset["digest"][7:]})
        executables = list(dest.rglob("uv.exe" if system == "windows" else "uv"))
        if len(executables) != 1:
            raise ValueError(tr('Python 安装辅助工具结构无效。'))
        uv = str(executables[0])
        self.changed(message=tr('正在准备独立 Python（Astral CPython）…'), can_cancel=False)
        await self.run([uv, "python", "install", "3.13", "--no-bin", "--no-registry", "--no-config"], env)
        python = await asyncio.to_thread(read_command, [uv, "python", "find", "3.13", "--managed-python", "--no-python-downloads", "--no-project", "--no-config"], env)
        path = Path(python)
        if not path.is_file() or not path.resolve().is_relative_to((self.directory / "python").resolve()):
            raise ValueError(tr('Python 安装位置未通过独立目录验证。'))
        self.save(python=str(path))
        result = await asyncio.to_thread(self.probe_python, env)
        if not result["ready"] or Path(result["path"]).resolve() != path.resolve():
            raise ValueError(tr('新 Python 缺少 venv/pip 支持。'))
        return result

    async def install_skills(self, targets, replace, node, info, env, config_dir):
        files = self.skill_files(node, info, config_dir)
        messages = []
        for target in targets:
            dest = self.target_path(target, env)
            if dest.is_symlink() or any((dest / rel).is_symlink() or not (dest / rel).resolve().is_relative_to(dest.resolve()) for rel in files):
                messages.append(TARGETS[target] + tr(' 技能包含链接，请手动核对，未覆盖。'))
                continue
            status = skill_installer._describe_installed_skill(dest, source_by_path=files,
                                                              bundled_digest=skill_installer._skill_digest(list(files.items())))
            if status["status"] == "error":
                raise ValueError(TARGETS[target] + tr(' 接入目录不可写。'))
            if status["stale_files"] and not replace:
                messages.append(TARGETS[target] + tr(' 接入内容不同，已保留；需要替换时勾选备份并替换。'))
                continue
            new_parent = not dest.parent.exists()
            receipt = skill_installer.write_skill_files(dest, files, self.directory / "skill-backups", backup_prefix=target + "-")
            if receipt["backup"]:
                messages.append(TARGETS[target] + tr(' 原接入已备份到 ') + receipt["backup"])
            if new_parent:
                messages.append(TARGETS[target] + tr(' 新建了技能目录，请重新打开 AI。'))
        return messages

    def expose_cli(self, node, info):
        if not info.get("managed_tools"):
            return tr('使用已验证的独立 CLI 完整路径；接入文件已提供调用方式。')
        prefix = self.directory / "cli"
        if os.name == "nt":
            # npm's Windows shim prefers a sibling node.exe. This keeps the command
            # usable even when an incompatible Node precedes our additions in PATH.
            source, launcher = Path(node["path"]), prefix / "node.exe"
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if launcher.exists() and hashlib.sha256(launcher.read_bytes()).hexdigest() != digest:
                previous = self.saved().get("launcher_node_sha256")
                if hashlib.sha256(launcher.read_bytes()).hexdigest() != previous:
                    raise ValueError(tr('独立 CLI 目录已有不同的 Node，请核对后重新检测；未覆盖。'))
                launcher.unlink()
            if not launcher.exists():
                try:
                    os.link(source, launcher)
                except OSError:
                    shutil.copy2(source, launcher)
            self.save(launcher_node_sha256=digest)
            import ctypes
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                try:
                    current, kind = winreg.QueryValueEx(key, "Path")
                except FileNotFoundError:
                    current, kind = "", winreg.REG_EXPAND_SZ
                parts = current.split(";") if current else []
                known = {part.rstrip("\\/").casefold() for part in parts}
                if str(prefix).rstrip("\\/").casefold() not in known:
                    parts.append(str(prefix))
                winreg.SetValueEx(key, "Path", 0, kind, ";".join(parts))
            result = ctypes.c_size_t()
            notify = ctypes.windll.user32.SendMessageTimeoutW
            notify.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_wchar_p,
                               ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_size_t)]
            notify.restype = ctypes.c_ssize_t
            notify(0xFFFF, 0x1A, 0, "Environment", 2, 1000, ctypes.byref(result))
            return tr('独立命令已加入用户 PATH。请重新打开 AI/终端；已打开进程不会自动获得新环境。')
        return tr('独立 CLI 已安装；macOS 图形 App 的 PATH 可能不同，接入文件使用完整路径。')

    async def _install(self, plan_id, targets, replace, env, cli_info, config_dir, minimum_ok, refresh_cli):
        try:
            current = await asyncio.to_thread(self.inspect, env, cli_info, config_dir, minimum_ok)
            if current["plan_id"] != plan_id or current["blocked"]:
                raise ValueError(tr('安装来源或接入文件已变化，请重试。'))
            if depends_on_app(self.directory):
                raise ValueError(tr('运行环境目录必须独立于 App 程序目录。'))
            self.directory.mkdir(parents=True, exist_ok=True)
            clean = installer_environment(env, self.directory)
            clean["SMART_SEARCH_CONFIG_DIR"] = config_dir
            node, python = current["node"], current["python"]
            async with httpx.AsyncClient(timeout=30, follow_redirects=False, headers={"User-Agent": "SmartSearch-Environment"}) as client:
                if not node["ready"]:
                    node = await self.install_node(client, clean)
                if not python["ready"]:
                    python = await self.install_python(client, clean)
                self.save(node=node["path"], npm=node["npm"], python=python["path"])
                clean["PATH"] = os.pathsep.join([str(Path(node["path"]).parent), str(Path(python["path"]).parent), clean.get("PATH", "")])
                clean["SMART_SEARCH_PYTHON"] = python["path"]
                if not current["independent"]:
                    if cli_info.get("package_root"):
                        self.changed(message=tr('正在修复独立 CLI 私有环境；保留原 npm/mise 安装与版本…'))
                    else:
                        version = json.loads(await metadata(client, NPM_URL))["version"]
                        if stable_version(version) is None:
                            raise ValueError(tr('npm 稳定版本无效。'))
                        self.changed(message=tr('正在安装独立 Smart Search CLI ') + version + "…", can_cancel=False)
                        # Also supports older published packages without explicit Python selection.
                        # Reproduce their two-step postinstall using the interpreter just verified.
                        await self.run([node["path"], node["npm"], "install", "--global", "--prefix", str(self.directory / "cli"),
                                        "--ignore-scripts", "--no-audit", "--no-fund", f"{PACKAGE}@{version}"], clean)
                        cli_info = desktop_cli.managed_cli_info(clean, self.directory)
                        if not cli_info:
                            raise ValueError(tr('独立 npm 包安装位置未通过验证。'))
                    root = Path(cli_info["package_root"])
                    for command in cli_runtime_commands(root, python["path"]):
                        await self.run(command, clean)
            self.changed(message=tr('正在验证独立 CLI 启动链…'), can_cancel=False)
            cli_info = await asyncio.to_thread(refresh_cli)
            if not cli_info.get("external_runtime_verified") or cli_info.get("manager") == "bundled":
                raise ValueError(tr('独立 CLI 的实际运行验证未通过，请重试。'))
            output = await asyncio.to_thread(read_command, [*self.invocation(node, cli_info), "--version"], clean)
            if output != "smart-search " + str(cli_info.get("external_version")):
                raise ValueError(tr('独立 CLI 的版本读回不一致。'))
            if targets:
                self.changed(message=tr('正在配置所选 AI 接入…'))
            notes = await self.install_skills(targets, replace, node, cli_info, env, config_dir)
            notes.append(self.expose_cli(node, cli_info))
            result = await asyncio.to_thread(self.inspect, env, cli_info, config_dir, minimum_ok)
            pending = any(row["status"] not in {"up_to_date", "extra_files"} for row in result["targets"] if row["target"] in targets)
            result["message"] = (tr('独立 CLI 已就绪；部分接入需要处理。') if pending else tr('环境与所选接入已准备好；AI 内实际调用待验证。')) + "\n" + "\n".join(notes)
            if not targets:
                result["message"] = tr('独立 CLI 已就绪。') + "\n" + "\n".join(notes)
            result["steps"][1]["message"] = tr('独立 CLI 完整启动链已通过本地验证')
            self.changed(**result, status="ready", busy=False, can_cancel=False)
        except asyncio.CancelledError:
            self.changed(status="cancelled", busy=False, can_cancel=False, plan_id="", message=tr('下载已取消，已安装组件保留；可重试。'))
        except Exception as error:
            message = sanitize_provider_error_message(str(error)) if isinstance(error, ValueError) else tr('网络或安装操作未完成，请重试。')
            self.changed(status="failed", busy=False, can_cancel=False, plan_id="", error=message, message=message)

    async def cancel(self):
        if self.task and not self.task.done() and self.state["can_cancel"]:
            self.changed(message=tr('正在取消下载…'), can_cancel=False)
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        return self.state

    async def close(self):
        if self.task and not self.task.done():
            if self.state["status"] == "checking" or self.state["can_cancel"]:
                self.task.cancel()
            # Do not kill a package manager mid-write when the UI disconnects.
            await asyncio.gather(self.task, return_exceptions=True)
