from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import create_session_factory
from backend.app.seed import seed_mvp0


def main() -> None:
    session_factory = create_session_factory()
    with session_factory() as session:
        summary = seed_mvp0(session)
    print(summary)


if __name__ == "__main__":
    main()
