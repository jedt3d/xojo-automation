# Scoped documentation lookup

In a xojo-automation checkout, read `docs/documentation-lookup.md` before answering
questions whose Xojo version or target matters. The repository CLI
`scripts/xdox_lookup.py` adds request-level scope and provenance over the existing
XDOX index. It is not bundled as an installed skill-side executable.

1. Select a registered installed/indexed corpus, project type and runtime/server
   OS. Keep the execution host distinct; Web's OS label describes its server.
2. Use exact class/member lookup when known. For discovery, use the existing
   XDOX keyword tier through the adapter. Native XMCP tools retain their original
   scope contract; a docs path alone does not pin their database search version.
3. Cite returned file/line/anchor/hash. An online link is convenient, but its
   current content may differ from the pinned local corpus.
4. Interpret Compatibility tables and member notes together. `unknown`, missing
   results and historical fixes require source review, not an unsupported verdict.
5. For API1 tutorials, inspect current member signatures, deprecation/replacement
   notices and `migration-and-older-examples.md`. Translate only after reviewing
   events and behavior; the tool does not automatically rename APIs.

The benchmark tests documentation retrieval about multiple platforms on one
macOS host. It establishes no target execution or broad semantic-search result.
