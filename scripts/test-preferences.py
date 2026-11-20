#!/usr/bin/python3
import importlib.machinery
import importlib.util
import os
import pathlib
import sys
import tempfile
import time

import gi

sys.dont_write_bytecode = True
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


loader = importlib.machinery.SourceFileLoader("aio_debian_gui_test", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)

appdir_original = os.environ.get("APPDIR")
os.environ["APPDIR"] = "/tmp/appimage-mount"
helper_sistema_original = app.HELPER_SISTEMA
app.HELPER_SISTEMA = "/usr/lib/aio-debian-gui/no-installed-helper"
helper = app.helper_mantenimiento()
assert helper == app.HELPER_SISTEMA
assert not app.helper_disponible(helper)
assert app.comando_pkexec(helper, "es_ES.UTF-8", "upgrade") == [
    "pkexec", helper, "--lang", "es_ES.UTF-8", "upgrade"
]
app.HELPER_SISTEMA = helper_sistema_original
if appdir_original is None:
    os.environ.pop("APPDIR", None)
else:
    os.environ["APPDIR"] = appdir_original

assert app.cargar_preferencias("/nonexistent/aio-debian-gui/preferences.json") == (
    app.PREFERENCIAS_DEFECTO
)

with tempfile.TemporaryDirectory() as directorio:
    ruta = pathlib.Path(directorio) / "preferences.json"
    valores = {"idioma": "zh", "tema": "oscuro", "modo_simple": True}
    app.guardar_preferencias(valores, str(ruta))
    assert app.cargar_preferencias(str(ruta)) == dict(valores, carpeta_repositorios="", canal_actualizaciones="stable")
    valores["carpeta_repositorios"] = directorio
    valores["canal_actualizaciones"] = "testing"
    app.guardar_preferencias(valores, str(ruta))
    assert app.cargar_preferencias(str(ruta)) == valores
    ruta.write_text('{"idioma":"invalid"}', encoding="utf-8")
    try:
        app.cargar_preferencias(str(ruta))
    except ValueError:
        pass
    else:
        raise AssertionError("A language outside the supported set was accepted.")

for idioma in ("en", "fr", "zh"):
    app.IDIOMA_ACTUAL = idioma
    assert app.traducir("Preferencias") != "Preferencias"
    for paso in app.PASOS:
        for texto in paso[1:3]:
            assert texto in app.TRADUCCIONES[idioma], (idioma, texto)

