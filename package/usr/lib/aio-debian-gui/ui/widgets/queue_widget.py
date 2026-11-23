"""Queue widget for software manager."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject


class QueueWidget(Gtk.Frame):
    """Widget para mostrar y gestionar cola de operaciones."""

    def __init__(self, translate_func):
        super().__init__()
        self.translate = translate_func
        self.queue = []
        self.set_no_show_all(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=8)
        self.add(box)

        self.title_label = Gtk.Label(xalign=0)
        self.title_label.get_style_context().add_class("aio-task-name")
        box.pack_start(self.title_label, False, False, 0)

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list_box.set_activate_on_single_click(False)
        scroll = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.NONE,
                                    max_content_height=180,
                                    propagate_natural_height=True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.list_box)
        box.pack_start(scroll, False, False, 0)

        actions = Gtk.Box(spacing=6)
        self.apply_btn = Gtk.Button()
        self.apply_btn.get_style_context().add_class("suggested-action")
        self.apply_btn.connect("clicked", lambda *_: self.emit("apply"))
        self.clear_btn = Gtk.Button()
        self.clear_btn.connect("clicked", lambda *_: self.emit("clear"))
        actions.pack_end(self.apply_btn, False, False, 0)
        actions.pack_end(self.clear_btn, False, False, 0)
        box.pack_start(actions, False, False, 0)

        self._update_labels()

    def add_item(self, item):
        if any(q["identifier"] == item["identifier"] for q in self.queue):
            return False

        self.queue.append(item)
        self._rebuild_list()
        self._update_labels()
        return True

    def remove_item(self, index):
        if 0 <= index < len(self.queue):
            del self.queue[index]
            self._rebuild_list()
            self._update_labels()

    def clear(self):
        self.queue.clear()
        self._rebuild_list()
        self._update_labels()

    def get_items(self):
        return list(self.queue)

    def _rebuild_list(self):
        for child in self.list_box.get_children():
            self.list_box.remove(child)

        for index, item in enumerate(self.queue):
            row = Gtk.Box(spacing=8, margin_top=2, margin_bottom=2)
            verbs = {"install": self.translate("Instalar"),
                     "upgrade": self.translate("Actualizar"),
                     "remove": self.translate("Desinstalar")}
            label = Gtk.Label(label=f"{verbs.get(item['action'], item['action'])} {item['name']}",
                              xalign=0, ellipsize=3)
            label.set_tooltip_text(item["identifier"])
            row.pack_start(label, True, True, 0)

            remove_btn = Gtk.Button(label="×")
            remove_btn.set_relief(Gtk.ReliefStyle.NONE)
            remove_btn.set_tooltip_text(self.translate("Quitar de la cola"))
            remove_btn.connect("clicked", lambda *_args, pos=index: self.remove_item(pos))
            row.pack_end(remove_btn, False, False, 0)

            self.list_box.add(row)

        self.list_box.show_all()

    def _update_labels(self):
        count = len(self.queue)
        self.title_label.set_label(self.translate("Cola de operaciones · %d operaciones") % count)
        self.apply_btn.set_label(self.translate("Aplicar cola (%d)") % count)
        self.clear_btn.set_label(self.translate("Vaciar cola"))
        self.set_visible(count > 0)

    def set_apply_callback(self, callback):
        self.apply_btn.connect("clicked", lambda *_: callback())

    def set_clear_callback(self, callback):
        self.clear_btn.connect("clicked", lambda *_: callback())