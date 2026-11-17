# SPDX-FileCopyrightText: 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OmarchyBuildTests(unittest.TestCase):
    def test_build_overrides_decorated_environment_before_packaging(self):
        builder = load('build_local_release')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            arguments = ['build', '--source-root', str(root / 'source'),
                         '--build-root', str(root / 'build'), '--output-dir', str(root / 'output')]
            with patch.object(sys, 'argv', arguments), patch.dict(os.environ, {'UBIQUITTY_LINUX_CHROMELESS': 'OFF', 'UBIQUITTY_PGO': 'OFF'}), patch.object(builder.subprocess, 'run') as run:
                builder.main()
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args_list[0].args[0], [str(root / 'source/Scripts/build-linux-gtk.sh'), 'Release'])
            for call in run.call_args_list:
                self.assertEqual(call.kwargs['env']['UBIQUITTY_LINUX_CHROMELESS'], 'ON')
                self.assertEqual(call.kwargs['env']['UBIQUITTY_PGO'], 'REQUIRE')
            self.assertIn('package_local_build.py', run.call_args_list[1].args[0][1])

    def test_packaging_rejects_missing_or_disabled_chromeless_before_install(self):
        packager = load('package_local_build')
        for chrome in ['', 'UBIQUITTY_LINUX_CHROMELESS:BOOL=OFF\n']:
            with self.subTest(chrome=chrome), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve()
                build = root / 'build'
                build.mkdir()
                (build / 'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release\n' + chrome)
                arguments = ['package', '--source-root', str(root), '--build-dir', str(build), '--output-dir', str(root / 'output')]
                with patch.object(sys, 'argv', arguments), patch.object(packager.subprocess, 'run') as run:
                    with self.assertRaises(SystemExit) as failure:
                        packager.main()
                    self.assertEqual(failure.exception.code, 2)
                    run.assert_not_called()
                self.assertFalse((root / 'output').exists())


if __name__ == '__main__':
    unittest.main()
