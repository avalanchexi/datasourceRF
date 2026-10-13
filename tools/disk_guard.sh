#!/usr/bin/env bash
# C: drive guard for a heavy run: every 30 s log free space on /mnt/c (the drive that backs the
# WSL disk, not the VHD's own free space); below the floor, TERM the target and exit 2.
#
#   tools/disk_guard.sh <PID> <log> <GB floor> &
#
# Guard the process that grows the disk: for `check.py full` that is the pytest child
# (`pgrep -f 'pytest -q'`), not the flock or `time` wrapper. Floors used so far: 12G for the
# full suite, 20G for a real run. See docs/agents/testing.md (时间与磁盘).
set -u
PID=$1; LOG=$2; FLOOR=$3
while kill -0 "$PID" 2>/dev/null; do
  FREE=$(df -BG /mnt/c | awk 'NR==2{gsub("G","",$4); print $4}')
  echo "$(date '+%F %T') pid=$PID c_free=${FREE}G" >> "$LOG"
  if [ "$FREE" -lt "$FLOOR" ]; then
    echo "$(date '+%F %T') c_free=${FREE}G < ${FLOOR}G: TERM $PID" >> "$LOG"
    kill -TERM "$PID"; exit 2
  fi
  sleep 30
done
echo "$(date '+%F %T') pid=$PID ended; c_free=$(df -BG /mnt/c | awk 'NR==2{print $4}')" >> "$LOG"
