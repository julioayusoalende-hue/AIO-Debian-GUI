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

## Publicación futura

1. Verificar el prototipo en Ubuntu 24.04 y 26.04 LTS con la interfaz y el asistente.
2. Solicitar revisión de la arquitectura a Canonical; es posible que haya que rediseñar
   la integración privilegiada y distribuirla fuera de Snap.
3. Registrar el nombre en Snap Store desde la cuenta del propietario y solicitar, si procede,
   autorización para `classic`.
4. Solo después de la aprobación y las pruebas, preparar una publicación en el canal adecuado.

**La versión DEB sigue siendo la recomendada para mantenimiento completo del sistema.**
