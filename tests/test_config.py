"""Unit tests for jantar.config — the root-cause area of the cwd bug.

These tests prove the configuration loads correctly regardless of working
directory and that secrets are stripped (the defect that produced the
``Illegal header value b'Bearer '`` crash).
"""

from __future__ import annotations

from pathlib import Path

from jantar.config import PROJECT_ROOT, Settings, settings


def test_project_root_points_at_repo_with_pyproject():
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_env_file_path_is_absolute_and_named_env():
    cfg = Settings.model_config
    env_file = Path(cfg["env_file"])
    assert env_file.is_absolute()
    assert env_file.name == ".env"
    assert env_file.parent == PROJECT_ROOT


def test_settings_loads_values_from_custom_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "SARVAM_API_KEY=sk_test_123\n"
        "QDRANT_URL=http://example.test:6333\n"
        "API_KEY=unit-test-key\n",
        encoding="utf-8",
    )
    s = Settings(_env_file=str(env))
    assert s.sarvam_api_key == "sk_test_123"
    assert s.qdrant_url == "http://example.test:6333"
    assert s.api_key == "unit-test-key"


def test_secret_whitespace_is_stripped(tmp_path):
    # A trailing newline in the key is exactly what produced the malformed
    # "Bearer <key>\n" header. The validator must strip it.
    env = tmp_path / ".env"
    env.write_text('SARVAM_API_KEY="  sk_padded \n"\n', encoding="utf-8")
    s = Settings(_env_file=str(env))
    assert s.sarvam_api_key == "sk_padded"


def test_relative_log_file_resolves_under_project_root():
    s = Settings(_env_file=str(PROJECT_ROOT / "does-not-exist.env"))
    s.log_file = "logs/jantar.log"
    assert s.log_file_path.is_absolute()
    assert s.log_file_path == PROJECT_ROOT / "logs" / "jantar.log"


def test_absolute_log_file_is_preserved(tmp_path):
    s = Settings(_env_file=str(PROJECT_ROOT / "does-not-exist.env"))
    abs_log = tmp_path / "custom.log"
    s.log_file = str(abs_log)
    assert s.log_file_path == abs_log


def test_unknown_env_keys_are_ignored(tmp_path):
    env = tmp_path / ".env"
    env.write_text("SARVAM_API_KEY=k\nTOTALLY_UNKNOWN_KEY=whatever\n", encoding="utf-8")
    # extra="ignore" => construction must not raise.
    s = Settings(_env_file=str(env))
    assert s.sarvam_api_key == "k"


def test_module_singleton_loaded_successfully():
    # The settings singleton must construct without error and have valid defaults.
    # Do NOT assert on specific env values (couples tests to dev secrets).
    assert settings.sarvam_base_url == "https://api.sarvam.ai"
    assert settings.host == "0.0.0.0"
    assert settings.port == 8000
