#!/bin/sh
# Mount and use the dedicated test volume in the same WSL invocation namespace.
set -eu
volume=/mnt/d/cursor/datasourceRF/.tmp/pytest/cpi-native-volume-20260908.ext4
target=/home/tywin/.cache/pring-cycle/verification/cpi-native-volume-20260908
python=/home/tywin/.local/share/pring-cycle/dev-venv/bin/python
records=.scratch/pring-data-acquisition-repair/verification-cpi-consumer
test "$(id -u)" = 0
test "$(pwd -P)" = /mnt/d/cursor/datasourceRF
test "$(blkid -p -s TYPE -o value "$volume")" = ext4
test ! -L "$volume"
test ! -L "$target"
if mountpoint -q "$target"; then
    echo 'Dedicated target already mounted; refusing to reuse it' >&2
    exit 1
fi
mount -o loop,nosuid,nodev "$volume" "$target"
trap 'umount "$target"' EXIT
findmnt --target "$target" --output SOURCE,TARGET,FSTYPE,OPTIONS
df -h "$target"
test ! -e "$target/focused-06"
test ! -e "$target/full-04"
test ! -e "$records/source-verified-before.json"
test ! -e "$records/source-verified-after.json"
set -C
runuser -u tywin -- env PYTHONDONTWRITEBYTECODE=1 "$python" \
    .scratch/pring-data-acquisition-repair/verification-catalog/fingerprint.py \
    > "$records/source-verified-before.json"
runuser -u tywin -- env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$python" -m pytest -q -x \
    tests/adapters/test_source_history_acquisition.py::test_valid_history_browser_wrapper_links_original_to_decoded_html \
    tests/integration/test_treasury_csv_acquisition.py::test_later_snapshot_and_failed_request_preserve_prior_treasury_values \
    tests/integration/test_full_run_retrieval.py::test_p2_tushare_failure_or_missing_field_does_not_veto_core_projection \
    tests/models/test_candidate_admission.py -k 'cpi or test_valid_history_browser_wrapper or test_later_snapshot_and_failed_request or test_p2_tushare_failure_or_missing_field' \
    --basetemp="$target/focused-06"
runuser -u tywin -- env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 "$python" -m pytest -q -x \
    --basetemp="$target/full-04"
runuser -u tywin -- env PYTHONDONTWRITEBYTECODE=1 "$python" \
    .scratch/pring-data-acquisition-repair/verification-catalog/fingerprint.py \
    > "$records/source-verified-after.json"
df -h "$target"
