"""SQLite storage for Pukaar.

We keep one shared connection guarded by a lock. The demo is small and
single-process, so this is simpler than a connection pool and avoids
"database is locked" errors when the replay and the API write at once.
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import scenario

DEFAULT_DB = Path(__file__).resolve().parents[1] / "pukaar.db"

_lock = threading.RLock()
_conn = None

SCHEMA = """
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
CREATE TABLE incidents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT, level TEXT, status TEXT, opened_at TEXT, note TEXT
);
CREATE TABLE reporters (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone TEXT UNIQUE, name TEXT, language TEXT, channel TEXT, area TEXT,
  created_at TEXT
);
CREATE TABLE messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  reporter_id INTEGER, direction TEXT, channel TEXT, text TEXT, language TEXT,
  ticket_id TEXT, kind TEXT, status TEXT, created_at TEXT, meta TEXT
);
CREATE TABLE reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id INTEGER, reporter_id INTEGER, language TEXT, fields TEXT,
  location_text TEXT, landmark TEXT, lat REAL, lng REAL, geo_confidence REAL,
  status TEXT, ticket_id TEXT, created_at TEXT
);
CREATE TABLE tickets (
  id TEXT PRIMARY KEY,
  title TEXT, area TEXT, landmark TEXT, lat REAL, lng REAL,
  kind TEXT, priority TEXT, priority_score INTEGER, reasons TEXT, status TEXT,
  people INTEGER, vulnerable TEXT, medical TEXT, water_level TEXT, danger TEXT,
  battery INTEGER, verify_reason TEXT, household_id TEXT,
  safe_camp TEXT, safe_at TEXT, otp TEXT, team_id TEXT,
  created_at TEXT, updated_at TEXT, last_update_at TEXT, notes TEXT
);
CREATE TABLE ticket_reports (
  ticket_id TEXT, report_id INTEGER, reporter_id INTEGER, reason TEXT,
  confidence REAL, created_at TEXT,
  PRIMARY KEY (ticket_id, report_id)
);
CREATE TABLE teams (
  id TEXT PRIMARY KEY,
  name TEXT, kind TEXT, skills TEXT, status TEXT, node TEXT,
  lat REAL, lng REAL, hours_on_duty REAL, capacity INTEGER,
  ticket_id TEXT, note TEXT
);
CREATE TABLE routes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  team_id TEXT, ticket_id TEXT, nodes TEXT, coords TEXT, roads TEXT,
  length_m REAL, eta_min REAL, status TEXT, progress REAL DEFAULT 0,
  created_at TEXT
);
CREATE TABLE approvals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT, ticket_id TEXT, team_id TEXT, title TEXT, payload TEXT,
  reasons TEXT, status TEXT, created_by TEXT, decided_by TEXT,
  decided_at TEXT, created_at TEXT
);
CREATE TABLE area_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT, ref TEXT, value TEXT, source TEXT, confirmations INTEGER,
  created_at TEXT, expires_at TEXT
);
CREATE TABLE camps (
  id TEXT PRIMARY KEY,
  name TEXT, lat REAL, lng REAL, capacity INTEGER, occupancy INTEGER, needs TEXT
);
CREATE TABLE households (
  id TEXT PRIMARY KEY,
  name TEXT, head TEXT, area TEXT, lane TEXT, landmark TEXT,
  lat REAL, lng REAL, people INTEGER, phone TEXT, status TEXT,
  safe_camp TEXT, safe_at TEXT
);
CREATE TABLE bulletins (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  text TEXT, language TEXT, area TEXT, status TEXT, approval_id INTEGER,
  created_at TEXT, sent_at TEXT
);
CREATE TABLE lookups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT, ticket_id TEXT, created_at TEXT
);
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT, agent TEXT, tool TEXT, kind TEXT, summary TEXT, input TEXT,
  result TEXT, ticket_id TEXT, approved_by TEXT
);
CREATE INDEX idx_messages_reporter ON messages(reporter_id);
CREATE INDEX idx_reports_ticket ON reports(ticket_id);
CREATE INDEX idx_audit_at ON audit_log(id);
"""

TABLES = [
    "settings", "incidents", "reporters", "messages", "reports", "tickets",
    "ticket_reports", "teams", "routes", "approvals", "area_events", "camps",
    "households", "bulletins", "lookups", "audit_log",
]


def db_path():
    return Path(os.environ.get("PUKAAR_DB", DEFAULT_DB))


def connect(path=None):
    """Open the database, creating and seeding it if it does not exist yet."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
        path = Path(path) if path else db_path()
        fresh = not path.exists() or path.stat().st_size == 0
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        if fresh or not _has_tables():
            reset()
    return _conn


def conn():
    if _conn is None:
        connect()
    return _conn


def _has_tables():
    row = _conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'"
    ).fetchone()
    return row is not None


