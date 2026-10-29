# Versioned documentation lookup

Use `scripts/xdox_lookup.py` when a lookup must identify its selected Xojo version,
project type, runtime/server OS and sources. It reads the existing XDOX database
and installed RST files. XDOX continues to own indexing, embeddings and notes.
This adapter adds no database, model, service or persistent MCP configuration.
It is a repository CLI, not a replacement for the XDOX UI or XMCP binary.

## Set up a corpus

Use Python with SQLite FTS5 enabled. The tested XDOX database schema is 5;
missing tables/FTS support fail explicitly rather than creating a replacement index.

Index the intended version in XDOX using the [user guide](user-guide.md). The model
servers can be stopped for this keyword workflow. Register its installed docs:

```sh
python3 scripts/xdox_lookup.py register \
  --database "$HOME/Library/Application Support/dk.o3jvind.xdox/xdox.db" \
  --docs-root "$HOME/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation" \
  --version 2026r3 --output work/docs-registry.json
```

The command records the corpus directory, version label and SHA-256 of
`llms-full.txt`. It refuses to overwrite a registry. Review registrations before
changing them: the label and fingerprint attest your chosen installed snapshot,
not a vendor signature. Queries verify the fingerprint, matching parent-directory
label, and that XDOX has rows for that version. Missing versions fail explicitly;
there is no fallback to the newest corpus or XDOX's active picker.

[The example registry](../examples/docs-registry.json) contains the tested 2026r3
fingerprint and tilde paths for this macOS installation layout. Generate a new
registry for a different snapshot. Relative paths resolve beside the registry;
`~` expands to the current home directory. Multiple installed/indexed versions
can be registered by adding distinct keys under `corpora`, each with its own
label, root and fingerprint. Review each root/hash independently.

## Exact API lookup

```sh
python3 scripts/xdox_lookup.py lookup \
  --registry work/docs-registry.json --version 2026r3 \
  --project-type desktop --platform windows \
  --class-name DesktopButton --member Enabled
```

Pass class and member separately. Exact page names are preferred: `PushButton`
retains its deprecated page, and `Button` retains its cross-control guide. The
adapter does not silently substitute Desktop/Web prefixes or translate API1 names.
When a parent page also documents the member, `also_documented_on_parent` supplies
another source. That field does not claim to identify the original declaration.

For older tutorials, inspect `deprecation_notices`, the current member and
replacement documentation, then the skill's migration/history reference. A
replacement notice alone does not prove that events, signatures or behavior can
be renamed mechanically.

## Keyword retrieval

```sh
python3 scripts/xdox_lookup.py search \
  --registry work/docs-registry.json --version 2026r3 \
  --project-type mobile --platform android \
  --query "Android introspection" --max-results 3
```

This uses XDOX's existing FTS5/BM25 index with an exact `docs_version` SQL filter.
Query words are quoted and ANDed; FTS operators are treated as query text.
It considers at most 200 ranked candidates and returns at most the requested
1–20 results. Known target mismatches are filtered; unknown scope is kept and
labeled. A broad query may exhaust the candidate budget before finding a relevant
target result. No result is evidence of an unsuccessful lookup, not API absence.

Chunk titles locate unique installed source pages. Member labels/section headings
locate the excerpt; split chunks can use a unique normalized source line. Returned
text is from installed RST, and `index_hit` records the ranking chunk and mapping
method. Ambiguous or unresolved mappings are counted and omitted. The adapter
excludes personal notes, MBS and version-independent migration chunks, whose
provenance differs from the selected official corpus. It does not duplicate
XDOX's hybrid, reranker or neighbour-expansion algorithms.

## Read the labels

Every response identifies `corpus`, `target` and the actual execution `host`.
Desktop/Console targets use macOS, Windows or Linux; Mobile uses iOS or Android.
For Web, `platform` means the **server OS**, not the browser/client OS. Browser
compatibility requires its own source review.

Each result includes local file, line range, SHA-256, RST anchor when present,
and compatibility/deprecation source locations. An online URL appears only when
the corresponding HTML page/fragment exists locally. The live website may change;
the local file/hash defines the versioned evidence. `text_truncated` marks the
6,000-character excerpt cap. A reused lookup rejects a changed source file.

| Availability | Meaning |
| --- | --- |
| `documented_compatible` | Recognized page Compatibility table includes the selected target; selected member has no unresolved platform prose |
| `documented_incompatible` | Recognized table excludes the target, or an unambiguous explicit OS-only restriction excludes it |
| `unknown` | Missing/ambiguous source or compatibility, platform-specific prose needing review, guide/history, no match, or request error |

These are documentation classifications, not compilation or execution results.
The prose parser is deliberately limited. It recognizes explicit `OS-only`
restrictions, preserves unknown/negative/conditional wording for review, and
supplies the source. Read platform notes before implementation decisions even
when a broad page table says All. Search responses keep overall availability
`unknown`; individual API hits have their own scoped classification.

Release notes separately identify `historical_release`. A 2024r3 Android fix
retrieved from the 2026r3 corpus is historical evidence, not a current availability
verdict. Deprecated pages retain their notices and are not silently upgraded.

CLI exit `0` means the lookup completed (including `no_match`/`ambiguous`); exit
`1` means invalid scope, missing corpus/index, changed fingerprint/source, or a
read/query error. Always inspect JSON `status` and `availability`.

## Reproduce the benchmark

```sh
python3 scripts/benchmark_docs.py --registry work/docs-registry.json \
  --output work/new-documentation-benchmark
python3 -m unittest discover -s tests -v
```

The output directory must be new. Run without Python `-O`; validation assertions
must remain enabled. The 23 curated cases cover Desktop, Web, Mobile and Console,
macOS/Windows/Linux/iOS/Android labels, inherited members, deprecation, history,
keyword discovery, missing APIs and a missing version. The runner checks target
and corpus labels, expected evidence, file hashes, line ranges, anchors and exact
excerpt bytes. Its exit code is nonzero if any expected outcome fails.

This benchmark runs on one macOS host. It tests retrieval *about* those platforms,
not execution on them. Two-version isolation is additionally covered with
synthetic databases because only 2026r3 is installed/indexed here. See the
[milestone report](milestone-3-documentation.md) for results and remaining work.
