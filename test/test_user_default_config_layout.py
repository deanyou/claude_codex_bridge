"""round 03 集成测试：安装器写完 config 后，启动链路可读出。

验证：
- 安装器写的 ``~/.cc-bridge/cc_bridge.config`` 可被 ``load_project_config`` 读出
- 项目级 ``<project>/.cc-bridge/cc_bridge.config`` 覆盖用户级
- ``build_project_layout_plan`` 用 ``layout_spec`` 产出正确 leaf 数
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.config_loader_runtime.io_runtime.documents import (
    load_project_config,
    parse_config_document_text,
    CONFIG_SOURCE_BUILTIN_DEFAULT,
    CONFIG_SOURCE_PROJECT,
    CONFIG_SOURCE_USER,
)
from agents.models_runtime.layout_plan import build_project_layout_plan
from cli.services.tmux_layout_shorthand import translate


# ---- round-trip：install 写出的 config 能被启动链路读 ----


def test_user_default_config_round_trips_via_load_project_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """install 写到 ``~/.cc-bridge/cc_bridge.config`` 的 spec 可被启动链路解析。"""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    config_path = fake_home / ".cc-bridge" / "cc_bridge.config"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    spec = translate("1x2", ["claude", "codex"])
    body = f"# cc-bridge layout shorthand: 1x2\n{spec}\n"
    config_path.write_text(body, encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CC_BRIDGE_SOURCE_HOME", raising=False)

    result = load_project_config(tmp_path / "fake-project")
    assert result.source_kind == CONFIG_SOURCE_USER
    assert result.source_path == config_path
    assert result.used_default is False
    # 解析出的 layout_spec 与 install 写的一致
    assert result.config.layout_spec.strip() == spec


def test_user_default_config_drives_layout_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_project_layout_plan`` 用 ``layout_spec`` 产出正确 leaf 数（验证可被启动链路使用）。"""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    config_path = fake_home / ".cc-bridge" / "cc_bridge.config"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    spec = translate("2x2", ["claude", "codex", "pi", "demo"])
    body = f"# cc-bridge layout shorthand: 2x2\n{spec}\n"
    config_path.write_text(body, encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CC_BRIDGE_SOURCE_HOME", raising=False)

    result = load_project_config(tmp_path / "fake-project")
    plan = build_project_layout_plan(
        result.config,
        target_agent_names=("claude", "codex", "pi", "demo"),
    )
    visible_leaves = list(plan.layout.iter_leaves())
    assert len(visible_leaves) == 4
    assert [leaf.name for leaf in visible_leaves] == ["claude", "codex", "pi", "demo"]


@pytest.mark.parametrize(
    "shorthand, agents, expected_leaf_count",
    [
        ("1x2", ["claude", "codex"], 2),
        ("1x3", ["claude", "codex", "pi"], 3),
        ("2x2", ["claude", "codex", "pi", "demo"], 4),
    ],
)
def test_install_written_layout_appears_in_visible_leaves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    shorthand: str,
    agents: list[str],
    expected_leaf_count: int,
) -> None:
    """shorthand → install 写出的 config → 启动链路 visible leaf 数 = shorthand 格数。"""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    config_path = fake_home / ".cc-bridge" / "cc_bridge.config"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    spec = translate(shorthand, agents)
    body = f"# cc-bridge layout shorthand: {shorthand}\n{spec}\n"
    config_path.write_text(body, encoding="utf-8")

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CC_BRIDGE_SOURCE_HOME", raising=False)

    result = load_project_config(tmp_path / "fake-project")
    plan = build_project_layout_plan(result.config, target_agent_names=tuple(agents))
    visible_leaves = list(plan.layout.iter_leaves())
    assert len(visible_leaves) == expected_leaf_count
    assert [leaf.name for leaf in visible_leaves] == agents


# ---- 项目级覆盖用户级 ----


def test_project_config_overrides_user_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """项目级 config 优先于用户级 config（spec D5：升级保留 + 项目级始终优先）。"""
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir()
    user_config = fake_home / ".cc-bridge" / "cc_bridge.config"
    user_config.parent.mkdir(parents=True, exist_ok=True)
    user_spec = translate("1x3", ["claude", "codex", "pi"])
    user_config.write_text(
        f"# user default\n{user_spec}\n", encoding="utf-8"
    )

    project_root = tmp_path / "fake-project"
    project_root.mkdir()
    project_config = project_root / ".cc-bridge" / "cc_bridge.config"
    project_config.parent.mkdir(parents=True, exist_ok=True)
    project_spec = translate("2x2", ["claude", "codex", "pi", "demo"])
    project_config.write_text(
        f"# project override\n{project_spec}\n", encoding="utf-8"
    )

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CC_BRIDGE_SOURCE_HOME", raising=False)

    result = load_project_config(project_root)
    assert result.source_kind == CONFIG_SOURCE_PROJECT
    assert result.source_path == project_config
    assert result.config.layout_spec.strip() == project_spec


# ---- fallback：没有 user / project config 时用 built-in default ----


def test_no_config_falls_back_to_builtin_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """既无 user 也无 project config → built-in default（``demo:codex``）。"""
    fake_home = tmp_path / "empty-home"
    fake_home.mkdir()
    project_root = tmp_path / "no-config-project"
    project_root.mkdir()

    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("CC_BRIDGE_SOURCE_HOME", raising=False)

    result = load_project_config(project_root)
    assert result.source_kind == CONFIG_SOURCE_BUILTIN_DEFAULT
    assert result.used_default is True


# ---- parser 直接处理 install 写出的格式 ----


def test_parse_config_document_text_handles_install_format(
    tmp_path: Path,
) -> None:
    """``parse_config_document_text`` 直接处理 install 写出的文件文本（不依赖磁盘）。"""
    spec = translate("1x2", ["claude", "codex"])
    body = f"# cc-bridge layout shorthand: 1x2\n{spec}\n"

    parsed = parse_config_document_text(
        body,
        path=tmp_path / "cc_bridge.config",
    )
    assert parsed["version"] == 2
    assert parsed["default_agents"] == ["claude", "codex"]
    # rendered ``layout`` 是归一化后的 spec（与 translate 一致）
    assert "claude" in parsed["layout"]
    assert "codex" in parsed["layout"]


def test_parse_config_document_text_rejects_bad_spec(
    tmp_path: Path,
) -> None:
    """install 写入出错时 round-trip parser 应拒收（spec 验收：startup 启动时不会拿到坏 spec）。"""
    from agents.config_loader_runtime.io_runtime.documents import (
        ConfigValidationError,
    )

    body = "this is not a layout_spec\n"
    with pytest.raises(ConfigValidationError):
        parse_config_document_text(body, path=tmp_path / "bad.config")