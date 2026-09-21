import calendar
import math
from datetime import date, datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_by_id,
    get_recent_transactions,
    get_user_by_email,
    get_user_by_id,
    get_user_stats,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
# Hardcoded for this learning project — a real deployment should load this
# from an environment variable instead.
app.secret_key = "spendly-dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


def _parse_date_arg(value):
    value = value.strip()
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    return value


def _shift_months(base_date, months):
    # Zero-index the month, subtract, then re-derive year/month from the
    # result so it rolls over correctly across year boundaries; the day is
    # clamped to the target month's length (e.g. Aug 31 - 6 months -> Feb 28/29).
    month_index = base_date.month - 1 - months
    year = base_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _date_presets():
    today = date.today()
    return {
        "this_month": {
            "label": "This Month",
            "start": today.replace(day=1).isoformat(),
            "end": today.isoformat(),
        },
        "last_3_months": {
            "label": "Last 3 Months",
            "start": _shift_months(today, 3).isoformat(),
            "end": today.isoformat(),
        },
        "last_6_months": {
            "label": "Last 6 Months",
            "start": _shift_months(today, 6).isoformat(),
            "end": today.isoformat(),
        },
    }


def _active_preset(start_date, end_date, presets):
    if not start_date and not end_date:
        return "all"
    for key, preset in presets.items():
        if start_date == preset["start"] and end_date == preset["end"]:
            return key
    return None


def _resolve_date_range(args):
    start_date = _parse_date_arg(args.get("start_date", ""))
    end_date = _parse_date_arg(args.get("end_date", ""))
    if start_date and end_date and start_date > end_date:
        start_date = None
        end_date = None
    return start_date, end_date


def _parse_expense_form(form):
    amount_raw = form.get("amount", "").strip()
    category = form.get("category", "").strip()
    expense_date = form.get("date", "").strip()
    description = form.get("description", "").strip()

    error = None
    amount = None
    try:
        amount = float(amount_raw)
        if not math.isfinite(amount) or amount <= 0:
            error = "Amount must be a positive number."
    except ValueError:
        error = "Please enter a valid amount."

    if not error and category not in CATEGORIES:
        error = "Please choose a valid category."

    if not error and not expense_date:
        expense_date = date.today().isoformat()

    return amount_raw, amount, category, expense_date, description, error


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method != "POST":
        return render_template("register.html")

    if not request.form:
        abort(400)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    error = None
    if not name:
        error = "Full name is required."
    elif not email or "@" not in email or "." not in email.split("@")[-1]:
        error = "Please enter a valid email address."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif get_user_by_email(email) is not None:
        error = "An account with that email already exists."

    if error:
        return render_template("register.html", error=error)

    password_hash = generate_password_hash(password)
    user_id = create_user(name, email, password_hash)
    session["user_id"] = user_id
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method != "POST":
        return render_template("login.html")

    if not request.form:
        abort(400)

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    error = "Invalid email or password."
    user = get_user_by_email(email)
    if user is not None and check_password_hash(user["password_hash"], password):
        error = None

    if error:
        return render_template("login.html", error=error)

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/seed-user")
def seed_user():
    seed_db()
    return "Demo user seeded — email: demo@spendly.com, password: demo123"


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.pop("user_id", None)
        session.pop("user_name", None)
        return redirect(url_for("login"))

    name_parts = user_row["name"].split()
    initials = "".join(part[0].upper() for part in name_parts[:2]) or "?"

    created_at = datetime.strptime(user_row["created_at"], "%Y-%m-%d %H:%M:%S")
    member_since = created_at.strftime("%B %Y")

    user = {
        "name": user_row["name"],
        "email": user_row["email"],
        "member_since": member_since,
        "initials": initials,
    }

    start_date, end_date = _resolve_date_range(request.args)

    presets = _date_presets()
    active_preset = _active_preset(start_date, end_date, presets)

    stats = get_user_stats(user_id, start_date=start_date, end_date=end_date)
    if stats["top_category"] is None:
        stats["top_category"] = "—"

    transactions = get_recent_transactions(
        user_id, limit=10, start_date=start_date, end_date=end_date
    )
    categories = get_category_breakdown(
        user_id, start_date=start_date, end_date=end_date
    )

    return render_template(
        "profile.html",
        user=user,
        transactions=transactions,
        categories=categories,
        stats=stats,
        start_date=start_date or "",
        end_date=end_date or "",
        presets=presets,
        active_preset=active_preset,
    )


@app.route("/analytics")
def analytics():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if request.method != "POST":
        return render_template(
            "expenses_add.html",
            categories=CATEGORIES,
            today=date.today().isoformat(),
        )

    if not request.form:
        abort(400)

    amount_raw, amount, category, expense_date, description, error = _parse_expense_form(
        request.form
    )

    if error:
        return render_template(
            "expenses_add.html",
            categories=CATEGORIES,
            today=date.today().isoformat(),
            error=error,
            amount=amount_raw,
            category=category,
            date=expense_date,
            description=description,
        )

    create_expense(user_id, amount, category, expense_date, description or None)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    expense = get_expense_by_id(expense_id, user_id)
    if expense is None:
        abort(404)

    if request.method != "POST":
        return render_template(
            "expenses_edit.html",
            categories=CATEGORIES,
            expense_id=expense_id,
            amount=expense["amount"],
            category=expense["category"],
            date=expense["date"],
            description=expense["description"],
        )

    if not request.form:
        abort(400)

    amount_raw, amount, category, expense_date, description, error = _parse_expense_form(
        request.form
    )

    if error:
        return render_template(
            "expenses_edit.html",
            categories=CATEGORIES,
            expense_id=expense_id,
            error=error,
            amount=amount_raw,
            category=category,
            date=expense_date,
            description=description,
        )

    update_expense(expense_id, amount, category, expense_date, description or None)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
