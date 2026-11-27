#!/usr/bin/env python3
"""Flujo GTK de selección múltiple y cola de instalación del gestor de software."""
import sys
import time
from pathlib import Path
from unittest.mock import patch

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

if not Gtk.init_check([])[0]:
    print('Sin pantalla: prueba GTK de la cola omitida (usar xvfb-run).')
    sys.exit(0)

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'ayusos-control-center/package/usr/lib/aio-debian-gui/extensions/ayusos'))
from software_manager import backend
from software_manager.manager import SoftwareManagerPage

window = Gtk.Window()
page = SoftwareManagerPage(window, lambda text: text, lambda: False)
page.store.clear()
for row in (
    ('Uno', 'uno:amd64', '1.0', 'Disponible', 'amd64'),
    ('Dos', 'dos:amd64', '2.0', 'Actualizable', 'amd64'),
    ('Tres', 'tres:amd64', '3.0', 'Instalado', 'amd64'),
):
    page.store.append(row)
selection = page.view.get_selection()
for index in range(3):
    selection.select_path(Gtk.TreePath.new_from_indices([index]))
assert [row[1] for row in page.selected_rows()] == [
    'uno:amd64', 'dos:amd64', 'tres:amd64']

page.queue_action('install')
assert [item['identifier'] for item in page.queue] == ['uno:amd64']
page.queue_action('upgrade')
assert [item['identifier'] for item in page.queue] == ['uno:amd64', 'dos:amd64']
page.queue_action('remove')
assert [item['identifier'] for item in page.queue] == [
    'uno:amd64', 'dos:amd64', 'tres:amd64']
page.queue_action('install')
assert len(page.queue) == 3, 'No se deben duplicar paquetes en la cola'
assert page.queue_frame.get_visible()
labels = [row.get_child().get_children()[0].get_text()
          for row in page.queue_list.get_children()]
assert labels == ['Instalar Uno', 'Actualizar Dos', 'Desinstalar Tres'], labels
page.dequeue(1)
assert [item['identifier'] for item in page.queue] == ['uno:amd64', 'tres:amd64']

# La cola pertenece a la página y al ámbito actuales: al cambiar, se vacía.
with patch.object(page, 'load'):
    page.page.set_active(1)
assert page.queue == [] and not page.queue_frame.get_visible()
with patch.object(page, 'load'):
    page.page.set_active(0)

for index in range(3):
    selection.select_path(Gtk.TreePath.new_from_indices([index]))
page.queue_action('install')
assert [item['identifier'] for item in page.queue] == ['uno:amd64']
captured = {}


def fake_execute(items, current_page, scope):
    captured.update(items=items, page=current_page, scope=scope)


with patch.object(backend, 'run', return_value=''), \
        patch.object(page, 'message', return_value=True), \
        patch.object(page, 'execute_queue', side_effect=fake_execute):
    page.apply_queue()
    limit = time.monotonic() + 3
    while not captured and time.monotonic() < limit:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(.005)
    assert captured, 'No se confirmó la cola'
    assert [item['identifier'] for item in captured['items']] == ['uno:amd64']
    assert captured['page'] == 0 and not page.busy

page.destroy()
window.destroy()
print('✔ Selección múltiple y cola de instalación en GTK')
