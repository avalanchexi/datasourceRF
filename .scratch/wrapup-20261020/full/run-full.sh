#!/usr/bin/env bash
# Full suite for the macro follow-ups integration branch (macro-followups), against the copy in dev-venv-mf.
W=/home/tywin/worktrees/datasourceRF-mf
G=/mnt/d/cursor/datasourceRF/.scratch/wrapup-20261020/full
V=$HOME/.local/share/pring-cycle/dev-venv-mf
cd $W
export PYTHONDONTWRITEBYTECODE=1 PATH=$V/bin:$PATH
$V/bin/python tools/clock_check.py > $G/clock.log 2>&1
echo "start $(date '+%F %T') head $(git rev-parse --short HEAD)" > $G/full.meta
( sleep 60; P=$(pgrep -f 'pytest -q' | head -1); echo "pytest_pid=$P" >> $G/full.meta; [ -n "$P" ] && bash tools/disk_guard.sh "$P" $G/guard-full.log 12 ) &
/usr/bin/time -f 'elapsed=%e' flock /tmp/pring-heavy.lock $V/bin/python tools/check.py full > $G/full.log 2>&1
echo "exit=$? end $(date '+%F %T')" >> $G/full.meta
