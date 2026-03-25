import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from app.core.config import DATABASE_URL

def get_conn():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    conn.autocommit = True
    return conn

def init_db():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    api_key TEXT
                );
            """)
            
            # Đề phòng bảng users đã tạo từ phiên bản trước đó
            cur.execute("""
                ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key TEXT;
                ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;
            """)
            # Đảm bảo Unique cho email nêú chưa có (Chỉ thêm nếu chưa tồn tại constraint)
            cur.execute("SELECT count(*) FROM pg_constraint WHERE conname = 'uk_email'")
            if cur.fetchone()['count'] == 0:
                try:
                    cur.execute("ALTER TABLE users ADD CONSTRAINT uk_email UNIQUE (email);")
                except Exception as e:
                    print(f"Bỏ qua lỗi thêm UK_EMAIL: {e}")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id),
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    file_hash TEXT, -- MD5/SHA256 của nội dung file
                    chunks_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'processing', -- 'processing', 'completed', 'failed'
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );
            """)

            cur.execute("""
                ALTER TABLE documents ADD COLUMN IF NOT EXISTS file_hash TEXT;
                ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;
            """)

            # Thêm user admin mặc định nếu chưa tồn tại
            cur.execute("SELECT id FROM users WHERE username = 'admin'")
            if not cur.fetchone():
                import bcrypt
                from app.core.config import ADMIN_PASSWORD
                salt = bcrypt.gensalt()
                hashed = bcrypt.hashpw(ADMIN_PASSWORD.encode('utf-8'), salt).decode('utf-8')
                cur.execute(
                    "INSERT INTO users (id, username, hashed_password, is_admin) VALUES (%s, %s, %s, %s)",
                    (str(uuid.uuid4()), "admin", hashed, True)
                )
    except Exception as e:
        print(f"Lỗi khởi tạo Database: {e}")
    finally:
        conn.close()

# ── SETTINGS ──
def get_setting(key: str, default: str = None) -> str:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
            row = cur.fetchone()
    return row["value"] if row else default

def set_setting(key: str, value: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value)
            )

def increment_setting(key: str, amount: int = 1):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO settings (key, value) 
                VALUES (%s, %s) 
                ON CONFLICT (key) 
                DO UPDATE SET value = (CAST(COALESCE(NULLIF(settings.value, ''), '0') AS INTEGER) + %s)::TEXT
            """, (key, str(amount), amount))


# ── USERS ──
def get_user_by_username(username: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_user_by_id(user_id: str) -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_user_by_email(email: str) -> dict:
    if not email: return None
    email = email.lower()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
    return dict(row) if row else None

def create_user(username: str, hashed_password: str, email: str = None) -> str:
    user_id = str(uuid.uuid4())
    if email: email = email.lower()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, username, hashed_password, email) VALUES (%s, %s, %s, %s)",
                (user_id, username, hashed_password, email)
            )
    return user_id


# ── SESSIONS ──

def get_all_sessions(user_id: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sessions WHERE user_id = %s ORDER BY created_at DESC", (user_id,)
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_or_create_session(user_id: str, session_id: str, first_message: str = "") -> dict:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM sessions WHERE id = %s AND user_id = %s", (session_id, user_id)
            )
            row = cur.fetchone()

            if row:
                return dict(row)

            title = first_message[:50] + ("..." if len(first_message) > 50 else "")
            now = datetime.now().isoformat()
            cur.execute(
                "INSERT INTO sessions (id, user_id, title, created_at) VALUES (%s, %s, %s, %s)",
                (session_id, user_id, title or "New chat", now)
            )
            return {"id": session_id, "user_id": user_id, "title": title, "created_at": now}


def delete_session(user_id: str, session_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sessions WHERE id = %s AND user_id = %s", (session_id, user_id))
            row = cur.fetchone()
            if row:
                cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
                cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))


# ── MESSAGES ──

def save_message(session_id: str, role: str, content: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (%s, %s, %s, %s, %s)",
                (str(uuid.uuid4()), session_id, role, content, datetime.now().isoformat())
            )


def get_messages(session_id: str) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,)
            )
            rows = cur.fetchall()
    return [dict(r) for r in rows]