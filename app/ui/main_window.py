"""Tender Designer-inspired main window for the Local Assistant application."""

from __future__ import annotations

import logging
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

from app.config import AppConfig
from app.ai_backends import OpenAIBackend
from app.launchers import BaseLauncher
from app.session_history import append_launch_event, read_session_history
from app.ui.history_panel import HistoryPanel
from app.ui.ai_chat_panel import AIChatPanel

LOGGER = logging.getLogger(__name__)


class MainWindow:
    """Primary window and dashboard for the Local Assistant."""

    COLORS = {
        "nav": "#0a1720",
        "brand": "#113a52",
        "teal": "#1f6678",
        "gold": "#d1a75c",
        "gold_light": "#eed7ae",
        "canvas": "#edf3f6",
        "surface": "#ffffff",
        "surface_soft": "#f8fbfd",
        "border": "#d9e0e6",
        "ink": "#102230",
        "muted": "#62717e",
        "white": "#ffffff",
        "success": "#1f6a42",
    }

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
        self.ai_backend = OpenAIBackend(
            api_key_env_var=config.chatgpt_api_key_env_var,
            model=config.chatgpt_model,
            timeout_seconds=config.chatgpt_timeout_seconds,
        )

        self.root.title(self.config.app_name)
        self._configure_window()
        self._build_menu()
        if self.config.window_mode != "menu_only":
            self._build_content()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        LOGGER.info("Main window initialized on %s", self.os_name)

    def _configure_window(self) -> None:
        if self.config.window_mode.lower().strip() == "menu_only":
            self.root.geometry("520x90")
            self.root.minsize(420, 70)
        else:
            self.root.geometry("1180x760")
            self.root.minsize(940, 650)
        self.root.configure(bg=self.COLORS["canvas"])
        if self.config.transparent_background:
            self._try_enable_transparent_background()

    def _try_enable_transparent_background(self) -> None:
        try:
            self.root.wm_attributes("-alpha", 0.96)
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

        tasks_menu = tk.Menu(menu_bar, tearoff=0)
        tasks_menu.add_command(label="Tasks", command=self._not_implemented)
        tasks_menu.add_command(label="Notes", command=self._not_implemented)
        menu_bar.add_cascade(label="Tasks & Notes", menu=tasks_menu,
                             state=tk.NORMAL if (self.config.enable_tasks or self.config.enable_notes) else tk.DISABLED)

        ai_menu = tk.Menu(menu_bar, tearoff=0)
        ai_menu.add_command(label="Open AI Assistant", command=self._open_ai_chat)
        menu_bar.add_cascade(label="AI Assistant", menu=ai_menu,
                             state=tk.NORMAL if self.config.enable_ai else tk.DISABLED)

        outlook_menu = tk.Menu(menu_bar, tearoff=0)
        outlook_menu.add_command(label="Outlook actions", command=self._not_implemented)
        menu_bar.add_cascade(label="Outlook", menu=outlook_menu,
                             state=tk.NORMAL if self.config.enable_outlook else tk.DISABLED)

        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu_bar)

    def _populate_apps_menu(self, menu: tk.Menu) -> None:
        apps = self.launcher.list_apps() if self.launcher else []
        if not apps:
            menu.add_command(label="No apps available", state=tk.DISABLED)
            return
        for app in apps:
            menu.add_command(label=app.name, command=lambda app_id=app.id: self._launch_app(app_id))

    def _build_content(self) -> None:
        self._build_navbar()
        body = tk.Frame(self.root, bg=self.COLORS["canvas"])
        body.pack(fill=tk.BOTH, expand=True, padx=28, pady=24)
        self._build_hero(body)
        self._build_metrics(body)
        self._build_workspace(body)

    def _build_navbar(self) -> None:
        nav = tk.Frame(self.root, bg=self.COLORS["nav"], height=68)
        nav.pack(fill=tk.X)
        nav.pack_propagate(False)

        mark = tk.Label(nav, text="PUX", bg=self.COLORS["gold"], fg=self.COLORS["nav"],
                        font=("Arial", 10, "bold"), width=4, pady=9)
        mark.pack(side=tk.LEFT, padx=(26, 12), pady=16)
        tk.Label(nav, text=self.config.app_name, bg=self.COLORS["nav"], fg="white",
                 font=("Arial", 17, "bold")).pack(side=tk.LEFT)

        for label, command in reversed([
            ("Dashboard", lambda: None),
            ("AI Research", self._open_ai_chat),
            ("History", self._open_history_panel),
            ("Settings", self._not_implemented),
        ]):
            tk.Button(nav, text=label, command=command, bg=self.COLORS["nav"], fg="#d8e2e8",
                      activebackground=self.COLORS["brand"], activeforeground="white",
                      relief=tk.FLAT, bd=0, font=("Arial", 10, "bold"), padx=13,
                      cursor="hand2").pack(side=tk.RIGHT, padx=(0, 7), pady=17)

    def _build_hero(self, parent: tk.Widget) -> None:
        hero = tk.Frame(parent, bg=self.COLORS["brand"], padx=30, pady=25)
        hero.pack(fill=tk.X, pady=(0, 18))
        copy = tk.Frame(hero, bg=self.COLORS["brand"])
        copy.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(copy, text="PERSONAL OPERATIONS BOARD", bg=self.COLORS["brand"], fg="#a9c7d2",
                 font=("Arial", 9, "bold")).pack(anchor=tk.W)
        tk.Label(copy, text="Your command centre", bg=self.COLORS["brand"], fg="white",
                 font=("Arial", 28, "bold")).pack(anchor=tk.W, pady=(7, 5))
        tk.Label(copy, text="Launch tools, review recent activity and keep everyday work moving from one place.",
                 bg=self.COLORS["brand"], fg="#d9e8ed", font=("Arial", 11),
                 wraplength=650, justify=tk.LEFT).pack(anchor=tk.W)
        tk.Button(hero, text="View activity", command=self._open_history_panel,
                  bg=self.COLORS["gold_light"], fg=self.COLORS["ink"], activebackground=self.COLORS["gold"],
                  relief=tk.FLAT, bd=0, font=("Arial", 10, "bold"), padx=20, pady=12,
                  cursor="hand2").pack(side=tk.RIGHT, padx=(20, 0))

    def _build_metrics(self, parent: tk.Widget) -> None:
        row = tk.Frame(parent, bg=self.COLORS["canvas"])
        row.pack(fill=tk.X, pady=(0, 18))
        apps = self.launcher.list_apps() if self.launcher else []
        launches = read_session_history(self.history_file)
        metrics = [
            ("AVAILABLE APPS", str(len(apps)), "Ready to launch"),
            ("SESSION ACTIVITY", str(len(launches)), "Recorded launches"),
            ("AI ASSISTANT", "Ready" if self.config.enable_ai else "Off", self.config.ai_backend.title()),
            ("SYSTEM", self.os_name, "Local workspace"),
        ]
        for index, (label, value, note) in enumerate(metrics):
            card = tk.Frame(row, bg=self.COLORS["surface"], highlightbackground=self.COLORS["border"],
                            highlightthickness=1, padx=18, pady=15)
            card.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 7, 0 if index == 3 else 7))
            row.grid_columnconfigure(index, weight=1)
            tk.Label(card, text=label, bg="white", fg=self.COLORS["muted"],
                     font=("Arial", 8, "bold")).pack(anchor=tk.W)
            tk.Label(card, text=value, bg="white", fg=self.COLORS["ink"],
                     font=("Arial", 20, "bold")).pack(anchor=tk.W, pady=(6, 2))
            tk.Label(card, text=note, bg="white", fg=self.COLORS["muted"],
                     font=("Arial", 9)).pack(anchor=tk.W)

    def _build_workspace(self, parent: tk.Widget) -> None:
        panel = tk.Frame(parent, bg=self.COLORS["surface"], highlightbackground=self.COLORS["border"],
                         highlightthickness=1)
        panel.pack(fill=tk.BOTH, expand=True)
        header = tk.Frame(panel, bg=self.COLORS["surface_soft"], padx=20, pady=15)
        header.pack(fill=tk.X)
        tk.Label(header, text="Application workspace", bg=self.COLORS["surface_soft"],
                 fg=self.COLORS["ink"], font=("Arial", 13, "bold")).pack(side=tk.LEFT)
        tk.Label(header, text="SELECT A TOOL TO BEGIN", bg=self.COLORS["surface_soft"],
                 fg=self.COLORS["muted"], font=("Arial", 8, "bold")).pack(side=tk.RIGHT)

        grid = tk.Frame(panel, bg=self.COLORS["surface"], padx=18, pady=18)
        grid.pack(fill=tk.BOTH, expand=True)
        apps = self.launcher.list_apps() if self.launcher else []
        if not apps:
            tk.Label(grid, text="No local applications are configured for this operating system.", bg="white",
                     fg=self.COLORS["muted"], font=("Arial", 11)).grid(row=0, column=0,
                                                                        columnspan=3, pady=(8, 18))
            features = [
                ("AI", "AI Research", self.config.enable_ai),
                ("TN", "Tasks & Notes", self.config.enable_tasks or self.config.enable_notes),
                ("OL", "Outlook", self.config.enable_outlook),
            ]
            for column, (initials, name, enabled) in enumerate(features):
                card = tk.Frame(grid, bg=self.COLORS["surface_soft"], highlightbackground=self.COLORS["border"],
                                highlightthickness=1, padx=16, pady=15)
                card.grid(row=1, column=column, sticky="nsew", padx=7, pady=7)
                tk.Label(card, text=initials, bg=self.COLORS["brand"], fg="white",
                         font=("Arial", 9, "bold"), width=4, pady=7).pack(side=tk.LEFT, padx=(0, 12))
                tk.Label(card, text=name, bg=self.COLORS["surface_soft"], fg=self.COLORS["ink"],
                         font=("Arial", 11, "bold")).pack(side=tk.LEFT)
                command = self._open_ai_chat if name == "AI Research" else self._not_implemented
                tk.Button(card, text="Open" if enabled else "Off", command=command,
                          state=tk.NORMAL if enabled else tk.DISABLED, bg=self.COLORS["brand"], fg="white",
                          activebackground=self.COLORS["teal"], activeforeground="white", relief=tk.FLAT,
                          bd=0, padx=13, pady=7, font=("Arial", 9, "bold"), cursor="hand2").pack(side=tk.RIGHT)
            return
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1, uniform="apps")
        for index, app in enumerate(apps):
            card = tk.Frame(grid, bg=self.COLORS["surface_soft"], highlightbackground=self.COLORS["border"],
                            highlightthickness=1, padx=16, pady=15)
            card.grid(row=index // 3, column=index % 3, sticky="nsew", padx=7, pady=7)
            badge = tk.Label(card, text=app.name[:2].upper(), bg=self.COLORS["brand"], fg="white",
                             font=("Arial", 9, "bold"), width=4, pady=7)
            badge.pack(side=tk.LEFT, padx=(0, 12))
            text = tk.Frame(card, bg=self.COLORS["surface_soft"])
            text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            tk.Label(text, text=app.name, bg=self.COLORS["surface_soft"], fg=self.COLORS["ink"],
                     font=("Arial", 11, "bold")).pack(anchor=tk.W)
            tk.Label(text, text="Available locally", bg=self.COLORS["surface_soft"], fg=self.COLORS["success"],
                     font=("Arial", 8)).pack(anchor=tk.W, pady=(3, 0))
            tk.Button(card, text="Open", command=lambda app_id=app.id: self._launch_app(app_id),
                      bg=self.COLORS["brand"], fg="white", activebackground=self.COLORS["teal"],
                      activeforeground="white", relief=tk.FLAT, bd=0, padx=13, pady=7,
                      font=("Arial", 9, "bold"), cursor="hand2").pack(side=tk.RIGHT)

    def _launch_app(self, app_id: str) -> None:
        if self.launcher is None:
            messagebox.showerror("Launcher unavailable", "This OS is not currently supported.")
            return
        try:
            app = self.launcher.launch_app(app_id)
            append_launch_event(self.history_file, app)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Failed to launch app %s", app_id)
            messagebox.showerror("Launch failed", str(exc))

    def _open_history_panel(self) -> None:
        HistoryPanel(master=self.root, history_file=self.history_file)

    def _open_ai_chat(self) -> None:
        if not self.config.enable_ai:
            messagebox.showinfo("AI disabled", "Enable AI in config.ini to use Research Chat.")
            return
        AIChatPanel(master=self.root, backend=self.ai_backend, data_dir=Path(self.config.data_dir))

    def _not_implemented(self) -> None:
        messagebox.showinfo("Coming soon", "This feature will be available in a later phase.")

    def _show_about(self) -> None:
        messagebox.showinfo("About", f"{self.config.app_name}\nRunning on: {self.os_name}")

    def on_close(self) -> None:
        LOGGER.info("Closing application")
        self.root.destroy()
