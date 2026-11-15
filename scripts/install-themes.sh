#!/usr/bin/env bash
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
# Install user-owned copies, retaining exact terminal palettes. Never switches theme.
set -euo pipefail
repository=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
destination="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/themes"
case ${1:-} in
  --destination) [[ $# == 2 ]] || { echo 'Usage: install-themes.sh [--destination DIRECTORY]' >&2; exit 2; }; destination=$2 ;;
  -h|--help) echo 'Usage: install-themes.sh [--destination DIRECTORY]'; exit 0 ;;
  '') ;;
  *) echo 'Usage: install-themes.sh [--destination DIRECTORY]' >&2; exit 2 ;;
esac
python3 "$repository/scripts/generate-themes.py" --check
destination=$(realpath -m -- "$destination")
case "$destination/" in /usr/share/omarchy/*) echo 'Refusing to modify packaged Omarchy files.' >&2; exit 1 ;; esac
mkdir -p -- "$destination"
staging=''
trap '[[ -z $staging ]] || rm -rf -- "$staging"' EXIT
for slug in noir noir-clair; do
  source_directory="$repository/themes/$slug"
  target="$destination/$slug"
  if [[ -d $target ]] && diff -qr -- "$source_directory" "$target" >/dev/null; then
    echo "$slug already installed"
    continue
  fi
  staging=$(mktemp -d "$destination/.$slug.install.XXXXXX")
  cp -a -- "$source_directory/." "$staging/"
  if [[ -e $target || -L $target ]]; then
    backup_root="$(dirname -- "$destination")/theme-backups/ubiquitty-omarchy"
    mkdir -p -- "$backup_root"
    backup=$(mktemp -d "$backup_root/$slug.XXXXXX")
    mv -- "$target" "$backup/$slug"
    echo "Previous $slug saved to $backup/$slug"
  fi
  mv -- "$staging" "$target"
  staging=''
  echo "Installed $slug in $target"
done
