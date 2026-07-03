import os
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "instance" / "noubti.db"
DB_PATH = Path(os.getenv("DATABASE_PATH", DEFAULT_DB_PATH))
if not DB_PATH.is_absolute():
    DB_PATH = BASE_DIR / DB_PATH

ACTIVE_STATUSES = ("waiting", "called", "in_service")
FINAL_STATUSES = ("completed", "cancelled", "absent")
ALL_STATUSES = ACTIVE_STATUSES + FINAL_STATUSES


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                business_type TEXT NOT NULL,
                address TEXT NOT NULL,
                opening_time TEXT NOT NULL,
                closing_time TEXT NOT NULL,
                average_service_time INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                duration INTEGER NOT NULL,
                price INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (business_id) REFERENCES businesses(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT,
                ticket_number TEXT NOT NULL,
                status TEXT NOT NULL,
                position INTEGER,
                estimated_waiting_minutes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                called_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                cancelled_at TEXT,
                absent_at TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """)
        migrate_schema(conn)
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tickets_business_number
            ON tickets (business_id, ticket_number)
        """)
        seed_sample_data(conn)


def migrate_schema(conn):
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tickets)").fetchall()}
    if "cancelled_at" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN cancelled_at TEXT")
    if "absent_at" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN absent_at TEXT")
    if "phone" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN phone TEXT")
    if "position" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN position INTEGER")
    if "estimated_waiting_minutes" not in columns:
        conn.execute("ALTER TABLE tickets ADD COLUMN estimated_waiting_minutes INTEGER NOT NULL DEFAULT 0")


def seed_sample_data(conn):
    now = now_text()
    business = conn.execute("SELECT * FROM businesses WHERE name = ?", ("Noubti Barber",)).fetchone()
    if business:
        business_id = business["id"]
    else:
        business_id = conn.execute("""
            INSERT INTO businesses
            (name, business_type, address, opening_time, closing_time, average_service_time, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("Noubti Barber", "Barbershop", "Rabat", "09:00", "20:00", 20, now)).lastrowid

    for name, duration, price in [
        ("Haircut", 20, 50),
        ("Beard", 10, 25),
        ("Haircut and Beard", 30, 70),
    ]:
        exists = conn.execute(
            "SELECT id FROM services WHERE business_id = ? AND lower(name) = lower(?)",
            (business_id, name),
        ).fetchone()
        if not exists:
            conn.execute("""
                INSERT INTO services (business_id, name, duration, price, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (business_id, name, duration, price, now))


def query_all(sql, params=()):
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def query_one(sql, params=()):
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def get_all_businesses():
    return query_all("SELECT * FROM businesses ORDER BY id")


def get_business(business_id):
    return query_one("SELECT * FROM businesses WHERE id = ?", (business_id,))


def get_services_for_business(business_id):
    return query_all("SELECT * FROM services WHERE business_id = ? ORDER BY id", (business_id,))


def get_service(service_id):
    return query_one("SELECT * FROM services WHERE id = ?", (service_id,))


def create_service(business_id, name, duration, price):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO services (business_id, name, duration, price, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (business_id, name, duration, price, now_text()))
        return cursor.lastrowid


def update_service(service_id, name, duration, price):
    with get_connection() as conn:
        conn.execute(
            "UPDATE services SET name = ?, duration = ?, price = ? WHERE id = ?",
            (name, duration, price, service_id),
        )


def has_active_tickets_for_service(service_id):
    placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
    row = query_one(
        f"SELECT COUNT(*) AS count FROM tickets WHERE service_id = ? AND status IN ({placeholders})",
        (service_id, *ACTIVE_STATUSES),
    )
    return row["count"] > 0


def delete_service(service_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM services WHERE id = ?", (service_id,))


def get_tickets_for_business(business_id):
    return query_all(
        """
        SELECT t.*, s.name AS service_name, s.duration AS service_duration
        FROM tickets t
        LEFT JOIN services s ON s.id = t.service_id
        WHERE t.business_id = ?
        ORDER BY t.created_at ASC, t.id ASC
        """,
        (business_id,),
    )


def get_ticket(ticket_id):
    return query_one(
        """
        SELECT t.*, s.name AS service_name, s.duration AS service_duration
        FROM tickets t
        LEFT JOIN services s ON s.id = t.service_id
        WHERE t.id = ?
        """,
        (ticket_id,),
    )


def get_next_waiting_ticket(business_id):
    return query_one(
        """
        SELECT * FROM tickets
        WHERE business_id = ? AND status = ?
        ORDER BY created_at ASC, id ASC
        LIMIT 1
        """,
        (business_id, "waiting"),
    )


def create_ticket(business_id, service_id, customer_name, phone):
    with get_connection() as conn:
        service = conn.execute(
            "SELECT * FROM services WHERE id = ? AND business_id = ?",
            (service_id, business_id),
        ).fetchone()
        if not service:
            return None

        ticket_number = generate_ticket_number(conn, business_id)
        cursor = conn.execute("""
            INSERT INTO tickets
            (business_id, service_id, customer_name, phone, ticket_number, status, position,
             estimated_waiting_minutes, created_at, called_at, started_at, completed_at, cancelled_at, absent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            business_id,
            service_id,
            customer_name,
            phone,
            ticket_number,
            "waiting",
            None,
            0,
            now_text(),
            None,
            None,
            None,
            None,
            None,
        ))
        ticket_id = cursor.lastrowid
    return get_ticket(ticket_id)


def update_ticket_status(ticket_id, new_status):
    if new_status not in ALL_STATUSES:
        raise ValueError("Invalid ticket status")

    timestamp_fields = {
        "called": "called_at",
        "in_service": "started_at",
        "completed": "completed_at",
        "cancelled": "cancelled_at",
        "absent": "absent_at",
    }
    with get_connection() as conn:
        field = timestamp_fields.get(new_status)
        if field:
            conn.execute(f"UPDATE tickets SET status = ?, {field} = ? WHERE id = ?", (new_status, now_text(), ticket_id))
        else:
            conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id))


def set_ticket_position(ticket_id, position, estimated_waiting):
    with get_connection() as conn:
        conn.execute(
            "UPDATE tickets SET position = ?, estimated_waiting_minutes = ? WHERE id = ?",
            (position, estimated_waiting, ticket_id),
        )


def generate_ticket_number(conn, business_id):
    row = conn.execute(
        "SELECT ticket_number FROM tickets WHERE business_id = ? ORDER BY id DESC LIMIT 1",
        (business_id,),
    ).fetchone()
    next_number = 1
    if row and row["ticket_number"] and row["ticket_number"][1:].isdigit():
        next_number = int(row["ticket_number"][1:]) + 1
    return f"A{next_number:03d}"
