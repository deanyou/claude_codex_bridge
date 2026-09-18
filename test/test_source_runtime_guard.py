from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CC_BRIDGE = REPO_ROOT / "cc_bridge.py"
CC_BRIDGE_TEST = REPO_ROOT / "cc_bridge_test"


def _run_source_cc_bridge(args: list[str], *, cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("CC_BRIDGE_SOURCE_RUNTIME_OK", None)
    env.pop("CC_BRIDGE_SOURCE_ALLOWED_ROOTS", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CC_BRIDGE), *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _run_cc_bridge_test(args: list[str], *, cwd: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("CC_BRIDGE_SOURCE_RUNTIME_OK", None)
    env.pop("CC_BRIDGE_SOURCE_ALLOWED_ROOTS", None)
    env.pop("CC_BRIDGE_TEST_ROOTS", None)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CC_BRIDGE_TEST), *args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_source_cc_bridge_allows_introspection_outside_test_roots() -> None:
    proc = _run_source_cc_bridge(["--print-version"], cwd=REPO_ROOT)

    assert proc.returncode == 0
    assert proc.stdout.strip()


def test_source_cc_bridge_rejects_stateful_commands_outside_test_roots() -> None:
    proc = _run_source_cc_bridge(["doctor"], cwd=REPO_ROOT)

    assert proc.returncode == 1
    assert "Refusing to run the CC_BRIDGE source checkout outside an allowed test project" in proc.stderr
    assert (
        "Use `/home/bfly/yunwei/cc_bridge_source/cc_bridge_test` from "
        "`/home/bfly/yunwei/test_ccb2` for source-change validation"
    ) in proc.stderr


def test_source_cc_bridge_default_allowed_roots_are_dedicated_test_project_only() -> None:
    proc = _run_source_cc_bridge(["doctor"], cwd=REPO_ROOT)

    allowed_line = next(line for line in proc.stderr.splitlines() if line.startswith("Allowed source roots:"))
    roots = [item.strip() for item in allowed_line.split(":", 1)[1].split(",")]
    assert roots == [str(REPO_ROOT.parent / "test_ccb2")]


def test_source_cc_bridge_rejects_legacy_sibling_project_arg_without_override() -> None:
    legacy_project = REPO_ROOT.parent / "test_cc_bridge"

    proc = _run_source_cc_bridge(["--project", str(legacy_project), "doctor"], cwd=REPO_ROOT)

    assert proc.returncode == 1
    assert "Refusing to run the CC_BRIDGE source checkout outside an allowed test project" in proc.stderr
    assert f"Allowed source roots: {REPO_ROOT.parent / 'test_ccb2'}" in proc.stderr


def test_source_cc_bridge_rejects_legacy_named_external_cwd_without_override(tmp_path: Path) -> None:
    legacy_named_project = tmp_path / "test_cc_bridge"
    legacy_named_project.mkdir()

    proc = _run_source_cc_bridge(["doctor"], cwd=legacy_named_project)

    assert proc.returncode == 1
    assert "Refusing to run the CC_BRIDGE source checkout outside an allowed test project" in proc.stderr
    assert f"Allowed source roots: {REPO_ROOT.parent / 'test_ccb2'}" in proc.stderr


def test_source_cc_bridge_allows_stateful_commands_under_configured_test_root(tmp_path: Path) -> None:
    allowed = tmp_path / "test-project"
    project = allowed / "repo"
    project.mkdir(parents=True)
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_source_cc_bridge(
        ["config", "validate"],
        cwd=project,
        extra_env={"CC_BRIDGE_SOURCE_ALLOWED_ROOTS": str(allowed)},
    )

    assert proc.returncode == 0
    assert "config_status: valid" in proc.stdout


def test_source_cc_bridge_allows_project_arg_under_configured_test_root_from_source_cwd(tmp_path: Path) -> None:
    allowed = tmp_path / "test-project"
    project = allowed / "repo"
    project.mkdir(parents=True)
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_source_cc_bridge(
        ["--project", str(project), "config", "validate"],
        cwd=REPO_ROOT,
        extra_env={"CC_BRIDGE_SOURCE_ALLOWED_ROOTS": str(allowed)},
    )

    assert proc.returncode == 0
    assert "config_status: valid" in proc.stdout


def test_source_cc_bridge_explicit_override_allows_one_off_run(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_source_cc_bridge(["config", "validate"], cwd=project, extra_env={"CC_BRIDGE_SOURCE_RUNTIME_OK": "1"})

    assert proc.returncode == 0
    assert "config_status: valid" in proc.stdout


def test_cc_bridge_test_rejects_source_checkout_cwd() -> None:
    proc = _run_cc_bridge_test(["doctor"], cwd=REPO_ROOT)

    assert proc.returncode == 1
    assert "Refusing to run `cc_bridge_test` from the CC_BRIDGE source checkout" in proc.stderr
    assert "cd /home/bfly/yunwei/test_ccb2 && /home/bfly/yunwei/cc_bridge_source/cc_bridge_test config validate" in proc.stderr


def test_cc_bridge_test_rejects_external_project_without_allowed_root(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_cc_bridge_test(["config", "validate"], cwd=project)

    assert proc.returncode == 1
    assert "Refusing to run `cc_bridge_test` outside an allowed source-test project" in proc.stderr
    assert f"Allowed source-test roots: {REPO_ROOT.parent / 'test_ccb2'}" in proc.stderr


def test_cc_bridge_test_allows_external_project_with_explicit_test_root(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_cc_bridge_test(["config", "validate"], cwd=project, extra_env={"CC_BRIDGE_TEST_ROOTS": str(tmp_path)})

    assert proc.returncode == 0
    assert "config_status: valid" in proc.stdout


def test_cc_bridge_test_allows_external_project_with_explicit_source_allowed_root(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_cc_bridge_test(["config", "validate"], cwd=project, extra_env={"CC_BRIDGE_SOURCE_ALLOWED_ROOTS": str(tmp_path)})

    assert proc.returncode == 0
    assert "config_status: valid" in proc.stdout


def test_cc_bridge_test_rejects_legacy_sibling_project_arg_without_override(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    legacy_project = REPO_ROOT.parent / "test_cc_bridge"

    proc = _run_cc_bridge_test(["--project", str(legacy_project), "doctor"], cwd=external)

    assert proc.returncode == 1
    assert "Refusing to run `cc_bridge_test` outside an allowed source-test project" in proc.stderr
    assert f"Checked project path: {legacy_project}" in proc.stderr


def test_cc_bridge_test_allows_project_arg_under_explicit_test_root(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    project = allowed / "repo"
    external = tmp_path / "external"
    project.mkdir(parents=True)
    external.mkdir()
    (project / ".cc-bridge").mkdir()
    (project / ".cc-bridge" / "cc_bridge.config").write_text("cmd; agent1:codex\n", encoding="utf-8")

    proc = _run_cc_bridge_test(
        ["--project", str(project), "config", "validate"],
        cwd=external,
        extra_env={"CC_BRIDGE_TEST_ROOTS": str(allowed)},
    )

    assert proc.returncode == 0
    assert "config_status: valid" in proc.stdout


def test_cc_bridge_test_rejects_project_arg_inside_source_checkout(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()

    proc = _run_cc_bridge_test(["--project", str(REPO_ROOT), "doctor"], cwd=external)

    assert proc.returncode == 1
    assert "Refusing to run `cc_bridge_test` against a project inside the CC_BRIDGE source checkout" in proc.stderr


def test_cc_bridge_test_diagnose_reports_wrapper_roots_and_allowance(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()

    proc = _run_cc_bridge_test(["--diagnose"], cwd=project)

    assert proc.returncode == 0
    assert f"wrapper: {CC_BRIDGE_TEST}" in proc.stdout
    assert f"source_cc_bridge: {CC_BRIDGE}" in proc.stdout
    assert f"cwd: {project}" in proc.stdout
    assert f"default_roots: {REPO_ROOT.parent / 'test_ccb2'}" in proc.stdout
    assert f"effective_roots: {REPO_ROOT.parent / 'test_ccb2'}" in proc.stdout
    assert "allowed_source_test_project: no" in proc.stdout


def test_cc_bridge_test_diagnose_reports_explicit_allowed_root(tmp_path: Path) -> None:
    project = tmp_path / "repo"
    project.mkdir()

    proc = _run_cc_bridge_test(["diagnose"], cwd=project, extra_env={"CC_BRIDGE_TEST_ROOTS": str(tmp_path)})

    assert proc.returncode == 0
    assert f"env_CC_BRIDGE_TEST_ROOTS: {tmp_path}" in proc.stdout
    assert f"checked_paths: {project}" in proc.stdout
    assert "allowed_source_test_project: yes" in proc.stdout


def test_cc_bridge_test_accepts_only_fresh_well_formed_benchmark_trace_envelope() -> None:
    namespace = runpy.run_path(str(CC_BRIDGE_TEST))
    entry_ns = namespace["_CC_BRIDGE_TEST_PROCESS_ENTRY_NS"]
    validate = namespace["_valid_startup_trace_envelope"]
    valid = {
        "CC_BRIDGE_STARTUP_TIMING_TRACE": "1",
        "CC_BRIDGE_STARTUP_TRACE_ID": "trace_" + "a" * 32,
        "CC_BRIDGE_STARTUP_TRACE_SPAWN_NS": str(entry_ns - 1),
    }

    assert validate(valid) is True
    assert validate({**valid, "CC_BRIDGE_STARTUP_TRACE_ID": "trace_invalid"}) is False
    assert validate({**valid, "CC_BRIDGE_STARTUP_TRACE_SPAWN_NS": str(entry_ns + 1)}) is False
    assert validate({**valid, "CC_BRIDGE_STARTUP_TRACE_WRAPPER_ENTRY_NS": "1"}) is False
