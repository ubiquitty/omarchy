<!-- SPDX-FileCopyrightText: 2026 Stanislav Yaglo -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Ubiquitty for Omarchy

Omarchy integration, original Noir themes, and distribution tooling for
[Ubiquitty](https://github.com/ubiquitty/ubiquitty).

## Install the themes

```sh
git clone https://github.com/ubiquitty/omarchy.git
cd omarchy
./scripts/install-themes.sh
omarchy theme set noir
# Or: omarchy theme set noir-clair
```

The installer copies both themes into the user's Omarchy theme directory. It
backs up changed copies and does not switch the active theme. Noir is dark;
Noir Clair is light. Both retain Ubiquitty's exact 16 ANSI colors, foreground,
background, and cursor in their terminal configurations. Desktop roles, wallpapers, lock-screen art and previews are generated from those
palettes; Noir also ships NASA's public-domain Webb "Cosmic Cliffs" image as its
first 4K wallpaper.

Use this installer for this multi-theme repository. The installed directories
are user-owned theme copies, preserving their exact terminal palettes.
[Provenance and generation details](themes/PROVENANCE.md) explain the mappings.

## Install Ubiquitty

Given a trusted Linux bundle and its adjacent `.sha256` file:

```sh
./scripts/install-ubiquitty.sh ./ubiquitty-linux-aarch64.tar.gz --omarchy
```

Use the actual archive filename supplied with the release. Architecture and
Release-build metadata are checked before installation. `--prefix` selects a
different installation directory. Add `--default-terminal` to select Ubiquitty;
otherwise the current default is preserved.

For a custom prefix, add its `bin` directory to `PATH` and its `share`
directory to `XDG_DATA_DIRS` so desktop launchers and `xdg-terminal-exec` can
find the installation. For example, with `--prefix "$HOME/apps/ubiquitty"`,
include `$HOME/apps/ubiquitty/bin` and `$HOME/apps/ubiquitty/share` respectively.

If registration or hook installation fails, the installer restores the previous
executable, integration helper, and desktop entry (or removes newly created
entry points on a first install). Complete release directories remain available
because a hook may already refer to them. Omarchy menu entries, copied hooks,
icons, the managed terminal-tag include, and a theme initialization completed before the failure are not rolled
back; rerun installation after correcting the reported error.

Installation keeps complete versioned applications, fonts, shaders, and license
notices together. The public executable is replaced atomically. Existing
processes retain their original resources. Quit all Ubiquitty windows and reopen
to use an updated executable.

Omarchy integration adds Ubiquitty to **Setup → Default → Terminal** and installs
separate theme and font hooks. A managed `dofile` entry in your user
`hypr/hyprland.lua` loads a versioned terminal-tag rule for `org.ubiquitty.linux`.
This makes Omarchy's universal Cmd+C/Cmd+V dispatch terminal-safe
Ctrl+Shift+C/Ctrl+Shift+V; plain Ctrl+C remains interrupt, and copying without a
selection leaves the clipboard unchanged. Existing and future windows receive
the tag after the automatic compositor reload. Other application IDs retain
Omarchy's existing rules. Remove this rule with
`ubiquitty-omarchy remove-terminal-rule`; unrelated Hyprland configuration is
preserved. Theme changes update the managed `Omarchy`
palette. Explicit font changes update the selected family and Foot's primary
point size while preserving weight, line spacing, fallback ranges, and padding.
Per-window application IDs let Omarchy float TUI launches such as btop using
its existing rules.

## Package an existing Release build

Build Ubiquitty from its own repository first, then package the result:

```sh
./scripts/package-local-build.sh \
  --source-root /path/to/ubiquitty \
  --build-dir /path/to/ubiquitty-build/omarchy \
  --output-dir dist
```

Packaging does not compile. It stages the application, resources, icons,
desktop entry, full license notices, and these integration helpers. It writes
an architecture/version manifest, a gzip archive, and a SHA256 checksum.
Compression uses one worker at a low compression level.

The bundle uses the system GTK, Vulkan, and C++ runtime libraries. It is an
Omarchy/Arch Linux distribution bundle, not an AppImage or a cross-distribution
runtime. A bundle from a modified checkout is a development preview; its
manifest records that version identity.

## Development

`libexec/` is the canonical integration implementation. The application
repository can consume this repository as a submodule. Theme data has one
canonical source, `themes/palettes.toml`; generated files are checked with:

```sh
python3 scripts/generate-themes.py --check
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Tests use temporary directories and do not change the active desktop theme or
user configuration. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
