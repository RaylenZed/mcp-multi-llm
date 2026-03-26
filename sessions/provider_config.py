"""Load and validate custom provider configs from ~/.mcp-multi-llm/custom_providers.json."""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_BUILTIN_NAMES = {"claude", "codex", "gemini"}
_VALID_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
_DEFAULT_CONFIG_PATH = Path.home() / ".mcp-multi-llm" / "custom_providers.json"


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str


def load_custom_providers(path: Path | None = None) -> list[ProviderConfig]:
    """Load custom providers from a JSON config file.

    Returns an empty list if the file doesn't exist or has no valid entries.
    Invalid entries are skipped with a warning log.
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

        providers.append(ProviderConfig(name=name, base_url=base_url, model=model, api_key=api_key))

    logger.info(f"[provider_config] Loaded {len(providers)} custom provider(s) from {path}")
    return providers
