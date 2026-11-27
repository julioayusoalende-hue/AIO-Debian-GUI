# Guía de contribución para AiO Debian GUI

¡Gracias por tu interés en contribuir a AiO Debian GUI! Este documento describe cómo participar en el desarrollo, probar cambios y enviar contribuciones de calidad.

## Índice

1. [Entorno de desarrollo](#entorno-de-desarrollo)
2. [Estructura del proyecto](#estructura-del-proyecto)
3. [Estilo de código](#estilo-de-código)
4. [Pruebas](#pruebas)
5. [Accesibilidad](#accesibilidad)
6. [Envío de cambios](#envío-de-cambios)
7. [Firma GPG](#firma-gpg)
8. [Código de conducta](#código-de-conducta)

---

## Entorno de desarrollo

### Requisitos

- **Python 3.10+**
- **GTK 3** (libgtk-3-dev)
- **PyGObject** (python3-gi, python3-gi-cairo)
- **VTE 2.91** (libvte-2.91-dev, gir1.2-vte-2.91)
- **Git**
- **make** (para los scripts de construcción)

### Configuración rápida

```bash
# Clonar el repositorio
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI

# Instalar dependencias de desarrollo (Debian/Ubuntu)
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-vte-2.91 \
  libgtk-3-dev libvte-2.91-dev

# Ejecutar comprobaciones de estilo y pruebas
./scripts/check.sh
```

### Ejecutar desde el código fuente

```bash
# Desde la raíz del repositorio
python3 package/usr/bin/aio-debian-gui
```

### Entorno virtual (opcional)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt  # si existe
```

---

## Estructura del proyecto

```
AIO-Debian-GUI/
├── package/                    # Contenido que se instala en el sistema
│   ├── usr/bin/aio-debian-gui  # Punto de entrada principal (GUI)
│   ├── usr/lib/aio-debian-gui/
│   │   ├── aio_core/           # Lógica de negocio (backend)
│   │   │   ├── operations.py   # Coordinador de operaciones
│   │   │   ├── scheduler.py    # Programación systemd
│   │   │   ├── diagnostics.py  # Diagnóstico del sistema
│   │   │   ├── updates.py      # Actualizaciones de la app
│   │   │   ├── preferences.py  # Gestión de preferencias
│   │   │   ├── history.py      # Historial de mantenimiento
│   │   │   ├── translations.py # Internacionalización
│   │   │   ├── extensions.py   # Sistema de extensiones
│   │   │   └── ...             # Otros módulos core
│   │   └── ui/                 # Interfaz gráfica (frontend)
│   │       ├── widgets/        # Widgets reutilizables
│   │       └── pages/          # Páginas del notebook
│   └── usr/share/              # Iconos, logos, esquemas Polkit
├── scripts/                    # Scripts de CI, build y pruebas
│   ├── build-deb.sh            # Construye el paquete DEB
│   ├── check.sh                # Lint + tests
│   └── test-*.py / test-*.sh   # Pruebas unitarias y de integración
├── tests/                      # Pruebas unitarias (pytest)
├── docs/                       # Documentación y capturas
│   ├── guia-de-uso.md
│   └── capturas/               # Screenshots para el README
├── ayusos-control-center/      # Extensión específica para AyusOS
├── CHANGELOG.md                # Historial de cambios
├── LICENSE                     # GNU GPL v3+
└── README.md
```

### Módulos clave

| Módulo | Responsabilidad |
|--------|-----------------|
| `aio_core/operations.py` | Coordinación de operaciones privilegiadas (evita solapamiento) |
| `aio_core/scheduler.py` | Programación systemd (timers, unidades, historial) |
| `aio_core/diagnostics.py` | Comprobaciones de salud del sistema |
| `aio_core/updates.py` | Auto-actualización DEB/Flatpak/AppImage |
| `aio_core/preferences.py` | Persistencia de preferencias de usuario |
| `aio_core/history.py` | Registro de ejecuciones (manuales y programadas) |
| `aio_core/extensions.py` | Carga de extensiones por distribución |
| `ui/widgets/task_list.py` | Lista de tareas de mantenimiento con checkboxes |
| `ui/widgets/queue_widget.py` | Cola de ejecución y progreso |

---

## Estilo de código

### Python

- **PEP 8** con línea máxima de 100 caracteres
- **Type hints** en funciones públicas y métodos de clase
- **Docstrings** en estilo Google/NumPy para módulos, clases y funciones públicas
- **Nombres en español** para variables, funciones y comentarios (el proyecto está en español)
- **Imports ordenados**: stdlib → third-party → local

```python
# Ejemplo de estilo
def sincronizar_reloj(comando_host: Callable[[List[str]], subprocess.CompletedProcess]) -> bool:
    """Sincroniza el reloj del sistema usando timedatectl o ntpdate.

    Args:
        comando_host: Función que ejecuta comandos en el anfitrión (Flatpak/AppImage)
                      o directamente (DEB).

    Returns:
        True si la sincronización fue exitosa, False en caso contrario.
    """
    try:
        resultado = comando_host("timedatectl", "set-ntp", "true")
        return resultado.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
```

### GTK / UI

- Usar **Gtk.Box**, **Gtk.Grid**, **Gtk.FlowBox** para layouts responsivos
- Clases CSS con prefijo `aio-` (ej: `.aio-card`, `.aio-task-name`)
- **Accesibilidad obligatoria** en widgets nuevos:
  - `widget.get_accessible().set_name(_("Nombre descriptivo"))`
  - `widget.get_accessible().set_description(_("Descripción extendida"))` si aplica
  - Roles ATK apropiados (`Atk.Role.STATUS` para live regions)
- **Live regions** para anuncios de estado dinámicos (ver sección Accesibilidad)

### CSS

- Variables semánticas: `@success_color`, `@warning_color`, `@error_color`
- Media query `@media (prefers-contrast: more)` para alto contraste
- Focus visible obligatorio: `outline: 2px solid @theme_selected_bg_color`
- Unidades relativas (`em`, `rem`) preferidas sobre `px`

---

## Pruebas

### Ejecutar todas las pruebas

```bash
./scripts/check.sh
```

Este script ejecuta:
1. **Lint** (flake8, mypy si está configurado)
2. **Pruebas unitarias** (pytest en `tests/`)
3. **Pruebas de integración** (scripts `test-*.sh`)

### Pruebas unitarias

```bash
# Todas
python3 -m pytest tests/ -v

# Módulo específico
python3 -m pytest tests/test_operations.py -v

# Con cobertura
python3 -m pytest tests/ --cov=aio_core --cov-report=term-missing
```

### Pruebas de interfaz gráfica

Las pruebas GTK requieren un servidor X virtual o Wayland:

```bash
# Con xvfb (headless)
xvfb-run -a python3 -m pytest tests/test_gui.py -v

# O usando el script de CI
./scripts/test-gtk-versions.py
```

### Añadir nuevas pruebas

- Ubicar en `tests/test_<modulo>.py`
- Usar `pytest` fixtures para configuración común
- Mockear llamadas al sistema (`subprocess`, `os`, `GLib`)
- Probar tanto casos de éxito como de error

---

## Accesibilidad

AiO Debian GUI se compromete a ser **totalmente accesible** para usuarios de lectores de pantalla (Orca, NVDA), navegación por teclado y alto contraste.

### Requisitos obligatorios para código nuevo

#### 1. Nombres y descripciones accesibles

```python
# Botones, switches, combos, entries
widget.get_accessible().set_name(_("Etiqueta visible o propósito"))
widget.get_accessible().set_description(_("Ayuda contextual opcional"))

# Imágenes informativas
imagen.get_accessible().set_name(_("Descripción de la imagen"))
imagen.set_tooltip_text(_("Descripción de la imagen"))
```

#### 2. Live regions para anuncios dinámicos

```python
from aio_core.constants import live_region  # o la función local en aio-debian-gui

# Región educada (polite) para actualizaciones de progreso
self.live_progress = live_region(polite=True, atomic=False)
contenedor.pack_start(self.live_progress, False, False, 0)

# Anunciar cambio de estado
def anunciar(mensaje: str):
    self.live_progress.set_text(mensaje)  # Orca lo leerá automáticamente
```

#### 3. Roles ATK correctos

```python
from gi.repository import Atk

# Barra de estado / anuncios
lbl = Gtk.Label()
lbl.get_accessible().set_role(Atk.Role.STATUS)

# Botón que abre un diálogo
btn.get_accessible().set_role(Atk.Role.PUSH_BUTTON)

# Grupo de controles relacionados
box.get_accessible().set_role(Atk.Role.GROUP)
box.get_accessible().set_name(_("Grupo: Opciones de red"))
```

#### 4. Navegación por teclado

- Todos los controles interactivos deben ser **enfocables** (`can_focus=True`)
- Orden de tabulación lógico (izquierda→derecha, arriba→abajo)
- Atajos de teclado documentados (Ctrl+C/V/A en terminal, Escape para cerrar diálogos)
- Focus visible en CSS:
  ```css
  .aio-page *:focus {
      outline: 2px solid @theme_selected_bg_color;
      outline-offset: 2px;
  }
  ```

#### 5. Alto contraste y escalado

- Probar con `GTK_THEME=HighContrast` o preferencias del sistema
- No usar solo color para transmitir información (añadir iconos/texto)
- Texto escalable: `set_line_wrap(True)`, `set_max_width_chars()`

#### 6. Comprobación manual

```bash
# Ejecutar con lector de pantalla
orca python3 package/usr/bin/aio-debian-gui

# Simular alto contraste
GTK_THEME=HighContrast python3 package/usr/bin/aio-debian-gui

# Verificar navegación por teclado (Tab, Shift+Tab, Enter, Espacio, Flechas)
```

### Lista de verificación (checklist) para PRs

- [ ] Todos los botones, switches, combos, entries tienen `set_name()` y `set_description()` si aplica
- [ ] Imágenes informativas tienen nombre accesible y tooltip
- [ ] Cambios de estado dinámicos usan live regions (`live_region()`)
- [ ] Roles ATK correctos (`STATUS`, `BUTTON`, `CHECK_BOX`, `GROUP`, etc.)
- [ ] Navegación por teclado funcional y orden lógico
- [ ] Focus visible en CSS
- [ ] Probado con Orca y alto contraste
- [ ] No hay información transmitida solo por color

---

## Envío de cambios

### Flujo de trabajo

1. **Fork** el repositorio
2. **Crea una rama** descriptiva: `feature/nueva-funcionalidad`, `fix/correccion-bug`, `a11y/mejora-accesibilidad`
3. **Desarrolla** con commits atómicos y mensajes claros
4. **Ejecuta** `./scripts/check.sh` localmente
5. **Abre un Pull Request** contra `main` (estable) o `testing` (pruebas)

### Convención de commits

```
tipo(ámbito): descripción breve en español

Cuerpo explicativo si el cambio lo requiere (qué y por qué).

Fixes #123
```

**Tipos:** `feat`, `fix`, `a11y`, `docs`, `refactor`, `test`, `chore`, `ci`

**Ejemplos:**

```
feat(mantenimiento): añadir tarea de limpieza de logs de journalctl

a11y(task_list): anunciar cambios de estado en live region

fix(updates): corregir comprobación de versión en Flatpak

docs(guia): actualizar sección de backup de repositorios
```

### Revisión de código

Los mantenedores revisarán:
- Correctness y edge cases
- Accesibilidad (ver checklist)
- Estilo de código y type hints
- Pruebas nuevas o actualizadas
- Documentación actualizada si aplica
- Sin credenciales ni datos sensibles en logs/código

---

## Firma GPG

Todos los commits y tags en el repositorio oficial **deben estar firmados con GPG**.

### Configurar firma GPG

```bash
# 1. Generar o importar tu clave GPG
gpg --full-generate-key
# Tipo: RSA y RSA, 4096 bits, sin expiración (o larga)
# Nombre real y email que coincidan con tu cuenta GitHub

# 2. Obtener el Key ID
gpg --list-secret-keys --keyid-format=long
# Ejemplo: sec   rsa4096/ABC123DEF456 2024-01-01 [SC]
#          Key ID = ABC123DEF456

# 3. Configurar Git
git config --global user.signingkey ABC123DEF456
git config --global commit.gpgsign true
git config --global tag.gpgsign true

# 4. Añadir clave pública a GitHub
gpg --armor --export ABC123DEF456
# Copiar la salida y añadirla en GitHub → Settings → SSH and GPG keys → New GPG key
```

### Firmar commits existentes (rebase)

```bash
# Reescribir los últimos N commits para firmarlos
git rebase --exec 'git commit --amend --no-edit -S' HEAD~3
```

### Verificar firmas

```bash
# Verificar commits firmados en el log
git log --show-signature --oneline -5

# Verificar un tag firmado
git tag -v 1.5.3
```

### Clave del proyecto (verificación de releases)

La clave GPG oficial del proyecto para verificar paquetes DEB y releases:

```
Key ID: 0xXXXXXXXXXXXXXXXX
Fingerprint: XXXX XXXX XXXX XXXX XXXX  XXXX XXXX XXXX XXXX XXXX
UID: Julio Ayuso <julio@ayuso.dev>
```

Para verificar un archivo `SHA256SUMS` firmado:

```bash
gpg --verify SHA256SUMS.sig SHA256SUMS
```

---

## Código de conducta

Este proyecto sigue el **Contributor Covenant v2.1**. Al participar, te comprometes a:

- Ser respetuoso e inclusivo
- Aceptar críticas constructivas
- Enfocarte en lo mejor para la comunidad
- No tolerar acoso, discriminación ni comportamiento tóxico

Consulta el texto completo en: https://www.contributor-covenant.org/version/2/1/code_of_conduct/

---

## Contacto

- **Issues**: https://github.com/julioayusoalende-hue/AIO-Debian-GUI/issues
- **Discusiones**: https://github.com/julioayusoalende-hue/AIO-Debian-GUI/discussions
- **Email**: julio@ayuso.dev

---

*Última actualización: 2026-11-27*