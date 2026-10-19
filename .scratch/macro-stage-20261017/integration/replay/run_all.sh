#!/usr/bin/env bash
# Replay the four original runs in order on the copy (each keeps the one before).
set -u
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
PY=$HOME/.local/share/pring-cycle/dev-venv-ms10/bin/python
for pair in 1014:run-0eb9553118ba92a183b9 1015:run-2b21b77b4968f3bbcfc3 1016:run-151cdf85c10e17a3facd 1019:run-153de3060fa2b0ebc424; do
  day=${pair%%:*}; run=${pair#*:}
  echo "$(date '+%F %T') start $day $run"
  nice -n 19 ionice -c3 "$PY" -I replay_run.py /tmp/pring-ms10-replay /home/tywin/worktrees/datasourceRF-ms "$run" "replay-$day.json" > "replay-$day.log" 2>&1
  echo "$(date '+%F %T') end $day exit=$? $(tail -1 replay-$day.log | cut -c1-120)"
done
echo ALL_DONE
