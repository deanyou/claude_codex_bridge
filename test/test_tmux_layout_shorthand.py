"""round 03 tmux layout shorthand → layout_spec 单测。"""

from __future__ import annotations

import pytest

from agents.models_runtime.layout import parse_layout_spec
from cli.services.tmux_layout_shorthand import (
    LayoutAgentCountError,
    LayoutShorthandError,
    UnknownShorthandError,
    expected_pane_count,
    translate,
    translate_and_validate,
)


# ---- 5 + 1 翻译表覆盖 ----


@pytest.mark.parametrize(
    "shorthand, agents, expected_spec, expected_leaves",
    [
        # 1x2 = 2 panes side-by-side (default provider = agent name)
        ("1x2", ["claude", "codex"], "claude:claude; codex:codex", ["claude", "codex"]),
        # 1x3 = 3 panes side-by-side
        (
            "1x3",
            ["claude", "codex", "pi"],
            "claude:claude; codex:codex; pi:pi",
            ["claude", "codex", "pi"],
        ),
        # 2x2 = 4 panes in 2x2 grid
        (
            "2x2",
            ["claude", "codex", "pi", "demo"],
            "claude:claude, codex:codex; pi:pi, demo:demo",
            ["claude", "codex", "pi", "demo"],
        ),
        # cmd 在 1x2 首位（保留 token，无 provider）
        ("1x2", ["cmd", "codex"], "cmd; codex:codex", ["cmd", "codex"]),
        # 大小写保持一致（CLAUDE → CLAUDE:CLAUDE）
        (
            "1x3",
            ["CLAUDE", "codex", "pi"],
            "CLAUDE:CLAUDE; codex:codex; pi:pi",
            ["CLAUDE", "codex", "pi"],
        ),
    ],
)
def test_shorthand_translates_to_expected_layout_spec(
    shorthand: str,
    agents: list[str],
    expected_spec: str,
    expected_leaves: list[str],
) -> None:
    spec = translate(shorthand, agents)
    assert spec == expected_spec
    leaves = [leaf.name for leaf in parse_layout_spec(spec).iter_leaves()]
    assert leaves == expected_leaves


# ---- round-trip ----


@pytest.mark.parametrize("shorthand", ["1x2", "1x3", "2x2"])
def test_shorthand_round_trips_through_parse_layout_spec(shorthand: str) -> None:
    """translate 输出能被既有 ``parse_layout_spec`` 解析，leaf 数等于预期。"""
    count = expected_pane_count(shorthand)
    agents = [f"agent_{i}" for i in range(count)]
    spec, node = translate_and_validate(shorthand, agents)
    leaves = list(node.iter_leaves())
    assert len(leaves) == count
    assert [leaf.name for leaf in leaves] == agents


def test_translate_with_explicit_providers() -> None:
    """``providers`` 与 ``agents`` 同序映射到 ``:provider`` 后缀。"""
    spec = translate(
        "1x3", ["claude", "codex", "pi"],
        providers=["anthropic", "openai", "pi-runtime"],
    )
    assert spec == "claude:anthropic; codex:openai; pi:pi-runtime"


def test_translate_providers_length_mismatch_raises() -> None:
    """providers 数量与 agents 不一致 → 拋 ``LayoutAgentCountError``。"""
    with pytest.raises(LayoutAgentCountError):
        translate(
            "1x3", ["claude", "codex", "pi"],
            providers=["anthropic", "openai"],
        )


# ---- 校验失败 ----


def test_shorthand_invalid_layout_raises() -> None:
    """未知 shorthand 抛 ``UnknownShorthandError``。"""
    with pytest.raises(UnknownShorthandError):
        translate("4x4", ["a", "b", "c", "d"])
    with pytest.raises(UnknownShorthandError):
        translate("0x0", ["a"])
    with pytest.raises(UnknownShorthandError):
        translate("", ["a"])
    with pytest.raises(UnknownShorthandError):
        translate("1x4", ["a", "b", "c", "d"])  # 不在 known set


def test_shorthand_agent_count_mismatch_raises() -> None:
    """agent 数量不符抛 ``LayoutAgentCountError``，spec D5。"""
    # 1x2 expects 2, got 1
    with pytest.raises(LayoutAgentCountError):
        translate("1x2", ["only_one"])
    # 1x2 expects 2, got 3
    with pytest.raises(LayoutAgentCountError):
        translate("1x2", ["a", "b", "c"])
    # 2x2 expects 4, got 2
    with pytest.raises(LayoutAgentCountError):
        translate("2x2", ["a", "b"])
    # empty agents
    with pytest.raises(LayoutAgentCountError):
        translate("1x2", [])


def test_shorthand_empty_agent_string_is_filtered() -> None:
    """空字符串 / whitespace-only 的 agent 视为不存在，不算 pane。"""
    with pytest.raises(LayoutAgentCountError):
        translate("1x2", ["", "  ", "a"])  # 过滤后只有 1 个有效


def test_shorthand_duplicate_agent_name_raises() -> None:
    """重复 agent 名直接抛错（防止静默截断，spec D5）。"""
    with pytest.raises(LayoutAgentCountError):
        translate("1x2", ["claude", "claude"])


# ---- expected_pane_count ----


@pytest.mark.parametrize(
    "shorthand, expected",
    [
        ("1x2", 2),
        ("1x3", 3),
        ("2x2", 4),
    ],
)
def test_expected_pane_count(shorthand: str, expected: int) -> None:
    assert expected_pane_count(shorthand) == expected


def test_expected_pane_count_unknown_raises() -> None:
    with pytest.raises(UnknownShorthandError):
        expected_pane_count("3x3")


# ---- 继承性：所有错误都是 LayoutShorthandError 子类 ----


def test_all_errors_inherit_from_layout_shorthand_error() -> None:
    """调用方可以统一 ``except LayoutShorthandError``。"""
    for exc_cls in (UnknownShorthandError, LayoutAgentCountError):
        assert issubclass(exc_cls, LayoutShorthandError)
        assert issubclass(exc_cls, ValueError)