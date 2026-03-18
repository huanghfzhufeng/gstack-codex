#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent


UPSTREAM_REPO = "https://github.com/garrytan/gstack.git"
UPSTREAM_SKILLS = [
    "browse",
    "design-consultation",
    "design-review",
    "document-release",
    "plan-ceo-review",
    "plan-design-review",
    "plan-eng-review",
    "qa",
    "qa-only",
    "retro",
    "review",
    "setup-browser-cookies",
    "ship",
]

SKILL_UI = {
    "gstack": {
        "display_name": "gstack",
        "short_description": "Choose the right gstack workflow",
        "default_prompt": "Use $gstack to choose the right Codex-native gstack workflow.",
    },
    "gstack-browse": {
        "display_name": "gstack Browse",
        "short_description": "Drive the gstack browser directly",
        "default_prompt": "Use $gstack-browse to drive gstack's fast browser from Codex.",
    },
    "gstack-design-consultation": {
        "display_name": "gstack Design Consultation",
        "short_description": "Build or refresh a design system",
        "default_prompt": "Use $gstack-design-consultation to shape a design system in Codex.",
    },
    "gstack-design-review": {
        "display_name": "gstack Design Review",
        "short_description": "Audit and fix UI design issues",
        "default_prompt": "Use $gstack-design-review to audit and fix UI issues.",
    },
    "gstack-document-release": {
        "display_name": "gstack Document Release",
        "short_description": "Update docs after shipping",
        "default_prompt": "Use $gstack-document-release to update docs after a release.",
    },
    "gstack-plan-ceo-review": {
        "display_name": "gstack Plan CEO Review",
        "short_description": "Rethink scope like a founder",
        "default_prompt": "Use $gstack-plan-ceo-review to pressure-test product scope.",
    },
    "gstack-plan-design-review": {
        "display_name": "gstack Plan Design Review",
        "short_description": "Review a plan through design",
        "default_prompt": "Use $gstack-plan-design-review to critique a plan's design quality.",
    },
    "gstack-plan-eng-review": {
        "display_name": "gstack Plan Engineering Review",
        "short_description": "Review architecture and test plans",
        "default_prompt": "Use $gstack-plan-eng-review to review architecture and implementation details.",
    },
    "gstack-qa": {
        "display_name": "gstack QA",
        "short_description": "Test a site and fix bugs",
        "default_prompt": "Use $gstack-qa to test a site and fix the bugs it finds.",
    },
    "gstack-qa-only": {
        "display_name": "gstack QA Only",
        "short_description": "Test a site without code changes",
        "default_prompt": "Use $gstack-qa-only to test a site and report bugs without editing code.",
    },
    "gstack-retro": {
        "display_name": "gstack Retro",
        "short_description": "Generate an engineering retrospective",
        "default_prompt": "Use $gstack-retro to generate an engineering retrospective.",
    },
    "gstack-review": {
        "display_name": "gstack Review",
        "short_description": "Review a diff before merge",
        "default_prompt": "Use $gstack-review to review the current diff before merging.",
    },
    "gstack-setup-browser-cookies": {
        "display_name": "gstack Setup Browser Cookies",
        "short_description": "Import browser cookies for QA",
        "default_prompt": "Use $gstack-setup-browser-cookies to import browser cookies for QA.",
    },
    "gstack-ship": {
        "display_name": "gstack Ship",
        "short_description": "Run the ship workflow",
        "default_prompt": "Use $gstack-ship to run the structured ship workflow.",
    },
    "gstack-upgrade": {
        "display_name": "gstack Upgrade",
        "short_description": "Refresh the Codex gstack port",
        "default_prompt": "Use $gstack-upgrade to refresh the Codex-native gstack install.",
    },
}

