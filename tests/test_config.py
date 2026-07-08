from __future__ import annotations

from pathlib import Path

from app.config import AppConfig, load_config


def test_load_config_uses_defaults_when_values_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text("", encoding="utf-8")

    config = load_config(str(config_path))

    assert config.app_name == AppConfig.app_name
    assert config.web_port == AppConfig.web_port
    assert config.enable_ai is AppConfig.enable_ai
    assert config.open_browser_delay_seconds == AppConfig.open_browser_delay_seconds


def test_load_config_overrides_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[general]
app_name = Test PUXAI
data_dir = ./custom-data
default_workspace = ./workspace
workspace_default_id = delivery

[features]
enable_ai = false
ai_backend = dummy

[web]
host = 0.0.0.0
port = 9999

[ollama]
model = llama-test
agent_model = llama-agent
""".strip(),
        encoding="utf-8",
    )

    config = load_config(str(config_path))

    assert config.app_name == "Test PUXAI"
    assert config.data_dir.endswith("custom-data")
    assert config.default_workspace == "./workspace"
    assert config.workspace_default_id == "delivery"
    assert config.enable_ai is False
    assert config.ai_backend == "dummy"
    assert config.web_host == "0.0.0.0"
    assert config.web_port == 9999
    assert config.ollama_model == "llama-test"
    assert config.ollama_agent_model == "llama-agent"


def test_load_config_parses_boolean_integer_and_float_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.ini"
    config_path.write_text(
        """
[features]
enable_ai = yes
enable_history_panel = no

[web]
port = 8010
debug = true
auto_open_browser = false
open_browser_delay_seconds = 2.5

[ollama]
request_timeout_seconds = 45
""".strip(),
        encoding="utf-8",
    )

    config = load_config(str(config_path))

    assert config.enable_ai is True
    assert config.enable_history_panel is False
    assert config.web_port == 8010
    assert config.web_debug is True
    assert config.auto_open_browser is False
    assert config.open_browser_delay_seconds == 2.5
    assert config.ollama_request_timeout_seconds == 45
