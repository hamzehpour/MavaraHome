from database.connection import get_connection


def create_payment(reservation_id: int, receipt_file_id: str, amount: int, receipt_source: str = "telegram") -> int:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO payments(reservation_id, receipt_file_id, receipt_source, amount)
            VALUES (?, ?, ?, ?)
            """,
            (reservation_id, receipt_file_id, receipt_source, amount),
        )
        return cur.lastrowid


def get_latest_payment(reservation_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM payments WHERE reservation_id = ?
            ORDER BY submitted_at DESC LIMIT 1
            """,
            (reservation_id,),
        ).fetchone()
        return dict(row) if row else None


def set_payment_status(payment_id: int, status: str, reviewed_by: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE payments
            SET status = ?, reviewed_at = datetime('now'), reviewed_by = ?
            WHERE id = ?
            """,
            (status, reviewed_by, payment_id),
        )
