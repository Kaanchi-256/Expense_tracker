"""
Tests for Step 06 — Date filter for the profile page.

Spec: .claude/specs/06-date-filter-profile-page.md

These tests exercise the /profile route's optional start_date/end_date query
parameters, the server-computed preset ranges (All Time, This Month,
Last 3 Months, Last 6 Months) and active-preset detection, and the
date-filtered database helpers in database/db.py. Test logic is derived from
the spec's stated behavior, not from reading the route/helper implementations
(those were only read to learn route names, session keys, function
signatures, and context-variable names needed to wire the tests up).
"""
import calendar
from contextlib import contextmanager
from datetime import date

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


def months_before(base_date, months):
    """Independent calendar-month-subtraction helper for computing expected
    preset ranges, per spec: 'a rolling window from N calendar months before
    today through today'."""
    month_index = base_date.month - 1 - months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# --------------------------------------------------------------------- #
# Auth guard
# --------------------------------------------------------------------- #

def test_profile_without_session_redirects_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302, "Unauthenticated /profile should redirect"
    assert "/login" in response.headers["Location"], (
        "Unauthenticated /profile should redirect to the login page"
    )


# --------------------------------------------------------------------- #
# No query params -> all-time data, All Time pill active (no regression)
# --------------------------------------------------------------------- #

def test_profile_no_params_shows_all_time_data_and_active_preset(app, client):
    user_id = create_test_user()
    today = date.today()
    insert_expense(user_id, 10.00, "Food", today.isoformat())
    insert_expense(user_id, 20.00, "Transport", months_before(today, 2).isoformat())
    insert_expense(user_id, 30.00, "Bills", months_before(today, 8).isoformat())
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    assert len(templates) == 1
    context = templates[0][1]

    assert len(context["transactions"]) == 3, "All-time view should include every expense"
    assert context["stats"]["transaction_count"] == 3
    assert context["stats"]["total_spent"] == pytest.approx(60.00)
    assert context["active_preset"] == "all", "No query params should mark All Time as active"
    assert context["start_date"] == ""
    assert context["end_date"] == ""


# --------------------------------------------------------------------- #
# Preset pills
# --------------------------------------------------------------------- #

def test_this_month_preset_filters_correctly_and_marks_active(app, client):
    user_id = create_test_user()
    today = date.today()
    in_range_1 = today
    in_range_2 = today.replace(day=1)
    out_of_range = months_before(today, 2)

    insert_expense(user_id, 10.00, "Food", in_range_1.isoformat())
    insert_expense(user_id, 20.00, "Transport", in_range_2.isoformat())
    insert_expense(user_id, 999.00, "Bills", out_of_range.isoformat())
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(
            "/profile",
            query_string={
                "start_date": today.replace(day=1).isoformat(),
                "end_date": today.isoformat(),
            },
        )

    assert response.status_code == 200
    context = templates[0][1]

    assert context["active_preset"] == "this_month"
    assert len(context["transactions"]) == 2
    assert context["stats"]["transaction_count"] == 2
    assert context["stats"]["total_spent"] == pytest.approx(30.00)
    returned_dates = {row["date"] for row in context["transactions"]}
    assert out_of_range.isoformat() not in returned_dates


def test_last_3_months_preset_filters_correctly_and_marks_active(app, client):
    user_id = create_test_user()
    today = date.today()

    insert_expense(user_id, 10.00, "Food", today.isoformat())
    insert_expense(user_id, 20.00, "Transport", months_before(today, 2).isoformat())
    insert_expense(user_id, 999.00, "Bills", months_before(today, 4).isoformat())
    login(client, user_id)

    start = months_before(today, 3).isoformat()
    end = today.isoformat()

    with captured_templates(app) as templates:
        response = client.get(
            "/profile", query_string={"start_date": start, "end_date": end}
        )

    assert response.status_code == 200
    context = templates[0][1]

    assert context["active_preset"] == "last_3_months"
    assert context["stats"]["transaction_count"] == 2
    assert context["stats"]["total_spent"] == pytest.approx(30.00)


def test_last_6_months_preset_filters_correctly_and_marks_active(app, client):
    user_id = create_test_user()
    today = date.today()

    insert_expense(user_id, 10.00, "Food", today.isoformat())
    insert_expense(user_id, 20.00, "Transport", months_before(today, 4).isoformat())
    insert_expense(user_id, 999.00, "Bills", months_before(today, 7).isoformat())
    login(client, user_id)

    start = months_before(today, 6).isoformat()
    end = today.isoformat()

    with captured_templates(app) as templates:
        response = client.get(
            "/profile", query_string={"start_date": start, "end_date": end}
        )

    assert response.status_code == 200
    context = templates[0][1]

    assert context["active_preset"] == "last_6_months"
    assert context["stats"]["transaction_count"] == 2
    assert context["stats"]["total_spent"] == pytest.approx(30.00)


