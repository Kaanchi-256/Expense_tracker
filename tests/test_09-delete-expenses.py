"""
Tests for Step 09 — Delete Expenses.

Spec: .claude/specs/09-delete-expenses.md

These tests exercise the GET/POST /expenses/<id>/delete route (auth guard,
confirmation-page rendering, ownership/not-found handling via abort(404),
the idempotent-safety of GET, and the fact that a successful POST delete
removes the row via database/db.py and is reflected on the profile page's
transaction list and stats). Test logic is derived from the spec's Routes,
Database changes, Rules for implementation, and Definition of Done
sections — app.py and database/db.py were only read to learn the route's
URL parameter name (expense_id, not id), session keys, and to confirm
get_expense_by_id()/delete_expense() exist, not to derive expected
behavior from their bodies.
"""
from contextlib import contextmanager

import pytest
from flask import template_rendered
from werkzeug.security import generate_password_hash

import database.db as db
from app import app as flask_app


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #

@pytest.fixture
def app(monkeypatch, tmp_path):
    """Point database/db.py at an isolated, per-test SQLite file."""
    db_path = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_path))
    db.init_db()

    flask_app.config.update(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
        }
    )
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def create_test_user(email="user@example.com", name="Test User"):
    return db.create_user(name, email, generate_password_hash("password123"))


def insert_expense(user_id, amount, category, date, description=""):
    conn = db.get_db()
    cursor = conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date, description),
    )
    conn.commit()
    expense_id = cursor.lastrowid
    conn.close()
    return expense_id


def login(client, user_id, name="Test User"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = name


def fetch_expense(expense_id):
    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return row


@contextmanager
def captured_templates(flask_application):
    """Capture the (template, context) pairs passed to render_template()."""
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, flask_application)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, flask_application)


ORIGINAL = {
    "amount": 20.00,
    "category": "Transport",
    "date": "2024-02-01",
    "description": "Taxi",
}


# --------------------------------------------------------------------- #
# Auth guard
# DoD: "Logged out, visiting /expenses/1/delete redirects to /login"
# --------------------------------------------------------------------- #

def test_get_delete_expense_without_session_redirects_to_login(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302, "Unauthenticated GET should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated GET /expenses/<id>/delete should redirect to login"
    )
    assert fetch_expense(expense_id) is not None, (
        "An unauthenticated GET must not delete anything"
    )


def test_post_delete_expense_without_session_redirects_to_login(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302, "Unauthenticated POST should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated POST /expenses/<id>/delete should redirect to login"
    )
    assert fetch_expense(expense_id) is not None, (
        "An unauthenticated POST must not delete the expense"
    )


# --------------------------------------------------------------------- #
# Ownership / not-found handling
# DoD: another user's expense -> 404; nonexistent id -> 404
# --------------------------------------------------------------------- #

def test_get_delete_expense_owned_by_another_user_returns_404(app, client):
    owner_id = create_test_user(email="owner@example.com", name="Owner")
    other_id = create_test_user(email="other@example.com", name="Other")
    expense_id = insert_expense(owner_id, **ORIGINAL)

    login(client, other_id)
    response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 404, (
        "Viewing the delete confirmation for another user's expense must return 404, not 403"
    )
    assert fetch_expense(expense_id) is not None, (
        "A 404 response must not delete the expense"
    )


def test_post_delete_expense_owned_by_another_user_returns_404_and_no_delete(app, client):
    owner_id = create_test_user(email="owner@example.com", name="Owner")
    other_id = create_test_user(email="other@example.com", name="Other")
    expense_id = insert_expense(owner_id, **ORIGINAL)

    login(client, other_id)
    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 404
    unchanged = fetch_expense(expense_id)
    assert unchanged is not None, (
        "An attempted delete by a non-owner must not remove the row"
    )
    assert unchanged["category"] == ORIGINAL["category"]


def test_get_delete_expense_nonexistent_id_returns_404(app, client):
    user_id = create_test_user()
    login(client, user_id)

    response = client.get("/expenses/999999/delete")

    assert response.status_code == 404, (
        "Viewing the delete confirmation for a non-existent expense id must return 404"
    )


