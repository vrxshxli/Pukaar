"""Sign-in for officers and volunteers.

Citizens and families never sign in: they reach the helpline by phone number,
like WhatsApp, and the family lookup only ever returns status and camp.

Accounts and sessions live in their own tables, outside db.TABLES, so
resetting the flood night does not sign anyone out or wipe the accounts.
Passwords are stored as salted PBKDF2 hashes and session tokens as SHA-256
hashes, so a copy of the database does not let anyone sign in.
"""
import hashlib
import hmac
import os
import secrets
import threading
import time

from fastapi import HTTPException, Request

from . import db

COOKIE = "pukaar_session"
SESSION_SECONDS = 12 * 3600  # one duty shift
MAX_FAILURES = 5
LOCKOUT_SECONDS = 60
_ITERATIONS = 200_000

DEFAULT_OFFICER_PASSWORD = "pukaar-officer"
DEFAULT_VOLUNTEER_PASSWORD = "pukaar-volunteer"

# username, display name, role, team
ACCOUNTS = [
    ("rao", "Officer Rao", "officer", None),
    ("desai", "Officer Desai", "officer", None),
    ("boat1", "Boat 1 (medic)", "volunteer", "boat1"),
    ("boat2", "Boat 2", "volunteer", "boat2"),
    ("boat3", "Boat 3", "volunteer", "boat3"),
    ("van1", "Supplies van", "volunteer", "van1"),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  username TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL,
  team_id TEXT,
  salt TEXT NOT NULL,
  password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  username TEXT NOT NULL,
  created_at REAL NOT NULL,
  expires_at REAL NOT NULL
);
"""

_failures: dict[str, list[float]] = {}
_failures_lock = threading.Lock()


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), _ITERATIONS).hex()


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _password_for(role):
    if role == "officer":
        return os.environ.get("PUKAAR_OFFICER_PASSWORD") or DEFAULT_OFFICER_PASSWORD
    return os.environ.get("PUKAAR_VOLUNTEER_PASSWORD") or DEFAULT_VOLUNTEER_PASSWORD


def set_password(username, password):
    salt = secrets.token_hex(16)
    db.execute("UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
               (salt, _hash_password(password, salt), username))


def ensure_accounts():
    """Create the tables and the demo accounts. Passwords set by environment variable win on every start."""
    with db._lock:
        db.conn().executescript(SCHEMA)
        for username, name, role, team in ACCOUNTS:
            if not db.one("SELECT username FROM users WHERE username = ?", (username,)):
                salt = secrets.token_hex(16)
                db.insert("users", username=username, display_name=name, role=role, team_id=team,
                          salt=salt, password_hash=_hash_password(_password_for(role), salt))
            elif os.environ.get("PUKAAR_OFFICER_PASSWORD" if role == "officer" else "PUKAAR_VOLUNTEER_PASSWORD"):
                set_password(username, _password_for(role))
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (time.time(),))


def using_default_passwords():
    return not os.environ.get("PUKAAR_OFFICER_PASSWORD") or not os.environ.get("PUKAAR_VOLUNTEER_PASSWORD")


def public_user(u):
    return {"username": u["username"], "name": u["display_name"], "role": u["role"], "team_id": u["team_id"]}


def _locked_out(key):
    now = time.time()
    with _failures_lock:
        recent = [t for t in _failures.get(key, []) if now - t < LOCKOUT_SECONDS]
        _failures[key] = recent
        return len(recent) >= MAX_FAILURES


def _record_failure(key):
    with _failures_lock:
        _failures.setdefault(key, []).append(time.time())


def reset_failures():
    with _failures_lock:
        _failures.clear()


def login(username, password):
    """Return (session token, user) or raise 401/429."""
    username = (username or "").strip().lower()
    if _locked_out(username):
        raise HTTPException(429, f"Too many wrong passwords. Try again in {LOCKOUT_SECONDS} seconds.")
    u = db.one("SELECT * FROM users WHERE username = ?", (username,))
    # Hash even for unknown names so the response time does not reveal which usernames exist.
    salt = u["salt"] if u else "00" * 16
    ok = hmac.compare_digest(_hash_password(password or "", salt), u["password_hash"] if u else "0")
    if not u or not ok:
        _record_failure(username)
        raise HTTPException(401, "Wrong username or password")
    token = secrets.token_urlsafe(32)
    now = time.time()
    db.insert("sessions", token_hash=_hash_token(token), username=username, created_at=now, expires_at=now + SESSION_SECONDS)
    return token, u


def logout(token):
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))


def user_for(request: Request):
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    s = db.one("SELECT * FROM sessions WHERE token_hash = ?", (_hash_token(token),))
    if not s or s["expires_at"] < time.time():
        return None
    return db.one("SELECT * FROM users WHERE username = ?", (s["username"],))


def require_user(request: Request):
    u = user_for(request)
    if not u:
        raise HTTPException(401, "Please sign in")
    return u


def require_officer(request: Request):
    u = require_user(request)
    if u["role"] != "officer":
        raise HTTPException(403, "Only duty officers can do this")
    return u


def require_team(request: Request, team_id: str):
    """Volunteers see only their own team; officers can open any team's view."""
    u = require_user(request)
    if u["role"] == "officer" or u["team_id"] == team_id:
        return u
    raise HTTPException(403, "This account belongs to a different team")
