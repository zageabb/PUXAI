"""Application entry point for the Local Assistant."""

from __future__ import annotations

import logging
import platform
import tkinter as tk
from enum import Enum

from app.config import AppConfig, load_config
from app.logging_setup import setup_logging
from app.ui.main_window import MainWindow


class OSName(Enum):
    """Enumeration of supported operating systems."""

    WINDOWS = "Windows"
    LINUX = "Linux"
    OTHER = "Other"


LOGGER = logging.getLogger(__name__)


def detect_os() -> OSName:
    """Detect the current operating system."""

    system_name = platform.system()
    if system_name == "Windows":
        return OSName.WINDOWS
    if system_name == "Linux":
        return OSName.LINUX
    return OSName.OTHER


def main() -> None:
    """Launch the Local Assistant application."""

    config: AppConfig = load_config()
    setup_logging(config.app_name)

    os_name = detect_os()
    LOGGER.info("Starting %s on %s", config.app_name, os_name.value)
    LOGGER.debug(
        "Feature flags: AI=%s, Tasks=%s, Notes=%s, Outlook=%s, Tray=%s",
        config.enable_ai,
        config.enable_tasks,
        config.enable_notes,
        config.enable_outlook,
        config.enable_tray_icon,
    )

    root = tk.Tk()
    MainWindow(root=root, config=config, os_name=os_name.value)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        LOGGER.info("Application interrupted by user")
    finally:
        LOGGER.info("Application shutting down")
        root.destroy()


if __name__ == "__main__":
    main()

