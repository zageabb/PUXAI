"""General Search-inspired AI chat workspace."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid
import webbrowser

from app.ai_backends import OpenAIBackend
from app.document_extraction import document_context


class AIChatPanel:
    """Persistent multi-chat UI with web research and file context."""

    COLORS = {
        "nav": "#0a1720", "brand": "#113a52", "teal": "#1f6678", "gold": "#d1a75c",
        "canvas": "#edf3f6", "surface": "#ffffff", "soft": "#f5f7fa", "border": "#d9e0e6",
        "ink": "#102230", "muted": "#62717e", "user": "#d9ecf2", "assistant": "#ffffff",
    }

    def __init__(self, master: tk.Tk, backend: OpenAIBackend, data_dir: Path) -> None:
        self.backend = backend
        self.data_dir = data_dir
        self.chat_file = data_dir / "ai_conversations.json"
        self.chats: list[dict] = self._load_chats()
        self.active_id: str | None = self.chats[0]["id"] if self.chats else None
        self.busy = False
        self.attached_context = ""
        self.attached_name = ""

        self.window = tk.Toplevel(master)
        self.window.title("PUX AI — Research Chat")
        self.window.geometry("1260x780")
        self.window.minsize(980, 640)
        self.window.configure(bg=self.COLORS["canvas"])
        self._build()
        if not self.active_id:
            self.new_chat()
        else:
            self.render()

    def _build(self) -> None:
        top = tk.Frame(self.window, bg=self.COLORS["nav"], height=64)
        top.pack(fill=tk.X)
        top.pack_propagate(False)
        tk.Label(top, text="AI", bg=self.COLORS["gold"], fg=self.COLORS["nav"],
                 font=("Arial", 10, "bold"), width=4, pady=8).pack(side=tk.LEFT, padx=(20, 12), pady=15)
        tk.Label(top, text="PUX AI Research", bg=self.COLORS["nav"], fg="white",
                 font=("Arial", 16, "bold")).pack(side=tk.LEFT)
        self.status = tk.Label(top, text="Ready", bg=self.COLORS["nav"], fg="#a9c7d2",
                               font=("Arial", 9, "bold"))
        self.status.pack(side=tk.RIGHT, padx=22)

        shell = tk.PanedWindow(self.window, orient=tk.HORIZONTAL, sashwidth=5, bg=self.COLORS["canvas"], bd=0)
        shell.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        sidebar = tk.Frame(shell, bg=self.COLORS["soft"], width=240)
        main = tk.Frame(shell, bg=self.COLORS["surface"], width=720)
        runtime = tk.Frame(shell, bg=self.COLORS["soft"], width=260)
        shell.add(sidebar, minsize=200)
        shell.add(main, minsize=520)
        shell.add(runtime, minsize=220)
        self._build_sidebar(sidebar)
        self._build_main(main)
        self._build_runtime(runtime)

    def _build_sidebar(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg=self.COLORS["soft"], padx=14, pady=15)
        header.pack(fill=tk.X)
        tk.Label(header, text="CONVERSATIONS", bg=self.COLORS["soft"], fg=self.COLORS["muted"],
                 font=("Arial", 8, "bold")).pack(anchor=tk.W)
        tk.Button(header, text="+ New chat", command=self.new_chat, bg=self.COLORS["brand"], fg="white",
                  activebackground=self.COLORS["teal"], activeforeground="white", relief=tk.FLAT,
                  bd=0, padx=12, pady=8, cursor="hand2").pack(fill=tk.X, pady=(10, 0))
        self.history = tk.Listbox(parent, bg=self.COLORS["soft"], fg=self.COLORS["ink"], bd=0,
                                  highlightthickness=0, selectbackground=self.COLORS["user"],
                                  selectforeground=self.COLORS["ink"], activestyle="none", font=("Arial", 10))
        self.history.pack(fill=tk.BOTH, expand=True, padx=9, pady=8)
        self.history.bind("<<ListboxSelect>>", self._select_chat)
        tk.Button(parent, text="Delete conversation", command=self.delete_chat, bg=self.COLORS["soft"],
                  fg="#8f1f1f", relief=tk.FLAT, bd=0, cursor="hand2").pack(pady=12)

    def _build_main(self, parent: tk.Frame) -> None:
        controls = tk.Frame(parent, bg=self.COLORS["surface"], padx=18, pady=13)
        controls.pack(fill=tk.X)
        heading = tk.Frame(controls, bg=self.COLORS["surface"])
        heading.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(heading, text="ACTIVE CONVERSATION", bg="white", fg=self.COLORS["muted"],
                 font=("Arial", 8, "bold")).pack(anchor=tk.W)
        self.title_label = tk.Label(heading, text="New research", bg="white", fg=self.COLORS["ink"],
                                    font=("Arial", 14, "bold"))
        self.title_label.pack(anchor=tk.W, pady=(3, 0))
        tk.Label(controls, text="Model", bg="white", fg=self.COLORS["muted"], font=("Arial", 8)).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value=self.backend.model)
        self.model_box = ttk.Combobox(controls, textvariable=self.model_var, width=18,
                                      values=(self.backend.model, "gpt-5.6", "gpt-5.6-mini"))
        self.model_box.pack(side=tk.LEFT, padx=(7, 0))

        conversation_frame = tk.Frame(parent, bg=self.COLORS["canvas"])
        conversation_frame.pack(fill=tk.BOTH, expand=True)
        self.conversation = tk.Text(conversation_frame, bg=self.COLORS["canvas"], fg=self.COLORS["ink"],
                                    bd=0, highlightthickness=0, wrap=tk.WORD, padx=22, pady=18,
                                    font=("Arial", 11), spacing1=3, spacing3=8, state=tk.DISABLED)
        scroll = ttk.Scrollbar(conversation_frame, command=self.conversation.yview)
        self.conversation.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.conversation.pack(fill=tk.BOTH, expand=True)
        self.conversation.tag_configure("user_label", foreground=self.COLORS["teal"], font=("Arial", 8, "bold"))
        self.conversation.tag_configure("assistant_label", foreground=self.COLORS["brand"], font=("Arial", 8, "bold"))
        self.conversation.tag_configure("body", foreground=self.COLORS["ink"], lmargin1=4, lmargin2=4)
        self.conversation.tag_configure("source", foreground="#15527f", font=("Arial", 9))
        self.conversation.tag_configure("empty", foreground=self.COLORS["muted"], justify=tk.CENTER,
                                        font=("Arial", 13))

        composer = tk.Frame(parent, bg=self.COLORS["surface"], padx=16, pady=14,
                            highlightbackground=self.COLORS["border"], highlightthickness=1)
        composer.pack(fill=tk.X)
        self.prompt = tk.Text(composer, height=4, wrap=tk.WORD, bd=0, highlightthickness=1,
                              highlightbackground=self.COLORS["border"], font=("Arial", 11), padx=10, pady=8)
        self.prompt.pack(fill=tk.X)
        self.prompt.bind("<Control-Return>", lambda _event: self.send())
        footer = tk.Frame(composer, bg="white")
        footer.pack(fill=tk.X, pady=(9, 0))
        self.context_label = tk.Label(footer, text="0 messages in context", bg="white",
                                      fg=self.COLORS["muted"], font=("Arial", 9))
        self.context_label.pack(side=tk.LEFT)
        self.send_button = tk.Button(footer, text="Send", command=self.send, bg=self.COLORS["brand"], fg="white",
                                     activebackground=self.COLORS["teal"], activeforeground="white", relief=tk.FLAT,
                                     bd=0, padx=22, pady=9, font=("Arial", 9, "bold"), cursor="hand2")
        self.send_button.pack(side=tk.RIGHT)

    def _build_runtime(self, parent: tk.Frame) -> None:
        tk.Label(parent, text="CAPABILITIES", bg=self.COLORS["soft"], fg=self.COLORS["muted"],
                 font=("Arial", 8, "bold")).pack(anchor=tk.W, padx=16, pady=(17, 10))
        self.web_var = tk.BooleanVar(value=True)
        tk.Checkbutton(parent, text="Automatic web research", variable=self.web_var, bg=self.COLORS["soft"],
                       fg=self.COLORS["ink"], activebackground=self.COLORS["soft"],
                       selectcolor=self.COLORS["surface"], font=("Arial", 10)).pack(anchor=tk.W, padx=13)
        tk.Label(parent, text="Uses current web sources and returns citations.", bg=self.COLORS["soft"],
                 fg=self.COLORS["muted"], wraplength=220, justify=tk.LEFT, font=("Arial", 9)).pack(anchor=tk.W, padx=16, pady=(3, 14))
        tk.Button(parent, text="Attach documents", command=self.attach_file, bg="white", fg=self.COLORS["brand"],
                  relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2").pack(fill=tk.X, padx=16)
        self.file_label = tk.Label(parent, text="No file attached", bg=self.COLORS["soft"], fg=self.COLORS["muted"],
                                   wraplength=220, justify=tk.LEFT, font=("Arial", 9))
        self.file_label.pack(anchor=tk.W, padx=16, pady=(7, 16))

        tk.Frame(parent, bg=self.COLORS["border"], height=1).pack(fill=tk.X, padx=16, pady=5)
        tk.Label(parent, text="LATEST RESULT", bg=self.COLORS["soft"], fg=self.COLORS["muted"],
                 font=("Arial", 8, "bold")).pack(anchor=tk.W, padx=16, pady=(12, 8))
        self.activity = tk.Label(parent, text="Ready for a question.", bg=self.COLORS["soft"], fg=self.COLORS["ink"],
                                 wraplength=220, justify=tk.LEFT, font=("Arial", 9))
        self.activity.pack(anchor=tk.W, padx=16)
        self.source_list = tk.Listbox(parent, height=7, bg="white", fg="#15527f", bd=0,
                                      highlightthickness=1, highlightbackground=self.COLORS["border"],
                                      font=("Arial", 9), activestyle="none")
        self.source_list.pack(fill=tk.X, padx=16, pady=12)
        self.source_list.bind("<Double-Button-1>", self._open_source)
        tk.Button(parent, text="Copy answer", command=self.copy_latest, bg="white", fg=self.COLORS["brand"],
                  relief=tk.FLAT, bd=0, padx=12, pady=8, cursor="hand2").pack(fill=tk.X, padx=16, pady=(0, 7))
        tk.Button(parent, text="Export Markdown", command=self.export_latest, bg=self.COLORS["brand"], fg="white",
                  activebackground=self.COLORS["teal"], activeforeground="white", relief=tk.FLAT,
                  bd=0, padx=12, pady=8, cursor="hand2").pack(fill=tk.X, padx=16)

    def _active(self) -> dict | None:
        return next((chat for chat in self.chats if chat["id"] == self.active_id), None)

    def new_chat(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        chat = {"id": uuid.uuid4().hex, "title": "New research", "created_at": now,
                "updated_at": now, "model": self.backend.model, "messages": []}
        self.chats.insert(0, chat)
        self.active_id = chat["id"]
        self.attached_context = ""
        self.attached_name = ""
        self._save_chats()
        self.render()
        self.prompt.focus_set()

    def delete_chat(self) -> None:
        chat = self._active()
        if not chat or self.busy:
            return
        if not messagebox.askyesno("Delete conversation", f"Delete “{chat['title']}”?", parent=self.window):
            return
        self.chats = [item for item in self.chats if item["id"] != chat["id"]]
        self.active_id = self.chats[0]["id"] if self.chats else None
        self._save_chats()
        if self.active_id:
            self.render()
        else:
            self.new_chat()

    def send(self) -> str:
        if self.busy:
            return "break"
        query = self.prompt.get("1.0", tk.END).strip()
        chat = self._active()
        if not query or not chat:
            return "break"
        if not self.backend.is_configured:
            messagebox.showerror("API key required", f"Set {self.backend.api_key_env_var} and restart PUX AI.", parent=self.window)
            return "break"
        content = query
        if self.attached_context:
            content += f"\n\nAttached file: {self.attached_name}\n---\n{self.attached_context}"
        chat["messages"].append({"role": "user", "content": content, "display": query})
        if len(chat["messages"]) == 1:
            chat["title"] = query[:52]
        chat["model"] = self.model_var.get().strip() or self.backend.model
        chat["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.prompt.delete("1.0", tk.END)
        self._set_busy(True)
        self._save_chats()
        self.render()
        messages = [{"role": item["role"], "content": item["content"]} for item in chat["messages"]]
        thread = threading.Thread(target=self._request, args=(chat["id"], messages, chat["model"], self.web_var.get()), daemon=True)
        thread.start()
        return "break"

    def _request(self, chat_id: str, messages: list[dict[str, str]], model: str, use_web: bool) -> None:
        try:
            result = self.backend.respond(messages, model=model, web_search=use_web)
            self.window.after(0, self._finish_request, chat_id, result.text, result.sources, result.usage, None)
        except Exception as exc:  # noqa: BLE001
            self.window.after(0, self._finish_request, chat_id, "", [], {}, str(exc))

    def _finish_request(self, chat_id: str, text: str, sources: list[dict[str, str]], usage: dict, error: str | None) -> None:
        chat = next((item for item in self.chats if item["id"] == chat_id), None)
        if chat:
            content = f"Request failed: {error}" if error else text
            chat["messages"].append({"role": "assistant", "content": content, "sources": sources, "usage": usage})
            chat["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._save_chats()
        self._set_busy(False)
        self.render()

    def render(self) -> None:
        chat = self._active()
        self.history.delete(0, tk.END)
        for index, item in enumerate(self.chats):
            self.history.insert(tk.END, f"{item['title']}  ·  {len(item['messages'])}")
            if item["id"] == self.active_id:
                self.history.selection_set(index)
        if not chat:
            return
        self.title_label.configure(text=chat["title"])
        self.model_var.set(chat.get("model") or self.backend.model)
        self.conversation.configure(state=tk.NORMAL)
        self.conversation.delete("1.0", tk.END)
        if not chat["messages"]:
            self.conversation.insert(tk.END, "\n\nWhat would you like to research?\n\nAsk a question, compare options, analyse an attached file, or request a sourced summary.", "empty")
        for message in chat["messages"]:
            role = message["role"]
            self.conversation.insert(tk.END, "YOU\n" if role == "user" else "PUX AI\n",
                                     "user_label" if role == "user" else "assistant_label")
            self.conversation.insert(tk.END, (message.get("display") or message["content"]) + "\n", "body")
            for source in message.get("sources", []):
                self.conversation.insert(tk.END, f"• {source['title']} — {source['url']}\n", "source")
            self.conversation.insert(tk.END, "\n")
        self.conversation.configure(state=tk.DISABLED)
        self.conversation.see(tk.END)
        self.context_label.configure(text=f"{len(chat['messages'])} messages in context · Ctrl+Enter to send")
        self._render_latest(chat)

    def _render_latest(self, chat: dict) -> None:
        latest = next((item for item in reversed(chat["messages"]) if item["role"] == "assistant"), None)
        self.source_list.delete(0, tk.END)
        if not latest:
            self.activity.configure(text="Ready for a question.")
            return
        usage = latest.get("usage", {})
        tokens = usage.get("total_tokens")
        self.activity.configure(text=f"Answer ready{f' · {tokens:,} tokens' if tokens else ''}. Double-click a source to open it.")
        for source in latest.get("sources", []):
            self.source_list.insert(tk.END, source["title"])

    def attach_file(self) -> None:
        paths = filedialog.askopenfilenames(parent=self.window, title="Attach documents",
                                            filetypes=(("Supported documents", "*.pdf *.docx *.xlsx *.csv *.txt *.md *.eml *.msg *.json *.py *.log"), ("All files", "*.*")))
        if not paths:
            return
        try:
            content, names = document_context([Path(path) for path in paths])
        except (OSError, ValueError, ImportError) as exc:
            messagebox.showerror("Could not attach documents", str(exc), parent=self.window)
            return
        self.attached_context = content
        self.attached_name = ", ".join(names)
        self.file_label.configure(text=f"{len(names)} document{'s' if len(names) != 1 else ''} attached\n{self.attached_name}\n{len(content):,} characters")

    def copy_latest(self) -> None:
        latest = self._latest_answer()
        if latest:
            self.window.clipboard_clear()
            self.window.clipboard_append(latest["content"])
            self.status.configure(text="Answer copied")

    def export_latest(self) -> None:
        latest = self._latest_answer()
        chat = self._active()
        if not latest or not chat:
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".md",
                                            initialfile="pux_ai_result.md", filetypes=(("Markdown", "*.md"),))
        if not path:
            return
        sources = "\n".join(f"- [{s['title']}]({s['url']})" for s in latest.get("sources", []))
        body = f"# {chat['title']}\n\n{latest['content']}\n"
        if sources:
            body += f"\n## Sources\n\n{sources}\n"
        Path(path).write_text(body, encoding="utf-8")
        self.status.configure(text="Markdown exported")

    def _latest_answer(self) -> dict | None:
        chat = self._active()
        return next((item for item in reversed(chat["messages"]) if item["role"] == "assistant"), None) if chat else None

    def _open_source(self, _event: tk.Event) -> None:
        latest = self._latest_answer()
        selected = self.source_list.curselection()
        if latest and selected and selected[0] < len(latest.get("sources", [])):
            webbrowser.open(latest["sources"][selected[0]]["url"])

    def _select_chat(self, _event: tk.Event) -> None:
        selection = self.history.curselection()
        if selection and not self.busy:
            self.active_id = self.chats[selection[0]]["id"]
            self.attached_context = ""
            self.attached_name = ""
            self.file_label.configure(text="No file attached")
            self.render()

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.send_button.configure(state=tk.DISABLED if busy else tk.NORMAL, text="Researching…" if busy else "Send")
        self.status.configure(text="Researching the web…" if busy and self.web_var.get() else "Thinking…" if busy else "Ready")

    def _load_chats(self) -> list[dict]:
        try:
            payload = json.loads(self.chat_file.read_text(encoding="utf-8"))
            return payload if isinstance(payload, list) else []
        except (OSError, ValueError):
            return []

    def _save_chats(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chat_file.write_text(json.dumps(self.chats[:40], indent=2), encoding="utf-8")
