#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
exec python3 "$(dirname "$0")/build_local_release.py" "$@"
