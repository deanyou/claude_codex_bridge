from __future__ import annotations

import os
import shlex
import subprocess
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"


def _python310_executable() -> str:
    for candidate in (
        sys.executable,
        "python3.14",
        "python3.13",
        "python3.12",
        "python3.11",
        "python3.10",
        "python3",
        "python",
    ):
        try:
            output = subprocess.check_output(
                [
                    candidate,
                    "-c",
                    "import sys\nif sys.version_info < (3, 10): raise SystemExit(1)\nprint(sys.executable)",
                ],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if output:
            return output
    raise AssertionError("Python 3.10+ is required to test source/dev wrappers")


def _run_source_dev_snippet(tmp_path: Path, shell_body: str) -> subprocess.CompletedProcess[str]:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    python310 = _python310_executable()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "CODEX_INSTALL_PREFIX": str(tmp_path / "managed"),
            "CODEX_BIN_DIR": str(tmp_path / "bin"),
            "CODEX_HOME": str(tmp_path / "codex-home"),
            "CC_BRIDGE_LANG": "en",
            "CC_BRIDGE_SOURCE_KIND": "source",
            "CC_BRIDGE_SOURCE_ROOT": str(REPO_ROOT),
            "CC_BRIDGE_PYTHON_BIN": python310,
        }
    )
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        source {shlex.quote(str(INSTALL_SH))}
        {shell_body}
        """
    )
    return subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )


def test_source_dev_install_links_live_bin_and_ask_skill_asset(tmp_path: Path) -> None:
    completed = _run_source_dev_snippet(
        tmp_path,
        """
        install_bin_links
        verify_installed_entrypoints
        install_codex_skills
        """,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert "OK: Installed entrypoints passed runtime smoke check" in completed.stdout

    bin_dir = tmp_path / "bin"
    cc_bridge_path = bin_dir / "cc_bridge"
    assert cc_bridge_path.exists()
    assert cc_bridge_path.is_symlink()
    assert cc_bridge_path.resolve() == (REPO_ROOT / "cc_bridge").resolve()

    ask_path = bin_dir / "ask"
    assert ask_path.exists()
    assert ask_path.is_symlink()
    assert ask_path.resolve() == (REPO_ROOT / "bin" / "ask").resolve()

    reconnect_path = bin_dir / "codex-reconnect"
    assert reconnect_path.exists()
    assert reconnect_path.is_symlink()
    assert reconnect_path.resolve() == (REPO_ROOT / "bin" / "codex-reconnect").resolve()
    reconnect_version = subprocess.run(
        [str(reconnect_path), "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert reconnect_version.returncode == 0, reconnect_version.stderr
    assert reconnect_version.stdout.strip() == "codex-reconnect 0.3.6"

    ask_skill_md = tmp_path / "codex-home" / "skills" / "ask" / "SKILL.md"
    assert ask_skill_md.is_file()
    assert not ask_skill_md.is_symlink()
    assert "name: ask" in ask_skill_md.read_text(encoding="utf-8")

    cc_bridge_clear_skill_md = tmp_path / "codex-home" / "skills" / "cc_bridge-clear" / "SKILL.md"
    assert cc_bridge_clear_skill_md.is_file()
    assert not cc_bridge_clear_skill_md.is_symlink()
    assert "name: cc_bridge-clear" in cc_bridge_clear_skill_md.read_text(encoding="utf-8")

    cc_bridge_compact_skill_md = tmp_path / "codex-home" / "skills" / "cc_bridge-compact" / "SKILL.md"
    assert cc_bridge_compact_skill_md.is_file()
    assert not cc_bridge_compact_skill_md.is_symlink()
    assert "name: cc_bridge-compact" in cc_bridge_compact_skill_md.read_text(encoding="utf-8")

    cc_bridge_diagnose_skill_md = tmp_path / "codex-home" / "skills" / "cc_bridge-diagnose" / "SKILL.md"
    assert cc_bridge_diagnose_skill_md.is_file()
    assert not cc_bridge_diagnose_skill_md.is_symlink()
    assert "name: cc_bridge-diagnose" in cc_bridge_diagnose_skill_md.read_text(encoding="utf-8")

    reconnect_skill_md = tmp_path / "codex-home" / "skills" / "reconnect" / "SKILL.md"
    assert reconnect_skill_md.is_file()
    assert not reconnect_skill_md.is_symlink()
    assert "name: reconnect" in reconnect_skill_md.read_text(encoding="utf-8")

    skills_dir = tmp_path / "codex-home" / "skills"
    assert not (skills_dir / "cc_bridge-config").exists()
    assert not (skills_dir / "all-plan").exists()
    assert not (skills_dir / "ping").exists()
    assert not (skills_dir / "pend").exists()
    assert not (skills_dir / "file-op").exists()


def test_source_dev_install_ignores_managed_codex_home_for_skill_assets(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    managed_home = (
        tmp_path
        / "project"
        / ".cc-bridge"
        / "agents"
        / "agent2"
        / "provider-state"
        / "codex"
        / "home"
    )
    python310 = _python310_executable()
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home_dir),
            "CODEX_INSTALL_PREFIX": str(tmp_path / "managed"),
            "CODEX_BIN_DIR": str(tmp_path / "bin"),
            "CODEX_HOME": str(managed_home),
            "CC_BRIDGE_LANG": "en",
            "CC_BRIDGE_SOURCE_KIND": "source",
            "CC_BRIDGE_SOURCE_ROOT": str(REPO_ROOT),
            "CC_BRIDGE_PYTHON_BIN": python310,
        }
    )
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        source {shlex.quote(str(INSTALL_SH))}
        install_codex_skills
        """
    )
    completed = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    cc_bridge_clear_skill_md = home_dir / ".codex" / "skills" / "cc_bridge-clear" / "SKILL.md"
    assert cc_bridge_clear_skill_md.is_file()
    assert not cc_bridge_clear_skill_md.is_symlink()
    assert not (home_dir / ".codex" / "skills" / "cc_bridge-config").exists()
    assert not (managed_home / "skills" / "cc_bridge-config").exists()
    assert not (managed_home / "skills" / "cc_bridge-clear").exists()
    assert (home_dir / ".codex" / "skills" / "cc_bridge-compact" / "SKILL.md").is_file()
    assert (home_dir / ".codex" / "skills" / "cc_bridge-diagnose" / "SKILL.md").is_file()


