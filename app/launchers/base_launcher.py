"""Base abstractions for platform-specific application launchers."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
import json
import logging
from pathlib import Path
import subprocess

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class LaunchableApp:
    """Metadata describing an app that can be launched by the assistant."""

    id: str
    name: str
    command: list[str]
    category: str | None = None


class BaseLauncher(ABC):
    """Base class for app launchers that read apps from a shared registry file."""

    platform_key: str = ""

    def __init__(self, registry_path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parent
        self.registry_path = registry_path or (base_dir / "apps_registry.json")
        self._apps = self._load_registry()

    def list_apps(self) -> list[LaunchableApp]:
        """Return launchable apps for this platform."""

        return list(self._apps)

    def launch_app(self, app_id: str) -> LaunchableApp:
        """Launch an app by id and return its metadata if launch succeeds."""

        app = self.get_app(app_id)
        if app is None:
            raise ValueError(f"Unknown app id: {app_id}")

        self._start_process(app.command)
        LOGGER.info("Launched app %s (%s)", app.name, app.id)
        return app

    def get_app(self, app_id: str) -> LaunchableApp | None:
        """Get app metadata by identifier."""

        return next((app for app in self._apps if app.id == app_id), None)

    def _load_registry(self) -> list[LaunchableApp]:
        if not self.registry_path.exists():
            LOGGER.warning("Apps registry file not found: %s", self.registry_path)
            return []

        with self.registry_path.open("r", encoding="utf-8") as handle:
            raw_registry = json.load(handle)

        raw_apps = self._extract_raw_apps(raw_registry)
        apps: list[LaunchableApp] = []
        for item in raw_apps:
            command = self._build_command(item)
            if not command:
                LOGGER.warning("Skipping app '%s' with empty command", item.get("id", "<unknown>"))
                continue

            apps.append(
                LaunchableApp(
                    id=item["id"],
                    name=item["name"],
                    category=item.get("category"),
                    command=command,
                )
            )

        LOGGER.info("Loaded %d launchers for %s", len(apps), self.platform_key)
        return apps

    def _extract_raw_apps(self, raw_registry: dict[str, object]) -> list[dict[str, object]]:
        """Support both the new unified apps schema and legacy per-platform layout."""

        if isinstance(raw_registry.get("apps"), list):
            return [app for app in raw_registry["apps"] if isinstance(app, dict)]

        legacy_apps = raw_registry.get(self.platform_key, [])
        if isinstance(legacy_apps, list):
            return [app for app in legacy_apps if isinstance(app, dict)]
        return []

    def _build_command(self, item: dict[str, object]) -> list[str]:
        platform_command_key = f"{self.platform_key}_command"
        platform_command = item.get(platform_command_key)

        if isinstance(platform_command, str) and platform_command.strip():
            return self._shell_command(platform_command)

        legacy_command = item.get("command", [])
        if isinstance(legacy_command, str) and legacy_command.strip():
            return [legacy_command]
        if isinstance(legacy_command, list):
            return [str(part) for part in legacy_command if str(part).strip()]

        return []

    def _shell_command(self, command: str) -> list[str]:
        """Build a platform-appropriate shell command list from a command string."""

        if self.platform_key == "windows":
            return ["cmd.exe", "/c", command]
        return ["/bin/sh", "-lc", command]

    def _start_process(self, command: list[str]) -> subprocess.Popen[bytes]:
        """Start process in detached/background mode for current platform."""

        raise NotImplementedError
