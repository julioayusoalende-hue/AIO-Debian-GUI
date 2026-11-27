"""GUI tests using xvfb."""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'package', 'usr', 'lib', 'aio-debian-gui'))

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import GLib, Gtk


class TestGUI:
    """Tests básicos de GUI."""

    def test_gtk_initialization(self):
        """Test que GTK se inicializa correctamente."""
        # En xvfb, Gtk.init() debería funcionar
        assert Gtk.get_major_version() == 3

    def test_widget_creation(self):
        """Test creación de widgets básicos."""
        window = Gtk.Window()
        window.set_default_size(400, 300)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        window.add(box)

        label = Gtk.Label(label="Test")
        box.pack_start(label, True, True, 0)

        button = Gtk.Button(label="Click")
        box.pack_start(button, False, False, 0)

        window.show_all()

        # Verificar jerarquía
        assert window.get_child() == box
        children = box.get_children()
        assert len(children) == 2

        window.destroy()

    def test_css_provider(self):
        """Test CSS provider."""
        css = b"""
        .test-class {
            color: red;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)

        # Verificar que se cargó sin depender del backend (X11/Wayland):
        # GdkWaylandWindow no expone get_style_context().
        context = Gtk.StyleContext.new()
        context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        assert context.get_color(Gtk.StateFlags.NORMAL) is not None

    def test_dialog_creation(self):
        """Test creación de diálogos."""
        dialog = Gtk.MessageDialog(
            transient_for=None,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Test"
        )
        dialog.format_secondary_text("Details")
        dialog.destroy()

    def test_tree_view_model(self):
        """Test TreeView con ListStore."""
        store = Gtk.ListStore(str, int)
        store.append(['Item 1', 1])
        store.append(['Item 2', 2])

        tree = Gtk.TreeView(model=store)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn('Name', renderer, text=0)
        tree.append_column(column)

        column2 = Gtk.TreeViewColumn('Value', renderer, text=1)
        tree.append_column(column2)

        assert len(tree.get_columns()) == 2
        assert len(store) == 2

    def test_entry_completion(self):
        """Test EntryCompletion."""
        entry = Gtk.Entry()
        completion = Gtk.EntryCompletion()
        model = Gtk.ListStore(str)
        model.append(['Option 1'])
        model.append(['Option 2'])
        completion.set_model(model)
        completion.set_text_column(0)
        entry.set_completion(completion)

        assert entry.get_completion() == completion

    def test_file_chooser_dialog(self):
        """Test FileChooserDialog."""
        dialog = Gtk.FileChooserDialog(
            title="Test",
            transient_for=None,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_buttons('Cancel', Gtk.ResponseType.CANCEL, 'OK', Gtk.ResponseType.OK)

        filter = Gtk.FileFilter()
        filter.set_name('Test files')
        filter.add_pattern('*.txt')
        dialog.add_filter(filter)

        dialog.destroy()


class TestAsyncOperations:
    """Tests para operaciones asíncronas."""

    def test_idle_add(self):
        """Test GLib.idle_add."""
        results = []

        def callback():
            results.append('done')
            return GLib.SOURCE_REMOVE

        GLib.idle_add(callback)

        # Procesar main loop
        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(False)

        assert results == ['done']

    def test_timeout_add(self):
        """Test GLib.timeout_add."""
        results = []

        def callback():
            results.append('tick')
            if len(results) >= 3:
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(10, callback)

        # Procesar el main loop sin bloquear: iteration(True) puede esperar
        # indefinidamente si otra fuente mantiene el contexto ocupado.
        context = GLib.MainContext.default()
        deadline = time.monotonic() + 2
        while len(results) < 3 and time.monotonic() < deadline:
            if context.pending():
                context.iteration(False)
            else:
                time.sleep(0.01)

        assert len(results) >= 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
