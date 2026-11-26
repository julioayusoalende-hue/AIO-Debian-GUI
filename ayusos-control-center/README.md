# ayusos-control-center

Integración independiente de AyusOS Linux en `aio-debian-gui`.

## Contenido

- Onboarding de primer arranque.
- Centro de Control con actualización, snapshots, hardware, diagnósticos y apariencia.
- Gestor de software APT/Flatpak.
- Pasos privilegiados para AyusOS.
- Servicios de autorización, snapshot y mantenimiento inicial.
- Aplicador de las preferencias elegidas en el onboarding.
- Módulo Calamares `ayusos-aio-setup`.
- Política Polkit y hook APT para Timeshift.

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

Genera `dist/ayusos-control-center_1.4.3_all.deb`.

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
