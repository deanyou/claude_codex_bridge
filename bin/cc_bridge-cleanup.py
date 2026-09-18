#!/usr/bin/env python3

from __future__ import annotations

import sys


def main() -> int:
    print(
        "error: standalone cc_bridge-cleanup was removed; use `cc_bridge kill --zombies` for global cleanup or `cc_bridge kill` inside a project",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
