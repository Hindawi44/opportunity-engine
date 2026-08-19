from __future__ import annotations

from .live_research_recovery_v1 import install_live_research_recovery
from .runner_v1 import main


def resilient_main() -> int:
    install_live_research_recovery()
    return main()


if __name__ == "__main__":
    raise SystemExit(resilient_main())
