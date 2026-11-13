"""Apply account tables.

From ``research/01_resume_intelligence``:

    py -3 -m accounts.migrate
"""
from __future__ import annotations

from accounts.db import prepare_database


def main() -> None:
    prepare_database()
    print("Account tables are ready.")


if __name__ == "__main__":
    main()
