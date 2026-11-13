#!/usr/bin/python3
import importlib.machinery
import importlib.util
import os
import pathlib
import subprocess
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

appdir_original = os.environ.get("APPDIR")
os.environ["APPDIR"] = "/tmp/appimage-mount"
helper_sistema_original = app.HELPER_SISTEMA
app.HELPER_SISTEMA = "/usr/lib/aio-debian-gui/no-installed-helper"
helper = app.helper_mantenimiento()
assert helper != app.HELPER
assert helper.startswith("/tmp/aio-debian-gui-")
assert pathlib.Path(helper).read_bytes() == pathlib.Path(app.HELPER).read_bytes()
assert pathlib.Path(helper).stat().st_mode & 0o111
assert pathlib.Path(helper).parents[2].joinpath(
    "share/polkit-1/actions/es.aiodebian.gui.policy"
).is_file()
assert app.helper_mantenimiento() == helper
assert app.comando_pkexec(helper, "es_ES.UTF-8", "upgrade") == [
    "pkexec", "/bin/bash", helper, "--lang", "es_ES.UTF-8", "upgrade"
]
resultado = subprocess.run(
    ["/bin/bash", helper, "--status"],
    capture_output=True, text=True, timeout=10,
)
assert resultado.returncode == 0, resultado.stderr
assert "##STATUS:repos:" in resultado.stdout
for directorio in app._directorios_helper_appimage:
    directorio.cleanup()
app._directorios_helper_appimage.clear()
app._helper_appimage_temporal = None
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
        assert ventana.get_titlebar().get_subtitle().startswith(subtitulo)
        ventana.show_all()
        menu = ventana.menu_popover.get_child()
        assert menu.get_visible()
        botones_menu = menu.get_children()
        assert len(botones_menu) == 2
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
    ventana.consulta_inicial = True
    ventana.consultando_estados = True
    ventana._actualizar_sensibilidad()
    assert not ventana.btn_iniciar.get_sensitive()
    # Solo se permite revocar reglas antiguas; nunca crear nuevas.
    assert ventana.chk_sin_contrasena.get_sensitive() == ventana.chk_sin_contrasena.get_active()
    assert ventana.btn_menu.get_sensitive()
    assert all(boton.get_sensitive() for boton in ventana.botones_preset)
    assert all(fila.get_sensitive() for fila in ventana.filas.values())
    assert all(switch.get_sensitive() for switch, _ in ventana.switches.values())

    class ProcesoSimulado:
        def __init__(self):
            self.cancelado = False

        def force_exit(self):
            self.cancelado = True

    proceso = ProcesoSimulado()
    ventana.proceso_estados = proceso
    assert ventana._consulta_estados_agotada() == GLib.SOURCE_REMOVE
    assert proceso.cancelado
    assert not ventana.consultando_estados
    assert ventana.btn_iniciar.get_sensitive()
    assert all(fila.get_sensitive() for fila in ventana.filas.values())
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

print("Preference persistence, language translations, about dialog, and simple mode: OK")
