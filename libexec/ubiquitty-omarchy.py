#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
"""Register Ubiquitty in Omarchy's user menu, or explicitly select it."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile
import time

DESKTOP_ID = "org.ubiquitty.linux.desktop"
MENU_ID = "setup.default.terminal.ubiquitty"


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
        os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def jsonc_tokens(text):
    """Replace comments with spaces while preserving offsets and quoted strings."""
    pattern = r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"') else
                  ''.join('\n' if c == '\n' else ' ' for c in m[0]), text)


def register_menu(path, helper, binary, desktop=None):
    original = path.read_text() if path.exists() else "{\n}\n"
    begin = "  // BEGIN UBIQUITTY TERMINAL\n"
    end = "  // END UBIQUITTY TERMINAL\n"
    text = re.sub(re.escape(begin) + r'[\s\S]*?' + re.escape(end), '', original)
    clean = jsonc_tokens(text)
    # Validate before writing; tolerate JSONC's trailing commas.
    parsed = json.loads(re.sub(r',\s*([}\]])', r'\1', clean))
    if not isinstance(parsed, dict):
        raise ValueError("Omarchy menu extension must be an object")
    if MENU_ID in parsed:
        raise ValueError("an unmanaged Ubiquitty menu entry already exists; preserve it manually")
    closing = clean.rfind('}')
    prefix = text[:closing]
    visible = clean[:closing].rstrip()
    if not visible.endswith(('{', ',')):
        prefix += ','
    action = shlex.quote(str(helper)) + " set-default --binary " + shlex.quote(str(binary))
    if desktop is not None:
        action += " --desktop " + shlex.quote(str(desktop))
    entry = {
        "icon": "", "label": "Ubiquitty",
        "action": action,
        "when": "test -x " + shlex.quote(str(binary)),
        "checked": 'test "$(xdg-terminal-exec --print-id)" = ' + DESKTOP_ID,
    }
    result = prefix.rstrip() + '\n' + begin
    result += '  ' + json.dumps(MENU_ID) + ': ' + json.dumps(entry, ensure_ascii=False) + ',\n' + end
    result += text[closing:]
    if result != original:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + '.bak.' + str(time.time_ns())))
        atomic_write(path, result)


def set_default(config, desktop):
    if not desktop.is_file():
        raise ValueError("install Ubiquitty's desktop entry before selecting it")
    path = config / 'xdg-terminals.list'
    original = path.read_text() if path.exists() else ''
    lines = [line for line in original.splitlines() if line.strip() != DESKTOP_ID]
    updated = DESKTOP_ID + '\n' + '\n'.join(lines) + ('\n' if lines else '')
    if updated != original:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + '.bak.' + str(time.time_ns())))
        atomic_write(path, updated)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['install', 'set-default'])
    parser.add_argument('--binary', type=Path, default=Path(__file__).absolute().parent / 'ubiquitty')
    parser.add_argument('--desktop', type=Path)
    args = parser.parse_args()
    config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    desktop = args.desktop or data / 'applications' / DESKTOP_ID
    binary = args.binary.absolute()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        parser.error('Ubiquitty binary must be installed and executable')
    try:
        if args.command == 'install':
            if not desktop.is_file():
                raise ValueError('desktop entry is missing')
            register_menu(config / 'omarchy/extensions/omarchy-menu.jsonc',
                          Path(__file__).absolute(), binary, desktop)
            print('Ubiquitty added to Omarchy → Setup → Default → Terminal')
        else:
            set_default(config, desktop)
            print('Ubiquitty selected as the default terminal')
    except (ValueError, OSError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
