"""Read official stable Skills as data; write Agent directories only on explicit sync."""
from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile
import time
import zlib

import httpx

from . import skill_installer as skills
from .desktop_environment import depends_on_app, metadata
from .desktop_updates import NPM_URL, PACKAGE, cache_directory, stable_version
from .i18n import tr

MAX_DOWNLOAD = 16 * 1024 * 1024


def unpack_skills(data: bytes, release: dict) -> dict[str, bytes]:
    integrity = release.get("integrity", "")
    if not isinstance(integrity, str) or not integrity.startswith("sha512-"):
        raise ValueError(tr('Skills 归档缺少 SHA512 完整性校验。'))
    expected = base64.b64decode(integrity[7:], validate=True)
    if len(expected) != 64 or hashlib.sha512(data).digest() != expected:
        raise ValueError(tr('Skills 归档完整性校验失败。'))
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
            unpacked = compressed.read(64 * 1024 * 1024 + 1)
    except (OSError, EOFError, zlib.error) as error:
        raise ValueError(tr('Skills 归档完整性校验失败。')) from error
    if len(unpacked) > 64 * 1024 * 1024:
        raise ValueError(tr('Skills 文件大小超限。'))
    files, manifest, size = {}, None, 0
    # Stream members and only keep Skill bytes; never extract or execute package code.
    with tarfile.open(fileobj=io.BytesIO(unpacked), mode="r|") as archive:
        for count, member in enumerate(archive, 1):
            path = PurePosixPath(member.name)
            size += member.size
            if (count > 10000 or size > 64 * 1024 * 1024 or member.size > 4 * 1024 * 1024
                    or member.size < 0 or not (member.isfile() or member.isdir())
                    or path.is_absolute() or ".." in path.parts or "\\" in member.name or ":" in member.name):
                raise ValueError(tr('Skills 归档包含不安全的路径、类型或大小。'))
            if member.isdir():
                continue
            if member.name == "package/package.json":
                if manifest is not None:
                    raise ValueError(tr('Skills 归档包含重复文件。'))
                manifest = json.loads(archive.extractfile(member).read())
            prefix = "package/skills/smart-search-cli/"
            if member.name.startswith(prefix):
                rel = member.name[len(prefix):]
                # Windows aliases (case, trailing dot/space, devices) must not collide.
                if (not rel or PurePosixPath(rel).as_posix() != rel or any(part.endswith((".", " ")) or part.split(".")[0].upper() in
                        {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}
                        for part in PurePosixPath(rel).parts)
                        or rel.casefold() in {name.casefold() for name in files}):
                    raise ValueError(tr('Skills 归档包含重复或无效文件名。'))
                files[rel] = archive.extractfile(member).read()
                if len(files) > 256 or sum(map(len, files.values())) > 2 * 1024 * 1024:
                    raise ValueError(tr('Skills 文件大小超限。'))
    if (not isinstance(manifest, dict) or manifest.get("name") != PACKAGE
            or manifest.get("version") != release["version"] or not files.get("SKILL.md")):
        raise ValueError(tr('Skills 归档与正式版包信息不一致。'))
    return files


async def fetch_skills(client) -> tuple[dict, bytes, dict[str, bytes]]:
    package = json.loads(await metadata(client, NPM_URL))
    version = package.get("version")
    if package.get("name") != PACKAGE or stable_version(version) is None:
        raise ValueError(tr('Skills 来源不是有效的官方稳定版本。'))
    url = f"https://registry.npmjs.org/{PACKAGE}/-/smart-search-{version}.tgz"
    dist = package.get("dist", {})
    if dist.get("tarball") != url:
        raise ValueError(tr('Skills 下载地址不是受信任的官方地址。'))
    release = {"version": version, "integrity": dist.get("integrity"), "url": url, "checked_at": time.time()}
    data = bytearray()
    async with client.stream("GET", url) as response:
        response.raise_for_status()  # Redirects are rejected, never followed.
        async for chunk in response.aiter_bytes(65536):
            data.extend(chunk)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError(tr('Skills 下载大小超限。'))
    files = await asyncio.to_thread(unpack_skills, bytes(data), release)
    return release, bytes(data), files


