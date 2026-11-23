"""Task list widget for maintenance page."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

from aio_core import traducir


class TaskList(Gtk.Box):
    """Lista de tareas de mantenimiento con checkboxes agrupadas por grupo."""

    __gsignals__ = {
        "selection-changed": (GObject.SIGNAL_RUN_FIRST, None, (object,))
    }

    def __init__(self, pasos, grupos, translate_func):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.pasos = pasos
        self.grupos = grupos
        self.translate = translate_func
        self.task_states = {}
        self.check_buttons = {}
        self.selected_tasks = set()
        self._build_ui()

    def _build_ui(self):
        for grupo_id, grupo_nombre in self.grupos:
            tareas_grupo = [p for p in self.pasos if p[4] == grupo_id]
            if not tareas_grupo:
                continue

            frame = Gtk.Frame()
            frame.get_style_context().add_class("aio-task-group")
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.set_border_width(8)
            frame.add(box)

            lbl_grupo = Gtk.Label(label=self.translate(grupo_nombre), xalign=0)
            lbl_grupo.get_style_context().add_class("aio-group")
            box.pack_start(lbl_grupo, False, False, 0)

            list_box = Gtk.ListBox()
            list_box.set_selection_mode(Gtk.SelectionMode.NONE)
            box.pack_start(list_box, True, True, 0)

            for task_id, titulo, descripcion, default_on, _ in tareas_grupo:
                row = Gtk.ListBoxRow()
                row.set_activatable(False)
                hbox = Gtk.Box(spacing=10, margin_top=4, margin_bottom=4)
                row.add(hbox)

                check = Gtk.CheckButton()
                check.get_style_context().add_class("aio-task")
                check.connect("toggled", self._on_task_toggled, task_id)
                hbox.pack_start(check, False, False, 0)

                info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                name_lbl = Gtk.Label(label=self.translate(titulo), xalign=0)
                name_lbl.get_style_context().add_class("aio-task-name")
                info.pack_start(name_lbl, False, False, 0)

                desc_lbl = Gtk.Label(label=self.translate(descripcion), xalign=0)
                desc_lbl.get_style_context().add_class("aio-task-detail")
                desc_lbl.set_line_wrap(True)
                info.pack_start(desc_lbl, False, False, 0)

                hbox.pack_start(info, True, True, 0)

                self.check_buttons[task_id] = check
                list_box.add(row)

            self.pack_start(frame, False, False, 0)

        self.show_all()

    def _on_task_toggled(self, check, task_id):
        if check.get_active():
            self.selected_tasks.add(task_id)
        else:
            self.selected_tasks.discard(task_id)
        self.emit("selection-changed", self.selected_tasks)

    def set_task_states(self, states):
        self.task_states = states
        for task_id, check in self.check_buttons.items():
            disponible = states.get(task_id, True)
            check.set_sensitive(disponible)
            if not disponible:
                check.set_active(False)
                check.set_tooltip_text(self.translate("No disponible en esta distribución"))
            else:
                check.set_tooltip_text(None)

    def refresh_translations(self, translate_func):
        self.translate = translate_func

    def get_selected(self):
        return self.selected_tasks

    def set_sensitive(self, sensitive):
        for check in self.check_buttons.values():
            check.set_sensitive(sensitive and check.get_sensitive())