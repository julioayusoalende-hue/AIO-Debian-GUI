"""Main window for AIO Debian GUI."""

import os
import sys
import threading
import subprocess
import shutil
import re

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")
from gi.repository import Gtk, Gdk, GLib, GObject, Vte, Pango

# Core imports
from aio_core import (
    clock as core_clock, history as core_history, preferences as core_preferences,
    updates as core_updates, diagnostics as core_diagnostics, preflight as core_preflight,
    scheduler as core_scheduler, host_integration as core_host_integration,
    desktop_backup as core_desktop_backup, recommended_list as core_recommended_list,
    fastfetch, gtk_appearance, gtk_scheduler, translations,
    PRGNAME, APP_ICON_NAME, POLKIT_ACTION, HELPER, HELPER_SISTEMA,
    GRUB_HELPER, APT_BACKUP_HELPER, APT_BACKUP_FILENAME, APT_BACKUP_LIMIT,
    HOMEPAGE, DEBIAN_LOGO, UBUNTU_LOGO, AYUSOS_LOGO, NOMBRE_AYUSOS,
    FASTFETCH_LAYOUT, NOTAS_VERSION, RECOMMENDED_ICON_DIR, BACKUP_ICON_DIR,
    IDIOMA_ACTUAL, PREFERENCIAS_DEFECTO, IDIOMAS, TEMAS,
    PASOS, GRUPOS, APPS_RECOMENDADAS, APLICACIONES_BACKUP,
    MAX_HISTORIAL, ruta_historial, leer_historial, guardar_registro_mantenimiento,
    ruta_preferencias, cargar_preferencias, guardar_preferencias,
    es_flatpak, comando_host, leer_texto, paquete_instalado,
    version_app, formato_actualizacion, datos_distribucion_anfitrion,
    distribucion_anfitrion, identidad_distribucion, logo_distribucion,
    imagen_logo_distribucion, traducir, traducir_detalle_diagnostico,
    helper_mantenimiento, usa_integracion_portable, helper_disponible,
    comando_administrativo, comando_pkexec, helper_admite_autorizacion_sin_contrasena,
    helper_admite_tarea, autorizacion_sin_contrasena_activa,
    etiqueta, ESTILO_APLICACION, cabecera_mantenimiento, tarjeta_mantenimiento,
)

# UI imports
from .widgets.header_bar import HeaderBar
from .maintenance_page import MaintenancePage
from .software_page import SoftwarePage
from .recommended_page import RecommendedPage
from .backup_page import BackupPage
from .home_page import HomePage
from .terminal_page import TerminalPage
from .preferences_dialog import PreferencesDialog
from .diagnostics_dialog import DiagnosticsDialog
from .about_dialog import AboutDialog

# Software manager
try:
    from software_manager.manager import SoftwareManagerPage
    HAS_SOFTWARE_MANAGER = True
except ImportError:
    HAS_SOFTWARE_MANAGER = False


