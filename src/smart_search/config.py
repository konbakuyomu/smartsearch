from .i18n import tr
import json
import math
import os
import sys
import hashlib
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from .state_files import file_lock
from .jev import JEV_DEFAULTS, JevSettings, validate_jev_value
from .intent_router import ALLOWED_INTENT_ROUTER_MODES, normalize_router_mode

_snapshot = ContextVar("smart_search_config_snapshot", default=None)

class Config:
    _instance = None
    _SETUP_COMMAND = (
        "Run `smart-search setup`, or configure XAI_API_KEY and/or "
        "OPENAI_COMPATIBLE_API_URL plus OPENAI_COMPATIBLE_API_KEY, then run "
        "`smart-search doctor --format json`."
    )
    _DEFAULT_MODEL = "grok-4-fast"
    _DEFAULT_XAI_TOOLS = "web_search,x_search"
    _DEFAULT_OPENAI_COMPATIBLE_API_MODE = "chat-completions"
    _DEFAULT_VALIDATION_LEVEL = "balanced"
    _DEFAULT_FALLBACK_MODE = "auto"
    _DEFAULT_MINIMUM_PROFILE = "standard"
    _DEFAULT_INTENT_ROUTER_MODE = "jev"
    _DEFAULT_INTENT_ROUTER_TIMEOUT_SECONDS = "8"
    _DEFAULT_SEARCH_TIMEOUT_SECONDS = "300"
    _DEFAULT_PROVIDER_COOLDOWN_SECONDS = "900"
    _DEFAULT_PROVIDER_FAILURE_THRESHOLD = "2"
    _DEFAULT_INTENT_EMBEDDING_THRESHOLD = "0.74"
    _DEFAULT_INTENT_EMBEDDING_MARGIN = "0.05"
    _ALLOWED_XAI_TOOLS = {"web_search", "x_search"}
    _ALLOWED_XAI_REASONING_EFFORTS = {"low", "medium", "high"}
    _ALLOWED_OPENAI_COMPATIBLE_API_MODES = {"chat-completions", "responses"}
    _ALLOWED_VALIDATION_LEVELS = {"fast", "balanced", "strict"}
    _ALLOWED_FALLBACK_MODES = {"auto", "off"}
    _ALLOWED_MINIMUM_PROFILES = {"standard", "off"}
    _ALLOWED_INTENT_ROUTER_MODES = ALLOWED_INTENT_ROUTER_MODES
    RETIRED_ROUTER_KEYS = {
        "INTENT_EMBEDDING_API_URL", "INTENT_EMBEDDING_API_KEY", "INTENT_EMBEDDING_MODEL",
        "INTENT_EMBEDDING_THRESHOLD", "INTENT_EMBEDDING_MARGIN",
        "INTENT_CLASSIFIER_API_URL", "INTENT_CLASSIFIER_API_KEY", "INTENT_CLASSIFIER_MODEL",
        "INTENT_ROUTER_TIMEOUT_SECONDS",
    }
    PROVIDER_ENABLED_KEYS: dict[str, str] = {
        "xai-responses": "XAI_ENABLED",
        "openai-compatible": "OPENAI_COMPATIBLE_ENABLED",
        "context7": "CONTEXT7_ENABLED",
        "exa": "EXA_ENABLED",
        "zhipu": "ZHIPU_ENABLED",
        "zhipu-mcp": "ZHIPU_MCP_ENABLED",
        "zhipu-mcp-reader": "ZHIPU_MCP_READER_ENABLED",
        "tavily": "TAVILY_ENABLED",
        "firecrawl": "FIRECRAWL_ENABLED",
        "tinyfish": "TINYFISH_ENABLED",
        "deepseek": "DEEPSEEK_ENABLED",
        "jina": "JINA_ENABLED",
        "anysearch": "ANYSEARCH_ENABLED",
        "sciverse": "SCIVERSE_ENABLED",
    }
    _CONFIG_KEYS = {
        "SMART_SEARCH_LANGUAGE",
        "XAI_API_URL",
        "XAI_API_KEY",
        "XAI_MODEL",
        "XAI_TOOLS",
        "XAI_REASONING_EFFORT",
        "XAI_STREAM",
        "OPENAI_COMPATIBLE_API_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_FALLBACK_MODELS",
        "OPENAI_COMPATIBLE_API_MODE",
        "OPENAI_COMPATIBLE_STREAM",
        "SMART_SEARCH_VALIDATION_LEVEL",
        "SMART_SEARCH_FALLBACK_MODE",
        "SMART_SEARCH_MINIMUM_PROFILE",
        "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS",
        "SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS",
        "SMART_SEARCH_INTENT_ROUTER",
        "SMART_SEARCH_TIMEOUT_SECONDS",
        "SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS",
        "SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD",
        "INTENT_EMBEDDING_API_URL",
        "INTENT_EMBEDDING_API_KEY",
        "INTENT_EMBEDDING_MODEL",
        "INTENT_EMBEDDING_THRESHOLD",
        "INTENT_EMBEDDING_MARGIN",
        "INTENT_CLASSIFIER_API_URL",
        "INTENT_CLASSIFIER_API_KEY",
        "INTENT_CLASSIFIER_MODEL",
        "INTENT_ROUTER_TIMEOUT_SECONDS",
        "EXA_API_KEY",
        "EXA_BASE_URL",
        "EXA_TIMEOUT_SECONDS",
        "CONTEXT7_API_KEY",
        "CONTEXT7_BASE_URL",
        "CONTEXT7_TIMEOUT_SECONDS",
        "ZHIPU_API_KEY",
        "ZHIPU_API_URL",
        "ZHIPU_SEARCH_ENGINE",
        "ZHIPU_TIMEOUT_SECONDS",
        "ZHIPU_MCP_API_KEY",
        "ZHIPU_MCP_SEARCH_API_URL",
        "ZHIPU_MCP_READER_API_URL",
        "ZHIPU_MCP_ZREAD_API_URL",
        "ZHIPU_MCP_TIMEOUT_SECONDS",
        "JINA_API_KEY",
        "JINA_READER_API_URL",
        "JINA_RESPOND_WITH",
        "JINA_TIMEOUT_SECONDS",
        "TAVILY_API_KEY",
        "TAVILY_API_URL",
        "TAVILY_ENABLED",
        "TAVILY_TIMEOUT_SECONDS",
        "FIRECRAWL_API_KEY",
        "FIRECRAWL_API_URL",
        "TINYFISH_API_KEY",
        "TINYFISH_SEARCH_API_URL",
        "TINYFISH_FETCH_API_URL",
        "TINYFISH_TIMEOUT_SECONDS",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_API_URL",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "ANYSEARCH_API_KEY",
        "ANYSEARCH_API_URL",
        "ANYSEARCH_TIMEOUT_SECONDS",
        "SCIVERSE_API_TOKEN",
        "SCIVERSE_API_URL",
        "SCIVERSE_TIMEOUT_SECONDS",
        "SMART_SEARCH_DEBUG",
        "SMART_SEARCH_LOG_LEVEL",
        "SMART_SEARCH_LOG_DIR",
        "SMART_SEARCH_RETRY_MAX_ATTEMPTS",
        "SMART_SEARCH_RETRY_MULTIPLIER",
        "SMART_SEARCH_RETRY_MAX_WAIT",
        "SMART_SEARCH_OUTPUT_CLEANUP",
        "SMART_SEARCH_LOG_TO_FILE",
        "SSL_VERIFY",
    }
    _CONFIG_KEYS.update(JEV_DEFAULTS)
    _CONFIG_KEYS.update(PROVIDER_ENABLED_KEYS.values())
    _LEGACY_CONFIG_KEYS: dict[str, str] = {}
    # Writing any of these invalidates the resolved-model cache.
    _MODEL_CACHE_KEYS = frozenset({
        "XAI_API_URL",
        "XAI_API_KEY",
        "XAI_ENABLED",
        "XAI_MODEL",
        "XAI_TOOLS",
        "XAI_REASONING_EFFORT",
        "XAI_STREAM",
        "OPENAI_COMPATIBLE_API_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_ENABLED",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_FALLBACK_MODELS",
        "OPENAI_COMPATIBLE_API_MODE",
        "OPENAI_COMPATIBLE_STREAM",
        "SMART_SEARCH_VALIDATION_LEVEL",
        "SMART_SEARCH_FALLBACK_MODE",
        "SMART_SEARCH_MINIMUM_PROFILE",
        "SMART_SEARCH_INTENT_ROUTER",
    })
    # Keys validated on write. The four original entries validate unconditionally;
    # the rest skip an empty value, which every getter already reads as "unset".
    _PLAIN_FLOAT_KEYS = frozenset({
        "INTENT_ROUTER_TIMEOUT_SECONDS",
        "SMART_SEARCH_RETRY_MULTIPLIER",
        "EXA_TIMEOUT_SECONDS",
        "CONTEXT7_TIMEOUT_SECONDS",
        "ZHIPU_TIMEOUT_SECONDS",
        "ZHIPU_MCP_TIMEOUT_SECONDS",
        "JINA_TIMEOUT_SECONDS",
        "TAVILY_TIMEOUT_SECONDS",
        "ANYSEARCH_TIMEOUT_SECONDS",
        "SCIVERSE_TIMEOUT_SECONDS",
    })
    _PLAIN_INT_KEYS = frozenset({
        "SMART_SEARCH_RETRY_MAX_ATTEMPTS",
        "SMART_SEARCH_RETRY_MAX_WAIT",
    })
    _UNIT_INTERVAL_KEYS = frozenset({
        "INTENT_EMBEDDING_THRESHOLD",
        "INTENT_EMBEDDING_MARGIN",
    })

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config_file = None
            cls._instance._config_dir_source = None
            cls._instance._cached_model = None
        return cls._instance

    @staticmethod
    def _default_config_dir() -> Path:
        if sys.platform.startswith("win"):
            local_appdata = os.getenv("LOCALAPPDATA")
            if local_appdata:
                return Path(local_appdata).expanduser() / "smart-search"
        return Path.home() / ".config" / "smart-search"

    @staticmethod
    def _legacy_windows_config_dir() -> Path:
        return Path.home() / ".config" / "smart-search"

    @staticmethod
    def _config_dir_override_value() -> str:
        return os.getenv("SMART_SEARCH_CONFIG_DIR") or ""

    @staticmethod
    def _same_config_dir(left: Path, right: Path) -> bool:
        left_text = os.path.abspath(os.path.expanduser(str(left)))
        right_text = os.path.abspath(os.path.expanduser(str(right)))
        if sys.platform.startswith("win"):
            left_text = left_text.replace("/", "\\").rstrip("\\").lower()
            right_text = right_text.replace("/", "\\").rstrip("\\").lower()
        else:
            left_text = left_text.rstrip("/")
            right_text = right_text.rstrip("/")
        return left_text == right_text

    @classmethod
    def _config_dir_override_matches_default(cls) -> bool:
        env_dir = cls._config_dir_override_value()
        if not env_dir:
            return False
        return cls._same_config_dir(Path(env_dir).expanduser(), cls._default_config_dir())

    @staticmethod
    def _resolve_config_dir() -> tuple[Path, str]:
        env_dir = os.getenv("SMART_SEARCH_CONFIG_DIR")
        if env_dir:
            return Path(env_dir).expanduser(), "environment"
        default_dir = Config._default_config_dir()
        if sys.platform.startswith("win"):
            legacy_dir = Config._legacy_windows_config_dir()
            if legacy_dir != default_dir and not (default_dir / "config.json").exists() and (legacy_dir / "config.json").exists():
                return legacy_dir, "legacy_windows_home"
        return default_dir, "default"

    @staticmethod
    def _safe_mkdir(p: Path) -> bool:
        try:
            p.mkdir(parents=True, exist_ok=True)
            return True
        except (PermissionError, OSError):
            return False

    @property
    def config_file(self) -> Path:
        snapshot = _snapshot.get()
        if snapshot is not None:
            return snapshot["path"]
        if self._config_file is None:
            config_dir, config_dir_source = self._resolve_config_dir()
            ok = self._safe_mkdir(config_dir)
            if config_dir_source == "default" and not ok:
                cwd_dir = Path.cwd() / ".smart-search"
                if self._safe_mkdir(cwd_dir):
                    config_dir = cwd_dir
                    config_dir_source = "cwd_fallback"
            self._config_file = config_dir / "config.json"
            self._config_dir_source = config_dir_source
        return self._config_file

    @property
    def config_dir_source(self) -> str:
        snapshot = _snapshot.get()
        if snapshot is not None:
            return snapshot["source"]
        if self._config_file is None:
            _ = self.config_file
        return self._config_dir_source or "override"

    def _load_config_file(self, *, strict: bool = False) -> dict:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    if strict:
                        raise ValueError(tr('配置文件不是 JSON 对象；请先修复，原文件未修改。'))
                    return {}
                return data
        except FileNotFoundError:
            return {}
        except (OSError, UnicodeError, json.JSONDecodeError):
            if strict:
                raise ValueError(tr('无法读取有效配置；请检查文件和权限，原文件未修改。')) from None
            return {}

    def revision(self) -> str:
        try:
            raw = self.config_file.read_bytes()
        except FileNotFoundError:
            raw = b""
        return hashlib.sha256(raw).hexdigest()

    def snapshot_revision(self) -> str:
        snapshot = _snapshot.get()
        if snapshot is not None and snapshot.get("revision") is not None:
            return snapshot["revision"]
        return self.revision()

    def effective_values(self, masked: bool = True) -> dict[str, str]:
        snapshot = _snapshot.get()
        if snapshot is not None:
            values = dict(snapshot["values"])
        else:
            values = self.get_saved_config(masked=False)
            values.update({key: os.environ[key] for key in self._CONFIG_KEYS if key in os.environ})
        mode = values.get("SMART_SEARCH_INTENT_ROUTER", "").strip().lower()
        if mode in self._ALLOWED_INTENT_ROUTER_MODES:
            values["SMART_SEARCH_INTENT_ROUTER"] = normalize_router_mode(mode)
        return {key: self._mask_if_secret(key, value) for key, value in values.items()} if masked else values

    @contextmanager
    def snapshot(self, values: dict[str, str] | None = None, *, merge: bool = True, directory: str = "",
                 source_overrides: dict[str, str] | None = None):
        """Freeze one invocation without changing process-wide environment variables."""
        previous = _snapshot.get()
        if directory:
            path = Path(directory).expanduser()
            if not path.is_absolute():
                raise ValueError(tr('配置目录必须是绝对路径。'))
            path = path / "config.json"
            source = self.config_dir_source if self._config_file is not None and path == self._config_file else "override"
        else:
            path, source = self.config_file, self.config_dir_source
        if previous is not None and not directory:
            resolved, sources = dict(previous["values"]), dict(previous["sources"])
            revision = previous.get("revision")
            saved = dict(previous.get("saved", {}))
        else:
            # Values and optimistic revision must describe the very same bytes.
            # Read atomically replaced files once; read-only profiles need no lock file.
            try:
                raw = path.read_bytes()
            except FileNotFoundError:
                raw = b""
            except OSError:
                raw = None
            try:
                data = json.loads(raw or b"{}")
            except (ValueError, UnicodeError):
                data = {}
            saved = self.get_saved_config(masked=False, data=data if isinstance(data, dict) else {})
            revision = hashlib.sha256(raw).hexdigest() if raw is not None else None
            resolved = dict(saved)
            resolved.update({key: os.environ[key] for key in self._CONFIG_KEYS if key in os.environ})
            sources = {key: "environment" if key in os.environ else "config_file" if key in saved else "default"
                       for key in self._CONFIG_KEYS}
        if not merge:
            resolved = {}
        resolved.update({key: str(value) for key, value in (values or {}).items()})
        if source_overrides is not None:
            sources = {key: source_overrides.get(key, "default") for key in self._CONFIG_KEYS}
        token = _snapshot.set({"path": path, "source": source, "values": resolved, "sources": sources,
                               "revision": revision, "saved": saved})
        try:
            yield
        finally:
            _snapshot.reset(token)

    def secret_values(self) -> tuple[str, ...]:
        return tuple(value for key, value in self.effective_values(masked=False).items()
                     if value and any(part in key for part in ("KEY", "TOKEN", "SECRET")))

    def _save_config_file(self, config_data: dict) -> None:
        """Write config.json atomically.

        A truncating in-place write can leave an empty or half-written file if the
        process dies mid-save, and an empty config.json silently means "no API keys
        configured". Write a private temp file and rename it over the target instead,
        the same way ``provider_health._save`` already does.
        """
        path = self.config_file
        temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        try:
            # A temp file left behind by a crash would make O_EXCL fail forever.
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
            # O_EXCL refuses to follow a planted symlink; 0o600 means the file
            # holding API keys is never world-readable, not even momentarily.
            fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                handle = os.fdopen(fd, "w", encoding="utf-8")
            except BaseException:
                os.close(fd)
                raise
            with handle as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except (IOError, PermissionError, OSError, TypeError, ValueError) as e:
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            hint = tr(' (sandbox/CI 下可设 SMART_SEARCH_CONFIG_DIR 指向可写目录)') if isinstance(e, PermissionError) else ""
            raise ValueError(tr('无法保存配置文件: {0}{1}', str(e), hint))

    def _get_config_value(self, key: str, default: str | None = None) -> str | None:
        snapshot = _snapshot.get()
        if snapshot is not None:
            return snapshot["values"].get(key, default)
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value

        data = self._load_config_file()
        value = data.get(key)
        if value is None:
            legacy_key = next((old for old, new in self._LEGACY_CONFIG_KEYS.items() if new == key), None)
            if legacy_key:
                value = data.get(legacy_key)
        if value is None:
            return default
        return str(value)

    def get_saved_config(self, masked: bool = True, *, data: dict | None = None) -> dict:
        if data is None:
            snapshot = _snapshot.get()
            if snapshot is not None and "saved" in snapshot:
                normalized = dict(snapshot["saved"])
                return {key: self._mask_if_secret(key, value) for key, value in normalized.items()} if masked else normalized
            data = self._load_config_file()
        normalized: dict[str, str] = {}
        for old_key, new_key in self._LEGACY_CONFIG_KEYS.items():
            if old_key in data and new_key not in data:
                normalized[new_key] = str(data[old_key])
        for key, value in data.items():
            if key in self._CONFIG_KEYS and value is not None:
                normalized[key] = str(value)
        if not masked:
            return normalized
        return {key: self._mask_if_secret(key, value) for key, value in normalized.items()}

    def get_config_source(self, key: str) -> str:
        snapshot = _snapshot.get()
        if snapshot is not None:
            return snapshot["sources"].get(key, "default")
        if os.getenv(key) is not None:
            return "environment"
        data = self._load_config_file()
        if key in data:
            return "config_file"
        legacy_key = next((old for old, new in self._LEGACY_CONFIG_KEYS.items() if new == key), None)
        if legacy_key and legacy_key in data:
            return "config_file"
        return "default"

    def get_config_sources(self) -> dict[str, str]:
        return {key: self.get_config_source(key) for key in sorted(self._CONFIG_KEYS)}

    def update_config_values(
        self,
        set_values: dict[str, str] | None = None,
        unset_keys: list[str] | None = None,
        *,
        expected_revision: str | None = None,
    ) -> dict:
        """Apply many config changes in one validated, atomic write.

        All-or-nothing: a single rejected key or value leaves the file untouched, so
        a typo in one field cannot strand half a provider profile on disk. One read
        and one atomic rename replace the per-key read-modify-write cycle, which the
        setup wizard used to repeat once for every value it saved.
        """
        normalized_set: dict[str, str] = {}
        normalized_unset: list[str] = []
        errors: list[dict] = []

        for raw_key, raw_value in (set_values or {}).items():
            key = str(raw_key).strip().upper()
            if key not in self._CONFIG_KEYS:
                errors.append({"key": key, "error": tr('Unsupported config key: {0}', key)})
                continue
            value = "" if raw_value is None else str(raw_value)
            if key == "XAI_REASONING_EFFORT":
                value = value.strip().lower()
            try:
                self._validate_config_value(key, value)
            except ValueError as e:
                errors.append({"key": key, "error": str(e)})
                continue
            normalized_set[key] = value

        for raw_key in (unset_keys or []):
            key = str(raw_key).strip().upper()
            if key not in self._CONFIG_KEYS:
                errors.append({"key": key, "error": tr('Unsupported config key: {0}', key)})
                continue
            normalized_unset.append(key)

        if errors:
            return {"ok": False, "errors": errors, "saved": [], "unset": []}

        try:
            with file_lock(self.config_file):
                if expected_revision is not None and expected_revision != self.revision():
                    return {"ok": False, "errors": [{"key": "config", "error": tr('配置已被其他进程修改，请刷新后重试。')}],
                            "saved": [], "unset": [], "conflict": True}
                config_data = self._load_config_file(strict=True)
                for key, value in normalized_set.items():
                    config_data[key] = value
                for key in normalized_unset:
                    config_data.pop(key, None)
                    for old_key, new_key in self._LEGACY_CONFIG_KEYS.items():
                        if new_key == key:
                            config_data.pop(old_key, None)
                self._save_config_file(config_data)
        except OSError:
            raise ValueError(tr('无法锁定或保存配置文件，请检查权限或稍后重试。')) from None

        if (set(normalized_set) | set(normalized_unset)) & self._MODEL_CACHE_KEYS:
            self._cached_model = None
        return {
            "ok": True,
            "errors": [],
            "saved": sorted(normalized_set),
            "unset": sorted(normalized_unset),
        }

    def set_config_value(self, key: str, value: str) -> None:
        result = self.update_config_values({key: value})
        if not result["ok"]:
            raise ValueError(result["errors"][0]["error"])

    def unset_config_value(self, key: str) -> None:
        result = self.update_config_values(unset_keys=[key])
        if not result["ok"]:
            raise ValueError(result["errors"][0]["error"])

    def config_path_info(self) -> dict:
        return {
            "ok": True,
            "config_file": str(self.config_file),
            "config_dir": str(self.config_file.parent),
            "config_dir_source": self.config_dir_source,
            "default_config_file": str(self._default_config_dir() / "config.json"),
            "legacy_windows_config_file": str(self._legacy_windows_config_dir() / "config.json") if sys.platform.startswith("win") else "",
            "legacy_windows_config_exists": (self._legacy_windows_config_dir() / "config.json").exists() if sys.platform.startswith("win") else False,
            "config_dir_override_value": self._config_dir_override_value(),
            "config_dir_override_matches_default": self._config_dir_override_matches_default(),
            "exists": self.config_file.exists(),
        }

    @property
    def debug_enabled(self) -> bool:
        return (self._get_config_value("SMART_SEARCH_DEBUG", "false") or "false").lower() in ("true", "1", "yes")

    @property
    def retry_max_attempts(self) -> int:
        return int(self._get_config_value("SMART_SEARCH_RETRY_MAX_ATTEMPTS", "3") or "3")

    @property
    def retry_multiplier(self) -> float:
        return float(self._get_config_value("SMART_SEARCH_RETRY_MULTIPLIER", "1") or "1")

    @property
    def retry_max_wait(self) -> int:
        return int(self._get_config_value("SMART_SEARCH_RETRY_MAX_WAIT", "10") or "10")

    @property
    def xai_api_url(self) -> str:
        return self._get_config_value("XAI_API_URL", "https://api.x.ai/v1") or "https://api.x.ai/v1"

    @property
    def xai_api_key(self) -> str | None:
        return self._get_config_value("XAI_API_KEY")

    @property
    def xai_model(self) -> str:
        return self._get_config_value("XAI_MODEL") or self._base_model_value()

    @property
    def xai_tools_raw(self) -> str:
        return self._get_config_value("XAI_TOOLS", self._DEFAULT_XAI_TOOLS) or self._DEFAULT_XAI_TOOLS

    @property
    def xai_reasoning_effort(self) -> str:
        value = (self._get_config_value("XAI_REASONING_EFFORT", "") or "").strip().lower()
        return self._validate_enum_value("XAI_REASONING_EFFORT", value, self._ALLOWED_XAI_REASONING_EFFORTS) if value else ""

    @property
    def xai_stream(self) -> bool:
        return (self._get_config_value("XAI_STREAM", "false") or "false").lower() in ("true", "1", "yes")

    @property
    def openai_compatible_api_url(self) -> str | None:
        return self._get_config_value("OPENAI_COMPATIBLE_API_URL")

    @property
    def openai_compatible_api_key(self) -> str | None:
        return self._get_config_value("OPENAI_COMPATIBLE_API_KEY")

    @property
    def openai_compatible_model(self) -> str:
        model = self._get_config_value("OPENAI_COMPATIBLE_MODEL") or self._base_model_value()
        return self.apply_model_suffix_for_url(model, self.openai_compatible_api_url or "")

    @property
    def openai_compatible_fallback_models(self) -> list[str]:
        raw = self._get_config_value("OPENAI_COMPATIBLE_FALLBACK_MODELS", "") or ""
        models: list[str] = []
        seen: set[str] = set()
        api_url = self.openai_compatible_api_url or ""
        primary = self.openai_compatible_model
        for item in raw.split(","):
            model = item.strip()
            if not model:
                continue
            model = self.apply_model_suffix_for_url(model, api_url)
            if model == primary or model in seen:
                continue
            seen.add(model)
            models.append(model)
        return models

    @property
    def openai_compatible_api_mode(self) -> str:
        return self._validated_enum(
            "OPENAI_COMPATIBLE_API_MODE",
            self._DEFAULT_OPENAI_COMPATIBLE_API_MODE,
            self._ALLOWED_OPENAI_COMPATIBLE_API_MODES,
        )

    @property
    def openai_compatible_stream(self) -> bool:
        return (self._get_config_value("OPENAI_COMPATIBLE_STREAM", "false") or "false").lower() in ("true", "1", "yes")

    def parse_xai_tools(self, raw: str | None = None) -> list[str]:
        raw = raw or self.xai_tools_raw
        tools: list[str] = []
        invalid: list[str] = []
        seen: set[str] = set()
        for item in raw.split(","):
            tool = item.strip().lower()
            if not tool:
                continue
            if tool not in self._ALLOWED_XAI_TOOLS:
                invalid.append(tool)
                continue
            if tool not in seen:
                seen.add(tool)
                tools.append(tool)
        if invalid:
            allowed = ", ".join(sorted(self._ALLOWED_XAI_TOOLS))
            invalid_text = ", ".join(invalid)
            raise ValueError(tr('Invalid XAI_TOOLS: {0}. Supported values: {1}', invalid_text, allowed))
        return tools

    def _validated_enum(self, key: str, default: str, allowed: set[str]) -> str:
        return self._validate_enum_value(key, self._get_config_value(key, default) or default, allowed)

    @staticmethod
    def _validate_enum_value(key: str, raw_value: object, allowed: set[str]) -> str:
        value = str(raw_value or "").strip().lower()
        if value not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(tr('Invalid {0}: {1}. Supported values: {2}', key, value, allowed_text))
        return value

    def _enum_info(self, key: str, default: str, allowed: set[str]) -> tuple[str, str]:
        value = (self._get_config_value(key, default) or default).strip().lower()
        if value not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            return value, f"Invalid {key}: {value}. Supported values: {allowed_text}"
        return value, ""

    def _float_value(self, key: str, default: str) -> float:
        value = self._get_config_value(key, default) or default
        try:
            return float(value)
        except (TypeError, ValueError):
            raise ValueError(tr('Invalid {0}: {1}. Expected a number.', key, value))

    def _float_info(self, key: str, default: str) -> tuple[float, str]:
        try:
            return self._float_value(key, default), ""
        except ValueError as e:
            return float(default), str(e)

    def _bounded_float_value(self, key: str, default: str, minimum: float, maximum: float) -> float:
        value = self._float_value(key, default)
        if value < minimum or value > maximum:
            raise ValueError(tr('Invalid {0}: {1}. Expected a number between {2:g} and {3:g}.', key, value, minimum, maximum))
        return value

    def _positive_float_value(self, key: str, default: str) -> float:
        value = self._get_config_value(key, default) or default
        return self._parse_positive_float_value(key, value)

    @staticmethod
    def _parse_positive_float_value(key: str, raw_value: object) -> float:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(tr('Invalid {0}: {1}. Expected a positive finite number.', key, raw_value))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(tr('Invalid {0}: {1}. Expected a positive finite number.', key, raw_value))
        return value

    def _validate_config_value(self, key: str, value: str) -> None:
        """Reject a bad value at write time instead of at the next read.

        Without this, ``config set SMART_SEARCH_VALIDATION_LEVEL bogus`` succeeds and
        only blows up on the next search, far from the mistake.
        """
        if key == "SMART_SEARCH_LANGUAGE":
            from .i18n import normalize
            normalize(value)
            return
        if key in JEV_DEFAULTS:
            validate_jev_value(key, value)
            return
        if key in {"SMART_SEARCH_TIMEOUT_SECONDS", "TINYFISH_TIMEOUT_SECONDS", "DEEPSEEK_TIMEOUT_SECONDS"}:
            self._parse_positive_float_value(key, value)
            return
        if key == "SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS":
            self._parse_non_negative_float_value(key, value)
            return
        if key == "SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD":
            self._parse_positive_int_value(key, value)
            return
        if key == "OPENAI_COMPATIBLE_API_MODE":
            self._validate_enum_value(key, value, self._ALLOWED_OPENAI_COMPATIBLE_API_MODES)
            return
        if key == "XAI_TOOLS":
            self.parse_xai_tools(value or self._DEFAULT_XAI_TOOLS)
            return
        # Every getter below falls back to its default on an empty value, so an
        # empty string is how a key is cleared rather than a value to check.
        if not str(value).strip():
            return
        if key in self.PROVIDER_ENABLED_KEYS.values():
            self._validate_enum_value(key, value, {"true", "false", "1", "0", "yes", "no", "on", "off"})
            return
        enum_allowed = {
            "XAI_REASONING_EFFORT": self._ALLOWED_XAI_REASONING_EFFORTS,
            "SMART_SEARCH_VALIDATION_LEVEL": self._ALLOWED_VALIDATION_LEVELS,
            "SMART_SEARCH_FALLBACK_MODE": self._ALLOWED_FALLBACK_MODES,
            "SMART_SEARCH_MINIMUM_PROFILE": self._ALLOWED_MINIMUM_PROFILES,
            "SMART_SEARCH_INTENT_ROUTER": self._ALLOWED_INTENT_ROUTER_MODES,
        }.get(key)
        if enum_allowed is not None:
            self._validate_enum_value(key, value, enum_allowed)
        elif key in self._UNIT_INTERVAL_KEYS:
            parsed = self._parse_plain_float_value(key, value)
            if parsed < 0.0 or parsed > 1.0:
                raise ValueError(tr('Invalid {0}: {1}. Expected a number between 0 and 1.', key, value))
        elif key in self._PLAIN_FLOAT_KEYS:
            self._parse_plain_float_value(key, value)
        elif key in self._PLAIN_INT_KEYS:
            self._parse_plain_int_value(key, value)

    @staticmethod
    def _parse_plain_float_value(key: str, raw_value: object) -> float:
        try:
            value = float(str(raw_value).strip())
        except (TypeError, ValueError):
            raise ValueError(tr('Invalid {0}: {1}. Expected a number.', key, raw_value))
        if not math.isfinite(value):
            raise ValueError(tr('Invalid {0}: {1}. Expected a number.', key, raw_value))
        return value

    @staticmethod
    def _parse_plain_int_value(key: str, raw_value: object) -> int:
        try:
            return int(str(raw_value).strip())
        except (TypeError, ValueError):
            raise ValueError(tr('Invalid {0}: {1}. Expected an integer.', key, raw_value))

    def _non_negative_float_value(self, key: str, default: str) -> float:
        value = self._get_config_value(key, default) or default
        return self._parse_non_negative_float_value(key, value)

    @staticmethod
    def _parse_non_negative_float_value(key: str, raw_value: object) -> float:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(tr('Invalid {0}: {1}. Expected a non-negative finite number.', key, raw_value))
        if not math.isfinite(value) or value < 0:
            raise ValueError(tr('Invalid {0}: {1}. Expected a non-negative finite number.', key, raw_value))
        return value

    def _non_negative_float_info(self, key: str, default: str) -> tuple[float, str]:
        try:
            return self._non_negative_float_value(key, default), ""
        except ValueError as e:
            return float(default), str(e)

    def _positive_int_value(self, key: str, default: str) -> int:
        value = self._get_config_value(key, default) or default
        return self._parse_positive_int_value(key, value)

    @staticmethod
    def _parse_positive_int_value(key: str, raw_value: object) -> int:
        try:
            value = int(str(raw_value).strip())
        except (TypeError, ValueError):
            raise ValueError(tr('Invalid {0}: {1}. Expected a positive integer.', key, raw_value))
        if value < 1:
            raise ValueError(tr('Invalid {0}: {1}. Expected a positive integer.', key, raw_value))
        return value

    def _positive_int_info(self, key: str, default: str) -> tuple[int, str]:
        try:
            return self._positive_int_value(key, default), ""
        except ValueError as e:
            return int(default), str(e)

    def _positive_float_info(self, key: str, default: str) -> tuple[float, str]:
        try:
            return self._positive_float_value(key, default), ""
        except ValueError as e:
            return float(default), str(e)

    def _bounded_float_info(self, key: str, default: str, minimum: float, maximum: float) -> tuple[float, str]:
        try:
            return self._bounded_float_value(key, default, minimum, maximum), ""
        except ValueError as e:
            return float(default), str(e)

    @property
    def validation_level(self) -> str:
        return self._validated_enum(
            "SMART_SEARCH_VALIDATION_LEVEL",
            self._DEFAULT_VALIDATION_LEVEL,
            self._ALLOWED_VALIDATION_LEVELS,
        )

    @property
    def fallback_mode(self) -> str:
        return self._validated_enum(
            "SMART_SEARCH_FALLBACK_MODE",
            self._DEFAULT_FALLBACK_MODE,
            self._ALLOWED_FALLBACK_MODES,
        )

    @property
    def minimum_profile(self) -> str:
        return self._validated_enum(
            "SMART_SEARCH_MINIMUM_PROFILE",
            self._DEFAULT_MINIMUM_PROFILE,
            self._ALLOWED_MINIMUM_PROFILES,
        )

    @property
    def intent_router_mode(self) -> str:
        return normalize_router_mode(self._validated_enum(
            "SMART_SEARCH_INTENT_ROUTER",
            self._DEFAULT_INTENT_ROUTER_MODE,
            self._ALLOWED_INTENT_ROUTER_MODES,
        ))

    def jev_settings(self) -> JevSettings:
        return JevSettings.from_config(self)

    @property
    def search_timeout(self) -> float:
        return self._positive_float_value("SMART_SEARCH_TIMEOUT_SECONDS", self._DEFAULT_SEARCH_TIMEOUT_SECONDS)

    @property
    def search_timeout_or_default(self) -> float:
        """Search budget for callers that must not raise on an invalid saved value.

        `search` validates the budget up front and reports `parameter_error`.
        Provider-level read ceilings run outside that check, so they fall back to
        the default rather than turning a bad config value into a transport error.
        """
        value, _error = self._positive_float_info(
            "SMART_SEARCH_TIMEOUT_SECONDS",
            self._DEFAULT_SEARCH_TIMEOUT_SECONDS,
        )
        return value

    @property
    def provider_cooldown_seconds(self) -> float:
        """Seconds a repeatedly failing optional provider stays skipped. 0 disables cooldown."""
        return self._non_negative_float_value(
            "SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS",
            self._DEFAULT_PROVIDER_COOLDOWN_SECONDS,
        )

    @property
    def provider_failure_threshold(self) -> int:
        """Consecutive soft failures before an optional provider is put on cooldown."""
        return self._positive_int_value(
            "SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD",
            self._DEFAULT_PROVIDER_FAILURE_THRESHOLD,
        )

    def _csv_values(self, key: str) -> list[str]:
        raw = self._get_config_value(key, "") or ""
        values: list[str] = []
        seen: set[str] = set()
        for item in raw.split(","):
            value = item.strip().lower()
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    @property
    def research_preferred_providers(self) -> list[str]:
        return self._csv_values("SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS")

    @property
    def research_disabled_providers(self) -> list[str]:
        return self._csv_values("SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS")

    @property
    def tavily_enabled(self) -> bool:
        return self.provider_enabled("tavily")

    @classmethod
    def provider_enabled_key(cls, provider: str) -> str:
        if provider == "zhipu-mcp-zread":
            provider = "zhipu-mcp"
        return cls.PROVIDER_ENABLED_KEYS.get(provider, "")

    def provider_enabled(self, provider: str) -> bool:
        if provider == "main-search":
            return any(self.provider_enabled(item) for item in ("xai-responses", "openai-compatible"))
        key = self.provider_enabled_key(provider)
        if not key:
            return True
        value = self._get_config_value(key, "true") or "true"
        return value.strip().lower() in {"true", "1", "yes", "on"}

    @property
    def tavily_api_url(self) -> str:
        return self._get_config_value("TAVILY_API_URL", "https://api.tavily.com") or "https://api.tavily.com"

    @property
    def tavily_api_key(self) -> str | None:
        return self._get_config_value("TAVILY_API_KEY")

    @property
    def tavily_timeout(self) -> float:
        return float(self._get_config_value("TAVILY_TIMEOUT_SECONDS", "30") or "30")

    @property
    def firecrawl_api_url(self) -> str:
        return self._get_config_value("FIRECRAWL_API_URL", "https://api.firecrawl.dev/v2") or "https://api.firecrawl.dev/v2"

    @property
    def firecrawl_api_key(self) -> str | None:
        return self._get_config_value("FIRECRAWL_API_KEY")

    @property
    def tinyfish_api_key(self) -> str | None:
        return self._get_config_value("TINYFISH_API_KEY")

    @property
    def tinyfish_search_api_url(self) -> str:
        return (
            self._get_config_value("TINYFISH_SEARCH_API_URL", "https://api.search.tinyfish.ai")
            or "https://api.search.tinyfish.ai"
        )

    @property
    def tinyfish_fetch_api_url(self) -> str:
        return (
            self._get_config_value("TINYFISH_FETCH_API_URL", "https://api.fetch.tinyfish.ai")
            or "https://api.fetch.tinyfish.ai"
        )

    @property
    def tinyfish_timeout(self) -> float:
        return self._parse_positive_float_value("TINYFISH_TIMEOUT_SECONDS", self._get_config_value("TINYFISH_TIMEOUT_SECONDS", "150") or "150")

    @property
    def deepseek_api_key(self) -> str | None:
        return self._get_config_value("DEEPSEEK_API_KEY")

    @property
    def deepseek_api_url(self) -> str:
        return self._get_config_value("DEEPSEEK_API_URL", "https://api.deepseek.com") or "https://api.deepseek.com"

    @property
    def deepseek_timeout(self) -> float:
        return self._parse_positive_float_value("DEEPSEEK_TIMEOUT_SECONDS", self._get_config_value("DEEPSEEK_TIMEOUT_SECONDS", "60") or "60")

    @property
    def anysearch_api_url(self) -> str:
        return self._get_config_value("ANYSEARCH_API_URL", "https://api.anysearch.com/mcp") or "https://api.anysearch.com/mcp"

    @property
    def anysearch_api_key(self) -> str | None:
        return self._get_config_value("ANYSEARCH_API_KEY")

    @property
    def anysearch_timeout(self) -> float:
        return float(self._get_config_value("ANYSEARCH_TIMEOUT_SECONDS", "30") or "30")

    @property
    def sciverse_api_url(self) -> str:
        return self._get_config_value("SCIVERSE_API_URL", "https://api.sciverse.space") or "https://api.sciverse.space"

    @property
    def sciverse_api_token(self) -> str | None:
        return self._get_config_value("SCIVERSE_API_TOKEN")

    @property
    def sciverse_timeout(self) -> float:
        return float(self._get_config_value("SCIVERSE_TIMEOUT_SECONDS", "30") or "30")

    @property
    def log_level(self) -> str:
        return (self._get_config_value("SMART_SEARCH_LOG_LEVEL", "INFO") or "INFO").upper()

    @property
    def log_dir(self) -> Path:
        log_dir_str = self.log_dir_config_value
        log_dir = Path(log_dir_str)
        if log_dir.is_absolute():
            return log_dir

        return self.config_file.parent / log_dir

    @property
    def log_dir_config_value(self) -> str:
        return self._get_config_value("SMART_SEARCH_LOG_DIR", "logs") or "logs"

    @staticmethod
    def apply_model_suffix_for_url(model: str, api_url: str) -> str:
        if "openrouter" in api_url and ":online" not in model:
            return f"{model}:online"
        return model

    def _base_model_value(self) -> str:
        return self._DEFAULT_MODEL

    @staticmethod
    def _mask_api_key(key: str) -> str:
        if not key or len(key) <= 8:
            return "***"
        return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"

    @classmethod
    def _mask_if_secret(cls, key: str, value: str) -> str:
        if "KEY" in key or "TOKEN" in key or "SECRET" in key:
            return cls._mask_api_key(value)
        return value

    @property
    def output_cleanup_enabled(self) -> bool:
        return (self._get_config_value("SMART_SEARCH_OUTPUT_CLEANUP", "true") or "true").lower() in ("true", "1", "yes")

    @property
    def log_to_file_enabled(self) -> bool:
        return (self._get_config_value("SMART_SEARCH_LOG_TO_FILE", "false") or "false").lower() in ("true", "1", "yes")

    @property
    def ssl_verify_enabled(self) -> bool:
        return (self._get_config_value("SSL_VERIFY", "true") or "true").lower() not in ("false", "0", "no")

    @property
    def exa_api_key(self) -> str | None:
        return self._get_config_value("EXA_API_KEY")

    @property
    def exa_base_url(self) -> str:
        return self._get_config_value("EXA_BASE_URL", "https://api.exa.ai") or "https://api.exa.ai"

    @property
    def exa_timeout(self) -> float:
        return float(self._get_config_value("EXA_TIMEOUT_SECONDS", "30") or "30")

    @property
    def context7_api_key(self) -> str | None:
        return self._get_config_value("CONTEXT7_API_KEY")

    @property
    def context7_base_url(self) -> str:
        return self._get_config_value("CONTEXT7_BASE_URL", "https://context7.com") or "https://context7.com"

    @property
    def context7_timeout(self) -> float:
        return float(self._get_config_value("CONTEXT7_TIMEOUT_SECONDS", "30") or "30")

    @property
    def zhipu_api_key(self) -> str | None:
        return self._get_config_value("ZHIPU_API_KEY")

    @property
    def zhipu_api_url(self) -> str:
        return self._get_config_value("ZHIPU_API_URL", "https://open.bigmodel.cn/api") or "https://open.bigmodel.cn/api"

    @property
    def zhipu_search_engine(self) -> str:
        return self._get_config_value("ZHIPU_SEARCH_ENGINE", "search_std") or "search_std"

    @property
    def zhipu_timeout(self) -> float:
        return float(self._get_config_value("ZHIPU_TIMEOUT_SECONDS", "30") or "30")

    @property
    def zhipu_mcp_api_key(self) -> str | None:
        return self._get_config_value("ZHIPU_MCP_API_KEY")

    @property
    def zhipu_mcp_search_api_url(self) -> str:
        return self._get_config_value(
            "ZHIPU_MCP_SEARCH_API_URL",
            "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
        ) or "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"

    @property
    def zhipu_mcp_reader_api_url(self) -> str:
        return self._get_config_value(
            "ZHIPU_MCP_READER_API_URL",
            "https://open.bigmodel.cn/api/mcp/web_reader/mcp",
        ) or "https://open.bigmodel.cn/api/mcp/web_reader/mcp"

    @property
    def zhipu_mcp_zread_api_url(self) -> str:
        return self._get_config_value(
            "ZHIPU_MCP_ZREAD_API_URL",
            "https://open.bigmodel.cn/api/mcp/zread/mcp",
        ) or "https://open.bigmodel.cn/api/mcp/zread/mcp"

    @property
    def zhipu_mcp_timeout(self) -> float:
        return float(self._get_config_value("ZHIPU_MCP_TIMEOUT_SECONDS", "30") or "30")

    @property
    def jina_api_key(self) -> str | None:
        return self._get_config_value("JINA_API_KEY")

    @property
    def jina_reader_api_url(self) -> str:
        return self._get_config_value("JINA_READER_API_URL", "https://r.jina.ai") or "https://r.jina.ai"

    @property
    def jina_respond_with(self) -> str:
        return self._get_config_value("JINA_RESPOND_WITH", "") or ""

    @property
    def jina_timeout(self) -> float:
        return float(self._get_config_value("JINA_TIMEOUT_SECONDS", "30") or "30")

    def get_config_info(self) -> dict:
        config_parameter_errors: list[str] = []
        jev_info = {}
        for key, default in JEV_DEFAULTS.items():
            value = self._get_config_value(key, default)
            try:
                value = validate_jev_value(key, value)
            except ValueError as exc:
                config_parameter_errors.append(str(exc))
            jev_info[key] = self._mask_if_secret(key, str(value)) if "KEY" in key else value
        xai_reasoning_effort = self._get_config_value("XAI_REASONING_EFFORT", "")
        try:
            xai_reasoning_effort = self.xai_reasoning_effort
        except ValueError as exc:
            config_parameter_errors.append(str(exc))
        xai_configured = self.provider_enabled("xai-responses") and bool(self.xai_api_key)
        openai_configured = self.provider_enabled("openai-compatible") and bool(self.openai_compatible_api_url and self.openai_compatible_api_key)
        explicit_main_configured = xai_configured or openai_configured
        if explicit_main_configured:
            config_status = tr('ok: 配置完整')
        else:
            config_status = f"config_error: {self._SETUP_COMMAND}"

        validation_level, validation_error = self._enum_info(
            "SMART_SEARCH_VALIDATION_LEVEL",
            self._DEFAULT_VALIDATION_LEVEL,
            self._ALLOWED_VALIDATION_LEVELS,
        )
        fallback_mode, fallback_error = self._enum_info(
            "SMART_SEARCH_FALLBACK_MODE",
            self._DEFAULT_FALLBACK_MODE,
            self._ALLOWED_FALLBACK_MODES,
        )
        minimum_profile, minimum_error = self._enum_info(
            "SMART_SEARCH_MINIMUM_PROFILE",
            self._DEFAULT_MINIMUM_PROFILE,
            self._ALLOWED_MINIMUM_PROFILES,
        )
        intent_router_mode, intent_router_error = self._enum_info(
            "SMART_SEARCH_INTENT_ROUTER",
            self._DEFAULT_INTENT_ROUTER_MODE,
            self._ALLOWED_INTENT_ROUTER_MODES,
        )
        if not intent_router_error:
            intent_router_mode = normalize_router_mode(intent_router_mode)
        if intent_router_mode == "jev":
            config_status = "ok: Jev routing configured" if self._get_config_value("TYPESAFE_API_KEY") else "ok: local routing (Jev not configured)"
        openai_compatible_api_mode, openai_compatible_api_mode_error = self._enum_info(
            "OPENAI_COMPATIBLE_API_MODE",
            self._DEFAULT_OPENAI_COMPATIBLE_API_MODE,
            self._ALLOWED_OPENAI_COMPATIBLE_API_MODES,
        )
        primary_api_mode = tr('未配置')
        if xai_configured:
            primary_api_mode = "xai-responses"
        elif openai_configured:
            primary_api_mode = openai_compatible_api_mode
        search_timeout, search_timeout_error = self._positive_float_info(
            "SMART_SEARCH_TIMEOUT_SECONDS",
            self._DEFAULT_SEARCH_TIMEOUT_SECONDS,
        )
        provider_cooldown_seconds, provider_cooldown_error = self._non_negative_float_info(
            "SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS",
            self._DEFAULT_PROVIDER_COOLDOWN_SECONDS,
        )
        provider_failure_threshold, provider_failure_threshold_error = self._positive_int_info(
            "SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD",
            self._DEFAULT_PROVIDER_FAILURE_THRESHOLD,
        )
        config_parameter_errors.extend(
            error
            for error in (
                validation_error,
                fallback_error,
                minimum_error,
                intent_router_error,
                openai_compatible_api_mode_error,
                search_timeout_error,
                provider_cooldown_error,
                provider_failure_threshold_error,
            )
            if error
        )
        if config_parameter_errors and config_status.startswith("ok:"):
            config_status = f"config_error: {'; '.join(config_parameter_errors)}"

        return {
            **jev_info,
            **{key: self.provider_enabled(provider) for provider, key in self.PROVIDER_ENABLED_KEYS.items()},
            "XAI_API_URL": self.xai_api_url,
            "XAI_API_KEY": self._mask_api_key(self.xai_api_key) if self.xai_api_key else tr('未配置'),
            "XAI_MODEL": self.xai_model,
            "XAI_TOOLS": self.xai_tools_raw,
            "XAI_REASONING_EFFORT": xai_reasoning_effort,
            "XAI_STREAM": self.xai_stream,
            "OPENAI_COMPATIBLE_API_URL": self.openai_compatible_api_url or tr('未配置'),
            "OPENAI_COMPATIBLE_API_KEY": self._mask_api_key(self.openai_compatible_api_key) if self.openai_compatible_api_key else tr('未配置'),
            "OPENAI_COMPATIBLE_MODEL": self.openai_compatible_model,
            "OPENAI_COMPATIBLE_FALLBACK_MODELS": ",".join(self.openai_compatible_fallback_models),
            "OPENAI_COMPATIBLE_API_MODE": openai_compatible_api_mode,
            "OPENAI_COMPATIBLE_STREAM": self.openai_compatible_stream,
            "SMART_SEARCH_VALIDATION_LEVEL": validation_level,
            "SMART_SEARCH_FALLBACK_MODE": fallback_mode,
            "SMART_SEARCH_MINIMUM_PROFILE": minimum_profile,
            "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS": ",".join(self.research_preferred_providers),
            "SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS": ",".join(self.research_disabled_providers),
            "SMART_SEARCH_INTENT_ROUTER": intent_router_mode,
            "SMART_SEARCH_TIMEOUT_SECONDS": search_timeout,
            "SMART_SEARCH_PROVIDER_COOLDOWN_SECONDS": provider_cooldown_seconds,
            "SMART_SEARCH_PROVIDER_FAILURE_THRESHOLD": provider_failure_threshold,
            "SMART_SEARCH_DEBUG": self.debug_enabled,
            "SMART_SEARCH_LOG_LEVEL": self.log_level,
            "SMART_SEARCH_LOG_DIR": self.log_dir_config_value,
            "SMART_SEARCH_RETRY_MAX_ATTEMPTS": self.retry_max_attempts,
            "SMART_SEARCH_RETRY_MULTIPLIER": self.retry_multiplier,
            "SMART_SEARCH_RETRY_MAX_WAIT": self.retry_max_wait,
            "TAVILY_API_URL": self.tavily_api_url,
            "TAVILY_API_KEY": self._mask_api_key(self.tavily_api_key) if self.tavily_api_key else tr('未配置'),
            "TAVILY_TIMEOUT_SECONDS": self.tavily_timeout,
            "FIRECRAWL_API_URL": self.firecrawl_api_url,
            "FIRECRAWL_API_KEY": self._mask_api_key(self.firecrawl_api_key) if self.firecrawl_api_key else tr('未配置'),
            "TINYFISH_SEARCH_API_URL": self.tinyfish_search_api_url,
            "TINYFISH_FETCH_API_URL": self.tinyfish_fetch_api_url,
            "TINYFISH_API_KEY": self._mask_api_key(self.tinyfish_api_key) if self.tinyfish_api_key else tr('未配置'),
            "TINYFISH_TIMEOUT_SECONDS": self.tinyfish_timeout,
            "DEEPSEEK_API_URL": self.deepseek_api_url,
            "DEEPSEEK_API_KEY": self._mask_api_key(self.deepseek_api_key) if self.deepseek_api_key else tr('未配置'),
            "DEEPSEEK_TIMEOUT_SECONDS": self.deepseek_timeout,
            "ANYSEARCH_API_URL": self.anysearch_api_url,
            "ANYSEARCH_API_KEY": self._mask_api_key(self.anysearch_api_key) if self.anysearch_api_key else tr('未配置'),
            "ANYSEARCH_TIMEOUT_SECONDS": self.anysearch_timeout,
            "SCIVERSE_API_URL": self.sciverse_api_url,
            "SCIVERSE_API_TOKEN": self._mask_api_key(self.sciverse_api_token) if self.sciverse_api_token else tr('未配置'),
            "SCIVERSE_TIMEOUT_SECONDS": self.sciverse_timeout,
            "SMART_SEARCH_OUTPUT_CLEANUP": self.output_cleanup_enabled,
            "SMART_SEARCH_LOG_TO_FILE": self.log_to_file_enabled,
            "SSL_VERIFY": self.ssl_verify_enabled,
            "EXA_API_KEY": self._mask_api_key(self.exa_api_key) if self.exa_api_key else tr('未配置'),
            "EXA_BASE_URL": self.exa_base_url,
            "EXA_TIMEOUT_SECONDS": self.exa_timeout,
            "CONTEXT7_API_KEY": self._mask_api_key(self.context7_api_key) if self.context7_api_key else tr('未配置'),
            "CONTEXT7_BASE_URL": self.context7_base_url,
            "CONTEXT7_TIMEOUT_SECONDS": self.context7_timeout,
            "ZHIPU_API_KEY": self._mask_api_key(self.zhipu_api_key) if self.zhipu_api_key else tr('未配置'),
            "ZHIPU_API_URL": self.zhipu_api_url,
            "ZHIPU_SEARCH_ENGINE": self.zhipu_search_engine,
            "ZHIPU_TIMEOUT_SECONDS": self.zhipu_timeout,
            "ZHIPU_MCP_API_KEY": self._mask_api_key(self.zhipu_mcp_api_key) if self.zhipu_mcp_api_key else tr('未配置'),
            "ZHIPU_MCP_SEARCH_API_URL": self.zhipu_mcp_search_api_url,
            "ZHIPU_MCP_READER_API_URL": self.zhipu_mcp_reader_api_url,
            "ZHIPU_MCP_ZREAD_API_URL": self.zhipu_mcp_zread_api_url,
            "ZHIPU_MCP_TIMEOUT_SECONDS": self.zhipu_mcp_timeout,
            "JINA_API_KEY": self._mask_api_key(self.jina_api_key) if self.jina_api_key else tr('未配置'),
            "JINA_READER_API_URL": self.jina_reader_api_url,
            "JINA_RESPOND_WITH": self.jina_respond_with,
            "JINA_TIMEOUT_SECONDS": self.jina_timeout,
            "primary_api_mode": primary_api_mode,
            "primary_api_mode_source": "config_file" if explicit_main_configured else "default",
            "config_file": str(self.config_file),
            "config_dir": str(self.config_file.parent),
            "config_dir_source": self.config_dir_source,
            "default_config_file": str(self._default_config_dir() / "config.json"),
            "legacy_windows_config_file": str(self._legacy_windows_config_dir() / "config.json") if sys.platform.startswith("win") else "",
            "legacy_windows_config_exists": (self._legacy_windows_config_dir() / "config.json").exists() if sys.platform.startswith("win") else False,
            "config_dir_override_value": self._config_dir_override_value(),
            "config_dir_override_matches_default": self._config_dir_override_matches_default(),
            "log_dir_config_value": self.log_dir_config_value,
            "resolved_log_dir": str(self.log_dir),
            "file_logging_enabled": self.debug_enabled or self.log_to_file_enabled,
            "config_sources": self.get_config_sources(),
            "config_parameter_errors": config_parameter_errors,
            "config_status": config_status
        }

config = Config()