def query(sql, params=()):
    with _lock:
        return [dict(r) for r in conn().execute(sql, params).fetchall()]


def one(sql, params=()):
    with _lock:
        row = conn().execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql, params=()):
    with _lock:
        cur = conn().execute(sql, params)
        conn().commit()
        return cur.lastrowid


def insert(table, **values):
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    return execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(_encode(v) for v in values.values()))


def update(table, key, key_value, **values):
    sets = ", ".join(f"{c} = ?" for c in values)
    params = tuple(_encode(v) for v in values.values()) + (key_value,)
    execute(f"UPDATE {table} SET {sets} WHERE {key} = ?", params)


def _encode(value):
    # Lists and dicts are stored as JSON text.
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def loads(value, default=None):
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def get_setting(key, default=None):
    row = one("SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )


def automation_on():
    return get_setting("automation", "on") == "on"


# The game clock. The replay runs the flood night faster than real time, so
# every timestamp in the app comes from here rather than from the wall clock.

def night_start():
    w = scenario.ward()
    return datetime.fromisoformat(f"{w['night_date']}T{w['replay_start']}:00")


def now_game():
    anchor = get_setting("clock_game")
    if not anchor:
        return night_start()
    real = float(get_setting("clock_real", time.time()))
    speed = float(get_setting("clock_speed", "1"))
    return datetime.fromisoformat(anchor) + timedelta(seconds=(time.time() - real) * speed)


def now_iso():
    return now_game().replace(microsecond=0).isoformat()


def set_clock(game_time, speed=None):
    """Pin the game clock to a time, and optionally change how fast it runs."""
    with _lock:
        if speed is None:
            speed = float(get_setting("clock_speed", "1"))
        set_setting("clock_game", game_time.replace(microsecond=0).isoformat())
        set_setting("clock_real", time.time())
        set_setting("clock_speed", speed)


def set_clock_speed(speed):
    set_clock(now_game(), speed)


def game_time_on_night(hhmm):
    """Turn '20:12' or '01:30' into a datetime on the flood night."""
    start = night_start()
    h, m = (int(x) for x in hhmm.split(":"))
    t = start.replace(hour=h, minute=m, second=0)
    if h < 12:
        t += timedelta(days=1)
    return t


def reset(llm_mode=None):
    """Drop everything and load the scenario fresh."""
    with _lock:
        c = conn()
        for table in TABLES:
            c.execute(f"DROP TABLE IF EXISTS {table}")
        c.executescript(SCHEMA)
        c.commit()
        _seed()
        if llm_mode:
            set_setting("llm_mode", llm_mode)


def _seed():
    set_setting("automation", "on")
    set_setting("llm_mode", os.environ.get("LLM_MODE", "rules"))
    set_setting("ticket_counter", "400")
    set_clock(night_start(), speed=1)
    set_setting("replay_state", "idle")

    for t in scenario.teams():
        node = scenario.roads()["nodes"][t["node"]]
        insert("teams", id=t["id"], name=t["name"], kind=t["kind"], skills=t["skills"],
               status="free", node=t["node"], lat=node["lat"], lng=node["lng"],
               hours_on_duty=t["hours_on_duty"], capacity=t["capacity"], note=t.get("note"))

    for c in scenario.camps():
        insert("camps", id=c["id"], name=c["name"], lat=c["lat"], lng=c["lng"],
               capacity=c["capacity"], occupancy=c["occupancy"], needs=c["needs"])

    for h in scenario.households():
        safe_at = game_time_on_night(h["safe_at"]).isoformat() if h.get("safe_at") else None
        insert("households", id=h["id"], name=h["name"], head=h["head"], area=h["area"],
               lane=h["lane"], landmark=h["landmark"], lat=h["lat"], lng=h["lng"],
               people=h["people"], phone=h["phone"], status=h["status"],
               safe_camp=h.get("safe_camp"), safe_at=safe_at)
        if h["status"] == "safe":
            _seed_closed_ticket(h, safe_at)

    insert("incidents", name=scenario.ward()["incident_name"], level="none",
           status="monitoring", opened_at=night_start().isoformat(), note="")


def _seed_closed_ticket(h, safe_at):
    # The Pinto family was rescued before the replay starts, so their ticket
    # already exists and is closed. Later reposts about them should hit this.
    insert("tickets", id="P-0398", title=h["name"], area=h["area"], landmark=h["landmark"],
           lat=h["lat"], lng=h["lng"], kind="rescue", priority="P2", priority_score=40,
           reasons=["Rescued earlier in the evening"], status="safe", people=h["people"],
           vulnerable=["elderly"], medical=None, water_level="waist", danger=[],
           household_id=h["id"], safe_camp=h["safe_camp"], safe_at=safe_at, team_id="boat3",
           created_at=game_time_on_night("19:40").isoformat(), updated_at=safe_at,
           last_update_at=safe_at, notes=["Closed by volunteer OTP and family confirmation"])
