# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
import configparser
import importlib.util
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import tomllib
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate_themes", ROOT / "scripts/generate-themes.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
THEMES = tomllib.loads((ROOT / "themes/palettes.toml").read_text())["themes"]


class ThemeTests(unittest.TestCase):
    def test_generated_outputs_are_current(self):
        subprocess.run(["python3", ROOT / "scripts/generate-themes.py", "--check"], check=True)

    def test_exact_terminal_palettes(self):
        names = ("black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")
        for theme in THEMES:
            directory = ROOT / "themes" / theme["slug"]
            foot = configparser.ConfigParser()
            foot.read(directory / "foot.ini")
            for section in ("colors-dark", "colors-light"):
                self.assertEqual(foot[section]["foreground"], theme["fg"][1:])
                self.assertEqual(foot[section]["background"], theme["bg"][1:])
                self.assertEqual(foot[section]["cursor"].split()[1], theme["cursor"][1:])
                self.assertEqual(["#" + foot[section][f"{'regular' if i < 8 else 'bright'}{i % 8}"] for i in range(16)], theme["ansi"])
            kitty = dict(line.split(maxsplit=1) for line in (directory / "kitty.conf").read_text().splitlines() if line and not line.startswith("#"))
            self.assertEqual([kitty[f"color{i}"] for i in range(16)], theme["ansi"])
            self.assertEqual(kitty["cursor"], theme["cursor"])
            ghostty = (directory / "ghostty.conf").read_text()
            self.assertEqual(["#" + line.split("=", 2)[2] for line in ghostty.splitlines() if line.startswith("palette = ")], theme["ansi"])
            alacritty = tomllib.loads((directory / "alacritty.toml").read_text())["colors"]
            self.assertEqual([alacritty[section][name] for section in ("normal", "bright") for name in names], theme["ansi"])
            self.assertEqual(alacritty["primary"]["foreground"], theme["fg"])

    def test_semantic_roles_preserve_light_ink_and_exact_palette(self):
        for theme in THEMES:
            colors = tomllib.loads((ROOT / "themes" / theme["slug"] / "colors.toml").read_text())
            self.assertEqual(colors["accent"], theme["ansi"][4])
            self.assertEqual(colors["foreground"], theme["fg"])
            self.assertEqual(colors["light_foreground"], theme["fg"])
            self.assertEqual(colors["selection_foreground"], theme["fg"])
            self.assertEqual(colors["mode"], "dark" if theme["is_dark"] else "light")
            self.assertEqual([colors[f"color{i}"] for i in range(16)], theme["ansi"])
            self.assertEqual(colors["dark_bg"], colors["dark_background"])
            self.assertEqual(colors["purple"], colors["magenta"])
            self.assertEqual(colors["selection"], colors["selection_background"])

    def test_original_backgrounds_are_valid_solid_palette_color(self):
        for theme in THEMES:
            png = (ROOT / "themes" / theme["slug"] / "backgrounds/solid.png").read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            position, compressed = 8, b""
            while position < len(png):
                length = struct.unpack_from(">I", png, position)[0]
                kind = png[position + 4:position + 8]
                payload = png[position + 8:position + 8 + length]
                self.assertEqual(struct.unpack_from(">I", png, position + 8 + length)[0], zlib.crc32(kind + payload))
                if kind == b"IHDR":
                    self.assertEqual(struct.unpack(">IIBBBBB", payload), (64, 64, 8, 2, 0, 0, 0))
                if kind == b"IDAT":
                    compressed += payload
                position += 12 + length
            self.assertEqual(zlib.decompress(compressed), (b"\x00" + bytes.fromhex(theme["bg"][1:]) * 64) * 64)

    def test_installer_copies_without_switching_and_backs_up_changed_themes(self):
        with tempfile.TemporaryDirectory(prefix="noir themes ") as temporary:
            target = Path(temporary) / "omarchy/themes"
            command = ["bash", ROOT / "scripts/install-themes.sh", "--destination", target]
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual((target / "noir/foot.ini").read_bytes(), (ROOT / "themes/noir/foot.ini").read_bytes())
            subprocess.run(command, check=True, capture_output=True)
            self.assertFalse((target.parent / "theme-backups").exists())
            (target / "noir/foot.ini").write_text("user modified palette")
            subprocess.run(command, check=True, capture_output=True)
            backups = list((target.parent / "theme-backups/ubiquitty-omarchy").glob("noir.*/noir/foot.ini"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "user modified palette")
            self.assertEqual((target / "noir/foot.ini").read_bytes(), (ROOT / "themes/noir/foot.ini").read_bytes())
            self.assertFalse((target / "noir/.git").exists())

    def test_only_original_house_palettes_are_carried(self):
        self.assertEqual({theme["name"] for theme in THEMES}, {"Noir", "Noir Clair"})
        self.assertEqual(len(THEMES), 2)
        # Fingerprints of the exact original Core palettes at extraction;
        # avoids duplicating the palette tables as another editable data source.
        original = {
            "Noir": "30de4a813b22ad18e57fcf7bc22ea6351851477c93629bce2bba1efba11f6e5d",
            "Noir Clair": "0371f2d54832becff63fa4233553ef07647bca547b20cac717776a479fcd0032",
        }
        for theme in THEMES:
            values = {key: theme[key] for key in ("name", "is_dark", "ansi", "fg", "bg", "cursor")}
            digest = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            self.assertEqual(digest, original[theme["name"]])
        source = tomllib.loads((ROOT / "themes/palettes.toml").read_text())
        self.assertEqual(source["upstream_path"], "Source/Core/Themes/builtin-themes.toml")
        self.assertEqual(len(source["upstream_commit"]), 40)
        self.assertEqual(len(source["upstream_file_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
