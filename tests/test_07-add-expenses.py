"""
Tests for Step 07 — Add Expenses.

Spec: .claude/specs/07-add-expenses.md

These tests exercise the GET/POST /expenses/add route (auth guard, form
rendering, validation, DB insertion scoped to the current user_id) and the
new database/db.py create_expense() helper, plus the fact that a newly
added expense flows through into the profile page's recent transactions
and category breakdown. Test logic is derived from the spec's Routes,
Database changes, and Definition of Done sections, not from reading the
add_expense view's implementation (that was only read to learn route
names, session keys, and field names needed to wire the tests up).
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


def insert_expense(user_id, amount, category, date_str, description=""):
    conn = db.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    conn.close()


def login(client, user_id, name="Test User"):
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = name


def fetch_all_expenses(user_id=None):
    conn = db.get_db()
    if user_id is None:
        rows = conn.execute("SELECT * FROM expenses").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchall()
    conn.close()
    return rows


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


VALID_PAYLOAD = {
    "amount": "42.50",
    "category": "Food",
    "date": "2024-05-01",
    "description": "Groceries",
}


# --------------------------------------------------------------------- #
# Auth guard
# --------------------------------------------------------------------- #

def test_get_add_expense_without_session_redirects_to_login(client):
    response = client.get("/expenses/add")
    assert response.status_code == 302, "Unauthenticated GET should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated GET /expenses/add should redirect to login"
    )


def test_post_add_expense_without_session_redirects_to_login(client):
    response = client.post("/expenses/add", data=VALID_PAYLOAD)
    assert response.status_code == 302, "Unauthenticated POST should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated POST /expenses/add should redirect to login"
    )
    assert fetch_all_expenses() == [], (
        "No expense should be inserted for an unauthenticated request"
    )


# --------------------------------------------------------------------- #
# GET renders the form
# --------------------------------------------------------------------- #

def test_get_add_expense_logged_in_renders_form(app, client):
    user_id = create_test_user()
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/expenses/add")

    assert response.status_code == 200
    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == "expenses_add.html"

    # Form fields expected per spec: amount, category (select), date, description
    assert b"amount" in response.data.lower()
    assert b"category" in response.data.lower()
    assert b"date" in response.data.lower()
    assert b"description" in response.data.lower()


def test_get_add_expense_category_options_come_from_categories_list(app, client):
    user_id = create_test_user()
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/expenses/add")

    assert response.status_code == 200
    for category in db.CATEGORIES:
        assert category.encode() in response.data, (
            f"Expected category '{category}' to appear as a select option"
        )


def test_get_add_expense_does_not_return_raw_string(app, client):
    """Spec DoD: no raw string responses remain for /expenses/add."""
    user_id = create_test_user()
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/expenses/add")

    assert response.status_code == 200
    assert len(templates) == 1, "GET /expenses/add must render a template, not a raw string"


# --------------------------------------------------------------------- #
# Happy path — valid submission
# --------------------------------------------------------------------- #

def test_post_valid_expense_inserts_row_and_redirects_to_profile(app, client):
    user_id = create_test_user()
    login(client, user_id)

    response = client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)

    assert response.status_code == 302, "Valid submission should redirect"
    assert response.headers["Location"].endswith("/profile"), (
        "Valid submission should redirect to /profile"
    )

    rows = fetch_all_expenses(user_id)
    assert len(rows) == 1, "Exactly one expense row should be inserted"
    row = rows[0]
    assert row["user_id"] == user_id, "Inserted expense must be scoped to the current user"
    assert row["amount"] == pytest.approx(42.50)
    assert row["category"] == "Food"
    assert row["date"] == "2024-05-01"
    assert row["description"] == "Groceries"


def test_post_valid_expense_scoped_to_correct_user_only(app, client):
    other_user_id = create_test_user(email="other@example.com", name="Other User")
    user_id = create_test_user(email="me@example.com", name="Me")
    login(client, user_id)

    client.post("/expenses/add", data=VALID_PAYLOAD)

    my_rows = fetch_all_expenses(user_id)
    other_rows = fetch_all_expenses(other_user_id)
    assert len(my_rows) == 1, "The new expense should belong to the logged-in user"
    assert len(other_rows) == 0, "The other user must not receive the new expense"


def test_new_expense_appears_in_profile_recent_transactions(app, client):
    user_id = create_test_user()
    login(client, user_id)

    client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    transactions = context["transactions"]
    matching = [
        row for row in transactions
        if row["date"] == "2024-05-01"
        and row["category"] == "Food"
        and row["description"] == "Groceries"
    ]
    assert len(matching) == 1, (
        "The newly added expense should appear in the profile page's recent transactions"
    )
    assert matching[0]["amount"] == pytest.approx(42.50)


def test_new_expense_appears_in_profile_category_breakdown(app, client):
    user_id = create_test_user()
    login(client, user_id)

    client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    categories = {c["name"]: c for c in context["categories"]}
    assert "Food" in categories, (
        "The newly added expense's category should appear in the category breakdown"
    )
    assert categories["Food"]["total"] == pytest.approx(42.50)


def test_new_expense_updates_profile_stats(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Transport", "2024-01-01")
    login(client, user_id)

    client.post("/expenses/add", data=VALID_PAYLOAD, follow_redirects=False)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    assert context["stats"]["transaction_count"] == 2
    assert context["stats"]["total_spent"] == pytest.approx(52.50)


# --------------------------------------------------------------------- #
# Validation — amount
# --------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["", "0", "-5", "-0.01", "abc", "twenty", "12,50", "NaN", "Infinity"],
)
def test_post_invalid_amount_rerenders_form_with_error_and_no_insert(app, client, bad_amount):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, amount=bad_amount)

    with captured_templates(app) as templates:
        response = client.post("/expenses/add", data=payload)

    assert response.status_code == 200, (
        "Invalid amount should re-render the form, not redirect"
    )
    assert len(templates) == 1
    template, context = templates[0]
    assert template.name == "expenses_add.html"
    assert context.get("error"), "An error message should be present in the context"

    assert fetch_all_expenses(user_id) == [], (
        "No row should be inserted when the amount is invalid"
    )


def test_post_invalid_amount_preserves_submitted_values(app, client):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, amount="not-a-number")

    with captured_templates(app) as templates:
        response = client.post("/expenses/add", data=payload)

    assert response.status_code == 200
    context = templates[0][1]
    # Spec: "re-render the form with an error message and the submitted
    # values preserved" — category, date, description should survive.
    assert context.get("category") == "Food"
    assert context.get("date") == "2024-05-01"
    assert context.get("description") == "Groceries"


# --------------------------------------------------------------------- #
# Validation — category
# --------------------------------------------------------------------- #

def test_post_invalid_category_rerenders_form_with_error_and_no_insert(app, client):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, category="NotARealCategory")

    with captured_templates(app) as templates:
        response = client.post("/expenses/add", data=payload)

    assert response.status_code == 200, (
        "Invalid category should re-render the form, not redirect"
    )
    context = templates[0][1]
    assert context.get("error"), "An error message should be present for invalid category"

    assert fetch_all_expenses(user_id) == [], (
        "No row should be inserted when the category is invalid"
    )


def test_post_empty_category_rerenders_form_with_error_and_no_insert(app, client):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, category="")

    with captured_templates(app) as templates:
        response = client.post("/expenses/add", data=payload)

    assert response.status_code == 200
    context = templates[0][1]
    assert context.get("error")
    assert fetch_all_expenses(user_id) == []


@pytest.mark.parametrize("category", db.CATEGORIES)
def test_post_each_valid_category_is_accepted(app, client, category):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, category=category)
    response = client.post("/expenses/add", data=payload, follow_redirects=False)

    assert response.status_code == 302, f"Category '{category}' should be accepted"
    rows = fetch_all_expenses(user_id)
    assert len(rows) == 1
    assert rows[0]["category"] == category


# --------------------------------------------------------------------- #
# POST with no form body
# --------------------------------------------------------------------- #

def test_post_add_expense_with_no_form_data_returns_400(app, client):
    user_id = create_test_user()
    login(client, user_id)

    response = client.post("/expenses/add", data=None, content_type="multipart/form-data")

    assert response.status_code == 400, (
        "POST with no form data should abort with 400, matching register/login pattern"
    )
    assert fetch_all_expenses(user_id) == []


# --------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------- #

def test_post_missing_description_defaults_and_still_inserts(app, client):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD)
    payload.pop("description")

    response = client.post("/expenses/add", data=payload, follow_redirects=False)

    assert response.status_code == 302, "Description should be optional"
    rows = fetch_all_expenses(user_id)
    assert len(rows) == 1


def test_post_very_long_description_is_accepted(app, client):
    user_id = create_test_user()
    login(client, user_id)

    long_description = "x" * 5000
    payload = dict(VALID_PAYLOAD, description=long_description)

    response = client.post("/expenses/add", data=payload, follow_redirects=False)

    assert response.status_code == 302
    rows = fetch_all_expenses(user_id)
    assert len(rows) == 1
    assert rows[0]["description"] == long_description


def test_post_sql_injection_attempt_in_description_is_stored_safely(app, client):
    user_id = create_test_user()
    login(client, user_id)

    malicious = "'); DROP TABLE expenses; --"
    payload = dict(VALID_PAYLOAD, description=malicious)

    response = client.post("/expenses/add", data=payload, follow_redirects=False)

    assert response.status_code == 302, "Malicious input should be handled safely, not crash"
    rows = fetch_all_expenses(user_id)
    assert len(rows) == 1, "The expenses table must still exist and contain the new row"
    assert rows[0]["description"] == malicious, (
        "The malicious string should be stored verbatim as data, not executed as SQL"
    )


def test_post_amount_with_many_decimal_places_is_accepted(app, client):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, amount="19.999999")
    response = client.post("/expenses/add", data=payload, follow_redirects=False)

    assert response.status_code == 302
    rows = fetch_all_expenses(user_id)
    assert rows[0]["amount"] == pytest.approx(19.999999)


def test_post_whitespace_only_amount_is_rejected(app, client):
    user_id = create_test_user()
    login(client, user_id)

    payload = dict(VALID_PAYLOAD, amount="   ")

    with captured_templates(app) as templates:
        response = client.post("/expenses/add", data=payload)

    assert response.status_code == 200
    context = templates[0][1]
    assert context.get("error")
    assert fetch_all_expenses(user_id) == []


# --------------------------------------------------------------------- #
# DB-layer behavior (direct, framework-independent of the route)
# --------------------------------------------------------------------- #

def test_db_create_expense_inserts_row_with_expected_values(app):
    user_id = create_test_user()

    expense_id = db.create_expense(user_id, 15.75, "Health", "2024-03-02", "Pharmacy")

    assert expense_id is not None
    rows = fetch_all_expenses(user_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == expense_id
    assert row["user_id"] == user_id
    assert row["amount"] == pytest.approx(15.75)
    assert row["category"] == "Health"
    assert row["date"] == "2024-03-02"
    assert row["description"] == "Pharmacy"


def test_db_create_expense_uses_parameterized_sql():
    """Spec: 'Parameterised queries only (`?` placeholders)'."""
    import inspect

    source = inspect.getsource(db.create_expense)
    assert "?" in source, "create_expense must use ? placeholders"
    assert "f\"" not in source and "f'" not in source, (
        "create_expense must not build SQL with f-strings"
    )
    assert ".format(" not in source, (
        "create_expense must not build SQL with str.format()"
    )
