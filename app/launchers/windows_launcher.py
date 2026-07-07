"""Windows launcher implementation."""

from __future__ import annotations

import subprocess

from app.launchers.base_launcher import BaseLauncher, LaunchableApp


class WindowsLauncher(BaseLauncher):
    """Launches configured apps on Windows."""

    platform_key = "windows"

    def launch_app(self, app_id: str) -> LaunchableApp:
        """Launch an app by id and return its metadata if launch succeeds."""

        app = self.get_app(app_id)
        if app is None:
            raise ValueError(f"Unknown app id: {app_id}")

        self._launch_windows_app(app)
        return app

    def _start_process(self, command: list[str]) -> subprocess.Popen[bytes]:
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        return subprocess.Popen(command, creationflags=creationflags)  # noqa: S603

    def _launch_windows_app(self, app: LaunchableApp) -> None:
        """Use the Windows shell for command resolution and protocol handlers."""

        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        if app.raw_command:
            subprocess.Popen(  # noqa: S602
                app.raw_command,
                shell=True,
                creationflags=creationflags,
            )
            return

        self._start_process(app.command)