class VentanaPrincipal(Gtk.Window):
    """Ventana principal de AIO Debian GUI."""

    def __init__(self, preferencias=None):
        super().__init__(title="AiO Debian")
        self.preferencias = (preferencias or PREFERENCIAS_DEFECTO).copy()
        self.destruida = False
        self.connect("destroy", self._on_destroy)

        global IDIOMA_ACTUAL
        IDIOMA_ACTUAL = self.preferencias["idioma"]

        self.set_default_size(1160, 780)
        self.set_icon_name(APP_ICON_NAME)

        # Estado general
        self.en_curso = False
        self.proceso = None
        self.flujo = None
        self.necesita_reinicio = False
        self.servicios_pendientes = set()
        self.hubo_errores = False
        self.fin_recibido = False
        self.terminado_gestionado = False
        self.configurando_sin_contrasena = None
        self.actualizando_sin_contrasena = False
        self.esperando_autorizacion = False
        self.cancelacion_autorizacion = None
        self.timeout_autorizacion_id = None
        self.consultando_estados = False
        self.timeout_estados_id = None
        self.estados_tareas = set()
        self.nvidia_presente = False
        self.nvidia_hibrida = False
        self.nvidia_instalada = False
        self.nvidia_candidata = "no-disponible"
        self.nvidia_secureboot = "desconocido"
        self.salida_estados = []
        self.comprobando_actualizacion = False
        self.backup_action_in_progress = False
        self.grub_action_in_progress = False
        self.grub_estado = None
        self.backup_buttons = {}
        self.recommended_scan_generation = 0
        self.terminal_started = False
        self.ventana_terminal = None
        self.terminal_monitor = None
        self.programando = False
        self.sincronizando_reloj = False
        self.aviso_reloj_inicial = False

        self.programacion = ControladorProgramacion(self)
        self.diagnostico_en_curso = False
        self.ventana_diagnostico = None
        self.btn_actualizar_diagnostico = None
        self.tareas_en_ejecucion = []
        self.actualizando_preset = False
        self.switches = {}
        self.filas = {}
        self.indicadores = {}
        self.reintento_en_ejecucion = None
        self.flatpak_sistema_en_ejecucion = False
        self.resultados_tareas = {}
        self.errores_tareas = {}
        self.salida_error_tarea = []
        self.estado_diagnostico = "No comprobado"

        # Datos del sistema
        self.datos_anfitrion = datos_distribucion_anfitrion()
        self.distribucion = distribucion_anfitrion(self.datos_anfitrion)
        self.canales_recomendados = {app["id"]: app["channels"] for app in APPS_RECOMENDADAS}
        self.canales_recomendados["ghostty"] = self._canales_ghostty(self.datos_anfitrion)
        self.snapd_presente = paquete_instalado("snapd")
        self.flatpak_presente = es_flatpak() or shutil.which("flatpak") is not None
        self.gnome_presente = paquete_instalado("gnome-shell")

        # Aplicar tema
        aplicar_tema(self.preferencias.get("tema", "sistema"))

        # Construir UI
        self._setup_css()
        self._build_header()
        self._build_body()
        self._update_sensitivity()

        # Eventos
        self.connect("key-press-event", self._on_key_press)
        self.connect("delete-event", self._on_delete)
        self.connect("focus-in-event", self._on_focus_in)

        # Inicialización asíncrona
        self._prepare_host_on_start()

    def _canales_ghostty(self, distribucion):
        sistema = distribucion.get("ID")
        version = distribucion.get("VERSION_ID", "")
        appimage = {"type": "appimage"}
        if sistema in ("debian", "ayusos"):
            return [appimage]
        if sistema == "ubuntu":
            if re.fullmatch(r"[0-9]{2,}\.[0-9]{2}", version) and tuple(map(int, version.split("."))) >= (26, 4):
                return [{"type": "deb", "package": "ghostty", "command": "ghostty"}, appimage]
            return [appimage]
        return []

    # -------------------------------------------------------------------------
    # Inicialización
    # -------------------------------------------------------------------------
    def _prepare_host_on_start(self):
        if self.sincronizando_reloj:
            return
        if (self.distribucion == "no-soportada"
                or self.preferencias.get("reloj_inicial_sincronizado") is True):
            self._prepare_initial_integration()
            return
        self.sincronizando_reloj = True
        self.status_label.set_text(traducir("Sincronizando el reloj del sistema…"))
        self._update_sensitivity()

        def sync():
            try:
                synced = core_clock.sincronizar(comando_host)
            except (OSError, subprocess.SubprocessError):
                synced = False
            GLib.idle_add(self._on_initial_clock_check, synced)

        threading.Thread(target=sync, daemon=True).start()

    def _on_initial_clock_check(self, sincronizado):
        if self.destruida:
            return GLib.SOURCE_REMOVE
        self.sincronizando_reloj = False
        self.aviso_reloj_inicial = not sincronizado
        if sincronizado:
            nuevas = dict(self.preferencias, reloj_inicial_sincronizado=True)
            try:
                guardar_preferencias(nuevas)
            except OSError as error:
                self._write_log("[!] %s: %s\n" % (
                    traducir("No se pudieron guardar las preferencias"), error), "aviso")
            self.preferencias = nuevas
        else:
            self._write_log("[!] %s\n" % traducir(
                "El reloj aún no está sincronizado. Se volverá a intentar al abrir AiO."), "aviso")
        self._update_sensitivity()
        self._prepare_initial_integration()
        return GLib.SOURCE_REMOVE

    def _prepare_initial_integration(self):
        fmt = formato_actualizacion()
        if fmt not in ("flatpak", "appimage") or self.distribucion == "no-soportada":
            self._query_task_states(initial=True)
            return
        self.programando = True
        self.status_label.set_text(traducir("Preparando el mantenimiento del sistema…"))
        self._update_sensitivity()
        version = version_app()

        def prepare():
            try:
                core_host_integration.prepare_host(fmt, version)
                error = None
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                error = str(exc)
            GLib.idle_add(self._on_host_prepared, error)

        threading.Thread(target=prepare, daemon=True).start()

    def _on_host_prepared(self, error):
        if self.destruida:
            return GLib.SOURCE_REMOVE
        self.programando = False
        self._update_sensitivity()
        if error:
            self._write_log("[!] %s %s\n" % (
                traducir("No se pudo preparar la integración del anfitrión."), error), "aviso")
        self._query_task_states(initial=True)
        return GLib.SOURCE_REMOVE

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------
    def _setup_css(self):
        pantalla = Gdk.Screen.get_default()
        if not getattr(pantalla, "_aio_estilo_aplicacion", None):
            proveedor = Gtk.CssProvider()
            proveedor.load_from_data(ESTILO_APLICACION)
            Gtk.StyleContext.add_provider_for_screen(
                pantalla, proveedor, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            pantalla._aio_estilo_aplicacion = proveedor

    def _build_header(self):
        callbacks = {
            "on_preferences": self._open_preferences,
            "on_history": self._show_history,
            "on_schedule": self._open_schedule,
            "on_host_guide": self._open_host_guide,
            "on_update": self._check_update,
            "on_about": self._about,
            "on_terminal": self._open_terminal,
        }
        self.header_bar = HeaderBar(self, self.datos_anfitrion, self.preferencias, callbacks)
        self.set_titlebar(self.header_bar)

    def _build_body(self):
        self.notebook = Gtk.Notebook()
        self.notebook.set_tab_pos(Gtk.PositionType.TOP)
        self.notebook.set_scrollable(True)
        self.add(self.notebook)

        # Crear páginas
        self.maintenance_page = MaintenancePage(self)
        self.recommended_page = RecommendedPage(self)
        self.backup_page = BackupPage(self)
        self.home_page = HomePage(self)
        self.terminal_page = TerminalPage(self)

        # Añadir en orden
        self.notebook.append_page(self.maintenance_page, Gtk.Label(label=traducir("Configuración y mantenimiento")))

        if HAS_SOFTWARE_MANAGER and not (es_flatpak() or os.environ.get("APPIMAGE") or os.environ.get("SNAP")):
            self.software_page = SoftwarePage(self)
            self.notebook.append_page(self.software_page, Gtk.Label(label=traducir("Gestor de software")))

        self.notebook.append_page(self.recommended_page, Gtk.Label(label=traducir("Apps recomendadas")))
        self.notebook.append_page(self.backup_page, Gtk.Label(label=traducir("Backup")))
        self.notebook.append_page(self.home_page, Gtk.Label(label=traducir("Inicio")))

        self.notebook.connect("switch-page", self._on_notebook_page_changed)

        # Status bar
        self.status_label = Gtk.Label(xalign=0, ellipsize=3)
        self.status_label.set_text(traducir("Listo"))
        self.notebook.set_action_widget(self.status_label, Gtk.PackType.END)

    # -------------------------------------------------------------------------
    # Callbacks de UI
    # -------------------------------------------------------------------------
    def _open_preferences(self, _btn=None):
        if self.programando or self.en_curso or self.comprobando_actualizacion:
            return
        dialog = PreferencesDialog(self, self.preferencias)
        dialog.connect("response", self._on_preferences_response)
        dialog.show_all()

    def _on_preferences_response(self, dialog, response):
        if response == Gtk.ResponseType.OK:
            nuevas = dialog.get_preferences()
            if nuevas != self.preferencias:
                try:
                    guardar_preferencias(nuevas)
                except OSError as error:
                    self._write_log("[!] %s: %s\n" % (
                        traducir("No se pudieron guardar las preferencias"), error), "aviso")
                else:
                    self.preferencias = nuevas
                    global IDIOMA_ACTUAL
                    IDIOMA_ACTUAL = nuevas["idioma"]
                    aplicar_tema(nuevas.get("tema", "sistema"))
                    self.header_bar.update_preferences(nuevas)
                    self.maintenance_page.on_preferences_changed(nuevas)
                    self.recommended_page.on_preferences_changed(nuevas)
        dialog.destroy()

    def _show_history(self, _btn=None):
        if self.programando or self.en_curso or self.comprobando_actualizacion:
            return
        from .history_dialog import HistoryDialog
        dialog = HistoryDialog(self)
        dialog.show_all()

    def _open_schedule(self, _btn=None):
        if self.programando or self.en_curso:
            return
        self.programacion.mostrar()

    def _open_host_guide(self, _btn=None):
        if self.programando or self.en_curso or self.comprobando_actualizacion:
            return
        # Implementation similar to original
        pass

    def _check_update(self, _btn=None):
        if self.comprobando_actualizacion:
            return
        self.comprobando_actualizacion = True
        self._update_sensitivity()
        self.status_label.set_text(traducir("Buscando actualizaciones…"))

        def check():
            try:
                release = obtener_release_actualizacion()
            except Exception as exc:
                GLib.idle_add(self._on_update_check_done, None, str(exc))
            else:
                GLib.idle_add(self._on_update_check_done, release, None)

        threading.Thread(target=check, daemon=True).start()

    def _on_update_check_done(self, release, error):
        self.comprobando_actualizacion = False
        self._update_sensitivity()
        if error:
            self._write_log("[!] %s: %s\n" % (traducir("Error buscando actualizaciones"), error), "error")
            self.status_label.set_text(traducir("Error buscando actualizaciones"))
            return
        if release:
            version_actual = version_app(para_apt=True)
            if core_updates.version_numerica(release["tag_name"].lstrip("v")) > core_updates.version_numerica(version_actual):
                self._show_update_available(release)
            else:
                self.status_label.set_text(traducir("Ya tienes la última versión"))
        else:
            self.status_label.set_text(traducir("No se pudo comprobar actualizaciones"))

    def _show_update_available(self, release):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                   message_type=Gtk.MessageType.INFO,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=traducir("Actualización disponible"))
        dialog.format_secondary_text(traducir("Versión %s disponible. ¿Quieres abrir la página de descarga?") % release["tag_name"])
        dialog.set_default_response(Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            import webbrowser
            webbrowser.open(release["html_url"])
        dialog.destroy()

    def _about(self, _btn=None):
        dialog = AboutDialog(self)
        dialog.show_all()

    def _open_terminal(self, _btn=None):
        self.terminal_page.show()

    def _on_notebook_page_changed(self, notebook, page, page_num):
        if hasattr(page, "on_page_activated"):
            page.on_page_activated()

    def _on_key_press(self, widget, event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if event.keyval == Gdk.KEY_r:
                self._refresh_current_page()
                return True
            elif event.keyval == Gdk.KEY_f:
                self._focus_search()
                return True
            elif event.keyval == Gdk.KEY_q:
                self._on_delete()
                return True
        return False

    def _refresh_current_page(self):
        page = self.notebook.get_nth_page(self.notebook.get_current_page())
        if hasattr(page, "refresh"):
            page.refresh()

    def _focus_search(self):
        page = self.notebook.get_nth_page(self.notebook.get_current_page())
        if hasattr(page, "focus_search"):
            page.focus_search()

    def _on_focus_in(self, widget, event):
        self.recommended_page.refresh_if_needed()
        return False

    def _on_delete(self, *args):
        if self.en_curso or self.programando or self.comprobando_actualizacion:
            return True
        self.destroy()
        return False

    def _on_destroy(self, _widget):
        self.destruida = True
        if self.ventana_terminal:
            self.ventana_terminal.destroy()
        Gtk.main_quit()

    # -------------------------------------------------------------------------
    # Utilidades
    # -------------------------------------------------------------------------
    def _write_log(self, texto, tipo="info"):
        self.maintenance_page.write_log(texto, tipo)

    def _update_sensitivity(self):
        sensitive = not (self.en_curso or self.programando or self.comprobando_actualizacion
                         or self.diagnostico_en_curso or self.backup_action_in_progress)
        self.header_bar.btn_menu.set_sensitive(sensitive)
        self.header_bar.btn_terminal.set_sensitive(sensitive)
        if hasattr(self, "software_page"):
            self.software_page.set_sensitive(sensitive)

    def _query_task_states(self, initial=False):
        self.maintenance_page.query_task_states(initial=initial)

    def _on_version_clicked(self, _btn, version):
        from aio_core import novedades_version
        dialogo = Gtk.Dialog(title=traducir("Novedades de esta versión"),
                             transient_for=self, modal=True)
        dialogo.add_button(traducir("Cerrar"), Gtk.ResponseType.CLOSE)
        dialogo.connect("response", lambda d, _r: d.destroy())

        ventana = self.get_window()
        monitor = self.get_display().get_monitor_at_window(ventana) if ventana else None
        area = monitor.get_workarea() if monitor else None
        ancho = min(820, area.width * 9 // 10) if area else 820
        alto = min(560, area.height * 9 // 10) if area else 560
        dialogo.set_default_size(ancho, alto)

        notas = novedades_version(version) or traducir("No hay notas para esta versión.")
        detalle = Gtk.TextView(editable=False, cursor_visible=False)
        detalle.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        detalle.set_left_margin(16)
        detalle.set_right_margin(16)
        detalle.set_top_margin(12)
        detalle.set_bottom_margin(12)
        detalle.set_pixels_below_lines(5)
        detalle.get_buffer().set_text(notas)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_overlay_scrolling(False)
        scroll.add(detalle)
        contenido = dialogo.get_content_area()
        contenido.set_border_width(12)
        contenido.pack_start(scroll, True, True, 0)
        dialogo.show_all()


# -------------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------------
def main():
    preferencias = cargar_preferencias()
    win = VentanaPrincipal(preferencias)
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()