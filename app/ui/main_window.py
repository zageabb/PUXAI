"""Tkinter main window for the Local Assistant application."""

from __future__ import annotations

import logging
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from app.config import AppConfig
from app.launchers import BaseLauncher
from app.session_history import append_launch_event
from app.ui.history_panel import HistoryPanel

LOGGER = logging.getLogger(__name__)


class MainWindow:
    """Primary window and menu system for the Local Assistant."""

    def __init__(
        self,
        root: tk.Tk,
        config: AppConfig,
        os_name: str,
        launcher: BaseLauncher | None,
        history_file: Path,
    ) -> None:
        self.root = root
        self.config = config
        self.os_name = os_name
        self.launcher = launcher
        self.history_file = history_file

        self.root.title(self.config.app_name)
        self._configure_window()

        self._build_menu()
        if self.config.window_mode != "menu_only":
            self._build_content()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        LOGGER.info("Main window initialized on %s", self.os_name)

    def _configure_window(self) -> None:
        window_mode = self.config.window_mode.lower().strip()
        if window_mode == "menu_only":
            self.root.geometry("420x80")
            self.root.minsize(320, 60)
        else:
            self.root.geometry("900x600")

        if self.config.transparent_background:
            self._try_enable_transparent_background()

    def _try_enable_transparent_background(self) -> None:
        # Tk transparency support depends heavily on OS/window manager.
        try:
            self.root.wm_attributes("-alpha", 0.9)
            LOGGER.info("Enabled translucent background with alpha 0.9")
        except tk.TclError:
            LOGGER.warning("Transparent background is not supported on this platform")

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.on_close)
        menu_bar.add_cascade(label="File", menu=file_menu)

        apps_menu = tk.Menu(menu_bar, tearoff=0)
        self._populate_apps_menu(apps_menu)
        menu_bar.add_cascade(label="Apps", menu=apps_menu)

        if self.config.enable_history_panel:
            history_menu = tk.Menu(menu_bar, tearoff=0)
            history_menu.add_command(label="Show Session History", command=self._open_history_panel)
            menu_bar.add_cascade(label="History", menu=history_menu)

        tasks_notes_menu = tk.Menu(menu_bar, tearoff=0)
        tasks_notes_menu.add_command(label="Tasks", command=self._not_implemented)
        tasks_notes_menu.add_command(label="Notes", command=self._not_implemented)
        if not (self.config.enable_tasks or self.config.enable_notes):
            menu_bar.add_cascade(label="Tasks & Notes", menu=tasks_notes_menu, state=tk.DISABLED)
        else:
            menu_bar.add_cascade(label="Tasks & Notes", menu=tasks_notes_menu)

        ai_menu = tk.Menu(menu_bar, tearoff=0)
        ai_menu.add_command(label="Open AI Assistant", command=self._not_implemented)
        if not self.config.enable_ai:
            menu_bar.add_cascade(label="AI Assistant", menu=ai_menu, state=tk.DISABLED)
        else:
            menu_bar.add_cascade(label="AI Assistant", menu=ai_menu)

        outlook_menu = tk.Menu(menu_bar, tearoff=0)
        outlook_menu.add_command(label="Outlook actions", command=self._not_implemented)
        if not self.config.enable_outlook:
            menu_bar.add_cascade(label="Outlook", menu=outlook_menu, state=tk.DISABLED)
        else:
            menu_bar.add_cascade(label="Outlook", menu=outlook_menu)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menu_bar)

    def _populate_apps_menu(self, apps_menu: tk.Menu) -> None:
        if self.launcher is None:
            apps_menu.add_command(label="No launcher for this OS", state=tk.DISABLED)
            return

        apps = self.launcher.list_apps()
        if not apps:
            apps_menu.add_command(label="No apps configured", state=tk.DISABLED)
            return

        for app in apps:
            apps_menu.add_command(
                label=app.name,
                command=lambda app_id=app.id: self._launch_app(app_id),
            )

    def _launch_app(self, app_id: str) -> None:
        if self.launcher is None:
            messagebox.showerror("Launcher unavailable", "This OS is not currently supported.")
            return

        try:
            app = self.launcher.launch_app(app_id)
            append_launch_event(self.history_file, app)
            LOGGER.info("Recorded launch event for %s", app.id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to launch app %s", app_id)
            messagebox.showerror("Launch failed", str(exc))

    def _open_history_panel(self) -> None:
        HistoryPanel(master=self.root, history_file=self.history_file)

    def _build_content(self) -> None:
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)

        welcome_label = tk.Label(frame, text=f"Welcome to {self.config.app_name}")
        welcome_label.pack(pady=20)

        info_label = tk.Label(
            frame,
            text=(
                "Menus above will enable features like launching apps, AI chat, "
                "tasks, notes, and Outlook integration as phases progress."
            ),
            wraplength=600,
            justify=tk.CENTER,
        )
        info_label.pack(pady=10)

    def _not_implemented(self) -> None:
        LOGGER.info("Feature not implemented yet")
        messagebox.showinfo("Coming soon", "This feature will be available in later phases.")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            f"{self.config.app_name}\nRunning on: {self.os_name}\n"
            "Features will appear as development progresses.",
        )

    def on_close(self) -> None:
        LOGGER.info("Closing application")
        self.root.destroy()
