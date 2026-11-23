"""Terminal page."""

import os
import subprocess

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, GLib, Vte, Gdk

from aio_core import (
    traducir, FASTFETCH_LAYOUT, comando_host, paquete_instalado,
    instalar_layout, restaurar_layout,
)


class TerminalPage(Gtk.Box):
    """Terminal integrada."""

    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.window = window
        self.translate = traducir
        self.terminal = None
        self.terminal_window = None
        self.detached = False
        self._build_ui()

    def _build_ui(self):
        toolbar = Gtk.Box(spacing=8)
        self.pack_start(toolbar, False, False, 0)

        self.btn_commands = Gtk.MenuButton()
        self.btn_commands.set_image(Gtk.Image.new_from_icon_name(
            "utilities-terminal-symbolic", Gtk.IconSize.BUTTON))
        self.btn_commands.set_tooltip_text(self.translate("Comandos"))
        popover, menu = self._create_command_menu()
        self.btn_commands.set_popover(popover)
        toolbar.pack_start(self.btn_commands, False, False, 0)

        self.btn_detach = Gtk.Button(label=self.translate("Separar terminal"))
        self.btn_detach.connect("clicked", self._toggle_detach)
        toolbar.pack_end(self.btn_detach, False, False, 0)

        self.terminal = Vte.Terminal()
        self.terminal.set_scrollback_lines(10000)
        self._setup_terminal()

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.terminal)
        self.pack_start(scroll, True, True, 0)

        self.show_all()
        self._spawn_shell()

    def _create_command_menu(self):
        popover = Gtk.Popover.new(self.btn_commands)
        menu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu.set_border_width(8)
        popover.add(menu)

        def add_cmd(label, cmd):
            btn = Gtk.Button(label=self.translate(label))
            btn.connect("clicked", lambda *_: (popover.popdown(), self._run_command(cmd)))
            menu.pack_start(btn, False, False, 0)
            return btn

        def add_sep(title):
            menu.pack_start(Gtk.Separator(), False, False, 0)
            lbl = Gtk.Label(label=title, xalign=0)
            lbl.get_style_context().add_class("dim-label")
            menu.pack_start(lbl, False, False, 0)

        self.btn_clear = add_cmd("Limpiar", "clear")
        self.btn_fastfetch = add_cmd("Fastfetch", "fastfetch")

        add_sep("Sistema")
        add_cmd("Htop", "htop")
        add_cmd("Btop", "btop")
        add_cmd("Análisis del arranque", "systemd-analyze blame")

        add_sep("Fastfetch")
        self.btn_apply_ff = Gtk.Button(label=self.translate("Aplicar diseño Fastfetch"))
        self.btn_apply_ff.connect("clicked", lambda *_: (popover.popdown(), self._apply_fastfetch()))
        menu.pack_start(self.btn_apply_ff, False, False, 0)

        self.btn_restore_ff = Gtk.Button(label=self.translate("Restaurar diseño anterior"))
        self.btn_restore_ff.connect("clicked", lambda *_: (popover.popdown(), self._restore_fastfetch()))
        menu.pack_start(self.btn_restore_ff, False, False, 0)

        menu.show_all()
        return popover, menu

    def _setup_terminal(self):
        self.terminal.connect("child-exited", self._on_child_exited)

    def _spawn_shell(self):
        shell = os.environ.get("SHELL", "/bin/bash")
        self.terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            os.environ.get("HOME", "/"),
            [shell],
            [],
            GLib.SpawnFlags.DO_NOT_REAP_CHILD,
            None, None,
            -1, None,
            self._on_spawn_done, None
        )

    def _on_spawn_done(self, terminal, success, _data):
        if not success:
            print("Error spawning terminal")

    def _on_child_exited(self, terminal):
        self._spawn_shell()

    def _run_command(self, cmd):
        if self.terminal:
            self.terminal.feed_child(f"{cmd}\n".encode())

    def _apply_fastfetch(self):
        try:
            instalar_layout(FASTFETCH_LAYOUT, comando_host)
            self._run_command("fastfetch")
        except Exception as exc:
            self.window._write_log(f"[!] Error aplicando Fastfetch: {exc}", "error")

    def _restore_fastfetch(self):
        try:
            restaurar_layout(comando_host)
            self._run_command("fastfetch")
        except Exception as exc:
            self.window._write_log(f"[!] Error restaurando Fastfetch: {exc}", "error")

    def _toggle_detach(self, _btn):
        if self.detached:
            self._reattach_terminal()
        else:
            self._detach_terminal()

    def _detach_terminal(self):
        self.terminal_window = Gtk.Window(title=self.translate("Terminal - AiO Debian"))
        self.terminal_window.set_default_size(800, 600)
        self.terminal_window.set_transient_for(self.window)
        self.terminal_window.connect("destroy", self._on_detached_window_destroy)

        parent = self.terminal.get_parent()
        if parent:
            parent.remove(self.terminal)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.terminal)
        self.terminal_window.add(scroll)
        self.terminal_window.show_all()

        self.detached = True
        self.btn_detach.set_label(self.translate("Acoplar terminal"))

    def _reattach_terminal(self):
        if self.terminal_window:
            self.terminal_window.destroy()
            self.terminal_window = None

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.add(self.terminal)
        self.pack_start(scroll, True, True, 0)
        self.show_all()

        self.detached = False
        self.btn_detach.set_label(self.translate("Separar terminal"))

    def _on_detached_window_destroy(self, _win):
        self._reattach_terminal()

    def show(self):
        if self.detached and self.terminal_window:
            self.terminal_window.present()

    def on_preferences_changed(self, prefs):
        self.translate = lambda t: TRADUCCIONES.get(prefs["idioma"], {}).get(t, t)