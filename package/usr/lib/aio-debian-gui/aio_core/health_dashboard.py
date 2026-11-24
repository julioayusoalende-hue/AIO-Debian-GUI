"""Panel de salud del sistema (Health Dashboard) para AiO Debian GUI.

El diagnóstico se ejecuta dentro de la propia pestaña: una barra de progreso
muestra el avance, cada apartado pinta su semáforo (verde/naranja/rojo) y,
cuando algo requiere atención, la misma tarjeta ofrece el botón que lo
soluciona sin salir de la pestaña.
"""

import threading

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from . import diagnostics as core_diagnostics

APP_ID_FLATPAK = "io.github.julioayusoalende_hue.aio_debian_gui"


# Mapeo de estado a color, texto e icono.
ESTADO_COLOR = {
    'ok': '#269343',        # verde
    'warning': '#E67E22',   # naranja
    'critical': '#C0392B',  # rojo
    'unknown': '#7F8C8D',   # gris
}

NOMBRE_ESTADO = {
    'ok': 'Correcto',
    'warning': 'Revisar',
    'critical': 'No superado',
    'unknown': 'Sin comprobar',
}

ESTADO_ICONO = {
    'ok': 'emblem-ok-symbolic',
    'warning': 'dialog-warning-symbolic',
    'critical': 'dialog-error-symbolic',
    'unknown': 'dialog-question-symbolic',
}

# Apartados que se muestran siempre, en este orden.
TARJETAS = [
    ("Espacio en /", "drive-harddisk-symbolic"),
    ("Estado de dpkg", "package-x-generic-symbolic"),
    ("Dependencias APT", "package-x-generic-symbolic"),
    ("Índices de APT", "view-refresh-symbolic"),
    ("Actualizaciones pendientes", "system-software-update-symbolic"),
    ("Reinicio pendiente", "system-reboot-symbolic"),
    ("Módulos DKMS", "preferences-system-symbolic"),
    ("Servicios systemd", "applications-system-symbolic"),
    ("Versión de AiO Debian GUI", "application-x-executable-symbolic"),
]