def test_clicking_all_time_after_filtering_restores_full_data(app, client):
    user_id = create_test_user()
    today = date.today()
    insert_expense(user_id, 10.00, "Food", today.isoformat())
    insert_expense(user_id, 999.00, "Bills", months_before(today, 8).isoformat())
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/profile")

    assert response.status_code == 200
    context = templates[0][1]
    assert context["active_preset"] == "all"
    assert context["stats"]["transaction_count"] == 2
    assert context["stats"]["total_spent"] == pytest.approx(1009.00)


# --------------------------------------------------------------------- #
# Custom date range
# --------------------------------------------------------------------- #

def test_custom_range_filters_transactions_categories_and_stats(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 100.00, "Food", "2020-01-05", "January groceries")
    insert_expense(user_id, 50.00, "Food", "2020-01-20", "More groceries")
    insert_expense(user_id, 200.00, "Bills", "2020-02-10", "February bill")
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(
            "/profile",
            query_string={"start_date": "2020-01-01", "end_date": "2020-01-31"},
        )

    assert response.status_code == 200
    context = templates[0][1]

    assert len(context["transactions"]) == 2, "Only January expenses should be returned"
    dates = {row["date"] for row in context["transactions"]}
    assert dates == {"2020-01-05", "2020-01-20"}

    assert context["stats"]["transaction_count"] == 2
    assert context["stats"]["total_spent"] == pytest.approx(150.00)

    category_names = {c["name"] for c in context["categories"]}
    assert category_names == {"Food"}, "February 'Bills' expense must be excluded"

    assert context["start_date"] == "2020-01-01"
    assert context["end_date"] == "2020-01-31"


