"""Selecciona módulos usando exclusivamente los datos del paquete APT candidato."""
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def select_module(chips, devices, version):
    """Todas las GPU deben estar soportadas; no se adivinan familias por nombre."""
    if not devices:
        raise ValueError('No hay GPU NVIDIA verificables.')
    open_supported = True
    for device in devices:
        matches = [c for c in chips if int(c['devid'], 16) == device['device']
                   and all(key not in c or int(c[key], 16) == device[key]
                           for key in ('subvendorid', 'subdevid'))]
        # Preferir la coincidencia específica del subsistema.
        if matches:
            specificity = max(sum(k in c for k in ('subvendorid', 'subdevid')) for c in matches)
            matches = [c for c in matches if sum(k in c for k in ('subvendorid', 'subdevid')) == specificity]
        if not matches or any(c.get('legacybranch') for c in matches):
            raise ValueError('GPU desconocida o de una rama legacy; revisión manual necesaria.')
        open_supported &= all('kernelopen' in c.get('features', []) for c in matches)
    major = int(version.split(':')[-1].split('.')[0])
    if major >= 560 and open_supported:
        return 'nvidia-open-kernel-dkms'
    # 550: conservar la variante propietaria de Debian, incluidos los equipos
    # Turing+, debido a las limitaciones de compilación de la variante abierta.
    return 'nvidia-kernel-dkms'


def devices_from_sysfs(root):
    devices = []
    for path in Path(root).iterdir():
        try:
            vendor = int((path / 'vendor').read_text().strip(), 16)
            pci_class = int((path / 'class').read_text().strip(), 16)
        except (FileNotFoundError, NotADirectoryError):
            continue
        if vendor != 0x10de or pci_class >> 16 != 3:
            continue
        devices.append({key: int((path / filename).read_text().strip(), 16)
                        for key, filename in (('device', 'device'),
                                              ('subvendorid', 'subsystem_vendor'),
                                              ('subdevid', 'subsystem_device'))})
    return devices


def from_package(directory, version, pci_root):
    if not re.fullmatch(r'[0-9][0-9A-Za-z.+:~\-]*', version):
        raise ValueError('Versión no válida.')
    packages = list(Path(directory).glob('*.deb'))
    if len(packages) != 1:
        raise ValueError('Se esperaba exactamente un paquete candidato.')
    deb = str(packages[0])
    identity = subprocess.check_output(
        ['dpkg-deb', '-W', '--showformat=${Package}\n${Version}', deb], text=True, timeout=15)
    if identity.strip() != 'nvidia-driver\n' + version:
        raise ValueError('Identidad del paquete incorrecta.')
    # No se extraen archivos ni se ejecutan scripts del paquete.
    with subprocess.Popen(['dpkg-deb', '--fsys-tarfile', deb], stdout=subprocess.PIPE) as proc:
        with tarfile.open(fileobj=proc.stdout, mode='r|') as archive:
            data = None
            for entry in archive:
                if entry.name.lstrip('./') == 'usr/share/doc/nvidia-driver/supported-gpus.json.gz':
                    if not entry.isfile() or entry.size > 4 * 1024 * 1024:
                        raise ValueError('Lista de GPU no válida.')
                    with gzip.GzipFile(fileobj=archive.extractfile(entry)) as stream:
                        data = stream.read(8 * 1024 * 1024 + 1)
                    if len(data) > 8 * 1024 * 1024:
                        raise ValueError('Lista de GPU demasiado grande.')
            # Consumir el archivo completo permite comprobar el resultado de dpkg-deb.
        proc.stdout.close()
        if proc.wait(timeout=15) != 0 or data is None:
            raise ValueError('No se pudo leer la lista de GPU del candidato.')
    return select_module(json.loads(data)['chips'], devices_from_sysfs(pci_root), version)


if __name__ == '__main__':
    try:
        print(from_package(*sys.argv[1:]))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, tarfile.TarError) as error:
        print('No se puede seleccionar NVIDIA: ' + str(error), file=sys.stderr)
        sys.exit(1)
