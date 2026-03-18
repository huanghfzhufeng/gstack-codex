from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import signal
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import urllib.request
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPO_ROOT / "vendor" / "gstack-upstream"
SYNC_SCRIPT = REPO_ROOT / "scripts" / "sync_gstack_codex.py"
FIXTURE_SITE = REPO_ROOT / "tests" / "fixtures" / "site"
QA_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "qa_app_buggy"
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


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, *, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for {url}")


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

    def stop_browse_for_project(self, project_dir: Path) -> None:
        state_file = project_dir / ".gstack" / "browse.json"
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

    def test_qa_closed_loop_fix_commit_regression_and_verify(self) -> None:
        node_bin = shutil.which("node")
        if not node_bin:
            self.skipTest("node is required for the QA closed-loop fixture")

        with tempfile.TemporaryDirectory(dir=self.temp_root, prefix="qa-closed-loop.") as temp_project_root:
            project_dir = Path(temp_project_root)
            shutil.copytree(QA_FIXTURE, project_dir / "app", dirs_exist_ok=True)
            project_dir = project_dir / "app"

            run_cmd(["git", "init", "-b", "codex/qa-closed-loop"], cwd=project_dir, timeout=30)
            run_cmd(["git", "config", "user.name", "Codex QA Smoke"], cwd=project_dir, timeout=30)
            run_cmd(["git", "config", "user.email", "qa-smoke@example.com"], cwd=project_dir, timeout=30)
            run_cmd(["git", "add", "."], cwd=project_dir, timeout=30)
            run_cmd(["git", "commit", "-m", "feat: seed qa closed-loop fixture"], cwd=project_dir, timeout=30)

            report_dir = project_dir / ".gstack" / "qa-reports" / "screenshots"
            report_dir.mkdir(parents=True, exist_ok=True)

            port = find_free_port()
            server = subprocess.Popen(
                [node_bin, "server.js"],
                cwd=str(project_dir),
                env={**with_bun_path(), "PORT": str(port)},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            browse = self.browse_binary()
            base_url = f"http://127.0.0.1:{port}/"
            try:
                wait_for_http(base_url)

                before = run_cmd(
                    [str(browse), "goto", base_url],
                    cwd=project_dir,
                    timeout=120,
                )
                self.assertIn("200", before.stdout)
                run_cmd(
                    [str(browse), "snapshot", "-a", "-o", ".gstack/qa-reports/screenshots/issue-001-before.png"],
                    cwd=project_dir,
                    timeout=120,
                )
                run_cmd([str(browse), "click", "#preview-alert"], cwd=project_dir, timeout=120)
                bug_state = run_cmd(
                    [
                        str(browse),
                        "js",
                        "JSON.stringify({text: document.querySelector('#badge-preview')?.textContent, className: document.querySelector('#badge-preview')?.className})",
                    ],
                    cwd=project_dir,
                    timeout=120,
                )
                bug_payload = json.loads(bug_state.stdout.strip())
                self.assertEqual(bug_payload["text"], "Needs attention")
                self.assertEqual(bug_payload["className"], "badge badge--info")
                run_cmd(
                    [str(browse), "snapshot", "-a", "-o", ".gstack/qa-reports/screenshots/issue-001-bug.png"],
                    cwd=project_dir,
                    timeout=120,
                )

                report_path = project_dir / ".gstack" / "qa-reports" / "qa-report-local-qa-fixture-2026-03-18.md"
                report_path.write_text(
                    "# QA Report: QA Closed Loop Fixture\n\n"
                    "## Issues\n\n"
                    "### ISSUE-001: Risk badge stays in info state\n\n"
                    "- Found while clicking `#preview-alert`.\n"
                )

                badge_source = project_dir / "src" / "badge.js"
                badge_text = badge_source.read_text()
                badge_text = badge_text.replace(
                    "    case \"info\":\n      return \"badge badge--info\";\n",
                    "    case \"alert\":\n      return \"badge badge--alert\";\n    case \"info\":\n      return \"badge badge--info\";\n",
                )
                badge_source.write_text(badge_text)

                styles_path = project_dir / "public" / "styles.css"
                styles_text = styles_path.read_text()
                styles_text += (
                    "\n.badge--alert {\n"
                    "  background: rgba(188, 93, 48, 0.18);\n"
                    "  color: var(--accent);\n"
                    "}\n"
                )
                styles_path.write_text(styles_text)

                run_cmd(["git", "add", "src/badge.js", "public/styles.css"], cwd=project_dir, timeout=30)
                run_cmd(
                    ["git", "commit", "-m", "fix(qa): ISSUE-001 — add alert badge state"],
                    cwd=project_dir,
                    timeout=30,
                )

                regression_test = project_dir / "test" / "badge.regression-1.test.js"
                regression_test.write_text(
                    "import test from \"node:test\";\n"
                    "import assert from \"node:assert/strict\";\n\n"
                    "import { badgeClass } from \"../src/badge.js\";\n\n"
                    "// Regression: ISSUE-001 — risky launch badge stayed in the info state\n"
                    "// Found by /qa on 2026-03-18\n"
                    "// Report: .gstack/qa-reports/qa-report-local-qa-fixture-2026-03-18.md\n"
                    "test(\"risky launch badge uses the alert visual state\", () => {\n"
                    "  assert.equal(badgeClass(\"alert\"), \"badge badge--alert\");\n"
                    "});\n"
                )

                run_cmd(["node", "--test", str(regression_test)], cwd=project_dir, timeout=120)
                run_cmd(["git", "add", str(regression_test.relative_to(project_dir))], cwd=project_dir, timeout=30)
                run_cmd(
                    ["git", "commit", "-m", "test(qa): regression test for ISSUE-001 — alert badge state"],
                    cwd=project_dir,
                    timeout=30,
                )

                run_cmd([str(browse), "goto", base_url], cwd=project_dir, timeout=120)
                run_cmd([str(browse), "click", "#preview-alert"], cwd=project_dir, timeout=120)
                after_state = run_cmd(
                    [
                        str(browse),
                        "js",
                        "JSON.stringify({text: document.querySelector('#badge-preview')?.textContent, className: document.querySelector('#badge-preview')?.className})",
                    ],
                    cwd=project_dir,
                    timeout=120,
                )
                fixed_payload = json.loads(after_state.stdout.strip())
                self.assertEqual(fixed_payload["text"], "Needs attention")
                self.assertEqual(fixed_payload["className"], "badge badge--alert")
                run_cmd(
                    [str(browse), "snapshot", "-a", "-o", ".gstack/qa-reports/screenshots/issue-001-after.png"],
                    cwd=project_dir,
                    timeout=120,
                )

                console = run_cmd([str(browse), "console", "--errors"], cwd=project_dir, timeout=120)
                self.assertIn("(no console errors)", console.stdout)

                history = run_cmd(["git", "log", "--format=%s", "-2"], cwd=project_dir, timeout=30)
                commits = history.stdout.strip().splitlines()
                self.assertEqual(
                    commits,
                    [
                        "test(qa): regression test for ISSUE-001 — alert badge state",
                        "fix(qa): ISSUE-001 — add alert badge state",
                    ],
                )
                self.assertTrue((project_dir / ".gstack" / "qa-reports" / "screenshots" / "issue-001-before.png").exists())
                self.assertTrue((project_dir / ".gstack" / "qa-reports" / "screenshots" / "issue-001-after.png").exists())
            finally:
                self.stop_browse_for_project(project_dir)
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
