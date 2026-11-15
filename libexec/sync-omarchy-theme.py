#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
"""Keep Ubiquitty's managed palette in step with Omarchy's Foot palette."""
import argparse
import configparser
import os
from pathlib import Path
import re
import shlex
import shutil
import time
import tomllib
import tempfile

arguments = argparse.ArgumentParser(description=__doc__)
operation = arguments.add_mutually_exclusive_group()
operation.add_argument('--initialize', action='store_true', help='select the managed theme, preserving other settings')
operation.add_argument('--write-hook', type=Path, help='write a Bash-compatible Omarchy hook for this installed helper')
arguments.add_argument('theme', nargs='?', help='theme slug supplied by Omarchy')
options = arguments.parse_args()

if options.write_hook:
    # Omarchy runs hooks with Bash, regardless of their executable shebang.
    # Keep the Python implementation separate and point the copied hook at its
    # versioned installation, including prefixes containing shell characters.
    helper = shlex.quote(str(Path(__file__).resolve()))
    options.write_hook.parent.mkdir(parents=True, exist_ok=True)
    options.write_hook.write_text(
        '#!/usr/bin/env bash\n'
        '# Copyright (C) 2026 Stanislav Yaglo\n'
        '# SPDX-License-Identifier: Apache-2.0\n'
        f'exec python3 {helper} "$@"\n')
    options.write_hook.chmod(0o755)
    raise SystemExit(0)

config_root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
state_root = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
source = state_root / 'omarchy/current/theme/foot.ini'
parser = configparser.ConfigParser(interpolation=None)
with source.open() as stream:
    parser.read_file(stream)
colors = parser['colors-dark'] if parser.has_section('colors-dark') else parser['colors']
def color(key):
    value = colors[key].strip().lstrip('#')
    if len(value) != 6 or any(c not in '0123456789abcdefABCDEF' for c in value):
        raise ValueError(f'Invalid Foot color: {key}')
    return '#' + value
ansi = [color(f'regular{i}') for i in range(8)] + [color(f'bright{i}') for i in range(8)]
cursor = colors.get('cursor', colors['foreground']).split()[-1].lstrip('#')
if len(cursor) != 6 or any(c not in '0123456789abcdefABCDEF' for c in cursor):
    raise ValueError('Invalid Foot cursor color')
bg = color('background')
is_dark = sum(int(bg[i:i+2], 16) for i in (1, 3, 5)) < 384
accent = 'unavailable'
try:
    candidate = tomllib.loads(source.with_name('colors.toml').read_text()).get('accent', '')
    if isinstance(candidate, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', candidate):
        accent = candidate.lower()
except (OSError, tomllib.TOMLDecodeError):
    pass
begin = '# BEGIN OMARCHY THEME (managed by theme-set.d/ubiquitty-theme)'
end = '# END OMARCHY THEME'
# Core notifies on every accepted document, including comment-only changes.
# The marker makes an accent-only theme switch wake the existing file watcher;
# the frontend reads the actual desktop accent rather than treating this as a key.
block = '\n'.join([begin, f'# Omarchy accent: {accent}', '[[themes]]', 'name = "Omarchy"', f'is_dark = {str(is_dark).lower()}', 'ansi = [' + ', '.join('"' + c + '"' for c in ansi) + ']', f'fg = "{color("foreground")}"', f'bg = "{bg}"', f'cursor = "#{cursor}"', end])
target = config_root / 'ubiquitty/config.toml'
text = target.read_text() if target.exists() else ''
if text:
    tomllib.loads(text)
updated = text
if begin in updated and end in updated:
    start = updated.index(begin)
    finish = updated.index(end, start) + len(end)
    updated = updated[:start] + block + updated[finish:]
elif options.initialize:
    updated = updated.rstrip() + '\n\n' + block + '\n'
else:
    raise ValueError('Ubiquitty config has no managed Omarchy theme block; run with --initialize')
if options.initialize:
    match = re.search(r'^\[appearance\]\s*$', updated, re.MULTILINE)
    if match:
        start = match.end()
        next_table = re.search(r'^\[', updated[start:], re.MULTILINE)
        finish = start + next_table.start() if next_table else len(updated)
        section = updated[start:finish]
        for key, value in [('theme', '"Omarchy"'), ('follow_system', 'false')]:
            pattern = rf'^{key}\s*=.*$'
            if re.search(pattern, section, re.MULTILINE):
                section = re.sub(pattern, f'{key} = {value}', section, flags=re.MULTILINE)
            else:
                section = '\n' + f'{key} = {value}\n' + section
        updated = updated[:start] + section + updated[finish:]
    else:
        updated = '[appearance]\ntheme = "Omarchy"\nfollow_system = false\n\n' + updated
    tomllib.loads(updated)
if updated != text:
    target.parent.mkdir(parents=True, exist_ok=True)
    if options.initialize and target.exists():
        shutil.copy2(target, target.with_name(target.name + ".bak." + str(time.time_ns())))
    fd, temporary = tempfile.mkstemp(prefix='.config-', dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(updated)
        os.chmod(temporary, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
