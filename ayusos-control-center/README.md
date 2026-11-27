# ayusos-control-center

Integración independiente de AyusOS Linux en `aio-debian-gui`.

## Contenido

- Onboarding de primer arranque.
- Centro de Control con actualización, snapshots, hardware, diagnósticos y apariencia.
- Modo Recovery con reparación APT/dpkg, GRUB, Timeshift, diagnóstico y terminal.
- Gestor de software APT/Flatpak.
- Pasos privilegiados para AyusOS.
- Servicios de autorización, snapshot y mantenimiento inicial.
- Aplicador de las preferencias elegidas en el onboarding.
- Módulo Calamares `ayusos-aio-setup`.
- Política Polkit y hook APT para Timeshift.
- Fondos de escritorio y tema Plymouth AyusOS.

## Ajustes de 1.4.7

- Runner `aio-run` para submódulos con contexto de paquete, usado por el helper y
  el aplicador de onboarding.
- Timeshift en `/etc/timeshift/timeshift.json`, compatible con cualquier raíz
  Btrfs y con diagnóstico en la misma ruta.
- Configuración de Flathub asegurada aunque Flatpak ya esté instalado.
- Actualización de AyusOS unificada en la pestaña del Centro de Control mediante
  `/usr/lib/ayusos/actualizar-terminal`; sin lanzador redundante.
- Detección de actualizaciones de `ayusos-release` con `apt-cache policy`.
- Fondos y Plymouth incluidos en este paquete, rejilla de fondos visible y
  `grub-btrfsd` incluido localmente en la ISO con sus archivos protegidos durante
  la construcción.
- Ventana de recuperación independiente, apertura automática con
  `ayusos-recovery` y política Polkit específica para las acciones privilegiadas.

## Modo Recovery

La entrada `AyusOS Recovery` de GRUB/ISOLINUX arranca el sistema Live con
`ayusos-recovery`. Un autostart condicionado inicia el Centro de Control; la
extensión detecta el parámetro, omite el onboarding y abre una ventana con:

- Reparar APT/dpkg.
- Regenerar GRUB.
- Ejecutar diagnóstico.
- Listar y restaurar snapshots de Timeshift.
- Abrir una terminal como usuario normal.

También se puede abrir desde **Diagnósticos → Abrir recuperación**. Las acciones
privilegiadas solicitan autorización mediante la política
`es.aiodebian.gui.ayusos.recovery`. La restauración de Timeshift se ejecuta en
modo no interactivo y los servicios automáticos de primer arranque se omiten
cuando está activo `ayusos-recovery`.

## Arquitectura

El core `aio-debian-gui` solo conoce el contrato `Extension`. Este paquete vive en:

```
/usr/lib/aio-debian-gui/extensions/ayusos/
```

El core descubre la extensión automáticamente. No hay parches de AyusOS en el core.

## Construcción

```bash
./build-deb.sh
```

Genera `dist/ayusos-control-center_1.4.7_all.deb`.

La ISO `AyusOS-Linux-1.4-release-final-v4-amd64.iso` fue validada en chroot con
SHA-256 `d24b3443b46ba1ad898c3a1b1f817f1491d547326ba6c20ca07c03606af68b9f`.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

## Primer arranque

1. Calamares escribe el preset en `/etc/ayusos/ayusos.conf`.
2. `ayusos-onboarding.service` lanza el wizard en la sesión gráfica.
3. El wizard guarda preferencias de usuario.
4. `ayusos-aio-inicial.service` ejecuta `ayusos-aplicar-onboarding`.
5. Después se ejecuta el mantenimiento programado.

El onboarding y el mantenimiento inicial se omiten en modo Live para no interrumpir Calamares.
