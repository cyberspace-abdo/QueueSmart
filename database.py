import os
import sqlite3
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "noubti.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = get_connection()
    try:
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
                price INTEGER NOT NULL,
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
                phone TEXT NOT NULL,
                ticket_number TEXT NOT NULL,
                status TEXT NOT NULL,
                position INTEGER,
                estimated_waiting_minutes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                called_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                FOREIGN KEY (business_id) REFERENCES businesses(id),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """)
        conn.commit()
        seed_sample_data(conn)
    finally:
        conn.close()


def seed_sample_data(conn):
    count = conn.execute("SELECT COUNT(*) as count FROM businesses").fetchone()["count"]
    if count > 0:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
        conn.execute("""
            INSERT INTO services (business_id, name, duration, price, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (business_id, name, duration, price, now))

    conn.commit()


def get_all_businesses():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM businesses ORDER BY id").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_business(business_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_services_for_business(business_id):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM services WHERE business_id = ? ORDER BY id", (business_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_service(service_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_service(business_id, name, duration, price):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO services (business_id, name, duration, price, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (business_id, name, duration, price, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    finally:
        conn.close()


def update_service(service_id, name, duration, price):
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE services SET name = ?, duration = ?, price = ?
            WHERE id = ?
        """, (name, duration, price, service_id))
        conn.commit()
    finally:
        conn.close()


def delete_service(service_id):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
        conn.commit()
    finally:
        conn.close()


def get_tickets_for_business(business_id):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM tickets WHERE business_id = ? ORDER BY created_at ASC", (business_id,)).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_ticket(ticket_id):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_next_waiting_ticket(business_id):
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM tickets
            WHERE business_id = ? AND status = ?
            ORDER BY created_at ASC
            LIMIT 1
        """, (business_id, "waiting")).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_ticket(business_id, service_id, customer_name, phone):
    conn = get_connection()
    try:
        business = conn.execute("SELECT * FROM businesses WHERE id = ?", (business_id,)).fetchone()
        service = conn.execute("SELECT * FROM services WHERE id = ?", (service_id,)).fetchone()
        if not business or not service:
            return None

        ticket_number = generate_ticket_number(conn, business_id, "A")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor = conn.execute("""
            INSERT INTO tickets
            (business_id, service_id, customer_name, phone, ticket_number, status, position,
             estimated_waiting_minutes, created_at, called_at, started_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (business_id, service_id, customer_name, phone, ticket_number, "waiting", None, 0, now, None, None, None))
        conn.commit()
        return get_ticket(cursor.lastrowid)
    finally:
        conn.close()


def update_ticket_status(ticket_id, new_status):
    conn = get_connection()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if new_status == "called":
            conn.execute("UPDATE tickets SET status = ?, called_at = ? WHERE id = ?", (new_status, now, ticket_id))
        elif new_status == "in_service":
            conn.execute("UPDATE tickets SET status = ?, started_at = ? WHERE id = ?", (new_status, now, ticket_id))
        elif new_status == "completed":
            conn.execute("UPDATE tickets SET status = ?, completed_at = ? WHERE id = ?", (new_status, now, ticket_id))
        else:
            conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id))
        conn.commit()
    finally:
        conn.close()


def set_ticket_position(ticket_id, position, estimated_waiting):
    conn = get_connection()
    try:
        conn.execute("UPDATE tickets SET position = ?, estimated_waiting_minutes = ? WHERE id = ?", (position, estimated_waiting, ticket_id))
        conn.commit()
    finally:
        conn.close()


def generate_ticket_number(conn, business_id, prefix):
    row = conn.execute("SELECT COUNT(*) as count FROM tickets WHERE business_id = ?", (business_id,)).fetchone()
    next_number = row["count"] + 1
    return f"{prefix}{next_number:03d}"