NAME_RE = re.compile(r"^[a-z0-9-]+$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)
PREAMBLE_BLOCK_RE = re.compile(
    r"## Preamble \(run first\)\n\n```bash\n.*?\n```\n",
    re.DOTALL,
)
BROWSE_SETUP_BLOCK_RE = re.compile(
    r"## SETUP \(run this check BEFORE any browse command\)\n\n```bash\n.*?\n```\n",
    re.DOTALL,
)


@dataclass
class SyncContext:
    repo_root: Path | None
    codex_home: Path
    skills_root: Path
    port_root: Path
    runtime_root: Path
    tools_root: Path
    manifest_path: Path


def find_repo_root() -> Path | None:
    script_path = Path(__file__).resolve()
    candidate = script_path.parents[1]
    if (candidate / "vendor" / "gstack-upstream").is_dir():
        return candidate
    return None


def build_context(codex_home_arg: str | None) -> SyncContext:
    codex_home = Path(codex_home_arg).expanduser().resolve() if codex_home_arg else Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser().resolve()
    skills_root = codex_home / "skills"
    port_root = skills_root / ".gstack-native"
    return SyncContext(
        repo_root=find_repo_root(),
        codex_home=codex_home,
        skills_root=skills_root,
        port_root=port_root,
        runtime_root=port_root / "runtime",
        tools_root=port_root / "tools",
        manifest_path=port_root / "manifest.json",
    )


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    bun_bin = str(Path.home() / ".bun" / "bin")
    path_parts = env.get("PATH", "").split(":") if env.get("PATH") else []
    if bun_bin not in path_parts:
        env["PATH"] = ":".join([bun_bin] + path_parts)
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def replace_dir_atomic(src_dir: Path, dest_dir: Path) -> None:
    tmp_dir = dest_dir.with_name(f"{dest_dir.name}.tmp")
    remove_path(tmp_dir)
    src_dir.rename(tmp_dir)
    remove_path(dest_dir)
    tmp_dir.rename(dest_dir)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def block_yaml(value: str) -> str:
    lines = value.splitlines() or [value]
    return "\n".join(f"  {line}" if line else "  " for line in lines)


def quote_yaml(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def parse_upstream_skill(skill_md: Path) -> tuple[str, str, str]:
    text = skill_md.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"Missing YAML frontmatter in {skill_md}")
    frontmatter = match.group(1)
    body = text[match.end():]

    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    if not name_match:
        raise ValueError(f"Missing name in {skill_md}")
    name = name_match.group(1).strip()

    desc_match = re.search(r"^description:\s*\|\s*$", frontmatter, re.MULTILINE)
    if desc_match:
        desc_lines: list[str] = []
        trailing = frontmatter[desc_match.end():].splitlines()
        for line in trailing:
            if line.startswith("  "):
                desc_lines.append(line[2:])
            elif not line.strip() and desc_lines:
                desc_lines.append("")
            else:
                break
        description = "\n".join(desc_lines).strip()
    else:
        inline_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
        description = inline_match.group(1).strip() if inline_match else ""

    return name, description, body


def build_frontmatter(name: str, description: str, *, license_name: str = "MIT") -> str:
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid skill name: {name}")
    return dedent(
        f"""\
        ---
        name: {name}
        description: |
        {block_yaml(description)}
        license: {license_name}
        ---
        """
    )


def render_skill(frontmatter_name: str, description: str, body: str, source_path: Path, repo_root: Path | None) -> str:
    source_label = str(source_path)
    if repo_root:
        try:
            source_label = str(source_path.relative_to(repo_root))
        except ValueError:
            pass
    generated_note = dedent(
        f"""\
        <!-- AUTO-GENERATED by sync_gstack_codex.py -->
        <!-- Source: {source_label} -->
        <!-- Edit upstream gstack or this sync script, then re-run the sync. -->
        """
    ).strip()
    return f"{build_frontmatter(frontmatter_name, description)}{generated_note}\n\n{body.lstrip()}"


def write_openai_yaml(skill_dir: Path, skill_name: str) -> None:
    meta = SKILL_UI[skill_name]
    agents_dir = skill_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    content = dedent(
        f"""\
        interface:
          display_name: {quote_yaml(meta["display_name"])}
          short_description: {quote_yaml(meta["short_description"])}
          default_prompt: {quote_yaml(meta["default_prompt"])}
        policy:
          allow_implicit_invocation: true
        """
    )
    (agents_dir / "openai.yaml").write_text(content)


def validate_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise ValueError(f"SKILL.md missing in {skill_dir}")

    text = skill_md.read_text()
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"Invalid frontmatter in {skill_md}")

    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    if not name_match:
        raise ValueError(f"Missing name in {skill_md}")
    name = name_match.group(1).strip()
    if not NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid skill name {name} in {skill_md}")

    if "description:" not in frontmatter:
        raise ValueError(f"Missing description in {skill_md}")

    openai_yaml = skill_dir / "agents" / "openai.yaml"
    if not openai_yaml.exists():
        raise ValueError(f"agents/openai.yaml missing in {skill_dir}")


