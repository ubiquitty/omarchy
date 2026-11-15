#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
"""Install a trusted prebuilt Ubiquitty bundle without compiling or sudo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import tomllib
import uuid


def run_optional(command):
    if shutil.which(command[0]):
        subprocess.run(command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def snapshot_file(path):
    if path.is_symlink():
        return ('link', os.readlink(path))
    if path.exists():
        if not path.is_file():
            raise ValueError(f'installation destination is not a file: {path}')
        return ('file', path.read_bytes(), path.stat().st_mode & 0o777)
    return None


def restore_file(path, previous):
    if previous is None:
        path.unlink(missing_ok=True)
        return
    temporary = path.with_name(f'.{path.name}-rollback-{uuid.uuid4().hex}')
    try:
        if previous[0] == 'link':
            temporary.symlink_to(previous[1])
        else:
            temporary.write_bytes(previous[1])
            temporary.chmod(previous[2])
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install_bundle(bundle, prefix, with_omarchy=False, set_default=False):
    manifest = json.loads((bundle / 'manifest.json').read_text())
    if manifest.get('format') != 1 or manifest.get('configuration') != 'Release':
        raise ValueError('unsupported bundle format or non-Release bundle')
    if manifest.get('architecture') != platform.machine():
        raise ValueError(f'bundle architecture {manifest.get("architecture")} does not match {platform.machine()}')
    if with_omarchy and not shutil.which('omarchy'):
        raise ValueError('--omarchy requires the omarchy command')
    if with_omarchy:
        config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'ubiquitty/config.toml'
        if config.exists():
            tomllib.loads(config.read_text())
    releases = prefix / 'lib/ubiquitty/releases'
    releases.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.staging-', dir=releases))
    previous_files = []
    try:
        shutil.copytree(bundle, stage, dirs_exist_ok=True, symlinks=True)
        version = subprocess.check_output([str(stage / 'bin/ubiquitty'), '--version'], text=True).strip()
        if version != manifest['version'] or not version.startswith('ubiquitty '):
            raise ValueError('executable identity differs from bundle manifest')
        identity = re.sub(r'[^A-Za-z0-9._-]+', '-', version)
        release = releases / f'{identity}-{uuid.uuid4().hex[:8]}'
        stage.rename(release)
        stage = None
        for name in ['theme', 'font']:
            subprocess.run(['python3', str(release / f'libexec/sync-omarchy-{name}.py'), '--write-hook', str(release / f'libexec/ubiquitty-{name}')], check=True)
        binary = prefix / 'bin/ubiquitty'
        desktop = prefix / 'share/applications/org.ubiquitty.linux.desktop'
        previous_files = [(path, snapshot_file(path)) for path in [binary, prefix / 'bin/ubiquitty-omarchy', desktop]]
        binary.parent.mkdir(parents=True, exist_ok=True)
        for name, target in [('ubiquitty', release / 'bin/ubiquitty'), ('ubiquitty-omarchy', release / 'libexec/ubiquitty-omarchy.py')]:
            link = prefix / 'bin' / name
            temporary = link.with_name(f'.{name}-{uuid.uuid4().hex}')
            temporary.symlink_to(target)
            temporary.replace(link)
        desktop.parent.mkdir(parents=True, exist_ok=True)
        quoted = str(binary).replace('\\', '\\\\\\\\').replace('"', '\\\\"').replace('`', '\\\\`').replace('$', '\\\\$').replace('%', '%%')
        lines = (release / 'share/applications/org.ubiquitty.linux.desktop').read_text().splitlines()
        lines = [f'Exec="{quoted}"' if line.startswith('Exec=') else line for line in lines]
        for key, value in [('X-TerminalArgExec', '-e'), ('X-TerminalArgAppId', '--app-id')]:
            if not any(line.startswith(key + '=') for line in lines):
                lines.append(key + '=' + value)
        temporary = desktop.with_name(desktop.name + '.new')
        temporary.write_text('\n'.join(lines) + '\n')
        temporary.replace(desktop)
        shutil.copytree(release / 'share/icons', prefix / 'share/icons', dirs_exist_ok=True)
        run_optional(['update-desktop-database', str(desktop.parent)])
        run_optional(['gtk-update-icon-cache', '-f', '-t', str(prefix / 'share/icons/hicolor')])
        if with_omarchy:
            helper = release / 'libexec/ubiquitty-omarchy.py'
            subprocess.run(['python3', str(helper), 'install', '--binary', str(binary), '--desktop', str(desktop)], check=True)
            subprocess.run(['omarchy', 'hook', 'install', 'font-set', str(release / 'libexec/ubiquitty-font')], check=True)
            theme = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'omarchy/current/theme/foot.ini'
            if theme.exists():
                subprocess.run([str(release / 'libexec/ubiquitty-theme'), '--initialize'], check=True)
                subprocess.run(['omarchy', 'hook', 'install', 'theme-set', str(release / 'libexec/ubiquitty-theme')], check=True)
            if set_default:
                subprocess.run(['python3', str(helper), 'set-default', '--binary', str(binary), '--desktop', str(desktop)], check=True)
        print(f'Installed: {binary}\nDesktop: {desktop}\nResources: {release}')
        return release
    except BaseException:
        # Hooks may already reference this release. Restore the public entry
        # points but retain its complete resources until the user removes it.
        for path, previous in previous_files:
            restore_file(path, previous)
        if previous_files:
            run_optional(['update-desktop-database', str(prefix / 'share/applications')])
        raise
    finally:
        if stage:
            shutil.rmtree(stage, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path, help='trusted bundle directory or .tar.gz archive with adjacent .sha256')
    parser.add_argument('--prefix', type=Path, default=Path.home() / '.local')
    parser.add_argument('--omarchy', action='store_true')
    parser.add_argument('--default', '--default-terminal', action='store_true', dest='set_default')
    options = parser.parse_args()
    prefix = options.prefix.expanduser().resolve()
    if options.bundle.is_dir():
        install_bundle(options.bundle.resolve(), prefix, options.omarchy or options.set_default, options.set_default)
        return
    expected = options.bundle.with_name(options.bundle.name + '.sha256').read_text().split()[0]
    with options.bundle.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        parser.error('archive checksum does not match its .sha256 manifest')
    with tempfile.TemporaryDirectory(prefix='ubiquitty-unpack-') as directory:
        with tarfile.open(options.bundle, 'r:gz') as archive:
            archive.extractall(directory, filter='data')
        install_bundle(Path(directory) / 'ubiquitty', prefix, options.omarchy or options.set_default, options.set_default)


if __name__ == '__main__':
    main()