class HealthDashboard(Gtk.Box):
    """Dashboard visual de salud del sistema, con diagnóstico integrado."""

    def __init__(self, window, translate, passwordless):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=12)
        self.window = window
        self.translate = translate
        self.passwordless = passwordless
        self.cards = {}  # name -> dict de widgets
        self.loading = False
        self.resultados = []
        self.formato = self._formato_actualizacion()

        # Cabecera: título y botón de ejecución.
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label=self.translate("Salud del sistema"))
        title.get_style_context().add_class("aio-heading")
        title.set_xalign(0)
        title_box.pack_start(title, True, True, 0)

        self.btn_full_diagnostic = Gtk.Button(label=self.translate("Ejecutar diagnóstico completo"))
        self.btn_full_diagnostic.set_image(Gtk.Image.new_from_icon_name(
            "system-search-symbolic", Gtk.IconSize.BUTTON))
        self.btn_full_diagnostic.set_always_show_image(True)
        self.btn_full_diagnostic.connect("clicked", self._on_run_diagnostics)
        title_box.pack_end(self.btn_full_diagnostic, False, False, 0)
        self.pack_start(title_box, False, False, 0)

        # Rejilla de tarjetas con desplazamiento.
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)

        self.grid = Gtk.FlowBox(
            orientation=Gtk.Orientation.HORIZONTAL,
            column_spacing=12,
            row_spacing=12,
            selection_mode=Gtk.SelectionMode.NONE,
            max_children_per_line=3,
        )
        self.grid.set_valign(Gtk.Align.START)
        scroller.add(self.grid)
        self.pack_start(scroller, True, True, 0)

        # Barra de progreso y resumen, abajo y sin abrir otra ventana.
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text(self.translate("Listo para diagnosticar"))
        self.pack_start(self.progress, False, False, 0)

        self.status_label = Gtk.Label(xalign=0)
        self.status_label.set_line_wrap(True)
        self.status_label.get_style_context().add_class("dim-label")
        self.status_label.set_text(self.translate(
            "Pulsa «Ejecutar diagnóstico completo» para revisar el sistema."))
        self.pack_start(self.status_label, False, False, 0)

        self._build_initial_cards()
        self.show_all()

    # ------------------------------------------------------------------
    # Construcción de tarjetas
    # ------------------------------------------------------------------
    def _build_initial_cards(self):
        """Crea las tarjetas vacías con los nombres de las comprobaciones."""
        for name, icon_name in TARJETAS:
            self.cards[name] = self._create_card(name, icon_name)
            self.grid.add(self.cards[name]["frame"])

    def _create_card(self, name, icon_name):
        """Crea una tarjeta individual para una comprobación."""
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.NONE)
        frame.set_hexpand(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        box.set_halign(Gtk.Align.FILL)
        box.set_hexpand(True)

        # Icono + nombre.
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        icon.set_pixel_size(28)
        header.pack_start(icon, False, False, 0)

        name_label = Gtk.Label(label=self.translate(name))
        name_label.get_style_context().add_class("aio-task-name")
        name_label.set_xalign(0)
        name_label.set_line_wrap(True)
        header.pack_start(name_label, True, True, 0)

        # Icono de estado en la esquina: verde, naranja, rojo o gris.
        status_icon = Gtk.Image.new_from_icon_name(
            ESTADO_ICONO["unknown"], Gtk.IconSize.BUTTON)
        header.pack_end(status_icon, False, False, 0)

        box.pack_start(header, False, False, 0)
        box.pack_start(Gtk.Separator(), False, False, 0)

        # Estado (círculo coloreado + texto CORRECTO/REVISAR/NO SUPERADO).
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_circle = Gtk.DrawingArea()
        status_circle.set_size_request(16, 16)
        status_circle.connect("draw", self._draw_status_circle, "unknown")
        status_box.pack_start(status_circle, False, False, 0)

        status_label = Gtk.Label(label=self.translate(NOMBRE_ESTADO["unknown"]))
        status_label.set_xalign(0)
        status_label.get_style_context().add_class("aio-task-name")
        status_box.pack_start(status_label, True, True, 0)
        box.pack_start(status_box, False, False, 0)

        # Detalle.
        detail_label = Gtk.Label(label=self.translate("Sin comprobar"))
        detail_label.set_xalign(0)
        detail_label.set_line_wrap(True)
        detail_label.set_max_width_chars(40)
        detail_label.set_selectable(True)
        box.pack_start(detail_label, False, False, 0)

        # Consejo (oculto hasta que haga falta).
        advice_label = Gtk.Label(label="")
        advice_label.set_xalign(0)
        advice_label.set_line_wrap(True)
        advice_label.set_max_width_chars(40)
        advice_label.get_style_context().add_class("dim-label")
        advice_label.set_no_show_all(True)
        box.pack_start(advice_label, False, False, 0)

        # Botones de solución dentro de la propia tarjeta.
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions.set_no_show_all(True)
        box.pack_start(actions, False, False, 0)

        frame.add(box)

        return {
            "frame": frame,
            "box": box,
            "name_label": name_label,
            "status_icon": status_icon,
            "status_circle": status_circle,
            "status_label": status_label,
            "detail_label": detail_label,
            "advice_label": advice_label,
            "actions": actions,
        }

    def _draw_status_circle(self, area, cr, status):
        """Dibuja un círculo coloreado según el estado."""
        color_hex = ESTADO_COLOR.get(status, ESTADO_COLOR["unknown"])
        r = int(color_hex[1:3], 16) / 255.0
        g = int(color_hex[3:5], 16) / 255.0
        b = int(color_hex[5:7], 16) / 255.0
        cr.set_source_rgba(r, g, b, 1.0)
        cr.arc(8, 8, 7, 0, 2 * 3.14159)
        cr.fill()

    # ------------------------------------------------------------------
    # Diagnóstico integrado en la pestaña
    # ------------------------------------------------------------------
    def _formato_actualizacion(self):
        try:
            from .constants import formato_actualizacion
            return formato_actualizacion()
        except Exception:
            return "desconocido"

    def _set_estado_tarjeta(self, name, status, detail="", advice=""):
        """Pinta una tarjeta con su semáforo y sus textos."""
        card = self.cards.get(name)
        if card is None:
            return
        card["status_label"].set_text(self.translate(NOMBRE_ESTADO.get(status, "Sin comprobar")))
        card["status_circle"].queue_draw()
        ctx = card["status_label"].get_style_context()
        for clase in ("status-ok", "status-warning", "status-critical", "status-unknown"):
            ctx.remove_class(clase)
        ctx.add_class(f"status-{status}")
        card["status_icon"].set_from_icon_name(
            ESTADO_ICONO.get(status, ESTADO_ICONO["unknown"]), Gtk.IconSize.BUTTON)
        card["detail_label"].set_text(detail or "—")
        if advice:
            card["advice_label"].set_text(advice)
            card["advice_label"].show()
        else:
            card["advice_label"].hide()

    def _limpiar_acciones(self, card):
        for widget in card["actions"].get_children():
            widget.destroy()
        card["actions"].hide()

    def _anadir_accion(self, card, etiqueta, callback, tooltip=None, comando=None):
        boton = Gtk.Button(label=self.translate(etiqueta))
        if tooltip:
            boton.set_tooltip_text(self.translate(tooltip))
        boton.get_style_context().add_class("suggested-action")
        boton.aio_command = comando
        boton.connect("clicked", callback)
        card["actions"].pack_start(boton, False, False, 0)
        card["actions"].show_all()

    def _pintar_resultado(self, resultado):
        """Pinta un resultado y añade el botón que lo soluciona."""
        name = resultado.get("name", "")
        status = resultado.get("status", "unknown")
        detail = self.translate(resultado.get("detail", ""))
        advice = resultado.get("advice", "")
        advice = self.translate(advice) if advice else ""
        if name not in self.cards:
            return
        self._set_estado_tarjeta(name, status, detail, advice)
        card = self.cards[name]
        self._limpiar_acciones(card)
        if status == "ok":
            return
        accion = resultado.get("action")
        if accion == "update":
            self._anadir_accion(card, "Actualizar AiO", self._on_update_app,
                                "Instalar la versión disponible con el actualizador de AiO")
        elif accion == "integration":
            self._anadir_accion(card, "Guía de integración", self._on_host_guide,
                                "Cómo conectar AiO con el sistema anfitrión")
        elif accion == "refresh-apt":
            self._anadir_accion(card, "Actualizar índices", self._on_refresh_apt,
                                "Refrescar los índices APT con autorización de administrador")
        elif accion == "maintenance":
            self._anadir_accion(card, "Abrir mantenimiento", self._on_open_maintenance,
                                "Ir a Configuración y mantenimiento")
        elif accion == "command":
            texto = resultado.get("command_label") or "Ver solución"
            self._anadir_accion(card, texto, self._on_solution,
                                resultado.get("command_tooltip"),
                                resultado.get("command"))

    def _progreso(self, fraccion, texto=None):
        self.progress.set_fraction(min(max(fraccion, 0.0), 1.0))
        if texto:
            self.progress.set_text(texto)
        return False

    def _on_run_diagnostics(self, _boton=None):
        if self.loading:
            return
        self.loading = True
        self.btn_full_diagnostic.set_sensitive(False)
        self.status_label.set_text(self.translate("Diagnóstico en curso…"))
        self._progreso(0.02, self.translate("Iniciando diagnóstico…"))
        for card in self.cards.values():
            self._limpiar_acciones(card)
            card["detail_label"].set_text(self.translate("Comprobando…"))

        formato = self.formato
        try:
            from .constants import version_app
            version_instalada = version_app(para_apt=True) if formato == "deb" else version_app()
        except Exception:
            version_instalada = "0"

        def worker():
            try:
                GLib.idle_add(self._progreso, 0.10,
                              self.translate("Actualizando índices APT…"))
                error_apt = None
                auditoria = None
                if formato == "deb":
                    try:
                        from .constants import (
                            comando_pkexec, helper_mantenimiento, es_flatpak)
                        if es_flatpak():
                            raise RuntimeError("Sin acceso al anfitrión desde Flatpak")
                        error_apt, auditoria = core_diagnostics.refresh_apt_indices(
                            comando_pkexec(helper_mantenimiento(), "C.UTF-8",
                                           "--refresh-diagnostic-apt"))
                    except Exception as exc:  # sin ayudante o sin autorización
                        error_apt = str(exc)

                GLib.idle_add(self._progreso, 0.45,
                              self.translate("Comprobando el sistema…"))
                resultados = (core_diagnostics.run_host_diagnostics(auditoria)
                              if formato == "flatpak"
                              else core_diagnostics.run_diagnostics(auditoria))

                if error_apt:
                    resultados.insert(0, {
                        "name": "Índices de APT", "status": "unknown",
                        "detail": "No se pudieron actualizar los índices APT; "
                                  "los resultados pueden estar desactualizados.",
                        "advice": error_apt,
                        "action": ("integration" if formato == "flatpak"
                                   else "refresh-apt"),
                    })
                    for resultado in resultados[1:]:
                        if resultado["name"] in ("Actualizaciones pendientes", "Índices de APT"):
                            resultado.update(
                                status="unknown",
                                detail="No se pudieron verificar con índices APT actualizados.",
                                advice="")

                GLib.idle_add(self._progreso, 0.80,
                              self.translate("Comprobando la versión de AiO…"))
                try:
                    # Se consulta el módulo vivo para que las pruebas puedan
                    # sustituirlo y para no cachear una respuesta antigua.
                    import importlib
                    core_updates = importlib.import_module("aio_core.updates")
                    estado_app = core_updates.estado_actualizacion_app(
                        formato, version_instalada, APP_ID_FLATPAK)
                except Exception as exc:
                    estado_app = {"status": "unknown", "detail": str(exc)}
                if error_apt and formato == "deb":
                    estado_app = {"status": "unknown",
                                  "detail": "No se pudieron verificar las actualizaciones "
                                            "con índices APT actualizados."}
                estado = {"available": "warning", "current": "ok"}.get(
                    estado_app["status"], "unknown")
                resultados.append({
                    "name": "Versión de AiO Debian GUI",
                    "status": estado,
                    "detail": estado_app["detail"],
                    "advice": ("Hay una actualización disponible. Puedes instalarla desde aquí."
                               if estado_app["status"] == "available" else ""),
                    "action": "update" if estado_app["status"] == "available" else None,
                })
                self._marcar_acciones(resultados)
                GLib.idle_add(self._on_diagnostics_done, resultados, None)
            except Exception as exc:
                GLib.idle_add(self._on_diagnostics_done, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _marcar_acciones(self, resultados):
        """Decide qué botón resuelve cada apartado que no está correcto."""
        for resultado in resultados:
            if resultado.get("action") or resultado.get("status") == "ok":
                continue
            name = resultado.get("name", "")
            advice = ((resultado.get("advice") or "") + " "
                      + (resultado.get("detail") or "")).lower()
            if name == "Espacio en /":
                resultado.update(action="command",
                                 command=("xdg-open", "trash:///"),
                                 command_label="Abrir la papelera",
                                 command_tooltip="Vacía archivos para liberar espacio")
            elif name == "Estado de dpkg":
                resultado.update(action="command",
                                 command=("pkexec", "dpkg", "--configure", "-a"),
                                 command_label="Completar paquetes",
                                 command_tooltip="Configura los paquetes a medias con dpkg")
            elif name == "Dependencias APT":
                resultado.update(action="command",
                                 command=("pkexec", "apt-get", "-f", "install"),
                                 command_label="Reparar dependencias",
                                 command_tooltip="Deja APT en un estado coherente")
            elif name in ("Actualizaciones pendientes", "Índices de APT"):
                resultado["action"] = "maintenance"
            elif name == "Reinicio pendiente":
                resultado.update(action="command",
                                 command=("gnome-session-quit", "--reboot", "--no-prompt"),
                                 command_label="Reiniciar ahora",
                                 command_tooltip="Guarda tu trabajo antes de reiniciar")
            elif name == "Módulos DKMS":
                resultado.update(action="command",
                                 command=("pkexec", "dkms", "autoinstall"),
                                 command_label="Recompilar módulos",
                                 command_tooltip="Reinstala los módulos DKMS registrados")
            elif name == "Servicios systemd":
                resultado.update(action="command",
                                 command=("systemctl", "--failed", "--no-pager"),
                                 command_label="Ver servicios fallidos",
                                 command_tooltip="Muestra las unidades que han fallado")
            elif "flatpak" in advice or "anfitrión" in advice or "host" in advice:
                resultado["action"] = "integration"
            else:
                resultado["action"] = "maintenance"

    def _on_diagnostics_done(self, results, error):
        self.loading = False
        self.btn_full_diagnostic.set_sensitive(True)

        if error:
            self.progress.set_fraction(0.0)
            self.progress.set_text(self.translate("Diagnóstico interrumpido"))
            self.status_label.set_text(self.translate("Error: ") + error)
            return GLib.SOURCE_REMOVE

        self.resultados = results
        self.status_label.set_text("")
        for resultado in results:
            self._pintar_resultado(resultado)

        recuento = {
            estado: sum(r.get("status") == estado for r in results)
            for estado in ("critical", "warning", "unknown", "ok")
        }
        total = len(results) or 1
        self.progress.set_fraction(recuento["ok"] / total)
        self.progress.set_text("%d/%d %s" % (recuento["ok"], len(results),
                                             self.translate("correctos")))
        estado = "Sin incidencias"
        if recuento["critical"] or recuento["warning"]:
            estado = "Requiere atención"
        elif recuento["unknown"]:
            estado = "No comprobado"
        self.status_label.set_text(
            "%s · %s: %s · %s: %s · %s: %s · %s: %s" % (
                self.translate(estado),
                self.translate("No superados"), recuento["critical"],
                self.translate("A revisar"), recuento["warning"],
                self.translate("Sin comprobar"), recuento["unknown"],
                self.translate("Correctos"), recuento["ok"]))
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------
    # Acciones sin salir de la pestaña
    # ------------------------------------------------------------------
    def _on_update_app(self, _boton):
        if hasattr(self.window, "_buscar_actualizacion"):
            self.window._buscar_actualizacion(None)

    def _on_host_guide(self, _boton):
        if hasattr(self.window, "_abrir_guia_integracion"):
            self.window._abrir_guia_integracion(parent=self.window)

    def _on_open_maintenance(self, _boton):
        notebook = getattr(self.window, "notebook", None)
        if notebook is not None:
            notebook.set_current_page(0)
        ventana = getattr(self.window, "ventana_salud", None)
        if ventana is not None:
            ventana.hide()
            self.window.present()

    def _on_refresh_apt(self, _boton):
        self._on_run_diagnostics()

    def _on_solution(self, boton):
        comando = getattr(boton, "aio_command", None)
        if not comando:
            self._on_open_maintenance(boton)
            return
        self._ejecutar_comando(comando)

    def _ejecutar_comando(self, comando):
        """Ejecuta una solución concreta y repite el diagnóstico al terminar."""
        import subprocess
        from .constants import comando_host

        self.status_label.set_text(self.translate("Ejecutando: ") + " ".join(comando))
        self._progreso(0.5, self.translate("Aplicando la solución…"))

        def worker():
            try:
                subprocess.run(comando_host(*comando), capture_output=True,
                               text=True, timeout=600, check=False)
                error = None
            except Exception as exc:
                error = str(exc)
            GLib.idle_add(self._comando_terminado, error)

        threading.Thread(target=worker, daemon=True).start()

    def _comando_terminado(self, error):
        if error:
            self.status_label.set_text(self.translate("No se pudo ejecutar: ") + error)
        self._on_run_diagnostics()
        return GLib.SOURCE_REMOVE

    # ------------------------------------------------------------------
    def refresh(self):
        """Actualiza el panel con un diagnóstico nuevo, en la misma pestaña."""
        if self.loading:
            return
        self._on_run_diagnostics()

    def on_page_show(self):
        """Se llama cuando la pestaña se hace visible."""
        self.refresh()

    def on_page_hide(self):
        """Se llama cuando la pestaña se oculta."""
        pass


def create_health_dashboard(window, translate, passwordless):
    """Factory function para crear el dashboard."""
    return HealthDashboard(window, translate, passwordless)
