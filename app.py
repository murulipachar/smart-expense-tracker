from flask import Flask, render_template, request, redirect, url_for, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"

DB_CONFIG = {
    "host": "localhost",
    "user": "murulihp",
    "password": "4709",
    "database": "expense_tracker"
}


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")
        confirm = request.form.get("confirm")

        if password != confirm:
            error = "Passwords do not match"
        else:
            hashed = generate_password_hash(password)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                    (name, email, hashed),
                )
                conn.commit()
                cursor.close()
                conn.close()
                return redirect(url_for("login"))
            except mysql.connector.IntegrityError:
                error = "Email already registered"

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    # Filters from query params
    category_filter = request.args.get("category", "all")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Add new expense (POST)
    if request.method == "POST":
        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get("description")
        date = request.form.get("date") or datetime.today().strftime("%Y-%m-%d")

        cursor.execute(
            "INSERT INTO expenses (user_id, category, amount, description, date) VALUES (%s, %s, %s, %s, %s)",
            (user_id, category, amount, description, date),
        )
        conn.commit()
        return redirect(url_for("dashboard"))

    # Build query with filters
    query = "SELECT * FROM expenses WHERE user_id = %s"
    params = [user_id]

    if category_filter != "all":
        query += " AND category = %s"
        params.append(category_filter)

    if start_date:
        query += " AND date >= %s"
        params.append(start_date)
    if end_date:
        query += " AND date <= %s"
        params.append(end_date)

    query += " ORDER BY date DESC"

    cursor.execute(query, tuple(params))
    expenses = cursor.fetchall()

    # Category list for filter dropdown
    cursor.execute(
        "SELECT DISTINCT category FROM expenses WHERE user_id = %s", (user_id,)
    )
    categories = [row["category"] for row in cursor.fetchall()]

    # Total amount
    total_amount = sum(float(exp["amount"]) for exp in expenses) if expenses else 0

    # Chart data: sum by category (for current user)
    cursor.execute(
        "SELECT category, SUM(amount) AS total FROM expenses WHERE user_id = %s GROUP BY category",
        (user_id,),
    )
    chart_rows = cursor.fetchall()
    cursor.close()
    conn.close()

    chart_labels = [row["category"] for row in chart_rows]
    chart_values = [float(row["total"]) for row in chart_rows]

    return render_template(
        "dashboard.html",
        expenses=expenses,
        categories=categories,
        category_filter=category_filter,
        start_date=start_date or "",
        end_date=end_date or "",
        total_amount=total_amount,
        chart_labels=chart_labels,
        chart_values=chart_values,
        user_name=session.get("user_name"),
    )


@app.route("/expense/edit/<int:expense_id>", methods=["POST"])
def edit_expense(expense_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    amount = request.form.get("amount")
    category = request.form.get("category")
    description = request.form.get("description")
    date = request.form.get("date")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE expenses SET amount=%s, category=%s, description=%s, date=%s "
        "WHERE id=%s AND user_id=%s",
        (amount, category, description, date, expense_id, session["user_id"]),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/expense/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM expenses WHERE id=%s AND user_id=%s",
        (expense_id, session["user_id"]),
    )
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for("dashboard"))


@app.route("/export")
def export_csv():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT date, category, amount, description "
        "FROM expenses WHERE user_id = %s ORDER BY date DESC",
        (session["user_id"],),
    )
    expenses = cursor.fetchall()
    cursor.close()
    conn.close()

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(["Date", "Category", "Amount", "Description"])
    for exp in expenses:
        cw.writerow(
            [
                exp["date"].strftime("%Y-%m-%d"),
                exp["category"],
                str(exp["amount"]),
                exp["description"],
            ]
        )

    output = si.getvalue()
    headers = {
        "Content-Disposition": "attachment; filename=expenses.csv",
        "Content-type": "text/csv",
    }
    return Response(output, headers=headers)


if __name__ == "__main__":
    app.run(debug=True)
