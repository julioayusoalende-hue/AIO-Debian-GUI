"""Asistente de bienvenida (Onboarding) para AyusOS.

Ventana a pantalla completa con flujo guiado paso a paso.
Se ejecuta automáticamente al primer arranque si es_ayusos() y no completado.
"""

import os
from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GdkPixbuf, GLib, GObject, Gtk, Pango

from aio_core.constants import traducir
from ..branding import (
    es_ayusos, logo_cabecera, color_acento_ayusos,
    get_ayusos_version, get_ayusos_codename,
    titulo_aplicacion, icono_aplicacion,
)
from .ayusos_config import (
    get_effective_config, load_user_preferences, save_user_preferences,
    mark_onboarding_done, get_profile_packages,
    get_recommended_apps_for_profile, APP_PROFILES,
    VALID_KERNEL_VARIANTS, VALID_NVIDIA_MODES, VALID_MAINTENANCE_SCHEDULES,
    VALID_APP_PROFILES, VALID_THEMES, VALID_ACCENTS,
)
from aio_core.operations import coordinator as operation_coordinator


# Estilo CSS para el onboarding
ONBOARDING_CSS = b"""
.onboarding-window {
    background-color: @theme_bg_color;
}
.onboarding-header {
    background: linear-gradient(to right, shade(@theme_bg_color, 0.9), @theme_bg_color);
    border-bottom: 1px solid alpha(@theme_fg_color, 0.12);
    padding: 24px 32px;
}
.onboarding-title {
    font-size: 1.8em;
    font-weight: 700;
    color: @theme_fg_color;
}
.onboarding-subtitle {
    font-size: 1.05em;
    color: alpha(@theme_fg_color, 0.7);
    margin-top: 4px;
}
.onboarding-progress {
    margin-top: 16px;
}
.onboarding-step-label {
    font-size: 0.9em;
    font-weight: 600;
    color: alpha(@theme_fg_color, 0.6);
}
.onboarding-content {
    padding: 32px 48px;
}
.onboarding-card {
    background-color: @theme_base_color;
    border: 1px solid alpha(@theme_fg_color, 0.1);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
}
.onboarding-card-title {
    font-size: 1.2em;
    font-weight: 700;
    margin-bottom: 8px;
}
.onboarding-card-desc {
    font-size: 0.95em;
    color: alpha(@theme_fg_color, 0.8);
}
.onboarding-button {
    font-weight: 600;
    padding: 12px 24px;
    border-radius: 8px;
    min-width: 140px;
}
.onboarding-button-primary {
    background-image: none;
    background-color: #279457;
    color: #ffffff;
    border-color: #279457;
}
.onboarding-button-secondary {
    background-color: alpha(@theme_fg_color, 0.08);
    color: @theme_fg_color;
}
.onboarding-button-accent {
    background-image: none;
    background-color: """ + color_acento_ayusos().encode() + b""";
    color: white;
}
.onboarding-footer {
    padding: 16px 32px;
    border-top: 1px solid alpha(@theme_fg_color, 0.1);
}
.onboarding-skip {
    color: alpha(@theme_fg_color, 0.5);
    font-size: 0.9em;
}
"""


class OnboardingStep:
    """Representa un paso del onboarding."""
    def __init__(self, step_id: str, title: str, description: str,
                 widget_factory, validate_fn=None, apply_fn=None):
        self.id = step_id
        self.title = title
        self.description = description
        self.widget_factory = widget_factory  # fn() -> Gtk.Widget
        self.validate_fn = validate_fn  # fn(widget) -> bool
        self.apply_fn = apply_fn  # fn(widget, config) -> bool
        self.widget = None
        self.completed = False


