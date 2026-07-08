"""Configuration loading utilities for the PUXAI application."""

from __future__ import annotations

import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOGGER: Final = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration loaded from ``config.ini``."""

    app_name: str = "PUXAI"
    data_dir: str = "./app/data"
    default_workspace: str = "."
    workspace_default_id: str = "personal"

    enable_ai: bool = True
    ai_backend: str = "ollama"
    enable_tasks: bool = True
    enable_notes: bool = True
    enable_outlook: bool = False
    enable_history_panel: bool = True
    enable_tray_icon: bool = False
    window_mode: str = "web"
    transparent_background: bool = False

    web_host: str = "127.0.0.1"
    web_port: int = 8787
    web_debug: bool = False
    auto_open_browser: bool = True
    open_browser_delay_seconds: float = 1.0

    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_request_timeout_seconds: int = 180
    ollama_agent_model: str = "llama3.1:8b"

    chatgpt_api_key_env_var: str = "OPENAI_API_KEY"
    chatgpt_model: str = "gpt-4.1-mini"
    chatgpt_timeout_seconds: int = 60

    copilot_enabled: bool = False
    copilot_tenant_id: str = ""
    copilot_client_id: str = ""
    copilot_client_secret_env_var: str = "COPILOT_CLIENT_SECRET"

    outlook_enabled: bool = True
    outlook_default_task_folder: str = "Tasks"
    outlook_read_inbox_folder: str = "Inbox"
    outlook_max_emails: int = 20


def _read_config_file(config_path: str) -> ConfigParser:
    parser = ConfigParser()
    parser.read(config_path)
    LOGGER.debug("Loaded configuration file from %s", config_path)
    return parser


def _getboolean(parser: ConfigParser, section: str, option: str, fallback: bool) -> bool:
    return parser.getboolean(section, option, fallback=fallback)


def load_config(config_path: str = "config.ini") -> AppConfig:
    """Load application configuration from an INI file.

    Args:
        config_path: Path to the configuration file. Defaults to ``config.ini``.

    Returns:
        An ``AppConfig`` instance populated with values from the INI file or
        sensible defaults when keys are missing.
    """

    parser = _read_config_file(config_path)

    app_name = parser.get("general", "app_name", fallback=AppConfig.app_name)
    data_dir = parser.get("general", "data_dir", fallback=AppConfig.data_dir)
    default_workspace = parser.get(
        "general",
        "default_workspace",
        fallback=AppConfig.default_workspace,
    )
    workspace_default_id = parser.get(
        "general",
        "workspace_default_id",
        fallback=AppConfig.workspace_default_id,
    )

    enable_ai = _getboolean(parser, "features", "enable_ai", AppConfig.enable_ai)
    ai_backend = parser.get("features", "ai_backend", fallback=AppConfig.ai_backend)
    enable_tasks = _getboolean(parser, "features", "enable_tasks", AppConfig.enable_tasks)
    enable_notes = _getboolean(parser, "features", "enable_notes", AppConfig.enable_notes)
    enable_outlook = _getboolean(parser, "features", "enable_outlook", AppConfig.enable_outlook)
    enable_history_panel = _getboolean(
        parser, "features", "enable_history_panel", AppConfig.enable_history_panel
    )
    enable_tray_icon = _getboolean(
        parser, "features", "enable_tray_icon", AppConfig.enable_tray_icon
    )
    window_mode = parser.get("features", "window_mode", fallback=AppConfig.window_mode)
    transparent_background = _getboolean(
        parser,
        "features",
        "transparent_background",
        AppConfig.transparent_background,
    )

    web_host = parser.get("web", "host", fallback=AppConfig.web_host)
    web_port = parser.getint("web", "port", fallback=AppConfig.web_port)
    web_debug = _getboolean(parser, "web", "debug", AppConfig.web_debug)
    auto_open_browser = _getboolean(
        parser,
        "web",
        "auto_open_browser",
        AppConfig.auto_open_browser,
    )
    open_browser_delay_seconds = parser.getfloat(
        "web",
        "open_browser_delay_seconds",
        fallback=AppConfig.open_browser_delay_seconds,
    )

    ollama_url = parser.get("ollama", "url", fallback=AppConfig.ollama_url)
    ollama_model = parser.get("ollama", "model", fallback=AppConfig.ollama_model)
    ollama_request_timeout_seconds = parser.getint(
        "ollama",
        "request_timeout_seconds",
        fallback=AppConfig.ollama_request_timeout_seconds,
    )
    ollama_agent_model = parser.get(
        "ollama",
        "agent_model",
        fallback=AppConfig.ollama_agent_model,
    )

    chatgpt_api_key_env_var = parser.get(
        "chatgpt", "api_key_env_var", fallback=AppConfig.chatgpt_api_key_env_var
    )
    chatgpt_model = parser.get("chatgpt", "model", fallback=AppConfig.chatgpt_model)
    chatgpt_timeout_seconds = parser.getint(
        "chatgpt", "timeout_seconds", fallback=AppConfig.chatgpt_timeout_seconds
    )

    copilot_enabled = _getboolean(parser, "copilot", "enabled", AppConfig.copilot_enabled)
    copilot_tenant_id = parser.get("copilot", "tenant_id", fallback=AppConfig.copilot_tenant_id)
    copilot_client_id = parser.get(
        "copilot", "client_id", fallback=AppConfig.copilot_client_id
    )
    copilot_client_secret_env_var = parser.get(
        "copilot",
        "client_secret_env_var",
        fallback=AppConfig.copilot_client_secret_env_var,
    )

    outlook_enabled = _getboolean(parser, "outlook", "enabled", AppConfig.outlook_enabled)
    outlook_default_task_folder = parser.get(
        "outlook", "default_task_folder", fallback=AppConfig.outlook_default_task_folder
    )
    outlook_read_inbox_folder = parser.get(
        "outlook", "read_inbox_folder", fallback=AppConfig.outlook_read_inbox_folder
    )
    outlook_max_emails = parser.getint(
        "outlook", "max_emails", fallback=AppConfig.outlook_max_emails
    )

    config = AppConfig(
        app_name=app_name,
        data_dir=str(Path(data_dir)),
        default_workspace=default_workspace,
        workspace_default_id=workspace_default_id,
        enable_ai=enable_ai,
        ai_backend=ai_backend,
        enable_tasks=enable_tasks,
        enable_notes=enable_notes,
        enable_outlook=enable_outlook,
        enable_history_panel=enable_history_panel,
        enable_tray_icon=enable_tray_icon,
        window_mode=window_mode,
        transparent_background=transparent_background,
        web_host=web_host,
        web_port=web_port,
        web_debug=web_debug,
        auto_open_browser=auto_open_browser,
        open_browser_delay_seconds=open_browser_delay_seconds,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        ollama_request_timeout_seconds=ollama_request_timeout_seconds,
        ollama_agent_model=ollama_agent_model,
        chatgpt_api_key_env_var=chatgpt_api_key_env_var,
        chatgpt_model=chatgpt_model,
        chatgpt_timeout_seconds=chatgpt_timeout_seconds,
        copilot_enabled=copilot_enabled,
        copilot_tenant_id=copilot_tenant_id,
        copilot_client_id=copilot_client_id,
        copilot_client_secret_env_var=copilot_client_secret_env_var,
        outlook_enabled=outlook_enabled,
        outlook_default_task_folder=outlook_default_task_folder,
        outlook_read_inbox_folder=outlook_read_inbox_folder,
        outlook_max_emails=outlook_max_emails,
    )

    LOGGER.debug("Configuration loaded: %s", config)
    return config


def save_config(config: AppConfig, config_path: str = "config.ini") -> None:
    config_file = Path(config_path)
    with config_file.open("w", encoding="utf-8") as handle:
        handle.write("[general]\n")
        handle.write(f"app_name = {config.app_name}\n")
        handle.write(f"data_dir = {config.data_dir}\n")
        handle.write(f"default_workspace = {config.default_workspace}\n")
        handle.write(f"workspace_default_id = {config.workspace_default_id}\n\n")

        handle.write("[features]\n")
        handle.write(f"enable_ai = {'true' if config.enable_ai else 'false'}\n")
        handle.write("# Current backend options:\n")
        handle.write("# - ollama\n")
        handle.write("# - dummy\n")
        handle.write("# Future planned options:\n")
        handle.write("# - openai\n")
        handle.write("# - azure_openai\n")
        handle.write("# - copilot\n")
        handle.write(f"ai_backend = {config.ai_backend}\n")
        handle.write(f"enable_tasks = {'true' if config.enable_tasks else 'false'}\n")
        handle.write(f"enable_notes = {'true' if config.enable_notes else 'false'}\n")
        handle.write(f"enable_outlook = {'true' if config.enable_outlook else 'false'}\n")
        handle.write(f"enable_history_panel = {'true' if config.enable_history_panel else 'false'}\n")
        handle.write(f"enable_tray_icon = {'true' if config.enable_tray_icon else 'false'}\n")
        handle.write(f"window_mode = {config.window_mode}\n")
        handle.write(f"transparent_background = {'true' if config.transparent_background else 'false'}\n\n")

        handle.write("[web]\n")
        handle.write(f"host = {config.web_host}\n")
        handle.write(f"port = {config.web_port}\n")
        handle.write(f"debug = {'true' if config.web_debug else 'false'}\n")
        handle.write(f"auto_open_browser = {'true' if config.auto_open_browser else 'false'}\n")
        handle.write(f"open_browser_delay_seconds = {config.open_browser_delay_seconds}\n\n")

        handle.write("[ollama]\n")
        handle.write(f"url = {config.ollama_url}\n")
        handle.write(f"model = {config.ollama_model}\n")
        handle.write(f"agent_model = {config.ollama_agent_model}\n")
        handle.write(f"request_timeout_seconds = {config.ollama_request_timeout_seconds}\n\n")

        handle.write("[chatgpt]\n")
        handle.write(f"api_key_env_var = {config.chatgpt_api_key_env_var}\n")
        handle.write(f"model = {config.chatgpt_model}\n")
        handle.write(f"timeout_seconds = {config.chatgpt_timeout_seconds}\n\n")

        handle.write("[copilot]\n")
        handle.write(f"enabled = {'true' if config.copilot_enabled else 'false'}\n")
        handle.write(f"tenant_id = {config.copilot_tenant_id}\n")
        handle.write(f"client_id = {config.copilot_client_id}\n")
        handle.write(f"client_secret_env_var = {config.copilot_client_secret_env_var}\n\n")

        handle.write("[outlook]\n")
        handle.write(f"enabled = {'true' if config.outlook_enabled else 'false'}\n")
        handle.write(f"default_task_folder = {config.outlook_default_task_folder}\n")
        handle.write(f"read_inbox_folder = {config.outlook_read_inbox_folder}\n")
        handle.write(f"max_emails = {config.outlook_max_emails}\n")
