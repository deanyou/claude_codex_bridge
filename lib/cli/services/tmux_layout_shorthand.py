"""tmux 布局 shorthand → ``layout_spec`` 翻译器（round 03）。

设计：
- 单一真值源是既有 ``layout_spec``（``lib/agents/models_runtime/layout.py``）。
- 安装器把用户选的 shorthand 翻译成 ``layout_spec``，写到
  ``~/.cc-bridge/cc_bridge.config``；``cc-bridge`` 启动链路读
  ``config.layout_spec``，无须改动 Python 端代码。
- shorthand 含义（spec D4）：1x2=2 格；1x3=3 格；2x2=4 格。
  不隐含额外 infra / cmd 行；``cmd`` 是否占格由生成的 spec 表达。
- ``cmd`` 出现在 agent 列表首位时翻译函数不特殊处理——它和其它 agent 一样是
  spec 的一个 leaf。``parse_layout_spec`` 已识别 ``cmd``（见 validation.py
  第 51-57 行：``'cmd'`` 是保留 token 但允许出现）。
"""

from __future__ import annotations

from typing import Iterable

from agents.models_runtime.layout import parse_layout_spec
from agents.models_runtime.layout_runtime.nodes import LayoutNode


# ---- 错误类型 ----


class LayoutShorthandError(ValueError):
    """shorthand 输入不合法或与 agent 数量不匹配。"""


class UnknownShorthandError(LayoutShorthandError):
    """shorthand 名不在已知列表里。"""


class LayoutAgentCountError(LayoutShorthandError):
    """agent 数量与 shorthand 要求不符。"""


# ---- shorthand 元数据 ----


# shorthand 表 (经实测 parser 支持任意 `;` 切分，所以这里直接拼字符串)
_SHORTHAND_PLANES: dict[str, int] = {
    "1x2": 2,
    "1x3": 3,
    "2x2": 4,
}


# ---- 公开 API ----


def expected_pane_count(shorthand: str) -> int:
    """shorthand → 总 pane 数（含 ``cmd``，不含 infra 旁路）。"""
    key = _normalize(shorthand)
    if key not in _SHORTHAND_PLANES:
        raise UnknownShorthandError(
            f"unknown layout shorthand {shorthand!r}; "
            f"expected one of {sorted(_SHORTHAND_PLANES)}"
        )
    return _SHORTHAND_PLANES[key]


def translate(
    shorthand: str,
    agents: Iterable[str],
    *,
    providers: Iterable[str] | None = None,
) -> str:
    """shorthand + agent 列表 → ``layout_spec`` 字符串（启动链路可直接读）。

    ``agents`` 按位置顺序映射到 pane：
      - 1x2 (2 panes)：``a[0]:p[0]; a[1]:p[1]``
      - 1x3 (3 panes)：``a[0]:p[0]; a[1]:p[1]; a[2]:p[2]``
      - 2x2 (4 panes)：``a[0]:p[0], a[1]:p[1]; a[2]:p[2], a[3]:p[3]``

    ``providers`` 与 ``agents`` 同序；省略时 agent 名作 provider 名
    （与 ``build_default_project_config`` 里的 ``{agent}:{provider}`` 习惯一致）。
    ``cmd`` 是保留 token（_parse_compact_leaf 允许的唯一无 provider 名）。

    返回字符串立即走 ``parse_layout_spec`` + ``_parse_compact_config_document``
    双重校验，确保启动链路读到此 spec 不报错。
    """
    key = _normalize(shorthand)
    if key not in _SHORTHAND_PLANES:
        raise UnknownShorthandError(
            f"unknown layout shorthand {shorthand!r}; "
            f"expected one of {sorted(_SHORTHAND_PLANES)}"
        )
    required = _SHORTHAND_PLANES[key]

    agent_list = _normalize_agent_list(agents)
    if len(agent_list) != required:
        raise LayoutAgentCountError(
            f"layout {key!r} needs exactly {required} panes but got "
            f"{len(agent_list)} agent(s): {agent_list}"
        )

    if providers is None:
        provider_list = list(agent_list)
    else:
        provider_list = _normalize_provider_list(providers, len(agent_list))

    # 预留 :provider；保留 token "cmd" 不强制 provider
    parts: list[str] = []
    for name, prov in zip(agent_list, provider_list):
        if name == "cmd":
            parts.append("cmd")
        else:
            parts.append(f"{name}:{prov}")

    if key == "1x2":
        spec = "; ".join(parts)
    elif key == "1x3":
        spec = "; ".join(parts)
    else:  # 2x2
        spec = f"{parts[0]}, {parts[1]}; {parts[2]}, {parts[3]}"

    # 双重 round-trip 校验：parser + compact config 解析
    parse_layout_spec(spec)
    _parse_compact_smoke(spec)
    return spec


def translate_and_validate(
    shorthand: str,
    agents: Iterable[str],
) -> tuple[str, LayoutNode]:
    """``translate`` + 返回 ``LayoutNode``。测试和 shell 端都更友好。"""
    spec = translate(shorthand, agents)
    node = parse_layout_spec(spec)
    return spec, node


# ---- 内部 ----


def _normalize(shorthand: str) -> str:
    return str(shorthand or "").strip().lower()


def _normalize_agent_list(agents: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in agents:
        name = str(raw or "").strip()
        if not name:
            continue
        # 与 parser 的 _LEAF_TOKEN_RE 对齐：去重 + 大小写折叠
        # parser 实际不折叠大小写，但 ``cmd`` 是保留小写。这里保留用户原始大小写，
        # 由 parser 决定是否接受。
        if name in seen:
            raise LayoutAgentCountError(f"duplicate agent name in input: {name!r}")
        seen.add(name)
        out.append(name)
    return out


def _normalize_provider_list(
    providers: Iterable[str],
    expected_count: int,
) -> list[str]:
    out: list[str] = []
    for raw in providers:
        prov = str(raw or "").strip()
        if not prov:
            continue
        out.append(prov)
        if len(out) >= expected_count:
            break
    if len(out) != expected_count:
        raise LayoutAgentCountError(
            f"providers list length {len(out)} does not match "
            f"agents list length {expected_count}"
        )
    return out


def _parse_compact_smoke(spec: str) -> None:
    """``parse_layout_spec`` 后再走 ``_parse_compact_config_document`` 路径，
    启动链路读 config 时会走该路径（lib/agents/config_loader_runtime/
    io_runtime/documents.py:102）。
    """
    from agents.config_loader_runtime.io_runtime.documents import (
        _parse_compact_config_document,
    )
    import tempfile

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".config", delete=False, encoding="utf-8"
    ) as f:
        f.write(spec + "\n")
        tmp_path = f.name
    try:
        _parse_compact_config_document(spec + "\n", path=tmp_path)  # type: ignore[arg-type]
    finally:
        from pathlib import Path
        Path(tmp_path).unlink(missing_ok=True)


__all__ = [
    "LayoutAgentCountError",
    "LayoutShorthandError",
    "UnknownShorthandError",
    "expected_pane_count",
    "translate",
    "translate_and_validate",
]