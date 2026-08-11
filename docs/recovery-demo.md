# Reproducible crash-and-resume evidence

CheckpointKit includes an offline integration scenario that demonstrates its core claim with a real child process rather than an in-process exception.

## Run it

From an editable checkout:

```bash
python -m pip install -e ".[dev]"
python examples/crash_resume_demo.py --workspace .checkpointkit-demo --reset
```

The command creates deterministic inputs, runs a clean reference workload, starts an equivalent recoverable workload, waits until exactly five items are durably committed, terminates the child process, and starts a second worker against the same checkpoint.

A successful run prints output similar to:

```text
recovery demo passed: completed_before=5 skipped=5 processed_after=11 duplicates=0
report: .../.checkpointkit-demo/recovery-report.json
```

## Evidence produced

The workspace contains:

```text
.checkpointkit-demo/
├── clean/
│   ├── artifacts.json
│   ├── checkpoint.json
│   ├── events.jsonl
│   ├── inputs/
│   └── outputs/
├── recovered/
│   ├── artifacts.json
│   ├── checkpoint.json
│   ├── events.jsonl
│   ├── inputs/
│   └── outputs/
└── recovery-report.json
```

The report records:

- the controlled interruption point and non-zero child exit code;
- items committed before termination;
- committed items skipped during resume;
- remaining items processed after resume;
- duplicate-processing evidence;
- monotonic checkpoint generations;
- exact artifact verification for clean and recovered outputs;
- byte-for-byte equivalence between the clean and recovered runs;
- elapsed times and paths to supporting evidence.

The report contract is documented by [`recovery-report.schema.json`](recovery-report.schema.json).

## CI evidence

The `recovery` CI matrix runs the same scenario on current GitHub-hosted Linux, Windows, and macOS runners. Each job uploads a uniquely named evidence artifact:

```text
recovery-evidence-linux
recovery-evidence-windows
recovery-evidence-macos
```

The downstream `package` gate cannot pass unless all three recovery jobs, the complete test matrix, and linting pass.

## What this proves

The scenario proves that:

1. item completion is durable before the worker is terminated;
2. a new process can load the same checkpoint;
3. committed items are skipped rather than processed again;
4. remaining items are completed;
5. the final outputs match an uninterrupted clean run;
6. the artifact manifest verifies exactly.

## What this does not prove

The scenario does not restore process memory or the exact CPU instruction at which a process stopped. It also does not make arbitrary remote APIs, database writes, payments, or other external side effects exactly-once. Those operations require application-level idempotency keys or domain transactions.
