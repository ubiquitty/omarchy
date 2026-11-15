#!/usr/bin/env python3
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
"""Apply an explicit Omarchy font-set event without replacing other preferences."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shlex
import tempfile
import tomllib


def synchronize_font(family, config_root):
    if not family.strip() or any(character in family for character in '\r\n\x00'):
        raise ValueError('font-set needs a nonempty font family')
    target = config_root / 'ubiquitty/config.toml'
    text = target.read_text() if target.exists() else ''
    before = tomllib.loads(text)
    changes = {'family': family}
    foot = config_root / 'foot/foot.ini'
    if foot.exists():
        match = re.search(r'^\s*font\s*=\s*([^\r\n]*)', foot.read_text(), re.MULTILINE)
        if match:
            # Omarchy preserves the primary font size when replacing its family.
            # A fallback's separate size must not become the terminal's size.
            size_match = re.search(r':size=([0-9.]+)(?:[:\s]|$)', match[1].split(',')[0])
            if size_match:
                size = float(size_match[1])
                if not math.isfinite(size) or size <= 0:
                    raise ValueError('Foot primary font size must be positive and finite')
                changes['size'] = size
    section = re.search(r'^\[font\][ \t]*(?:#[^\n]*)?$', text, re.MULTILINE)
    if section:
        start = section.end()
        following = re.search(r'^\[', text[start:], re.MULTILINE)
        finish = start + following.start() if following else len(text)
        body = text[start:finish]
        for key, value in changes.items():
            assignment = f'{key} = {json.dumps(value, ensure_ascii=False)}'
            pattern = rf'^[ \t]*{key}[ \t]*=.*$'
            if re.search(pattern, body, re.MULTILINE):
                body = re.sub(pattern, lambda _: assignment, body, flags=re.MULTILINE)
            else:
                body = '\n' + assignment + '\n' + body
        updated = text[:start] + body + text[finish:]
    else:
        if 'font' in before:
            raise ValueError('font-set requires a regular [font] table')
        block = '[font]\n' + ''.join(f'{key} = {json.dumps(value, ensure_ascii=False)}\n' for key, value in changes.items())
        updated = block + '\n' + text
    after = tomllib.loads(updated)
    expected = dict(before)
    expected['font'] = {**before.get('font', {}), **changes}
    if after != expected:
        raise ValueError('font-set would change unrelated preferences')
    if updated == text:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.config-', dir=target.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(updated)
        os.chmod(temporary, target.stat().st_mode & 0o777 if target.exists() else 0o644)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-hook', type=Path)
    parser.add_argument('family', nargs='?')
    options = parser.parse_args()
    if options.write_hook:
        helper = shlex.quote(str(Path(__file__).resolve()))
        options.write_hook.parent.mkdir(parents=True, exist_ok=True)
        options.write_hook.write_text(
            '#!/usr/bin/env bash\n'
            '# Copyright (C) 2026 Stanislav Yaglo\n'
            '# SPDX-License-Identifier: Apache-2.0\n'
            f'exec python3 {helper} "$@"\n')
        options.write_hook.chmod(0o755)
        return
    if options.family is None:
        parser.error('font-set needs a font family')
    synchronize_font(options.family, Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))))


if __name__ == '__main__':
    main()
