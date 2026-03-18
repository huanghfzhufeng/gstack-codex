from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import signal
import socketserver
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "vendor" / "gstack-upstream"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_gstack_codex.py"
FIXTURE_SITE = REPO_ROOT / "tests" / "fixtures" / "site"
EXPECTED_SKILLS = [
    "gstack",
    "gstack-upgrade",
    "gstack-browse",
    "gstack-design-consultation",
    "gstack-design-review",
    "gstack-document-release",
    "gstack-plan-ceo-review",
    "gstack-plan-design-review",
    "gstack-plan-eng-review",
    "gstack-qa",
    "gstack-qa-only",
    "gstack-retro",
    "gstack-review",
    "gstack-setup-browser-cookies",
    "gstack-ship",
]


def with_bun_path(env: dict[str, str] | None = None) -> dict[str, str]:
    merged = dict(env or os.environ)
    bun_bin = str(Path.home() / ".bun" / "bin")
    merged["PATH"] = f"{bun_bin}:{merged.get('PATH', '')}" if merged.get("PATH") else bun_bin
    return merged


def run_cmd(cmd: list[str], *, cwd: Path, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=with_bun_path(),
        check=True,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class GstackCodexPortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory(prefix="gstack-codex-tests.")
        cls.temp_root = Path(cls.tempdir.name)
        cls.codex_home = cls.temp_root / "codex-home"
        cls.project_dir = cls.temp_root / "smoke-project"
        shutil.copytree(FIXTURE_SITE, cls.project_dir)
        run_cmd(["git", "init"], cwd=cls.project_dir, timeout=30)
        cls.sync_result = run_cmd(
            [
                "python3",
                str(SYNC_SCRIPT),
                "--source",
                str(SOURCE_ROOT),
                "--codex-home",
                str(cls.codex_home),
            ],
            cwd=REPO_ROOT,
            timeout=900,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.stop_browse_server()
        cls.tempdir.cleanup()

    @classmethod
    def stop_browse_server(cls) -> None:
        state_file = cls.project_dir / ".gstack" / "browse.json"
        if not state_file.exists():
            return
        try:
            state = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            return
        pid = state.get("pid")
        if not isinstance(pid, int):
            return
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return

    def browse_binary(self) -> Path:
        return self.codex_home / "skills" / ".gstack-native" / "runtime" / "browse" / "dist" / "browse"

    def test_sync_generates_manifest_and_skills(self) -> None:
        manifest_path = self.codex_home / "skills" / ".gstack-native" / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json should be written")
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["source_kind"], "explicit-path")
        self.assertEqual(manifest["source_version"], "0.6.4.0")
        self.assertEqual(manifest["skills"], EXPECTED_SKILLS)

        for skill in EXPECTED_SKILLS:
            skill_dir = self.codex_home / "skills" / skill
            self.assertTrue((skill_dir / "SKILL.md").exists(), f"{skill} SKILL.md missing")
            self.assertTrue((skill_dir / "agents" / "openai.yaml").exists(), f"{skill} openai.yaml missing")

    def test_ui_labels_are_humanized(self) -> None:
        qa_yaml = (self.codex_home / "skills" / "gstack-qa" / "agents" / "openai.yaml").read_text()
        ceo_yaml = (self.codex_home / "skills" / "gstack-plan-ceo-review" / "agents" / "openai.yaml").read_text()
        eng_yaml = (self.codex_home / "skills" / "gstack-plan-eng-review" / "agents" / "openai.yaml").read_text()

        self.assertIn('display_name: "gstack QA"', qa_yaml)
        self.assertIn('display_name: "gstack Plan CEO Review"', ceo_yaml)
        self.assertIn('display_name: "gstack Plan Engineering Review"', eng_yaml)

    def test_browse_smoke_status_goto_text(self) -> None:
        handler = functools.partial(SilentHandler, directory=str(self.project_dir))
        server = socketserver.TCPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_address[1]}/"
            browse = self.browse_binary()
            self.assertTrue(browse.exists(), "browse binary should exist after setup")

            status = run_cmd([str(browse), "status"], cwd=self.project_dir, timeout=120)
            status_output = f"{status.stdout}\n{status.stderr}".lower()
            self.assertIn("healthy", status_output)

            goto = run_cmd([str(browse), "goto", base_url], cwd=self.project_dir, timeout=120)
            self.assertIn("200", goto.stdout)

            text = run_cmd([str(browse), "text"], cwd=self.project_dir, timeout=120)
            self.assertIn("Codex Port Smoke Test", text.stdout)
            self.assertIn("gstack browse", text.stdout.lower())
        finally:
            server.shutdown()
            server.server_close()
            self.stop_browse_server()
