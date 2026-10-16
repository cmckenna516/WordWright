from __future__ import annotations

import ctypes
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from typing import Callable

from . import __version__
from .hardware import MODEL_LABELS
from .hotkeys import (
    KEY_CHOICES,
    MODIFIER_CHOICES,
    hold_hotkey_label,
    hotkey_label,
    parse_hold_hotkey,
    parse_hotkey,
)
from .settings import SettingsStore, parse_vocabulary
from .sounds import SoundPlayer
from .state import AppState
from .startup import StartupRegistration
from .theme import theme_for


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

    def __init__(
        self,
        root: tk.Tk,
        settings: SettingsStore,
        sounds: SoundPlayer,
        on_toggle: Callable[[], None],
        on_quit: Callable[[], None],
        on_settings_changed: Callable[[], None],
        on_model_changed: Callable[[], None] | None = None,
        model_explainer: Callable[[], str] | None = None,
        hotkey_changer: Callable[[str], str | None] | None = None,
        hold_hotkey_changer: Callable[[str], str | None] | None = None,
        startup_registration: StartupRegistration | None = None,
    ) -> None:
        self._root = root
        self._hotkey_changer = hotkey_changer or (lambda spec: None)
        self._hold_hotkey_changer = hold_hotkey_changer or (lambda spec: None)
        self._startup_registration = startup_registration or StartupRegistration()
        self._settings = settings
        self._sounds = sounds
        self._on_toggle = on_toggle
        self._on_quit = on_quit
        self._on_settings_changed = on_settings_changed
        self._on_model_changed = on_model_changed or (lambda: None)
        self._model_explainer = model_explainer or (lambda: "")
        self._state = AppState.LOADING.value
        self._pages: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, tk.Button] = {}
        self._configure_root()
        self._build_shell()
        self.show_page("dictate")

    def _configure_root(self) -> None:
        self._root.title("Wordwright")
        self._root.geometry("850x700")
        self._root.minsize(760, 680)
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
            ("speech", "Speech", "✎"),
            ("settings", "Settings", "⚙"),
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
        self._pages["speech"] = self._build_speech(content)
        self._pages["settings"] = self._build_settings(content)
        for page in self._pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        footer = tk.Frame(shell, height=30, bg="#111313")
        footer.pack(fill="x")
        footer.pack_propagate(False)
        tk.Label(
            footer,
            text=f"WORDWRIGHT {__version__}",
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
            "Tap your toggle shortcut for hands-free dictation, or hold your push-to-talk shortcut. "
            "Wordwright types the finished text where you left your cursor.",
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
            4, 4, 14, 14, fill=theme_for(AppState.LOADING).accent, outline=""
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
            text=theme_for(AppState.LOADING).launcher_copy,
            bg=self._PANEL,
            fg=theme_for(AppState.LOADING).accent,
            font=("Trebuchet MS", 9),
        )
        self._status_label.pack(anchor="w", pady=(3, 0))
        self._keycaps = tk.Frame(status_panel, bg=self._PANEL)
        self._keycaps.pack(side="right")
        self._render_keycaps()

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
                ("SCRIBE", "Choosing a model…"),
                ("PRIVACY", "Nothing is saved"),
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
            if label == "SCRIBE":
                self._model_card = value_label
        return page

    def _render_keycaps(self) -> None:
        for child in self._keycaps.winfo_children():
            child.destroy()
        tk.Label(
            self._keycaps,
            text="HOLD",
            bg=self._PANEL,
            fg=self._MUTED,
            font=("Courier New", 7, "bold"),
        ).pack(side="left", padx=(0, 6))
        parts = hold_hotkey_label(self._settings.snapshot().hold_hotkey).split("+")
        for index, key in enumerate(parts):
            if index:
                tk.Label(self._keycaps, text="+", bg=self._PANEL, fg=self._MUTED, font=("Courier New", 8)).pack(side="left", padx=3)
            tk.Label(
                self._keycaps,
                text=key.upper(),
                bg="#292b29",
                fg="#c9c4b7",
                padx=6,
                pady=4,
                font=("Courier New", 7),
                highlightbackground="#4b4d46",
                highlightthickness=1,
            ).pack(side="left")

    def _build_speech(self, parent: tk.Widget) -> tk.Frame:
        page = self._page(parent)
        self._heading(
            page,
            "Speech recognition",
            "Words Wordwright should know",
            "Names, products, and jargon the model tends to misspell. One per line. "
            "Changes apply to your next dictation.",
        )
        body = tk.Frame(page, bg=self._BACKGROUND)
        body.pack(fill="both", expand=True, pady=(16, 0))
        self._vocabulary_text = tk.Text(
            body,
            height=7,
            wrap="word",
            bg=self._PANEL,
            fg=self._TEXT,
            insertbackground=self._ACCENT,
            selectbackground=self._PANEL_ACTIVE,
            highlightbackground=self._BORDER,
            highlightcolor=self._ACCENT,
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=8,
            font=("Trebuchet MS", 9),
        )
        self._vocabulary_text.pack(fill="x")
        self._vocabulary_text.insert("1.0", "\n".join(self._settings.snapshot().vocabulary))

        actions = tk.Frame(body, bg=self._BACKGROUND)
        actions.pack(fill="x", pady=(8, 0))
        tk.Button(
            actions,
            text="Save words",
            command=self._save_vocabulary,
            bg=self._ACCENT,
            fg="#1b160b",
            activebackground="#e2bc66",
            activeforeground="#1b160b",
            bd=0,
            padx=12,
            pady=5,
            font=("Trebuchet MS", 8, "bold"),
        ).pack(side="left")
        self._vocabulary_status = tk.Label(
            actions,
            text=self._vocabulary_summary(len(self._settings.snapshot().vocabulary)),
            bg=self._BACKGROUND,
            fg=self._MUTED,
            font=("Trebuchet MS", 8),
        )
        self._vocabulary_status.pack(side="left", padx=(10, 0))

        self._section_label(body, "SPEECH MODEL", top=20)
        self._model_var = tk.StringVar(value=self._settings.snapshot().model_choice)
        self._option_row(
            body,
            "Model",
            self._model_var,
            {label: key for key, label in MODEL_LABELS.items()},
            self._save_model_choice,
            width=34,
        )
        self._model_note = tk.Label(
            body,
            text=self._model_explainer(),
            bg=self._BACKGROUND,
            fg=self._MUTED,
            justify="left",
            wraplength=540,
            font=("Trebuchet MS", 8),
        )
        self._model_note.pack(anchor="w", pady=(4, 0))
        return page

    @staticmethod
    def _vocabulary_summary(count: int) -> str:
        if count == 0:
            return "No custom words yet."
        return f"{count} word{'s' if count != 1 else ''} saved. Keep the list short; only the first ~220 tokens are used."

    def _save_vocabulary(self) -> None:
        terms = parse_vocabulary(self._vocabulary_text.get("1.0", "end"))
        try:
            self._settings.update(vocabulary=terms)
        except ValueError as exc:
            self._vocabulary_status.configure(text=str(exc), fg=theme_for(AppState.ERROR).accent)
            return
        self._vocabulary_text.delete("1.0", "end")
        self._vocabulary_text.insert("1.0", "\n".join(terms))
        self._vocabulary_status.configure(text=self._vocabulary_summary(len(terms)), fg=self._MUTED)

    def _save_model_choice(self) -> None:
        self._settings.update(model_choice=self._model_var.get())
        self._model_note.configure(text=self._model_explainer())
        self._on_model_changed()

    def _build_settings(self, parent: tk.Widget) -> tk.Frame:
        page = tk.Frame(parent, bg=self._BACKGROUND, padx=42, pady=24)
        self._heading(page, "Preferences", "Settings", "Keep the utility quiet, local, and easy to understand.")
        settings = self._settings.snapshot()
        self._overlay_var = tk.BooleanVar(value=settings.show_overlay_always)
        self._sounds_var = tk.BooleanVar(value=settings.sounds_enabled)
        self._position_var = tk.StringVar(value=settings.overlay_position)
        self._startup_var = tk.BooleanVar(value=self._startup_registration.is_enabled())
        body = tk.Frame(page, bg=self._BACKGROUND)
        body.pack(fill="both", expand=True, pady=(18, 0))
        self._section_label(body, "SHORTCUTS")
        self._shortcut_row(body)
        self._hold_shortcut_row(body)
        self._section_label(body, "WINDOWS", top=17)
        startup_available = self._startup_registration.available
        self._check_row(
            body,
            "Start Wordwright when I sign in to Windows",
            (
                "Starts with only the compact scroll visible. Opening Wordwright yourself still opens the full window."
                if startup_available
                else "Available in the installed Windows app."
            ),
            self._startup_var,
            self._save_startup,
            enabled=startup_available,
        )
        self._startup_status = tk.Label(
            body,
            text="",
            bg=self._BACKGROUND,
            fg=self._MUTED,
            justify="left",
            wraplength=540,
            font=("Trebuchet MS", 8),
        )
        self._startup_status.pack(anchor="w")
        self._section_label(body, "OVERLAY", top=17)
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
        return page

    @staticmethod
    def _key_display(key: str) -> str:
        return key.title() if key == "space" else key.upper()

    def _shortcut_row(self, parent: tk.Widget) -> None:
        current = parse_hotkey(self._settings.snapshot().hotkey)
        modifier_options = dict(MODIFIER_CHOICES)
        current_mods = next(
            (label for label, mods in modifier_options.items() if mods == current.modifiers),
            None,
        )
        if current_mods is None:
            current_mods = " + ".join(m.title() for m in current.modifiers)
            modifier_options[current_mods] = current.modifiers
        self._modifier_options = modifier_options
        self._key_options = {self._key_display(key): key for key in KEY_CHOICES}
        self._modifier_var = tk.StringVar(value=current_mods)
        self._key_var = tk.StringVar(value=self._key_display(current.key))

        row = tk.Frame(parent, bg=self._BACKGROUND)
        row.pack(fill="x", pady=4)
        tk.Label(row, text="Toggle dictation", bg=self._BACKGROUND, fg=self._TEXT, font=("Trebuchet MS", 9)).pack(side="left")
        tk.Button(
            row,
            text="Apply",
            command=self._apply_shortcut,
            bg=self._ACCENT,
            fg="#1b160b",
            activebackground="#e2bc66",
            activeforeground="#1b160b",
            bd=0,
            padx=12,
            pady=4,
            font=("Trebuchet MS", 8, "bold"),
        ).pack(side="right", padx=(8, 0))
        for variable, options, width in (
            (self._key_var, self._key_options, 6),
            (self._modifier_var, self._modifier_options, 16),
        ):
            menu = tk.OptionMenu(row, variable, *options)
            menu.configure(
                width=width,
                bg=self._PANEL,
                fg=self._TEXT,
                activebackground=self._PANEL_ACTIVE,
                activeforeground=self._TEXT,
                highlightthickness=0,
                bd=0,
                font=("Courier New", 8),
            )
            menu["menu"].configure(bg=self._PANEL, fg=self._TEXT, activebackground=self._PANEL_ACTIVE)
            menu.pack(side="right", padx=(4, 0))
            if variable is self._key_var:
                tk.Label(row, text="+", bg=self._BACKGROUND, fg=self._MUTED, font=("Courier New", 8)).pack(side="right", padx=(4, 0))
        self._shortcut_status = tk.Label(
            parent,
            text=self._shortcut_summary(),
            bg=self._BACKGROUND,
            fg=self._MUTED,
            justify="left",
            wraplength=540,
            font=("Trebuchet MS", 8),
        )
        self._shortcut_status.pack(anchor="w")

    def _shortcut_summary(self) -> str:
        return (
            f"Press {hotkey_label(self._settings.snapshot().hotkey)} once to start and again to stop. "
            "Esc cancels while recording."
        )

    def _apply_shortcut(self) -> None:
        modifiers = self._modifier_options[self._modifier_var.get()]
        key = self._key_options[self._key_var.get()]
        spec = "+".join((*modifiers, key))
        error = self._hotkey_changer(spec)
        if error:
            self._shortcut_status.configure(text=error, fg=theme_for(AppState.ERROR).accent)
            return
        self._shortcut_status.configure(text=self._shortcut_summary(), fg=self._MUTED)
        self._render_keycaps()
        self._on_settings_changed()

    def _hold_shortcut_row(self, parent: tk.Widget) -> None:
        current = parse_hold_hotkey(self._settings.snapshot().hold_hotkey)
        modifier_options = dict(MODIFIER_CHOICES)
        current_mods = next(
            (label for label, mods in modifier_options.items() if mods == current.modifiers),
            None,
        )
        if current_mods is None:
            current_mods = " + ".join(m.title() for m in current.modifiers)
            modifier_options[current_mods] = current.modifiers
        self._hold_modifier_options = modifier_options
        self._hold_key_options: dict[str, str | None] = {
            "Modifiers only": None,
            **{self._key_display(key): key for key in KEY_CHOICES},
        }
        self._hold_modifier_var = tk.StringVar(value=current_mods)
        self._hold_key_var = tk.StringVar(
            value="Modifiers only" if current.key is None else self._key_display(current.key)
        )

        row = tk.Frame(parent, bg=self._BACKGROUND)
        row.pack(fill="x", pady=(10, 4))
        tk.Label(
            row,
            text="Hold to dictate",
            bg=self._BACKGROUND,
            fg=self._TEXT,
            font=("Trebuchet MS", 9),
        ).pack(side="left")
        tk.Button(
            row,
            text="Apply",
            command=self._apply_hold_shortcut,
            bg=self._ACCENT,
            fg="#1b160b",
            activebackground="#e2bc66",
            activeforeground="#1b160b",
            bd=0,
            padx=12,
            pady=4,
            font=("Trebuchet MS", 8, "bold"),
        ).pack(side="right", padx=(8, 0))
        for variable, options, width in (
            (self._hold_key_var, self._hold_key_options, 14),
            (self._hold_modifier_var, self._hold_modifier_options, 16),
        ):
            menu = tk.OptionMenu(row, variable, *options)
            menu.configure(
                width=width,
                bg=self._PANEL,
                fg=self._TEXT,
                activebackground=self._PANEL_ACTIVE,
                activeforeground=self._TEXT,
                highlightthickness=0,
                bd=0,
                font=("Courier New", 8),
            )
            menu["menu"].configure(
                bg=self._PANEL,
                fg=self._TEXT,
                activebackground=self._PANEL_ACTIVE,
            )
            menu.pack(side="right", padx=(4, 0))
        self._hold_shortcut_status = tk.Label(
            parent,
            text=self._hold_shortcut_summary(),
            bg=self._BACKGROUND,
            fg=self._MUTED,
            justify="left",
            wraplength=540,
            font=("Trebuchet MS", 8),
        )
        self._hold_shortcut_status.pack(anchor="w")

    def _hold_shortcut_summary(self) -> str:
        return (
            f"Hold {hold_hotkey_label(self._settings.snapshot().hold_hotkey)} to record; "
            "release any held key to stop and transcribe."
        )

    def _apply_hold_shortcut(self) -> None:
        modifiers = self._hold_modifier_options[self._hold_modifier_var.get()]
        key = self._hold_key_options[self._hold_key_var.get()]
        spec = "+".join((*modifiers, *((key,) if key else ())))
        error = self._hold_hotkey_changer(spec)
        if error:
            self._hold_shortcut_status.configure(
                text=error,
                fg=theme_for(AppState.ERROR).accent,
            )
            return
        self._hold_shortcut_status.configure(
            text=self._hold_shortcut_summary(),
            fg=self._MUTED,
        )
        self._render_keycaps()
        self._on_settings_changed()

    def _section_label(self, parent: tk.Widget, text: str, top: int = 0) -> None:
        tk.Label(parent, text=text, bg=self._BACKGROUND, fg=self._ACCENT, font=("Courier New", 7, "bold")).pack(anchor="w", pady=(top, 5))

    def _check_row(
        self,
        parent: tk.Widget,
        title: str,
        note: str,
        variable: tk.BooleanVar,
        command: Callable[[], None],
        enabled: bool = True,
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
            state="normal" if enabled else "disabled",
        ).pack(side="right", padx=(12, 0))

    def _option_row(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.StringVar,
        options: dict[str, str],
        command: Callable[[], None],
        width: int = 14,
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
            width=width,
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

    def _save_startup(self) -> None:
        enabled = self._startup_var.get()
        try:
            self._startup_registration.set_enabled(enabled)
        except (OSError, RuntimeError):
            self._startup_var.set(self._startup_registration.is_enabled())
            self._startup_status.configure(
                text="Windows could not update this startup setting. Try again or check your account permissions.",
                fg=theme_for(AppState.ERROR).accent,
            )
            return
        self._startup_status.configure(
            text=(
                "Wordwright will start in compact mode the next time you sign in."
                if enabled
                else "Wordwright will no longer start automatically."
            ),
            fg=self._MUTED,
        )

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

    def set_model_label(self, label: str) -> None:
        self._model_card.configure(text=f"{label} · local")
        self._model_note.configure(text=self._model_explainer())

    def update_state(self, state: str) -> None:
        self._state = state
        theme = theme_for(state)
        self._status_label.configure(text=theme.launcher_copy, fg=theme.accent)
        self._status_orb.itemconfigure(self._orb_id, fill=theme.accent)
        if state == AppState.RECORDING.value:
            self._record_button.configure(text="■  Stop and transcribe", bg="#9e3c35", fg="#fff4ea", state="normal")
        elif state == AppState.IDLE.value:
            self._record_button.configure(text="●  Start dictation", bg=self._ACCENT, fg="#1b160b", state="normal")
        else:
            label = "Transcribing…" if state == AppState.TRANSCRIBING.value else "Please wait"
            self._record_button.configure(text=label, bg="#313534", fg="#88887f", state="disabled")

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
