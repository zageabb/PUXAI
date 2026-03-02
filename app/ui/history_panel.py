"""Simple history panel for launched applications."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

from app.session_history import format_history_entry, read_session_history


class HistoryPanel:
    """A basic top-level window showing launch history entries."""

    def __init__(self, master: tk.Tk, history_file: Path) -> None:
        self._history_file = history_file
        self._window = tk.Toplevel(master)
        self._window.title("Session History")
        self._window.geometry("650x320")

        self._listbox = tk.Listbox(self._window)
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 4))

        refresh_button = tk.Button(self._window, text="Refresh", command=self.refresh)
        refresh_button.pack(pady=(0, 10))

        self.refresh()

    def refresh(self) -> None:
        """Reload history from disk and update list display."""

        self._listbox.delete(0, tk.END)
        entries = read_session_history(self._history_file)
        if not entries:
            self._listbox.insert(tk.END, "No launches recorded yet.")
            return

        for entry in reversed(entries):
            self._listbox.insert(tk.END, format_history_entry(entry))
