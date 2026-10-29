# Examples And Offline Docs

## Current Example Library

Default root:

```text
/Users/worajedt/xojoexamples
```

The existing converted library snapshot has 444 text projects (it predates 2026r3 and is not proof of current API coverage):

- desktop: 243
- iOS: 74
- web: 60
- Android: 57
- console: 10

Use the generated indexes before opening many files:

- `examples-index.json`: machine-readable project index with platform, tags, manifest shape, notable items, and description snippets.
- `examples-index.md`: human-readable project list.
- `platform-summary.md`: projects grouped by target platform.
- `feature-summary.md`: projects grouped by feature tags.
- `learning-journal.md`: study log and heuristic corrections.

## How To Use Examples

For a task, search the index first:

```bash
python3 - <<'PY'
import json
from pathlib import Path
idx=json.loads(Path('references/examples-index.json').read_text())
for item in idx:
    if 'sqlite' in item['tags'] and item['platform'] == 'desktop':
        print(item['relative_path'], item['descriptions'][:1])
PY
```

Then read only the best matching example files. Prefer examples with matching platform plus matching feature tag.

When a sample, blog, or tutorial comes from an older Xojo release, use `migration-and-older-examples.md` before applying its code. Identify the API generation and exact target; distinguish a still-valid technique from a renamed member, changed behavior, unsupported feature, or workaround superseded by a later fix. The same assessment applies to older snippets embedded in otherwise current official guides.

When a study pass produces a reusable lesson, append a human-readable note to `learning-journal.md`. Record the examples/docs inspected, the lesson learned, and how it changes future Codex behavior.

## Offline Docs

Default docs root:

```text
/Users/worajedt/Library/Application Support/Xojo/Xojo/Xojo 2026r3/Documentation
```

Use `offline-docs-index.md` or `offline-docs-index.json` to find relevant current-version docs. Prefer local docs over web search for Xojo behavior when the docs are present.

The index includes Agentic Mode, all UI component pages, table interfaces, graphics, platform topics, migration/deprecation guides, Web optimization, and all 21 release notes from 2024r1 through 2026r3, alongside IDE Communicator, scripting, databases, and debugging. Use `migration-and-older-examples.md` for history and migration decisions and `2026-changes.md` for current additions; read the exact class/member's compatibility and notes before implementation.

The installed docs also contain later release-note filenames. Their presence does not establish a released version or a supported feature in 2026r3; this skill's reviewed release scope stops at 2026r3. For current examples missing from the converted snapshot, use the IDE's Examples chooser; convert only the needed example under the GUI lease. DBKit v2 has updated Desktop/Web tutorials and a conversion guide under `topics/databases/`.

## Rebuilding Indexes

After examples or docs change:

```bash
python3 scripts/index_xojo_examples.py --append-journal
```

Append to the journal when a study pass changes how the skill should behave.

The early journal entries intentionally preserve heuristic mistakes from the first indexer passes. Treat the latest generated index and the latest explicit journal notes as the current view.
