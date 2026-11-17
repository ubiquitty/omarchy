#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
"""Build the chromeless Omarchy application and package it with its integration."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--build-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    options = parser.parse_args()
    source = options.source_root.resolve()
    build = options.build_root.resolve()
    environment = dict(os.environ, UBQ_BUILD_ROOT=str(build),
                       UBIQUITTY_LINUX_CHROMELESS='ON', UBIQUITTY_PGO='REQUIRE')
    subprocess.run([str(source / 'Scripts/build-linux-gtk.sh'), 'Release'],
                   cwd=source, env=environment, check=True)
    subprocess.run([sys.executable, str(Path(__file__).with_name('package_local_build.py')),
                    '--source-root', str(source), '--build-dir', str(build / 'linux'),
                    '--output-dir', str(options.output_dir.resolve())],
                   cwd=source, env=environment, check=True)


if __name__ == '__main__':
    main()