def copy_directory(source: Path, target: Path, *, ignore: shutil.IgnorePattern | None = None) -> None:
    if source.is_dir():
        shutil.copytree(source, target, ignore=ignore, copy_function=shutil.copy2)
    else:
        shutil.copy2(source, target)


def patch_runtime_cli(cli_path: Path) -> None:
    cli_text = cli_path.read_text()
    cli_text, spawn_count = re.subn(
        r"""(?ms)^  // Start server as detached background process
  const proc = Bun\.spawn\(\['bun', 'run', SERVER_SCRIPT\], \{
    stdio: \['ignore', 'pipe', 'pipe'\],
    env: \{ \.\.\.process\.env, BROWSE_STATE_FILE: config\.stateFile \},
  \}\);
""",
        dedent(
            """\
              // Start server as a real background process. In Codex we do not keep
              // stdout/stderr pipes attached because Bun may tear the child down when
              // the short-lived CLI exits.
              const proc = Bun.spawn(['bun', 'run', SERVER_SCRIPT], {
                stdio: ['ignore', 'ignore', 'ignore'],
                detached: true,
                env: { ...process.env, BROWSE_STATE_FILE: config.stateFile },
              });
            """
        ),
        cli_text,
        count=1,
    )
    if spawn_count == 0 and "detached: true" not in cli_text:
        raise RuntimeError("Expected browse CLI spawn block not found while applying Codex runtime patch")

    cli_text, _ = re.subn(
        r"""(?ms)^  // Don't hold the CLI open
  proc\.unref\(\);

  // Wait for state file to appear
""",
        "  // Wait for state file to appear\n",
        cli_text,
        count=1,
    )
    cli_text, alive_count = re.subn(
        r"""(?ms)^    if \(state && isProcessAlive\(state\.pid\)\) \{
      return state;
    \}
""",
        dedent(
            """\
                if (state && isProcessAlive(state.pid)) {
                  // Detach only after the background server is confirmed alive.
                  proc.unref();
                  return state;
                }
            """
        ),
        cli_text,
        count=1,
    )
    if alive_count == 0 and "Dettach only after the background server is confirmed alive." not in cli_text and "Detach only after the background server is confirmed alive." not in cli_text:
        raise RuntimeError("Expected browse CLI state confirmation block not found while applying Codex runtime patch")

    cli_text, _ = re.subn(
        r"""(?ms)^  // If we get here, server didn't start in time
  // Try to read stderr for error message
  const stderr = proc\.stderr;
  if \(stderr\) \{
    const reader = stderr\.getReader\(\);
    const \{ value \} = await reader\.read\(\);
    if \(value\) \{
      const errText = new TextDecoder\(\)\.decode\(value\);
      throw new Error\(`Server failed to start:\\n\$\{errText\}`\);
    \}
  \}
  throw new Error\(`Server failed to start within \$\{MAX_START_WAIT / 1000\}s`\);
""",
        "  throw new Error(`Server failed to start within ${MAX_START_WAIT / 1000}s`);\n",
        cli_text,
        count=1,
    )
    cli_path.write_text(cli_text)


def install_tooling(context: SyncContext) -> None:
    build_dir = context.port_root / "tools-build"
    remove_path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), build_dir / "sync_gstack_codex.py")
    replace_dir_atomic(build_dir, context.tools_root)


def copy_runtime(context: SyncContext, source_root: Path, *, skip_setup: bool) -> dict[str, str]:
    runtime_build = context.port_root / "runtime-build"
    remove_path(runtime_build)
    shutil.copytree(
        source_root,
        runtime_build,
        ignore=shutil.ignore_patterns(".git", "node_modules", ".DS_Store", "browse/dist"),
        copy_function=shutil.copy2,
    )
    patch_runtime_cli(runtime_build / "browse" / "src" / "cli.ts")
    replace_dir_atomic(runtime_build, context.runtime_root)

    if skip_setup:
        return {"stdout": "setup skipped", "stderr": ""}

    setup_result = run(["./setup"], cwd=context.runtime_root)
    return {
        "stdout": setup_result.stdout.strip(),
        "stderr": setup_result.stderr.strip(),
    }


