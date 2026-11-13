# Borrador de solicitud a Snap Store — AiO Debian GUI

> **No enviado.** El propietario debe registrar primero el snap y presentar
> personalmente la solicitud en la categoría `store-requests` de
> https://forum.snapcraft.io/. El confinamiento clásico **no está aprobado**.

## Asunto sugerido

Request for classic confinement: aio-debian-gui (experimental system maintenance GUI)

## Texto para revisión (inglés)

Hello Snap Store reviewers,

I maintain AiO Debian GUI, an open-source GTK3 desktop application for
maintenance of Debian and Ubuntu LTS systems:

- Source: https://github.com/julioayusoalende-hue/AIO-Debian-GUI
- Snapcraft recipe: https://github.com/julioayusoalende-hue/AIO-Debian-GUI/blob/main/snap/snapcraft.yaml
- App ID/name requested: `aio-debian-gui` (subject to name registration)
- License: GPL-3.0-or-later
- Current candidate: 1.2.1, `grade: devel`, `confinement: classic`
- Supported architecture: amd64

The application displays system information and offers optional APT updates,
repository configuration, Flatpak tasks, and distribution-specific kernel
maintenance. The GUI runs as the unprivileged desktop user. Administrative
operations are delegated to a separate host-installed, allowlisted Bash helper
invoked using Polkit authentication. The snap does **not** install that helper
or a Polkit policy on the host. Without a compatible host helper, privileged
maintenance operations are unavailable. The snap is not a replacement for the
existing DEB installation.

Classic confinement is requested because the current architecture requires
access to host OS metadata, package-management tools, and a separately installed
privileged Polkit helper outside the snap. We understand that this alone may
not justify classic confinement. The official review guidance explicitly
discourages using classic simply to enable direct `pkexec` or admin tooling.

Please advise whether this use case is eligible for classic confinement or
whether the project should instead publish a strictly confined read-only GUI,
with privileged maintenance provided exclusively by a separate native DEB.
We are open to redesigning the integration and will not claim approval or
publish a stable snap before the required technical/security review.

Security properties:
1. No passwordless Polkit rule is created.
2. The GUI requires explicit confirmation of selected tasks.
3. The privileged helper checks the distribution again, enforces fixed tasks,
   and rejects unsupported distributions and cross-distribution tasks.
4. The snap does not ship an automatically installed privileged host service.
5. No Snap Store credentials are committed to the repository.
6. An experimental Snap candidate has been built in GitHub Actions. GUI and
   end-to-end privileged operations have **not** yet been verified on real
   Ubuntu 24.04/26.04 desktops.

Please let us know what additional evidence is needed. Thank you.

## Evidencias pendientes antes del envío

- [ ] Confirmar cuenta de desarrollador y registro del nombre `aio-debian-gui`
- [ ] Instalar y abrir el Snap en Ubuntu 24.04 LTS con GNOME (incluido tema e iconos)
- [ ] Repetir prueba de interfaz en Ubuntu 26.04 LTS
- [ ] Verificar que el Snap sin asistente del anfitrión bloquea mantenimiento con un mensaje claro
- [ ] Verificar invocación Polkit con asistente previamente instalado y misma versión
- [ ] Probar cancelación/denegación de Polkit sin cambios en el sistema
- [ ] Probar tareas administrativas en una máquina virtual restaurable, no en producción
- [ ] Revisar bibliotecas Python/GTK, dependencias y ausencia de conflictos ABI
- [ ] Solicitar evaluación de si `classic` es aceptable o si hace falta un frontend `strict`
- [ ] Conservar URL de la revisión de Canonical y su resolución, sea favorable o no

Referencias oficiales:

- https://snapcraft.io/docs/reference/administration/reviewing-classic-confinement-snaps/
- https://snapcraft.io/docs/explanation/security/classic-confinement/
- https://snapcraft.io/docs/registering-your-app-name/
- https://snapcraft.io/docs/releasing-your-app/

**No subir credenciales, contraseñas ni ficheros exportados con `snapcraft export-login`
a Issues, PRs o repositorios públicos.**