def test_custom_range_only_start_date_is_open_ended(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Food", "2020-06-15")
    insert_expense(user_id, 30.00, "Food", "2020-12-31")
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/profile", query_string={"start_date": "2020-06-01"})

    assert response.status_code == 200
    context = templates[0][1]
    dates = {row["date"] for row in context["transactions"]}
    assert dates == {"2020-06-15", "2020-12-31"}, (
        "Only start_date supplied should include that date onward"
    )
    assert context["stats"]["total_spent"] == pytest.approx(50.00)


def test_custom_range_only_end_date_is_open_ended(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Food", "2020-06-15")
    insert_expense(user_id, 30.00, "Food", "2020-12-31")
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get("/profile", query_string={"end_date": "2020-06-30"})

    assert response.status_code == 200
    context = templates[0][1]
    dates = {row["date"] for row in context["transactions"]}
    assert dates == {"2020-01-01", "2020-06-15"}, (
        "Only end_date supplied should include everything up to that date"
    )
    assert context["stats"]["total_spent"] == pytest.approx(30.00)


def test_start_date_after_end_date_falls_back_to_unfiltered(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Food", "2020-06-15")
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(
            "/profile",
            query_string={"start_date": "2020-12-01", "end_date": "2020-01-01"},
        )

    assert response.status_code == 200, "Reversed range must not raise a 500"
    context = templates[0][1]
    assert len(context["transactions"]) == 2, "Invalid range should fall back to unfiltered data"
    assert context["stats"]["total_spent"] == pytest.approx(30.00)


@pytest.mark.parametrize(
    "bad_start,bad_end",
    [
        ("not-a-date", ""),
        ("", "not-a-date"),
        ("2026-13-40", ""),
        ("2026/09/18", ""),
        ("18-09-2026", "2026-09-18"),
    ],
)
def test_malformed_date_params_fall_back_to_unfiltered(app, client, bad_start, bad_end):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Food", "2020-06-15")
    login(client, user_id)

    query_string = {}
    if bad_start:
        query_string["start_date"] = bad_start
    if bad_end:
        query_string["end_date"] = bad_end

    with captured_templates(app) as templates:
        response = client.get("/profile", query_string=query_string)

    assert response.status_code == 200, "Malformed date params must not cause a 500"
    context = templates[0][1]
    assert len(context["transactions"]) == 2, "Malformed dates should fall back to unfiltered data"


def test_custom_range_matching_preset_marks_that_preset_active(app, client):
    user_id = create_test_user()
    today = date.today()
    insert_expense(user_id, 10.00, "Food", today.isoformat())
    login(client, user_id)

    start = today.replace(day=1).isoformat()
    end = today.isoformat()

    with captured_templates(app) as templates:
        response = client.get(
            "/profile", query_string={"start_date": start, "end_date": end}
        )

    assert response.status_code == 200
    context = templates[0][1]
    assert context["active_preset"] == "this_month", (
        "A custom range identical to a preset's computed range must be marked active"
    )


def test_custom_range_not_matching_any_preset_marks_none_active(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-03-01")
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(
            "/profile",
            query_string={"start_date": "2020-03-01", "end_date": "2020-03-10"},
        )

    assert response.status_code == 200
    context = templates[0][1]
    assert not context["active_preset"], (
        "A custom range matching no preset must not mark any preset as active"
    )


# --------------------------------------------------------------------- #
# Empty-state behavior
# --------------------------------------------------------------------- #

def test_zero_matching_transactions_shows_empty_state(app, client):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    login(client, user_id)

    with captured_templates(app) as templates:
        response = client.get(
            "/profile",
            query_string={"start_date": "2099-01-01", "end_date": "2099-01-31"},
        )

    assert response.status_code == 200
    context = templates[0][1]

    assert context["transactions"] == [], "No expenses fall inside a future-only range"
    assert context["categories"] == [], "Category breakdown should also be empty"
    assert context["stats"]["transaction_count"] == 0
    assert context["stats"]["total_spent"] in (0, 0.0)

    assert b"No transactions in this range" in response.data, (
        "Spec requires an explicit empty-state message when the filtered range "
        "has no matching transactions"
    )


# --------------------------------------------------------------------- #
# DB-layer behavior (direct, framework-independent of the route)
# --------------------------------------------------------------------- #

def test_db_get_recent_transactions_filters_by_date_range(app):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Food", "2020-06-15")
    insert_expense(user_id, 30.00, "Food", "2020-12-31")

    rows = db.get_recent_transactions(
        user_id, limit=10, start_date="2020-01-01", end_date="2020-06-30"
    )
    dates = {row["date"] for row in rows}
    assert dates == {"2020-01-01", "2020-06-15"}


def test_db_get_user_stats_filters_by_date_range(app):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Food", "2020-06-15")
    insert_expense(user_id, 30.00, "Food", "2020-12-31")

    stats = db.get_user_stats(user_id, start_date="2020-01-01", end_date="2020-06-30")
    assert stats["transaction_count"] == 2
    assert stats["total_spent"] == pytest.approx(30.00)


def test_db_get_category_breakdown_filters_by_date_range(app):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Bills", "2020-06-15")
    insert_expense(user_id, 30.00, "Shopping", "2020-12-31")

    categories = db.get_category_breakdown(
        user_id, start_date="2020-01-01", end_date="2020-06-30"
    )
    names = {c["name"] for c in categories}
    assert names == {"Food", "Bills"}
    assert "Shopping" not in names


def test_db_helpers_still_default_to_all_time_when_no_dates_given(app):
    user_id = create_test_user()
    insert_expense(user_id, 10.00, "Food", "2020-01-01")
    insert_expense(user_id, 20.00, "Bills", "2020-12-31")

    rows = db.get_recent_transactions(user_id, limit=10)
    assert len(rows) == 2

    stats = db.get_user_stats(user_id)
    assert stats["transaction_count"] == 2

    categories = db.get_category_breakdown(user_id)
    assert len(categories) == 2


# --------------------------------------------------------------------- #
# Static check: parameterized SQL only, per spec's standing rule
# --------------------------------------------------------------------- #

def test_date_filter_sql_uses_parameterized_placeholders():
    """Spec: 'All SQL queries touching the date filter use ? placeholders,
    verified by reading database/db.py.'"""
    import inspect

    source = inspect.getsource(db)

    # The date-filter clause builder must only ever emit '?' placeholders,
    # never the literal date value spliced into the SQL text.
    clause_source = inspect.getsource(db._date_filter_clause)
    assert "?" in clause_source
    assert "{start_date}" not in clause_source
    assert "{end_date}" not in clause_source
    assert "%s" not in clause_source, "No old-style string formatting in SQL"

    # No f-string / .format() / % interpolation of start_date or end_date
    # directly into any SQL text anywhere in the module.
    assert "{start_date}" not in source
    assert "{end_date}" not in source

    # Every function that filters by date must forward params through
    # conn.execute(query, params) rather than baking values into the query.
    for func in (
        db.get_recent_transactions,
        db.get_user_stats,
        db.get_category_breakdown,
    ):
        func_source = inspect.getsource(func)
        assert "date_params" in func_source, (
            f"{func.__name__} should thread the parameterized date args through "
            "to conn.execute rather than inlining them into the SQL string"
        )
