"""Simple history panel for launched applications."""

from __future__ import annotations

from pathlib import Path
import tkinter as tk

from app.session_history import format_history_entry, read_session_history


class HistoryPanel:
    """A styled top-level window showing launch history entries."""

    def __init__(self, master: tk.Tk, history_file: Path) -> None:
        self._history_file = history_file
        self._window = tk.Toplevel(master)
        self._window.title("Session History")
        self._window.geometry("760x440")
        self._window.minsize(620, 340)
        self._window.configure(bg="#edf3f6")

        header = tk.Frame(self._window, bg="#113a52", padx=24, pady=20)
        header.pack(fill=tk.X)
        tk.Label(header, text="ACTIVITY LOG", bg="#113a52", fg="#a9c7d2",
                 font=("Arial", 8, "bold")).pack(anchor=tk.W)
        tk.Label(header, text="Session history", bg="#113a52", fg="white",
                 font=("Arial", 22, "bold")).pack(anchor=tk.W, pady=(5, 0))

        content = tk.Frame(self._window, bg="white", highlightbackground="#d9e0e6",
                           highlightthickness=1)
        content.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)
        self._listbox = tk.Listbox(content, bg="white", fg="#102230", bd=0,
                                   highlightthickness=0, selectbackground="#d9ecf2",
                                   selectforeground="#102230", font=("Arial", 10),
                                   activestyle="none")
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=16, pady=(16, 8))

        refresh_button = tk.Button(content, text="Refresh activity", command=self.refresh,
                                   bg="#113a52", fg="white", activebackground="#1f6678",
                                   activeforeground="white", relief=tk.FLAT, bd=0,
                                   font=("Arial", 9, "bold"), padx=16, pady=8,
                                   cursor="hand2")
        refresh_button.pack(anchor=tk.E, padx=16, pady=(0, 16))

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