def test_python_selection_falls_back_to_versioned_python_command(tmp_path: Path) -> None:
    home_dir = tmp_path / "home"
    fake_bin = tmp_path / "fake-bin"
    home_dir.mkdir()
    fake_bin.mkdir()
    for name in ("python3", "python3.14", "python3.13", "python3.11", "python3.10"):
        (fake_bin / name).write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
        (fake_bin / name).chmod(0o755)
    (fake_bin / "python3.12").write_text(
        (
            "#!/usr/bin/env bash\n"
            "if [[ \"${1:-}\" == \"-c\" && \"${2:-}\" == *sys.executable* ]]; then\n"
            "  printf '%s\\n' \"$0\"\n"
            "fi\n"
            "exit 0\n"
        ),
        encoding="utf-8",
    )
    (fake_bin / "python3.12").chmod(0o755)
    env = os.environ.copy()
    env.pop("CC_BRIDGE_PYTHON_BIN", None)
    env.update(
        {
            "HOME": str(home_dir),
            "CODEX_INSTALL_PREFIX": str(tmp_path / "managed"),
            "CODEX_BIN_DIR": str(tmp_path / "bin"),
            "CC_BRIDGE_LANG": "en",
        }
    )
    command = textwrap.dedent(
        f"""
        set -euo pipefail
        source {shlex.quote(str(INSTALL_SH))}
        export PATH={shlex.quote(str(fake_bin))}:$PATH
        selected_python_executable
        """
    )

    completed = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert completed.stdout.strip() == str(fake_bin / "python3.12")


def test_claude_route_install_preserves_unmarked_external_rules_file(tmp_path: Path) -> None:
    completed = _run_source_dev_snippet(
        tmp_path,
        """
        mkdir -p "$HOME/.claude/rules"
        printf 'user custom claude rule\\n' > "$HOME/.claude/rules/cc_bridge-config.md"
        export CC_BRIDGE_CLAUDE_MD_MODE=route
        install_claude_md_config
        """,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    external_config = tmp_path / "home" / ".claude" / "rules" / "cc_bridge-config.md"
    assert external_config.read_text(encoding="utf-8") == "user custom claude rule\n"
    assert "Preserved non-CC_BRIDGE external CC_BRIDGE config" in completed.stdout


def test_claude_route_install_removes_marked_external_rules_file(tmp_path: Path) -> None:
    completed = _run_source_dev_snippet(
        tmp_path,
        """
        mkdir -p "$HOME/.claude/rules"
        printf '<!-- CC_BRIDGE_CONFIG_START -->\\nold cc_bridge block\\n<!-- CC_BRIDGE_CONFIG_END -->\\n' > "$HOME/.claude/rules/cc_bridge-config.md"
        export CC_BRIDGE_CLAUDE_MD_MODE=route
        install_claude_md_config
        """,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    external_config = tmp_path / "home" / ".claude" / "rules" / "cc_bridge-config.md"
    assert not external_config.exists()
    assert "Removed CC_BRIDGE-owned external CC_BRIDGE config" in completed.stdout


def test_claude_uninstall_preserves_unmarked_external_rules_file(tmp_path: Path) -> None:
    completed = _run_source_dev_snippet(
        tmp_path,
        """
        mkdir -p "$HOME/.claude/rules"
        printf 'user custom claude rule\\n' > "$HOME/.claude/rules/cc_bridge-config.md"
        uninstall_claude_md_config
        """,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    external_config = tmp_path / "home" / ".claude" / "rules" / "cc_bridge-config.md"
    assert external_config.read_text(encoding="utf-8") == "user custom claude rule\n"
    assert "Preserved non-CC_BRIDGE external CC_BRIDGE config" in completed.stdout


def test_claude_uninstall_removes_marked_external_rules_file(tmp_path: Path) -> None:
    completed = _run_source_dev_snippet(
        tmp_path,
        """
        mkdir -p "$HOME/.claude/rules"
        printf '<!-- CC_BRIDGE_CONFIG_START -->\\nold cc_bridge block\\n<!-- CC_BRIDGE_CONFIG_END -->\\n' > "$HOME/.claude/rules/cc_bridge-config.md"
        uninstall_claude_md_config
        """,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    external_config = tmp_path / "home" / ".claude" / "rules" / "cc_bridge-config.md"
    assert not external_config.exists()
    assert "Removed CC_BRIDGE-owned external CC_BRIDGE config" in completed.stdout
