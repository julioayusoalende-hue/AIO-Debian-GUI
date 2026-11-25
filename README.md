<div align="center">

<img src="package/usr/share/icons/hicolor/256x256/apps/aio-debian-gui.png" width="112" height="112" alt="Icono de AiO Debian GUI">

# AiO Debian GUI

### Tu sistema al día. El control, en tus manos.

Mantenimiento, diagnóstico y copias de configuración para **Debian y Ubuntu LTS**, desde una interfaz gráfica GTK.

[![Estable](https://img.shields.io/github/v/release/julioayusoalende-hue/AIO-Debian-GUI?label=estable&color=C70036)](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)
[![Formato DEB](https://img.shields.io/badge/formato-DEB-C70036)](#instalación)
[![Licencia](https://img.shields.io/badge/licencia-GPL--3.0-blue)](LICENSE)

**[Descargar estable](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)** · **[Instalar](#instalación)** · **[Guía de uso](docs/guia-de-uso.md)** · **[Ver novedades](CHANGELOG.md)**

</div>

---

## Menos comandos repetidos. Más claridad.

AiO reúne las tareas habituales de administración en una sola aplicación: eliges qué hacer, revisas las comprobaciones y sigues el resultado desde la interfaz. Las operaciones administrativas se autorizan mediante Polkit.

Puedes mantener el sistema, programar tareas, revisar problemas, gestionar aplicaciones y guardar la configuración de tus repositorios o de tu escritorio.

## Capturas de pantalla

![Configuración y mantenimiento de AiO Debian GUI 1.1.0](docs/capturas/mantenimiento.png)

<details>
<summary><strong>Inicio, Backup, Apps recomendadas y Terminal</strong></summary>

| Inicio de GRUB | Ajustes de GRUB cargados |
| --- | --- |
| ![Configuración de GRUB antes de cargar los ajustes](docs/capturas/grub-antes-de-cargar.png) | ![Configuración de GRUB con los ajustes cargados](docs/capturas/grub-ajustes-cargados.png) |
| **Backup** | **Apps recomendadas** |
| ![Opciones para copiar y restaurar repositorios y ajustes](docs/capturas/backup.png) | ![Catálogo de aplicaciones con opciones DEB y Flatpak](docs/capturas/apps-recomendadas.png) |

![Terminal integrada con el menú Comandos abierto](docs/capturas/terminal.png)

</details>

<details>
<summary><strong>Diagnóstico, novedades y preferencias</strong></summary>

| Diagnóstico preventivo | Detalles técnicos |
| --- | --- |
| ![Resultados del diagnóstico preventivo del sistema](docs/capturas/diagnostico.png) | ![Información de la distribución, el hardware y el escritorio](docs/capturas/detalles-tecnicos.png) |
| **Novedades de la versión** | **Preferencias** |
| ![Ventana de novedades de AiO Debian GUI 1.1.0](docs/capturas/novedades.png) | ![Preferencias de idioma, apariencia e interfaz simple](docs/capturas/preferencias.png) |
| **Programación** | **Acerca de** |
| ![Configuración del mantenimiento automático y última ejecución](docs/capturas/programacion.png) | ![Versión y licencia de AiO Debian GUI](docs/capturas/acerca-de.png) |

</details>

## Qué puedes hacer

| Área | Funciones |
|---|---|
| **Mantenimiento** | Actualizar APT, limpiar caché y retirar dependencias innecesarias. Revisar la simulación de APT antes de continuar cuando requiere confirmación. |
| **Limpieza segura** | Apartado independiente para limpiar caché APT, papelera, miniaturas antiguas, registros de systemd, Flatpak sin uso y revisiones antiguas de Snap. |
| **Diagnóstico** | Consultar espacio, estado de APT/dpkg, actualizaciones, DKMS, servicios y necesidad de reinicio. Desde **Salud del sistema** puedes actualizar solo AiO sin ejecutar el mantenimiento completo. |
| **Programación** | Ejecutar mantenimiento diario, semanal o mensual mediante systemd y consultar próximas ejecuciones y resultados, incluso con AiO cerrado. |
| **Backup** | Copiar y restaurar repositorios APT y ajustes de GNOME o KDE Plasma. Acceder a Timeshift y Respaldos (Déjà Dup), con instalación opcional. |
| **Kernel y hardware** | Gestionar Backports de kernel/Mesa en Debian, volver a Stable y comprobar la instalación NVIDIA. Las tareas disponibles dependen de la distribución y la compatibilidad. |
| **Aplicaciones** | Instalar aplicaciones recomendadas en los formatos disponibles para cada una. En GNOME, instalar extensiones recomendadas desde una lista blanca. Actualizar Flatpak y, si está instalado, Snap. |
| **Terminal** | Usar Bash, consultar la salida de mantenimiento, copiar y pegar, y aplicar o restaurar el diseño incluido de Fastfetch. |
| **Preferencias** | Elegir español, inglés, francés o chino, apariencia clara u oscura y una interfaz simple. |

### Lo nuevo en la 1.4.4

- Se corrige el error D-Bus `NoReply: Message recipient disconnected from message bus without replying` al instalar extensiones de GNOME: la llamada ahora se dirige directamente a `org.gnome.Shell`, que espera la confirmación del usuario sin cortar la conexión.

[Consultar el historial completo →](CHANGELOG.md)

## Descargas

### Versión estable

**Recomendada para el uso habitual.** La última estable publicada es **1.4.4**, disponible como paquete **DEB**, junto con `SHA256SUMS`.

**[Descargar la última estable →](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest)**

La serie actual se distribuye exclusivamente como DEB. El soporte para gestionar aplicaciones Flatpak, Snap o AppImage no significa que AiO se distribuya en esos formatos.

### Versiones testing

Las pruebas se publican por separado como preversiones de la rama [`testing`](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/tree/testing). Incluyen los cambios en desarrollo y pueden contener errores.

**[Consultar las publicaciones testing →](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases?q=testing&expanded=true)**

En el paquete DEB, selecciona **Testing** en **Preferencias → Canal de actualizaciones** y usa **Buscar actualizaciones** para consultar el repositorio firmado de pruebas. También puedes descargar las preversiones desde GitHub. Si vuelves a **Estable**, AiO esperará a una versión estable más reciente que la instalada.

## Instalación

Compatible con **Debian 12 o superior** y **Ubuntu 24.04/26.04 LTS**. Necesita una sesión gráfica; la programación utiliza systemd. Algunas tareas son específicas de cada distribución.

### 1. Descarga el DEB

Abre la [última release estable](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest) y descarga el archivo `.deb`. Abre un terminal en la carpeta donde lo guardaste.

### 2. Instala el paquete

Para la versión 1.4.3:

```bash
sudo apt install ./aio-debian-gui_1.4.3_all.deb
```

APT instala las dependencias y el paquete configura el repositorio firmado del proyecto para futuras actualizaciones.

### 3. Abre AiO

Búscalo en el menú de aplicaciones o ejecuta, como tu usuario habitual:

```bash
aio-debian-gui
```

Las tareas que lo necesitan solicitan autorización administrativa desde la aplicación.

<details>
<summary><strong>Comprobar la integridad de la descarga</strong></summary>

Descarga `SHA256SUMS` de la misma release y colócalo junto al DEB. Desde esa carpeta:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

Comprueba que el archivo descargado aparece con resultado correcto antes de instalarlo.

</details>

## Actualizaciones

Usa **Menú → Buscar actualizaciones**, tu gestor de paquetes o estos comandos para actualizar únicamente AiO:

```bash
sudo apt update
sudo apt install --only-upgrade aio-debian-gui
```

Cierra y vuelve a abrir la aplicación para cargar la versión nueva. El paquete utiliza la época Debian `1:` para permitir la actualización desde la numeración anterior; no necesitas añadirla al nombre del archivo descargado.

## Antes de empezar

- **Revisa la selección y las advertencias.** Los cambios de kernel, Mesa, repositorios o controladores merecen una copia de seguridad previa.
- **La programación tiene límites.** No programa eliminaciones ni cambios de kernel, controladores o repositorios; no enciende un equipo apagado ni reinicia automáticamente.
- **NVIDIA se instala solo cuando se puede verificar la compatibilidad.** La comprobación del módulo DKMS no sustituye la prueba de funcionamiento después de reiniciar. Secure Boot activo o desconocido requiere preparación manual de la firma DKMS/MOK.
- **La autorización sin contraseña es opcional.** Está desactivada inicialmente y reduce la protección de la cuenta si se habilita.

El diagnóstico puede pedir autorización para renovar los índices APT. Si se cancela o falla esa actualización, lo indica y no presenta las lecturas como actualizadas.

## Guías

| Necesitas… | Consulta |
|---|---|
| Guardar y restaurar fuentes y claves APT | [Copias de repositorios](docs/guia-de-uso.md#copiar-y-restaurar-repositorios-apt) |
| Conservar ajustes, extensiones, paneles y widgets | [Copias de GNOME y KDE Plasma](docs/guia-de-uso.md#copiar-y-restaurar-ajustes-del-escritorio) |
| Entender horarios y permisos | [Programación y permisos](docs/guia-de-uso.md#programación-y-permisos) |
| Saber qué limpia la tarea de Snap | [Mantenimiento de Snap](docs/guia-de-uso.md#mantenimiento-de-snap) |

## Desarrollo y colaboración

```bash
git clone https://github.com/julioayusoalende-hue/AIO-Debian-GUI.git
cd AIO-Debian-GUI
./scripts/check.sh
```

Las comprobaciones gráficas requieren PyGObject, GTK 3, VTE y una pantalla disponible o virtual. El entorno de CI está definido en los [workflows](.github/workflows).

- [Comunicar un problema](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/issues): incluye versión de AiO, distribución, escritorio y pasos para reproducirlo. Retira credenciales de los registros antes de compartirlos.
- [Consultar el código de testing](https://github.com/julioayusoalende-hue/AIO-Debian-GUI/tree/testing).
- [Historial de cambios](CHANGELOG.md).

<details>
<summary><strong>Cómo se numeran las versiones testing</strong></summary>

Cada cambio en `testing` que supera las comprobaciones publica una preversión sin modificar `main` ni el repositorio APT estable. Parte de la siguiente versión respecto a la última estable: por ejemplo, tras `1.1.1`, `1.1.3~testing.N.INTENTO`.

El contador se aplica al paquete construido. Debian considera esa preversión anterior a `1.1.3`. La publicación estable se realiza por separado, sin arrastrar el contador.

</details>

---

Desarrollado por **Julio Ayuso** · [GNU GPL v3 o posterior](LICENSE) · Sin garantía.

Proyecto independiente del script de consola [aio-debian](https://github.com/julioayusoalende-hue/aio-debian).
