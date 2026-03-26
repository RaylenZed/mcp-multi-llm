"""Load and validate custom provider configs from ~/.mcp-multi-llm/custom_providers.json."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILTIN_NAMES = {"claude", "codex"}
_VALID_PROTOCOLS = {"openai", "anthropic"}
_VALID_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
_DEFAULT_CONFIG_PATH = Path.home() / ".mcp-multi-llm" / "custom_providers.json"
_DEFAULT_SETTINGS_PATH = Path.home() / ".mcp-multi-llm" / "settings.json"


@dataclass
class BuiltinProviderSettings:
    mode: str = "cli"       # "cli" or "api"
    api_key: str = ""       # falls back to env var if empty
    base_url: str = ""      # uses provider default if empty
    model: str = ""         # uses provider default if empty


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str
    protocol: str = "openai"          # "openai" or "anthropic"
    extra_body: dict = field(default_factory=dict)  # merged into request body (openai protocol only)


def load_custom_providers(path: Path | None = None) -> list[ProviderConfig]:
    """Load custom providers from a JSON config file.

    Returns an empty list if the file doesn't exist or has no valid entries.
    Invalid entries are skipped with a warning log.

    Supported fields per entry:
        name (str, required)       — identifier used as tool name suffix
        base_url (str, required)   — API base URL
        model (str, required)      — model name to pass in requests
        api_key (str, required)    — API key
        protocol (str, optional)   — "openai" (default) or "anthropic"
        extra_body (obj, optional) — extra fields merged into the request body (openai only)
    """
    if path is None:
        path = _DEFAULT_CONFIG_PATH

    if not path.exists():
        return []

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[provider_config] Failed to read {path}: {e}")
        return []

    if not isinstance(raw, list):
        logger.error(f"[provider_config] {path} must contain a JSON array, got {type(raw).__name__}")
        return []

    providers = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            logger.warning(f"[provider_config] Entry {i}: not a JSON object — skipping")
            continue

        name = entry.get("name", "")
        base_url = entry.get("base_url", "")
        model = entry.get("model", "")
        api_key = entry.get("api_key", "")

        if not all([name, base_url, model, api_key]):
            logger.warning(f"[provider_config] Entry {i}: missing required field(s) — skipping")
            continue

        if not _VALID_NAME.match(name):
            logger.warning(f"[provider_config] Entry {i}: name '{name}' is not a valid identifier — skipping")
            continue

        if name.lower() in _BUILTIN_NAMES:
            logger.warning(f"[provider_config] Entry {i}: name '{name}' conflicts with a built-in provider — skipping")
            continue

        protocol = entry.get("protocol", "openai")
        if protocol not in _VALID_PROTOCOLS:
            logger.warning(
                f"[provider_config] Entry {i}: unknown protocol '{protocol}', "
                f"must be one of {sorted(_VALID_PROTOCOLS)} — skipping"
            )
            continue

        extra_body = entry.get("extra_body", {})
        if not isinstance(extra_body, dict):
            logger.warning(f"[provider_config] Entry {i}: extra_body must be a JSON object — ignoring")
            extra_body = {}

        providers.append(ProviderConfig(
            name=name,
            base_url=base_url,
            model=model,
            api_key=api_key,
            protocol=protocol,
            extra_body=extra_body,
        ))

    logger.info(f"[provider_config] Loaded {len(providers)} custom provider(s) from {path}")
    return providers


def load_builtin_settings(path: Path | None = None) -> dict[str, BuiltinProviderSettings]:
    """Load CLI-vs-API mode settings for built-in providers (claude, codex).

    Reads ~/.mcp-multi-llm/settings.json. Missing file → all providers default to CLI.

    Example settings.json:
        {
          "claude": {"mode": "api", "model": "claude-opus-4-6"},
          "codex":  {"mode": "cli"}
        }
    """
    if path is None:
        path = _DEFAULT_SETTINGS_PATH

    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"[provider_config] Failed to read {path}: {e}")
        return {}

    if not isinstance(raw, dict):
        logger.error(f"[provider_config] {path} must be a JSON object")
        return {}

    result: dict[str, BuiltinProviderSettings] = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            logger.warning(f"[provider_config] settings '{name}' must be a JSON object — skipping")
            continue
        mode = cfg.get("mode", "cli")
        if mode not in ("cli", "api"):
            logger.warning(f"[provider_config] settings '{name}': unknown mode '{mode}', defaulting to 'cli'")
            mode = "cli"
        result[name] = BuiltinProviderSettings(
            mode=mode,
            api_key=cfg.get("api_key", ""),
            base_url=cfg.get("base_url", ""),
            model=cfg.get("model", ""),
        )

    return result
