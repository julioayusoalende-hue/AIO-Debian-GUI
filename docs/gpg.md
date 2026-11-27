# Claves GPG y verificación de firmas en AiO Debian GUI

Este documento describe cómo se usan las claves GPG en el proyecto, cómo verificar la integridad de las descargas y cómo firmar paquetes y el repositorio APT.

## 🔑 Clave pública del proyecto

La clave pública se incluye en el paquete DEB en:
```
/usr/share/keyrings/aio-debian-gui.gpg
```

### Huella digital (fingerprint)
```
<FINGERPRINT_DE_LA_CLAVE>  # Se completa en cada release
```

### Obtener la clave
```bash
# Desde el paquete instalado
gpg --show-keys /usr/share/keyrings/aio-debian-gui.gpg

# Descargar directamente desde GitHub (release estable)
wget https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/latest/download/aio-debian-gui.gpg
gpg --show-keys aio-debian-gui.gpg
```

## ✅ Verificar la integridad de un paquete DEB

Cada release estable incluye un archivo `SHA256SUMS` firmado.

### 1. Descargar DEB, SHA256SUMS y la firma
```bash
wget https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/download/v1.5.2/aio-debian-gui_1.5.2_all.deb
wget https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/download/v1.5.2/SHA256SUMS
wget https://github.com/julioayusoalende-hue/AIO-Debian-GUI/releases/download/v1.5.2/SHA256SUMS.sig
```

### 2. Verificar la firma del archivo SHA256SUMS
```bash
# Importar la clave pública del proyecto
gpg --import aio-debian-gui.gpg

# Verificar la firma
gpg --verify SHA256SUMS.sig SHA256SUMS
```
Deberías ver:
```
gpg: Firma correcta ...
gpg: clave pública "AiO Debian GUI <...>" ...
```

### 3. Verificar el checksum del DEB
```bash
sha256sum -c --ignore-missing SHA256SUMS
```
Resultado esperado:
```
aio-debian-gui_1.5.2_all.deb: La suma coincide
```

## 🔐 Verificar el repositorio APT

Tras instalar el paquete, el repositorio firmado se configura automáticamente en `/etc/apt/sources.list.d/aio-debian-gui.sources` (formato deb822) o `.list` (formato clásico).

### Verificar manualmente
```bash
# Descargar InRelease del repositorio
wget https://github.com/julioayusoalende-hue/AIO-Debian-GUI/raw/apt/stable/InRelease

# Verificar con la clave del sistema
gpgv --keyring /usr/share/keyrings/aio-debian-gui.gpg InRelease
```

### Verificar tras `apt update`
APT verifica automáticamente la firma. Si ves:
```
Get:1 https://.../stable InRelease [X B]
Hit:1 https://.../stable InRelease
```
La firma es válida. Si falla:
```
Err:1 https://.../stable InRelease
  The following signatures were invalid: EXPKEYSIG ...
```
La clave ha expirado o el repositorio ha sido alterado.

## 📦 Firmar paquetes y repositorio (solo mantenedores)

### Requisitos
- Clave privada GPG correspondiente a `aio-debian-gui.gpg`
- `gpg-agent` configurado (recomendado) o `GPG_PASSPHRASE` en entorno
- Variables de entorno:
  - `GPG_KEY`: fingerprint de la clave de firma
  - `APT_REPO_DIR`: ruta local del repositorio APT (estructura `dists/stable/`, `pool/`)
  - `SITE_DIR`: directorio del sitio GitHub Pages (para publicar clave pública)

### Firmar el repositorio APT
```bash
export GPG_KEY="<FINGERPRINT>"
export APT_REPO_DIR="/ruta/al/repo"
export SITE_DIR="/ruta/al/sitio"
./scripts/publish-apt-repo.sh
```

El script:
1. Genera `Packages` / `Sources` y `Release` en `dists/stable/`
2. Firma `Release` → `InRelease` (clearsign) y `Release.gpg` (detached)
3. Copia la clave pública a `SITE_DIR/aio-debian-gui.gpg`
4. Sube cambios a GitHub Pages (si está configurado)

### Firmar un paquete DEB individual
```bash
# dpkg-sig no se usa; el repo APT firma los metadatos, no los .deb individuales.
# La integridad del .deb se verifica vía SHA256SUMS firmado en la release de GitHub.
```

### Generar nueva clave GPG (rotación)
```bash
gpg --full-generate-key
# Tipo: ECC (Ed25519) o RSA 4096
# Uso: Sign only
# Expiración: 2-3 años
# Nombre: "AiO Debian GUI"
# Email: proyecto@dominio.org

# Exportar clave pública
gpg --export --armor "AiO Debian GUI" > package/usr/share/keyrings/aio-debian-gui.gpg

# Actualizar fingerprint en scripts/publish-apt-repo.sh y documentar en CHANGELOG
```

## 🛡️ Modelo de confianza

| Componente | Verificación | Quién |
|------------|--------------|-------|
| DEB descargado | SHA256SUMS + firma GPG | Usuario final |
| Repositorio APT | `InRelease` firmado + `apt update` | APT (automático) |
| Integración host (Flatpak/AppImage) | Helper verificado por hash en código | Usuario al instalar integración |
| Código fuente | Commits firmados (opcional) | Colaboradores |

## ❓ Preguntas frecuentes

### "The following signatures were invalid: EXPKEYSIG"
La clave GPG ha expirado. Soluciones:
1. Actualiza el paquete `aio-debian-gui` a una versión más reciente (incluye clave renovada)
2. O descarga la nueva clave pública y agrégala:
   ```bash
   wget -O- https://github.com/julioayusoalende-hue/AIO-Debian-GUI/raw/apt/stable/aio-debian-gui.gpg | sudo tee /usr/share/keyrings/aio-debian-gui.gpg
   sudo apt update
   ```

### "NO_PUBKEY" al hacer `apt update`
Falta la clave en el keyring. El paquete DEB debería instalarla automáticamente. Si falla:
```bash
sudo mkdir -p /usr/share/keyrings
wget -O- https://github.com/julioayusoalende-hue/AIO-Debian-GUI/raw/apt/stable/aio-debian-gui.gpg | sudo tee /usr/share/keyrings/aio-debian-gui.gpg
sudo apt update
```

### ¿Puedo usar mi propia clave para un fork?
Sí. Genera tu clave, actualiza `package/usr/share/keyrings/` y modifica `scripts/publish-apt-repo.sh` con tu `GPG_KEY`. Los usuarios de tu fork necesitarán tu clave pública.

## 📚 Referencias
- `scripts/publish-apt-repo.sh` — publicación del repo firmado
- `scripts/build-deb.sh` — empaquetado DEB con keyring
- `scripts/test-host-package.py` — tests de verificación GPG automatizados
- [GPG Best Practices](https://gist.github.com/brauner/5f5c1b9c6e8b6e8b6e8b) (Guía de la comunidad Debian)