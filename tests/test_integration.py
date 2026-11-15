#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location('integration', (Path(__file__).resolve().parents[1] / 'libexec').joinpath('ubiquitty-omarchy.py'))
integration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integration)


class IntegrationTests(unittest.TestCase):
    def test_registration_preserves_comments_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'menu.jsonc'
            path.write_text('{\n // keep https://example.com\n "other": {"label":"Keep"},\n}\n')
            integration.register_menu(path, Path('/tmp/helper with spaces'), Path('/tmp/terminal'))
            first = path.read_text()
            integration.register_menu(path, Path('/tmp/helper with spaces'), Path('/tmp/terminal'))
            self.assertEqual(path.read_text(), first)
            self.assertIn('// keep https://example.com', first)
            self.assertIn('"other": {"label":"Keep"}', first)
            self.assertIn("'/tmp/helper with spaces' set-default --binary /tmp/terminal", first)

    def test_empty_and_unterminated_last_entry(self):
        for original in ['{}', '{"other": {"label":"Keep"}}']:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'menu.jsonc'
                path.write_text(original)
                integration.register_menu(path, Path('/helper'), Path('/binary'))
                integration.register_menu(path, Path('/helper'), Path('/binary'))
                self.assertEqual(path.read_text().count('BEGIN UBIQUITTY'), 1)

    def test_terminal_tag_rule_preserves_user_configuration_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hyprland.lua'
            original = '-- personal rules\no.window("other", { float = true })\n'
            path.write_text(original)
            path.chmod(0o640)
            rule = Path(directory) / 'versioned "installation"/ubiquitty-terminal.lua'
            integration.register_terminal_rule(path, rule)
            first = path.read_text()
            integration.register_terminal_rule(path, rule)
            self.assertEqual(path.read_text(), first)
            self.assertIn(original, first)
            self.assertIn('dofile(' + json.dumps(str(rule), ensure_ascii=False) + ')', first)
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)
            integration.register_terminal_rule(path, rule, remove=True)
            removed = path.read_text()
            self.assertIn(original, removed)
            self.assertNotIn('UBIQUITTY TERMINAL RULE', removed)
            integration.register_terminal_rule(path, rule, remove=True)
            self.assertEqual(path.read_text(), removed)

    def test_terminal_tag_rule_matches_only_ubiquitty_and_refuses_partial_markers(self):
        rule = (ROOT / 'libexec/ubiquitty-terminal.lua').read_text()
        self.assertIn('^org\\\\.ubiquitty\\\\.linux$', rule)
        self.assertIn('tag = "+terminal"', rule)
        self.assertNotIn('org.omarchy', rule)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hyprland.lua'
            original = '-- BEGIN UBIQUITTY TERMINAL RULE\n-- unmanaged remainder\n'
            path.write_text(original)
            with self.assertRaises(ValueError):
                integration.register_terminal_rule(path, Path('/rule.lua'))
            self.assertEqual(path.read_text(), original)

    def test_default_preserves_fallbacks_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            desktop = root / integration.DESKTOP_ID
            desktop.touch()
            path = root / 'xdg-terminals.list'
            original = '# personal\nfoot.desktop\nkitty.desktop\n'
            path.write_text(original)
            integration.set_default(root, desktop)
            expected = integration.DESKTOP_ID + '\n' + original
            self.assertEqual(path.read_text(), expected)
            integration.set_default(root, desktop)
            self.assertEqual(path.read_text(), expected)
            self.assertEqual(len(list(root.glob('xdg-terminals.list.bak.*'))), 1)

    def test_font_event_preserves_unrelated_preferences_and_primary_foot_size(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'ubiquitty/config.toml'
            target.parent.mkdir()
            target.write_text('# keep this comment\n[font]\nfamily = "Old"\nsize = 9\nbold_weight = 600\nline_spacing = 0.5\nfeatures = "calt=0"\n[appearance]\npadding = 14\ntheme = "Omarchy"\n')
            foot = root / 'foot/foot.ini'
            foot.parent.mkdir()
            foot.write_text('[main]\nfont=New Nerd Font:size=11.5,Other:size=20\n')
            before = tomllib.loads(target.read_text())
            helper = (Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-font.py')
            env = dict(os.environ, XDG_CONFIG_HOME=str(root))
            family = 'New "Quoted" Nerd Font'
            subprocess.run([sys.executable, str(helper), family], env=env, check=True)
            expected = before.copy()
            expected['font'] = {**before['font'], 'family': family, 'size': 11.5}
            self.assertEqual(tomllib.loads(target.read_text()), expected)
            self.assertIn('# keep this comment', target.read_text())
            first = target.read_bytes()
            subprocess.run([sys.executable, str(helper), family], env=env, check=True)
            self.assertEqual(first, target.read_bytes())

    def test_font_event_without_foot_preserves_size_and_range_maps(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'ubiquitty/config.toml'
            target.parent.mkdir()
            target.write_text('[font]\nsize = 13\nbold_weight = 600\n[font.ranges]\n"U+E000-U+F8FF" = "Symbols Nerd Font Mono"\n')
            before = tomllib.loads(target.read_text())
            subprocess.run([sys.executable, str((Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-font.py')), 'New Family'],
                           env=dict(os.environ, XDG_CONFIG_HOME=str(root)), check=True)
            before['font']['family'] = 'New Family'
            self.assertEqual(tomllib.loads(target.read_text()), before)

    def test_font_event_hook_uses_bash_and_does_not_initialize_at_install(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "release with 'quotes'/ubiquitty-font.py"
            helper.parent.mkdir()
            shutil.copyfile((Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-font.py'), helper)
            target = root / '.config/ubiquitty/config.toml'
            target.parent.mkdir(parents=True)
            target.write_text('[font]\nfamily = "Keep until event"\nbold_weight = 600\n')
            original = target.read_bytes()
            hook = root / '.config/omarchy/hooks/font-set.d/ubiquitty-font'
            env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(root / '.config'))
            subprocess.run([sys.executable, str(helper), '--write-hook', str(hook)], env=env, check=True)
            self.assertEqual(original, target.read_bytes())
            runner = shutil.which('omarchy-hook')
            command = [runner, 'font-set', 'Selected Family'] if runner else ['bash', str(hook), 'Selected Family']
            subprocess.run(command, env=env, check=True)
            self.assertEqual(tomllib.loads(target.read_text())['font'], {'family': 'Selected Family', 'bold_weight': 600})

    def test_font_event_refuses_invalid_config_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'ubiquitty/config.toml'
            target.parent.mkdir()
            target.write_text('[font]\nfamily = "unterminated\n')
            original = target.read_bytes()
            result = subprocess.run([sys.executable, str((Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-font.py')), 'New'],
                                    env=dict(os.environ, XDG_CONFIG_HOME=str(root)), capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(original, target.read_bytes())

    def test_theme_initialization_preserves_typography(self):
        for original in ['', '[font]\nfamily = "JetBrains Mono"\nsize = 11\n',
                         '[appearance]\ntheme = "Other"\nfollow_system = true\n[font]\nsize = 11\n']:
            with self.subTest(original=original), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                palette = root / 'state/omarchy/current/theme/foot.ini'
                palette.parent.mkdir(parents=True)
                colors = ['[colors]', 'foreground=abcdef', 'background=123456']
                colors += [f'{kind}{i}={i:06x}' for kind in ['regular', 'bright'] for i in range(8)]
                palette.write_text('\n'.join(colors))
                config = root / 'config/ubiquitty/config.toml'
                config.parent.mkdir(parents=True)
                config.write_text(original)
                env = dict(os.environ, XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'))
                script = (Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-theme.py')
                subprocess.run([sys.executable, str(script), '--initialize'], env=env, check=True)
                first = config.read_text()
                parsed = tomllib.loads(first)
                self.assertEqual(parsed['appearance']['theme'], 'Omarchy')
                self.assertFalse(parsed['appearance']['follow_system'])
                self.assertEqual(parsed.get('font'), tomllib.loads(original).get('font'))
                subprocess.run([sys.executable, str(script)], env=env, check=True)
                self.assertEqual(config.read_text(), first)

    def test_invalid_menu_is_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'menu.jsonc'
            path.write_text('{bad}')
            with self.assertRaises(ValueError):
                integration.register_menu(path, Path('/helper'), Path('/binary'))
            self.assertEqual(path.read_text(), '{bad}')

    def test_theme_change_uses_the_official_bash_hook_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_root = root / '.config'
            palette = root / 'state/omarchy/current/theme/foot.ini'
            palette.parent.mkdir(parents=True)
            colors = ['[colors-dark]', 'foreground=abcdef', 'background=123456', 'cursor=123456 aabbcc']
            colors += [f'{kind}{i}={i:06x}' for kind in ['regular', 'bright'] for i in range(8)]
            palette.write_text('\n'.join(colors))
            config = config_root / 'ubiquitty/config.toml'
            config.parent.mkdir(parents=True)
            config.write_text('# keep typography\n[font]\nfamily="JetBrains Mono"\nsize=9\nline_spacing=1\n')
            env = dict(os.environ, HOME=str(root), XDG_CONFIG_HOME=str(config_root), XDG_STATE_HOME=str(root / 'state'))
            helper = root / "release with spaces and 'quotes'/libexec/ubiquitty-theme.py"
            helper.parent.mkdir(parents=True)
            shutil.copyfile((Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-theme.py'), helper)
            subprocess.run([sys.executable, str(helper), '--initialize'], env=env, check=True)
            before = tomllib.loads(config.read_text())
            hook = config_root / 'omarchy/hooks/theme-set.d/ubiquitty-theme'
            subprocess.run([sys.executable, str(helper), '--write-hook', str(hook)], env=env, check=True)
            palette.write_text(palette.read_text().replace('foreground=abcdef', 'foreground=fedcba'))
            runner = shutil.which('omarchy-hook')
            command = [runner, 'theme-set', 'tokyo-night'] if runner else ['bash', str(hook), 'tokyo-night']
            subprocess.run(command, env=env, check=True)
            after = tomllib.loads(config.read_text())
            self.assertEqual(after['themes'][0]['fg'], '#fedcba')
            self.assertEqual(after['themes'][0]['cursor'], '#aabbcc')
            self.assertEqual(after['font'], before['font'])
            self.assertIn('# keep typography', config.read_text())

    def test_accent_only_change_updates_the_document_without_changing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palette = root / 'state/omarchy/current/theme/foot.ini'
            palette.parent.mkdir(parents=True)
            colors = ['[colors]', 'foreground=abcdef', 'background=123456']
            colors += [f'{kind}{i}={i:06x}' for kind in ['regular', 'bright'] for i in range(8)]
            palette.write_text('\n'.join(colors))
            desktop = palette.with_name('colors.toml')
            desktop.write_text('accent = "#7aa2f7"\nblue = "#7aa2f7"\n')
            config = root / 'config/ubiquitty/config.toml'
            config.parent.mkdir(parents=True)
            config.write_text('[font]\nsize=9\nline_spacing=1\n')
            env = dict(os.environ, XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'))
            script = (Path(__file__).resolve().parents[1] / 'libexec').joinpath('sync-omarchy-theme.py')
            subprocess.run([sys.executable, str(script), '--initialize'], env=env, check=True)
            original = config.read_text()
            desktop.write_text('accent = "#dcd7ba"\nblue = "#7aa2f7"\n')
            subprocess.run([sys.executable, str(script), 'kanagawa'], env=env, check=True)
            changed = config.read_text()
            self.assertNotEqual(changed, original)
            self.assertIn('# Omarchy accent: #dcd7ba', changed)
            self.assertEqual(tomllib.loads(changed), tomllib.loads(original))


if __name__ == '__main__':
    unittest.main()
