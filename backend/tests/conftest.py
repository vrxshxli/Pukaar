import pytest

from app import db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Every test gets its own database loaded from the scenario, in rules mode."""
    monkeypatch.setenv("LLM_MODE", "rules")
    monkeypatch.setenv("PUKAAR_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("PUKAAR_OFFICER_PASSWORD", raising=False)
    monkeypatch.delenv("PUKAAR_VOLUNTEER_PASSWORD", raising=False)
    from app import auth
    auth.reset_failures()
    db.connect(tmp_path / "test.db")
    db.set_clock(db.game_time_on_night("21:40"), speed=0)
    yield
