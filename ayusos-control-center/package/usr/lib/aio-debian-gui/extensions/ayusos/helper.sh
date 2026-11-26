#!/bin/bash
# Pasos privilegiados específicos de AyusOS. El helper core carga este archivo
# desde su hook genérico de extensiones.

AIO_AYUSOS_MODULE_DIR=/usr/lib/aio-debian-gui/extensions/ayusos/aio_core
AIO_AYUSOS_RUNNER=/usr/lib/aio-debian-gui/extensions/ayusos/aio-run

paso_ayusos_update() {
    local accion="${1:-check}"
    local canal="${2:-stable}"
    local dry_run="${3:-false}"
    local modulo="$AIO_AYUSOS_MODULE_DIR/ayusos_update.py"
    [ -f "$modulo" ] || { err "Módulo ayusos_update no encontrado."; return 1; }

    case "$accion" in
        check)
            info "Comprobando actualizaciones de AyusOS..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_update check
            ;;
        install)
            info "Actualizando AyusOS a canal $canal..."
            if [ "$dry_run" = "true" ]; then
                /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_update update "$canal" --dry-run
            else
                /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_update update "$canal"
            fi
            ;;
        *) err "Acción desconocida: $accion"; return 1 ;;
    esac
}

paso_ayusos_snapshot() {
    local accion="${1:-create}"
    local snapshot_id="${2:-}"
    local comment="${3:-Snapshot AiO}"
    local tags="${4:-O}"
    local modulo="$AIO_AYUSOS_MODULE_DIR/ayusos_snapshots.py"
    [ -f "$modulo" ] || { err "Módulo ayusos_snapshots no encontrado."; return 1; }

    case "$accion" in
        create)
            info "Creando snapshot del sistema ($comment)..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_snapshots create "$comment" "$tags"
            ;;
        restore)
            [ -n "$snapshot_id" ] || { err "Falta ID de snapshot para restaurar."; return 1; }
            warn "Restaurando snapshot $snapshot_id (requerirá reinicio)..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_snapshots restore "$snapshot_id"
            REINICIO_REQUERIDO=1
            echo "##REBOOT:1"
            ;;
        delete)
            [ -n "$snapshot_id" ] || { err "Falta ID de snapshot para eliminar."; return 1; }
            info "Eliminando snapshot $snapshot_id..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_snapshots delete "$snapshot_id"
            ;;
        status)
            info "Estado de snapshots..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_snapshots status
            ;;
        grub-update)
            info "Actualizando menú GRUB con snapshots Btrfs..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_snapshots grub-update
            ;;
        *) err "Acción desconocida: $accion"; return 1 ;;
    esac
}

paso_ayusos_hardware() {
    local accion="${1:-detect}"
    local profile="${2:-}"
    local modulo="$AIO_AYUSOS_MODULE_DIR/ayusos_hardware.py"
    [ -f "$modulo" ] || { err "Módulo ayusos_hardware no encontrado."; return 1; }

    case "$accion" in
        detect)
            info "Detectando perfil de hardware recomendado..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_hardware detect
            ;;
        apply)
            [ -n "$profile" ] || { err "Falta perfil a aplicar (laptop, desktop, gaming, workstation, server)."; return 1; }
            info "Aplicando perfil de hardware: $profile..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_hardware apply "$profile"
            ;;
        status)
            info "Estado de perfiles de hardware..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_hardware status
            ;;
        info)
            info "Información de hardware..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_hardware info
            ;;
        *) err "Acción desconocida: $accion"; return 1 ;;
    esac
}

paso_ayusos_branding() {
    local accion="${1:-apply}"
    local valor="${2:-}"
    local modulo="$AIO_AYUSOS_MODULE_DIR/ayusos_branding.py"
    [ -f "$modulo" ] || { err "Módulo ayusos_branding no encontrado."; return 1; }

    case "$accion" in
        apply)
            info "Aplicando branding completo de AyusOS..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_branding apply
            ;;
        theme)
            [ -n "$valor" ] || { err "Falta variante de tema (system, light, dark)."; return 1; }
            info "Estableciendo tema: $valor..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_branding theme "$valor"
            ;;
        accent)
            [ -n "$valor" ] || { err "Falta color de acento."; return 1; }
            info "Estableciendo acento: $valor..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_branding accent "$valor"
            ;;
        wallpaper)
            [ -n "$valor" ] || { err "Falta ruta de fondo de pantalla."; return 1; }
            local modo="${3:-both}"
            info "Estableciendo fondo de pantalla..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_branding wallpaper "$valor" "$modo"
            ;;
        status)
            info "Estado de branding..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_branding status
            ;;
        *) err "Acción desconocida: $accion"; return 1 ;;
    esac
}

