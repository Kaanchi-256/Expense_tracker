import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT date, description, category, amount
        FROM expenses
        WHERE user_id = ?
        ORDER BY date DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    conn.close()
    return rows


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_user_stats(user_id):
    conn = get_db()
    totals = conn.execute(
        """
        SELECT COUNT(*) AS transaction_count,
               COALESCE(SUM(amount), 0) AS total_spent
        FROM expenses
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()
    top = conn.execute(
        """
        SELECT category
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY SUM(amount) DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    return {
        "total_spent": totals["total_spent"],
        "transaction_count": totals["transaction_count"],
        "top_category": top["category"] if top else None,
    }


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    conn = get_db()

    existing = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    if existing:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = date.today()

    sample_expenses = [
        (user_id, 12.50, "Food", today.replace(day=1).isoformat(), "Groceries"),
        (user_id, 3.75, "Transport", today.replace(day=3).isoformat(), "Bus fare"),
        (user_id, 85.00, "Bills", today.replace(day=5).isoformat(), "Electricity bill"),
        (user_id, 40.00, "Health", today.replace(day=8).isoformat(), "Pharmacy"),
        (user_id, 25.00, "Entertainment", today.replace(day=10).isoformat(), "Movie tickets"),
        (user_id, 60.00, "Shopping", today.replace(day=14).isoformat(), "New shoes"),
        (user_id, 15.00, "Other", today.replace(day=18).isoformat(), "Miscellaneous"),
        (user_id, 22.30, "Food", today.replace(day=21).isoformat(), "Restaurant dinner"),
    ]

    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        sample_expenses,
    )

    conn.commit()
    conn.close()


def get_user_by_email(email):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_category_breakdown(user_id):
    conn = get_db()
    rows = conn.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM expenses
        WHERE user_id = ?
        GROUP BY category
        ORDER BY total DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return []

    grand_total = sum(r["total"] for r in rows)
    if not grand_total:
        return [{"name": r["category"], "total": r["total"], "percent": 0} for r in rows]

    categories = []
    percents = []
    for r in rows:
        pct = round(r["total"] * 100 / grand_total)
        percents.append(pct)
        categories.append({"name": r["category"], "total": r["total"], "percent": pct})

    remainder = 100 - sum(percents)
    categories[0]["percent"] += remainder  # largest category (rows already sorted desc) absorbs rounding remainder

    return categories
