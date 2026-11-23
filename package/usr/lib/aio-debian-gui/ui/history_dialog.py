"""History dialog."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from aio_core import history as core_history

from aio_core import traducir, ruta_historial, leer_historial


class HistoryDialog(Gtk.Dialog):
    """Diálogo de historial de mantenimiento."""

    def __init__(self, parent):
        super().__init__(title=traducir("Historial de mantenimiento"), transient_for=parent, modal=True)
        self.add_button(traducir("Cerrar"), Gtk.ResponseType.CLOSE)
        self.set_default_size(700, 500)

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_border_width(16)

        toolbar = Gtk.Box(spacing=8)
        self.btn_refresh = Gtk.Button(label=self.translate("Actualizar"))
        self.btn_refresh.connect("clicked", self._load_history)
        toolbar.pack_start(self.btn_refresh, False, False, 0)

        self.btn_clear = Gtk.Button(label=self.translate("Limpiar historial"))
        self.btn_clear.connect("clicked", self._clear_history)
        toolbar.pack_end(self.btn_clear, False, False, 0)
        content.pack_start(toolbar, False, False, 0)

        self.store = Gtk.ListStore(str, str, str, str, str)
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(True)

        for i, title in enumerate([self.translate("Fecha"), self.translate("Tareas"),
                                    self.translate("Resultado"), self.translate("Reinicio"),
                                    self.translate("Versión")]):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=i)
            col.set_resizable(True)
            col.set_expand(i == 1)
            self.tree.append_column(col)

        self.tree.get_selection().connect("changed", self._on_selection_changed)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.tree)
        content.pack_start(scroll, True, True, 0)

        self.details_view = Gtk.TextView(editable=False, cursor_visible=False,
                                          wrap_mode=Gtk.WrapMode.WORD_CHAR,
                                          left_margin=8, right_margin=8)
        details_scroll = Gtk.ScrolledWindow()
        details_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        details_scroll.set_min_content_height(120)
        details_scroll.add(self.details_view)
        content.pack_start(details_scroll, False, False, 0)

        self.show_all()
        self._load_history()

    def _load_history(self, _btn=None):
        self.store.clear()
        try:
            entries = leer_historial()
            for entry in reversed(entries):
                fecha = entry.get("fecha", "")
                tareas = ", ".join(entry.get("tareas", []))
                resultado = entry.get("resultado", "")
                reinicio = self.translate("Sí") if entry.get("reinicio") else self.translate("No")
                version = entry.get("version", "")
                self.store.append([fecha, tareas, resultado, reinicio, version])
        except Exception as exc:
            print(f"Error loading history: {exc}")

    def _on_selection_changed(self, selection):
        model, treeiter = selection.get_selected()
        if treeiter:
            buffer = self.details_view.get_buffer()
            buffer.set_text("Detalles no implementados completamente")

    def _clear_history(self, _btn):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Limpiar historial"))
        dialog.format_secondary_text(self.translate("¿Eliminar todo el historial de mantenimiento?"))
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        if dialog.run() == Gtk.ResponseType.OK:
            try:
                import os
                os.remove(ruta_historial())
                self._load_history()
            except Exception as exc:
                print(f"Error clearing history: {exc}")
        dialog.destroy()