# Milestone 3: documentation precision

Implemented and tested on 2026-10-29 against the installed 2026r3 documentation
and XDOX 0.2.0's existing schema-5 index. The upstream pins remain unchanged.
The [lookup guide](documentation-lookup.md) explains setup, commands, labels and
failure handling. No IDE operation or model-service launch was needed.

## Why a read-only adapter

The pinned XMCP `LookupClass` already accepts separate class/member arguments
and extracts documented RST labels. Its `SearchDocs` calls `SemanticSearch`,
which reads `metadata.active_docs_version`; neither tool exposes request-level
version/platform parameters. XDOX owns a versioned `chunks` table and FTS5 index,
but this database contract contains no canonical source file/line/anchor fields.
The installed schema and the actual MCP tools/responses are retained in
[milestone-3 evidence](../evidence/2026-10-29-milestone-3/).

The repository adapter therefore reuses the existing XDOX FTS5 index, adds an
explicit per-request SQL version filter, and resolves the result to installed
RST sources. Exact API lookup follows the already-working member-label approach.
This avoids a second index or search service and works with the released XDOX
binary. It does not patch upstream applications or require MBS development plugins.

Inspect the pinned [XMCP lookup implementation](https://github.com/o3jvind/XMCP/blob/32200c34809e2ae7e218854ac60038a09df30851/src/Tools/LookupClass.xojo_code),
[search implementation](https://github.com/o3jvind/XMCP/blob/32200c34809e2ae7e218854ac60038a09df30851/src/SemanticSearch.xojo_code),
and [XDOX database/retrieval contract](https://github.com/o3jvind/XDOX/blob/7b906d28d0099092207d44de4a7163777bbeaa8d/README.md).
The new behavior belongs to this repository CLI; native XMCP calls retain their
original contracts. No MCP registration or installed personal skill was changed.

## Delivered behavior

- Explicit registered version, project type and runtime/server OS for each request.
  Missing/unindexed versions fail instead of silently changing scope.
- Registered bundle fingerprint and source file hashes/line ranges. Member RST
  labels and verified local HTML fragments supply navigable source references.
- Known-target filtering for search, conservative compatibility classifications,
  deprecation notices and separate historical-release labels.
- Targeted member lookup, supporting parent-member source, and current source
  excerpts located through XDOX chunk titles or unique normalized lines.
- A reproducible 23-case benchmark and synthetic regression tests, including
  two-version isolation while the global picker selects the other version.

## Results

The [accepted current-code benchmark](../evidence/2026-10-29-milestone-3/verified-benchmark/summary.json)
passes **23/23 expected outcomes**: 19 found-result cases,
three no-match cases and one explicit unregistered-version error. Four cases
exercise keyword discovery; the rest exercise exact lookup and scope/error
behavior. These denominators include deliberately negative/unknown answers;
23/23 is contract acceptance, not a general relevance or availability score.

| Coverage | Observed result |
| --- | --- |
| DesktopButton.Enabled on macOS/Windows/Linux | Current member and DesktopUIControl supporting source, with target labels |
| DesktopButton.MacButtonStyle | macOS compatible; Windows/Linux explicitly incompatible in docs |
| ConsoleApplication.Run on three host OSes | Current event source, broad Compatibility table, unknown member availability pending platform prose review |
| MobileButton.Pressed on iOS/Android | Current member, Mobile/All compatibility and separate OS labels |
| WebSession.LazyLoadDependencies | Current experimental-property documentation; Web server context labeled |
| Web API requested for Desktop | Documented project-type mismatch |
| String.Left | Character-oriented member located by exact and keyword lookup |
| PushButton.Action | Deprecated API retained, replacement notice sourced |
| Android introspection history | 2024r3 note retrieved inside 2026r3 corpus; availability unknown |
| Agentic Mode | Current guide and source reference; IDE feature not mistaken for target API |
| Invented class/member/query | No match; availability unknown |
| Missing 2024r1 corpus | Explicit error with requested version/target; no latest-version fallback |

The first benchmark passed 20/23. Its expected Console Run labels incorrectly
assumed a broad page table settled member availability. Source inspection showed
OS-specific encoding/escaping prose; the adapter correctly retained `unknown`.
Those three expectations were corrected with an explicit rationale, and the
original per-case expectations/results are retained under `first-benchmark`.
No code was weakened to make those availability assertions pass.

Regression tests cover request isolation, fingerprint/source drift, read-only DB
access, verified anchors, unsupported target pairs, target filtering, conservative
prose handling, unknown compatibility values, exact-name/no-prefix behavior,
ambiguous pages, parent/deprecation references and unresolved source chunks.
All 20 documentation regression tests pass; the same log includes the 17
milestone-2 coordinator tests. The original 12 harness checks also pass, for
49 automated tests in total. Database bytes, metadata and chunk counts were
unchanged before/after lookup. Both model-service ports remained unavailable;
no server or IDE process was started for documentation lookup.

## Limits and next boundary

Only one real installed/indexed corpus (2026r3) is available. Multiple-version
isolation is synthetic-tested, not qualified against two real Xojo installations.
The benchmark executes on macOS ARM64 and establishes no Windows/Linux/iOS/Android
runtime result. The registry is a reviewed local binding, not vendor attestation.

The tested retrieval tier is keyword BM25. It does not qualify hybrid retrieval,
reranking, broad natural-language relevance, personal notes, MBS or curated
version-independent migration chunks. Unmapped/ambiguous chunks are omitted and
counted; candidate/excerpt limits are explicit. There is no new semantic-search
service or native MCP attachment. Adding these guarantees to the native tools
would require an upstream change or a separately tested MCP adapter.

Compatibility prose remains a source-review task when the parser cannot safely
classify it. Legacy migration still requires member/signature/event review and
release history, not automatic API renaming. The next roadmap boundary is target
execution and packaging; this milestone does not begin it.
