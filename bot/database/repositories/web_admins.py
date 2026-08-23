from database.connection import get_connection


def get_by_username(username: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM web_admins WHERE username = ? AND is_active = 1", (username,)
        ).fetchone()
        return dict(row) if row else None


def get_by_id(admin_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM web_admins WHERE id = ?", (admin_id,)).fetchone()
        return dict(row) if row else None


def create(username: str, password_hash: str, password_salt: str, role: str = "admin") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO web_admins(username, password_hash, password_salt, role) VALUES (?, ?, ?, ?)",
            (username, password_hash, password_salt, role),
        )
        return cur.lastrowid


def count() -> int:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) c FROM web_admins").fetchone()["c"]


def mark_login(admin_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE web_admins SET last_login_at = datetime('now') WHERE id = ?", (admin_id,))


def set_password(admin_id: int, password_hash: str, password_salt: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE web_admins SET password_hash = ?, password_salt = ? WHERE id = ?",
            (password_hash, password_salt, admin_id),
        )
