"""Windows launcher implementation."""

from __future__ import annotations

import subprocess

from app.launchers.base_launcher import BaseLauncher


class WindowsLauncher(BaseLauncher):
    """Launches configured apps on Windows."""

    platform_key = "windows"

    def _start_process(self, command: list[str]) -> subprocess.Popen[bytes]:
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen(command, creationflags=creationflags)  # noqa: S603
