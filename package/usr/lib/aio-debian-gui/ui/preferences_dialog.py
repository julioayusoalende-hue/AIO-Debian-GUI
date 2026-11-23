"""Preferences dialog."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from aio_core import traducir, PREFERENCIAS_DEFECTO, IDIOMAS, TEMAS


class PreferencesDialog(Gtk.Dialog):
    """Diálogo de preferencias."""

    def __init__(self, parent, current_prefs):
        super().__init__(title=traducir("Preferencias"), transient_for=parent, modal=True)
        self.current_prefs = current_prefs.copy()
        self.translate = traducir

        self.add_button(traducir("Cancelar"), Gtk.ResponseType.CANCEL)
        self.add_button(traducir("Guardar"), Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)
        self.set_default_size(400, -1)

        content = self.get_content_area()
        content.set_spacing(12)
        content.set_border_width(16)

        # Idioma
        lang_box = Gtk.Box(spacing=12)
        lang_lbl = Gtk.Label(label=self.translate("Idioma"), xalign=0)
        lang_lbl.set_size_request(120, -1)
        lang_box.pack_start(lang_lbl, False, False, 0)

        self.lang_combo = Gtk.ComboBoxText()
        lang_names = {"es": "Español", "en": "English", "fr": "Français", "zh": "中文"}
        for code in sorted(IDIOMAS):
            self.lang_combo.append(code, lang_names.get(code, code))
        self.lang_combo.set_active_id(self.current_prefs.get("idioma", "es"))
        lang_box.pack_start(self.lang_combo, True, True, 0)
        content.pack_start(lang_box, False, False, 0)

        # Tema
        theme_box = Gtk.Box(spacing=12)
        theme_lbl = Gtk.Label(label=self.translate("Tema"), xalign=0)
        theme_lbl.set_size_request(120, -1)
        theme_box.pack_start(theme_lbl, False, False, 0)

        self.theme_combo = Gtk.ComboBoxText()
        theme_labels = {"sistema": self.translate("Sistema"), "claro": self.translate("Claro"), "oscuro": self.translate("Oscuro")}
        for code in sorted(TEMAS):
            self.theme_combo.append(code, theme_labels.get(code, code))
        self.theme_combo.set_active_id(self.current_prefs.get("tema", "sistema"))
        theme_box.pack_start(self.theme_combo, True, True, 0)
        content.pack_start(theme_box, False, False, 0)

        # Interfaz simple
        simple_box = Gtk.Box(spacing=12)
        simple_lbl = Gtk.Label(label=self.translate("Interfaz simple"), xalign=0)
        simple_lbl.set_size_request(120, -1)
        simple_box.pack_start(simple_lbl, False, False, 0)

        self.simple_switch = Gtk.Switch()
        self.simple_switch.set_active(self.current_prefs.get("modo_simple", False))
        simple_box.pack_start(self.simple_switch, False, False, 0)
        content.pack_start(simple_box, False, False, 0)

        # Canal actualizaciones
        channel_box = Gtk.Box(spacing=12)
        channel_lbl = Gtk.Label(label=self.translate("Canal de actualizaciones"), xalign=0)
        channel_lbl.set_size_request(120, -1)
        channel_box.pack_start(channel_lbl, False, False, 0)

        self.channel_combo = Gtk.ComboBoxText()
        self.channel_combo.append("stable", self.translate("Estable"))
        self.channel_combo.append("testing", self.translate("Testing"))
        self.channel_combo.set_active_id(self.current_prefs.get("canal_actualizaciones", "stable"))
        channel_box.pack_start(self.channel_combo, True, True, 0)
        content.pack_start(channel_box, False, False, 0)

        # Carpeta repositorios
        repo_box = Gtk.Box(spacing=12)
        repo_lbl = Gtk.Label(label=self.translate("Carpeta repositorios"), xalign=0)
        repo_lbl.set_size_request(120, -1)
        repo_box.pack_start(repo_lbl, False, False, 0)

        self.repo_entry = Gtk.Entry()
        self.repo_entry.set_text(self.current_prefs.get("carpeta_repositorios", ""))
        self.repo_entry.set_placeholder_text(self.translate("Dejar vacío para usar la predeterminada"))
        repo_box.pack_start(self.repo_entry, True, True, 0)

        btn_browse = Gtk.Button(label=self.translate("Examinar…"))
        btn_browse.connect("clicked", self._browse_repo_folder)
        repo_box.pack_start(btn_browse, False, False, 0)
        content.pack_start(repo_box, False, False, 0)

        self.show_all()

    def _browse_repo_folder(self, _btn):
        dialog = Gtk.FileChooserDialog(title=self.translate("Seleccionar carpeta"),
                                        transient_for=self, action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(traducir("Cancelar"), Gtk.ResponseType.CANCEL,
                           traducir("Seleccionar"), Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            self.repo_entry.set_text(dialog.get_filename())
        dialog.destroy()

    def get_preferences(self):
        return {
            "idioma": self.lang_combo.get_active_id() or "es",
            "tema": self.theme_combo.get_active_id() or "sistema",
            "modo_simple": self.simple_switch.get_active(),
            "canal_actualizaciones": self.channel_combo.get_active_id() or "stable",
            "carpeta_repositorios": self.repo_entry.get_text().strip(),
            "reloj_inicial_sincronizado": self.current_prefs.get("reloj_inicial_sincronizado", False),
        }