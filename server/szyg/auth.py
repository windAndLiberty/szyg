"""
Authentication module — JWT + SQLite user management
"""
import hashlib
import secrets
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from pydantic import BaseModel

# --- Config ---
_DEFAULT_SECRET = "dev-secret-change-in-production"
SECRET_KEY = os.environ.get("SZYG_SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = _DEFAULT_SECRET
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "SZYG_SECRET_KEY not set — using insecure default. "
        "Set SZYG_SECRET_KEY to a random 32+ char value in production."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day
DB_PATH = os.environ.get("SZYG_AUTH_DB", "data/auth.db")

# Simple password hashing using PBKDF2-SHA256 (no external bcrypt dependency needed)
def _hash_pw(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 600000)
    return f"pbkdf2:sha256:600000:{salt}:{dk.hex()}"

def _verify_pw(password: str, hashed: str) -> bool:
    try:
        _, _, _, salt, _ = hashed.split(':')
        return _hash_pw(password, salt) == hashed
    except (ValueError, AttributeError):
        return False


# --- Models ---
class User(BaseModel):
    id: int
    username: str
    role: str = "user"
    email: str = ""
    oem_id: str | None = None
    is_active: bool = True

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class LoginRequest(BaseModel):
    username: str
    password: str


# --- DB ---
def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            email TEXT DEFAULT '',
            oem_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    # Migration: add email column if missing
    try:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def _default_admin():
    """Create default admin if no users exist.

    Uses SZYG_ADMIN_PASSWORD env-var if set; otherwise generates a random
    password and prints it once to stdout so the operator can log in.
    """
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        admin_pw = os.environ.get("SZYG_ADMIN_PASSWORD", "")
        if not admin_pw:
            admin_pw = secrets.token_urlsafe(16)
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "No SZYG_ADMIN_PASSWORD set — generated initial admin password: %s  "
                "Change it immediately or set SZYG_ADMIN_PASSWORD before next restart.",
                admin_pw,
            )
        conn.execute(
            "INSERT INTO users (username, hashed_password, role) VALUES (?, ?, ?)",
            ("admin", _hash_pw(admin_pw), "admin"),
        )
        conn.commit()
    conn.close()


# --- Auth Logic ---
verify_password = _verify_pw
hash_password = _hash_pw

def get_user_by_username(username: str) -> UserInDB | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if row:
        return UserInDB(**dict(row))
    return None

def get_user_by_id(user_id: int) -> User | None:
    conn = _get_conn()
    row = conn.execute("SELECT id, username, role, email, oem_id, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(**dict(row))
    return None

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def authenticate(username: str, password: str) -> Token | None:
    user = get_user_by_username(username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return Token(
        access_token=token,
        user=User(id=user.id, username=user.username, role=user.role, oem_id=user.oem_id),
    )

def get_current_user(token_str: str) -> User | None:
    try:
        payload = jwt.decode(token_str, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        return get_user_by_id(user_id)
    except JWTError:
        return None

def list_users() -> list[User]:
    conn = _get_conn()
    rows = conn.execute("SELECT id, username, role, email, oem_id, is_active FROM users ORDER BY id").fetchall()
    conn.close()
    return [User(**dict(r)) for r in rows]

def create_user(username: str, password: str, role: str = "user", email: str = "", oem_id: str | None = None) -> User | None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO users (username, hashed_password, role, email, oem_id) VALUES (?, ?, ?, ?, ?)",
            (username, _hash_pw(password), role, email, oem_id),
        )
        conn.commit()
        row = conn.execute("SELECT id, username, role, email, oem_id, is_active FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        return User(**dict(row))
    except sqlite3.IntegrityError:
        conn.close()
        return None

def update_user(user_id: int, email: str | None = None, role: str | None = None) -> User | None:
    conn = _get_conn()
    fields = []
    vals = []
    if email is not None:
        fields.append("email = ?")
        vals.append(email)
    if role is not None:
        fields.append("role = ?")
        vals.append(role)
    if fields:
        vals.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", vals)
        conn.commit()
    row = conn.execute("SELECT id, username, role, email, oem_id, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return User(**dict(row)) if row else None

def delete_user(user_id: int) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0

def toggle_user_active(user_id: int) -> User | None:
    conn = _get_conn()
    row = conn.execute("SELECT is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return None
    new_val = 0 if row["is_active"] else 1
    conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_val, user_id))
    conn.commit()
    row = conn.execute("SELECT id, username, role, email, oem_id, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return User(**dict(row)) if row else None

# Initialize on import
_init_db()
_default_admin()
