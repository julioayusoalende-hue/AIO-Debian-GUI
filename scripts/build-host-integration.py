#!/usr/bin/env python3
"""Construye el instalador autónomo que acompaña a AppImage y Flatpak."""
import argparse
import ast
from pathlib import Path
import re
import subprocess
import sys


def package_version(package):
    control = (package / 'DEBIAN/control').read_text(encoding='utf-8')
    matches = re.findall(r'^Version: (\d+\.\d+\.\d+)$', control, re.M)
    if len(matches) != 1:
        raise ValueError('No se pudo identificar la versión del paquete.')
    version = matches[0]
    helper = (package / 'usr/lib/aio-debian-gui/aio-debian-gui-helper').read_text(encoding='utf-8')
    if re.findall(r'^HELPER_VERSION=(\d+\.\d+\.\d+)$', helper, re.M) != [version]:
        raise ValueError('La versión del asistente no coincide con el paquete.')
    tree = ast.parse((package / 'usr/lib/aio-debian-gui/aio_core/scheduler.py').read_text(encoding='utf-8'))
    versions = [node.value.value for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                and any(isinstance(target, ast.Name) and target.id == 'VERSION' for target in node.targets)]
    if versions != [version]:
        raise ValueError('La versión del programador no coincide con el paquete.')
    return version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    package = args.source_root.resolve() / 'package'
    version = package_version(package)
    installer = package / 'usr/lib/aio-debian-gui/aio_core/host_integration.py'
    subprocess.run([sys.executable, '-I', str(installer), '--build', str(package),
                    version, str(args.output.resolve())], check=True)
    print(f'Integración autónoma {version}: {args.output}')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