class Skills:
    def __init__(self, emit, environment, *, directory=None):
        self.emit, self.environment = emit, environment
        self.directory = Path(directory) if directory else cache_directory() / "skills"
        self.task = None
        self.files = None
        self.expected_files = None
        self.context = None
        self.state = {"auto_check": True, "last_attempt": 0, "checking": False, "busy": False,
                      "source": {}, "cached": True, "error": "", "targets": [], "plan_id": "", "can_sync": False,
                      "result": None}
        try:
            saved = json.loads((self.directory / "state.json").read_text(encoding="utf-8"))
            if type(saved.get("auto_check")) is bool:
                self.state["auto_check"] = saved["auto_check"]
            attempt = saved.get("last_attempt", 0)
            if type(attempt) in {int, float} and 0 <= attempt <= time.time():
                self.state["last_attempt"] = attempt
            source = saved.get("source", {})
            if stable_version(source.get("version")) is not None:
                archive = self.directory / (source["version"] + ".tgz")
                if archive.stat().st_size <= MAX_DOWNLOAD:
                    self.files = unpack_skills(archive.read_bytes(), source)
                    self.state["source"] = source
        except (OSError, ValueError, TypeError, AttributeError, tarfile.TarError):
            pass

    def save(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.directory / "state.json.tmp"
        temporary.write_text(json.dumps({k: self.state[k] for k in ("auto_check", "last_attempt", "source")}), encoding="utf-8")
        temporary.replace(self.directory / "state.json")

    def changed(self):
        self.emit("skills", self.state)

    def snapshot(self, env, info, config_dir):
        node = self.environment.probe_node(env)
        self.context = (dict(env), dict(info), config_dir, node)
        return self.refresh()

    def refresh(self):
        if not self.context:
            return self.state
        env, info, config_dir, node = self.context
        files = self.files or dict(skills._load_skill_files())
        independent = (info.get("external_runtime_verified") and info.get("manager") != "bundled"
                       and not depends_on_app(info.get("package_root")) and not depends_on_app(node.get("path")))
        invocation = self.environment.invocation(node, info) if independent else []
        self.expected_files = skills.with_invocation(files, invocation, config_dir)
        result = skills.status_skill_targets(list(skills.SKILL_TARGET_BY_ID), project_root=self.environment.home, files=self.expected_files, env=env)
        ready = bool(invocation)
        reason = "" if ready else tr('独立 CLI 尚未验证；可更新 Skills 内容，原有本机调用信息会保留。')
        fingerprint = {"source": result["bundled_hash"], "targets": [(t["path"], t["installed_hash"]) for t in result["targets"]]}
        self.state.update(targets=result["targets"], cli_version=info.get("external_version", ""), cli_ready=ready,
                          compatibility=reason, can_sync=bool(self.files and not self.state["cached"] and not self.state["error"]),
                          plan_id=hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest())
        return self.state

    def auto_check(self, env, info, config_dir):
        if self.state["auto_check"] and time.time() - self.state["last_attempt"] >= 86400:
            self.check((env, info, config_dir))

    def check(self, context=None):
        if self.state["busy"] or self.state["checking"]:
            return self.state
        self.state.update(checking=True, can_sync=False, cached=True, last_attempt=time.time(), error="")
        try:
            self.save()
        except OSError:
            self.state.update(checking=False, error=tr('Skills 检查或完整性校验失败；保留原文件，请重试。'))
            self.changed()
            return self.state
        self.task = asyncio.create_task(self._check(context))
        self.changed()
        return self.state

    async def _check(self, context=None):
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                source, data, files = await asyncio.wait_for(fetch_skills(client), 60)
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.directory / "download.tmp"
            temporary.write_bytes(data)
            temporary.replace(self.directory / (source["version"] + ".tgz"))
            self.files = files
            self.state.update(source=source, cached=False)
            if context:
                await asyncio.to_thread(self.snapshot, *context)
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError, AttributeError, tarfile.TarError, asyncio.TimeoutError):
            self.state.update(error=tr('Skills 检查或完整性校验失败；保留原文件，请重试。'), cached=True)
        finally:
            self.state["checking"] = False
            self.refresh()
            try:
                self.save()
            except OSError:
                self.state.update(can_sync=False, error=tr('Skills 检查或完整性校验失败；保留原文件，请重试。'))
            self.changed()

    @staticmethod
    def selected_targets(params):
        targets = params.get("targets")
        if (params.get("confirm") is not True or not isinstance(targets, list) or not targets
                or any(not isinstance(t, str) or t not in skills.SKILL_TARGET_BY_ID for t in targets)):
            raise ValueError(tr('请确认并选择有效的 Skills 目标。'))
        return list(dict.fromkeys(targets))

    def update(self, params):
        targets = self.selected_targets(params)
        if self.state["busy"] or self.state["checking"]:
            raise ValueError(tr('Skills 操作正在进行，请等待完成。'))
        self.refresh()
        before = {row["target"]: (row["path"], row["installed_hash"])
                  for row in self.state["targets"] if row["target"] in targets}
        self.state["result"] = None
        self.check()
        if self.state["checking"]:
            check_task = self.task
            self.state["busy"] = True
            self.task = asyncio.create_task(self._update_checked(check_task, targets, before))
            self.changed()
        return self.state

    async def _update_checked(self, check_task, targets, before):
        try:
            await check_task
            self.refresh()
            if not self.state["can_sync"]:
                return
            current = {row["target"]: (row["path"], row["installed_hash"])
                       for row in self.state["targets"] if row["target"] in targets}
            if current != before or len(current) != len(targets):
                raise ValueError(tr('所选 Skills 文件在检查期间发生变化，请重试。'))
            await self._sync(targets, dict(self.expected_files), self.context[0])
        except ValueError as error:
            self.state["error"] = str(error)
        finally:
            self.state["busy"] = False
            self.changed()

    def sync(self, params):
        if self.state["busy"] or self.state["checking"]:
            raise ValueError(tr('Skills 操作正在进行，请等待完成。'))
        self.refresh()
        targets = self.selected_targets(params)
        if not self.state["can_sync"] or params.get("plan_id") != self.state["plan_id"]:
            raise ValueError(tr('Skills 来源或本机状态已变化，请重新检查后确认更新。'))
        env = self.context[0]
        files = dict(self.expected_files)
        self.state.update(busy=True, result=None)
        self.task = asyncio.create_task(self._sync(targets, files, env))
        self.changed()
        return self.state

    async def _sync(self, targets, files, env):
        installed, failed = [], []
        try:
            for target in targets:
                try:
                    dest = skills.target_path(target, self.environment.home, env)
                    row = next(row for row in self.state["targets"] if row["target"] == target)
                    if row["status"] in {"up_to_date", "extra_files"}:
                        installed.append({"target": target, "path": str(dest), "changed_files": 0, "backup": ""})
                        continue
                    receipt = await asyncio.to_thread(skills.write_skill_files, dest, files,
                                                     self.directory / "backups", backup_prefix=target + "-")
                    installed.append({"target": target, "path": str(dest), **receipt})
                except (OSError, ValueError) as error:
                    failed.append({"target": target, "error": str(error)})
            self.state["result"] = {"ok": not failed, "installed": installed, "failed": failed}
        finally:
            self.state["busy"] = False
            self.refresh()
            self.changed()

    async def close(self):
        if self.task and not self.task.done():
            if self.state["checking"]:
                self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
