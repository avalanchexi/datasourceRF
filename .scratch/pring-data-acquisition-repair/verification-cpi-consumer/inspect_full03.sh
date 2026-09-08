#!/bin/sh
set -eu
volume=/mnt/d/cursor/datasourceRF/.tmp/pytest/cpi-native-volume-20260908.ext4
target=/home/tywin/.cache/pring-cycle/verification/cpi-native-volume-20260908
test "$(id -u)" = 0
test "$(blkid -p -s TYPE -o value "$volume")" = ext4
test ! -L "$volume"
test ! -L "$target"
if mountpoint -q "$target"; then exit 1; fi
mount -o loop,ro,noload,nosuid,nodev "$volume" "$target"
trap 'umount "$target"' EXIT
runuser -u tywin -- /home/tywin/.local/share/pring-cycle/dev-venv/bin/python -B \
    .scratch/pring-data-acquisition-repair/verification-cpi-consumer/inspect_full03.py
