# XMCP and XDOX evaluation

The repository's [milestone report](../../../docs/milestone-1-evaluation.md)
and [evidence manifest](../../../evidence/2026-10-29/manifest.json) are the source
of truth for the 2026r3 macOS ARM64 evaluation. Upstream revisions are pinned in
`../../../upstreams.json`. Other host/target combinations remain untested here.

- Reuse XMCP/XDOX before replacing their IDE or documentation capabilities.
- Inspect `tools/list` on the actual binary. The evaluated XMCP supports
  `lookup_class` with separate `class_name` and `member` arguments; default
  output is a summary, and `full=true` explicitly requests the raw page.
- Query version labels come from XDOX's active DB version. An explicit docs
  path alone does not pin database search to that version.
- All source chunks must be indexed/embedded before assessing semantic coverage;
  model-server health alone is insufficient. Reranker readiness is separate.
- Coordinate the watcher, exact project/IDE, shared lease, and operation order.
  The evaluation observed stale diagnostics when a command preceded reload.
- Poll for fresh run output. The Run acknowledgment preceded exception-log
  creation in a tested case. `get_debug_log` requires application-side logging
  and reads a global temporary file; it is not live debugger variable access.
- The repository harness corrects ProjectShellPath comparison for observed shell
  escaping. It still does not verify watcher completion or orchestrate all MCP
  clients. Unit tests do not establish cross-platform qualification.
- Keep local execution, architecture presence, signature verification, and
  distribution readiness as separate results.
