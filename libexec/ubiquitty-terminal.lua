-- Copyright (C) 2026 Stanislav Yaglo
-- SPDX-License-Identifier: Apache-2.0

-- Omarchy's universal clipboard shortcuts choose terminal-safe Ctrl+Shift
-- chords by this tag. Match only the normal Ubiquitty application ID.
o.window("^org\\.ubiquitty\\.linux$", { name = "ubiquitty-terminal", tag = "+terminal" })