def custom_preamble_block() -> str:
    return dedent(
        """\
        ## Preamble (run first)

        ```bash
        _GSTACK_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
        _GSTACK_RUNTIME="$_GSTACK_CODEX_HOME/skills/.gstack-native/runtime"
        _GSTACK_UPDATE="$_GSTACK_RUNTIME/bin/gstack-update-check"
        _GSTACK_CONFIG="$_GSTACK_RUNTIME/bin/gstack-config"
        _UPD=$("$_GSTACK_UPDATE" 2>/dev/null || true)
        [ -n "$_UPD" ] && echo "$_UPD" || true
        mkdir -p ~/.gstack/sessions
        touch ~/.gstack/sessions/"$PPID"
        _SESSIONS=$(find ~/.gstack/sessions -mmin -120 -type f 2>/dev/null | wc -l | tr -d ' ')
        find ~/.gstack/sessions -mmin +120 -type f -delete 2>/dev/null || true
        _CONTRIB=$("$_GSTACK_CONFIG" get gstack_contributor 2>/dev/null || true)
        _BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
        echo "BRANCH: $_BRANCH"
        _LAKE_SEEN=$([ -f ~/.gstack/.completeness-intro-seen ] && echo "yes" || echo "no")
        echo "LAKE_INTRO: $_LAKE_SEEN"
        ```
        """
    )


def custom_browse_setup_block() -> str:
    return dedent(
        """\
        ## SETUP (run this check BEFORE any browse command)

        ```bash
        _ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
        B=""
        [ -n "$_ROOT" ] && [ -x "$_ROOT/.codex/skills/gstack-runtime/browse/dist/browse" ] && B="$_ROOT/.codex/skills/gstack-runtime/browse/dist/browse"
        [ -z "$B" ] && [ -x "${CODEX_HOME:-$HOME/.codex}/skills/.gstack-native/runtime/browse/dist/browse" ] && B="${CODEX_HOME:-$HOME/.codex}/skills/.gstack-native/runtime/browse/dist/browse"
        if [ -x "$B" ]; then
          echo "READY: $B"
        else
          echo "NEEDS_SETUP"
        fi
        ```
        """
    )


def adapt_common_body(body: str) -> str:
    body = body.lstrip()
    body = PREAMBLE_BLOCK_RE.sub(custom_preamble_block(), body, count=1)
    body = BROWSE_SETUP_BLOCK_RE.sub(custom_browse_setup_block(), body, count=1)

    body = body.replace(
        'If output shows `UPGRADE_AVAILABLE <old> <new>`: read `~/.claude/skills/gstack/gstack-upgrade/SKILL.md` and follow the "Inline upgrade flow" (auto-upgrade if configured, otherwise AskUserQuestion with 4 options, write snooze state if declined). If `JUST_UPGRADED <from> <to>`: tell user "Running gstack v{to} (just updated!)" and continue.',
        'If output shows `UPGRADE_AVAILABLE <old> <new>`: read `~/.codex/skills/gstack-upgrade/SKILL.md` and follow the "Inline upgrade flow" section. If `JUST_UPGRADED <from> <to>`: tell the user "Running Codex gstack v{to} (just updated!)" and continue.',
    )
    body = body.replace(
        '2. Run: `cd <SKILL_DIR> && ./setup`',
        '2. Run: `cd "${CODEX_HOME:-$HOME/.codex}/skills/.gstack-native/runtime" && ./setup`',
    )
    body = body.replace(
        "always use the Read tool on the output PNG(s) so the user can see them. Without this, screenshots are invisible.",
        "always open or reference the output PNG(s) explicitly so the user can see them. Without this, screenshots are invisible.",
    )
    body = body.replace("## AskUserQuestion Format", "## User Question Format")
    body = body.replace(
        "**ALWAYS follow this structure for every AskUserQuestion call:**",
        "**When you need user input, ask one direct question using this structure:**",
    )
    body = body.replace(
        "Per-skill instructions may add additional formatting rules on top of this baseline.",
        "Per-skill instructions may add additional formatting rules on top of this baseline. In Codex, prefer concise plain-text questions unless the workflow truly needs a structured decision.",
    )

    replacements = [
        ("AskUserQuestion Q-final", "Question Q-final"),
        ("AskUserQuestion Q2", "Question Q2"),
        ("AskUserQuestion Q1", "Question Q1"),
        ("call AskUserQuestion individually", "ask the user directly, one question at a time"),
        ("Call AskUserQuestion individually", "Ask the user directly, one question at a time"),
        ("use AskUserQuestion", "ask the user directly"),
        ("Use AskUserQuestion", "Ask the user directly"),
        ("AskUserQuestion once per issue", "Ask the user one direct question per issue"),
        ("AskUserQuestion", "direct user question"),
        ("~/.claude/skills/gstack/bin/", "~/.codex/skills/.gstack-native/runtime/bin/"),
        (".claude/skills/gstack/bin/", "~/.codex/skills/.gstack-native/runtime/bin/"),
        ("~/.claude/skills/gstack/browse/dist/browse", "~/.codex/skills/.gstack-native/runtime/browse/dist/browse"),
        (".claude/skills/gstack/browse/dist/browse", "~/.codex/skills/.gstack-native/runtime/browse/dist/browse"),
        ("~/.claude/skills/review/", "~/.codex/skills/gstack-review/"),
        (".claude/skills/review/", "~/.codex/skills/gstack-review/"),
        ("review/TODOS-format.md", "~/.codex/skills/gstack-review/TODOS-format.md"),
        ("review/checklist.md", "~/.codex/skills/gstack-review/checklist.md"),
        ("review/design-checklist.md", "~/.codex/skills/gstack-review/design-checklist.md"),
        ("review/greptile-triage.md", "~/.codex/skills/gstack-review/greptile-triage.md"),
    ]
    for old, new in replacements:
        body = body.replace(old, new)
    return body


