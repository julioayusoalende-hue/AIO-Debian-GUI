#!/usr/bin/python3
"""AyusOS Software Manager GTK interface."""

from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk

from . import backend

PAGES = ('DEB', 'Flatpak', 'Repositorios')
VERBS = {'install': 'Instalar', 'upgrade': 'Actualizar', 'remove': 'Desinstalar'}
QUEUE_LIMIT = 100


class SoftwareManagerPage(Gtk.Box):
    def __init__(self, window, translate=lambda text: text, passwordless=lambda: False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.translate = translate
        self.passwordless = passwordless
        self.details_pool = ThreadPoolExecutor(max_workers=2)
        self.details_request = None
        self.details_timer = 0
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.rows = []
        self.queue = []
        self.catalogue_errors = []
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
            self.filters.append_text(self.translate(name))
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

        self.details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.details_title = Gtk.Label(xalign=0, ellipsize=3)
        self.details_title.get_style_context().add_class('aio-task-name')
        self.details.pack_start(self.details_title, False, False, 0)
        self.details_view = Gtk.TextView(editable=False, cursor_visible=False,
                                         wrap_mode=Gtk.WrapMode.WORD_CHAR, left_margin=8,
                                         right_margin=8, top_margin=6, bottom_margin=6)
        details_scroll = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN, min_content_height=118)
        details_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        details_scroll.add(self.details_view)
        self.details.pack_start(details_scroll, True, True, 0)
        self.details.show_all()
        self.details.set_no_show_all(True)
        self.pack_start(self.details, False, False, 0)

        self.actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                   column_spacing=6, row_spacing=4, max_children_per_line=8)
        self.pack_start(self.actions, False, False, 0)

        self.queue_frame = Gtk.Frame()
        queue_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin=8)
        self.queue_title = Gtk.Label(xalign=0)
        self.queue_title.get_style_context().add_class('aio-task-name')
        queue_box.pack_start(self.queue_title, False, False, 0)
        self.queue_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.queue_list.set_activate_on_single_click(False)
        queue_scroll = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.NONE,
                                          max_content_height=180,
                                          propagate_natural_height=True)
        queue_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        queue_scroll.add(self.queue_list)
        queue_box.pack_start(queue_scroll, False, False, 0)
        self.queue_actions = Gtk.Box(spacing=6)
        self.queue_apply = Gtk.Button()
        self.queue_apply.connect('clicked', lambda *_: self.apply_queue())
        self.queue_clear = Gtk.Button()
        self.queue_clear.connect('clicked', lambda *_: self.clear_queue())
        self.queue_actions.pack_end(self.queue_apply, False, False, 0)
        self.queue_actions.pack_end(self.queue_clear, False, False, 0)
        queue_box.pack_start(self.queue_actions, False, False, 0)
        self.queue_frame.add(queue_box)
        self.queue_frame.set_no_show_all(True)
        self.pack_start(self.queue_frame, False, False, 0)

        self.status = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status, False, False, 0)

        self.page.connect('changed', self.change_page)
        self.scope.connect('changed', self.change_page)
        self.search.connect('changed', self.queue_filter)
        self.filters.connect('changed', self.queue_filter)
        selection = self.view.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect('changed', self.selection_changed)
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
        self.cancel_details()
        self.details_pool.shutdown(wait=False, cancel_futures=True)
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
            text = f'{visible}{total:,} resultados'
            if self.catalogue_errors:
                text += ' · ' + (self.translate('No se pudieron consultar todos los remotos (%d)')
                                 % len(self.catalogue_errors))
            elif packages and wanted == 3 and not query and not total:
                text = self.translate('No hay actualizaciones disponibles.')
            self.status.set_text(text)
            self.status.set_tooltip_text('\n'.join(self.catalogue_errors) or None)
        return False

    def change_page(self, *_):
        page = self.page.get_active()
        scope = self.scope.get_active_id() if page else None
        if self.queue and any((item['page'], item['scope']) != (page, scope)
                              for item in self.queue):
            self.clear_queue()
        self.scope.set_visible(page != 0)
        self.filters.set_visible(page in (0, 1))
        self.search.set_text('')
        self.search.set_placeholder_text(
            'Buscar repositorios…' if page == 2 else 'Buscar por nombre o identificador…')
        names = ('Nombre', 'URL', 'Tipo', 'Estado', 'Origen o archivo') if page == 2 else (
            'Nombre', 'Identificador', 'Versión', 'Estado', 'Arquitectura' if page == 0 else 'Remoto')
        for column, title in zip(self.columns, names):
            column.set_title(title)
        self.load()
        self.show_details()

    def job(self, message, task, completed):
        self.busy = True
        for widget in (self.page, self.scope, self.actions, self.queue_actions):
            widget.set_sensitive(False)
        self.status.set_text(message)
        future = self.pool.submit(task)

        def finish():
            if self.destroyed:
                return False
            self.applying_changes = False
            self.busy = False
            for widget in (self.page, self.scope, self.actions, self.queue_actions):
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
            self.rows, self.catalogue_errors = result
            if self.timer:
                GLib.source_remove(self.timer)
            self.filter_rows()
            self.show_actions()

        if not force and key in self.catalogues:
            display(self.catalogues[key])
        else:
            self.rows = []
            self.catalogue_errors = []
            self.status.set_tooltip_text(None)
            self.store.clear()
            self.show_actions()
            readers = (backend.debs, lambda: backend.flatpaks(scope), lambda: backend.repos(scope))
            self.job('Cargando catálogo…', readers[page], display)

    def selected_rows(self):
        model, paths = self.view.get_selection().get_selected_rows()
        return [tuple(model[model.get_iter(path)]) for path in paths]

    def selected(self):
        rows = self.selected_rows()
        return rows[0] if rows else None

    def selection_changed(self, _selection):
        self.show_actions()
        self.show_details()

    def cancel_details(self):
        if self.details_timer:
            GLib.source_remove(self.details_timer)
            self.details_timer = 0
        if self.details_request is not None:
            request, self.details_request = self.details_request, None
            request.cancel()

    def show_details(self):
        self.cancel_details()
        page, scope = self.page.get_active(), self.scope.get_active_id()
        row = self.selected()
        self.details.set_visible(page in (0, 1))
        self.details.set_tooltip_text(None)
        self.details_title.set_text(row[0] if row and page in (0, 1)
                                    else self.translate('Detalles del paquete'))
        buffer = self.details_view.get_buffer()
        if not row or page not in (0, 1):
            buffer.set_text(self.translate('Selecciona un paquete para ver su descripción y dependencias.'))
            return
        _, identifier, version, state, origin = row
        buffer.set_text(self.translate('Cargando detalles del paquete…'))

        def finish(request):
            if self.destroyed or request is not self.details_request:
                return GLib.SOURCE_REMOVE
            self.details_request = None
            try:
                metadata = request.result()
            except (RuntimeError, OSError) as exc:
                buffer.set_text(self.translate('No se pudieron consultar los detalles de este paquete.'))
                self.details.set_tooltip_text(str(exc)[-1000:])
            else:
                self.render_details(metadata, row, page)
            return GLib.SOURCE_REMOVE

        def start():
            self.details_timer = 0
            if page == 0:
                task = self.details_pool.submit(backend.deb_details, identifier, version, origin)
            else:
                task = self.details_pool.submit(
                    backend.flatpak_details, scope, origin, identifier, state != 'Disponible')
            self.details_request = task
            task.add_done_callback(lambda request: GLib.idle_add(finish, request))
            return GLib.SOURCE_REMOVE

        self.details_timer = GLib.timeout_add(120, start)

    def render_details(self, metadata, row, page):
        _, identifier, version, _, origin = row
        translate = self.translate
        fields = [
            ('Identificador', identifier),
            ('Versión', metadata.get('Version') or version),
            ('Arquitectura', metadata.get('Architecture') or (origin if page == 0 else '')),
            ('Remoto', origin if page == 1 else ''),
            ('Rama', metadata.get('Branch')),
            ('Dependencias previas', metadata.get('Pre-Depends')),
            ('Dependencias', metadata.get('Depends')),
            ('Paquetes recomendados', metadata.get('Recommends')),
            ('Entorno de ejecución requerido', metadata.get('Runtime')),
            ('Tamaño de descarga', metadata.get('Download Size')),
            ('Tamaño instalado', metadata.get('Installed Size')),
            ('Sección', metadata.get('Section')),
            ('Licencia', metadata.get('License')),
            ('Sitio web', metadata.get('Homepage')),
        ]
        lines = [metadata.get('Description') or translate('Descripción no disponible.'), '']
        lines.extend(f'{translate(label)}: {value}' for label, value in fields if value)
        self.details_view.get_buffer().set_text('\n'.join(lines))
        self.details_view.scroll_to_iter(self.details_view.get_buffer().get_start_iter(),
                                         0, False, 0, 0)

    def show_actions(self):
        for child in self.actions.get_children():
            self.actions.remove(child)
        page, scope = self.page.get_active(), self.scope.get_active_id()
        rows = self.selected_rows()
        row = rows[0] if len(rows) == 1 else None
        if page in (0, 2):
            self.button('Actualizar índices APT', lambda: self.modify(
                'Actualizar los índices de APT', self.admin('refresh')))
        self.button('Recargar', lambda: self.load(force=True))
        if page == 0:
            self.button('Instalar archivo .deb…', self.choose_local_deb)
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
        if page in (0, 1) and rows:
            states = {item[3] for item in rows}
            if 'Disponible' in states:
                self.button(self.translate('Instalar seleccionados'),
                            lambda: self.queue_action('install'))
            if 'Actualizable' in states:
                self.button(self.translate('Actualizar seleccionados'),
                            lambda: self.queue_action('upgrade'))
            if states & {'Instalado', 'Actualizable'}:
                self.button(self.translate('Desinstalar seleccionados'),
                            lambda: self.queue_action('remove'))
        self.actions.show_all()

    def button(self, label, action):
        button = Gtk.Button(label=label)
        button.connect('clicked', lambda *_: action())
        self.actions.add(button)

    def queue_action(self, action):
        if self.busy:
            return
        page, scope = self.page.get_active(), self.scope.get_active_id()
        if page not in (0, 1):
            return
        accepted = {'install': {'Disponible'},
                    'upgrade': {'Actualizable'},
                    'remove': {'Instalado', 'Actualizable'}}[action]
        added = 0
        queued = 0
        for row in self.selected_rows():
            name, identifier, _, state, origin = row
            if state not in accepted:
                continue
            if any(item['identifier'] == identifier for item in self.queue):
                queued += 1
                continue
            if len(self.queue) >= QUEUE_LIMIT:
                self.message(self.translate('La cola está llena'),
                             self.translate('Puedes añadir hasta %d operaciones a la cola.')
                             % QUEUE_LIMIT)
                break
            self.queue.append({'action': action, 'identifier': identifier, 'name': name,
                               'origin': origin, 'page': page, 'scope': scope})
            added += 1
        if added:
            self.status.set_text(self.translate('%d operaciones en cola') % len(self.queue))
        else:
            self.status.set_text(self.translate(
                'Ya están en la cola.' if queued else
                'No hay paquetes compatibles con esa acción en la selección.'))
        self.show_queue()
        self.show_actions()

    def show_queue(self):
        for child in self.queue_list.get_children():
            self.queue_list.remove(child)
        if not self.queue:
            self.queue_frame.hide()
            return
        for index, item in enumerate(self.queue):
            row = Gtk.Box(spacing=8)
            label = Gtk.Label(xalign=0, ellipsize=3, label=(
                f"{self.translate(VERBS[item['action']])} {item['name']}"))
            label.set_tooltip_text(item['identifier'])
            row.pack_start(label, True, True, 0)
            remove = Gtk.Button(label='×')
            remove.set_relief(Gtk.ReliefStyle.NONE)
            remove.set_tooltip_text(self.translate('Quitar de la cola'))
            remove.connect('clicked', lambda *_args, position=index: self.dequeue(position))
            row.pack_end(remove, False, False, 0)
            self.queue_list.add(row)
        self.queue_title.set_text(self.translate('Cola de instalación · %d operaciones')
                                  % len(self.queue))
        self.queue_apply.set_label(self.translate('Aplicar cola (%d)') % len(self.queue))
        self.queue_clear.set_label(self.translate('Vaciar cola'))
        self.queue_frame.set_no_show_all(False)
        self.queue_frame.show_all()
        self.queue_frame.set_no_show_all(True)

    def dequeue(self, position):
        if self.busy or not 0 <= position < len(self.queue):
            return
        del self.queue[position]
        self.show_queue()

    def clear_queue(self):
        if self.busy or not self.queue:
            return
        self.queue.clear()
        self.show_queue()

    def queue_commands(self, items, page, scope):
        commands = []
        if page == 0:
            for action in ('install', 'upgrade', 'remove'):
                identifiers = [item['identifier'] for item in items
                               if item['action'] == action]
                if identifiers:
                    commands.append(self.admin(action, *identifiers))
            return commands
        for action in ('install', 'upgrade', 'remove'):
            group = [item for item in items if item['action'] == action]
            if not group:
                continue
            if action == 'install':
                origins = {}
                for item in group:
                    origins.setdefault(item['origin'], []).append(item['identifier'])
                for origin, references in origins.items():
                    commands.append(backend.flatpak(
                        scope, 'install', '-y', '--', origin, *references))
                continue
            verb = 'update' if action == 'upgrade' else 'uninstall'
            commands.append(backend.flatpak(
                scope, verb, '-y', '--', *[item['identifier'] for item in group]))
        if self.passwordless():
            commands = [self.admin('flatpak-system', *command[2:])
                        if command[:2] == ['/usr/bin/flatpak', '--system'] else command
                        for command in commands]
        return commands

    def apply_queue(self):
        if self.busy or not self.queue:
            return
        page, scope = self.page.get_active(), self.scope.get_active_id()
        items = list(self.queue)

        def simulate():
            if page != 0:
                return ''
            lines = []
            for action in ('install', 'upgrade', 'remove'):
                identifiers = [item['identifier'] for item in items
                               if item['action'] == action]
                if not identifiers:
                    continue
                apt_action = ['install', '--only-upgrade'] if action == 'upgrade' else [action]
                output = backend.run(
                    ['/usr/bin/apt-get', '-s', *apt_action, '--', *identifiers])
                lines.append(f"== {self.translate(VERBS[action])}: "
                             f"{', '.join(identifiers)} ==\n{output.strip()}")
            return '\n\n'.join(lines)

        def confirmed(plan):
            if self.destroyed:
                return
            details = '\n'.join(
                f"{self.translate(VERBS[item['action']])} {item['name']} "
                f"({item['identifier']})" for item in items)
            if plan:
                details += '\n\n' + plan
            if self.message(self.translate('¿Aplicar %d operaciones?') % len(items),
                            details, confirm=True, accept_label=self.translate('Aplicar')):
                self.execute_queue(items, page, scope)

        self.job(self.translate('Comprobando dependencias…'), simulate, confirmed)

    def execute_queue(self, items, page, scope):
        commands = self.queue_commands(items, page, scope)

        def run_all():
            errors = []
            for command in commands:
                try:
                    backend.run(command)
                except (RuntimeError, OSError, ValueError) as exc:
                    errors.append(str(exc))
            return errors

        def finished(errors):
            self.catalogues.clear()
            if errors:
                self.message(self.translate('La cola no se pudo aplicar por completo'),
                             '\n\n'.join(errors))
            else:
                self.queue.clear()
                self.show_queue()
            self.load(force=True)

        self.applying_changes = True
        self.job(self.translate('Aplicando la cola…'), run_all, finished)

    def admin(self, *args):
        if self.passwordless():
            return ['/usr/bin/pkexec', backend.MAINTENANCE, '--software', *args]
        return ['/usr/bin/pkexec', backend.ADMIN, *args]

    def message(self, title, details='', confirm=False, accept_label=None):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True, text=title,
                                   buttons=Gtk.ButtonsType.OK_CANCEL if confirm else Gtk.ButtonsType.CLOSE)
        if accept_label:
            dialog.get_widget_for_response(Gtk.ResponseType.OK).set_label(accept_label)
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

        if command[:2] == ['/usr/bin/flatpak', '--system'] and self.passwordless():
            command = self.admin('flatpak-system', *command[2:])
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

    def choose_local_deb(self):
        dialog = Gtk.FileChooserDialog(title='Seleccionar paquete Debian', transient_for=self.window,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancelar', Gtk.ResponseType.CANCEL, 'Abrir', Gtk.ResponseType.OK)
        packages = Gtk.FileFilter()
        packages.set_name('Paquetes Debian (*.deb)')
        packages.add_pattern('*.[dD][eE][bB]')
        dialog.add_filter(packages)
        filename = dialog.get_filename() if dialog.run() == Gtk.ResponseType.OK else None
        dialog.destroy()
        if filename:
            self.open_local_deb(filename)

    def open_local_deb(self, filename):
        if self.destroyed:
            return GLib.SOURCE_REMOVE
        if self.busy or self.window.sincronizando_reloj:
            return GLib.SOURCE_CONTINUE

        def confirm(result):
            digest, package, trusted, details = result
            if self.passwordless() and not trusted:
                details = "Este archivo requiere autenticación de administrador.\n\n" + details
            if self.message('¿Instalar este paquete Debian?', f'{filename}\n\n{details}',
                            confirm=True, accept_label='Instalar'):
                self.applying_changes = True
                command = (self.admin('install-trusted-local', digest, package) if trusted else
                           ['/usr/bin/pkexec', backend.ADMIN, 'install-local', digest])
                self.job('Instalando el paquete…', lambda: backend.install_local_deb(filename, command),
                         installed)

        def installed(_output):
            self.catalogues.clear()
            self.message('Instalación completada', filename)
            self.load(force=True)

        self.job('Comprobando dependencias…', lambda: backend.preview_local_deb(filename), confirm)
        return GLib.SOURCE_REMOVE

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
