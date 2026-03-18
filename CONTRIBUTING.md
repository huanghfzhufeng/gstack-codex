# Contributing

## Setup

Requirements:

- Python 3.10+
- Bun 1.0+
- Git

Install the port into your local Codex home:

```bash
./setup
```

## Test

Run the full test suite:

```bash
python3 -m unittest discover -s tests -v
```

The suite validates:

- sync success into an isolated Codex home
- generated skill files and metadata
- `browse status`
- `browse goto`
- `browse text`

## Updating The Upstream Snapshot

If you intentionally refresh the vendored upstream copy:

1. Replace `vendor/gstack-upstream` with the new upstream snapshot.
2. Re-run `python3 scripts/sync_gstack_codex.py --source vendor/gstack-upstream --codex-home <temp-home>`.
3. Run `python3 -m unittest discover -s tests -v`.
4. Review generated skill metadata names and any instruction rewrites.

## Contribution Guidelines

- Keep the port Codex-native rather than layering local one-off hacks on top.
- Prefer adapting the sync pipeline over manually editing generated skills.
- Do not commit `node_modules`, `browse/dist`, `__pycache__`, or local state artifacts.
