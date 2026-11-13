# Snap experimental de AiO Debian GUI

**Estado:** prototipo de desarrollo, **no publicado en Snap Store**. Este paquete no es una alternativa completamente independiente a la edición DEB.

## Motivo del confinamiento

AiO Debian GUI modifica APT, repositorios y kernel mediante un asistente Polkit **instalado en el anfitrión**.
Snap Store requiere revisión previa y aprobación para publicar snaps con `confinement: classic`.
La política oficial menciona los **snaps de administración del sistema** y el uso directo de `pkexec`
entre los casos que no justifican normalmente este tipo de confinamiento. Por tanto, **no
se puede garantizar su publicación**, y el proyecto no subirá automáticamente ninguna
revisión a Snap Store ni almacenará credenciales del editor en GitHub.

Referencias oficiales:
- https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/
- https://ubuntu.com/docs/snapcraft/latest/how-to/publishing/publish-a-snap/

## Construcción

En Ubuntu 24.04, con Snapcraft y un proveedor de compilación configurados:

```bash
snapcraft pack
sudo snap install ./aio-debian-gui_1.2.1_amd64.snap --dangerous --classic
```

El workflow `build-snap.yml` también genera un artefacto experimental. La ruta exacta puede
variar según la versión de Snapcraft.

## Requisitos de ejecución y riesgos

- La interfaz usa Python 3 y GTK 3 incluidos en el paquete; **se requiere probarla en un escritorio Ubuntu real**.
- El snap **no instala automáticamente** el asistente privilegiado ni políticas en `/usr` o `/etc`.
  Para tareas administrativas se necesita un asistente `aio-debian-gui-helper` versión 1.2.1 instalado
  previamente por el administrador en `/usr/lib/aio-debian-gui/` junto a su política Polkit válida.
- Si ese asistente no está disponible, la interfaz puede abrirse para consultar el sistema,
  pero no ejecutará el mantenimiento.
- Las actualizaciones de los snaps las gestiona `snapd`; el botón de actualización interna
  se oculta en esta edición.
- Nunca se debe instalar el snap experimental con `--devmode` para intentar saltarse estas limitaciones.

## Preparación de revisión en Snap Store

He incluido un [borrador técnico para la solicitud a Canonical](snap-store-review-request.md)
que detalla las necesidades de privilegios, sus limitaciones y las pruebas pendientes.
No se ha enviado ni aprobado ninguna solicitud.

La revisión oficial [desaconseja solicitar classic únicamente por acceso directo a
`pkexec`](https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/).
Por ello, si Canonical no aprueba esta arquitectura, la alternativa será una interfaz
Snap con confinamiento estricto y mantenimiento administrativo mediante el DEB nativo.

Para comprobar una instalación experimental sin cambiar repositorios ni invocar Polkit:

```bash
python3 scripts/smoke-snap-installed.py
```

Este script es un chequeo básico de recursos; **no prueba la interfaz gráfica ni
la ejecución de tareas administrativas**.

## Publicación futura

1. Verificar el prototipo en Ubuntu 24.04 y 26.04 LTS con la interfaz y el asistente.
2. Solicitar revisión de la arquitectura a Canonical; es posible que haya que rediseñar
   la integración privilegiada y distribuirla fuera de Snap.
3. Registrar el nombre en Snap Store desde la cuenta del propietario y solicitar, si procede,
   autorización para `classic`.
4. Solo después de la aprobación y las pruebas, preparar una publicación en el canal adecuado.

**La versión DEB sigue siendo la recomendada para mantenimiento completo del sistema.**
