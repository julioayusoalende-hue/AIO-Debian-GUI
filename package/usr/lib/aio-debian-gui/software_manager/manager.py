#!/usr/bin/env python3
"""Enhanced Software Manager with caching, filters, and drag & drop."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gtk, Gdk

from . import backend
from . import admin

PAGES = ('DEB', 'Flatpak', 'Repositorios')
VERBS = {'install': 'Instalar', 'upgrade': 'Actualizar', 'remove': 'Desinstalar'}
QUEUE_LIMIT = 100


class EnhancedSoftwareManagerPage(Gtk.Box):
    """Software Manager mejorado con caché, filtros avanzados y drag & drop."""

    def __init__(self, window, translate=lambda text: text, passwordless=lambda: False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
        self.window = window
        self.translate = translate
        self.passwordless = passwordless

        # Estado
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
        self.catalogue_extra = {}
        self.loaded = False
        self.destroyed = False
        self.connect('destroy', self.on_destroy)

        # Filtros
        self.current_section_filter = "Todas"
        self.search_index = backend.search_index

        # UI
        self._build_ui()

        # Configurar drag & drop
        self._setup_drag_drop()

    def _build_ui(self):
        # Toolbar principal
        toolbar = Gtk.Box(spacing=8)
        self.pack_start(toolbar, False, False, 0)

        # Selector de página
        self.page_combo = Gtk.ComboBoxText()
        for name in PAGES:
            self.page_combo.append_text(name)
        self.page_combo.set_active(0)
        self.page = self.page_combo
        toolbar.pack_start(self.page_combo, False, False, 0)

        # Scope (usuario/sistema) para Flatpak
        self.scope_combo = Gtk.ComboBoxText()
        self.scope_combo.append('user', 'Usuario')
        self.scope_combo.append('system', 'Sistema')
        self.scope_combo.set_active_id('user')
        toolbar.pack_end(self.scope_combo, False, False, 0)

        # Búsqueda
        self.search_entry = Gtk.SearchEntry(placeholder_text='Buscar por nombre, descripción, sección…')
        self.search_entry.set_max_length(200)
        toolbar.pack_start(self.search_entry, True, True, 0)
        self.completions = Gtk.ListStore(str)
        completion = Gtk.EntryCompletion(model=self.completions, text_column=0,
                                         minimum_key_length=2)
        completion.set_match_func(lambda *_: True)
        self.search_entry.set_completion(completion)

        # Filtros básicos
        self.filters_combo = Gtk.ComboBoxText()
        for name in ('Todos', 'Instalados', 'Disponibles', 'Actualizables'):
            self.filters_combo.append_text(self.translate(name))
        self.filters_combo.set_active(0)
        toolbar.pack_end(self.filters_combo, False, False, 0)

        # Filtro de sección (solo DEB)
        self.section_combo = Gtk.ComboBoxText()
        self.section_combo.append_text(self.translate("Todas las secciones"))
        for section in sorted(backend.DEB_SECTIONS):
            self.section_combo.append_text(section.capitalize())
        self.section_combo.set_active(0)
        self.section_combo.set_visible(False)  # Solo visible en página DEB
        toolbar.pack_end(self.section_combo, False, False, 0)

        # TreeView
        self.store = Gtk.ListStore(str, str, str, str, str)
        self.view = Gtk.TreeView(model=self.store, enable_search=False)
        self.columns = []
        for index in range(6):
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

        # Ocultar columna de sección por defecto
        self.columns[5].set_visible(False)

        scroller = Gtk.ScrolledWindow(shadow_type=Gtk.ShadowType.IN)
        scroller.add(self.view)
        self.pack_start(scroller, True, True, 0)

        # Detalles
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

        # Acciones
        self.actions = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                   column_spacing=6, row_spacing=4, max_children_per_line=8)
        self.pack_start(self.actions, False, False, 0)

        # Cola
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

        # Status
        self.status = Gtk.Label(xalign=0, ellipsize=3)
        self.pack_end(self.status, False, False, 0)

        # Conexiones
        self.page_combo.connect('changed', self.change_page)
        self.scope_combo.connect('changed', self.change_page)
        self.search_entry.connect('changed', self.queue_filter)
        self.filters_combo.connect('changed', self.queue_filter)
        self.section_combo.connect('changed', self.queue_filter)
        selection = self.view.get_selection()
        selection.set_mode(Gtk.SelectionMode.MULTIPLE)
        selection.connect('changed', self.selection_changed)
        self.scope_combo.set_no_show_all(True)
        self.connect('map', self.on_map)

    def _setup_drag_drop(self):
        """Configura drag & drop para archivos .deb."""
        targets = [
            Gtk.TargetEntry.new('text/uri-list', 0, 0),
            Gtk.TargetEntry.new('application/x-deb', 0, 1),
        ]
        self.drag_dest_set(Gtk.DestDefaults.ALL, targets, Gdk.DragAction.COPY)
        self.connect('drag-data-received', self._on_drag_data_received)

    def _on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        """Maneja archivos .deb soltados."""
        uris = data.get_uris()
        if not uris:
            return

        for uri in uris:
            if uri.startswith('file://'):
                filepath = uri[7:]  # Quitar 'file://'
                if filepath.lower().endswith('.deb'):
                    GLib.idle_add(self._handle_dropped_deb, filepath)

        drag_context.finish(True, False, time)

    def _handle_dropped_deb(self, filepath):
        """Procesa un archivo .deb soltado."""
        if self.busy:
            return

        self.status.set_text(self.translate("Analizando paquete .deb..."))

        def worker():
            try:
                info = backend.analyze_deb_file(filepath)
                GLib.idle_add(self._show_deb_install_dialog, info)
            except Exception as exc:
                GLib.idle_add(self._show_error, self.translate("Error analizando .deb"), str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _show_deb_install_dialog(self, info: backend.DebFileInfo):
        """Muestra diálogo de confirmación para instalar .deb."""
        details = f"{info.package} {info.version} ({info.architecture})\n\n"
        details += f"{self.translate('Descripción')}: {info.description}\n\n"
        details += f"{self.translate('Dependencias')}: {info.depends or 'Ninguna'}\n"
        if info.pre_depends:
            details += f"{self.translate('Pre-dependencias')}: {info.pre_depends}\n"
        details += f"\n{self.translate('Plan de instalación')}:\n{info.install_plan}"

        if info.trusted:
            details = self.translate("✓ Paquete verificado en repositorios APT\n\n") + details
        else:
            details = self.translate("⚠ Paquete NO verificado - requiere autenticación\n\n") + details

        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   buttons=Gtk.ButtonsType.OK_CANCEL,
                                   text=self.translate("Instalar paquete .deb"))
        dialog.format_secondary_text(details)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)

        if dialog.run() == Gtk.ResponseType.OK:
            self._install_local_deb(info)
        dialog.destroy()

    def _install_local_deb(self, info: backend.DebFileInfo):
        """Instala un paquete .deb local."""
        if info.trusted and self.passwordless():
            command = self.admin('install-trusted-local', info.sha256, info.package)
        else:
            command = ['/usr/bin/pkexec', admin.ADMIN, 'install-local', info.sha256]

        self.applying_changes = True
        self.status.set_text(self.translate("Instalando..."))

        def worker():
            try:
                backend.install_local_deb(info.path, command)
                GLib.idle_add(self._on_install_done, True, info.package)
            except Exception as exc:
                GLib.idle_add(self._on_install_done, False, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _on_install_done(self, success, msg):
        self.applying_changes = False
        if success:
            self.status.set_text(self.translate("✓ %s instalado") % msg)
            self.load(force=True)
        else:
            self._show_error(self.translate("Error instalando"), msg)

    def _show_error(self, title, details):
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True,
                                   message_type=Gtk.MessageType.ERROR,
                                   buttons=Gtk.ButtonsType.CLOSE,
                                   text=title)
        dialog.format_secondary_text(details)
        dialog.run()
        dialog.destroy()

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
        query = self.search_entry.get_text().strip().casefold()
        wanted = self.filters_combo.get_active()
        packages = self.page_combo.get_active() != 2
        section_filter = self.section_combo.get_active_text() if self.section_combo.get_visible() else "Todas"

        self.store.clear()
        self.completions.clear()
        suggestions = set()
        prefixes, matches = [], []

        for row in self.rows:
            # Filtro por estado
            if packages and wanted and row[3] not in (
                (), ('Instalado', 'Actualizable'), ('Disponible',), ('Actualizable',)
            )[wanted]:
                continue

            # Filtro por sección (DEB)
            if packages and self.page_combo.get_active() == 0 and section_filter != "Todas":
                row_section = row[5] if len(row) > 5 else ''
                if row_section.lower() != section_filter.lower():
                    continue

            # Filtro por búsqueda
            fields = (row[0].casefold(), row[1].casefold(),
                      self.catalogue_extra.get(row[0] or row[1], '').casefold())
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
            visible = f'{self.translate("Mostrando")} {len(self.store):,} {self.translate("de")} ' if total > len(self.store) else ''
            text = f'{visible}{total:,} {self.translate("resultados")}'
            if self.catalogue_errors:
                text += ' · ' + (self.translate('No se pudieron consultar todos los remotos (%d)')
                                 % len(self.catalogue_errors))
            elif packages and wanted == 3 and not query and not total:
                text = self.translate('No hay actualizaciones disponibles.')
            self.status.set_text(text)
            self.status.set_tooltip_text('\n'.join(self.catalogue_errors) or None)

        return False

    def change_page(self, *_):
        page = self.page_combo.get_active()
        scope = self.scope_combo.get_active_id() if page else None

        if self.queue and any((item['page'], item['scope']) != (page, scope)
                              for item in self.queue):
            self.clear_queue()

        self.scope_combo.set_visible(page != 0)
        self.filters_combo.set_visible(page in (0, 1))
        self.section_combo.set_visible(page == 0)  # Solo DEB
        self.search_entry.set_text('')
        self.search_entry.set_placeholder_text(
            self.translate('Buscar repositorios…') if page == 2 else self.translate('Buscar por nombre, descripción, sección…'))

        names = ('Nombre', 'Identificador', 'Versión', 'Estado', 'Arquitectura' if page == 0 else 'Remoto', 'Sección') if page != 2 else (
            'Nombre', 'URL', 'Tipo', 'Estado', 'Origen o archivo', '')
        for column, title in zip(self.columns, names):
            column.set_title(title)
            column.set_visible(bool(title))

        self.load()
        self.show_details()

    def load(self, force=False):
        page, scope = self.page_combo.get_active(), self.scope_combo.get_active_id()
        key = (page, scope if page else None)

        def display(result):
            self.catalogues[key] = result
            self.rows, self.catalogue_errors = result[:2]
            self.catalogue_extra = result[2] if len(result) > 2 else {}

            # Construir índice de búsqueda
            if page == 0:
                self.search_index.build(self.rows, self.catalogue_extra)

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

            # Usar caché
            cached = backend.catalogue_manager.get_cached(page, scope)
            if cached and not force:
                display(cached)
            else:
                backend.catalogue_manager.load_async(page, scope, display)

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
        page, scope = self.page_combo.get_active(), self.scope_combo.get_active_id()
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
                task = self.details_pool.submit(
                    backend.deb_details, identifier, version, origin, state == 'Actualizable')
            else:
                task = self.details_pool.submit(
                    backend.flatpak_details, scope, origin, identifier, state != 'Disponible',
                    self.catalogue_extra.get((origin, identifier)))
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
            ('Versión disponible', metadata.get('Versión disponible')),
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
        page = self.page_combo.get_active()
        scope = self.scope_combo.get_active_id() if page else None
        rows = self.selected_rows()
        row = rows[0] if len(rows) == 1 else None

        if page in (0, 2):
            self.button(self.translate('Actualizar índices APT'), lambda: self.modify(
                self.translate('Actualizar los índices de APT'), self.admin('refresh')))

        self.button(self.translate('Recargar'), lambda: self.load(force=True))

        if page == 0:
            self.button(self.translate('Instalar archivo .deb…'), self.choose_local_deb)

        if page == 2:
            self.button(self.translate('Añadir repositorio APT…'), self.add_apt)
            self.button(self.translate('Añadir remoto Flatpak…'), self.add_remote)
            if row and row[2] == 'Flatpak':
                toggle = self.translate('Desactivar') if row[3] == 'Activo' else self.translate('Activar')
                command = 'disable' if row[3] == 'Activo' else 'enable'
                self.button(toggle, lambda: self.modify(f'{toggle} {row[0]}',
                    backend.flatpak(scope, 'remote-modify', f'--{command}', '--', row[4])))
                self.button(self.translate('Quitar'), lambda: self.modify(f'{self.translate("Quitar el remoto")} {row[0]}',
                    backend.flatpak(scope, 'remote-delete', '--', row[4])))
            elif row:
                toggle = self.translate('Restaurar archivo') if row[4].endswith('.disabled') else self.translate('Pausar archivo')
                command = 'enable' if row[4].endswith('.disabled') else 'disable'
                self.button(toggle, lambda: self.modify(toggle, self.admin(command, row[4]),
                    f'{self.translate("Se aplica a todas las entradas de")} {row[4]}.'))
                if row[2] == 'APT • gestionado':
                    self.button(self.translate('Quitar'), lambda: self.modify(f'{self.translate("Quitar el repositorio")} {row[0]}',
                        self.admin('delete', row[4])))
        elif page == 1:
            pass  # "Actualizar todo" manejado abajo

        if row and page in (0, 1):
            if row[3] == 'Disponible':
                self.button(self.translate('Instalar'), lambda: self.package_action(page, scope, row, 'install'))
            else:
                if row[3] == 'Actualizable' or page == 1:
                    self.button(self.translate('Actualizar'), lambda: self.package_action(page, scope, row, 'upgrade'))
                self.button(self.translate('Desinstalar'), lambda: self.package_action(page, scope, row, 'remove'))

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

        if page in (0, 1):
            all_rows = self.catalogues.get((page, scope if page else None), ([], []))[0]
            if any(row[3] == 'Actualizable' for row in all_rows):
                self.suggested_button(self.translate('Actualizar todo'),
                                      lambda: self.queue_all_upgrades(all_rows, page, scope))

        self.actions.show_all()

    def button(self, label, action):
        button = Gtk.Button(label=label)
        button.connect('clicked', lambda *_: action())
        self.actions.add(button)

    def suggested_button(self, label, action):
        button = Gtk.Button(label=label)
        button.get_style_context().add_class('suggested-action')
        button.connect('clicked', lambda *_: action())
        self.actions.add(button)

    def queue_action(self, action):
        if self.busy:
            return
        page, scope = self.page_combo.get_active(), self.scope_combo.get_active_id()
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

    def queue_all_upgrades(self, all_rows, page, scope):
        if self.busy:
            return
        upgrades = [row for row in all_rows if row[3] == 'Actualizable']
        if not upgrades:
            self.status.set_text(self.translate('No hay actualizaciones disponibles.'))
            return
        if len(upgrades) > QUEUE_LIMIT:
            self.message(self.translate('Demasiadas actualizaciones'),
                         self.translate('Hay %d actualizaciones; el límite de la cola es %d.')
                         % (len(upgrades), QUEUE_LIMIT))
            return
        for row in upgrades:
            name, identifier, _, _, origin = row
            self.queue.append({'action': 'upgrade', 'identifier': identifier, 'name': name,
                               'origin': origin, 'page': page, 'scope': scope})
        self.status.set_text(self.translate('%d actualizaciones en cola') % len(upgrades))
        self.show_queue()
        self.show_actions()
        self.apply_queue()

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
        page, scope = self.page_combo.get_active(), self.scope_combo.get_active_id()
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
        if self.busy or getattr(self.window, 'sincronizando_reloj', False):
            return GLib.SOURCE_CONTINUE

        def confirm(result):
            digest, package, trusted, details = result
            if self.passwordless() and not trusted:
                details = "Este archivo requiere autenticación de administrador.\n\n" + details
            if self.message('¿Instalar este paquete Debian?', f'{filename}\n\n{details}',
                            confirm=True, accept_label='Instalar'):
                self.applying_changes = True
                command = (self.admin('install-trusted-local', digest, package) if trusted else
                           ['/usr/bin/pkexec', admin.ADMIN, 'install-local', digest])
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
            scope = self.scope_combo.get_active_id()
            self.modify(f'Añadir {name}', backend.flatpak(
                scope, 'remote-add', '--if-not-exists', '--', name, url), url)

    def job(self, message, task, completed):
        self.busy = True
        for widget in (self.page_combo, self.scope_combo, self.actions, self.queue_actions):
            widget.set_sensitive(False)
        self.status.set_text(message)
        future = self.pool.submit(task)

        def finish():
            if self.destroyed:
                return False
            self.applying_changes = False
            self.busy = False
            for widget in (self.page_combo, self.scope_combo, self.actions, self.queue_actions):
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


# Para compatibilidad, re-exportar el original
SoftwareManagerPage = EnhancedSoftwareManagerPage