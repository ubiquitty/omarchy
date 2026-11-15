#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
"""Package an already-built Release; never compile on deployment machines."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, default=Path.cwd())
    options = parser.parse_args()
    source = options.source_root.resolve()
    build = options.build_dir.resolve()
    cache = (build / 'CMakeCache.txt').read_text()
    if not re.search(r'^CMAKE_BUILD_TYPE:[^=]+=Release$', cache, re.MULTILINE) and not re.search(r'^CMAKE_CONFIGURATION_TYPES:[^=]+=.+', cache, re.MULTILINE):
        parser.error('a Release build is required')
    options.output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ubiquitty-package-') as directory:
        stage = Path(directory) / 'ubiquitty'
        subprocess.run(['cmake', '--install', str(build), '--prefix', str(stage), '--config', 'Release'], check=True)
        version = subprocess.check_output([str(stage / 'bin/ubiquitty'), '--version'], text=True).strip()
        if not version.startswith('ubiquitty '):
            raise ValueError('unexpected executable identity')
        integration = Path(__file__).resolve().parents[1]
        shutil.copytree(integration / 'libexec', stage / 'libexec', dirs_exist_ok=True)
        applications = stage / 'share/applications'
        applications.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / 'Resources/linux/org.ubiquitty.linux.desktop', applications)
        icon_root = stage / 'share/icons/hicolor'
        for size in [16, 24, 32, 48, 64, 128, 256]:
            destination = icon_root / f'{size}x{size}/apps/org.ubiquitty.linux.png'
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / f'Resources/Icon/Raster/Ubiquitty-{size}.png', destination)
        destination = icon_root / 'scalable/apps/org.ubiquitty.linux.svg'
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / 'Resources/Icon/Ubiquitty.svg', destination)
        kit = source / 'Libraries/ubiquitty-kit'
        core = kit / 'Libraries/ubiquitty-core'
        subprocess.run(['python3', str(core / 'Scripts/license_notices.py'), '--source', str(source), '--core', str(core), '--kit', str(kit), '--copy', str(stage / 'share/doc/ubiquitty')], check=True)
        architecture = platform.machine()
        manifest = {'format': 1, 'version': version, 'architecture': architecture, 'configuration': 'Release'}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        identity = re.sub(r'[^A-Za-z0-9._-]+', '-', version)
        output = options.output_dir / f'{identity}-linux-{architecture}.tar.gz'
        with output.open('wb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', compresslevel=1, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|') as archive:
                archive.add(stage, arcname='ubiquitty')
        with output.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        output.with_name(output.name + '.sha256').write_text(f'{digest}  {output.name}\n')
        print(output)


if __name__ == '__main__':
    main()
