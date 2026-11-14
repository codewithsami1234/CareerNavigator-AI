"""Makes the project folder importable when running pytest from any directory."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(autouse=True)
def isolated_account_database(tmp_path, monkeypatch):
    """Give each test its own SQLite database."""
    url = "sqlite:///" + (tmp_path / "auth.sqlite").as_posix()
    monkeypatch.setenv("CAREERNAV_DATABASE_URL", url)
    monkeypatch.setenv("CAREERNAV_COOKIE_SECURE", "0")
    monkeypatch.setenv("CAREERNAV_ARGON_MEMORY", "8192")
    monkeypatch.setenv("CAREERNAV_ARGON_TIME", "1")
    from accounts.db import reset_engine
    from accounts.service import reset_login_limits

    reset_engine()
    reset_login_limits()
    yield
    reset_engine()
    reset_login_limits()
