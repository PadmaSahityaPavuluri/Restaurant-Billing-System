from flask import Flask, render_template, request, redirect, url_for, session
from flask_bcrypt import Bcrypt
import sqlite3, datetime

app = Flask(__name__)
app.secret_key = "supersecretkey"
bcrypt = Bcrypt(app)

# -------------------------------
# Menu
# -------------------------------
menu = {
    'Idly': 20,
    'Dosa': 40,
    'Chapathi': 30,
    'Puri': 35,
    'Roti': 50,
    'Biryani': 200,
    'Fried Rice': 150,
    'Paneer Curry': 120,
    'Gulab Jamun': 60,
    'Ice Cream': 80
}

GST_RATE = 0.05
COUPONS = {"SAVE10": 0.10, "SAVE20": 0.20}

# -------------------------------
# Users with bcrypt-hashed passwords
# -------------------------------
users = {
    "admin": {
        "password": bcrypt.generate_password_hash("admin123").decode("utf-8"),
        "role": "admin"
    },
    "cashier": {
        "password": bcrypt.generate_password_hash("cashier123").decode("utf-8"),
        "role": "cashier"
    }
}

# -------------------------------
# Database Setup
# -------------------------------
def init_db():
    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item TEXT,
            qty INTEGER,
            cost REAL,
            subtotal REAL,
            gst REAL,
            discount REAL,
            final_total REAL,
            date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# -------------------------------
# Routes
# -------------------------------
@app.route("/")
def home():
    return render_template("menu.html", menu=menu, session=session)

@app.route("/bill", methods=["POST"])
def bill():
    order_details = {}
    subtotal = 0

    for item in menu.keys():
        qty_str = request.form.get(item)
        if qty_str and qty_str.isdigit():
            qty = int(qty_str)
            if qty > 0:
                cost = menu[item] * qty
                subtotal += cost
                order_details[item] = {"qty": qty, "cost": cost}

    if not order_details:
        return "❌ No items selected. <a href='/'>Go back</a>"

    gst = subtotal * GST_RATE
    total_with_gst = subtotal + gst

    coupon = request.form.get("coupon", "").strip().upper()
    discount = COUPONS.get(coupon, 0) * total_with_gst if coupon in COUPONS else 0
    final_total = total_with_gst - discount

    conn = sqlite3.connect("restaurant.db")
    cur = conn.cursor()
    for item, details in order_details.items():
        cur.execute(
            "INSERT INTO orders (item, qty, cost, subtotal, gst, discount, final_total, date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (item, details['qty'], details['cost'], subtotal, gst, discount, final_total,
             datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    conn.commit()
    conn.close()

    return render_template("bill.html", order=order_details, subtotal=subtotal,
                           gst=gst, discount=discount, final_total=final_total, coupon=coupon)

# -------------------------------
# Login
# -------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username in users and bcrypt.check_password_hash(users[username]["password"], password):
            session["user"] = username
            session["role"] = users[username]["role"]
            return redirect(url_for("home"))
        else:
            return "❌ Invalid login. <a href='/login'>Try again</a>"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# -------------------------------
# Sales Report (Admin Only)
# -------------------------------
@app.route("/report", methods=["GET", "POST"])
def report():
    if "user" not in session or session.get("role") != "admin":
        return "❌ Access Denied! Admins only. <a href='/login'>Login</a>"

    report_data = None
    date_input = None

    if request.method == "POST":
        date_input = request.form.get("date")
        if not date_input:
            date_input = datetime.datetime.now().strftime("%Y-%m-%d")

        try:
            datetime.datetime.strptime(date_input, "%Y-%m-%d")
        except ValueError:
            return "❌ Invalid date! Use format YYYY-MM-DD. <a href='/report'>Try again</a>"

        conn = sqlite3.connect("restaurant.db")
        cur = conn.cursor()

        start = f"{date_input} 00:00:00"
        end = f"{date_input} 23:59:59"

        cur.execute(
            "SELECT SUM(final_total), COUNT(DISTINCT date) FROM orders WHERE date BETWEEN ? AND ?",
            (start, end)
        )
        row = cur.fetchone()

        total_revenue = float(row[0]) if row and row[0] is not None else 0.0
        orders_count = int(row[1]) if row and row[1] is not None else 0

        cur.execute("""
            SELECT item, SUM(qty) as total_qty 
            FROM orders 
            WHERE date BETWEEN ? AND ? 
            GROUP BY item
            ORDER BY total_qty DESC
        """, (start, end))
        items = cur.fetchall() or []
        conn.close()

        report_data = {
            "date": date_input,
            "orders_count": orders_count,
            "total_revenue": total_revenue,
            "items": items,
            "top_seller": items[0] if items else None
        }

    return render_template("report.html", report=report_data, user=session.get("user"))
# -------------------------------
# Run
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)
