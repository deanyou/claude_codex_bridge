from __future__ import annotations


def named_agent_instance(agent_name: str, *, primary_agent: str) -> str | None:
    normalized_agent = str(agent_name or "").strip().lower()
    # ccb and peri use instance-encoded session filenames (e.g. .ccb-executor-session,
    # .peri-session), so no additional instance suffix is needed — return None to avoid
    # double-encoding that would produce e.g. .peri-peri-session.
    if primary_agent in ('ccb', 'peri'):
        return None
    return normalized_agent or None


def should_fallback_to_primary_session(*, agent_name: str, primary_agent: str) -> bool:
    del primary_agent
    return not bool(named_agent_instance(agent_name, primary_agent=""))


__all__ = ["named_agent_instance", "should_fallback_to_primary_session"]
