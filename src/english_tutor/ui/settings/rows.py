"""One row of the Settings window: label, help, a control and inline messages."""

from __future__ import annotations

from collections.abc import Callable
from tkinter import filedialog
from typing import Any

import customtkinter as ctk

from ...i18n import t
from ...settings.model import FIELD_BOUNDS
from ...settings.registry import TOGGLE_ACTIONS, Control, SettingSpec
from .. import theme
from .focus import enable_keyboard
from .values import format_scale, index_of_nearest, option_labels, value_for_label

OnChange = Callable[[str, Any], None]
Capture = Callable[[str, Callable[[str], None]], None]
"""``capture(setting_key, apply)``: ask for a key press and pass the result to ``apply``."""
WRAP = 500
_UNITS = {"daily_goal_minutes": "unit.minutes"}
"""i18n key of the unit shown next to a slider (points when not listed)."""

_BUTTON_TEXT = {
    "restore_defaults": "button.restore_defaults",
    "export_report": "button.export",
    "export_mistakes": "button.export",
    "export_anki": "button.export",
    "clear_logs": "button.delete",
    "clear_mistakes": "button.delete",
    "clear_memory": "button.delete",
    "test_connection": "button.test",
}
_RESULT_COLOURS = {
    "ok": theme.OK_TEXT, "warning": theme.NOTICE_TEXT,
    "error": theme.ERROR_TEXT, "info": theme.MUTED_TEXT,
}


