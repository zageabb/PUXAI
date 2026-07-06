"""macOS launcher implementation."""

from __future__ import annotations

import subprocess

from app.launchers.base_launcher import BaseLauncher


class MacOSLauncher(BaseLauncher):
    """Launches configured apps on macOS."""

    platform_key = "macos"

    def _start_process(self, command: list[str]) -> subprocess.Popen[bytes]:
        return subprocess.Popen(command, start_new_session=True)  # noqa: S603
