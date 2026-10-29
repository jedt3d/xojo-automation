# Working on xojo-automation

This repository contains a Xojo development skill, automation helpers, and a
bounded evaluation of XMCP/XDOX. Read `README.md` for scope and
`docs/milestone-1-evaluation.md` before extending an evaluated capability.

- Keep observed results, upstream claims, and untested behavior distinct. Attach
  a source or evidence path to capability claims.
- Before IDE work, read `skills/xojo-automation/references/workflow.md` and
  `diagnostics.md`. Use the shared GUI lease, verify the IDE and exact project,
  and preserve the user's open projects and Agentic Mode setting.
- Use `fixtures/agentic-smoke/AgenticSmoke` for deliberate errors and source
  changes. Stop debugging before editing its manifest. Verify reloads before
  Analyze, Build, or Run. Read its generated `XOJO-CODING.md` too.
- Keep third-party clones, executables, models, doc databases, private notes,
  credentials, and generated builds outside tracked source. Pin tested upstream
  commits/releases in `upstreams.json`; do not silently update them.
- Documentation inputs are installed Xojo docs, read-only. Keep version/platform
  labels and source locations. A missing search result does not prove an API is
  unsupported. Personal conventions do not establish API facts.
- Python helpers use the standard library. Run the affected checks and
  `python3 -m unittest discover -s skills/xojo-automation/tests -v` for harness
  changes. IDE integration claims require a live fixture result.
- For new evidence runs, use a new directory under `evidence/`. Record environment,
  source revisions, inputs, outcomes, limitations, and cleanup. Preserve failed
  and stale-result attempts alongside successful retries.
- The next implementation milestone is not authorized by an evaluation or a
  roadmap entry. Finish the requested scope and report the next boundary.
