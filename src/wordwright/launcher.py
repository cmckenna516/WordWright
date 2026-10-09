from __future__ import annotations

import ctypes
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

from .settings import SettingsStore
from .sounds import SoundPlayer


class LauncherWindow:
    """Wordwright's compact, old-school desktop launcher."""

    _BACKGROUND = "#171919"
    _SIDEBAR = "#121414"
    _TITLEBAR = "#242624"
    _PANEL = "#101212"
    _PANEL_ACTIVE = "#2b2921"
    _BORDER = "#3b3b35"
    _TEXT = "#f2ecdc"
    _BODY = "#c3c0b6"
    _MUTED = "#87887f"
    _ACCENT = "#d6a84b"
    _STATE_COLORS = {
        "Loading model": "#d6a84b",
        "Idle": "#87a975",
        "Recording": "#f08b7e",
        "Transcribing": "#78b8e9",
        "Paste sent": "#79c78b",
        "Copied to clipboard": "#e1b75e",
        "Error": "#d98bd9",
    }
    _STATE_COPY = {
        "Loading model": "Preparing the local scribe…",
        "Idle": "Ready to write",
        "Recording": "Recording",
        "Transcribing": "Setting your words in type…",
        "Paste sent": "Paste command sent",
        "Copied to clipboard": "No text field found — copied to clipboard",
        "Error": "Something needs attention",
    }

    def __init__(
        self,
        root: tk.Tk,
        settings: SettingsStore,
        sounds: SoundPlayer,
        on_toggle: Callable[[], None],
        on_quit: Callable[[], None],
        on_settings_changed: Callable[[], None],
    ) -> None:
        self._root = root
        self._settings = settings
        self._sounds = sounds
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._on_settings_changed = on_settings_changed
        self._state = "Loading model"
        self._pages: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, tk.Button] = {}
        self._configure_root()
        self._build_shell()
        self.show_page("dictate")

    def _configure_root(self) -> None:
        self._root.title("Wordwright")
        self._root.geometry("850x560")
        self._root.minsize(760, 520)
        self._root.configure(bg=self._BACKGROUND)
        self._root.protocol("WM_DELETE_WINDOW", self.hide)
        self._root.after(0, self._apply_dark_titlebar)

    def _apply_dark_titlebar(self) -> None:
        if os.name != "nt":
            return
        try:
            self._root.update_idletasks()
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                self._root.winfo_id(), 20, ctypes.byref(value), ctypes.sizeof(value)
            )
        except (AttributeError, OSError, tk.TclError):
            pass

    def _build_shell(self) -> None:
        shell = tk.Frame(
            self._root,
            bg=self._BACKGROUND,
            highlightbackground="#4c4a42",
            highlightthickness=1,
        )
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, height=48, bg=self._TITLEBAR)
        header.pack(fill="x")
        header.pack_propagate(False)
        self._build_wordmark(header)
        tk.Label(
            header,
            text="LOCAL DICTATION",
            bg=self._TITLEBAR,
            fg=self._MUTED,
            font=("Courier New", 8),
        ).pack(side="right", padx=17)

        body = tk.Frame(shell, bg=self._BACKGROUND)
        body.pack(fill="both", expand=True)
        sidebar = tk.Frame(body, width=176, bg=self._SIDEBAR)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        for key, label, glyph in (
            ("dictate", "Dictate", "●"),
            ("settings", "Settings", "⚙"),
            ("history", "History", "▤"),
            ("stats", "Stats", "▥"),
        ):
            button = tk.Button(
                sidebar,
                text=f" {glyph}   {label}",
                anchor="w",
                padx=12,
                pady=10,
                bd=0,
                relief="flat",
                bg=self._SIDEBAR,
                fg=self._MUTED,
                activebackground=self._PANEL_ACTIVE,
                activeforeground=self._TEXT,
                font=("Trebuchet MS", 9),
                command=lambda page=key: self.show_page(page),
            )
            button.pack(fill="x", padx=10, pady=2)
            self._nav_buttons[key] = button

        tk.Button(
            sidebar,
            text="×   Quit Wordwright",
            anchor="w",
            padx=14,
            pady=9,
            bd=0,
            relief="flat",
            bg=self._SIDEBAR,
            fg=self._MUTED,
            activebackground=self._PANEL_ACTIVE,
            activeforeground=self._TEXT,
            font=("Courier New", 8),
            command=self._on_quit,
        ).pack(side="bottom", fill="x", padx=10, pady=12)

        content = tk.Frame(body, bg=self._BACKGROUND)
        content.pack(side="left", fill="both", expand=True)
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        self._pages["dictate"] = self._build_dictate(content)
        self._pages["settings"] = self._build_settings(content)
        self._pages["history"] = self._build_future_page(
            content,
            "Optional local archive",
            "History is off.",
            "Nothing is saved unless you explicitly choose a local folder and enable history.",
            "Local search, corrections, retention controls, mind maps, and exports will live here.",
        )
        self._pages["stats"] = self._build_future_page(
            content,
            "Private local insights",
            "Stats are coming later.",
            "Usage summaries will remain on this machine and can be disabled.",
            "Words dictated, time saved, vocabulary, and exportable trends will live here.",
        )
        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        footer = tk.Frame(shell, height=30, bg="#111313")
        footer.pack(fill="x")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text="WORDWRIGHT 0.1",
            bg="#111313",
            fg="#71736d",
            font=("Courier New", 8),
        ).pack(side="left", padx=12)
        tk.Label(
            footer,
            text="Everything stays on this machine",
            bg="#111313",
            fg="#71736d",
            font=("Courier New", 8),
        ).pack(side="right", padx=12)

    def _build_wordmark(self, parent: tk.Widget) -> None:
        mark = tk.Canvas(parent, width=28, height=28, bg=self._TITLEBAR, highlightthickness=0)
        mark.pack(side="left", padx=(14, 5))
        mark.create_line(8, 21, 20, 7, fill=self._ACCENT, width=2)
        mark.create_line(13, 15, 22, 6, fill=self._ACCENT, width=4)
        mark.create_line(8, 22, 19, 22, fill="#9a7035", width=1)
        tk.Label(
            parent,
            text="WORDWRIGHT",
            bg=self._TITLEBAR,
            fg=self._TEXT,
            font=("Georgia", 11, "bold"),
        ).pack(side="left")

    def _page(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(parent, bg=self._BACKGROUND, padx=42, pady=32)

    def _heading(self, parent: tk.Widget, eyebrow: str, title: str, copy: str) -> None:
        tk.Label(
            parent,
            text=eyebrow.upper(),
            bg=self._BACKGROUND,
            fg=self._ACCENT,
            font=("Courier New", 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            parent,
            text=title,
            bg=self._BACKGROUND,
            fg=self._TEXT,
            font=("Georgia", 22),
        ).pack(anchor="w", pady=(7, 5))
        tk.Label(
            parent,
            text=copy,
            bg=self._BACKGROUND,
            fg=self._MUTED,
            justify="left",
            wraplength=555,
            font=("Trebuchet MS", 9),
        ).pack(anchor="w")

    def _build_dictate(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        self._heading(
            page,
            "Local dictation utility",
            "Ready at your command.",
            "Press the hotkey, speak naturally, and Wordwright places the finished text where you left your cursor.",
        )
        status_panel = tk.Frame(
            page,
            bg=self._PANEL,
            highlightbackground=self._BORDER,
            highlightthickness=1,
            padx=15,
            pady=14,
        )
        status_panel.pack(fill="x", pady=(28, 0))
        self._status_orb = tk.Canvas(status_panel, width=18, height=18, bg=self._PANEL, highlightthickness=0)
        self._status_orb.pack(side="left", padx=(0, 9))
        self._orb_id = self._status_orb.create_oval(
            4, 4, 14, 14, fill=self._STATE_COLORS["Loading model"], outline=""
        )
        state_copy = tk.Frame(status_panel, bg=self._PANEL)
        state_copy.pack(side="left", fill="x", expand=True)
        tk.Label(
            state_copy,
            text="CURRENT STATE",
            bg=self._PANEL,
            fg=self._MUTED,
            font=("Courier New", 7),
        ).pack(anchor="w")
        self._status_label = tk.Label(
            state_copy,
            text=self._STATE_COPY["Loading model"],
            bg=self._PANEL,
            fg=self._STATE_COLORS["Loading model"],
            font=("Trebuchet MS", 9),
        )
        self._status_label.pack(anchor="w", pady=(3, 0))
        self._hotkey_keys(status_panel)

        self._record_button = tk.Button(
            page,
            text="●  Start dictation",
            padx=16,
            pady=10,
            bd=0,
            relief="flat",
            bg=self._ACCENT,
            fg="#1b160b",
            activebackground="#e2bc66",
            activeforeground="#1b160b",
            disabledforeground="#88887f",
            font=("Trebuchet MS", 9, "bold"),
            command=self._on_toggle,
        )
        self._record_button.pack(anchor="w", pady=(16, 0))

        details = tk.Frame(page, bg=self._BACKGROUND)
        details.pack(fill="x", side="bottom")
        for index, (label, value) in enumerate(
            (
                ("SCRIBE", "small.en · local"),
                ("PRIVACY", "History is off"),
                ("OVERLAY", "Closed scroll while idle"),
            )
        ):
            block = tk.Frame(details, bg=self._BACKGROUND)
            block.pack(side="left", fill="x", expand=True, padx=(0 if index == 0 else 10, 0))
            tk.Label(
                block,
                text=label,
                bg=self._BACKGROUND,
                fg=self._MUTED,
                font=("Courier New", 7),
            ).pack(anchor="w")
            value_label = tk.Label(
                block,
                text=value,
                bg=self._BACKGROUND,
                fg=self._BODY,
                font=("Trebuchet MS", 8),
            )
            value_label.pack(anchor="w", pady=(5, 0))
            if label == "PRIVACY":
                self._history_card = value_label
        return page

    def _hotkey_keys(self, parent: tk.Widget) -> None:
        for index, key in enumerate(("CTRL", "ALT", "SPACE")):
            if index:
                tk.Label(parent, text="+", bg=self._PANEL, fg=self._MUTED, font=("Courier New", 8)).pack(side="left", padx=3)
            tk.Label(
                parent,
                text=key,
                bg="#292b29",
                fg="#c9c4b7",
                padx=6,
                pady=4,
                font=("Courier New", 7),
                highlightbackground="#4b4d46",
                highlightthickness=1,
            ).pack(side="left")

    def _build_future_page(
        self,
        parent: tk.Widget,
        eyebrow: str,
        title: str,
        copy: str,
        planned: str,
    ) -> tk.Frame:
        page = self._page(parent)
        self._heading(page, eyebrow, title, copy)
        panel = tk.Frame(
            page,
            bg=self._PANEL,
            highlightbackground=self._BORDER,
            highlightthickness=1,
            padx=22,
            pady=22,
        )
        panel.pack(fill="x", pady=(28, 0))
        tk.Label(
            panel,
            text="PLANNED FOR A LATER BUILD",
            bg=self._PANEL,
            fg=self._ACCENT,
            font=("Courier New", 8, "bold"),
        ).pack(anchor="w")
        tk.Label(
            panel,
            text=planned,
            bg=self._PANEL,
            fg=self._MUTED,
            justify="left",
            wraplength=500,
            font=("Trebuchet MS", 9),
        ).pack(anchor="w", pady=(9, 0))
        return page

    def _build_settings(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        self._heading(page, "Preferences", "Settings", "Keep the utility quiet, local, and easy to understand.")
        settings = self._settings.snapshot()
        self._overlay_var = tk.BooleanVar(value=settings.show_overlay_always)
        self._sounds_var = tk.BooleanVar(value=settings.sounds_enabled)
        self._position_var = tk.StringVar(value=settings.overlay_position)
        body = tk.Frame(page, bg=self._BACKGROUND)
        body.pack(fill="both", expand=True, pady=(18, 0))
        self._section_label(body, "OVERLAY")
        self._check_row(
            body,
            "Keep the scroll available",
            "When off, the overlay appears only while Wordwright is actively working.",
            self._overlay_var,
            self._save_overlay_visibility,
        )
        self._option_row(
            body,
            "Overlay position",
            self._position_var,
            {
                "Top center": "top_center",
                "Bottom center": "bottom_center",
                "Left center": "left_center",
                "Right center": "right_center",
            },
            self._save_overlay_position,
        )
        self._section_label(body, "SOUNDS", top=17)
        self._check_row(
            body,
            "Enable sound cues",
            "Optional local WAV files play when recording starts and stops.",
            self._sounds_var,
            self._save_sounds_enabled,
        )
        self._sound_row(body, "Start sound", "start_sound_path")
        self._sound_row(body, "Stop sound", "stop_sound_path")
        self._section_label(body, "PRIVACY", top=17)
        tk.Label(
            body,
            text="Transcript history, correction learning, and mind maps are off by default.",
            bg=self._BACKGROUND,
            fg=self._MUTED,
            font=("Trebuchet MS", 8),
        ).pack(anchor="w")
        return page

    def _section_label(self, parent: tk.Widget, text: str, top: int = 0) -> None:
        tk.Label(parent, text=text, bg=self._BACKGROUND, fg=self._ACCENT, font=("Courier New", 7, "bold")).pack(anchor="w", pady=(top, 5))

    def _check_row(
        self,
        parent: tk.Widget,
        title: str,
        note: str,
        variable: tk.BooleanVar,
        command: Callable[[], None],
    ) -> None:
        row = tk.Frame(parent, bg=self._BACKGROUND)
        row.pack(fill="x", pady=4)
        copy = tk.Frame(row, bg=self._BACKGROUND)
        copy.pack(side="left", fill="x", expand=True)
        tk.Label(copy, text=title, bg=self._BACKGROUND, fg=self._TEXT, font=("Trebuchet MS", 9)).pack(anchor="w")
        tk.Label(
            copy,
            text=note,
            bg=self._BACKGROUND,
            fg=self._MUTED,
            justify="left",
            wraplength=390,
            font=("Trebuchet MS", 8),
        ).pack(anchor="w", pady=(2, 0))
        tk.Checkbutton(
            row,
            variable=variable,
            command=command,
            bg=self._BACKGROUND,
            activebackground=self._BACKGROUND,
            selectcolor=self._PANEL_ACTIVE,
            fg=self._TEXT,
            activeforeground=self._TEXT,
            bd=0,
            highlightthickness=0,
        ).pack(side="right", padx=(12, 0))

    def _option_row(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.StringVar,
        options: dict[str, str],
        command: Callable[[], None],
    ) -> None:
        row = tk.Frame(parent, bg=self._BACKGROUND)
        row.pack(fill="x", pady=5)
        tk.Label(row, text=title, bg=self._BACKGROUND, fg=self._TEXT, font=("Trebuchet MS", 9)).pack(side="left")
        reverse = {value: label for label, value in options.items()}
        display = tk.StringVar(value=reverse.get(variable.get(), next(iter(options))))

        def choose(label: str) -> None:
            variable.set(options[label])
            command()

        menu = tk.OptionMenu(row, display, *options, command=choose)
        menu.configure(
            width=14,
            bg=self._PANEL,
            fg=self._TEXT,
            activebackground=self._PANEL_ACTIVE,
            activeforeground=self._TEXT,
            highlightthickness=0,
            bd=0,
            font=("Courier New", 8),
        )
        menu["menu"].configure(bg=self._PANEL, fg=self._TEXT, activebackground=self._PANEL_ACTIVE)
        menu.pack(side="right")

    def _sound_row(self, parent: tk.Widget, title: str, setting_name: str) -> None:
        row = tk.Frame(parent, bg=self._BACKGROUND)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=title, bg=self._BACKGROUND, fg=self._TEXT, font=("Trebuchet MS", 9)).pack(side="left")
        tk.Button(
            row,
            text="Preview",
            command=lambda: self._sounds.play_file(getattr(self._settings.snapshot(), setting_name)),
            bg=self._PANEL,
            fg=self._TEXT,
            activebackground=self._PANEL_ACTIVE,
            activeforeground=self._TEXT,
            bd=0,
            padx=10,
            pady=5,
            font=("Courier New", 8),
        ).pack(side="right", padx=(6, 0))
        tk.Button(
            row,
            text="Choose WAV…",
            command=lambda: self._choose_sound(setting_name),
            bg=self._PANEL,
            fg=self._TEXT,
            activebackground=self._PANEL_ACTIVE,
            activeforeground=self._TEXT,
            bd=0,
            padx=10,
            pady=5,
            font=("Courier New", 8),
        ).pack(side="right")

    def _choose_sound(self, setting_name: str) -> None:
        selected = filedialog.askopenfilename(
            parent=self._root,
            title="Choose a WAV sound",
            filetypes=(("WAV audio", "*.wav"),),
        )
        if selected:
            self._settings.update(**{setting_name: str(Path(selected))})
            self._on_settings_changed()

    def _save_overlay_visibility(self) -> None:
        self._settings.update(show_overlay_always=self._overlay_var.get())
        self._on_settings_changed()

    def _save_overlay_position(self) -> None:
        self._settings.update(overlay_position=self._position_var.get())
        self._on_settings_changed()

    def _save_sounds_enabled(self) -> None:
        self._settings.update(sounds_enabled=self._sounds_var.get())
        self._on_settings_changed()

    def show_page(self, name: str) -> None:
        self._pages[name].tkraise()
        for key, button in self._nav_buttons.items():
            active = key == name
            button.configure(
                bg=self._PANEL_ACTIVE if active else self._SIDEBAR,
                fg=self._TEXT if active else self._MUTED,
            )

    def update_state(self, state: str) -> None:
        self._state = state
        color = self._STATE_COLORS.get(state, self._MUTED)
        self._status_label.configure(text=self._STATE_COPY.get(state, state), fg=color)
        self._status_orb.itemconfigure(self._orb_id, fill=color)
        if state == "Recording":
            self._record_button.configure(text="■  Stop and transcribe", bg="#9e3c35", fg="#fff4ea", state="normal")
        elif state == "Idle":
            self._record_button.configure(text="●  Start dictation", bg=self._ACCENT, fg="#1b160b", state="normal")
        else:
            label = "Transcribing…" if state == "Transcribing" else "Please wait"
            self._record_button.configure(text=label, bg="#313534", fg="#88887f", state="disabled")
        self._history_card.configure(
            text="History is on" if self._settings.snapshot().history_enabled else "History is off"
        )

    def is_visible(self) -> bool:
        try:
            return self._root.state() not in {"withdrawn", "iconic"}
        except tk.TclError:
            return False

    def show(self) -> None:
        self._root.deiconify()
        self._root.lift()
        self._root.focus_force()

    def hide(self) -> None:
        self._root.withdraw()
