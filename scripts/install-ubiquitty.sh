#!/usr/bin/env bash
# Copyright (C) 2026 Stanislav Yaglo
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
exec python3 "$(dirname "$0")/install_ubiquitty.py" "$@"
