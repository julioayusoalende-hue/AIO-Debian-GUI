"""Diagnostics dialog."""

import threading
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from aio_core import diagnostics as core_diagnostics

from aio_core import traducir, comando_host, datos_distribucion_anfitrion, distribucion_anfitrion


class DiagnosticsDialog(Gtk.Dialog):
    """Diálogo de diagnóstico preventivo."""

    def __init__(self, parent):
        super().__init__(title=traducir("Diagnóstico preventivo"), transient_for=parent, modal=True)
        self.parent_window = parent
        self.translate = traducir
        self.running = False

        self.add_button(traducir("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(600, 500)

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_border_width(16)

        toolbar = Gtk.Box(spacing=8)
        self.btn_refresh = Gtk.Button(label=self.translate("Actualizar"))
        self.btn_refresh.get_style_context().add_class("suggested-action")
        self.btn_refresh.connect("clicked", self._run_diagnostics)
        toolbar.pack_start(self.btn_refresh, False, False, 0)

        self.btn_export = Gtk.Button(label=self.translate("Exportar"))
        self.btn_export.connect("clicked", self._export_report)
        toolbar.pack_start(self.btn_export, False, False, 0)
        content.pack_start(toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(True)

        for i, title in enumerate([self.translate("Comprobación"), self.translate("Estado"), self.translate("Detalles")]):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=i)
            col.set_resizable(True)
            col.set_expand(i == 2)
            self.tree.append_column(col)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.tree)
        content.pack_start(scroll, True, True, 0)

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_text(self.translate("Pulse Actualizar para ejecutar el diagnóstico"))
        content.pack_start(self.status_label, False, False, 0)

        self.show_all()

    def _run_diagnostics(self, _btn):
        if self.running:
            return
        self.running = True
        self.btn_refresh.set_sensitive(False)
        self.status_label.set_text(self.translate("Ejecutando diagnóstico…"))
        self.store.clear()

        def worker():
            try:
                results = core_diagnostics.run_all(comando_host)
                GLib.idle_add(self._on_diagnostics_done, results, None)
            except Exception as exc:
                GLib.idle_add(self._on_diagnostics_done, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_diagnostics_done(self, results, error):
        self.running = False
        self.btn_refresh.set_sensitive(True)

        if error:
            self.status_label.set_text(self.translate("Error: ") + error)
            return

        self.store.clear()
        for check in results:
            status = check.get("status", "unknown")
            icon = {"ok": "✓", "warning": "⚠", "error": "✗", "info": "ℹ"}.get(status, "?")
            status_text = {"ok": self.translate("OK"),
                           "warning": self.translate("Advertencia"),
                           "error": self.translate("Error"),
                           "info": self.translate("Info")}.get(status, status)
            details = check.get("details", "")
            self.store.append([icon, status_text, details])

        self.status_label.set_text(self.translate("Diagnóstico completado"))

    def _export_report(self, _btn):
        dialog = Gtk.FileChooserDialog(title=self.translate("Guardar informe"),
                                        transient_for=self, action=Gtk.FileChooserAction.SAVE)
        dialog.add_buttons(traducir("Cancelar"), Gtk.ResponseType.CANCEL,
                           traducir("Guardar"), Gtk.ResponseType.OK)
        dialog.set_current_name("diagnostico.txt")
        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
            try:
                with open(path, "w") as f:
                    for row in self.store:
                        f.write(f"[{row[1]}] {row[0]} - {row[2]}\n")
                self.status_label.set_text(self.translate("Informe guardado en ") + path)
            except Exception as exc:
                self.status_label.set_text(self.translate("Error guardando: ") + str(exc))
        dialog.destroy()