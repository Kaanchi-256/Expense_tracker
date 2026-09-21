"""
Tests for Step 08 — Edit Expenses.

Spec: .claude/specs/08-edit-expenses.md

These tests exercise the GET/POST /expenses/<id>/edit route (auth guard,
pre-filled form rendering, ownership/not-found handling via abort(404),
amount/category validation with value preservation on error, and the fact
that a successful edit persists via database/db.py and is reflected on the
profile page's transaction list). Test logic is derived from the spec's
Routes, Database changes, Rules for implementation, and Definition of Done
sections — app.py and database/db.py were only read to learn route names,
session keys, field names, and to confirm get_expense_by_id()/
update_expense() exist, not to derive expected behavior from their bodies.
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

VALID_UPDATE_PAYLOAD = {
    "amount": "42.50",
    "category": "Food",
    "date": "2024-05-01",
    "description": "Groceries",
}


# --------------------------------------------------------------------- #
# Auth guard
# DoD: "Logged out, visiting /expenses/1/edit redirects to /login"
# --------------------------------------------------------------------- #

def test_get_edit_expense_without_session_redirects_to_login(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    response = client.get(f"/expenses/{expense_id}/edit")

    assert response.status_code == 302, "Unauthenticated GET should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated GET /expenses/<id>/edit should redirect to login"
    )


def test_post_edit_expense_without_session_redirects_to_login(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    response = client.post(f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD)

    assert response.status_code == 302, "Unauthenticated POST should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated POST /expenses/<id>/edit should redirect to login"
    )
    unchanged = fetch_expense(expense_id)
    assert unchanged["amount"] == pytest.approx(ORIGINAL["amount"]), (
        "No update should occur for an unauthenticated request"
    )


# --------------------------------------------------------------------- #
# Ownership / not-found handling
# DoD: another user's expense -> 404; nonexistent id -> 404
# --------------------------------------------------------------------- #

def test_get_edit_expense_owned_by_another_user_returns_404(app, client):
    owner_id = create_test_user(email="owner@example.com", name="Owner")
    other_id = create_test_user(email="other@example.com", name="Other")
    expense_id = insert_expense(owner_id, **ORIGINAL)

    login(client, other_id)
    response = client.get(f"/expenses/{expense_id}/edit")

    assert response.status_code == 404, (
        "Editing another user's expense must return 404, not 403 or a redirect"
    )


def test_post_edit_expense_owned_by_another_user_returns_404_and_no_update(app, client):
    owner_id = create_test_user(email="owner@example.com", name="Owner")
    other_id = create_test_user(email="other@example.com", name="Other")
    expense_id = insert_expense(owner_id, **ORIGINAL)

    login(client, other_id)
    response = client.post(f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD)

    assert response.status_code == 404
    unchanged = fetch_expense(expense_id)
    assert unchanged["amount"] == pytest.approx(ORIGINAL["amount"]), (
        "An attempted edit by a non-owner must not modify the row"
    )
    assert unchanged["category"] == ORIGINAL["category"]


def test_get_edit_expense_nonexistent_id_returns_404(app, client):
    user_id = create_test_user()
    login(client, user_id)

    response = client.get("/expenses/999999/edit")

    assert response.status_code == 404, (
        "Editing a non-existent expense id must return 404"
    )


def test_post_edit_expense_nonexistent_id_returns_404(app, client):
    user_id = create_test_user()
    login(client, user_id)

    response = client.post("/expenses/999999/edit", data=VALID_UPDATE_PAYLOAD)

    assert response.status_code == 404


# --------------------------------------------------------------------- #
# Happy path — GET renders a pre-filled form
# DoD: "renders a form pre-filled with its current amount, category, date,
# and description"
# --------------------------------------------------------------------- #

def test_get_edit_expense_own_expense_renders_prefilled_form(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(f"/expenses/{expense_id}/edit")

    assert response.status_code == 200
    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == "expenses_edit.html", (
        "Spec requires a new expenses_edit.html template, not the add-expense one"
    )

    # The current values should be present in the rendered response.
    assert str(ORIGINAL["amount"]).encode() in response.data or b"20.0" in response.data or b"20" in response.data
    assert ORIGINAL["category"].encode() in response.data
    assert ORIGINAL["date"].encode() in response.data
    assert ORIGINAL["description"].encode() in response.data


def test_get_edit_expense_does_not_return_raw_string(app, client):
    """Spec: replaces the stub that returned a raw string."""
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(f"/expenses/{expense_id}/edit")

    assert response.status_code == 200
    assert len(templates) == 1, "GET /expenses/<id>/edit must render a template, not a raw string"


def test_get_edit_expense_category_options_come_from_categories_list(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    response = client.get(f"/expenses/{expense_id}/edit")

    assert response.status_code == 200
    for category in db.CATEGORIES:
        assert category.encode() in response.data, (
            f"Expected category '{category}' to appear as a select option "
            "(spec: reuse CATEGORIES from database/db.py)"
        )


# --------------------------------------------------------------------- #
# Happy path — valid submission updates and redirects
# DoD: "Submitting the form with a valid amount/category/date updates the
# expense and redirects to /profile"
# --------------------------------------------------------------------- #

def test_post_valid_update_persists_and_redirects_to_profile(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    response = client.post(
        f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD, follow_redirects=False
    )

    assert response.status_code == 302, "Valid submission should redirect"
    assert response.headers["Location"].endswith("/profile"), (
        "Valid submission should redirect to /profile"
    )

    row = fetch_expense(expense_id)
    assert row["amount"] == pytest.approx(42.50)
    assert row["category"] == "Food"
    assert row["date"] == "2024-05-01"
    assert row["description"] == "Groceries"
    assert row["user_id"] == user_id, "Update must not change the expense's owner"


def test_post_valid_update_does_not_create_a_new_row(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD, follow_redirects=False)

    conn = db.get_db()
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
    ).fetchone()["c"]
    conn.close()
    assert count == 1, "Editing must update the existing row in place, not insert a new one"


def test_post_valid_update_does_not_affect_other_users_expenses(app, client):
    user_id = create_test_user(email="me@example.com", name="Me")
    other_id = create_test_user(email="other@example.com", name="Other")
    expense_id = insert_expense(user_id, **ORIGINAL)
    other_expense_id = insert_expense(other_id, 5.00, "Bills", "2024-01-01", "Water")
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD, follow_redirects=False)

    other_row = fetch_expense(other_expense_id)
    assert other_row["amount"] == pytest.approx(5.00)
    assert other_row["category"] == "Bills"
    assert other_row["description"] == "Water"


# --------------------------------------------------------------------- #
# DB side effects — reflected on the profile page
# DoD: "After a successful edit, the updated values are visible in the
# profile page's transaction list"
# --------------------------------------------------------------------- #

def test_updated_expense_appears_in_profile_recent_transactions(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD, follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    transactions = context["transactions"]
    matching = [
        row for row in transactions
        if row["id"] == expense_id
        and row["date"] == "2024-05-01"
        and row["category"] == "Food"
        and row["description"] == "Groceries"
    ]
    assert len(matching) == 1, (
        "The edited expense should reflect its new values in the profile "
        "page's recent transactions"
    )
    assert matching[0]["amount"] == pytest.approx(42.50)

    stale = [row for row in transactions if row["category"] == ORIGINAL["category"]]
    assert stale == [], "The old category value should no longer appear for this expense"


def test_updated_expense_reflected_in_profile_category_breakdown(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    client.post(f"/expenses/{expense_id}/edit", data=VALID_UPDATE_PAYLOAD, follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    categories = {c["name"]: c for c in context["categories"]}
    assert "Food" in categories, "The new category should appear in the breakdown"
    assert categories["Food"]["total"] == pytest.approx(42.50)
    assert "Transport" not in categories, (
        "The old category should no longer be present once its only expense is edited away"
    )


# --------------------------------------------------------------------- #
# Validation — amount
# DoD: "invalid amount (blank, zero, negative, non-numeric) re-renders the
# form with an error and preserves entered values"
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["", "0", "-5", "-0.01", "abc", "twenty", "NaN", "Infinity"],
)
def test_post_invalid_amount_rerenders_form_with_error_and_no_update(app, client, bad_amount):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    payload = dict(VALID_UPDATE_PAYLOAD, amount=bad_amount)

    with captured_templates(app) as templates:
        response = client.post(f"/expenses/{expense_id}/edit", data=payload)

    assert response.status_code == 200, (
        "Invalid amount should re-render the form, not redirect"
    )
    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == "expenses_edit.html"
    assert context.get("error"), "An error message should be present in the context"

    unchanged = fetch_expense(expense_id)
    assert unchanged["amount"] == pytest.approx(ORIGINAL["amount"]), (
        "The expense must not be updated when the amount is invalid"
    )


def test_post_invalid_amount_preserves_submitted_values(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    payload = dict(VALID_UPDATE_PAYLOAD, amount="not-a-number")

    with captured_templates(app) as templates:
        response = client.post(f"/expenses/{expense_id}/edit", data=payload)

    assert response.status_code == 200
    context = templates[0][1]
    # Spec DoD: "re-renders the form with an error and preserves entered
    # values" — the newly submitted category/date/description should be
    # shown back, not the stale DB values.
    assert context.get("category") == VALID_UPDATE_PAYLOAD["category"]
    assert context.get("date") == VALID_UPDATE_PAYLOAD["date"]
    assert context.get("description") == VALID_UPDATE_PAYLOAD["description"]


def test_post_whitespace_only_amount_is_rejected(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    payload = dict(VALID_UPDATE_PAYLOAD, amount="   ")

    with captured_templates(app) as templates:
        response = client.post(f"/expenses/{expense_id}/edit", data=payload)

    assert response.status_code == 200
    context = templates[0][1]
    assert context.get("error")
    unchanged = fetch_expense(expense_id)
    assert unchanged["amount"] == pytest.approx(ORIGINAL["amount"])


# --------------------------------------------------------------------- #
# Validation — category
# DoD: "category not in CATEGORIES re-renders the form with an error"
# --------------------------------------------------------------------- #

def test_post_invalid_category_rerenders_form_with_error_and_no_update(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    payload = dict(VALID_UPDATE_PAYLOAD, category="NotARealCategory")

    with captured_templates(app) as templates:
        response = client.post(f"/expenses/{expense_id}/edit", data=payload)

    assert response.status_code == 200, (
        "Invalid category should re-render the form, not redirect"
    )
    context = templates[0][1]
    assert context.get("error"), "An error message should be present for invalid category"

    unchanged = fetch_expense(expense_id)
    assert unchanged["category"] == ORIGINAL["category"], (
        "The expense's category must not be updated when the submitted category is invalid"
    )


def test_post_empty_category_rerenders_form_with_error_and_no_update(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    payload = dict(VALID_UPDATE_PAYLOAD, category="")

    with captured_templates(app) as templates:
        response = client.post(f"/expenses/{expense_id}/edit", data=payload)

    assert response.status_code == 200
    context = templates[0][1]
    assert context.get("error")
    unchanged = fetch_expense(expense_id)
    assert unchanged["category"] == ORIGINAL["category"]


@pytest.mark.parametrize("category", db.CATEGORIES)
def test_post_each_valid_category_is_accepted(app, client, category):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    payload = dict(VALID_UPDATE_PAYLOAD, category=category)
    response = client.post(f"/expenses/{expense_id}/edit", data=payload, follow_redirects=False)

    assert response.status_code == 302, f"Category '{category}' should be accepted"
    row = fetch_expense(expense_id)
    assert row["category"] == category


# --------------------------------------------------------------------- #
# POST with no form body
# --------------------------------------------------------------------- #

def test_post_edit_expense_with_no_form_data_returns_400(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    response = client.post(
        f"/expenses/{expense_id}/edit", data=None, content_type="multipart/form-data"
    )

    assert response.status_code == 400, (
        "POST with no form data should abort with 400, matching add_expense's pattern"
    )
    unchanged = fetch_expense(expense_id)
    assert unchanged["amount"] == pytest.approx(ORIGINAL["amount"])


# --------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------- #

def test_post_sql_injection_attempt_in_description_is_stored_safely(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    malicious = "'); DROP TABLE expenses; --"
    payload = dict(VALID_UPDATE_PAYLOAD, description=malicious)

    response = client.post(f"/expenses/{expense_id}/edit", data=payload, follow_redirects=False)

    assert response.status_code == 302, "Malicious input should be handled safely, not crash"
    row = fetch_expense(expense_id)
    assert row is not None, "The expenses table must still exist and contain the row"
    assert row["description"] == malicious, (
        "The malicious string should be stored verbatim as data, not executed as SQL"
    )


def test_post_very_long_description_is_accepted(app, client):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)
    login(client, user_id)

    long_description = "x" * 5000
    payload = dict(VALID_UPDATE_PAYLOAD, description=long_description)

    response = client.post(f"/expenses/{expense_id}/edit", data=payload, follow_redirects=False)

    assert response.status_code == 302
    row = fetch_expense(expense_id)
    assert row["description"] == long_description


# --------------------------------------------------------------------- #
# DB-layer behavior (direct, framework-independent of the route)
# Spec: "New functions needed in database/db.py: get_expense_by_id(),
# update_expense()"
# --------------------------------------------------------------------- #

def test_db_get_expense_by_id_returns_matching_row(app):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    row = db.get_expense_by_id(expense_id, user_id)

    assert row is not None
    assert row["id"] == expense_id
    assert row["user_id"] == user_id
    assert row["amount"] == pytest.approx(ORIGINAL["amount"])
    assert row["category"] == ORIGINAL["category"]
    assert row["date"] == ORIGINAL["date"]
    assert row["description"] == ORIGINAL["description"]


def test_db_get_expense_by_id_returns_none_for_missing_id(app):
    user_id = create_test_user()
    row = db.get_expense_by_id(999999, user_id)
    assert row is None, "get_expense_by_id must return None, not raise, for a missing row"


def test_db_get_expense_by_id_returns_none_for_mismatched_user(app):
    owner_id = create_test_user(email="owner@example.com")
    other_id = create_test_user(email="other@example.com")
    expense_id = insert_expense(owner_id, **ORIGINAL)

    row = db.get_expense_by_id(expense_id, other_id)
    assert row is None, "get_expense_by_id must not return a row owned by a different user"


def test_db_update_expense_persists_new_values(app):
    user_id = create_test_user()
    expense_id = insert_expense(user_id, **ORIGINAL)

    db.update_expense(expense_id, 99.99, "Shopping", "2024-06-15", "New description")

    row = fetch_expense(expense_id)
    assert row["amount"] == pytest.approx(99.99)
    assert row["category"] == "Shopping"
    assert row["date"] == "2024-06-15"
    assert row["description"] == "New description"
    assert row["user_id"] == user_id, "update_expense must not change the owning user_id"


def test_db_update_expense_uses_parameterized_sql():
    """Spec: 'Parameterised queries only' for update_expense()."""
    import inspect

    source = inspect.getsource(db.update_expense)
    assert "?" in source, "update_expense must use ? placeholders"
    assert "f\"" not in source and "f'" not in source, (
        "update_expense must not build SQL with f-strings"
    )
    assert ".format(" not in source, (
        "update_expense must not build SQL with str.format()"
    )


def test_db_get_expense_by_id_uses_parameterized_sql():
    """Spec: 'Parameterised queries only' for get_expense_by_id()."""
    import inspect

    source = inspect.getsource(db.get_expense_by_id)
    assert "?" in source, "get_expense_by_id must use ? placeholders"
    assert "f\"" not in source and "f'" not in source, (
        "get_expense_by_id must not build SQL with f-strings"
    )
