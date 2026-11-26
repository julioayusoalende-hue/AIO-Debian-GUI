"""Pestañas y acciones del Centro de Control de AyusOS.

Este módulo se instala como extensión de aio-debian-gui; el core no conoce
nada de AyusOS. Los métodos se enlazan a la ventana principal en install().
"""

import json
import os
import subprocess
import threading

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GdkPixbuf, GLib, Gtk, Pango

from aio_core.constants import (
    traducir, etiqueta, tarjeta_mantenimiento, cabecera_mantenimiento,
    comando_host, HELPER_SISTEMA,
)
from .aio_core.ayusos_branding import ACENTOS


class AyusOSPagesMixin:
    def _pagina_ayusos_update(self):
        """Pestaña: Actualización de AyusOS (canal stable/testing)."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Estado actual
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Estado de AyusOS", "system-software-update-symbolic"), False, False, 0)

        self.ayusos_update_status = self._etiqueta_estado()
        caja.pack_start(self.ayusos_update_status, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=8)
        grid.set_border_width(4)
        caja.pack_start(grid, False, False, 0)

        self.ayusos_version_label = etiqueta("Versión actual: —")
        self.ayusos_channel_label = etiqueta("Canal: —")
        grid.attach(self.ayusos_version_label, 0, 0, 1, 1)
        grid.attach(self.ayusos_channel_label, 1, 0, 1, 1)

        self.ayusos_check_btn = Gtk.Button(label=traducir("Comprobar actualizaciones"))
        self.ayusos_check_btn.connect("clicked", self._ayusos_check_updates)
        caja.pack_start(self.ayusos_check_btn, False, False, 0)

        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Actualizar
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Actualizar sistema", "system-software-update-symbolic"), False, False, 0)

        channel_box = Gtk.Box(spacing=8)
        channel_box.pack_start(etiqueta("Canal:"), False, False, 0)
        self.ayusos_channel_combo = Gtk.ComboBoxText()
        self.ayusos_channel_combo.append("stable", traducir("Estable (recomendado)"))
        self.ayusos_channel_combo.append("testing", traducir("Testing (próxima versión)"))
        self.ayusos_channel_combo.set_active_id("stable")
        self.ayusos_channel_combo.set_sensitive(False)
        self.ayusos_channel_combo.set_tooltip_text(traducir("Usa el canal configurado en el sistema."))
        channel_box.pack_start(self.ayusos_channel_combo, False, False, 0)
        caja2.pack_start(channel_box, False, False, 0)

        self.ayusos_dryrun_check = Gtk.CheckButton(label=traducir("Solo simular (dry-run)"))
        self.ayusos_dryrun_check.set_sensitive(False)
        self.ayusos_dryrun_check.set_tooltip_text(traducir("La simulación se realiza dentro del actualizador del sistema."))
        caja2.pack_start(self.ayusos_dryrun_check, False, False, 0)

        self.ayusos_update_btn = Gtk.Button(label=traducir("Actualizar ahora"))
        self.ayusos_update_btn.get_style_context().add_class("suggested-action")
        self.ayusos_update_btn.connect("clicked", self._ayusos_do_update)
        caja2.pack_start(self.ayusos_update_btn, False, False, 0)

        contenido.pack_start(tarjeta2, False, False, 0)

        # Tarjeta: Changelog
        tarjeta3, caja3 = tarjeta_mantenimiento(10)
        caja3.pack_start(cabecera_mantenimiento("Notas de versión", "text-x-changelog-symbolic"), False, False, 0)
        self.ayusos_changelog_view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.ayusos_changelog_view.set_size_request(-1, 200)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.ayusos_changelog_view)
        caja3.pack_start(scrolled, True, True, 0)
        contenido.pack_start(tarjeta3, True, True, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _pagina_ayusos_snapshots(self):
        """Pestaña: Snapshots del sistema (Timeshift / Btrfs)."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Estado
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Estado de snapshots", "drive-harddisk-symbolic"), False, False, 0)

        self.snapshots_status = self._etiqueta_estado()
        caja.pack_start(self.snapshots_status, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=8)
        grid.set_border_width(4)
        caja.pack_start(grid, False, False, 0)

        self.snapshots_btrfs_label = etiqueta("Btrfs: —")
        self.snapshots_timeshift_label = etiqueta("Timeshift: —")
        self.snapshots_grub_label = etiqueta("grub-btrfs: —")
        grid.attach(self.snapshots_btrfs_label, 0, 0, 1, 1)
        grid.attach(self.snapshots_timeshift_label, 1, 0, 1, 1)
        grid.attach(self.snapshots_grub_label, 0, 1, 2, 1)

        btn_row = Gtk.Box(spacing=8)
        self.snapshots_refresh_btn = Gtk.Button(label=traducir("Actualizar estado"))
        self.snapshots_refresh_btn.connect("clicked", self._snapshots_refresh)
        btn_row.pack_start(self.snapshots_refresh_btn, False, False, 0)

        self.snapshots_grub_update_btn = Gtk.Button(label=traducir("Actualizar GRUB"))
        self.snapshots_grub_update_btn.connect("clicked", self._snapshots_grub_update)
        btn_row.pack_start(self.snapshots_grub_update_btn, False, False, 0)
        caja.pack_start(btn_row, False, False, 0)

        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Crear snapshot
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Crear snapshot", "document-new-symbolic"), False, False, 0)

        comment_box = Gtk.Box(spacing=8)
        comment_box.pack_start(etiqueta("Comentario:"), False, False, 0)
        self.snapshots_comment = Gtk.Entry(placeholder_text=traducir("Ej: Antes de actualización"))
        comment_box.pack_start(self.snapshots_comment, True, True, 0)
        caja2.pack_start(comment_box, False, False, 0)

        tags_box = Gtk.Box(spacing=8)
        tags_box.pack_start(etiqueta("Tipo:"), False, False, 0)
        self.snapshots_tags = Gtk.ComboBoxText()
        for tag_id, tag_name in [("O", "Bajo demanda"), ("B", "Arranque"), ("H", "Horario"), ("D", "Diario"), ("W", "Semanal"), ("M", "Mensual"), ("Y", "Anual")]:
            self.snapshots_tags.append(tag_id, traducir(tag_name))
        self.snapshots_tags.set_active_id("O")
        tags_box.pack_start(self.snapshots_tags, False, False, 0)
        caja2.pack_start(tags_box, False, False, 0)

        self.snapshots_create_btn = Gtk.Button(label=traducir("Crear snapshot ahora"))
        self.snapshots_create_btn.get_style_context().add_class("suggested-action")
        self.snapshots_create_btn.connect("clicked", self._snapshots_create)
        caja2.pack_start(self.snapshots_create_btn, False, False, 0)

        contenido.pack_start(tarjeta2, False, False, 0)

        # Tarjeta: Lista de snapshots
        tarjeta3, caja3 = tarjeta_mantenimiento(10)
        caja3.pack_start(cabecera_mantenimiento("Snapshots existentes", "view-list-symbolic"), False, False, 0)

        self.snapshots_list = Gtk.TreeView()
        self.snapshots_list.set_headers_visible(True)
        store = Gtk.ListStore(str, str, str, str, str)  # id, date, tags, comment, type
        self.snapshots_list.set_model(store)

        for i, title in enumerate(["ID", traducir("Fecha"), traducir("Tipo"), traducir("Comentario"), ""]):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=i)
            col.set_resizable(True)
            self.snapshots_list.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(-1, 250)
        scrolled.add(self.snapshots_list)
        caja3.pack_start(scrolled, True, True, 0)

        actions = Gtk.Box(spacing=8)
        self.snapshots_restore_btn = Gtk.Button(label=traducir("Restaurar seleccionado"))
        self.snapshots_restore_btn.connect("clicked", self._snapshots_restore)
        self.snapshots_delete_btn = Gtk.Button(label=traducir("Eliminar seleccionado"))
        self.snapshots_delete_btn.connect("clicked", self._snapshots_delete)
        actions.pack_start(self.snapshots_restore_btn, False, False, 0)
        actions.pack_end(self.snapshots_delete_btn, False, False, 0)
        caja3.pack_start(actions, False, False, 0)

        contenido.pack_start(tarjeta3, True, True, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _pagina_ayusos_hardware(self):
        """Pestaña: Perfil de hardware (laptop/desktop/gaming/workstation/server)."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Detección
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Perfil de hardware", "computer-symbolic"), False, False, 0)

        self.hardware_status = self._etiqueta_estado()
        caja.pack_start(self.hardware_status, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=8)
        grid.set_border_width(4)
        caja.pack_start(grid, False, False, 0)

        self.hardware_detected_label = etiqueta("Detectado: —")
        self.hardware_cpu_label = etiqueta("CPU: —")
        self.hardware_ram_label = etiqueta("RAM: —")
        self.hardware_gpu_label = etiqueta("GPU: —")
        grid.attach(self.hardware_detected_label, 0, 0, 2, 1)
        grid.attach(self.hardware_cpu_label, 0, 1, 1, 1)
        grid.attach(self.hardware_ram_label, 1, 1, 1, 1)
        grid.attach(self.hardware_gpu_label, 0, 2, 2, 1)

        btn_row = Gtk.Box(spacing=8)
        self.hardware_refresh_btn = Gtk.Button(label=traducir("Detectar hardware"))
        self.hardware_refresh_btn.connect("clicked", self._hardware_refresh)
        btn_row.pack_start(self.hardware_refresh_btn, False, False, 0)

        self.hardware_info_btn = Gtk.Button(label=traducir("Información completa"))
        self.hardware_info_btn.connect("clicked", self._hardware_show_info)
        btn_row.pack_start(self.hardware_info_btn, False, False, 0)
        caja.pack_start(btn_row, False, False, 0)

        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Aplicar perfil
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Aplicar perfil optimizado", "preferences-system-symbolic"), False, False, 0)

        profile_box = Gtk.Box(spacing=8)
        profile_box.pack_start(etiqueta("Perfil:"), False, False, 0)
        self.hardware_profile_combo = Gtk.ComboBoxText()
        profiles = [
            ("laptop", "Portátil (ahorro batería, térmicas)"),
            ("desktop", "Escritorio (rendimiento equilibrado)"),
            ("gaming", "Gaming (latencia baja, GPU máxima)"),
            ("workstation", "Workstation (cargas profesionales)"),
            ("server", "Servidor (throughput, estabilidad)"),
        ]
        for pid, pname in profiles:
            self.hardware_profile_combo.append(pid, traducir(pname))
        self.hardware_profile_combo.set_active_id("laptop")
        profile_box.pack_start(self.hardware_profile_combo, True, True, 0)
        caja2.pack_start(profile_box, False, False, 0)

        self.hardware_apply_btn = Gtk.Button(label=traducir("Aplicar perfil"))
        self.hardware_apply_btn.get_style_context().add_class("suggested-action")
        self.hardware_apply_btn.connect("clicked", self._hardware_apply_profile)
        caja2.pack_start(self.hardware_apply_btn, False, False, 0)

        contenido.pack_start(tarjeta2, False, False, 0)

        # Tarjeta: Servicios activos
        tarjeta3, caja3 = tarjeta_mantenimiento(10)
        caja3.pack_start(cabecera_mantenimiento("Servicios de hardware", "system-run-symbolic"), False, False, 0)

        self.hardware_services_store = Gtk.ListStore(str, str, str)  # servicio, estado, perfil
        self.hardware_services_view = Gtk.TreeView(model=self.hardware_services_store)
        self.hardware_services_view.set_headers_visible(True)
        for i, title in enumerate([traducir("Servicio"), traducir("Estado"), traducir("Perfil")]):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=i)
            col.set_resizable(True)
            self.hardware_services_view.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(-1, 200)
        scrolled.add(self.hardware_services_view)
        caja3.pack_start(scrolled, True, True, 0)

        contenido.pack_start(tarjeta3, True, True, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _pagina_ayusos_diagnostics(self):
        """Pestaña: Diagnósticos completos del sistema."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Ejecutar diagnóstico
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Diagnóstico completo", "dialog-information-symbolic"), False, False, 0)

        self.diagnostics_status = self._etiqueta_estado()
        caja.pack_start(self.diagnostics_status, False, False, 0)

        self.diagnostics_run_btn = Gtk.Button(label=traducir("Ejecutar diagnóstico completo"))
        self.diagnostics_run_btn.get_style_context().add_class("suggested-action")
        self.diagnostics_run_btn.connect("clicked", self._diagnostics_run)
        caja.pack_start(self.diagnostics_run_btn, False, False, 0)

        self.diagnostics_extensions_btn = Gtk.Button(label=traducir("Reparar extensiones de GNOME"))
        self.diagnostics_extensions_btn.connect("clicked", self._diagnostics_repair_extensions)
        caja.pack_start(self.diagnostics_extensions_btn, False, False, 0)

        self.diagnostics_recovery_btn = Gtk.Button(label=traducir("Abrir recuperación"))
        self.diagnostics_recovery_btn.connect("clicked", lambda _boton: self._abrir_recuperacion())
        caja.pack_start(self.diagnostics_recovery_btn, False, False, 0)

        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Resultados
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Resultados", "view-list-symbolic"), False, False, 0)

        self.diagnostics_store = Gtk.ListStore(str, str, str)  # check, estado, mensaje
        self.diagnostics_view = Gtk.TreeView(model=self.diagnostics_store)
        self.diagnostics_view.set_headers_visible(True)
        for i, title in enumerate([traducir("Comprobación"), traducir("Estado"), traducir("Detalle")]):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=i)
            col.set_resizable(True)
            self.diagnostics_view.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(-1, 350)
        scrolled.add(self.diagnostics_view)
        caja2.pack_start(scrolled, True, True, 0)

        contenido.pack_start(tarjeta2, True, True, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _pagina_ayusos_branding(self):
        """Pestaña: Apariencia (tema, acento, fondos, Plymouth)."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Tema y acento
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Tema y color de acento", "preferences-desktop-theme-symbolic"), False, False, 0)

        self.branding_status = self._etiqueta_estado()
        caja.pack_start(self.branding_status, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=8)
        grid.set_border_width(4)
        caja.pack_start(grid, False, False, 0)

        # Tema
        grid.attach(etiqueta("Tema GTK:"), 0, 0, 1, 1)
        self.branding_theme = Gtk.ComboBoxText()
        for t in ["system", "light", "dark"]:
            self.branding_theme.append(t, traducir({"system": "Sistema", "light": "Claro", "dark": "Oscuro"}[t]))
        self.branding_theme.set_active_id("system")
        grid.attach(self.branding_theme, 1, 0, 1, 1)

        # Acento
        grid.attach(etiqueta("Color de acento:"), 0, 1, 1, 1)
        self.branding_accent = Gtk.ComboBoxText()
        for acc_id, acc_data in ACENTOS.items():
            self.branding_accent.append(acc_id, acc_data["name"])
        self.branding_accent.set_active_id("ayusos")
        grid.attach(self.branding_accent, 1, 1, 1, 1)

        # Wallpaper mode
        grid.attach(etiqueta("Fondo de pantalla:"), 0, 2, 1, 1)
        self.branding_wallpaper_mode = Gtk.ComboBoxText()
        for wm in ["auto", "light", "dark", "custom"]:
            self.branding_wallpaper_mode.append(wm, traducir({"auto": "Auto (claro/oscuro)", "light": "Solo claro", "dark": "Solo oscuro", "custom": "Personalizado"}[wm]))
        self.branding_wallpaper_mode.set_active_id("auto")
        grid.attach(self.branding_wallpaper_mode, 1, 2, 1, 1)

        btn_row = Gtk.Box(spacing=8)
        self.branding_apply_btn = Gtk.Button(label=traducir("Aplicar todo"))
        self.branding_apply_btn.get_style_context().add_class("suggested-action")
        self.branding_apply_btn.connect("clicked", self._branding_apply_all)
        btn_row.pack_start(self.branding_apply_btn, False, False, 0)

        self.branding_refresh_btn = Gtk.Button(label=traducir("Actualizar estado"))
        self.branding_refresh_btn.connect("clicked", self._branding_refresh)
        btn_row.pack_start(self.branding_refresh_btn, False, False, 0)
        grid.attach(btn_row, 0, 3, 2, 1)

        caja.pack_start(grid, False, False, 0)
        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Fondos disponibles
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Fondos de pantalla", "preferences-desktop-wallpaper-symbolic"), False, False, 0)

        self.branding_wallpapers_grid = self._rejilla_tarjetas()
        caja2.pack_start(self._scroll_tarjetas(self.branding_wallpapers_grid), True, True, 0)
        contenido.pack_start(tarjeta2, True, True, 0)

        # Tarjeta: Plymouth
        tarjeta3, caja3 = tarjeta_mantenimiento(10)
        caja3.pack_start(cabecera_mantenimiento("Tema de arranque (Plymouth)", "system-reboot-symbolic"), False, False, 0)

        plymouth_box = Gtk.Box(spacing=8)
        plymouth_box.pack_start(etiqueta("Tema:"), False, False, 0)
        self.branding_plymouth = Gtk.ComboBoxText()
        self.branding_plymouth.append("ayusos", traducir("AyusOS"))
        self.branding_plymouth.append("bgrt", "BGRTSimple")
        self.branding_plymouth.append("spinner", "Spinner")
        self.branding_plymouth.set_active_id("ayusos")
        plymouth_box.pack_start(self.branding_plymouth, False, False, 0)

        self.branding_plymouth_btn = Gtk.Button(label=traducir("Aplicar tema"))
        self.branding_plymouth_btn.connect("clicked", self._branding_apply_plymouth)
        plymouth_box.pack_start(self.branding_plymouth_btn, False, False, 0)
        caja3.pack_start(plymouth_box, False, False, 0)

        contenido.pack_start(tarjeta3, False, False, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _pagina_ayusos_autorizacion(self):
        """Pestaña: Autorización sin contraseña para administradores."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Estado actual
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Autorización AiO", "preferences-system-symbolic"), False, False, 0)

        self.autorizacion_status = self._etiqueta_estado()
        caja.pack_start(self.autorizacion_status, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=8)
        grid.set_border_width(4)
        caja.pack_start(grid, False, False, 0)

        self.autorizacion_usuarios_label = etiqueta("Administradores autorizados: —")
        grid.attach(self.autorizacion_usuarios_label, 0, 0, 2, 1)

        btn_row = Gtk.Box(spacing=8)
        self.autorizacion_refresh_btn = Gtk.Button(label=traducir("Actualizar estado"))
        self.autorizacion_refresh_btn.connect("clicked", self._autorizacion_refresh)
        btn_row.pack_start(self.autorizacion_refresh_btn, False, False, 0)

        self.autorizacion_aplicar_btn = Gtk.Button(label=traducir("Aplicar a todos los administradores"))
        self.autorizacion_aplicar_btn.get_style_context().add_class("suggested-action")
        self.autorizacion_aplicar_btn.connect("clicked", self._autorizacion_aplicar)
        btn_row.pack_start(self.autorizacion_aplicar_btn, False, False, 0)
        grid.attach(btn_row, 0, 1, 2, 1)

        caja.pack_start(grid, False, False, 0)
        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Usuarios actuales
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Usuarios con acceso sin contraseña", "system-users-symbolic"), False, False, 0)

        self.autorizacion_list = Gtk.TreeView()
        self.autorizacion_list.set_headers_visible(True)
        store = Gtk.ListStore(str, str, str)  # username, uid, status
        self.autorizacion_list.set_model(store)

        for i, title in enumerate([traducir("Usuario"), traducir("UID"), traducir("Estado")]):
            renderer = Gtk.CellRendererText()
            col = Gtk.TreeViewColumn(title, renderer, text=i)
            col.set_resizable(True)
            self.autorizacion_list.append_column(col)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(-1, 200)
        scrolled.add(self.autorizacion_list)
        caja2.pack_start(scrolled, True, True, 0)

        actions = Gtk.Box(spacing=8)
        self.autorizacion_remove_btn = Gtk.Button(label=traducir("Revocar acceso"))
        self.autorizacion_remove_btn.connect("clicked", self._autorizacion_revocar)
        actions.pack_end(self.autorizacion_remove_btn, False, False, 0)
        caja2.pack_start(actions, False, False, 0)

        contenido.pack_start(tarjeta2, True, True, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _autorizacion_refresh(self, _boton):
        self.autorizacion_refresh_btn.set_sensitive(False)
        self.autorizacion_status.set_text(traducir("Cargando estado…"))

        def cargar():
            try:
                import subprocess, json
                result = subprocess.run(
                    ["/usr/local/libexec/ayusos-aio-autorizar", "status"],
                    capture_output=True, text=True, timeout=10
                )
                # El script imprime a stdout, no JSON. Parseamos.
                usuarios = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip().startswith('- '):
                        # Formato: "  - user (UID 1000)"
                        parts = line.strip()[2:].split(' (UID ')
                        if len(parts) == 2:
                            usuarios.append((parts[0], parts[1].rstrip(')')))
                GLib.idle_add(self._autorizacion_refresh_done, True, usuarios)
            except (OSError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._autorizacion_refresh_done, False, str(exc))

        threading.Thread(target=cargar, daemon=True).start()

    def _autorizacion_refresh_done(self, ok, data):
        self.autorizacion_refresh_btn.set_sensitive(True)
        if not ok:
            self.autorizacion_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        # Actualizar etiqueta resumen
        count = len(data)
        self.autorizacion_usuarios_label.set_text(traducir("Administradores autorizados: %d") % count)

        # Actualizar lista
        store = self.autorizacion_list.get_model()
        store.clear()
        for username, uid in data:
            store.append([username, uid, traducir("Activo")])

        self.autorizacion_status.set_text(traducir("Estado actualizado."))
        return GLib.SOURCE_REMOVE

    def _autorizacion_aplicar(self, _boton):
        self.autorizacion_aplicar_btn.set_sensitive(False)
        self.autorizacion_status.set_text(traducir("Aplicando autorización a todos los administradores…"))

        def aplicar():
            try:
                import subprocess, json
                result = subprocess.run(
                    ["/usr/local/libexec/ayusos-aio-autorizar", "apply"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    GLib.idle_add(self._autorizacion_aplicar_done, True, result.stdout)
                else:
                    GLib.idle_add(self._autorizacion_aplicar_done, False, result.stderr or result.stdout)
            except (OSError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._autorizacion_aplicar_done, False, str(exc))

        threading.Thread(target=aplicar, daemon=True).start()

    def _autorizacion_aplicar_done(self, ok, data):
        self.autorizacion_aplicar_btn.set_sensitive(True)
        if not ok:
            self.autorizacion_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        self.autorizacion_status.set_text(traducir("Autorización aplicada correctamente."))
        self._autorizacion_refresh(None)
        return GLib.SOURCE_REMOVE

    def _autorizacion_revocar(self, _boton):
        selection = self.autorizacion_list.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            return
        username = model[treeiter][0]
        uid = model[treeiter][1]

        # Confirmar
        dialog = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=traducir("¿Revocar el acceso sin contraseña para %s?") % username,
        )
        dialog.format_secondary_text(traducir("El usuario seguirá siendo administrador, pero necesitará contraseña para operaciones de AiO."))
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        self.autorizacion_remove_btn.set_sensitive(False)
        self.autorizacion_status.set_text(traducir("Revocando acceso para %s…") % username)

        def revocar():
            try:
                import subprocess, json
                result = subprocess.run(
                    ["/usr/local/libexec/ayusos-aio-limpiar-usuario", username],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    GLib.idle_add(self._autorizacion_revocar_done, True, username)
                else:
                    GLib.idle_add(self._autorizacion_revocar_done, False, result.stderr or result.stdout)
            except (OSError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._autorizacion_revocar_done, False, str(exc))

        threading.Thread(target=revocar, daemon=True).start()

    def _autorizacion_revocar_done(self, ok, data):
        self.autorizacion_remove_btn.set_sensitive(True)
        if not ok:
            self.autorizacion_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        self.autorizacion_status.set_text(traducir("Acceso revocado para %s.") % data)
        self._autorizacion_refresh(None)
        return GLib.SOURCE_REMOVE

    def _ayusos_check_updates(self, _boton):
        self.ayusos_check_btn.set_sensitive(False)
        self.ayusos_update_status.set_text(traducir("Comprobando actualizaciones…"))

        def comprobar():
            try:
                from .aio_core import ayusos_update
                import json
                result = json.loads(ayusos_update.cli_check_updates())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._ayusos_check_done, False, str(exc))
            else:
                GLib.idle_add(self._ayusos_check_done, True, result)

        threading.Thread(target=comprobar, daemon=True).start()

    def _ayusos_check_done(self, ok, data):
        self.ayusos_check_btn.set_sensitive(True)
        if not ok:
            self.ayusos_update_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        update_available = data.get("update_available", False)
        current = data.get("current_version", "?")
        new_ver = data.get("new_version")
        channel = data.get("channel", "stable")

        self.ayusos_version_label.set_text(traducir("Versión actual: %s") % current)
        self.ayusos_channel_label.set_text(traducir("Canal: %s") % ("Testing" if channel == "testing" else "Estable"))

        if update_available and new_ver:
            self.ayusos_update_status.set_text(traducir("¡Actualización disponible: %s!") % new_ver)
            self.ayusos_update_btn.set_sensitive(True)
            # Cargar changelog
            try:
                from .aio_core import ayusos_update
                changelog = ayusos_update.get_changelog(new_ver)
                buffer = self.ayusos_changelog_view.get_buffer()
                buffer.set_text(changelog or traducir("Sin notas disponibles."))
            except Exception:
                pass
        else:
            self.ayusos_update_status.set_text(traducir("Sistema actualizado (versión %s).") % current)
            self.ayusos_update_btn.set_sensitive(False)
            buffer = self.ayusos_changelog_view.get_buffer()
            buffer.set_text(traducir("No hay actualizaciones pendientes."))

        return GLib.SOURCE_REMOVE

    def _ayusos_do_update(self, _boton):
        """Abre el actualizador del sistema dentro del Centro de Control."""
        try:
            subprocess.Popen([
                "gnome-terminal", "--title", traducir("Actualizar AyusOS"),
                "--", "/usr/lib/ayusos/actualizar-terminal",
            ])
        except OSError as exc:
            self.ayusos_update_status.set_text(traducir("No se pudo abrir el actualizador: %s") % exc)
            return
        self.ayusos_update_status.set_text(traducir(
            "Actualizador abierto. Sigue las instrucciones en la terminal."
        ))

    def _snapshots_refresh(self, _boton):
        self.snapshots_refresh_btn.set_sensitive(False)
        self.snapshots_status.set_text(traducir("Cargando estado…"))

        def cargar():
            try:
                from .aio_core import ayusos_snapshots
                import json
                result = json.loads(ayusos_snapshots.cli_snapshot_status())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._snapshots_refresh_done, False, str(exc))
            else:
                GLib.idle_add(self._snapshots_refresh_done, True, result)

        threading.Thread(target=cargar, daemon=True).start()

    def _snapshots_refresh_done(self, ok, data):
        self.snapshots_refresh_btn.set_sensitive(True)
        if not ok:
            self.snapshots_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        btrfs = data.get("btrfs_root", False)
        timeshift = data.get("timeshift_installed", False)
        grub_btrfs = data.get("grub_btrfs_active", False)

        self.snapshots_btrfs_label.set_text(traducir("Btrfs: %s") % ("Sí" if btrfs else "No"))
        self.snapshots_timeshift_label.set_text(traducir("Timeshift: %s") % ("Sí" if timeshift else "No"))
        self.snapshots_grub_label.set_text(traducir("grub-btrfs: %s") % ("Activo" if grub_btrfs else "Inactivo"))

        # Cargar lista de snapshots
        store = self.snapshots_list.get_model()
        store.clear()
        for snap in data.get("timeshift_snapshots", [])[:50]:
            store.append([snap.get("id", ""), snap.get("date", ""), snap.get("tags", ""), snap.get("comment", ""), "timeshift"])
        for snap in data.get("btrfs_snapshots", [])[:50]:
            store.append([snap.get("id", ""), snap.get("path", ""), "", "", "btrfs"])

        self.snapshots_status.set_text(traducir("Estado actualizado."))
        return GLib.SOURCE_REMOVE

    def _snapshots_create(self, _boton):
        comment = self.snapshots_comment.get_text().strip() or "Snapshot AiO"
        tags = self.snapshots_tags.get_active_id() or "O"

        self.snapshots_create_btn.set_sensitive(False)
        self.snapshots_status.set_text(traducir("Creando snapshot…"))

        def crear():
            try:
                from .aio_core import ayusos_snapshots
                import json
                result = json.loads(ayusos_snapshots.cli_create_snapshot(comment, tags))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._snapshots_create_done, False, str(exc))
            else:
                GLib.idle_add(self._snapshots_create_done, True, result)

        threading.Thread(target=crear, daemon=True).start()

    def _snapshots_create_done(self, ok, data):
        self.snapshots_create_btn.set_sensitive(True)
        if not ok:
            self.snapshots_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        success = data.get("success", False)
        message = data.get("message", "")
        if success:
            self.snapshots_status.set_text(traducir("Snapshot creado: %s") % message)
            self._snapshots_refresh(None)
        else:
            self.snapshots_status.set_text(traducir("Error creando snapshot: %s") % message)
        return GLib.SOURCE_REMOVE

    def _snapshots_restore(self, _boton):
        selection = self.snapshots_list.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            self._mensaje(Gtk.MessageType.INFO, traducir("Sin selección"), traducir("Selecciona un snapshot de la lista."))
            return

        snap_id = model.get_value(treeiter, 0)
        if not snap_id:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO, text=traducir("¿Restaurar snapshot %s?") % snap_id
        )
        dialog.format_secondary_text(traducir(
            "Esto revertirá el sistema al estado del snapshot. Requerirá reinicio."
        ))
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        self.snapshots_restore_btn.set_sensitive(False)
        self.snapshots_status.set_text(traducir("Restaurando snapshot…"))

        def restaurar():
            try:
                from .aio_core import ayusos_snapshots
                import json
                result = json.loads(ayusos_snapshots.cli_restore_snapshot(snap_id))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._snapshots_restore_done, False, str(exc))
            else:
                GLib.idle_add(self._snapshots_restore_done, True, result)

        threading.Thread(target=restaurar, daemon=True).start()

    def _snapshots_restore_done(self, ok, data):
        self.snapshots_restore_btn.set_sensitive(True)
        if not ok:
            self.snapshots_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        success = data.get("success", False)
        message = data.get("message", "")
        if success:
            self.snapshots_status.set_text(traducir("Snapshot restaurado. Reinicia para aplicar: %s") % message)
        else:
            self.snapshots_status.set_text(traducir("Error restaurando: %s") % message)
        return GLib.SOURCE_REMOVE

    def _snapshots_delete(self, _boton):
        selection = self.snapshots_list.get_selection()
        model, treeiter = selection.get_selected()
        if not treeiter:
            self._mensaje(Gtk.MessageType.INFO, traducir("Sin selección"), traducir("Selecciona un snapshot de la lista."))
            return

        snap_id = model.get_value(treeiter, 0)
        if not snap_id:
            return

        dialog = Gtk.MessageDialog(
            transient_for=self, message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO, text=traducir("¿Eliminar snapshot %s?") % snap_id
        )
        dialog.format_secondary_text(traducir("Esta acción no se puede deshacer."))
        response = dialog.run()
        dialog.destroy()

        if response != Gtk.ResponseType.YES:
            return

        self.snapshots_delete_btn.set_sensitive(False)
        self.snapshots_status.set_text(traducir("Eliminando snapshot…"))

        def eliminar():
            try:
                from .aio_core import ayusos_snapshots
                import json
                result = json.loads(ayusos_snapshots.cli_delete_snapshot(snap_id))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._snapshots_delete_done, False, str(exc))
            else:
                GLib.idle_add(self._snapshots_delete_done, True, result)

        threading.Thread(target=eliminar, daemon=True).start()

    def _snapshots_delete_done(self, ok, data):
        self.snapshots_delete_btn.set_sensitive(True)
        if not ok:
            self.snapshots_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        success = data.get("success", False)
        message = data.get("message", "")
        if success:
            self.snapshots_status.set_text(traducir("Snapshot eliminado: %s") % message)
            self._snapshots_refresh(None)
        else:
            self.snapshots_status.set_text(traducir("Error eliminando: %s") % message)
        return GLib.SOURCE_REMOVE

    def _snapshots_grub_update(self, _boton):
        self.snapshots_grub_update_btn.set_sensitive(False)
        self.snapshots_status.set_text(traducir("Actualizando menú GRUB…"))

        def actualizar():
            try:
                from .aio_core import ayusos_snapshots
                import json
                result = json.loads(ayusos_snapshots.cli_grub_btrfs_update())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._snapshots_grub_done, False, str(exc))
            else:
                GLib.idle_add(self._snapshots_grub_done, True, result)

        threading.Thread(target=actualizar, daemon=True).start()

    def _snapshots_grub_done(self, ok, data):
        self.snapshots_grub_update_btn.set_sensitive(True)
        if not ok:
            self.snapshots_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        success = data.get("success", False)
        message = data.get("message", "")
        self.snapshots_status.set_text(traducir("GRUB actualizado: %s") % message if success else traducir("Error: %s") % message)
        return GLib.SOURCE_REMOVE

    def _hardware_refresh(self, _boton):
        self.hardware_refresh_btn.set_sensitive(False)
        self.hardware_status.set_text(traducir("Detectando hardware…"))

        def detectar():
            try:
                from .aio_core import ayusos_hardware
                import json
                info = json.loads(ayusos_hardware.cli_hardware_info())
                profile = json.loads(ayusos_hardware.cli_detect_profile())
                status = json.loads(ayusos_hardware.cli_profile_status())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._hardware_refresh_done, False, str(exc))
            else:
                GLib.idle_add(self._hardware_refresh_done, True, info, profile, status)

        threading.Thread(target=detectar, daemon=True).start()

    def _hardware_refresh_done(self, ok, *args):
        self.hardware_refresh_btn.set_sensitive(True)
        if not ok:
            self.hardware_status.set_text(traducir("Error: %s") % args[0])
            return GLib.SOURCE_REMOVE

        info, profile, status = args[0], args[1], args[2]

        detected = profile.get("profile", "unknown")
        self.hardware_detected_label.set_text(traducir("Detectado: %s") % status.get("profiles", {}).get(detected, detected))
        self.hardware_cpu_label.set_text(traducir("CPU: %s (%d núcleos)") % (info.get("cpu_model", "?"), info.get("cpu_cores", 0)))
        self.hardware_ram_label.set_text(traducir("RAM: %s GB") % info.get("ram_total_gb", "?"))
        gpus = info.get("gpus", [])
        self.hardware_gpu_label.set_text(traducir("GPU: %s") % (", ".join(gpus) if gpus else "No detectada"))

        # Servicios
        store = self.hardware_services_store
        store.clear()
        for svc, active in status.get("active_services", {}).items():
            store.append([svc, traducir("Activo" if active else "Inactivo"), ""])

        self.hardware_status.set_text(traducir("Detección completada."))
        return GLib.SOURCE_REMOVE

    def _hardware_show_info(self, _boton):
        self._hardware_refresh(None)

    def _hardware_apply_profile(self, _boton):
        profile = self.hardware_profile_combo.get_active_id()
        if not profile:
            return

        self.hardware_apply_btn.set_sensitive(False)
        self.hardware_status.set_text(traducir("Aplicando perfil %s…") % profile)

        def aplicar():
            try:
                from .aio_core import ayusos_hardware
                import json
                result = json.loads(ayusos_hardware.cli_apply_profile(profile))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._hardware_apply_done, False, str(exc))
            else:
                GLib.idle_add(self._hardware_apply_done, True, result)

        threading.Thread(target=aplicar, daemon=True).start()

    def _hardware_apply_done(self, ok, data):
        self.hardware_apply_btn.set_sensitive(True)
        if not ok:
            self.hardware_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        success = data.get("success", False)
        message = data.get("message", "")
        if success:
            self.hardware_status.set_text(traducir("Perfil aplicado: %s") % message)
            self._hardware_refresh(None)
        else:
            self.hardware_status.set_text(traducir("Error aplicando perfil: %s") % message)
        return GLib.SOURCE_REMOVE

    def _diagnostics_run(self, _boton):
        self.diagnostics_run_btn.set_sensitive(False)
        self.diagnostics_status.set_text(traducir("Ejecutando diagnóstico completo…"))
        self.diagnostics_store.clear()

        def diagnosticar():
            try:
                from .aio_core import ayusos_diagnostics
                import json
                result = json.loads(ayusos_diagnostics.cli_diagnostics())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._diagnostics_done, False, str(exc))
            else:
                GLib.idle_add(self._diagnostics_done, True, result)

        threading.Thread(target=diagnosticar, daemon=True).start()

    def _diagnostics_done(self, ok, data):
        self.diagnostics_run_btn.set_sensitive(True)
        if not ok:
            self.diagnostics_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        # Llenar árbol de resultados
        for check_name, check_data in data.items():
            if check_name.startswith("_"):
                continue
            ok_check = check_data.get("ok", False)
            msg = check_data.get("message") or check_data.get("details", "")
            self.diagnostics_store.append([
                check_name.replace("_", " ").title(),
                traducir("✓ OK") if ok_check else traducir("✗ FALLO"),
                str(msg)
            ])

        summary = data.get("_summary", {})
        passed = summary.get("passed", 0)
        total = summary.get("total", 0)
        self.diagnostics_status.set_text(traducir("Diagnóstico completado: %d/%d OK") % (passed, total))
        return GLib.SOURCE_REMOVE

    def _branding_refresh(self, _boton):
        self.branding_refresh_btn.set_sensitive(False)
        self.branding_status.set_text(traducir("Cargando estado…"))

        def cargar():
            try:
                from .aio_core import ayusos_branding
                import json
                result = json.loads(ayusos_branding.cli_branding_status())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._branding_refresh_done, False, str(exc))
            else:
                GLib.idle_add(self._branding_refresh_done, True, result)

        threading.Thread(target=cargar, daemon=True).start()

    def _branding_refresh_done(self, ok, data):
        self.branding_refresh_btn.set_sensitive(True)
        if not ok:
            self.branding_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        self.branding_theme.set_active_id(data.get("theme", "system"))
        self.branding_accent.set_active_id(data.get("accent", "ayusos"))
        self.branding_wallpaper_mode.set_active_id(data.get("wallpaper_mode", "auto"))

        # Cargar wallpapers
        grid = self.branding_wallpapers_grid
        for child in grid.get_children():
            grid.remove(child)
        for wp in data.get("available_wallpapers", []):
            grid.add(self._crear_tarjeta_wallpaper(wp))
        grid.show_all()

        self.branding_status.set_text(traducir("Estado actualizado."))
        return GLib.SOURCE_REMOVE

    def _branding_set_wallpaper(self, _boton, path):
        self.branding_status.set_text(traducir("Aplicando fondo…"))
        def aplicar():
            try:
                from .aio_core import ayusos_branding
                import json
                result = json.loads(ayusos_branding.cli_set_wallpaper(path, "both"))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._branding_wallpaper_done, False, str(exc))
            else:
                GLib.idle_add(self._branding_wallpaper_done, True, result)
        threading.Thread(target=aplicar, daemon=True).start()

    def _branding_wallpaper_done(self, ok, data):
        if not ok:
            self.branding_status.set_text(traducir("Error: %s") % data)
        else:
            self.branding_status.set_text(traducir("Fondo aplicado correctamente."))
        return GLib.SOURCE_REMOVE

    def _branding_apply_all(self, _boton):
        self.branding_apply_btn.set_sensitive(False)
        self.branding_status.set_text(traducir("Aplicando tema, acento y fondos…"))

        theme = self.branding_theme.get_active_id() or "system"
        accent = self.branding_accent.get_active_id() or "ayusos"
        wallpaper_mode = self.branding_wallpaper_mode.get_active_id() or "auto"

        def aplicar():
            try:
                from .aio_core import ayusos_branding
                import json
                # Aplicar tema
                json.loads(ayusos_branding.cli_set_theme(theme))
                # Aplicar acento
                json.loads(ayusos_branding.cli_set_accent(accent))
                # Aplicar todo (incluye Plymouth)
                result = json.loads(ayusos_branding.cli_apply_all())
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._branding_apply_done, False, str(exc))
            else:
                GLib.idle_add(self._branding_apply_done, True, result)

        threading.Thread(target=aplicar, daemon=True).start()

    def _branding_apply_done(self, ok, data):
        self.branding_apply_btn.set_sensitive(True)
        if not ok:
            self.branding_status.set_text(traducir("Error: %s") % data)
        else:
            success = data.get("success", False)
            self.branding_status.set_text(traducir("Branding aplicado correctamente.") if success else traducir("Error aplicando branding."))
            self._branding_refresh(None)
        return GLib.SOURCE_REMOVE

    def _branding_apply_plymouth(self, _boton):
        theme = self.branding_plymouth.get_active_id() or "ayusos"
        self.branding_plymouth_btn.set_sensitive(False)
        self.branding_status.set_text(traducir("Aplicando tema Plymouth…"))

        def aplicar():
            try:
                from .aio_core import ayusos_branding
                import json
                result = json.loads(ayusos_branding.cli_set_plymouth(theme))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                GLib.idle_add(self._branding_plymouth_done, False, str(exc))
            else:
                GLib.idle_add(self._branding_plymouth_done, True, result)

        threading.Thread(target=aplicar, daemon=True).start()

    def _branding_plymouth_done(self, ok, data):
        self.branding_plymouth_btn.set_sensitive(True)
        if not ok:
            self.branding_status.set_text(traducir("Error: %s") % data)
        else:
            success = data.get("success", False)
            self.branding_status.set_text(traducir("Plymouth actualizado.") if success else traducir("Error: %s") % data)
        return GLib.SOURCE_REMOVE

    def _crear_tarjeta_wallpaper(self, wp):
        tarjeta, contenido = tarjeta_mantenimiento(8)
        tarjeta.set_size_request(330, -1)

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(wp["path"], 200, 120, True)
            imagen = Gtk.Image.new_from_pixbuf(pixbuf)
        except GLib.Error:
            imagen = Gtk.Image.new_from_icon_name("image-x-generic", Gtk.IconSize.DIALOG)
        contenido.pack_start(imagen, False, False, 0)

        titulo = etiqueta(wp["name"])
        titulo.get_style_context().add_class("aio-heading")
        contenido.pack_start(titulo, False, False, 0)

        btn = Gtk.Button(label=traducir("Usar este fondo"))
        btn.connect("clicked", self._branding_set_wallpaper, wp["path"])
        contenido.pack_start(btn, False, False, 0)

        return tarjeta

    def _pagina_ayusos_identity(self):
        """Pestaña: Backup y restauración de la identidad de AyusOS."""
        pagina = self._pagina_tarjetas()
        contenido = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Tarjeta: Estado
        tarjeta, caja = tarjeta_mantenimiento(10)
        caja.pack_start(cabecera_mantenimiento("Identidad de AyusOS", "preferences-desktop-symbolic"), False, False, 0)

        self.identity_status = self._etiqueta_estado()
        caja.pack_start(self.identity_status, False, False, 0)

        grid = Gtk.Grid(column_spacing=14, row_spacing=8)
        grid.set_border_width(4)
        caja.pack_start(grid, False, False, 0)

        self.identity_sources_label = etiqueta("Fuentes APT: —")
        self.identity_keyring_label = etiqueta("Llavero GPG: —")
        grid.attach(self.identity_sources_label, 0, 0, 1, 1)
        grid.attach(self.identity_keyring_label, 1, 0, 1, 1)

        btn_row = Gtk.Box(spacing=8)
        self.identity_refresh_btn = Gtk.Button(label=traducir("Actualizar estado"))
        self.identity_refresh_btn.connect("clicked", self._identity_refresh)
        btn_row.pack_start(self.identity_refresh_btn, False, False, 0)
        grid.attach(btn_row, 0, 1, 2, 1)

        caja.pack_start(grid, False, False, 0)
        contenido.pack_start(tarjeta, False, False, 0)

        # Tarjeta: Backup
        tarjeta2, caja2 = tarjeta_mantenimiento(10)
        caja2.pack_start(cabecera_mantenimiento("Backup de identidad", "document-save-symbolic"), False, False, 0)

        backup_box = Gtk.Box(spacing=8)
        backup_box.pack_start(etiqueta("Archivo:"), False, False, 0)
        self.identity_backup_entry = Gtk.Entry(placeholder_text=traducir("~/ayusos-identity.zip"))
        backup_box.pack_start(self.identity_backup_entry, True, True, 0)
        caja2.pack_start(backup_box, False, False, 0)

        self.identity_backup_btn = Gtk.Button(label=traducir("Crear backup"))
        self.identity_backup_btn.get_style_context().add_class("suggested-action")
        self.identity_backup_btn.connect("clicked", self._identity_backup)
        caja2.pack_start(self.identity_backup_btn, False, False, 0)

        contenido.pack_start(tarjeta2, False, False, 0)

        # Tarjeta: Restaurar
        tarjeta3, caja3 = tarjeta_mantenimiento(10)
        caja3.pack_start(cabecera_mantenimiento("Restaurar identidad", "document-revert-symbolic"), False, False, 0)

        restore_box = Gtk.Box(spacing=8)
        restore_box.pack_start(etiqueta("Archivo:"), False, False, 0)
        self.identity_restore_entry = Gtk.Entry(placeholder_text=traducir("~/ayusos-identity.zip"))
        restore_box.pack_start(self.identity_restore_entry, True, True, 0)
        caja3.pack_start(restore_box, False, False, 0)

        restore_btns = Gtk.Box(spacing=8)
        self.identity_dryrun_check = Gtk.CheckButton(label=traducir("Solo simular (dry-run)"))
        restore_btns.pack_start(self.identity_dryrun_check, False, False, 0)

        self.identity_restore_btn = Gtk.Button(label=traducir("Restaurar ahora"))
        self.identity_restore_btn.get_style_context().add_class("suggested-action")
        self.identity_restore_btn.connect("clicked", self._identity_restore)
        restore_btns.pack_end(self.identity_restore_btn, False, False, 0)
        caja3.pack_start(restore_btns, False, False, 0)

        contenido.pack_start(tarjeta3, False, False, 0)

        # Tarjeta: Qué incluye
        tarjeta4, caja4 = tarjeta_mantenimiento(10)
        caja4.pack_start(cabecera_mantenimiento("Contenido del backup", "help-browser-symbolic"), False, False, 0)
        caja4.pack_start(etiqueta(
            "El backup de identidad incluye:\n"
            "• Fuentes APT de AyusOS (/etc/apt/sources.list.d/ayusos.sources)\n"
            "• Llavero GPG del repositorio (/usr/share/keyrings/ayusos-archive.gpg)\n"
            "• Archivo de versión (/etc/ayusos-release)\n"
            "• Configuración de Timeshift\n"
            "• Extensiones GNOME habilitadas y su configuración\n"
            "• Branding (tema GTK, color de acento, fondos de pantalla)"
        ), False, False, 0)
        contenido.pack_start(tarjeta4, False, False, 0)

        pagina.pack_start(self._scroll_tarjetas(contenido), True, True, 0)
        return pagina

    def _identity_refresh(self, _boton):
        self.identity_refresh_btn.set_sensitive(False)
        self.identity_status.set_text(traducir("Cargando estado…"))

        def cargar():
            try:
                import subprocess, json
                result = subprocess.run(
                    ["/usr/local/libexec/ayusos-aio-autorizar", "status"],
                    capture_output=True, text=True, timeout=10
                )
                # Verificar existencia de archivos
                import os
                sources = os.path.exists("/etc/apt/sources.list.d/ayusos.sources")
                keyring = os.path.exists("/usr/share/keyrings/ayusos-archive.gpg")
                release = os.path.exists("/etc/ayusos-release")
                timeshift = os.path.exists("/etc/timeshift.json") or os.path.exists("/etc/timeshift/default.json")
                GLib.idle_add(self._identity_refresh_done, True, {
                    "sources": sources, "keyring": keyring, "release": release, "timeshift": timeshift
                })
            except (OSError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._identity_refresh_done, False, str(exc))

        threading.Thread(target=cargar, daemon=True).start()

    def _identity_refresh_done(self, ok, data):
        self.identity_refresh_btn.set_sensitive(True)
        if not ok:
            self.identity_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        self.identity_sources_label.set_text(traducir("Fuentes APT: %s") % (traducir("Sí") if data["sources"] else traducir("No")))
        self.identity_keyring_label.set_text(traducir("Llavero GPG: %s") % (traducir("Sí") if data["keyring"] else traducir("No")))

        items = []
        if data["release"]:
            items.append(traducir("versión"))
        if data["timeshift"]:
            items.append(traducir("Timeshift"))
        if items:
            self.identity_status.set_text(traducir("Identidad detectada: %s") % ", ".join(items))
        else:
            self.identity_status.set_text(traducir("Identidad de AyusOS no detectada."))
        return GLib.SOURCE_REMOVE

    def _identity_backup(self, _boton):
        path = self.identity_backup_entry.get_text().strip()
        if not path:
            path = "~/ayusos-identity.zip"
        path = os.path.expanduser(path)

        self.identity_backup_btn.set_sensitive(False)
        self.identity_status.set_text(traducir("Creando backup…"))

        def backup():
            try:
                import subprocess, json
                result = subprocess.run(
                    ["/usr/local/libexec/ayusos-aio-autorizar", "status"],
                    capture_output=True, text=True, timeout=30
                )
                # Usar el módulo directamente
                from .aio_core import ayusos_identity
                result = json.loads(ayusos_identity.cli_backup(path))
                GLib.idle_add(self._identity_backup_done, True, result)
            except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._identity_backup_done, False, str(exc))

        threading.Thread(target=backup, daemon=True).start()

    def _identity_backup_done(self, ok, data):
        self.identity_backup_btn.set_sensitive(True)
        if not ok:
            self.identity_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        if data.get("success"):
            self.identity_status.set_text(traducir("Backup guardado en %s") % data.get("path", ""))
        else:
            self.identity_status.set_text(traducir("Error creando backup."))
        return GLib.SOURCE_REMOVE

    def _identity_restore(self, _boton):
        path = self.identity_restore_entry.get_text().strip()
        if not path:
            self.identity_status.set_text(traducir("Falta archivo de backup."))
            return
        path = os.path.expanduser(path)
        dry_run = self.identity_dryrun_check.get_active()

        self.identity_restore_btn.set_sensitive(False)
        self.identity_status.set_text(traducir("Restaurando identidad%s…") % (" (simulación)" if dry_run else ""))

        def restore():
            try:
                import subprocess, json
                from .aio_core import ayusos_identity
                result = json.loads(ayusos_identity.cli_restore(path, dry_run))
                GLib.idle_add(self._identity_restore_done, True, result)
            except (OSError, ValueError, RuntimeError, ImportError, subprocess.SubprocessError) as exc:
                GLib.idle_add(self._identity_restore_done, False, str(exc))

        threading.Thread(target=restore, daemon=True).start()

    def _identity_restore_done(self, ok, data):
        self.identity_restore_btn.set_sensitive(True)
        if not ok:
            self.identity_status.set_text(traducir("Error: %s") % data)
            return GLib.SOURCE_REMOVE

        if data.get("success"):
            self.identity_status.set_text(traducir("Identidad restaurada correctamente."))
            self._identity_refresh(None)
        else:
            self.identity_status.set_text(traducir("Error: %s") % data.get("message", ""))
        return GLib.SOURCE_REMOVE
