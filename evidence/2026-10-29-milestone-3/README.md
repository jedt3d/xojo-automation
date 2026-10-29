# Milestone-3 evidence

The accepted current-code run is [verified-benchmark/summary.json](verified-benchmark/summary.json):
23/23 curated outcomes against the shipped example registry and installed 2026r3
corpus. Requests, original expectations, returned text/labels/references and
assessments are retained in individual case files.

- `first-benchmark/`: 20/23. Three Console Run expectations were too strong;
  cited OS-specific argument prose correctly produced unknown availability.
- `benchmark/`: 23/23 after source-backed expectation corrections.
- `final-benchmark/`: 23/23 plus before/after DB snapshot checks.
- `pre-final-verification/`: 23/23 before the reused-corpus drift regression.
- `verified-benchmark/`: 23/23 after final structured-error/source-snapshot checks,
  using the shipped tilde-path example registry.
- `native-xmcp.json`: pinned server initialization, actual tool schemas, inherited
  member lookup and Android-history search. No IDE operation was invoked.
- `environment.json`: installed corpus fingerprint, XDOX schema/counts/metadata,
  unavailable model-service probes, benchmark and database read-only checks.
- `tests.txt`: 37 tests (20 documentation plus 17 coordinator).
- `harness-tests.txt`: original 12 harness tests.
- `checks.json` and `manifest.json`: final checks and hashes of delivery inputs.

These results qualify documentation lookup about multiple platforms, executed
on one macOS ARM64 host. They do not qualify those target runtimes, multiple
real installed corpora, hybrid retrieval or reranker quality. No upstream binary,
model, doc database, notes or complete vendor documentation is included.

See [the milestone report](../../docs/milestone-3-documentation.md) for the design,
limits and corrected expectations.
