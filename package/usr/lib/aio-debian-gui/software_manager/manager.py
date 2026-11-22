#!/usr/bin/python3
"""AyusOS Software Manager GTK interface."""

from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

from . import backend

PAGES = ('DEB', 'Flatpak', 'Repositorios')


class SoftwareManagerPage(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.rows = []
        self.timer = 0
        self.busy = False
        self.applying_changes = False
        self.catalogues = {}
        self.loaded = False
        self.destroyed = False
        self.connect('destroy', self.on_destroy)

        toolbar = Gtk.Box(spacing=8)
        self.pack_start(toolbar, False, False, 0)
        self.page = Gtk.ComboBoxText()
        for name in PAGES:
            self.page.append_text(name)
        self.page.set_active(0)
        toolbar.pack_start(self.page, False, False, 0)
        self.scope = Gtk.ComboBoxText()
        self.scope.append('user', 'Usuario')
        self.scope.append('system', 'Sistema')
        self.scope.set_active_id('user')
        toolbar.pack_end(self.scope, False, False, 0)

        self.search = Gtk.SearchEntry(placeholder_text='Buscar por nombre o identificador…')
        self.search.set_max_length(200)
        toolbar.pack_start(self.search, True, True, 0)
        self.completions = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion(model=self.completions, text_column=0,
                                         minimum_key_length=2)
        completion.set_match_func(lambda *_: True)
        self.search.set_completion(completion)

        self.filters = Gtk.ComboBoxText()
        for name in ('Todos', 'Instalados', 'Disponibles', 'Actualizables'):
            self.filters.append_text(name)
        self.filters.set_active(0)
        toolbar.pack_end(self.filters, False, False, 0)

        self.store = Gtk.ListStore(str, str, str, str, str)
        self.view = Gtk.TreeView(model=self.store, enable_search=False)
        self.columns = []
        for index in range(5):
            column = Gtk.TreeViewColumn('')
            if index == 0:
                installed = Gtk.CellRendererText(foreground='#269343', weight=700,
                                                 width=24, xalign=0.5)
                column.pack_start(installed, False)
                column.set_cell_data_func(installed, self.show_installed_mark)
            name = Gtk.CellRendererText(ellipsize=3)
            column.pack_start(name, True)
            column.add_attribute(name, 'text', index)
            column.set_resizable(True)
            column.set_sort_column_id(index)
            column.set_expand(index in (0, 1))
            self.view.append_column(column)
            self.columns.append(column)
        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scroller.add(self.view)
        self.pack_start(scroller, True, True, 0)

        self.actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                   column_spacing=6, row_spacing=4, max_children_per_line=8)
        self.pack_start(self.actions, False, False, 0)
        self.status = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status, False, False, 0)

        self.page.connect('changed', self.change_page)
        self.scope.connect('changed', self.change_page)
        self.search.connect('changed', self.queue_filter)
        self.filters.connect('changed', self.queue_filter)
        self.view.get_selection().connect('changed', lambda *_: self.show_actions())
        self.scope.set_no_show_all(True)
        self.connect('map', self.on_map)

    @staticmethod
    def show_installed_mark(_column, renderer, model, iterator, _data):
        state = model.get_value(iterator, 3)
        renderer.set_property('text', '✓' if state in ('Instalado', 'Actualizable') else '')

    def on_map(self, _widget):
        if not self.loaded:
            self.loaded = True
            self.change_page()

    def on_destroy(self, _widget):
        self.destroyed = True
        if self.timer:
            GLib.source_remove(self.timer)
            self.timer = 0
        self.pool.shutdown(wait=False, cancel_futures=True)

    def queue_filter(self, *_):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add(40, self.filter_rows)

    def filter_rows(self):
        self.timer = 0
        query = self.search.get_text().strip().casefold()
        wanted = self.filters.get_active()
        packages = self.page.get_active() != 2
        self.store.clear()
        self.completions.clear()
        suggestions = set()
        prefixes, matches = [], []
        for row in self.rows:
            fields = (row[0].casefold(), row[1].casefold())
            if packages and wanted and row[3] not in (
                (), ('Instalado', 'Actualizable'), ('Disponible',), ('Actualizable',)
            )[wanted]:
                continue
            if not all(any(term in field for field in fields) for term in query.split()):
                continue
            (prefixes if any(field.startswith(query) for field in fields) else matches).append(row)
        found = prefixes + matches
        for row in found[:1500]:
            self.store.append(row)
            if len(query) >= 2 and len(suggestions) < 12:
                suggestion = row[0] or row[1]
                if suggestion not in suggestions:
                    suggestions.add(suggestion)
                    self.completions.append((suggestion,))
        if not self.busy:
            total = len(found)
            visible = f'Mostrando {len(self.store):,} de ' if total > len(self.store) else ''
            self.status.set_text(f'{visible}{total:,} resultados')
        return False

    def change_page(self, *_):
        page = self.page.get_active()
        self.scope.set_visible(page != 0)
        self.filters.set_visible(page == 0)
        self.search.set_text('')
        self.search.set_placeholder_text(
            'Buscar repositorios…' if page == 2 else 'Buscar por nombre o identificador…')
        names = ('Nombre', 'URL', 'Tipo', 'Estado', 'Origen o archivo') if page == 2 else (
            'Nombre', 'Identificador', 'Versión', 'Estado', 'Arquitectura' if page == 0 else 'Remoto')
        for column, title in zip(self.columns, names):
            column.set_title(title)
        self.load()

    def job(self, message, task, completed):
        self.busy = True
        for widget in (self.page, self.scope, self.actions):
            widget.set_sensitive(False)
        self.status.set_text(message)
        future = self.pool.submit(task)

        def finish():
            if self.destroyed:
                return False
            self.applying_changes = False
            self.busy = False
            for widget in (self.page, self.scope, self.actions):
                widget.set_sensitive(True)
            try:
                result = future.result()
            except (RuntimeError, OSError, ValueError) as exc:
                self.status.set_text('La operación no se pudo completar')
                self.message('Error', str(exc))
            else:
                completed(result)
            self.show_actions()
            return False

        future.add_done_callback(lambda _: GLib.idle_add(finish))

    def load(self, force=False):
        page, scope = self.page.get_active(), self.scope.get_active_id()
        key = (page, scope if page else None)

        def display(result):
            self.catalogues[key] = result
            self.rows, errors = result
            if self.timer:
                GLib.source_remove(self.timer)
            self.filter_rows()
            if errors:
                self.status.set_text(f'{len(self.store):,} resultados · {len(errors)} remotos inaccesibles')
                self.status.set_tooltip_text('\n'.join(errors))
            else:
                self.status.set_tooltip_text(None)
            self.show_actions()

        if not force and key in self.catalogues:
            display(self.catalogues[key])
        else:
            self.rows = []
            self.store.clear()
            self.show_actions()
            readers = (backend.debs, lambda: backend.flatpaks(scope), lambda: backend.repos(scope))
            self.job('Cargando catálogo…', readers[page], display)

    def selected(self):
        model, iterator = self.view.get_selection().get_selected()
        return tuple(model[iterator]) if iterator else None

    def show_actions(self):
        for child in self.actions.get_children():
            self.actions.remove(child)
        page, scope = self.page.get_active(), self.scope.get_active_id()
        row = self.selected()
        if page in (0, 2):
            self.button('Actualizar índices APT', lambda: self.modify(
                'Actualizar los índices de APT', self.admin('refresh')))
        self.button('Recargar', lambda: self.load(force=True))
        if page == 2:
            self.button('Añadir repositorio APT…', self.add_apt)
            self.button('Añadir remoto Flatpak…', self.add_remote)
            if row and row[2] == 'Flatpak':
                toggle = 'Desactivar' if row[3] == 'Activo' else 'Activar'
                command = 'disable' if row[3] == 'Activo' else 'enable'
                self.button(toggle, lambda: self.modify(f'{toggle} {row[0]}',
                    backend.flatpak(scope, 'remote-modify', f'--{command}', '--', row[4])))
                self.button('Quitar', lambda: self.modify(f'Quitar el remoto {row[0]}',
                    backend.flatpak(scope, 'remote-delete', '--', row[4])))
            elif row:
                toggle = 'Restaurar archivo' if row[4].endswith('.disabled') else 'Pausar archivo'
                command = 'enable' if row[4].endswith('.disabled') else 'disable'
                self.button(toggle, lambda: self.modify(toggle, self.admin(command, row[4]),
                    f'Se aplica a todas las entradas de {row[4]}.'))
                if row[2] == 'APT • gestionado':
                    self.button('Quitar', lambda: self.modify(f'Quitar el repositorio {row[0]}',
                        self.admin('delete', row[4])))
        elif page == 1:
            self.button('Actualizar todos', lambda: self.modify(
                'Actualizar los Flatpaks de este ámbito', backend.flatpak(scope, 'update', '-y')))
        if row and page in (0, 1):
            if row[3] == 'Disponible':
                self.button('Instalar', lambda: self.package_action(page, scope, row, 'install'))
            else:
                if row[3] == 'Actualizable' or page == 1:
                    self.button('Actualizar', lambda: self.package_action(page, scope, row, 'upgrade'))
                self.button('Desinstalar', lambda: self.package_action(page, scope, row, 'remove'))
        self.actions.show_all()

    def button(self, label, action):
        button = Gtk.Button(label=label)
        button.connect('clicked', lambda *_: action())
        self.actions.add(button)

    @staticmethod
    def admin(*args):
        return ['/usr/bin/pkexec', backend.ADMIN, *args]

    def message(self, title, details='', confirm=False):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, text=title,
                                   buttons=Gtk.ButtonsType.OK_CANCEL if confirm else Gtk.ButtonsType.CLOSE)
        if details:
            area = dialog.get_message_area()
            scroll = Gtk.ScrolledWindow(min_content_width=500, min_content_height=180)
            view = Gtk.TextView(editable=False, cursor_visible=False,
                                monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
            view.get_buffer().set_text(details)
            scroll.add(view)
            area.pack_start(scroll, True, True, 0)
            scroll.show_all()
        dialog.set_default_response(Gtk.ResponseType.CANCEL if confirm else Gtk.ResponseType.CLOSE)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.OK

    def modify(self, title, command, details=''):
        if self.busy or not self.message(title, details, confirm=True):
            return

        def finished(_output):
            self.catalogues.clear()
            self.load(force=True)

        self.applying_changes = True
        self.job('Aplicando cambios…', lambda: backend.run(command), finished)

    def package_action(self, page, scope, row, action):
        name, identifier, _, _, origin = row
        verb = {'install': 'Instalar', 'upgrade': 'Actualizar', 'remove': 'Desinstalar'}[action]
        if page == 1:
            args = {'install': ['install', '-y', '--', origin, identifier],
                    'upgrade': ['update', '-y', '--', identifier],
                    'remove': ['uninstall', '-y', '--', identifier]}[action]
            self.modify(f'{verb} {name}', backend.flatpak(scope, *args))
            return
        apt_action = ['install', '--only-upgrade'] if action == 'upgrade' else [action]
        simulate = ['/usr/bin/apt-get', '-s', *apt_action, '--', identifier]
        self.job('Comprobando dependencias…', lambda: backend.run(simulate),
                 lambda plan: self.modify(f'{verb} {identifier}', self.admin(action, identifier), plan))

    def fields(self, title, fields):
        dialog = Gtk.Dialog(title=title, transient_for=self.window, modal=True)
        dialog.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Continuar', Gtk.ResponseType.OK)
        grid = Gtk.Grid(column_spacing=12, row_spacing=10, margin=16)
        entries = []
        for index, (label, default) in enumerate(fields):
            entry = Gtk.Entry(text=default, width_chars=48)
            grid.attach(Gtk.Label(label=label, xalign=0), 0, index, 1, 1)
            grid.attach(entry, 1, index, 1, 1)
            entries.append(entry)
        dialog.get_content_area().add(grid)
        dialog.show_all()
        response = dialog.run()
        values = [entry.get_text().strip() for entry in entries]
        dialog.destroy()
        return values if response == Gtk.ResponseType.OK else None

    def add_apt(self):
        values = self.fields('Añadir repositorio APT', (
            ('URL HTTPS', ''), ('Distribución', 'trixie'), ('Componentes', 'main'),
            ('Clave de firma local (.asc o .gpg)', '')))
        if values:
            try:
                backend.source_contents(*values)
            except (OSError, ValueError) as exc:
                self.message('Comprueba los datos del repositorio', str(exc))
                return
            self.modify('Añadir repositorio APT', self.admin('add-source', *values), values[0])

    def add_remote(self):
        values = self.fields('Añadir remoto Flatpak', (
            ('Nombre', 'flathub'), ('URL del archivo .flatpakrepo', backend.FLATPAK_REPO)))
        if values:
            name, url = values
            if not name or not url.startswith('https://') or not url.endswith('.flatpakrepo'):
                self.message('Indica un nombre y una URL HTTPS de un archivo .flatpakrepo')
                return
            scope = self.scope.get_active_id()
            self.modify(f'Añadir {name}', backend.flatpak(
                scope, 'remote-add', '--if-not-exists', '--', name, url), url)
