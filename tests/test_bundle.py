#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install_ubiquitty.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class BundleTests(unittest.TestCase):
    def make_bundle(self, root):
        bundle = root / 'ubiquitty'
        (bundle / 'bin').mkdir(parents=True)
        binary = bundle / 'bin/ubiquitty'
        binary.write_text('#!/bin/sh\nprintf "ubiquitty fixture\\n"\n')
        binary.chmod(0o755)
        (bundle / 'bin/glyph.spv').write_bytes(b'shader')
        (bundle / 'bin/font.ttf').write_bytes(b'font')
        shutil.copytree(ROOT / 'libexec', bundle / 'libexec')
        applications = bundle / 'share/applications'
        applications.mkdir(parents=True)
        (applications / 'org.ubiquitty.linux.desktop').write_text('[Desktop Entry]\nType=Application\nName=Ubiquitty\nExec=ubiquitty\n')
        icons = bundle / 'share/icons/hicolor/scalable/apps'
        icons.mkdir(parents=True)
        (icons / 'org.ubiquitty.linux.svg').write_text('<svg/>')
        (bundle / 'manifest.json').write_text(json.dumps({'format': 1, 'configuration': 'Release', 'version': 'ubiquitty fixture', 'architecture': platform.machine()}))
        return bundle

    def test_directory_install_keeps_complete_versioned_resources_and_old_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            prefix = root / "prefix with 'quotes' and spaces"
            first = installer.install_bundle(bundle, prefix)
            second = installer.install_bundle(bundle, prefix)
            self.assertNotEqual(first, second)
            self.assertTrue(first.exists())
            self.assertEqual((prefix / 'bin/ubiquitty').resolve(), second / 'bin/ubiquitty')
            self.assertEqual((second / 'bin/glyph.spv').read_bytes(), b'shader')
            self.assertEqual((second / 'bin/font.ttf').read_bytes(), b'font')
            desktop = (prefix / 'share/applications/org.ubiquitty.linux.desktop').read_text()
            self.assertIn('X-TerminalArgAppId=--app-id', desktop)
            self.assertIn('X-TerminalArgExec=-e', desktop)
            self.assertIn(str(prefix / 'bin/ubiquitty'), desktop)
            hook = (second / 'libexec/ubiquitty-font').read_text()
            self.assertIn('exec python3', hook)
            self.assertIn('sync-omarchy-font.py', hook)
            self.assertFalse((prefix / 'config.toml').exists())

    def test_incorrect_architecture_never_replaces_installed_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            prefix = root / 'prefix'
            first = installer.install_bundle(bundle, prefix)
            manifest = json.loads((bundle / 'manifest.json').read_text())
            manifest['architecture'] = 'wrong-architecture'
            (bundle / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):
                installer.install_bundle(bundle, prefix)
            self.assertEqual((prefix / 'bin/ubiquitty').resolve(), first / 'bin/ubiquitty')

    def test_packaging_stages_release_without_a_build_command(self):
        spec = importlib.util.spec_from_file_location('packager', ROOT / 'scripts/package_local_build.py')
        packager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(packager)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            desktop = source / 'Resources/linux/org.ubiquitty.linux.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('[Desktop Entry]\nExec=ubiquitty\n')
            icons = source / 'Resources/Icon'
            (icons / 'Raster').mkdir(parents=True)
            (icons / 'Ubiquitty.svg').write_text('<svg/>')
            for size in [16, 24, 32, 48, 64, 128, 256]:
                (icons / f'Raster/Ubiquitty-{size}.png').write_bytes(b'icon')
            build = root / 'build'
            build.mkdir()
            (build / 'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release\n')
            commands = []
            def stage_install(command, **kwargs):
                commands.append(command)
                if command[0] == 'cmake':
                    stage = Path(command[command.index('--prefix') + 1])
                    (stage / 'bin').mkdir(parents=True)
                    binary = stage / 'bin/ubiquitty'
                    binary.write_text('#!/bin/sh\nprintf "ubiquitty fixture\\n"\n')
                    binary.chmod(0o755)
                    (stage / 'bin/atlas.spv').write_bytes(b'shader')
                else:
                    destination = Path(command[command.index('--copy') + 1])
                    destination.mkdir(parents=True)
                    (destination / 'NOTICE').write_text('fixture notice')
                return subprocess.CompletedProcess(command, 0)
            arguments = ['package_local_build.py', '--source-root', str(source), '--build-dir', str(build), '--output-dir', str(root / 'output')]
            # Preserve real execution of the staged --version fixture.
            def version_output(command, **kwargs):
                return 'ubiquitty fixture\n'
            with mock.patch.object(sys, 'argv', arguments), mock.patch.object(packager.subprocess, 'run', stage_install), mock.patch.object(packager.subprocess, 'check_output', version_output):
                packager.main()
            self.assertTrue(all('--build' not in command for command in commands))
            archive = next((root / 'output').glob('*.tar.gz'))
            with tarfile.open(archive) as content:
                self.assertIn('ubiquitty/bin/atlas.spv', content.getnames())
                self.assertIn('ubiquitty/share/doc/ubiquitty/NOTICE', content.getnames())
                self.assertIn('ubiquitty/libexec/sync-omarchy-font.py', content.getnames())
                manifest = json.load(content.extractfile('ubiquitty/manifest.json'))
                self.assertEqual(manifest['configuration'], 'Release')
            self.assertEqual(archive.with_name(archive.name + '.sha256').read_text().split()[0], hashlib.sha256(archive.read_bytes()).hexdigest())

    def test_archive_checksum_is_checked_before_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self.make_bundle(root)
            archive = root / 'fixture.tar.gz'
            with tarfile.open(archive, 'w:gz', compresslevel=1) as output:
                output.add(bundle, arcname='ubiquitty')
            checksum = archive.with_name(archive.name + '.sha256')
            checksum.write_text('0' * 64 + '  fixture.tar.gz\n')
            command = [str(ROOT / 'scripts/install-ubiquitty.sh'), str(archive), '--prefix', str(root / 'prefix')]
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertFalse((root / 'prefix').exists())
            checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  fixture.tar.gz\n')
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertTrue((root / 'prefix/bin/ubiquitty').exists())


if __name__ == '__main__':
    unittest.main()
