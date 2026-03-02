# app/ui/main_window.py  (inside MainWindow.__init__)

import tkinter as tk
from tkinter import messagebox
import logging

class MainWindow:
    def __init__(self, root: tk.Tk, config, os_name: str) -> None:
        self.root = root
        self.config = config
        self.os_name = os_name
        self.logger = logging.getLogger(__name__)

        # ---- NEW: configure window as a slim top bar ----
        self._configure_window_appearance()

        self._build_menu()
        self._build_main_content()
        self._configure_close_handler()

    def _configure_window_appearance(self) -> None:
        """Configure the window to act like a slim top bar."""
        # Full width of screen, small height
        screen_width = self.root.winfo_screenwidth()
        bar_height = 80  # tweak to taste – 60–80 usually feels good

        # Position at top of screen, spanning full width
        self.root.geometry(f"{screen_width}x{bar_height}+0+0")

        # Optional: keep on top of other windows
        self.root.attributes("-topmost", True)

        # Optional: make background slightly transparent
        # 0.0 = fully transparent, 1.0 = fully opaque
        self.root.attributes("-alpha", 0.90)

        # Only allow horizontal resize (or disable resize completely)
        self.root.resizable(True, False)

        # Set title as before
        self.root.title(self.config.app_name)

""" """Tkinter main window for the Local Assistant application."""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

from app.config import AppConfig

LOGGER = logging.getLogger(__name__)


class MainWindow:
    """Primary window and menu system for the Local Assistant."""

    def __init__(self, root: tk.Tk, config: AppConfig, os_name: str) -> None:
        self.root = root
        self.config = config
        self.os_name = os_name

        self.root.title(self.config.app_name)
        self.root.geometry("900x600")

        self._build_menu()
        self._build_content()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        LOGGER.info("Main window initialized on %s", self.os_name)

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        file_menu.add_command(label="Exit", command=self.on_close)
        menu_bar.add_cascade(label="File", menu=file_menu)

        apps_menu = tk.Menu(menu_bar, tearoff=0)
        apps_menu.add_command(label="Launchers coming soon", command=self._not_implemented)
        menu_bar.add_cascade(label="Apps", menu=apps_menu)

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
"""

    def _build_main_content(self) -> None:
        """Create a minimal main content area."""
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Optional: a tiny status label instead of a big welcome message
        welcome_label = tk.Label(
            self.main_frame,
            text="",
        )
        welcome_label.pack(pady=2)

    #def _build_content(self) -> None:
    #    frame = tk.Frame(self.root)
    #    frame.pack(fill=tk.BOTH, expand=True)

    #    welcome_label = tk.Label(frame, text=f"Welcome to {self.config.app_name}")
    #    welcome_label.pack(pady=20)

    #    info_label = tk.Label(
    #        frame,
    #        text=(
    #            "Menus above will enable features like launching apps, AI chat, "
    #            "tasks, notes, and Outlook integration as phases progress."
    #        ),
    #        wraplength=600,
    #        justify=tk.CENTER,
    #    )
    #    info_label.pack(pady=10)

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

