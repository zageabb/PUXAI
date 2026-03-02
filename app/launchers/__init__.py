"""Launcher package exports and factory helpers."""

from __future__ import annotations

from app.launchers.base_launcher import BaseLauncher, LaunchableApp
from app.launchers.linux_launcher import LinuxLauncher
from app.launchers.windows_launcher import WindowsLauncher


def create_launcher(os_name: str) -> BaseLauncher | None:
    """Create a launcher implementation for the detected OS name."""

    normalized = os_name.lower().strip()
    if normalized == "windows":
        return WindowsLauncher()
    if normalized == "linux":
        return LinuxLauncher()
    return None


__all__ = ["BaseLauncher", "LaunchableApp", "LinuxLauncher", "WindowsLauncher", "create_launcher"]