class Row(ctk.CTkFrame):
    """Renders one ``SettingSpec`` and reports edits through ``on_change(key, value)``.

    ``env_var`` set means a TUTOR_* variable pins the value: the control is disabled
    and the row says so. ``unavailable`` (a reason) disables the control the same way.
    ``action`` is called by ACTION rows.
    """

    def __init__(
        self,
        master: Any,
        spec: SettingSpec,
        value: Any,
        on_change: OnChange,
        action: Callable[[], None] | None = None,
        env_var: str | None = None,
        capture: Capture | None = None,
        unavailable: str | None = None,
    ) -> None:
        super().__init__(master, fg_color=theme.ROW_BG, corner_radius=8)
        self.spec = spec
        self._on_change = on_change
        self._action = action
        self._capture = capture
        self.capture_button: ctk.CTkButton | None = None
        self._disabled = env_var is not None or unavailable is not None
        self._widgets: list[Any] = []
        self.grid_columnconfigure(0, weight=1)
        pad = theme.SPACE_M
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=pad, pady=(pad, 0))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            top, text=t(spec.label), font=(theme.FAMILY, 13, "bold"), anchor="w",
            text_color=theme.TEXT,
        ).grid(row=0, column=0, sticky="w")
        if spec.restart:
            ctk.CTkLabel(
                top, text=t("settings.pill_restart"), font=theme.FONT_HINT, corner_radius=8,
                fg_color=theme.PILL_BG, text_color=theme.PILL_TEXT, height=20,
            ).grid(row=0, column=1, padx=(theme.SPACE_S, 0))  # fmt: skip
        ctk.CTkLabel(
            self, text=t(spec.help), font=theme.FONT_HINT, text_color=theme.MUTED_TEXT,
            anchor="w", justify="left", wraplength=WRAP,
        ).grid(row=1, column=0, sticky="w", padx=pad)  # fmt: skip
        if env_var or unavailable:
            ctk.CTkLabel(
                self, text=t("settings.locked", var=env_var) if env_var else unavailable,
                font=theme.FONT_HINT,
                text_color=theme.NOTICE_TEXT, anchor="w",
            ).grid(row=2, column=0, sticky="w", padx=pad)  # fmt: skip
        self._control_frame = ctk.CTkFrame(self, fg_color="transparent", height=1)
        self._note = ctk.CTkLabel(
            self, text="", font=theme.FONT_HINT, anchor="w", justify="left", wraplength=WRAP,
        )  # fmt: skip
        self._result = ctk.CTkLabel(
            self, text="", font=theme.FONT_HINT, anchor="w", justify="left", wraplength=WRAP,
        )  # fmt: skip
        self.grid_rowconfigure(6, minsize=pad)
        self._build_control(top, value)
        if self._control_frame.winfo_children():
            self._control_frame.grid(
                row=3, column=0, sticky="ew", padx=pad, pady=(theme.SPACE_S, 0)
            )
        if self._disabled:
            for widget in self._widgets:
                widget.configure(state="disabled")

    # ------------------------------------------------------------------ public
    def set_note(self, error: str | None, warning: str | None) -> None:
        """Show an error (red) or, failing that, a warning (amber) under the control."""
        text = error or warning or ""
        colour = theme.ERROR_TEXT if error else theme.NOTICE_TEXT
        self._note.configure(text=text, text_color=colour)
        if text:
            self._note.grid(row=4, column=0, sticky="w", padx=theme.SPACE_M)
        else:
            self._note.grid_remove()

    def set_result(self, text: str, kind: str) -> None:
        """Show the outcome of an action (``kind``: info, ok, warning or error) under the row."""
        self._result.configure(text=text, text_color=_RESULT_COLOURS.get(kind, theme.MUTED_TEXT))
        self._result.grid(row=5, column=0, sticky="w", padx=theme.SPACE_M)

    # ---------------------------------------------------------------- controls
    def _emit(self, value: Any) -> None:
        self._on_change(self.spec.key, value)

    def _build_control(self, top: Any, value: Any) -> None:
        builders = {
            Control.SWITCH: lambda: self._switch(top, value),
            Control.CHOICE: lambda: self._choice(value),
            Control.SLIDER: lambda: self._slider(value),
            Control.COMBO: lambda: self._combo(value),
            Control.PATH: lambda: self._entry(value, browse=True),
            Control.ACTION: lambda: self._action_control(top, value),
            Control.KEY: lambda: self._entry(value, record=True),
            Control.SHORTCUT: lambda: self._entry(value, record=True),
        }
        builders.get(self.spec.control, lambda: self._entry(value))()

    def _switch(self, top: Any, value: Any) -> None:
        var = ctk.BooleanVar(value=bool(value))
        switch = ctk.CTkSwitch(
            top, text="", width=46, variable=var, command=lambda: self._emit(var.get())
        )
        switch.grid(row=0, column=2, padx=(theme.SPACE_S, 0))
        enable_keyboard(switch, switch.toggle)
        self._widgets.append(switch)

    def _choice(self, value: Any) -> None:
        key, options = self.spec.key, self.spec.options
        labels = option_labels(key, options)

        def pick(label: str) -> None:
            chosen = value_for_label(key, options, label)
            if chosen is not None:
                self._emit(chosen)

        current = labels[options.index(str(value))] if str(value) in options else labels[0]
        if len(options) <= 3:
            widget: Any = ctk.CTkSegmentedButton(self._control_frame, values=labels, command=pick)
        else:
            widget = ctk.CTkOptionMenu(self._control_frame, values=labels, command=pick)
        widget.set(current)
        widget.pack(anchor="w")
        self._widgets.append(widget)

    def _slider(self, value: Any) -> None:
        key = self.spec.key
        if self.spec.options:  # discrete steps such as the interface scale
            choices = [float(o) for o in self.spec.options]
            low, high, position = 0, len(choices) - 1, index_of_nearest(choices, float(value))

            def convert(raw: float) -> tuple[float, str]:
                chosen = choices[round(raw)]
                return chosen, format_scale(chosen)
        else:
            low, high = FIELD_BOUNDS[key]
            position = int(value)

            def convert(raw: float) -> tuple[int, str]:  # type: ignore[misc]
                return round(raw), t(_UNITS.get(key, "unit.points"), value=round(raw))

        shown = ctk.CTkLabel(self._control_frame, text=convert(position)[1], width=60, anchor="w")

        def moved(raw: float) -> None:
            chosen, text = convert(raw)
            shown.configure(text=text)
            self._emit(chosen)

        slider = ctk.CTkSlider(
            self._control_frame, from_=low, to=high, number_of_steps=high - low, command=moved
        )
        slider.set(position)
        slider.pack(side="left", fill="x", expand=True)
        shown.pack(side="left", padx=(theme.SPACE_S, 0))
        self._widgets.append(slider)

    def _text_var(self, value: Any) -> Any:
        var = ctk.StringVar(value=str(value))
        var.trace_add("write", lambda *_: self._emit(var.get()))
        return var

    def _combo(self, value: Any) -> None:
        var = self._text_var(value)
        combo = ctk.CTkComboBox(
            self._control_frame, values=list(self.spec.options), variable=var, width=260
        )
        combo.pack(anchor="w")
        self._widgets.append(combo)

    def _entry(self, value: Any, browse: bool = False, record: bool = False) -> None:
        var = self._text_var(value)
        entry = ctk.CTkEntry(self._control_frame, textvariable=var)
        entry.pack(side="left", fill="x", expand=True)
        self._widgets.append(entry)
        if browse:
            button = ctk.CTkButton(
                self._control_frame, text=t("button.browse"), width=90,
                command=lambda: self._browse(var),
            )  # fmt: skip
            button.pack(side="left", padx=(theme.SPACE_S, 0))
            enable_keyboard(button, button.invoke)
            self._widgets.append(button)

        if record and self._capture is not None:
            button = ctk.CTkButton(
                self._control_frame, text=t("button.change"), width=90,
                command=lambda: self._capture(self.spec.key, var.set),
            )  # fmt: skip
            button.pack(side="left", padx=(theme.SPACE_S, 0))
            enable_keyboard(button, button.invoke)
            self._widgets.append(button)
            self.capture_button = button

    def _browse(self, var: Any) -> None:
        chosen = filedialog.askdirectory(parent=self, initialdir=var.get() or None)
        if chosen:
            var.set(chosen)

    def _action_control(self, top: Any, value: Any) -> None:
        if self.spec.key in TOGGLE_ACTIONS:
            self._switch(top, value)
        else:
            self._action_button(top)

    def _action_button(self, top: Any) -> None:
        text_key = _BUTTON_TEXT.get(self.spec.key, "button.open")
        red = theme.BADGE_MAJOR if self.spec.danger else None
        button = ctk.CTkButton(
            top, text=t(text_key), width=120, fg_color=red,
            command=lambda: self._action() if self._action else None,
        )  # fmt: skip
        button.grid(row=0, column=2, padx=(theme.SPACE_S, 0))
        enable_keyboard(button, button.invoke)
        self._widgets.append(button)
