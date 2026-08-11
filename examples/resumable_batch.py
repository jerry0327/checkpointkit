"""Interrupt this script and rerun it; completed items are skipped."""

from __future__ import annotations

import time

from checkpointkit import CheckpointStore

store = CheckpointStore(".checkpointkit/example-batch.json")

for number in range(1, 11):
    key = str(number)
    if store.is_complete(key):
        print(f"skip {number}: already complete")
        continue

    print(f"process {number}")
    time.sleep(0.5)  # Replace this with real work.
    store.mark_complete(key, {"value": number * number})

print("done")