class OnboardingWizard(Gtk.Window):
    """Ventana principal del asistente de bienvenida."""

    __gsignals__ = {
        "completed": (GObject.SIGNAL_RUN_FIRST, None, ()),
        "cancelled": (GObject.SIGNAL_RUN_FIRST, None, ()),
    }

    def __init__(self, parent=None):
        super().__init__(title=titulo_aplicacion())
        self.set_icon_name(icono_aplicacion())
        self.set_default_size(900, 650)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_decorated(False)  # Pantalla completa sin decoraciones
        self.set_resizable(False)

        # CSS
        self._setup_css()

        # Estado
        self.steps: List[OnboardingStep] = []
        self.current_index = 0
        self.config = get_effective_config()
        self.version = get_ayusos_version() or "1.0"
        self.parent_window = parent

        # UI
        self._build_ui()
        self._define_steps()

        # Mostrar primer paso
        self._show_step(0)

        self.connect("destroy", self._on_destroy)

    def _setup_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(ONBOARDING_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        self.get_style_context().add_class("onboarding-window")

    def _build_ui(self):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(main_box)

        # Header
        self.header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.header.get_style_context().add_class("onboarding-header")
        main_box.pack_start(self.header, False, False, 0)

        # Logo + título
        header_top = Gtk.Box(spacing=16)
        logo = logo_cabecera(64)
        if logo:
            header_top.pack_start(logo, False, False, 0)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.title_label = Gtk.Label()
        self.title_label.get_style_context().add_class("onboarding-title")
        self.title_label.set_xalign(0)
        title_box.pack_start(self.title_label, False, False, 0)

        self.subtitle_label = Gtk.Label()
        self.subtitle_label.get_style_context().add_class("onboarding-subtitle")
        self.subtitle_label.set_xalign(0)
        title_box.pack_start(self.subtitle_label, False, False, 0)

        header_top.pack_start(title_box, True, True, 0)
        self.header.pack_start(header_top, False, False, 0)

        # Progress bar + step indicator
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.progress_bar = Gtk.LevelBar()
        self.progress_bar.set_mode(Gtk.LevelBarMode.CONTINUOUS)
        self.progress_bar.set_min_value(0)
        self.progress_bar.set_max_value(1)
        self.progress_bar.get_style_context().add_class("onboarding-progress")
        progress_box.pack_start(self.progress_bar, False, False, 0)

        self.step_label = Gtk.Label()
        self.step_label.get_style_context().add_class("onboarding-step-label")
        self.step_label.set_xalign(0)
        progress_box.pack_start(self.step_label, False, False, 0)

        self.header.pack_start(progress_box, False, False, 0)

        # Content area (scrollable)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.get_style_context().add_class("onboarding-content")
        main_box.pack_start(scrolled, True, True, 0)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_border_width(32)
        scrolled.add(self.content_box)

        # Footer con botones
        self.footer = Gtk.Box(spacing=12)
        self.footer.get_style_context().add_class("onboarding-footer")
        self.footer.set_border_width(16)
        main_box.pack_start(self.footer, False, False, 0)

        # Botón saltar (izquierda)
        self.btn_skip = Gtk.Button(label=traducir("Saltar configuración"))
        self.btn_skip.get_style_context().add_class("onboarding-skip")
        self.btn_skip.connect("clicked", self._on_skip)
        self.footer.pack_start(self.btn_skip, False, False, 0)

        # Espaciador
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        self.footer.pack_start(spacer, True, True, 0)

        # Botón anterior
        self.btn_back = Gtk.Button(label=traducir("Anterior"))
        self.btn_back.get_style_context().add_class("onboarding-button")
        self.btn_back.get_style_context().add_class("onboarding-button-secondary")
        self.btn_back.connect("clicked", self._on_back)
        self.footer.pack_start(self.btn_back, False, False, 0)

        # Botón siguiente/finalizar
        self.btn_next = Gtk.Button(label=traducir("Siguiente"))
        self.btn_next.get_style_context().add_class("onboarding-button")
        self.btn_next.get_style_context().add_class("onboarding-button-primary")
        self.btn_next.connect("clicked", self._on_next)
        self.footer.pack_start(self.btn_next, False, False, 0)

    def _define_steps(self):
        """Define la secuencia de pasos del onboarding."""
        self.steps = [
            OnboardingStep(
                "welcome",
                traducir("Bienvenido a AyusOS"),
                traducir("Configuraremos tu sistema en unos minutos. "
                         "Puedes personalizar cada opción o aceptar los valores recomendados."),
                self._create_welcome_step,
            ),
            OnboardingStep(
                "repos",
                traducir("Repositorios de software"),
                traducir("Habilita repositorios adicionales para acceder a más aplicaciones, "
                         "controladores y codecs."),
                self._create_repos_step,
                validate_fn=self._validate_repos,
                apply_fn=self._apply_repos,
            ),
            OnboardingStep(
                "flatpak",
                traducir("Flatpak y Flathub"),
                traducir("Instala aplicaciones sandbox desde Flathub, "
                         "la mayor tienda de apps Linux."),
                self._create_flatpak_step,
                validate_fn=self._validate_flatpak,
                apply_fn=self._apply_flatpak,
            ),
            OnboardingStep(
                "kernel",
                traducir("Variante de kernel"),
                traducir("Elige el kernel que mejor se adapte a tu hardware. "
                         "Backports = hardware nuevo, HWE = Ubuntu LTS."),
                self._create_kernel_step,
                validate_fn=self._validate_kernel,
                apply_fn=self._apply_kernel,
            ),
            OnboardingStep(
                "nvidia",
                traducir("Controladores NVIDIA"),
                traducir("Si tienes GPU NVIDIA, configura los controladores propietarios. "
                         "Detección automática recomendada."),
                self._create_nvidia_step,
                validate_fn=self._validate_nvidia,
                apply_fn=self._apply_nvidia,
            ),
            OnboardingStep(
                "apps",
                traducir("Perfil de aplicaciones"),
                traducir("Selecciona un conjunto de aplicaciones preinstaladas según tu uso. "
                         "Se instalarán automáticamente."),
                self._create_apps_step,
                validate_fn=self._validate_apps,
                apply_fn=self._apply_apps,
            ),
            OnboardingStep(
                "gnome_ext",
                traducir("Extensiones de GNOME"),
                traducir("Mejora tu escritorio con extensiones populares: "
                         "dock, indicadores, efectos visuales..."),
                self._create_gnome_ext_step,
                validate_fn=self._validate_gnome_ext,
                apply_fn=self._apply_gnome_ext,
            ),
            OnboardingStep(
                "maintenance",
                traducir("Mantenimiento automático"),
                traducir("Programa actualizaciones y limpieza automáticas "
                         "para mantener tu sistema sano sin esfuerzo."),
                self._create_maintenance_step,
                validate_fn=self._validate_maintenance,
                apply_fn=self._apply_maintenance,
            ),
            OnboardingStep(
                "appearance",
                traducir("Apariencia"),
                traducir("Personaliza el tema, color de acento y fondos de pantalla."),
                self._create_appearance_step,
                validate_fn=self._validate_appearance,
                apply_fn=self._apply_appearance,
            ),
            OnboardingStep(
                "finish",
                traducir("¡Todo listo!"),
                traducir("Tu sistema está configurado. "
                         "Las aplicaciones seleccionadas se instalarán en segundo plano."),
                self._create_finish_step,
                apply_fn=self._apply_finish,
            ),
        ]

    # --- Fábricas de widgets por paso ---

    def _create_welcome_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.get_style_context().add_class("onboarding-card")

        # Versión
        version_box = Gtk.Box(spacing=8)
        lbl_version = Gtk.Label(label=f"{traducir('Versión')}: {self.version}")
        lbl_version.get_style_context().add_class("onboarding-card-title")
        version_box.pack_start(lbl_version, False, False, 0)

        codename = get_ayusos_codename()
        lbl_codename = Gtk.Label(label=f"{traducir('Base')}: Debian {codename.capitalize()}")
        lbl_codename.get_style_context().add_class("onboarding-card-desc")
        version_box.pack_start(lbl_codename, False, False, 0)

        box.pack_start(version_box, False, False, 0)

        # Descripción
        desc = Gtk.Label()
        desc.set_markup(traducir(
            "<b>AyusOS Linux</b> es una distribución basada en Debian "
            "diseñada para ser completa, bonita y fácil de usar desde el primer momento.\n\n"
            "Este asistente configurará:\n"
            "• Repositorios y fuentes de software\n"
            "• Flatpak + Flathub para apps modernas\n"
            "• Kernel optimizado para tu hardware\n"
            "• Controladores gráficos (NVIDIA si aplica)\n"
            "• Aplicaciones según tu perfil de uso\n"
            "• Extensiones de GNOME para productividad\n"
            "• Mantenimiento automático programado\n"
            "• Tema y personalización visual"
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        desc.set_justify(Gtk.Justification.LEFT)
        box.pack_start(desc, False, False, 0)

        return box

    def _create_repos_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Repositorios de software"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Debian separa el software en secciones. Habilitar 'contrib' y 'non-free' "
            "permite instalar controladores propietarios, firmware, codecs y apps como Steam."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 0)

        # Checkboxes
        self.repo_contrib = Gtk.CheckButton(label=traducir("contrib / non-free (recomendado)"))
        self.repo_contrib.set_active(self.config.repos.contrib_nonfree)
        box.pack_start(self.repo_contrib, False, False, 0)

        self.repo_backports = Gtk.CheckButton(label=traducir("Debian Backports (kernel y apps nuevas)"))
        self.repo_backports.set_active(self.config.repos.backports)
        box.pack_start(self.repo_backports, False, False, 0)

        self.repo_backports_mesa = Gtk.CheckButton(label=traducir("Mesa desde Backports (gráficos más nuevos)"))
        self.repo_backports_mesa.set_active(self.config.repos.backports_mesa)
        box.pack_start(self.repo_backports_mesa, False, False, 0)

        return box

    def _create_flatpak_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Flatpak y Flathub"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Flatpak permite instalar aplicaciones en contenedores aislados, "
            "independientes de la versión de Debian. Flathub es la mayor tienda."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 0)

        self.flatpak_enabled = Gtk.CheckButton(label=traducir("Habilitar Flatpak"))
        self.flatpak_enabled.set_active(self.config.flatpak.enabled)
        box.pack_start(self.flatpak_enabled, False, False, 0)

        self.flathub_enabled = Gtk.CheckButton(label=traducir("Añadir repositorio Flathub"))
        self.flathub_enabled.set_active(self.config.flatpak.flathub)
        box.pack_start(self.flathub_enabled, False, False, 0)

        return box

    def _create_kernel_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Variante de kernel"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "• <b>Stable</b>: Kernel probado, máxima estabilidad (recomendado para servidores).\n"
            "• <b>Backports</b>: Kernel más nuevo desde Debian Backports (mejor hardware reciente).\n"
            "• <b>HWE</b>: Hardware Enablement de Ubuntu (solo si base es Ubuntu LTS)."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        desc.set_use_markup(True)
        box.pack_start(desc, False, False, 0)

        self.kernel_combo = Gtk.ComboBoxText()
        for variant in ["stable", "backports", "hwe"]:
            label = {"stable": "Stable (recomendado)", "backports": "Backports", "hwe": "HWE (Ubuntu)"}[variant]
            self.kernel_combo.append(variant, traducir(label))
        self.kernel_combo.set_active(["stable", "backports", "hwe"].index(self.config.kernel.variant))
        box.pack_start(self.kernel_combo, False, False, 0)

        return box

    def _create_nvidia_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Controladores NVIDIA"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Si tu equipo tiene GPU NVIDIA, los controladores propietarios ofrecen "
            "mejor rendimiento y compatibilidad (CUDA, juegos, renderizado).\n"
            "La detección automática analiza tu GPU, kernel, Secure Boot y portátiles híbridos."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 0)

        self.nvidia_combo = Gtk.ComboBoxText()
        for mode in ["auto", "manual", "none"]:
            label = {"auto": "Auto-detectar (recomendado)", "manual": "Instalar manualmente", "none": "No instalar"}[mode]
            self.nvidia_combo.append(mode, traducir(label))
        self.nvidia_combo.set_active(["auto", "manual", "none"].index(self.config.nvidia.mode))
        box.pack_start(self.nvidia_combo, False, False, 0)

        self.nvidia_prime = Gtk.CheckButton(label=traducir("PRIME offload (portátiles híbridos Intel/NVIDIA)"))
        self.nvidia_prime.set_active(self.config.nvidia.prime_offload)
        box.pack_start(self.nvidia_prime, False, False, 0)

        return box

    def _create_apps_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Perfil de aplicaciones"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Selecciona un perfil. Las aplicaciones se instalarán automáticamente "
            "desde repositorios APT y Flathub tras completar el asistente."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 0)

        # Radio buttons para perfiles
        self.profile_radios = {}
        profile_group = None
        profiles_info = [
            ("minimal", traducir("Mínimo"), traducir("Solo sistema base + herramientas esenciales")),
            ("development", traducir("Desarrollo"), traducir("VS Code, Git, Docker, terminales, herramientas CLI")),
            ("multimedia", traducir("Multimedia"), traducir("VLC, GIMP, HandBrake, Kdenlive, OBS, Audacity")),
            ("gaming", traducir("Gaming"), traducir("Steam, Heroic, Lutris, RetroArch, MangoHud, GameMode")),
            ("full", traducir("Completo"), traducir("Todo lo anterior + ofimática, Thunderbird, OnlyOffice")),
        ]

        for i, (pid, pname, pdesc) in enumerate(profiles_info):
            radio = Gtk.RadioButton.new_with_label_from_widget(profile_group, "")
            if profile_group is None:
                profile_group = radio
            radio.set_active(pid == self.config.apps.profile)

            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lbl_name = Gtk.Label(label=pname)
            lbl_name.get_style_context().add_class("onboarding-card-title")
            lbl_name.set_xalign(0)
            row.pack_start(lbl_name, False, False, 0)

            lbl_desc = Gtk.Label(label=pdesc)
            lbl_desc.set_xalign(0)
            lbl_desc.get_style_context().add_class("onboarding-card-desc")
            row.pack_start(lbl_desc, False, False, 0)

            hbox = Gtk.Box(spacing=12)
            hbox.pack_start(radio, False, False, 0)
            hbox.pack_start(row, True, True, 0)
            box.pack_start(hbox, False, False, 0)

            self.profile_radios[pid] = radio

        self.auto_install_check = Gtk.CheckButton(label=traducir("Instalar automáticamente al terminar"))
        self.auto_install_check.set_active(self.config.apps.auto_install)
        box.pack_start(self.auto_install_check, False, False, 0)

        return box

    def _create_gnome_ext_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Extensiones de GNOME"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Extensiones recomendadas para mejorar la productividad y experiencia visual."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 0)

        self.ext_checks = {}
        extensions = [
            ("gnome-ext-appindicator", traducir("AppIndicator Support"),
             traducir("Iconos de bandeja para apps como Steam, Discord, VPN...")),
            ("gnome-ext-blur-shell", traducir("Blur my Shell"),
             traducir("Efecto de desenfoque translúcido en paneles y vistas.")),
            ("gnome-ext-dash-to-dock", traducir("Dash to Dock"),
             traducir("Convierte el dash en un dock configurable siempre visible.")),
            ("gnome-ext-caffeine", traducir("Caffeine"),
             traducir("Evita suspensión automática temporalmente.")),
            ("gnome-ext-tiling-shell", traducir("Tiling Shell"),
             traducir("Organiza ventanas en mosaico (estilo i3/sway).")),
        ]

        for ext_id, ext_name, ext_desc in extensions:
            check = Gtk.CheckButton(label=ext_name)
            check.set_active(ext_id in self.config.gnome_extensions.enabled_by_default)
            check.set_tooltip_text(ext_desc)
            box.pack_start(check, False, False, 0)
            self.ext_checks[ext_id] = check

        return box

    def _create_maintenance_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Mantenimiento automático"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Programa tareas de mantenimiento (actualizaciones, limpieza, comprobaciones) "
            "para que se ejecuten automáticamente en segundo plano."
        ))
        desc.set_line_wrap(True)
        desc.set_xalign(0)
        box.pack_start(desc, False, False, 0)

        # Frecuencia
        freq_box = Gtk.Box(spacing=12)
        lbl_freq = Gtk.Label(label=traducir("Frecuencia:"))
        freq_box.pack_start(lbl_freq, False, False, 0)

        self.maint_freq = Gtk.ComboBoxText()
        for sched in ["daily", "weekly", "monthly", "disabled"]:
            label = {"daily": "Diario", "weekly": "Semanal", "monthly": "Mensual", "disabled": "Desactivado"}[sched]
            self.maint_freq.append(sched, traducir(label))
        self.maint_freq.set_active(["daily", "weekly", "monthly", "disabled"].index(self.config.maintenance.schedule))
        freq_box.pack_start(self.maint_freq, False, False, 0)
        box.pack_start(freq_box, False, False, 0)

        # Hora
        time_box = Gtk.Box(spacing=12)
        lbl_time = Gtk.Label(label=traducir("Hora:"))
        time_box.pack_start(lbl_time, False, False, 0)

        self.maint_time = Gtk.Entry()
        self.maint_time.set_text(self.config.maintenance.time)
        self.maint_time.set_width_chars(5)
        time_box.pack_start(self.maint_time, False, False, 0)
        box.pack_start(time_box, False, False, 0)

        # Tareas
        tasks_frame = Gtk.Frame(label=traducir("Tareas incluidas"))
        tasks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tasks_box.set_border_width(8)
        tasks_frame.add(tasks_box)

        self.maint_task_checks = {}
        tasks = [
            ("upgrade", traducir("Actualizar paquetes del sistema")),
            ("autoclean", traducir("Limpiar caché APT")),
            ("flatpak-update", traducir("Actualizar Flatpak")),
            ("snap-update", traducir("Actualizar Snap")),
            ("clean-journal", traducir("Limpiar journal systemd (>30 días)")),
            ("rebootcheck", traducir("Comprobar si requiere reinicio")),
        ]
        for task_id, task_name in tasks:
            check = Gtk.CheckButton(label=task_name)
            check.set_active(task_id in self.config.maintenance.tasks)
            tasks_box.pack_start(check, False, False, 0)
            self.maint_task_checks[task_id] = check

        box.pack_start(tasks_frame, False, False, 0)

        self.maint_notify = Gtk.CheckButton(label=traducir("Notificar antes de ejecutar"))
        self.maint_notify.set_active(self.config.maintenance.notify)
        box.pack_start(self.maint_notify, False, False, 0)

        return box

    def _create_appearance_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.get_style_context().add_class("onboarding-card")

        title = Gtk.Label(label=traducir("Apariencia"))
        title.get_style_context().add_class("onboarding-card-title")
        box.pack_start(title, False, False, 0)

        # Tema
        theme_box = Gtk.Box(spacing=12)
        lbl_theme = Gtk.Label(label=traducir("Tema:"))
        theme_box.pack_start(lbl_theme, False, False, 0)

        self.appearance_theme = Gtk.ComboBoxText()
        for theme in ["system", "light", "dark"]:
            label = {"system": "Sistema", "light": "Claro", "dark": "Oscuro"}[theme]
            self.appearance_theme.append(theme, traducir(label))
        self.appearance_theme.set_active(["system", "light", "dark"].index(self.config.appearance.theme))
        theme_box.pack_start(self.appearance_theme, False, False, 0)
        box.pack_start(theme_box, False, False, 0)

        # Acento
        accent_box = Gtk.Box(spacing=12)
        lbl_accent = Gtk.Label(label=traducir("Color de acento:"))
        accent_box.pack_start(lbl_accent, False, False, 0)

        self.appearance_accent = Gtk.ComboBoxText()
        accents = ["ayusos", "blue", "green", "orange", "purple", "red", "teal"]
        for acc in accents:
            self.appearance_accent.append(acc, acc.capitalize())
        self.appearance_accent.set_active(accents.index(self.config.appearance.accent))
        accent_box.pack_start(self.appearance_accent, False, False, 0)
        box.pack_start(accent_box, False, False, 0)

        # Wallpaper
        wp_box = Gtk.Box(spacing=12)
        lbl_wp = Gtk.Label(label=traducir("Fondo de pantalla:"))
        wp_box.pack_start(lbl_wp, False, False, 0)

        self.appearance_wallpaper = Gtk.ComboBoxText()
        for mode in ["auto", "light", "dark", "custom"]:
            label = {"auto": "Automático (claro/oscuro)", "light": "Solo claro", "dark": "Solo oscuro", "custom": "Personalizado"}[mode]
            self.appearance_wallpaper.append(mode, traducir(label))
        self.appearance_wallpaper.set_active(["auto", "light", "dark", "custom"].index(self.config.appearance.wallpaper_mode))
        wp_box.pack_start(self.appearance_wallpaper, False, False, 0)
        box.pack_start(wp_box, False, False, 0)

        return box

    def _create_finish_step(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.get_style_context().add_class("onboarding-card")

        # Icono éxito
        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic", Gtk.IconSize.DIALOG)
        icon.set_pixel_size(64)
        box.pack_start(icon, False, False, 0)

        title = Gtk.Label()
        title.set_markup(f"<big><b>{traducir('¡Configuración completada!')}</b></big>")
        box.pack_start(title, False, False, 0)

        desc = Gtk.Label(label=traducir(
            "Tu sistema AyusOS está listo.\n\n"
            "• Las aplicaciones seleccionadas se instalarán en segundo plano.\n"
            "• El mantenimiento automático se ejecutará según lo programado.\n"
            "• Puedes abrir el Centro de Control en cualquier momento para ajustar opciones.\n\n"
            "¡Disfruta de tu nuevo sistema!"
        ))
        desc.set_line_wrap(True)
        desc.set_justify(Gtk.Justification.CENTER)
        box.pack_start(desc, False, False, 0)

        # Botón finalizar (en modo --onboarding-only la app cierra al terminar)
        btn_open = Gtk.Button(label=traducir("Finalizar configuración"))
        btn_open.get_style_context().add_class("onboarding-button")
        btn_open.get_style_context().add_class("onboarding-button-accent")
        btn_open.connect("clicked", lambda *_: self.emit("completed"))
        box.pack_start(btn_open, False, False, 0)

        return box

    # --- Validación y aplicación por paso ---

    def _validate_repos(self, widget) -> bool:
        return True  # Siempre válido

    def _apply_repos(self, widget, config) -> bool:
        config.repos.contrib_nonfree = self.repo_contrib.get_active()
        config.repos.backports = self.repo_backports.get_active()
        config.repos.backports_mesa = self.repo_backports_mesa.get_active()
        return True

    def _validate_flatpak(self, widget) -> bool:
        return True

    def _apply_flatpak(self, widget, config) -> bool:
        config.flatpak.enabled = self.flatpak_enabled.get_active()
        config.flatpak.flathub = self.flathub_enabled.get_active()
        return True

    def _validate_kernel(self, widget) -> bool:
        return self.kernel_combo.get_active_id() in VALID_KERNEL_VARIANTS

    def _apply_kernel(self, widget, config) -> bool:
        config.kernel.variant = self.kernel_combo.get_active_id() or "stable"
        return True

    def _validate_nvidia(self, widget) -> bool:
        return self.nvidia_combo.get_active_id() in VALID_NVIDIA_MODES

    def _apply_nvidia(self, widget, config) -> bool:
        config.nvidia.mode = self.nvidia_combo.get_active_id() or "auto"
        config.nvidia.prime_offload = self.nvidia_prime.get_active()
        return True

    def _validate_apps(self, widget) -> bool:
        for pid, radio in self.profile_radios.items():
            if radio.get_active():
                return pid in VALID_APP_PROFILES
        return False

    def _apply_apps(self, widget, config) -> bool:
        for pid, radio in self.profile_radios.items():
            if radio.get_active():
                config.apps.profile = pid
                break
        config.apps.auto_install = self.auto_install_check.get_active()
        return True

    def _validate_gnome_ext(self, widget) -> bool:
        return True

    def _apply_gnome_ext(self, widget, config) -> bool:
        enabled = [ext_id for ext_id, check in self.ext_checks.items() if check.get_active()]
        config.gnome_extensions.enabled_by_default = enabled
        return True

    def _validate_maintenance(self, widget) -> bool:
        sched = self.maint_freq.get_active_id()
        if sched not in VALID_MAINTENANCE_SCHEDULES:
            return False
        # Validar hora HH:MM
        import re
        time_str = self.maint_time.get_text().strip()
        if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time_str):
            return False
        return True

    def _apply_maintenance(self, widget, config) -> bool:
        config.maintenance.schedule = self.maint_freq.get_active_id() or "weekly"
        config.maintenance.time = self.maint_time.get_text().strip() or "03:00"
        config.maintenance.tasks = [
            task_id for task_id, check in self.maint_task_checks.items()
            if check.get_active()
        ]
        config.maintenance.notify = self.maint_notify.get_active()
        return True

    def _validate_appearance(self, widget) -> bool:
        theme = self.appearance_theme.get_active_id()
        accent = self.appearance_accent.get_active_id()
        wallpaper = self.appearance_wallpaper.get_active_id()
        return (theme in VALID_THEMES and accent in VALID_ACCENTS and
                wallpaper in ["auto", "light", "dark", "custom"])

    def _apply_appearance(self, widget, config) -> bool:
        config.appearance.theme = self.appearance_theme.get_active_id() or "system"
        config.appearance.accent = self.appearance_accent.get_active_id() or "ayusos"
        config.appearance.wallpaper_mode = self.appearance_wallpaper.get_active_id() or "auto"
        return True

    def _apply_finish(self, widget, config) -> bool:
        # Guardar todas las elecciones en preferencias de usuario (sin root).
        prefs = load_user_preferences()
        prefs.update(config.to_dict())
        prefs.pop("_schema_version", None)
        save_user_preferences(prefs)
        # Marcar onboarding completado (conserva las preferencias existentes).
        mark_onboarding_done(self.version)
        return True

    # --- Navegación ---

    def _show_step(self, index: int):
        if index < 0 or index >= len(self.steps):
            return

        self.current_index = index
        step = self.steps[index]

        # Limpiar contenido anterior
        for child in self.content_box.get_children():
            self.content_box.remove(child)

        # Crear widget del paso si no existe
        if step.widget is None:
            step.widget = step.widget_factory()

        # Añadir al contenido
        self.content_box.pack_start(step.widget, True, True, 0)
        self.content_box.show_all()

        # Actualizar header
        self.title_label.set_text(step.title)
        self.subtitle_label.set_text(step.description)
        self.progress_bar.set_value((index + 1) / len(self.steps))
        self.step_label.set_text(f"{traducir('Paso')} {index + 1} {traducir('de')} {len(self.steps)}: {step.title}")

        # Botones
        self.btn_back.set_sensitive(index > 0)
        is_last = (index == len(self.steps) - 1)
        self.btn_next.set_label(traducir("Finalizar") if is_last else traducir("Siguiente"))
        if is_last:
            self.btn_next.get_style_context().remove_class("onboarding-button-primary")
            self.btn_next.get_style_context().add_class("onboarding-button-accent")

    def _on_next(self, _):
        step = self.steps[self.current_index]

        # Validar
        if step.validate_fn and not step.validate_fn(step.widget):
            self._show_error(traducir("Por favor, completa correctamente este paso."))
            return

        # Aplicar
        if step.apply_fn and not step.apply_fn(step.widget, self.config):
            self._show_error(traducir("Error al aplicar la configuración."))
            return

        step.completed = True

        # Siguiente paso o finalizar
        if self.current_index + 1 < len(self.steps):
            self._show_step(self.current_index + 1)
        else:
            # _apply_finish ya ha persistido la configuracion del usuario.
            self.emit("completed")

    def _on_back(self, _):
        if self.current_index > 0:
            self._show_step(self.current_index - 1)

    def _on_skip(self, _):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=traducir("¿Saltar configuración?"),
        )
        dialog.format_secondary_text(traducir(
            "Se usarán los valores por defecto. Podrás configurar todo después "
            "desde el Centro de Control."
        ))
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.YES:
            mark_onboarding_done(self.version)
            self.emit("completed")

    def _show_error(self, message: str):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message,
        )
        dialog.run()
        dialog.destroy()

    def _on_destroy(self, _):
        if self.parent_window:
            self.parent_window.present()


def launch_onboarding(parent=None) -> OnboardingWizard:
    """Lanza el wizard de onboarding. Retorna la ventana."""
    wizard = OnboardingWizard(parent)
    wizard.show_all()
    return wizard


def should_launch_onboarding() -> bool:
    """True si se debe lanzar onboarding (AyusOS instalado + no completado)."""
    from ..branding import es_ayusos
    from .ayusos_config import is_onboarding_completed
    if not es_ayusos() or is_onboarding_completed():
        return False
    # Nunca interrumpir Calamares en la sesion Live.
    if os.path.exists("/run/live/medium"):
        return False
    try:
        if "boot=live" in Path("/proc/cmdline").read_text(encoding="utf-8").split():
            return False
    except OSError:
        pass
    return True