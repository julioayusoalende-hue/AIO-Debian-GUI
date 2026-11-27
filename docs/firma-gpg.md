# Guía de firma GPG para AiO Debian GUI

Este documento describe cómo configurar, usar y verificar firmas GPG en el proyecto AiO Debian GUI.

## Índice

1. [Propósito](#propósito)
2. [Clave oficial del proyecto](#clave-oficial-del-proyecto)
3. [Configurar tu clave GPG](#configurar-tu-clave-gpg)
4. [Firmar commits y tags](#firmar-commits-y-tags)
5. [Verificar firmas](#verificar-firmas)
6. [Verificar paquetes DEB y releases](#verificar-paquetes-deb-y-releases)
7. [Rotación y revocación de claves](#rotación-y-revocación-de-claves)
8. [Solución de problemas](#solución-de-problemas)

---

## Propósito

La firma GPG garantiza:

- **Autenticidad**: El código proviene del autor declarado
- **Integridad**: El código no ha sido modificado en tránsito
- **No repudio**: El autor no puede negar su autoría

Todos los commits en `main`, `testing` y tags de release **deben estar firmados**.

---

## Clave oficial del proyecto

| Campo | Valor |
|-------|-------|
| **Key ID** | `0xXXXXXXXXXXXXXXXX` |
| **Fingerprint** | `XXXX XXXX XXXX XXXX XXXX  XXXX XXXX XXXX XXXX XXXX` |
| **Usuario** | `Julio Ayuso <julio@ayuso.dev>` |
| **Algoritmo** | RSA 4096 |
| **Uso** | Firmar commits, tags, releases, paquetes DEB |
| **Caducidad** | Sin caducidad (rotación manual) |

### Importar la clave pública

```bash
# Desde keyserver
gpg --keyserver keyserver.ubuntu.com --recv-keys XXXXXXXXXXXXXXXX

# O desde archivo (si se distribuye)
gpg --import julio-ayuso-pubkey.asc

# Verificar fingerprint
gpg --fingerprint XXXXXXXXXXXXXXXX
```

---

## Configurar tu clave GPG

### 1. Generar una clave nueva (recomendado)

```bash
gpg --full-generate-key
```

**Opciones recomendadas:**

```
Please select what kind of key you want:
   (1) RSA and RSA (default)          ← Seleccionar 1
What keysize do you want? (3072) 4096  ← 4096 bits
Key is valid for? (0) 0                ← Sin caducidad (0 = nunca)
Real name: Tu Nombre Completo
Email address: tu@email.com            ← Debe coincidir con GitHub
Comment:                               ← Opcional, dejar vacío
```

### 2. Usar una clave existente

```bash
# Listar claves secretas
gpg --list-secret-keys --keyid-format=long

# Ejemplo de salida:
# sec   rsa4096/ABC123DEF456 2024-01-01 [SC]
#      XXXX XXXX XXXX XXXX XXXX  XXXX XXXX XXXX XXXX XXXX
# uid           [ultimate] Tu Nombre <tu@email.com>
# ssb   rsa4096/78901234ABCD 2024-01-01 [E]
```

El **Key ID** es `ABC123DEF456` (los últimos 16 caracteres del fingerprint).

### 3. Configurar Git para firmar

```bash
# Clave por defecto para firmar
git config --global user.signingkey ABC123DEF456

# Firmar commits automáticamente
git config --global commit.gpgsign true

# Firmar tags automáticamente
git config --global tag.gpgsign true

# Usar gpg2 si está disponible
git config --global gpg.program gpg2
```

### 4. Añadir clave pública a GitHub

```bash
# Exportar en formato ASCII armor
gpg --armor --export ABC123DEF456
```

1. Copiar la salida completa (incluyendo `-----BEGIN PGP PUBLIC KEY BLOCK-----` y `-----END PGP PUBLIC KEY BLOCK-----`)
2. Ir a **GitHub → Settings → SSH and GPG keys → New GPG key**
3. Pegar la clave y guardar
4. Verificar que aparece como **Verified** (verde)

### 5. Configurar agente GPG (evitar introducir passphrase repetidamente)

```bash
# ~/.gnupg/gpg-agent.conf
default-cache-ttl 3600
max-cache-ttl 7200
pinentry-program /usr/bin/pinentry-gtk-2  # o pinentry-curses, pinentry-tty

# Reiniciar agente
gpgconf --kill gpg-agent
```

---

## Firmar commits y tags

### Commits nuevos

```bash
# Commit firmado (si commit.gpgsign=true)
git commit -m "feat: nueva funcionalidad"

# Forzar firma en un commit específico
git commit -S -m "fix: corrección importante"

# Reescribir último commit para firmarlo
git commit --amend --no-edit -S
```

### Tags de release

```bash
# Tag anotado y firmado (recomendado para releases)
git tag -s 1.5.0 -m "Release 1.5.0

Cambios:
- Corrección en autoactualización DEB
- Mejora en diagnóstico NVIDIA
- Actualizaciones de traducciones"

# Tag ligero firmado
git tag -s 1.5.0 -m "Release 1.5.0"
```

### Verificar que se firmaron

```bash
# Commits firmados
git log --show-signature --oneline -5

# Tags firmados
git tag -v 1.5.0
```

Salida esperada para commit firmado:
```
commit abc123def456 (HEAD -> main)
gpg: Firma hecha el mié 27 nov 2026 10:00:00 CET
gpg:                usando clave RSA ABC123DEF456
gpg: Firma correcta de "Tu Nombre <tu@email.com>" [ultimate]
Author: Tu Nombre <tu@email.com>
Date:   Wed Nov 27 10:00:00 2026 +0100

    feat: nueva funcionalidad
```

---

## Verificar firmas

### Verificar commits en el historial

```bash
# Últimos 10 commits con verificación
git log --show-signature --oneline -10

# Solo commits firmados correctamente
git log --pretty="%h %G? %s" | grep "^[a-f0-9]* G "

# Verificar autor específico
git log --show-signature --author="Julio Ayuso" --oneline
```

Estados de verificación (`%G?`):
- `G` = Firma válida (Good)
- `B` = Firma inválida (Bad)
- `U` = Clave no encontrada (Unknown)
- `X` = Caducada (Expired)
- `Y` = Clave revocada (Revoked)
- `N` = Sin firma (None)

### Verificar tag de release

```bash
git tag -v 1.5.0
```

Salida esperada:
```
objeto abc123def4567890abcdef1234567890abcdef12
tipo commit
tag 1.5.0
etiquetador Julio Ayuso <julio@ayuso.dev> 1701086400 +0100
Release 1.5.0
...
gpg: Firma hecha el mié 27 nov 2026 10:00:00 CET
gpg:                usando clave RSA XXXXXXXXXXXXXXXX
gpg: Firma correcta de "Julio Ayuso <julio@ayuso.dev>" [desconocido]
```

---

## Verificar paquetes DEB y releases

### Archivos firmados en cada release

| Archivo | Descripción |
|---------|-------------|
| `aio-debian-gui_X.Y.Z_all.deb` | Paquete binario |
| `SHA256SUMS` | Sumas SHA-256 de todos los archivos |
| `SHA256SUMS.sig` | Firma GPG de SHA256SUMS |

### Verificar integridad de la descarga

```bash
# 1. Descargar DEB, SHA256SUMS y SHA256SUMS.sig de la misma release

# 2. Verificar la firma de SHA256SUMS
gpg --verify SHA256SUMS.sig SHA256SUMS

# Salida esperada:
# gpg: Firma hecha el mié 27 nov 2026 10:00:00 CET
# gpg:                usando clave RSA XXXXXXXXXXXXXXXX
# gpg: Firma correcta de "Julio Ayuso <julio@ayuso.dev>" [ultimate]

# 3. Verificar la suma del DEB
sha256sum -c --ignore-missing SHA256SUMS

# Salida esperada:
# aio-debian-gui_1.5.0_all.deb: La suma coincide
```

### Verificar paquete DEB instalado

```bash
# Verificar firma del paquete (si está firmado con dpkg-sig)
dpkg-sig --verify aio-debian-gui_1.5.0_all.deb

# O verificar contenido contra sums oficiales
dpkg-deb -c aio-debian-gui_1.5.0_all.deb | head -20
```

---

## Rotación y revocación de claves

### Rotar clave (generar nueva)

1. Generar nueva clave RSA 4096
2. Firmar la nueva clave con la antigua (transición de confianza)
3. Publicar nueva clave en keyservers y GitHub
4. Actualizar `git config user.signingkey`
5. Revocar clave antigua tras período de transición

```bash
# Firmar nueva clave con la antigua
gpg --default-key ANTIGUA_KEYID --sign-key NUEVA_KEYID

# Exportar ambas claves públicas juntas
gpg --armor --export ANTIGUA_KEYID NUEVA_KEYID > claves-transicion.asc
```

### Revocar clave comprometida

```bash
# Generar certificado de revocación (hacerlo al crear la clave y guardar offline)
gpg --gen-revoke ABC123DEF456 > revoke-ABC123DEF456.asc

# Si la clave se ve comprometida, importar y publicar certificado
gpg --import revoke-ABC123DEF456.asc
gpg --keyserver keyserver.ubuntu.com --send-keys ABC123DEF456
```

### Clave del proyecto (mantenedor principal)

La clave del proyecto se rota cada 2-3 años. El proceso:

1. Anunciar rotación en GitHub Discussions y CHANGELOG
2. Publicar nueva clave firmada por la antigua
3. Actualizar documentación y scripts de verificación
4. Período de transición de 3 meses
5. Revocar clave antigua

---

## Solución de problemas

### Error: "gpg: signing failed: Inappropriate ioctl for device"

```bash
# Exportar TTY para pinentry
export GPG_TTY=$(tty)
echo "GPG_TTY=$(tty)" >> ~/.bashrc

# O configurar pinentry en gpg-agent.conf
pinentry-program /usr/bin/pinentry-tty
```

### Error: "gpg: skipped: No secret key"

```bash
# Verificar clave configurada
git config user.signingkey

# Listar claves secretas disponibles
gpg --list-secret-keys --keyid-format=long

# Reconfigurar si falta
git config --global user.signingkey NUEVA_KEYID
```

### Error: "gpg: Can't check signature: No public key"

```bash
# Importar clave pública del firmante
gpg --keyserver keyserver.ubuntu.com --recv-keys KEYID_DEL_FIRMANTE

# O desde archivo
gpg --import clave-publica.asc
```

### La firma no aparece como "Verified" en GitHub

1. Verificar que el email de la clave GPG coincide **exactamente** con el email verificado en GitHub
2. Verificar que la clave pública está subida a GitHub (Settings → SSH and GPG keys)
3. Esperar unos minutos (caché de GitHub)
4. Forzar nuevo commit de prueba firmado

### Firmar commits pasados (rebase interactivo)

```bash
# Firmar últimos 5 commits
git rebase --exec 'git commit --amend --no-edit -S' HEAD~5

# Advertencia: reescribe historial, solo en ramas propias no compartidas
```

### Verificar configuración completa

```bash
# Script de verificación
cat << 'EOF' > verify-gpg-setup.sh
#!/bin/bash
echo "=== Configuración GPG ==="
echo "Clave configurada: $(git config user.signingkey)"
echo "Firma commits: $(git config commit.gpgsign)"
echo "Firma tags: $(git config tag.gpgsign)"
echo ""
echo "=== Claves secretas ==="
gpg --list-secret-keys --keyid-format=long
echo ""
echo "=== Test de firma ==="
echo "test" | gpg --clearsign --dry-run 2>&1 | head -5
EOF
chmod +x verify-gpg-setup.sh
./verify-gpg-setup.sh
```

---

## Referencias

- [GitHub: Managing commit signature verification](https://docs.github.com/en/authentication/managing-commit-signature-verification)
- [GPG Best Practices](https://gist.github.com/StefanoKowalski/0d4d1e5b6b5e8e8e8e8e)
- [Debian: Signing packages](https://wiki.debian.org/SigningPackages)
- [Contributor Covenant](https://www.contributor-covenant.org/)

---

*Última actualización: 2026-11-27*