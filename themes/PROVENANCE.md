<!-- SPDX-FileCopyrightText: 2026 Stanislav Yaglo -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Noir and Noir Clair

These are Ubiquitty's two original house palettes, by Stanislav Yaglo, licensed
under Apache-2.0. Core's `Source/Core/Themes/theme-credits.md` identifies both
as original work. No adapted third-party schemes are copied here.

`palettes.toml` is the canonical port data. It records the upstream source path,
commit and whole-file SHA-256 at extraction; only the two named palettes are
retained. Refresh explicitly with:

```sh
python3 scripts/generate-themes.py --import-core /path/to/ubiquitty-core/Source/Core/Themes/builtin-themes.toml
```

The 16 ANSI colors, foreground, background and cursor retain their exact source
values. Generated terminal files preserve them independently of Omarchy's stock
templates, which intentionally substitute background for ANSI black and
foreground for ANSI white. This distinction matters particularly for Noir Clair.
Install these directories with `scripts/install-themes.sh`, which makes user-owned
copies without `.git` directories; Omarchy sanitizes terminal files from directly
cloned theme repositories.

Additional desktop roles are derived, not original palette entries: accent is
ANSI blue; surfaces mix background toward foreground by 3%, 6% and 12%; selection
mixes background toward blue by 22%; dim foreground mixes foreground toward
background by 45%; orange aliases yellow, and brown mixes yellow with background
by 50%. The exact derivation is in `scripts/generate-themes.py`. Light-mode
foreground roles use the actual text foreground, never the pale ANSI white.

`backgrounds/solid.png` is an original generated solid-color image matching each
palette's exact background. It contains no downloaded imagery.