def test_post_delete_expense_nonexistent_id_returns_404(app, client):
    user_id = create_test_user()
    login(client, user_id)

    response = client.post("/expenses/999999/delete")

    assert response.status_code == 404


# --------------------------------------------------------------------- #
# Happy path — GET renders a confirmation page with expense details
# DoD: "renders a confirmation page showing that expense's date, category,
# amount, and description"
# --------------------------------------------------------------------- #

def test_get_delete_expense_own_expense_renders_confirmation_page(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 200
    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == "expenses_delete.html", (
        "Spec requires a new expenses_delete.html confirmation template"
    )

    assert ORIGINAL["date"].encode() in response.data
    assert ORIGINAL["category"].encode() in response.data
    assert ORIGINAL["description"].encode() in response.data
    assert (
        str(ORIGINAL["amount"]).encode() in response.data
        or b"20.0" in response.data
        or b"20" in response.data
    ), "The confirmation page should show the expense's amount"


def test_get_delete_expense_does_not_return_raw_string(app, client):
    """Spec: replaces the stub that returned a raw string."""
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 200
    assert len(templates) == 1, (
        "GET /expenses/<id>/delete must render a template, not a raw string"
    )


# --------------------------------------------------------------------- #
# Idempotent safety — a GET must never delete
# DoD: "A plain GET to the confirmation page does not delete the expense —
# reloading it repeatedly leaves the expense untouched"
# --------------------------------------------------------------------- #

def test_repeated_get_requests_do_not_delete_the_expense(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    for _ in range(5):
        response = client.get(f"/expenses/{expense_id}/delete")
        assert response.status_code == 200

    row = fetch_expense(expense_id)
    assert row is not None, (
        "Reloading the confirmation page must never delete the expense"
    )
    assert row["amount"] == pytest.approx(ORIGINAL["amount"])
    assert row["category"] == ORIGINAL["category"]
    assert row["date"] == ORIGINAL["date"]
    assert row["description"] == ORIGINAL["description"]


# --------------------------------------------------------------------- #
# Happy path — POST deletes and redirects
# DoD: "Submitting the confirmation form (POST) deletes the expense and
# redirects to /profile"
# --------------------------------------------------------------------- #

def test_post_delete_expense_removes_row_and_redirects_to_profile(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    response = client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    assert response.status_code == 302, "A successful delete should redirect"
    assert response.headers["Location"].endswith("/profile"), (
        "A successful delete should redirect to /profile"
    )
    assert fetch_expense(expense_id) is None, (
        "The expense row must be removed from the database after POST delete"
    )


def test_post_delete_expense_does_not_affect_other_users_expenses(app, client):
    user_id = create_test_user(email="me@example.com", name="Me")
    other_id = create_test_user(email="other@example.com", name="Other")
    expense_id = insert_expense(user_id, **ORIGINAL)
    other_expense_id = insert_expense(other_id, 5.00, "Bills", "2024-01-01", "Water")
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    other_row = fetch_expense(other_expense_id)
    assert other_row is not None, (
        "Deleting one user's expense must not remove another user's expense"
    )
    assert other_row["amount"] == pytest.approx(5.00)
    assert other_row["category"] == "Bills"


def test_post_delete_expense_only_removes_targeted_row(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    other_expense_id = insert_expense(user_id, 5.00, "Bills", "2024-01-01", "Water")
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    conn = db.get_db()
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    conn.close()
    assert count == 1, "Only the targeted expense should be deleted"
    assert fetch_expense(other_expense_id) is not None


# --------------------------------------------------------------------- #
# DB side effects — reflected on the profile page
# DoD: "After deletion, the expense no longer appears in the profile
# page's transaction list, and profile stats (total spent, transaction
# count, top category) reflect its removal"
# --------------------------------------------------------------------- #

def test_deleted_expense_no_longer_appears_in_profile_recent_transactions(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    other_expense_id = insert_expense(user_id, 5.00, "Bills", "2024-01-01", "Water")
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    transaction_ids = [row["id"] for row in context["transactions"]]
    assert expense_id not in transaction_ids, (
        "The deleted expense must not appear in the profile page's transactions"
    )
    assert other_expense_id in transaction_ids, (
        "Other, non-deleted expenses must still appear"
    )


def test_deleted_expense_reflected_in_profile_stats(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    remaining_id = insert_expense(user_id, 5.00, "Bills", "2024-01-01", "Water")
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    stats = context["stats"]
    assert stats["transaction_count"] == 1, (
        "Transaction count should decrease by one after deletion"
    )
    assert stats["total_spent"] == pytest.approx(5.00), (
        "Total spent should reflect the removal of the deleted expense's amount"
    )
    assert stats["top_category"] == "Bills", (
        "Top category should reflect only the remaining expenses"
    )
    assert remaining_id in [row["id"] for row in context["transactions"]]


def test_deleted_expense_reflected_in_profile_category_breakdown(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    category_names = {c["name"] for c in context["categories"]}
    assert "Transport" not in category_names, (
        "The deleted expense's category should no longer appear in the breakdown "
        "once its only expense is removed"
    )


def test_deleting_last_expense_results_in_zero_stats(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/delete", follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    stats = context["stats"]
    assert stats["transaction_count"] == 0
    assert stats["total_spent"] == 0
    assert context["transactions"] == []


# --------------------------------------------------------------------- #
# Cancel behavior
# DoD: "The 'Cancel' link on the confirmation page returns to /profile
# without deleting anything"
# --------------------------------------------------------------------- #

def test_confirmation_page_contains_cancel_link_to_profile(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 200
    assert b'href="/profile"' in response.data, (
        "The confirmation page must contain a Cancel link back to /profile"
    )


def test_visiting_cancel_link_target_does_not_delete_expense(app, client):
    """Simulates following the Cancel link: a GET to /profile is not the
    delete route and must never remove the expense."""
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    client.get(f"/expenses/{expense_id}/delete")
    response = client.get("/profile")

    assert response.status_code == 200
    assert fetch_expense(expense_id) is not None, (
        "Cancelling (navigating to /profile) must not delete the expense"
    )


# --------------------------------------------------------------------- #
# DB-layer behavior (direct, framework-independent of the route)
# Spec: "New function needed in database/db.py: delete_expense(expense_id)"
# --------------------------------------------------------------------- #

def test_db_delete_expense_removes_row(app):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    db.delete_expense(expense_id, user_id)

    assert fetch_expense(expense_id) is None, (
        "delete_expense must remove the row with the matching id"
    )


def test_db_delete_expense_only_removes_targeted_row(app):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    other_expense_id = insert_expense(user_id, 5.00, "Bills", "2024-01-01", "Water")

    db.delete_expense(expense_id, user_id)

    assert fetch_expense(expense_id) is None
    assert fetch_expense(other_expense_id) is not None, (
        "delete_expense must not remove unrelated rows"
    )


def test_db_delete_expense_does_not_remove_another_users_row(app):
    owner_id = create_test_user(email="owner3@example.com")
    other_id = create_test_user(email="other3@example.com")
    expense_id = insert_expense(owner_id, **ORIGINAL)

    db.delete_expense(expense_id, other_id)

    assert fetch_expense(expense_id) is not None, (
        "delete_expense must not remove a row owned by a different user"
    )


def test_db_delete_expense_nonexistent_id_does_not_raise(app):
    """Deleting a non-existent id at the db layer should be a no-op, not an error."""
    user_id = create_test_user()
    db.delete_expense(999999, user_id)  # should not raise


def test_db_delete_expense_uses_parameterized_sql():
    """Spec: 'DELETE FROM expenses WHERE id = ?' — parameterised queries only."""
    import inspect

    source = inspect.getsource(db.delete_expense)
    assert "?" in source, "delete_expense must use ? placeholders"
    assert "f\"" not in source and "f'" not in source, (
        "delete_expense must not build SQL with f-strings"
    )
    assert ".format(" not in source, (
        "delete_expense must not build SQL with str.format()"
    )