paso_ayusos_diagnostics() {
    local modulo="$AIO_AYUSOS_MODULE_DIR/ayusos_diagnostics.py"
    [ -f "$modulo" ] || { err "Módulo ayusos_diagnostics no encontrado."; return 1; }
    info "Ejecutando diagnóstico completo de AyusOS..."
    /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_diagnostics
}

paso_ayusos_autorizacion() {
    local accion="${1:-apply}"
    local username="${2:-}"
    case "$accion" in
        apply)
            info "Configurando autorización AiO para todos los administradores..."
            /usr/local/libexec/ayusos-aio-autorizar
            ;;
        remove-user)
            [ -n "$username" ] || { err "Falta nombre de usuario."; return 1; }
            info "Eliminando autorización AiO para $username..."
            /usr/local/libexec/ayusos-aio-limpiar-usuario "$username"
            ;;
        status)
            info "Estado de autorización AiO..."
            state=/var/lib/ayusos
            if [[ -f "$state/aio-usuarios" ]]; then
                echo "Usuarios autorizados:"
                while read -r uid; do
                    user=$(getent passwd "$uid" | cut -d: -f1)
                    echo "  - $user (UID $uid)"
                done < "$state/aio-usuarios"
            else
                echo "Sin usuarios autorizados."
            fi
            ;;
        *) err "Acción desconocida: $accion"; return 1 ;;
    esac
}

paso_ayusos_identity() {
    local accion="${1:-snapshot}"
    local archivo="${2:-}"
    local modulo="$AIO_AYUSOS_MODULE_DIR/ayusos_identity.py"
    [ -f "$modulo" ] || { err "Módulo ayusos_identity no encontrado."; return 1; }

    case "$accion" in
        snapshot)
            info "Capturando identidad de AyusOS..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_identity snapshot
            ;;
        backup)
            [ -n "$archivo" ] || { err "Falta ruta de archivo para backup."; return 1; }
            info "Guardando backup de identidad en $archivo..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_identity backup "$archivo"
            ;;
        restore)
            [ -n "$archivo" ] || { err "Falta archivo de backup para restaurar."; return 1; }
            info "Restaurando identidad de AyusOS desde $archivo..."
            /usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_identity restore "$archivo"
            ;;
        *) err "Acción desconocida: $accion"; return 1 ;;
    esac
}

# Registro de pasos: el core declara TITULOS antes de cargar extensiones.
TITULOS[ayusos-update]="Actualizar AyusOS (stable/testing)"
TITULOS[ayusos-snapshot]="Crear/restablecer snapshot del sistema (Timeshift/Btrfs)"
TITULOS[ayusos-hardware]="Aplicar perfil de hardware (laptop/gaming/desktop)"
TITULOS[ayusos-branding]="Aplicar tema, acento y fondos de AyusOS"
TITULOS[ayusos-diagnostics]="Ejecutar diagnóstico completo del sistema"
TITULOS[ayusos-autorizacion]="Gestionar autorización sin contraseña para administradores"
TITULOS[ayusos-identity]="Backup y restauración de la identidad de AyusOS"

ayusos_extension_status() {
    local update_status
    if [ -f "$AIO_AYUSOS_MODULE_DIR/ayusos_update.py" ]; then
        update_status=$(/usr/bin/python3 -I "$AIO_AYUSOS_RUNNER" ayusos_update check 2>/dev/null || true)
        if grep -q '"update_available": true' <<< "$update_status"; then
            printf '##STATUS:ayusos-update:2\n'
        else
            printf '##STATUS:ayusos-update:1\n'
        fi
    else
        printf '##STATUS:ayusos-update:0\n'
    fi

    if paquete_instalado timeshift || [ -d /.snapshots ]; then
        printf '##STATUS:ayusos-snapshot:1\n'
    else
        printf '##STATUS:ayusos-snapshot:0\n'
    fi

    for tarea in hardware branding diagnostics; do
        if [ -f "$AIO_AYUSOS_MODULE_DIR/ayusos_${tarea}.py" ]; then
            printf '##STATUS:ayusos-%s:1\n' "$tarea"
        else
            printf '##STATUS:ayusos-%s:0\n' "$tarea"
        fi
    done

    # Estado de autorización
    state=/var/lib/ayusos
    if [[ -f "$state/aio-usuarios" ]]; then
        count=$(wc -l < "$state/aio-usuarios")
        printf '##STATUS:ayusos-autorizacion:%d\n' "$count"
    else
        printf '##STATUS:ayusos-autorizacion:0\n'
    fi

    # Estado de identidad (si existen fuentes APT o llavero)
    if [[ -f /etc/apt/sources.list.d/ayusos.sources ]] || [[ -f /usr/share/keyrings/ayusos-archive.gpg ]]; then
        printf '##STATUS:ayusos-identity:1\n'
    else
        printf '##STATUS:ayusos-identity:0\n'
    fi
}

EXTENSION_STATUS_HOOKS+=(ayusos_extension_status)