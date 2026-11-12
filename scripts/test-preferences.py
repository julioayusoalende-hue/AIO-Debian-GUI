#!/usr/bin/python3
import importlib.machinery
import importlib.util
import pathlib
import sys
import tempfile

import gi

sys.dont_write_bytecode = True
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


loader = importlib.machinery.SourceFileLoader("aio_debian_gui_test", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
app = importlib.util.module_from_spec(spec)
loader.exec_module(app)

assert app.cargar_preferencias("/nonexistent/aio-debian-gui/preferences.json") == (
    app.PREFERENCIAS_DEFECTO
)

with tempfile.TemporaryDirectory() as directorio:
    ruta = pathlib.Path(directorio) / "preferences.json"
    valores = {"idioma": "zh", "tema": "oscuro", "modo_simple": True}
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
        assert ventana.get_titlebar().get_subtitle() == subtitulo
        ventana.show_all()
        menu = ventana.menu_popover.get_child()
        assert menu.get_visible()
        botones_menu = menu.get_children()
        assert len(botones_menu) == 1
        assert botones_menu[0].get_visible()
        assert botones_menu[0].get_label() == app.traducir("Preferencias")
        ventana.btn_menu.set_active(True)
        while Gtk.events_pending():
            Gtk.main_iteration()
        assert ventana.menu_popover.get_visible()
        assert menu.get_allocation().width > 1
        ventana.btn_menu.set_active(False)
        assert ventana.marco_consola.get_visible()
        assert ventana.log.get_visible()
        ventana._escribir("visible output")
        inicio, fin = ventana.buf.get_bounds()
        assert ventana.buf.get_text(inicio, fin, True) == "visible output"
        ventana.destroy()

    ventana = app.VentanaPrincipal(
        {"idioma": "es", "tema": "claro", "modo_simple": True}
    )
    ventana.show_all()
    assert not ventana.marco_consola.get_visible()
    assert not ventana.log.get_visible()
    ventana._escribir("hidden output")
    inicio, fin = ventana.buf.get_bounds()
    assert ventana.buf.get_text(inicio, fin, True) == ""
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
                else:
                    combo.set_active_id(tema)
            casillas[0].set_active(modo_simple)
            dialogo.response(Gtk.ResponseType.OK)
            return GLib.SOURCE_REMOVE

        GLib.idle_add(guardar_desde_dialogo, "en", "oscuro", True)
        ventana._abrir_preferencias(None)
        guardadas = app.cargar_preferencias(str(ruta))
        assert guardadas == {
            "idioma": "en", "tema": "oscuro", "modo_simple": True
        }, guardadas
        nuevas_ventanas = [
            widget for widget in Gtk.Window.list_toplevels()
            if isinstance(widget, app.VentanaPrincipal)
        ]
        assert len(nuevas_ventanas) == 1
        nueva = nuevas_ventanas[0]
        assert nueva.get_titlebar().get_subtitle() == (
            "System maintenance and configuration"
        )
        assert not nueva.marco_consola.get_visible()
        assert Gtk.Settings.get_default().get_property(
            "gtk-application-prefer-dark-theme"
        )
        GLib.idle_add(guardar_desde_dialogo, "en", "oscuro", False)
        nueva._abrir_preferencias(None)
        assert nueva.marco_consola.get_visible()
        assert nueva.log.get_visible()
        nueva._escribir("console restored")
        inicio, fin = nueva.buf.get_bounds()
        assert nueva.buf.get_text(inicio, fin, True) == "console restored"
        nueva.disconnect(nueva.handler_cierre)
        nueva.destroy()
        app.aplicar_tema("claro")
    app.VentanaPrincipal._consultar_estados_tareas = consulta_original

print("Preference persistence, language translations, and simple mode: OK")
