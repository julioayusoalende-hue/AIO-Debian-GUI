# Auditoría técnica: base de 2.6.0

## Alcance y comprobaciones
- Revisión estática de flujo de preflight, simulación APT y estado ocupado GTK.
- Revisión de límites de privilegios del helper y autorización Polkit.
- Revisión de instantáneas opcionales: Btrfs y configuración Snapper root.
- Comprobación de empaquetado DEB/AppImage/Flatpak mediante CI.

## Riesgos identificados y correcciones propuestas
- La vista previa APT debe destacar explícitamente cambios en kernel, Mesa y NVIDIA (incluido en esta rama).
- El panel de salud debe actualizarse únicamente desde el hilo GTK (corregido).
- Evitar comprobaciones de salud mientras se ejecutan tareas de mantenimiento (corregido).
- Validar explícitamente el montaje raíz antes de crear instantáneas (corregido).

## Validación pendiente
- Ejecutar scripts/check.sh y revisar su resultado en CI.
- Probar de forma manual la interfaz en GNOME y otros escritorios.
- Probar Snapper con Btrfs real y con fallos de configuración.
- Probar Debian 13 y Ubuntu LTS en máquinas virtuales.
- Revisar traducciones completas, rendimiento y lectores de pantalla.

No se afirma compatibilidad completa ni recuperación automática hasta superar las pruebas manuales.

## Segunda pasada
- Reforzada la validación de nombres de usuario antes de interpolarlos en reglas JavaScript Polkit.
- Añadidas pruebas de rechazo de inyección y casos positivos/negativos de instantáneas Snapper.
- Los tests de Snapper usan funciones simuladas y no crean instantáneas reales.

## Integración Timeshift (rama de auditoría)
- Consulta sin privilegios `--snapshot-options`: solo presenta Timeshift con configuración y Snapper root sobre Btrfs.
- Sin proveedores disponibles no aparece el diálogo de instantáneas.
- Si hay ambos, el usuario elige el proveedor; por defecto no se crea ninguna instantánea.
- El helper vuelve a validar la configuración y cancela el mantenimiento si falla la creación.
- Pendiente: pruebas funcionales de Timeshift con configuraciones rsync/Btrfs y GNOME.
