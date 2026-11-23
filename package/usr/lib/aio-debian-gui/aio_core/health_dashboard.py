"""Panel de salud del sistema (Health Dashboard) para AiO Debian GUI."""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from .diagnostics import run_diagnostics


# Mapeo de estado a color e icono
ESTADO_COLOR = {
    'ok': '#269343',        # verde
    'warning': '#E67E22',   # naranja
    'critical': '#C0392B',  # rojo
    'unknown': '#7F8C8D',   # gris
}

NOMBRE_ESTADO = {
    'ok': 'Correcto',
    'warning': 'Aviso',
    'critical': 'Crítico',
    'unknown': 'No comprobado',
}


class HealthDashboard(Gtk.Box):
    """Dashboard visual de salud del sistema."""

    def __init__(self, window, translate, passwordless):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=12)
        self.window = window
        self.translate = translate
        self.passwordless = passwordless
        self.cards = {}  # name -> (frame, status_label, status_circle, detail_label, advice_label)
        self.loading = False

        # Título
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_bottom=6)
        title = Gtk.Label(label=self.translate("Salud del sistema"))
        title.get_style_context().add_class("aio-task-name")
        title.set_xalign(0)
        title_box.pack_start(title, True, True, 0)

        # Botón de diagnóstico completo
        self.btn_full_diagnostic = Gtk.Button(label=self.translate("Ejecutar diagnóstico completo"))
        self.btn_full_diagnostic.set_image(Gtk.Image.new_from_icon_name(
            "system-search-symbolic", Gtk.IconSize.BUTTON))
        self.btn_full_diagnostic.set_always_show_image(True)
        self.btn_full_diagnostic.connect("clicked", self._on_full_diagnostic)
        title_box.pack_end(self.btn_full_diagnostic, False, False, 0)

        self.pack_start(title_box, False, False, 0)

        # Scrolled container para las tarjetas
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

        # Estado inicial
        self._build_initial_cards()

    def _build_initial_cards(self):
        """Crea las tarjetas vacías con los nombres de las comprobaciones."""
        checks = [
            ("Espacio en /", "drive-harddisk-symbolic"),
            ("Actualizaciones pendientes", "system-software-update-symbolic"),
            ("Estado de dpkg", "package-x-generic-symbolic"),
            ("Dependencias APT", "package-x-generic-symbolic"),
            ("Índices de APT", "view-refresh-symbolic"),
            ("Módulos DKMS", "preferences-system-symbolic"),
            ("Reinicio pendiente", "system-reboot-symbolic"),
            ("Servicios systemd", "applications-system-symbolic"),
        ]

        for name, icon_name in checks:
            frame, status_label, status_circle, detail_label, advice_label = self._create_card(name, icon_name)
            self.cards[name] = (frame, status_label, status_circle, detail_label, advice_label)
            self.grid.add(frame)

    def _create_card(self, name, icon_name):
        """Crea una tarjeta individual para una comprobación."""
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.NONE)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin=12)
        box.set_halign(Gtk.Align.FILL)
        box.set_hexpand(True)

        # Icono + nombre
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        icon.set_pixel_size(32)
        header.pack_start(icon, False, False, 0)

        name_label = Gtk.Label(label=self.translate(name))
        name_label.get_style_context().add_class("aio-task-name")
        name_label.set_xalign(0)
        name_label.set_ellipsize(3)
        header.pack_start(name_label, True, True, 0)

        box.pack_start(header, False, False, 0)

        # Separador
        sep = Gtk.Separator()
        box.pack_start(sep, False, False, 0)

        # Estado (círculo coloreado + texto)
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_circle = Gtk.DrawingArea()
        status_circle.set_size_request(16, 16)
        status_circle.connect("draw", self._draw_status_circle, "unknown")
        status_box.pack_start(status_circle, False, False, 0)

        status_label = Gtk.Label(label=self.translate(NOMBRE_ESTADO["unknown"]))
        status_label.set_xalign(0)
        status_box.pack_start(status_label, True, True, 0)

        box.pack_start(status_box, False, False, 0)

        # Detalle
        detail_label = Gtk.Label(label=self.translate("Cargando…"))
        detail_label.set_xalign(0)
        detail_label.set_ellipsize(3)
        detail_label.set_line_wrap(True)
        detail_label.set_max_width_chars(40)
        box.pack_start(detail_label, False, False, 0)

        # Consejo (inicialmente oculto)
        advice_label = Gtk.Label(label="")
        advice_label.set_xalign(0)
        advice_label.set_ellipsize(3)
        advice_label.set_line_wrap(True)
        advice_label.set_max_width_chars(40)
        advice_label.get_style_context().add_class("dim-label")
        advice_label.set_no_show_all(True)
        box.pack_start(advice_label, False, False, 0)

        frame.add(box)
        frame.show_all()

        return frame, status_label, status_circle, detail_label, advice_label

    def _draw_status_circle(self, area, cr, status):
        """Dibuja un círculo coloreado según el estado."""
        color_hex = ESTADO_COLOR.get(status, ESTADO_COLOR["unknown"])
        r = int(color_hex[1:3], 16) / 255.0
        g = int(color_hex[3:5], 16) / 255.0
        b = int(color_hex[5:7], 16) / 255.0
        cr.set_source_rgba(r, g, b, 1.0)
        cr.arc(8, 8, 7, 0, 2 * 3.14159)
        cr.fill()

    def refresh(self):
        """Actualiza el dashboard con los datos más recientes."""
        if self.loading:
            return
        self.loading = True
        self.btn_full_diagnostic.set_sensitive(False)

        def worker():
            try:
                findings = run_diagnostics()
                GLib.idle_add(self._update_cards, findings)
            except Exception as exc:
                GLib.idle_add(self._on_error, str(exc))

        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _on_error(self, error):
        self.loading = False
        self.btn_full_diagnostic.set_sensitive(True)
        for name, card in self.cards.items():
            _, status_label, status_circle, detail_label, advice_label = card
            status_circle.queue_draw()
            detail_label.set_text(self.translate("Error: ") + error)

    def _update_cards(self, findings):
        """Actualiza las tarjetas con los resultados del diagnóstico."""
        self.loading = False
        self.btn_full_diagnostic.set_sensitive(True)

        # Mapear hallazgos por nombre
        findings_map = {f["name"]: f for f in findings}

        for name, card in self.cards.items():
            frame, status_label, status_circle, detail_label, advice_label = card
            finding = findings_map.get(name)

            if finding:
                status = finding.get("status", "unknown")
                detail = finding.get("detail", "")
                advice = finding.get("advice", "")

                # Actualizar estado
                status_label.set_text(self.translate(NOMBRE_ESTADO.get(status, "Desconocido")))
                status_label.get_style_context().remove_class("status-ok")
                status_label.get_style_context().remove_class("status-warning")
                status_label.get_style_context().remove_class("status-critical")
                status_label.get_style_context().remove_class("status-unknown")
                status_label.get_style_context().add_class(f"status-{status}")
                status_circle.queue_draw()

                # Actualizar detalle
                detail_label.set_text(detail or "—")

                # Actualizar consejo
                if advice:
                    advice_label.set_text(advice)
                    advice_label.show()
                else:
                    advice_label.hide()
            else:
                # Sin datos para esta comprobación
                status_label.set_text(self.translate("No comprobado"))
                status_circle.queue_draw()
                detail_label.set_text("—")
                advice_label.hide()

        return False

    def _on_full_diagnostic(self, _button):
        """Abre el diálogo de diagnóstico completo existente."""
        if hasattr(self.window, '_abrir_diagnostico'):
            self.window._abrir_diagnostico()

    def on_page_show(self):
        """Se llama cuando la pestaña se hace visible."""
        self.refresh()

    def on_page_hide(self):
        """Se llama cuando la pestaña se oculta."""
        pass


def create_health_dashboard(window, translate, passwordless):
    """Factory function para crear el dashboard."""
    return HealthDashboard(window, translate, passwordless)