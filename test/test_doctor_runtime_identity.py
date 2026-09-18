from __future__ import annotations

from pathlib import Path

from cli.render_runtime.ops_views_doctor import render_doctor
from cli.services.doctor_runtime import cc_bridge_daemon, system


def test_runtime_identity_summary_reports_root_project_owner_warning(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    cc_bridge_dir = project_root / ".cc-bridge"
    install_dir = tmp_path / "install"
    cc_bridge_dir.mkdir(parents=True)
    install_dir.mkdir()

    monkeypatch.setattr(system, "_effective_uid", lambda: 0)
    monkeypatch.setattr(system, "_user_name", lambda uid: "root" if uid == 0 else "demo")

    def fake_path_owner(path: Path):
        if path == project_root or path == cc_bridge_dir:
            return {"uid": 1000, "name": "demo"}
        if path == install_dir:
            return {"uid": 0, "name": "root"}
        return None

    monkeypatch.setattr(system, "_path_owner", fake_path_owner)

    payload = system.runtime_identity_summary(
        project_root,
        cc_bridge_dir=cc_bridge_dir,
        installation={
            "path": str(install_dir),
            "root_install": True,
            "install_user_id": "0",
            "install_user_name": "root",
            "sudo_user": "demo",
        },
    )

    assert payload["user_id"] == 0
    assert payload["user_name"] == "root"
    assert payload["root_runtime"] is True
    assert payload["install_root_owned"] is True
    assert payload["project_owner"] == "1000:demo"
    assert payload["cc_bridge_dir_owner"] == "1000:demo"
    assert payload["install_owner"] == "0:root"
    assert payload["sudo_user"] == "demo"
    assert payload["warnings"] == (
        "Running CC_BRIDGE as root in a non-root-owned project can create root-owned .cc-bridge files.",
    )


def test_render_doctor_includes_root_runtime_identity_lines() -> None:
    payload = {
        "project": "/tmp/repo",
        "project_id": "proj-1",
        "installation": {
            "path": "/tmp/install",
            "install_mode": "release",
            "source_kind": "release",
            "version": "7.2.1",
            "channel": "stable",
            "build_time": "2026-06-03T00:00:00Z",
            "platform": "linux",
            "arch": "x86_64",
        },
        "entrypoint": {
            "status": "degraded",
            "reason": "bare_cc_bridge_resolves_under_temporary_directory",
            "path": "/tmp/smoke/bin/cc_bridge",
            "realpath": "/tmp/smoke/prefix/cc_bridge",
            "expected_install_path": "/opt/cc_bridge",
            "matches_current_install": False,
        },
        "runtime": {
            "user_id": 0,
            "user_name": "root",
            "home": "/root",
            "root_runtime": True,
            "install_root_owned": True,
            "install_user_id": 0,
            "install_user_name": "root",
            "sudo_user": "demo",
            "project_owner": "1000:demo",
            "cc_bridge_dir_owner": "1000:demo",
            "install_owner": "0:root",
            "warnings": (
                "Running CC_BRIDGE as root in a non-root-owned project can create root-owned .cc-bridge files.",
            ),
        },
        "requirements": {
            "python_executable": "/usr/bin/python3",
            "python_version": "3.12.0",
            "tmux_available": True,
            "tmux_path": "/usr/bin/tmux",
            "provider_commands": (
                {
                    "provider": "codex",
                    "executable": "codex",
                    "available": True,
                    "path": "/mnt/c/Users/demo/AppData/Local/Microsoft/WindowsApps/codex.exe",
                    "status": "degraded",
                    "reason": "wsl_windows_interop_executable",
                    "warning": "codex resolves to a Windows interop executable; use a Linux codex binary or CODEX_START_CMD",
                },
            ),
        },
        "cc_bridge_daemon": {
            "state": "unmounted",
            "pid": None,
            "keeper_pid": None,
            "implementation_root": None,
            "implementation_status": "unknown",
            "implementation_reason": "pid_unavailable",
            "implementation_cmdline": None,
            "health": "unknown",
            "generation": 0,
            "last_heartbeat_at": None,
            "pid_alive": False,
            "socket_connectable": False,
            "heartbeat_fresh": False,
            "takeover_allowed": True,
            "reason": "not_started",
            "active_execution_count": 0,
            "recoverable_execution_count": 0,
            "nonrecoverable_execution_count": 0,
            "pending_items_count": 0,
            "terminal_pending_count": 0,
            "recoverable_execution_providers": [],
            "nonrecoverable_execution_providers": [],
            "diagnostic_errors": (),
        },
        "agents": [],
    }

    lines = render_doctor(payload)

    assert "user_id: 0" in lines
    assert "user_name: root" in lines
    assert "home: /root" in lines
    assert "root_runtime: True" in lines
    assert "install_root_owned: True" in lines
    assert "entrypoint_status: degraded" in lines
    assert "entrypoint_reason: bare_cc_bridge_resolves_under_temporary_directory" in lines
    assert "cc_bridge_daemon_implementation_status: unknown" in lines
    assert "sudo_user: demo" in lines
    assert "project_owner: 1000:demo" in lines
    assert "cc_bridge_dir_owner: 1000:demo" in lines
    assert (
        "runtime_warning: Running CC_BRIDGE as root in a non-root-owned project can create root-owned .cc-bridge files."
        in lines
    )
    assert (
        "requirement_provider: name=codex executable=codex available=True "
        "path=/mnt/c/Users/demo/AppData/Local/Microsoft/WindowsApps/codex.exe "
        "status=degraded reason=wsl_windows_interop_executable "
        "warning=codex resolves to a Windows interop executable; use a Linux codex binary or CODEX_START_CMD"
        in lines
    )


def test_entrypoint_summary_flags_temporary_bare_cc_bridge(monkeypatch) -> None:
    monkeypatch.setattr(system.shutil, "which", lambda command: "/tmp/cc_bridge-smoke/bin/cc_bridge")

    payload = system.entrypoint_summary(installation={"path": "/home/demo/.local/share/codex-dual"})

    assert payload["status"] == "degraded"
    assert payload["reason"] == "bare_cc_bridge_resolves_under_temporary_directory"
    assert payload["matches_current_install"] is False


def test_entrypoint_summary_accepts_current_install(monkeypatch, tmp_path: Path) -> None:
    del tmp_path
    install_dir = "/home/demo/.local/share/codex-dual"
    monkeypatch.setattr(system.shutil, "which", lambda command: f"{install_dir}/bin/cc_bridge")

    payload = system.entrypoint_summary(installation={"path": install_dir})

    assert payload["status"] == "ok"
    assert payload["reason"] == "matches_current_install"
    assert payload["matches_current_install"] is True


def test_requirements_summary_flags_wsl_codex_windows_interop(monkeypatch) -> None:
    def fake_which(command: str) -> str | None:
        if command == "tmux":
            return "/usr/bin/tmux"
        if command == "codex":
            return "/mnt/c/Users/demo/AppData/Local/Microsoft/WindowsApps/codex.exe"
        return None

    monkeypatch.setattr(system, "_is_wsl_runtime", lambda: True)
    monkeypatch.setattr(system.shutil, "which", fake_which)

    payload = system.requirements_summary()
    codex = next(item for item in payload["provider_commands"] if item["provider"] == "codex")

    assert codex["available"] is True
    assert codex["status"] == "degraded"
    assert codex["reason"] == "wsl_windows_interop_executable"
    assert "Linux codex binary" in codex["warning"]


def test_cc_bridge_daemon_implementation_summary_flags_temporary_root(monkeypatch) -> None:
    monkeypatch.setattr(
        cc_bridge_daemon,
        "_process_cmdline",
        lambda pid: ("python3", "/tmp/cc_bridge-smoke/prefix/lib/cc_bridge_daemon/main.py", "--project", "/repo"),
    )

    payload = cc_bridge_daemon._implementation_summary(1234)

    assert payload["status"] == "degraded"
    assert payload["reason"] == "cc_bridge_daemon_implementation_root_is_temporary"
    assert payload["root"] == str(Path("/tmp/cc_bridge-smoke/prefix").resolve(strict=False))


def test_cc_bridge_daemon_implementation_summary_flags_resolved_tempdir_root(monkeypatch) -> None:
    temp_root = Path("/private/var/folders/cc_bridge-test/T").resolve(strict=False)
    monkeypatch.setattr(cc_bridge_daemon.tempfile, "gettempdir", lambda: str(temp_root))
    monkeypatch.setattr(
        cc_bridge_daemon,
        "_process_cmdline",
        lambda pid: ("python3", str(temp_root / "prefix/lib/cc_bridge_daemon/main.py"), "--project", "/repo"),
    )

    payload = cc_bridge_daemon._implementation_summary(1234)

    assert payload["status"] == "degraded"
    assert payload["reason"] == "cc_bridge_daemon_implementation_root_is_temporary"
