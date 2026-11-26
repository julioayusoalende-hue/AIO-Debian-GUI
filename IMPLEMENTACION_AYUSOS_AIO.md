# Integración AyusOS ↔ aio-debian-gui

## Arquitectura

La integración está separada en dos paquetes independientes:

| Paquete | Responsabilidad |
|---------|-----------------|
| `aio-debian-gui` | Core agnóstico, mantenimiento, software, backup, salud, hook de extensiones |
| `ayusos-control-center` 1.4.6 | Onboarding, branding, pestañas AyusOS, gestor de software, helper privilegiado, servicios, Calamares, aplicador de preferencias, autorización multi-usuario, backup/restauración de identidad, perfil de apps AyusOS y actualización asistida |

Esto permite actualizar aio-debian-gui sin modificar la integración AyusOS.

## Hook de extensiones

El core descubre paquetes en `/usr/lib/aio-debian-gui/extensions/*/` y carga su clase `Extension`.

Una extensión puede:

- Cambiar título/icono/logo (`app_title`, `app_icon`, `header_logo`)
- Añadir páginas al notebook (`install`)
- Proporcionar onboarding (`should_launch_onboarding`, `launch_onboarding`)
- Registrar pasos privilegiados mediante `helper.sh`

El helper core carga `/usr/lib/aio-debian-gui/extensions/*/helper.sh` después de declarar `TITULOS`.
Cada extensión puede añadir entradas a `TITULOS` y hooks a `EXTENSION_STATUS_HOOKS`.

## Runner de submódulos

La extensión AyusOS incluye `/usr/lib/aio-debian-gui/extensions/ayusos/aio-run`.
Este runner ejecuta los módulos de `ayusos.aio_core` con `runpy`, conservando el
contexto de paquete y las rutas del core y de la extensión. El helper y
`ayusos-aplicar-onboarding` lo invocan con `python3 -I`, evitando imports
relativos rotos sin modificar el core.

## Paquete ayusos-control-center

```
ayusos-control-center/
├── package/
│   ├── DEBIAN/{control,postinst,prerm}
│   ├── etc/
│   │   ├── apt/apt.conf.d/80ayusos-timeshift
│   │   ├── calamares/modules/ayusos-aio-setup.conf
│   │   ├── gdm3/conf.d/99-ayusos-onboarding.conf
│   │   ├── xdg/autostart/ayusos-recovery.desktop
│   │   └── systemd/system/
│   │       ├── ayusos-onboarding.service
│   │       ├── ayusos-aio-inicial.service
│   │       ├── ayusos-aio-autorizacion.service
│   │       ├── ayusos-snapshot-inicial.service
│   │       └── grub-btrfsd.service.d/timeshift.conf
│   └── usr/
│       ├── bin/ayusos-onboarding-graphical
│       ├── lib/calamares/modules/ayusos-aio-setup/
│       ├── lib/aio-debian-gui/extensions/ayusos/
│       │   ├── extension.py
│       │   ├── branding.py
│       │   ├── pages.py
│       │   ├── recovery.py
│       │   ├── helper.sh
│       │   ├── aio-run
│       │   ├── ayusos-recovery
│       │   ├── software_manager/
│       │   │   ├── admin.py
│       │   │   ├── backend.py
│       │   │   └── manager.py
│       │   └── aio_core/
│       │       ├── ayusos_config.py
│       │       ├── ayusos_update.py
│       │       ├── ayusos_snapshots.py
│       │       ├── ayusos_branding.py
│       │       ├── ayusos_diagnostics.py
│       │       ├── ayusos_hardware.py
│       │       ├── ayusos_recovery.py
│       │       ├── onboarding.py
│       │       └── ayusos_onboarding_apply.py
│       ├── local/libexec/
│       │   ├── ayusos-aio-inicial
│       │   ├── ayusos-aio-autorizar
│       │   ├── ayusos-aplicar-onboarding
│       │   ├── ayusos-recovery-session
│       │   └── ayusos-timeshift
│       └── share/
│           ├── ayusos-control-center/
│           ├── backgrounds/ayusos/
│           └── plymouth/themes/ayusos/
└── build-deb.sh
```