def upgrade_skill_body() -> str:
    return dedent(
        """\
        # /gstack-upgrade

        This is the Codex-native upgrade workflow for gstack. Invoke it explicitly with `$gstack-upgrade` when you want to refresh the local Codex port from upstream gstack.

        ## Inline upgrade flow

        This section is referenced by all gstack Codex skills when they detect `UPGRADE_AVAILABLE`.

        ### Step 1: Check whether auto-upgrade is enabled

        ```bash
        _GSTACK_CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
        _GSTACK_RUNTIME="$_GSTACK_CODEX_HOME/skills/.gstack-native/runtime"
        _GSTACK_CONFIG="$_GSTACK_RUNTIME/bin/gstack-config"
        _AUTO=""
        [ "${GSTACK_AUTO_UPGRADE:-}" = "1" ] && _AUTO="true"
        [ -z "$_AUTO" ] && _AUTO=$("$_GSTACK_CONFIG" get auto_upgrade 2>/dev/null || true)
        echo "AUTO_UPGRADE=$_AUTO"
        ```

        If `AUTO_UPGRADE=true` or `AUTO_UPGRADE=1`, skip the question and continue to Step 2.

        Otherwise, ask one direct question:
        - Question: "Codex gstack v{new} is available (you're on v{old}). Upgrade now?"
        - Options:
          - Yes, upgrade now
          - Always keep me up to date
          - Not now
          - Never ask again

        If the user picks "Always keep me up to date", run:

        ```bash
        "${CODEX_HOME:-$HOME/.codex}/skills/.gstack-native/runtime/bin/gstack-config" set auto_upgrade true
        ```

        If the user picks "Not now", write snooze state with escalating backoff:

        ```bash
        _SNOOZE_FILE=~/.gstack/update-snoozed
        _REMOTE_VER="{new}"
        _CUR_LEVEL=0
        if [ -f "$_SNOOZE_FILE" ]; then
          _SNOOZED_VER=$(awk '{print $1}' "$_SNOOZE_FILE")
          if [ "$_SNOOZED_VER" = "$_REMOTE_VER" ]; then
            _CUR_LEVEL=$(awk '{print $2}' "$_SNOOZE_FILE")
            case "$_CUR_LEVEL" in *[!0-9]*) _CUR_LEVEL=0 ;; esac
          fi
        fi
        _NEW_LEVEL=$((_CUR_LEVEL + 1))
        [ "$_NEW_LEVEL" -gt 3 ] && _NEW_LEVEL=3
        echo "$_REMOTE_VER $_NEW_LEVEL $(date +%s)" > "$_SNOOZE_FILE"
        ```

        If the user picks "Never ask again", run:

        ```bash
        "${CODEX_HOME:-$HOME/.codex}/skills/.gstack-native/runtime/bin/gstack-config" set update_check false
        ```

        ### Step 2: Run the Codex-native sync

        ```bash
        python3 "${CODEX_HOME:-$HOME/.codex}/skills/.gstack-native/tools/sync_gstack_codex.py" --upgrade
        ```

        The installed sync tool prefers a locally installed `~/.claude/skills/gstack` source when it exists. If that copy is missing, it clones `https://github.com/garrytan/gstack.git`, refreshes the Codex runtime, regenerates all `gstack-*` skills, and validates the result.

        ### Step 3: Summarize the result

        Tell the user:
        - which upstream source was used
        - the old and new versions
        - that all `gstack-*` Codex skills were regenerated
        - to restart Codex if the skill list does not refresh immediately
        """
    )


