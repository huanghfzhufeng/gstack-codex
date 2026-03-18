# Notice

This repository contains a Codex-native port of [Garry Tan's `gstack`](https://github.com/garrytan/gstack).

## Upstream Attribution

- Project: `gstack`
- Upstream repository: <https://github.com/garrytan/gstack>
- Upstream author: Garry Tan
- Upstream license: MIT
- Vendored upstream snapshot in this repository: `vendor/gstack-upstream`
- Vendored upstream version at the time of this port snapshot: `0.6.4.0`

The upstream MIT license text is preserved in [LICENSE](LICENSE).

## Port-Specific Changes

This repository adds a Codex integration layer on top of upstream `gstack`, including:

- standalone skill sync and regeneration via `scripts/sync_gstack_codex.py`
- Codex-native `SKILL.md` generation and `agents/openai.yaml` metadata
- humanized UI labels for generated skills
- runtime compatibility fixes for `browse` in Codex
- smoke tests and CI for sync and browser validation

Where practical, upstream workflow bodies are preserved and adapted rather than rewritten from scratch.