## Flujo de primer arranque

1. Calamares escribe `/etc/ayusos/ayusos.conf` con el preset elegido.
2. GDM desactiva `gnome-initial-setup`.
3. `ayusos-onboarding.service` detecta la sesión gráfica y lanza `aio-debian-gui --onboarding-only`.
4. El wizard guarda las elecciones en `~/.config/aio-debian-gui/preferences.json`.
5. El launcher marca `/var/lib/ayusos/onboarding-done`.
6. `ayusos-aio-inicial.service` (ordenado después del onboarding) ejecuta `ayusos-aplicar-onboarding`.
7. El aplicador configura repos, Flatpak, kernel, NVIDIA, apps, extensiones, mantenimiento y apariencia.
8. Después se ejecuta el mantenimiento inicial programado.

En modo Live, el onboarding y el mantenimiento inicial se omiten para no interrumpir Calamares.

## Aplicador de onboarding

`ayusos_onboarding_apply.py`:

- Lee preferencias del usuario y fusiona con `SYSTEM_DEFAULTS`.
- Ejecuta pasos del helper con `PKEXEC_UID` correcto.
- Instala solo paquetes APT disponibles del perfil.
- Configura el programador con frecuencia/hora/tareas elegidas.
- Aplica el tema GTK en la sesión del usuario.
- Tolera fallos no críticos y continúa con el resto.

El script de primer arranque usa el marcador `/var/lib/ayusos/onboarding-applied` para ejecutarlo una sola vez.

## Ajustes recientes de 1.4.3

- El helper y el aplicador de onboarding usan `aio-run`, que conserva el contexto
  de paquete al ejecutar submódulos Python.
- Timeshift utiliza `/etc/timeshift/timeshift.json`; el diagnóstico consulta esa
  misma ruta. `ayusos-timeshift` admite cualquier raíz Btrfs, sin exigir el
  subvolumen `/@`.
- `paso_flatpak_setup` asegura el remoto Flathub incluso cuando Flatpak ya está
  instalado.
- Los fondos `/usr/share/backgrounds/ayusos/` y el tema Plymouth AyusOS forman
  parte de `ayusos-control-center`. La rejilla de fondos se refresca con
  `show_all()`.
- `grub-btrfsd` se incluye localmente en la ISO y el build protege su binario,
  servicio, configuración y módulo GRUB frente a la limpieza. No se solicita a
  APT porque Debian 13 no publica ese paquete.
- La pestaña de actualización abre `/usr/lib/ayusos/actualizar-terminal`. Se han
  eliminado el lanzador `ayusos-actualizar.desktop` y su icono, y
  `ayusos-instalar.desktop` ya no está en los favoritos del dock.
- La comprobación de actualizaciones consulta el candidato de `ayusos-release`
  mediante `apt-cache policy`, usando los índices APT locales.

## Modo Recovery

- La ISO añade la entrada `AyusOS Recovery` en GRUB e ISOLINUX. Es un clon de la
  entrada Live normal con el parámetro de kernel `ayusos-recovery` y no cambia
  la entrada predeterminada.
- En el sistema instalado, `GRUB_RECOVERY_TITLE` y
  `GRUB_CMDLINE_LINUX_RECOVERY` añaden la opción equivalente en las entradas de
  recuperación generadas por GRUB.
- Al detectar el parámetro, la extensión abre una ventana independiente de
  recuperación y omite el onboarding. La ventana también se puede abrir desde
  **Diagnósticos → Abrir recuperación**.
- Un autostart de GNOME inicia la aplicación solo cuando existe
  `ayusos-recovery`; los servicios automáticos de onboarding, autorización,
  mantenimiento inicial y snapshot se omiten en ese modo.
- La ventana permite reparar APT/dpkg, regenerar GRUB, ejecutar diagnóstico,
  listar y restaurar snapshots de Timeshift y abrir una terminal de usuario.