if Gtk.init_check([])[0]:
    for idioma, subtitulo in (
        ("en", "System maintenance and configuration"),
        ("fr", "Maintenance et configuration du système"),
        ("zh", "系统维护与配置"),
    ):
        ventana = app.VentanaPrincipal(
            {"idioma": idioma, "tema": "claro", "modo_simple": False}
        )
        assert ventana.get_titlebar().get_custom_title() is not None
        ventana.show_all()
        menu = ventana.menu_popover.get_child()
        assert menu.get_visible()
        botones_menu = menu.get_children()
        assert len(botones_menu) == 5
        assert all(boton.get_visible() for boton in botones_menu)
        assert [boton.get_label() for boton in botones_menu] == [
            app.traducir("Preferencias"),
            app.traducir("Historial de mantenimiento"),
            app.traducir("Programar mantenimiento"),
            app.traducir("Buscar actualizaciones"),
            app.traducir("Acerca de AiO Debian"),
        ]
        assert ventana.btn_preferencias_menu is botones_menu[0]
        assert ventana.btn_programar is botones_menu[2]
        assert ventana.btn_actualizar is botones_menu[3]
        assert ventana.paneles_principales.get_orientation() == Gtk.Orientation.HORIZONTAL
        ventana.btn_menu.set_active(True)
        deadline = time.monotonic() + 2
        while menu.get_allocation().width <= 1 and time.monotonic() < deadline:
            while Gtk.events_pending():
                Gtk.main_iteration()
            time.sleep(.005)
        assert ventana.menu_popover.get_visible()
        assert menu.get_allocation().width > 1
        ventana.btn_menu.set_active(False)
        assert ventana.marco_consola.get_visible()
        assert ventana.log.get_visible()
        ventana._escribir("visible output")
        inicio, fin = ventana.buf.get_bounds()
        assert ventana.buf.get_text(inicio, fin, True) == "visible output"
        ventana.btn_ver_terminal.clicked()
        assert ventana.notebook.get_current_page() == ventana.notebook.page_num(ventana.pagina_terminal)
        ventana._escribir(" - terminal")
        inicio, fin = ventana.buf.get_bounds()
        assert ventana.buf.get_text(inicio, fin, True) == "visible output - terminal"
        assert ventana.marco_consola.get_visible()
        ventana.destroy()

    ventana = app.VentanaPrincipal(
        {"idioma": "es", "tema": "claro", "modo_simple": True}
    )
    ventana.show_all()
    assert not ventana.expansor_consola.get_expanded()
    assert [p.get_visible() for p in ventana.notebook.get_children()] == [True, False, False, False, False]
    assert not ventana.panel_derecho.get_visible()
    assert ventana.panel_izquierdo.get_visible()
    ventana.preferencias["modo_simple"] = False
    ventana._aplicar_modo_simple()
    assert ventana.panel_derecho.get_visible()
    assert ventana.btn_diagnostico.get_visible()
    ventana.preferencias["modo_simple"] = True
    ventana._aplicar_modo_simple()
    ventana.show_all()
    assert not ventana.panel_derecho.get_visible()
    ventana._abrir_terminal()
    assert ventana.notebook.get_current_page() == 0
    ventana._escribir("hidden output", "error")
    assert not ventana.expansor_consola.get_visible()
    ventana._preparar_resultados(["upgrade"])
    ventana._resultado_tarea("upgrade", "Error")
    assert not ventana.expansor_consola.get_visible()
    inicio, fin = ventana.buf.get_bounds()
    assert ventana.buf.get_text(inicio, fin, True) == "hidden output"
    ventana.destroy()

    ventana = app.VentanaPrincipal(
        {"idioma": "es", "tema": "claro", "modo_simple": False}
    )
    ventana.consulta_inicial = True
    ventana.consultando_estados = True
    ventana._actualizar_sensibilidad()
    assert not ventana.btn_iniciar.get_sensitive()
    # Configuración de Polkit deshabilitada mientras hay una operación activa.
    assert not ventana.chk_sin_contrasena.get_sensitive()
    assert ventana.btn_menu.get_sensitive()
    assert all(boton.get_sensitive() for boton in ventana.botones_preset.values())
    assert all(fila.get_sensitive() for pid, fila in ventana.filas.items() if pid != "nvidia-driver")
    assert all(switch.get_sensitive() for pid, (switch, _) in ventana.switches.items() if pid != "nvidia-driver")

    ventana._estados_terminados(-1, "", "El asistente no respondió en 15 segundos.")
    assert not ventana.consultando_estados
    assert ventana.btn_iniciar.get_sensitive()
    assert all(fila.get_sensitive() for pid, fila in ventana.filas.items() if pid != "nvidia-driver")
    ventana.destroy()

    ventana = app.VentanaPrincipal(
        {"idioma": "es", "tema": "claro", "modo_simple": False}
    )
    acerca = ventana._crear_dialogo_acerca_de()

    def widgets_descendientes(widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for hijo in widget.get_children():
                yield from widgets_descendientes(hijo)

    credito = next(
        widget for widget in widgets_descendientes(acerca)
        if isinstance(widget, Gtk.Label) and widget.get_text() == "© 2026 Julio Ayuso"
    )
    assert 'size="large"' in credito.get_label()
    assert '<a href="aio-debian-gui://inspiracion">Julio Ayuso</a>' in credito.get_label()

    dedicatoria = {}

    def cerrar_dedicatoria():
        dialogos = [
            widget for widget in Gtk.Window.list_toplevels()
            if isinstance(widget, Gtk.Dialog)
            and widget is not acerca
            and widget.get_title() == app.traducir("Agradecimiento")
        ]
        if not dialogos:
            return GLib.SOURCE_CONTINUE
        dialogo = dialogos[-1]
        try:
            hijos = list(widgets_descendientes(dialogo))
            imagenes = [widget for widget in hijos if isinstance(widget, Gtk.Image)]
            textos = [
                widget.get_text() for widget in hijos
                if isinstance(widget, Gtk.Label)
            ]
            assert len(imagenes) == 1
            assert imagenes[0].get_pixbuf() is not None
            assert "Gracias a Adri y Lu por ser mi inspiración en TODO lo que hago" in textos
            dedicatoria["visible"] = True
        except Exception as error:
            dedicatoria["error"] = error
        finally:
            dialogo.response(Gtk.ResponseType.CLOSE)
        return GLib.SOURCE_REMOVE

    GLib.idle_add(cerrar_dedicatoria)
    assert credito.emit("activate-link", "aio-debian-gui://inspiracion")
    assert dedicatoria.get("visible"), dedicatoria
    assert "error" not in dedicatoria, dedicatoria
    acerca.destroy()
    ventana.destroy()

    ventana = app.VentanaPrincipal(
        {"idioma": "es", "tema": "claro", "modo_simple": False}
    )
    consulta_original = app.VentanaPrincipal._consultar_estados_tareas
    app.VentanaPrincipal._consultar_estados_tareas = lambda self, inicial=False: None
    ventana.handler_cierre = ventana.connect("destroy", Gtk.main_quit)
    with tempfile.TemporaryDirectory() as directorio:
        ruta = pathlib.Path(directorio) / "preferences.json"
        app.ruta_preferencias = lambda: str(ruta)

        def guardar_desde_dialogo(idioma, tema, modo_simple):
            dialogos = [
                widget for widget in Gtk.Window.list_toplevels()
                if isinstance(widget, Gtk.Dialog)
            ]
            if not dialogos:
                return GLib.SOURCE_CONTINUE
            dialogo = dialogos[-1]
            combos = [
                widget for widget in dialogo.get_content_area().get_children()[0].get_children()
                if isinstance(widget, Gtk.ComboBox)
            ]
            casillas = [
                widget for widget in dialogo.get_content_area().get_children()[0].get_children()
                if isinstance(widget, Gtk.CheckButton)
            ]
            for combo in combos:
                if combo.get_active_id() in {"es", "en", "fr", "zh"}:
                    combo.set_active_id(idioma)
                elif combo.get_active_id() in {"sistema", "claro", "oscuro"}:
                    combo.set_active_id(tema)
            casillas[0].set_active(modo_simple)
            dialogo.response(Gtk.ResponseType.OK)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(guardar_desde_dialogo, "en", "oscuro", True)
        ventana._abrir_preferencias(None)
        guardadas = app.cargar_preferencias(str(ruta))
        assert guardadas == {
            "idioma": "en", "tema": "oscuro", "modo_simple": True, "carpeta_repositorios": "",
            "canal_actualizaciones": "stable"
        }, guardadas
        nuevas_ventanas = [
            widget for widget in Gtk.Window.list_toplevels()
            if isinstance(widget, app.VentanaPrincipal)
        ]
        assert len(nuevas_ventanas) == 1
        nueva = nuevas_ventanas[0]
        assert nueva.get_titlebar().get_custom_title() is not None
        assert not nueva.expansor_consola.get_expanded()
        assert [p.get_visible() for p in nueva.notebook.get_children()] == [True, False, False, False, False]
        assert Gtk.Settings.get_default().get_property(
            "gtk-application-prefer-dark-theme"
        )
        GLib.idle_add(guardar_desde_dialogo, "en", "oscuro", False)
        nueva._abrir_preferencias(None)
        nueva = next(widget for widget in Gtk.Window.list_toplevels()
                     if isinstance(widget, app.VentanaPrincipal))
        assert not nueva.expansor_consola.get_expanded()
        nueva.expansor_consola.set_expanded(True)
        assert nueva.marco_consola.get_visible()
        assert all(p.get_visible() for p in nueva.notebook.get_children())
        nueva.notebook.set_current_page(2)
        GLib.idle_add(guardar_desde_dialogo, "en", "oscuro", True)
        nueva._abrir_preferencias(None)
        assert nueva.notebook.get_current_page() == 0
        assert [p.get_visible() for p in nueva.notebook.get_children()] == [True, False, False, False, False]
        nueva._escribir("console restored")
        inicio, fin = nueva.buf.get_bounds()
        assert nueva.buf.get_text(inicio, fin, True) == "console restored"
        nueva.disconnect(nueva.handler_cierre)
        nueva.destroy()
        app.aplicar_tema("claro")
    app.VentanaPrincipal._consultar_estados_tareas = consulta_original

print("Preference persistence, language translations, about dialog, and simple mode: OK")