def umbrella_skill_body() -> str:
    return dedent(
        """\
        # gstack for Codex

        Use this skill when the user mentions gstack generally, asks what gstack can do in Codex, or wants help choosing the right Codex-native gstack workflow.

        ## Skill map

        - `$gstack-plan-ceo-review`: rethink product scope and find the 10-star version
        - `$gstack-plan-eng-review`: pressure-test architecture, data flow, edge cases, and tests
        - `$gstack-plan-design-review`: audit a plan from a design perspective before implementation
        - `$gstack-design-consultation`: build or refresh a design system
        - `$gstack-review`: do a pre-landing review of the current diff
        - `$gstack-browse`: drive gstack's fast Playwright browser directly
        - `$gstack-qa`: test a web app, fix bugs, and verify the fixes
        - `$gstack-qa-only`: test a web app and report bugs without changing code
        - `$gstack-design-review`: audit a live UI and fix design issues
        - `$gstack-setup-browser-cookies`: import real browser cookies into the gstack browser session
        - `$gstack-ship`: run the structured ship workflow
        - `$gstack-document-release`: update docs after shipping
        - `$gstack-retro`: generate a retrospective from commit history
        - `$gstack-upgrade`: refresh this Codex-native gstack port from upstream
        """
    )


def build_skill_description(skill: str, source_description: str) -> str:
    return f"Codex-native port of gstack's /{skill} workflow. {normalize_whitespace(source_description)}"


def sync_upstream_skill(context: SyncContext, source_root: Path, skill: str) -> None:
    source_dir = source_root / skill
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Missing upstream skill directory: {source_dir}")

    _name, upstream_description, body = parse_upstream_skill(source_dir / "SKILL.md")
    adapted_body = adapt_common_body(body)
    skill_name = f"gstack-{skill}"
    display_intro = (
        f"This is the Codex-native port of gstack's `/{skill}` workflow. "
        f"Invoke it explicitly with `${skill_name}` when you want this exact workflow.\n\n"
    )

    build_dir = context.port_root / "build" / skill_name
    remove_path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    for child in source_dir.iterdir():
        if child.name in {"SKILL.md", "SKILL.md.tmpl", "agents"}:
            continue
        target = build_dir / child.name
        copy_directory(child, target)

    (build_dir / "SKILL.md").write_text(
        render_skill(
            skill_name,
            build_skill_description(skill, upstream_description),
            display_intro + adapted_body,
            source_dir / "SKILL.md",
            context.repo_root,
        )
    )
    write_openai_yaml(build_dir, skill_name)
    validate_skill(build_dir)
    replace_dir_atomic(build_dir, context.skills_root / skill_name)


def sync_custom_skill(context: SyncContext, skill_name: str, description: str, body: str) -> None:
    build_dir = context.port_root / "build" / skill_name
    remove_path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    source_hint = Path(__file__).resolve()
    (build_dir / "SKILL.md").write_text(
        render_skill(skill_name, description, body, source_hint, context.repo_root)
    )
    write_openai_yaml(build_dir, skill_name)
    validate_skill(build_dir)
    replace_dir_atomic(build_dir, context.skills_root / skill_name)


