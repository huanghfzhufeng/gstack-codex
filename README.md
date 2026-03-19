# gstack-codex

Codex-native port of Garry Tan's gstack, with a sync pipeline and runtime compatibility fixes for Codex.

> Unofficial port. This repository is not maintained by Garry Tan or the upstream `gstack` project.
>
> Public beta. Core workflows are verified, but this project is still maturing and should be treated as a macOS-first Codex port rather than a fully official upstream-equivalent release.

Upstream project: [garrytan/gstack](https://github.com/garrytan/gstack)

## What This Repository Does

This repo takes the original Claude Code-oriented `gstack` workflows and turns them into first-class Codex skills.

It ships:

- a standalone sync pipeline that regenerates `gstack-*` Codex skills from upstream
- a vendored upstream snapshot for deterministic installs and CI
- Codex-native skill metadata with cleaner UI names like `gstack QA` and `gstack Plan CEO Review`
- a runtime compatibility patch for `browse`, fixing the detached background server behavior in Codex
- smoke tests that verify sync, skill generation, and `browse status/goto/text`
- a closed-loop QA integration test that proves the `/qa` flow can detect a real UI bug, commit the fix, add a regression test, and re-verify the result

## What Changed From Upstream

This port keeps upstream workflow content as intact as possible, but adapts the integration layer for Codex:

- slash-command-centric instructions are rewritten for explicit Codex skill invocation such as `$gstack-review`
- Claude-specific paths and prompts are rewritten to Codex paths and interaction patterns
- generated skills include `agents/openai.yaml` metadata so Codex can surface them cleanly
- the `browse` runtime is patched so Bun does not tear down the background server when the short-lived CLI exits
- the port can sync from a vendored snapshot, a local `~/.claude/skills/gstack` install, or a fresh upstream clone

## Verified Workflows

These workflows have been validated beyond simple file-generation checks:

- `$gstack-review`: exercised on a real Git diff and confirmed to surface actionable review findings
- `$gstack-qa-only`: exercised against a live local web app with browser navigation, screenshots, and a structured QA report
- `$gstack-qa`: covered by a closed-loop integration test that detects a real UI bug, commits a fix, adds a regression test, and re-verifies the repaired UI
- `$gstack-design-review`: exercised against a live local app with fix commits and before/after visual verification
- `$gstack-ship`: exercised through a real GitHub remote, including push and pull request creation

## Known Limitations

- This is an unofficial port, not the upstream `gstack` project.
- It is not yet a 100% parity release with Claude Code behavior or upstream workflow coverage.
- Validation depth is strongest on macOS-first setups.
- Not every `gstack-*` workflow has the same level of end-to-end verification yet.
- New users still need some familiarity with Codex skills, local CLI tooling, and environment setup.

## Support Matrix

| Area | Status | Notes |
|------|--------|-------|
| Codex core skill install/sync | Verified | Covered by integration tests and recent successful CI runs |
| `browse` runtime on macOS | Verified | Primary compatibility target so far |
| `review` / `qa-only` / `qa` / `design-review` / `ship` | Verified | Core workflows have real validation coverage |
| Linux | Limited verification | No dedicated Linux compatibility matrix yet |
| Windows | Not verified | No automated or manual Windows validation yet |
| Node/static web app fixtures | Verified | Used in the live QA and design workflow checks |
| Other stacks (Rails, Python, monorepos, etc.) | Limited verification | Additional real-project coverage is still needed |

## Included Skills

- `$gstack`
- `$gstack-browse`
- `$gstack-design-consultation`
- `$gstack-design-review`
- `$gstack-document-release`
- `$gstack-plan-ceo-review`
- `$gstack-plan-design-review`
- `$gstack-plan-eng-review`
- `$gstack-qa`
- `$gstack-qa-only`
- `$gstack-retro`
- `$gstack-review`
- `$gstack-setup-browser-cookies`
- `$gstack-ship`
- `$gstack-upgrade`

## Requirements

- Codex desktop or Codex CLI
- Git
- [Bun](https://bun.sh/) v1.0+
- Python 3.10+
- Node.js 20+ for the closed-loop `/qa` fixture test

## Install

After cloning this repository, install it into your Codex home with:

```bash
./setup
```

That command is a thin wrapper around:

```bash
python3 scripts/sync_gstack_codex.py
```

To install into a different Codex home:

```bash
./setup --codex-home /path/to/codex-home
```

## Use In Codex

This port uses Codex skill invocation rather than Claude slash commands.

Examples:

- `Use $gstack-review to review the current branch`
- `Use $gstack-qa to test this staging site and fix what it finds`
- `Use $gstack-browse to open https://example.com`
- `Use $gstack-plan-eng-review to pressure-test this implementation plan`
- `Use $gstack-ship to run the release workflow`

## Upgrade From Upstream

To refresh the local Codex port and regenerate all installed skills:

```bash
python3 scripts/sync_gstack_codex.py --upgrade
```

Source resolution order:

1. explicit `--source`
2. vendored snapshot in `vendor/gstack-upstream`
3. local `~/.claude/skills/gstack`
4. fresh clone from `https://github.com/garrytan/gstack.git`

## Development

Install into your own Codex home:

```bash
./setup
```

Run the test suite:

```bash
python3 -m unittest discover -s tests -v
```

The suite now covers:

- sync generation and skill metadata
- `browse` runtime smoke tests
- a closed-loop `/qa` validation on a real JS fixture app:
  detect a bug in the browser, commit a source fix, add a regression test, and verify the repaired UI

Run a one-off sync into a temporary Codex home:

```bash
python3 scripts/sync_gstack_codex.py --source vendor/gstack-upstream --codex-home /tmp/gstack-codex-test-home
```

## Repository Layout

- `scripts/sync_gstack_codex.py`: standalone sync/install pipeline
- `vendor/gstack-upstream`: vendored upstream snapshot used for deterministic regeneration
- `tests/test_port.py`: end-to-end validation for sync and `browse`
- `tests/fixtures/site`: local smoke-test website
- `tests/fixtures/qa_app_buggy`: intentionally buggy fixture app for closed-loop `/qa` validation

## Attribution

This project is a Codex-native port of Garry Tan's `gstack`.

- Upstream repository: [garrytan/gstack](https://github.com/garrytan/gstack)
- Upstream license: MIT
- Attribution details: [NOTICE.md](NOTICE.md)

The upstream MIT license is preserved in [LICENSE](LICENSE).
