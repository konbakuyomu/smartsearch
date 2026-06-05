import json
import os
import sys
from pathlib import Path

class Config:
    _instance = None
    _SETUP_COMMAND = (
        "Run `smart-search setup`, or configure XAI_API_KEY and/or "
        "OPENAI_COMPATIBLE_API_URL plus OPENAI_COMPATIBLE_API_KEY, then run "
        "`smart-search doctor --format json`."
    )
    _DEFAULT_MODEL = "grok-4-fast"
    _DEFAULT_XAI_TOOLS = "web_search,x_search"
    _DEFAULT_VALIDATION_LEVEL = "balanced"
    _DEFAULT_FALLBACK_MODE = "auto"
    _DEFAULT_MINIMUM_PROFILE = "standard"
    _ALLOWED_XAI_TOOLS = {"web_search", "x_search"}
    _ALLOWED_VALIDATION_LEVELS = {"fast", "balanced", "strict"}
    _ALLOWED_FALLBACK_MODES = {"auto", "off"}
    _ALLOWED_MINIMUM_PROFILES = {"standard", "off"}
    _CONFIG_KEYS = {
        "XAI_API_URL",
        "XAI_API_KEY",
        "XAI_MODEL",
        "XAI_TOOLS",
        "OPENAI_COMPATIBLE_API_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "OPENAI_COMPATIBLE_STREAM",
        "SMART_SEARCH_VALIDATION_LEVEL",
        "SMART_SEARCH_FALLBACK_MODE",
        "SMART_SEARCH_MINIMUM_PROFILE",
        "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS",
        "SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS",
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
        "ANYSEARCH_API_KEY",
        "ANYSEARCH_API_URL",
        "ANYSEARCH_TIMEOUT_SECONDS",
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
    _LEGACY_CONFIG_KEYS: dict[str, str] = {}

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
        if self._config_file is None:
            _ = self.config_file
        return self._config_dir_source or "override"

    def _load_config_file(self) -> dict:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except (FileNotFoundError, PermissionError, OSError, json.JSONDecodeError):
            return {}

    def _save_config_file(self, config_data: dict) -> None:
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
        except (IOError, PermissionError, OSError) as e:
            hint = " (sandbox/CI 下可设 SMART_SEARCH_CONFIG_DIR 指向可写目录)" if isinstance(e, PermissionError) else ""
            raise ValueError(f"无法保存配置文件: {str(e)}{hint}")

    def _get_config_value(self, key: str, default: str | None = None) -> str | None:
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

    def get_saved_config(self, masked: bool = True) -> dict:
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

    def set_config_value(self, key: str, value: str) -> None:
        key = key.strip().upper()
        if key not in self._CONFIG_KEYS:
            raise ValueError(f"Unsupported config key: {key}")
        config_data = self._load_config_file()
        config_data[key] = value
        self._save_config_file(config_data)
        if key in {
            "XAI_API_URL",
            "XAI_API_KEY",
            "XAI_MODEL",
            "XAI_TOOLS",
            "OPENAI_COMPATIBLE_API_URL",
            "OPENAI_COMPATIBLE_API_KEY",
            "OPENAI_COMPATIBLE_MODEL",
            "OPENAI_COMPATIBLE_STREAM",
            "SMART_SEARCH_VALIDATION_LEVEL",
            "SMART_SEARCH_FALLBACK_MODE",
            "SMART_SEARCH_MINIMUM_PROFILE",
        }:
            self._cached_model = None

    def unset_config_value(self, key: str) -> None:
        key = key.strip().upper()
        if key not in self._CONFIG_KEYS:
            raise ValueError(f"Unsupported config key: {key}")
        config_data = self._load_config_file()
        config_data.pop(key, None)
        for old_key, new_key in self._LEGACY_CONFIG_KEYS.items():
            if new_key == key:
                config_data.pop(old_key, None)
        self._save_config_file(config_data)
        if key in {
            "XAI_API_URL",
            "XAI_API_KEY",
            "XAI_MODEL",
            "XAI_TOOLS",
            "OPENAI_COMPATIBLE_API_URL",
            "OPENAI_COMPATIBLE_API_KEY",
            "OPENAI_COMPATIBLE_MODEL",
            "OPENAI_COMPATIBLE_STREAM",
            "SMART_SEARCH_VALIDATION_LEVEL",
            "SMART_SEARCH_FALLBACK_MODE",
            "SMART_SEARCH_MINIMUM_PROFILE",
        }:
            self._cached_model = None

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
            raise ValueError(f"Invalid XAI_TOOLS: {invalid_text}. Supported values: {allowed}")
        return tools

    def _validated_enum(self, key: str, default: str, allowed: set[str]) -> str:
        value = (self._get_config_value(key, default) or default).strip().lower()
        if value not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            raise ValueError(f"Invalid {key}: {value}. Supported values: {allowed_text}")
        return value

    def _enum_info(self, key: str, default: str, allowed: set[str]) -> tuple[str, str]:
        value = (self._get_config_value(key, default) or default).strip().lower()
        if value not in allowed:
            allowed_text = ", ".join(sorted(allowed))
            return value, f"Invalid {key}: {value}. Supported values: {allowed_text}"
        return value, ""

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
        return (self._get_config_value("TAVILY_ENABLED", "true") or "true").lower() in ("true", "1", "yes")

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
    def anysearch_api_url(self) -> str:
        return self._get_config_value("ANYSEARCH_API_URL", "https://api.anysearch.com/mcp") or "https://api.anysearch.com/mcp"

    @property
    def anysearch_api_key(self) -> str | None:
        return self._get_config_value("ANYSEARCH_API_KEY")

    @property
    def anysearch_timeout(self) -> float:
        return float(self._get_config_value("ANYSEARCH_TIMEOUT_SECONDS", "30") or "30")

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
        explicit_main_configured = bool(
            self.xai_api_key
            or (self.openai_compatible_api_url and self.openai_compatible_api_key)
        )
        if explicit_main_configured:
            config_status = "ok: 配置完整"
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
        config_parameter_errors.extend(error for error in (validation_error, fallback_error, minimum_error) if error)
        if config_parameter_errors and config_status.startswith("ok:"):
            config_status = f"config_error: {'; '.join(config_parameter_errors)}"

        return {
            "XAI_API_URL": self.xai_api_url,
            "XAI_API_KEY": self._mask_api_key(self.xai_api_key) if self.xai_api_key else "未配置",
            "XAI_MODEL": self.xai_model,
            "XAI_TOOLS": self.xai_tools_raw,
            "OPENAI_COMPATIBLE_API_URL": self.openai_compatible_api_url or "未配置",
            "OPENAI_COMPATIBLE_API_KEY": self._mask_api_key(self.openai_compatible_api_key) if self.openai_compatible_api_key else "未配置",
            "OPENAI_COMPATIBLE_MODEL": self.openai_compatible_model,
            "OPENAI_COMPATIBLE_STREAM": self.openai_compatible_stream,
            "SMART_SEARCH_VALIDATION_LEVEL": validation_level,
            "SMART_SEARCH_FALLBACK_MODE": fallback_mode,
            "SMART_SEARCH_MINIMUM_PROFILE": minimum_profile,
            "SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS": ",".join(self.research_preferred_providers),
            "SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS": ",".join(self.research_disabled_providers),
            "SMART_SEARCH_DEBUG": self.debug_enabled,
            "SMART_SEARCH_LOG_LEVEL": self.log_level,
            "SMART_SEARCH_LOG_DIR": self.log_dir_config_value,
            "SMART_SEARCH_RETRY_MAX_ATTEMPTS": self.retry_max_attempts,
            "SMART_SEARCH_RETRY_MULTIPLIER": self.retry_multiplier,
            "SMART_SEARCH_RETRY_MAX_WAIT": self.retry_max_wait,
            "TAVILY_API_URL": self.tavily_api_url,
            "TAVILY_ENABLED": self.tavily_enabled,
            "TAVILY_API_KEY": self._mask_api_key(self.tavily_api_key) if self.tavily_api_key else "未配置",
            "TAVILY_TIMEOUT_SECONDS": self.tavily_timeout,
            "FIRECRAWL_API_URL": self.firecrawl_api_url,
            "FIRECRAWL_API_KEY": self._mask_api_key(self.firecrawl_api_key) if self.firecrawl_api_key else "未配置",
            "ANYSEARCH_API_URL": self.anysearch_api_url,
            "ANYSEARCH_API_KEY": self._mask_api_key(self.anysearch_api_key) if self.anysearch_api_key else "未配置",
            "ANYSEARCH_TIMEOUT_SECONDS": self.anysearch_timeout,
            "SMART_SEARCH_OUTPUT_CLEANUP": self.output_cleanup_enabled,
            "SMART_SEARCH_LOG_TO_FILE": self.log_to_file_enabled,
            "SSL_VERIFY": self.ssl_verify_enabled,
            "EXA_API_KEY": self._mask_api_key(self.exa_api_key) if self.exa_api_key else "未配置",
            "EXA_BASE_URL": self.exa_base_url,
            "EXA_TIMEOUT_SECONDS": self.exa_timeout,
            "CONTEXT7_API_KEY": self._mask_api_key(self.context7_api_key) if self.context7_api_key else "未配置",
            "CONTEXT7_BASE_URL": self.context7_base_url,
            "CONTEXT7_TIMEOUT_SECONDS": self.context7_timeout,
            "ZHIPU_API_KEY": self._mask_api_key(self.zhipu_api_key) if self.zhipu_api_key else "未配置",
            "ZHIPU_API_URL": self.zhipu_api_url,
            "ZHIPU_SEARCH_ENGINE": self.zhipu_search_engine,
            "ZHIPU_TIMEOUT_SECONDS": self.zhipu_timeout,
            "ZHIPU_MCP_API_KEY": self._mask_api_key(self.zhipu_mcp_api_key) if self.zhipu_mcp_api_key else "未配置",
            "ZHIPU_MCP_SEARCH_API_URL": self.zhipu_mcp_search_api_url,
            "ZHIPU_MCP_READER_API_URL": self.zhipu_mcp_reader_api_url,
            "ZHIPU_MCP_ZREAD_API_URL": self.zhipu_mcp_zread_api_url,
            "ZHIPU_MCP_TIMEOUT_SECONDS": self.zhipu_mcp_timeout,
            "JINA_API_KEY": self._mask_api_key(self.jina_api_key) if self.jina_api_key else "未配置",
            "JINA_READER_API_URL": self.jina_reader_api_url,
            "JINA_RESPOND_WITH": self.jina_respond_with,
            "JINA_TIMEOUT_SECONDS": self.jina_timeout,
            "primary_api_mode": "xai-responses" if self.xai_api_key else ("chat-completions" if self.openai_compatible_api_url and self.openai_compatible_api_key else "未配置"),
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
