#!/bin/sh
set -eu
volume=/mnt/d/cursor/datasourceRF/.tmp/pytest/cpi-native-volume-20260908.ext4
target=/home/tywin/.cache/pring-cycle/verification/cpi-native-volume-20260908
python=/home/tywin/.local/share/pring-cycle/dev-venv/bin/python
test "$(id -u)" = 0
test "$(pwd -P)" = /mnt/d/cursor/datasourceRF
test "$(blkid -p -s TYPE -o value "$volume")" = ext4
test ! -L "$volume"
test ! -L "$target"
if mountpoint -q "$target"; then exit 2; fi
mount -o loop,nosuid,nodev "$volume" "$target"
trap 'umount "$target"' EXIT
runuser -u tywin -- env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$python" .scratch/pring-data-acquisition-repair/verify-search-provider-screening.py