def write_manifest(context: SyncContext, *, source_kind: str, source_path: str, source_version: str, setup_output: dict[str, str]) -> None:
    context.port_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source_kind": source_kind,
        "source_path": source_path,
        "source_version": source_version,
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "runtime_path": str(context.runtime_root),
        "skills": ["gstack", "gstack-upgrade"] + [f"gstack-{skill}" for skill in UPSTREAM_SKILLS],
        "repo_root": str(context.repo_root) if context.repo_root else None,
        "setup_stdout": setup_output["stdout"],
        "setup_stderr": setup_output["stderr"],
    }
    context.manifest_path.write_text(json.dumps(manifest, indent=2))


def current_version(context: SyncContext) -> str | None:
    version_file = context.runtime_root / "VERSION"
    if not version_file.exists():
        return None
    return version_file.read_text().strip() or None


def clone_upstream() -> tuple[Path, Path]:
    tmp_root = Path(tempfile.mkdtemp(prefix="gstack-codex-"))
    clone_dir = tmp_root / "gstack"
    run(["git", "clone", "--depth", "1", UPSTREAM_REPO, str(clone_dir)])
    return tmp_root, clone_dir


def resolve_source(context: SyncContext, explicit_source: str | None) -> tuple[str, Path, Path | None]:
    if explicit_source:
        source_path = Path(explicit_source).expanduser().resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Explicit source does not exist: {source_path}")
        return "explicit-path", source_path, None

    if context.repo_root:
        vendor_source = context.repo_root / "vendor" / "gstack-upstream"
        if vendor_source.exists():
            return "vendor-snapshot", vendor_source.resolve(), None

    claude_source = Path.home() / ".claude" / "skills" / "gstack"
    if claude_source.exists():
        return "claude-install", claude_source.resolve(), None

    tmp_root, clone_dir = clone_upstream()
    return "git-clone", clone_dir.resolve(), tmp_root


def source_version(source_root: Path) -> str:
    version_file = source_root / "VERSION"
    if not version_file.exists():
        return "unknown"
    return version_file.read_text().strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install or refresh the Codex-native gstack port.")
    parser.add_argument("--source", help="Optional source directory. Defaults to vendored upstream, then ~/.claude/skills/gstack, then GitHub.")
    parser.add_argument("--codex-home", help="Override the target CODEX_HOME (defaults to ~/.codex or $CODEX_HOME).")
    parser.add_argument("--upgrade", action="store_true", help="Human-friendly output for upgrade flows.")
    parser.add_argument("--skip-setup", action="store_true", help="Copy files without running ./setup.")
    args = parser.parse_args()

    context = build_context(args.codex_home)
    context.skills_root.mkdir(parents=True, exist_ok=True)
    context.port_root.mkdir(parents=True, exist_ok=True)
    (context.port_root / "build").mkdir(parents=True, exist_ok=True)

    old_version = current_version(context) or "none"
    source_kind = ""
    source_root: Path | None = None
    tmp_root: Path | None = None

    try:
        source_kind, source_root, tmp_root = resolve_source(context, args.source)
        new_version = source_version(source_root)

        install_tooling(context)
        setup_output = copy_runtime(context, source_root, skip_setup=args.skip_setup)

        sync_custom_skill(
            context,
            "gstack",
            "Codex-native umbrella skill for routing between the available gstack workflows in Codex.",
            umbrella_skill_body(),
        )
        sync_custom_skill(
            context,
            "gstack-upgrade",
            "Codex-native upgrade workflow for refreshing the local gstack port and regenerating the installed gstack-* skills.",
            upgrade_skill_body(),
        )
        for skill in UPSTREAM_SKILLS:
            sync_upstream_skill(context, source_root, skill)

        write_manifest(
            context,
            source_kind=source_kind,
            source_path=str(source_root),
            source_version=new_version,
            setup_output=setup_output,
        )
    finally:
        if tmp_root and tmp_root.exists():
            shutil.rmtree(tmp_root)

    generated = ["gstack", "gstack-upgrade"] + [f"gstack-{skill}" for skill in UPSTREAM_SKILLS]
    print(f"Synced Codex gstack from {source_kind}: {source_root}")
    print(f"Version: {old_version} -> {new_version}")
    print("Generated skills:")
    for skill in generated:
        print(f"- {skill}")
    if args.upgrade:
        print("Upgrade complete. Restart Codex if the skill list does not refresh immediately.")
    else:
        print("Sync complete. Restart Codex if the new skills do not appear immediately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
