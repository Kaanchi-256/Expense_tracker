from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
# Hardcoded for this learning project — a real deployment should load this
# from an environment variable instead.
app.secret_key = "spendly-dev-secret-key"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
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
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
