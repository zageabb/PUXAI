"""Configuration loading utilities for the Local Assistant application."""

from __future__ import annotations

import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Final

LOGGER: Final = logging.getLogger(__name__)


@dataclass
class AppConfig:
    """Application configuration loaded from ``config.ini``.

    Attributes:
        app_name: Human-friendly application name for window titles and logs.
        data_dir: Directory where JSON data files and logs may be stored.
        enable_ai: Flag indicating whether AI features are enabled.
        ai_backend: Selected AI backend identifier (``none``, ``chatgpt``, ``copilot``).
        enable_tasks: Flag indicating whether task management features are enabled.
        enable_notes: Flag indicating whether notes features are enabled.
        enable_outlook: Flag indicating whether Outlook integration is enabled.
        enable_history_panel: Flag indicating whether the history panel is visible.
        enable_tray_icon: Flag indicating whether the system tray icon is enabled.
        chatgpt_api_key_env_var: Environment variable name holding the ChatGPT API key.
        chatgpt_model: Default model identifier for ChatGPT interactions.
        chatgpt_timeout_seconds: Timeout in seconds for ChatGPT requests.
        copilot_enabled: Flag for Microsoft Copilot integration readiness.
        copilot_tenant_id: Azure AD tenant ID for Copilot/MS Graph authentication.
        copilot_client_id: Client ID for Copilot/MS Graph authentication.
        copilot_client_secret_env_var: Environment variable holding the Copilot secret.
        outlook_enabled: Flag indicating if Outlook integration is active.
        outlook_default_task_folder: Default Outlook tasks folder name.
        outlook_read_inbox_folder: Outlook inbox folder name to read from.
        outlook_max_emails: Maximum number of emails to fetch when reading inbox.
    """

    app_name: str = "Local Assistant"
    data_dir: str = "./app/data"

    enable_ai: bool = True
    ai_backend: str = "chatgpt"
    enable_tasks: bool = True
    enable_notes: bool = True
    enable_outlook: bool = True
    enable_history_panel: bool = True
    enable_tray_icon: bool = True

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
        enable_ai=enable_ai,
        ai_backend=ai_backend,
        enable_tasks=enable_tasks,
        enable_notes=enable_notes,
        enable_outlook=enable_outlook,
        enable_history_panel=enable_history_panel,
        enable_tray_icon=enable_tray_icon,
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