- Las acciones privilegiadas usan `ayusos-recovery` con una política Polkit
  específica (`auth_admin`), sin ejecutar la terminal como root.

## Construcción

```bash
./scripts/build-deb.sh
./ayusos-control-center/build-deb.sh
cd AyusOS-Linux
pkexec env AYUSOS_OUTPUT="$PWD/AyusOS-Linux-1.4-release-final-v4-amd64.iso" "$PWD/construir.sh"
```

El build de ISO valida que:

- El core contiene `aio_core/extensions.py`.
- El core no contiene `ayusos_*.py` ni `onboarding.py`.
- La integración contiene `extensions/ayusos/extension.py` y el runner `aio-run`.
- La integración contiene el servicio de onboarding y el modo Recovery.
- Los servicios, `grub-btrfsd`, fondos, Plymouth y lanzadores críticos están instalados.
- El lanzador redundante `ayusos-actualizar.desktop` no está presente.
- GRUB e ISOLINUX contienen `AyusOS Recovery` con el parámetro `ayusos-recovery`.

## Nuevas características (roadmap 1.4.x)

### 1. Autorización multi-usuario (`ayusos-aio-autorizar` mejorado)
- Detecta y autoriza **todos** los usuarios del grupo `sudo`, no solo el primero.
- Nuevo script `ayusos-aio-limpiar-usuario` para revocar acceso al eliminar un usuario.
- Pestaña "Autorización" en el Centro de Control para gestionar usuarios autorizados.

### 2. Perfil de aplicaciones AyusOS
- Filtro "Perfil AyusOS" en la página "Apps recomendadas".
- Pre-selecciona las aplicaciones que forman parte de la instalación estándar de AyusOS.
- Lista mantenida en `Extension.ayusos_apps()` (conjunto de IDs).

### 3. Backup y restauración de identidad (`ayusos_identity.py`)
- Backup de: fuentes APT, llavero GPG, versión, Timeshift, extensiones GNOME, branding.
- Formato ZIP con manifiesto JSON, límite 16 MB.
- CLI para helper privilegiado: `snapshot`, `backup <archivo>`, `restore <archivo> [--dry-run]`.
- Pestaña "Identidad" en el Centro de Control.

### 4. Actualización asistida de AyusOS
- `ayusos_update.perform_update()` implementa: snapshot previo (Timeshift), `apt update`, `apt install --only-upgrade ayusos-release`, migración de config, ejecutar aplicador de onboarding.
- `dry-run` simula con `apt-get -s`.
- Changelog desde `/usr/share/doc/ayusos-release/changelog.Debian.gz`.
- Pestaña "Actualización AyusOS" muestra changelog al detectar nueva versión.

## Estado validado

- 75 tests pytest del core.
- 20 tests de extensión, configuración TOML, aplicador de onboarding y Recovery.
- 4 tests de arranque GRUB/ISOLINUX del modo Recovery.
- Flujos GTK y gestor de software.
- `scripts/check.sh` completo.
- Sistema de archivos de la ISO: paquetes, core limpio, extensión, `aio-run`,
  helper, servicios, Timeshift/Flathub, `grub-btrfsd`, recursos, actualización
  unificada, Recovery, Calamares, Polkit y sintaxis.

ISO validada: `AyusOS-Linux/AyusOS-Linux-1.4-release-final-v4-amd64.iso`.

SHA-256: `d24b3443b46ba1ad898c3a1b1f817f1491d547326ba6c20ca07c03606af68b9f`.

## Verificación en una VM

```bash
dpkg -l | grep -E 'aio-debian-gui|ayusos-control-center'

python3 - <<'PY'
import sys
sys.path.insert(0, '/usr/lib/aio-debian-gui')
from aio_core.extensions import load_extensions
print([e.name for e in load_extensions()])
PY

systemctl status ayusos-onboarding.service --no-pager
systemctl status ayusos-aio-inicial.service --no-pager
journalctl -u ayusos-onboarding.service -b --no-pager
```
