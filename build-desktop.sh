#!/bin/bash
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt pyinstaller
.venv/bin/pyinstaller --noconfirm --distpath dist --workpath build tools/brymaps.spec
echo "built dist/BryMaps"
