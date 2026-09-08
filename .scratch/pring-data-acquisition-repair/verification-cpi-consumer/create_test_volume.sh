#!/bin/sh
# One-time isolated test storage. No production data or existing volumes are modified.
set -eu
volume=/mnt/d/cursor/datasourceRF/.tmp/pytest/cpi-native-volume-20260908.ext4
target=/home/tywin/.cache/pring-cycle/verification/cpi-native-volume-20260908
test "$(id -u)" = 0
test ! -e "$volume"
test ! -e "$target"
test "$(readlink -f /mnt/d/cursor/datasourceRF)" = /mnt/d/cursor/datasourceRF
mkdir -p /mnt/d/cursor/datasourceRF/.tmp/pytest
# noclobber prevents replacing an existing artifact even after the initial check.
(set -C; : > "$volume")
truncate -s 32G "$volume"
mkfs.ext4 -q -L pring-cpi-test "$volume"
mkdir -m 700 "$target"
mount -o loop,nosuid,nodev "$volume" "$target"
chown 1000:1000 "$target"
findmnt --target "$target" --output SOURCE,TARGET,FSTYPE,OPTIONS
df -h "$target"
losetup --list --output NAME,BACK-FILE
