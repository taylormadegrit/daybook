#!/usr/bin/env bash
# Universal launcher for Linux & macOS
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
    exec python3 -u "$DIR/arcade.py" "$@"
elif command -v python >/dev/null 2>&1; then
    exec python -u "$DIR/arcade.py" "$@"
else
    echo "Error: Python 3 is required to run 8-Bit Terminal Arcade." >&2
    exit 1
fi
