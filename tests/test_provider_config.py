"""Tests for custom provider config loading."""
import json
import pytest
from pathlib import Path
from sessions.provider_config import load_custom_providers, ProviderConfig


def write_config(tmp_path: Path, data) -> Path:
    p = tmp_path / "custom_providers.json"
    p.write_text(json.dumps(data))
    return p


def test_load_valid_config(tmp_path):
    """Valid config returns list of ProviderConfig objects."""
    cfg_path = write_config(tmp_path, [
        {"name": "deepseek", "base_url": "https://api.deepseek.com/v1",
         "model": "deepseek-chat", "api_key": "sk-123"},
    ])
    providers = load_custom_providers(cfg_path)
    assert len(providers) == 1
    assert providers[0].name == "deepseek"
    assert providers[0].model == "deepseek-chat"
    assert providers[0].api_key == "sk-123"


def test_load_missing_file_returns_empty(tmp_path):
    """Missing config file returns empty list (not an error)."""
    providers = load_custom_providers(tmp_path / "nonexistent.json")
    assert providers == []


def test_invalid_name_is_skipped(tmp_path):
    """Entries with invalid names (spaces, special chars) are skipped with a warning."""
    cfg_path = write_config(tmp_path, [
        {"name": "bad name!", "base_url": "https://x.com", "model": "m", "api_key": "k"},
        {"name": "valid", "base_url": "https://x.com", "model": "m", "api_key": "k"},
    ])
    providers = load_custom_providers(cfg_path)
    assert len(providers) == 1
    assert providers[0].name == "valid"


def test_builtin_name_is_skipped(tmp_path):
    """Entries named 'claude', 'codex', or 'gemini' are rejected."""
    cfg_path = write_config(tmp_path, [
        {"name": "claude", "base_url": "https://x.com", "model": "m", "api_key": "k"},
    ])
    providers = load_custom_providers(cfg_path)
    assert providers == []


def test_missing_required_field_is_skipped(tmp_path):
    """Entries missing required fields are skipped."""
    cfg_path = write_config(tmp_path, [
        {"name": "deepseek", "model": "deepseek-chat", "api_key": "sk-123"},  # no base_url
    ])
    providers = load_custom_providers(cfg_path)
    assert providers == []


def test_load_multiple_providers(tmp_path):
    """Multiple valid entries all load correctly."""
    cfg_path = write_config(tmp_path, [
        {"name": "deepseek", "base_url": "https://api.deepseek.com/v1",
         "model": "deepseek-chat", "api_key": "sk-a"},
        {"name": "qianwen", "base_url": "https://dashscope.aliyuncs.com/v1",
         "model": "qwen-plus", "api_key": "sk-b"},
    ])
    providers = load_custom_providers(cfg_path)
    assert len(providers) == 2
    assert {p.name for p in providers} == {"deepseek", "qianwen"}


def test_non_dict_entry_is_skipped(tmp_path):
    """Non-dict entries in the array are skipped without crashing."""
    cfg_path = write_config(tmp_path, ["not-a-dict", 42, None])
    providers = load_custom_providers(cfg_path)
    assert providers == []


def test_malformed_json_returns_empty(tmp_path):
    """Malformed JSON file returns empty list."""
    p = tmp_path / "custom_providers.json"
    p.write_text("this is not json")
    providers = load_custom_providers(p)
    assert providers == []
