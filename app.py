from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
import os
import csv
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "atm_secret_key"
app.permanent_session_lifetime = timedelta(minutes=10)

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "database.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Email config (GitHub par real password na mukhvo)
SENDER_EMAIL = os.getenv("ATM_EMAIL")
SENDER_PASSWORD = os.getenv("ATM_EMAIL_PASSWORD")

# =========================
# DATABASE SETUP
# =========================
def create_database():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card TEXT UNIQUE,
        pin TEXT,
        name TEXT,
        email TEXT,
        balance REAL DEFAULT 0,
        failed_attempts INTEGER DEFAULT 0,
        is_locked INTEGER DEFAULT 0,
        security_question TEXT,
        security_answer TEXT,
        last_login TEXT,
        login_ip TEXT,
        profile_pic TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card TEXT,
        type TEXT,
        amount REAL,
        date TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS fixed_deposits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card TEXT,
        amount REAL,
        months INTEGER,
        interest_rate REAL,
        created_at TEXT
    )
    """)

    # Demo user
    c.execute("SELECT * FROM users WHERE card=?", ("246450307052",))
    user = c.fetchone()

    if user is None:
        demo_pin = generate_password_hash("#Rm_54321")
        c.execute("""
        INSERT INTO users(card, pin, name, email, balance, security_question, security_answer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            "246450307052",
            demo_pin,
            "Jal Modi",
            "jal@example.com",
            10000,
            "What is your favorite color?",
            "blue"
        ))

    conn.commit()
    conn.close()

create_database()

# =========================
# SESSION
# =========================
@app.before_request
def make_session_permanent():
    session.permanent = True

# =========================
# HELPERS
# =========================
def get_conn():
    return sqlite3.connect(DATABASE)

def get_current_datetime():
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

def login_required():
    return "card" in session

def send_email_receipt(to_email, subject, message):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("Email skipped: ATM_EMAIL / ATM_EMAIL_PASSWORD not set")
        return

    try:
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email sending failed:", e)

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        card = request.form.get("card", "").strip()
        pin = request.form.get("pin", "").strip()

        if not card or not pin:
            return "Card number and PIN are required"

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE card=?", (card,))
        user = c.fetchone()

        if not user:
            conn.close()
            return "Card Number Not Found"

        user_id = user[0]
        db_pin = user[2]
        failed_attempts = user[6]
        is_locked = user[7]

        if is_locked == 1:
            conn.close()
            return "Your account is locked due to 3 wrong login attempts."

        if check_password_hash(db_pin, pin):
            last_login = get_current_datetime()
            login_ip = request.remote_addr

            c.execute("""
                UPDATE users
                SET failed_attempts=0, last_login=?, login_ip=?
                WHERE id=?
            """, (last_login, login_ip, user_id))

            conn.commit()
            conn.close()

            session["card"] = card
            return redirect("/dashboard")
        else:
            failed_attempts += 1

            if failed_attempts >= 3:
                c.execute("""
                    UPDATE users
                    SET failed_attempts=?, is_locked=1
                    WHERE id=?
                """, (failed_attempts, user_id))
                conn.commit()
                conn.close()
                return "Account locked! You entered wrong PIN 3 times."
            else:
                c.execute("""
                    UPDATE users
                    SET failed_attempts=?
                    WHERE id=?
                """, (failed_attempts, user_id))
                conn.commit()
                conn.close()
                return f"Wrong PIN! Attempt {failed_attempts}/3"

    return render_template("login.html")

# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        card = request.form.get("card", "").strip()
        pin = request.form.get("pin", "").strip()
        security_question = request.form.get("security_question", "").strip()
        security_answer = request.form.get("security_answer", "").strip()

        if not all([name, email, card, pin, security_question, security_answer]):
            return "All fields are required"

        if len(pin) < 4:
            return "PIN must be at least 4 characters"

        hashed_pin = generate_password_hash(pin)

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE card=?", (card,))
        user = c.fetchone()

        if user:
            conn.close()
            return "Card Number Already Exists"

        c.execute("""
        INSERT INTO users(card, pin, name, email, balance, security_question, security_answer)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (card, hashed_pin, name, email, 0, security_question, security_answer))

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("register.html")

# =========================
# FORGOT PIN
# =========================
@app.route("/forgot_pin", methods=["GET", "POST"])
def forgot_pin():
    if request.method == "POST":
        card = request.form.get("card", "").strip()
        security_question = request.form.get("security_question", "").strip()
        security_answer = request.form.get("security_answer", "").strip()
        new_pin = request.form.get("new_pin", "").strip()

        if not all([card, security_question, security_answer, new_pin]):
            return "All fields are required"

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT * FROM users
            WHERE card=? AND security_question=? AND security_answer=?
        """, (card, security_question, security_answer))

        user = c.fetchone()

        if user:
            hashed_new_pin = generate_password_hash(new_pin)
            c.execute("UPDATE users SET pin=? WHERE card=?", (hashed_new_pin, card))
            conn.commit()
            conn.close()
            return "PIN reset successful! Now login with new PIN."

        conn.close()
        return "Invalid card number or security answer"

    return render_template("forgot_pin.html")

# =========================
# DASHBOARD
# =========================
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT name, card, balance, last_login, login_ip
        FROM users
        WHERE card=?
    """, (session["card"],))
    user = c.fetchone()
    conn.close()

    if not user:
        return redirect("/logout")

    return render_template(
        "dashboard.html",
        name=user[0],
        card=user[1],
        balance=user[2],
        last_login=user[3],
        login_ip=user[4]
    )

# =========================
# BALANCE
# =========================
@app.route("/balance")
def balance():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
    row = c.fetchone()
    conn.close()

    if not row:
        return redirect("/logout")

    return render_template("balance.html", balance=row[0])

# =========================
# DEPOSIT
# =========================
@app.route("/deposit", methods=["GET", "POST"])
def deposit():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            return "Invalid amount"

        if amount <= 0:
            return "Amount must be greater than 0"

        conn = get_conn()
        c = conn.cursor()

        c.execute("UPDATE users SET balance = balance + ? WHERE card=?", (amount, session["card"]))

        c.execute("""
            INSERT INTO transactions(card, type, amount, date)
            VALUES (?, ?, ?, ?)
        """, (session["card"], "Deposit", amount, get_current_datetime()))

        conn.commit()

        c.execute("SELECT email FROM users WHERE card=?", (session["card"],))
        row = c.fetchone()
        user_email = row[0] if row else None
        conn.close()

        if user_email:
            send_email_receipt(
                user_email,
                "ATM Deposit Receipt",
                f"Dear User,\n\nYour deposit of ₹{amount} was successful.\n\nThank you for using ATM Management System."
            )

        return redirect("/dashboard")

    return render_template("deposit.html")

# =========================
# WITHDRAW
# =========================
@app.route("/withdraw", methods=["GET", "POST"])
def withdraw():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            return "Invalid amount"

        if amount <= 0:
            return "Amount must be greater than 0"

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT balance, email FROM users WHERE card=?", (session["card"],))
        row = c.fetchone()

        if not row:
            conn.close()
            return "User not found"

        balance = row[0]
        user_email = row[1]

        if balance < amount:
            conn.close()
            return "Insufficient Balance"

        c.execute("UPDATE users SET balance = balance - ? WHERE card=?", (amount, session["card"]))

        c.execute("""
            INSERT INTO transactions(card, type, amount, date)
            VALUES (?, ?, ?, ?)
        """, (session["card"], "Withdraw", amount, get_current_datetime()))

        conn.commit()
        conn.close()

        if user_email:
            send_email_receipt(
                user_email,
                "ATM Withdrawal Receipt",
                f"Dear User,\n\nYour withdrawal of ₹{amount} was successful.\n\nThank you for using ATM Management System."
            )

        return redirect("/dashboard")

    return render_template("withdraw.html")

# =========================
# FAST CASH
# =========================
@app.route("/fast_cash", methods=["GET", "POST"])
def fast_cash():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            return "Invalid amount"

        if amount <= 0:
            return "Amount must be greater than 0"

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
        row = c.fetchone()

        if not row:
            conn.close()
            return "User not found"

        balance = row[0]

        if balance < amount:
            conn.close()
            return "Insufficient Balance"

        c.execute("UPDATE users SET balance=? WHERE card=?", (balance - amount, session["card"]))

        c.execute("""
            INSERT INTO transactions(card, type, amount, date)
            VALUES (?, ?, ?, ?)
        """, (session["card"], "Fast Cash Withdraw", amount, get_current_datetime()))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("fast_cash.html")

# =========================
# TRANSFER
# =========================
@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        receiver = request.form.get("receiver", "").strip()

        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            return "Invalid amount"

        if not receiver:
            return "Receiver card number is required"

        if amount <= 0:
            return "Amount must be greater than 0"

        if receiver == session["card"]:
            return "You cannot transfer money to your own account"

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT balance, email FROM users WHERE card=?", (session["card"],))
        sender = c.fetchone()

        if sender is None:
            conn.close()
            return "Sender not found"

        sender_balance = sender[0]
        sender_email = sender[1]

        c.execute("SELECT email FROM users WHERE card=?", (receiver,))
        receiver_data = c.fetchone()

        if receiver_data is None:
            conn.close()
            return "Receiver Card Number Not Found"

        if sender_balance < amount:
            conn.close()
            return "Insufficient Balance"

        c.execute("UPDATE users SET balance = balance - ? WHERE card=?", (amount, session["card"]))
        c.execute("UPDATE users SET balance = balance + ? WHERE card=?", (amount, receiver))

        tx_time = get_current_datetime()

        c.execute("""
            INSERT INTO transactions(card, type, amount, date)
            VALUES (?, ?, ?, ?)
        """, (session["card"], "Money Transfer Sent", amount, tx_time))

        c.execute("""
            INSERT INTO transactions(card, type, amount, date)
            VALUES (?, ?, ?, ?)
        """, (receiver, "Money Transfer Received", amount, tx_time))

        conn.commit()
        conn.close()

        if sender_email:
            send_email_receipt(
                sender_email,
                "ATM Transfer Receipt",
                f"Dear User,\n\n₹{amount} has been transferred successfully to card number {receiver}.\n\nThank you for using ATM Management System."
            )

        return redirect("/dashboard")

    return render_template("transfer.html")

# =========================
# HISTORY
# =========================
@app.route("/history")
def history():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
    """, (session["card"],))

    data = c.fetchall()
    conn.close()

    return render_template("history.html", data=data)

# =========================
# MINI STATEMENT
# =========================
@app.route("/mini_statement")
def mini_statement():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
        LIMIT 5
    """, (session["card"],))

    data = c.fetchall()
    conn.close()

    return render_template("mini_statement.html", data=data)

# =========================
# RECEIPT
# =========================
@app.route("/receipt")
def receipt():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
        LIMIT 1
    """, (session["card"],))

    transaction = c.fetchone()
    conn.close()

    if transaction is None:
        return "No transaction found"

    return render_template("receipt.html", card=session["card"], transaction=transaction)

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# FIXED DEPOSIT
# =========================
@app.route("/fixed_deposit", methods=["GET", "POST"])
def fixed_deposit():
    if not login_required():
        return redirect("/")

    maturity_amount = None

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
            months = int(request.form.get("months", 0))
        except ValueError:
            return "Invalid amount or months"

        if amount <= 0:
            return "Amount must be greater than 0"

        if months <= 0:
            return "Months must be greater than 0"

        interest_rate = 7.5
        created_at = get_current_datetime()

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
        user = c.fetchone()

        if user is None:
            conn.close()
            return "User not found"

        balance = user[0]

        if balance < amount:
            conn.close()
            return "Insufficient Balance"

        new_balance = balance - amount

        c.execute("UPDATE users SET balance=? WHERE card=?", (new_balance, session["card"]))

        c.execute("""
            INSERT INTO fixed_deposits(card, amount, months, interest_rate, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (session["card"], amount, months, interest_rate, created_at))

        c.execute("""
            INSERT INTO transactions(card, type, amount, date)
            VALUES (?, ?, ?, ?)
        """, (session["card"], "Fixed Deposit", amount, created_at))

        conn.commit()
        conn.close()

        maturity_amount = amount + ((amount * interest_rate * months) / (12 * 100))
        return render_template(
            "fixed_deposit.html",
            maturity_amount=round(maturity_amount, 2),
            success=f"Fixed Deposit of ₹{amount} created successfully for {months} months"
        )

    return render_template("fixed_deposit.html", maturity_amount=maturity_amount)

# =========================
# INTEREST CALCULATOR
# =========================
@app.route("/interest_calculator", methods=["GET", "POST"])
def interest_calculator():
    interest = None
    total_amount = None

    if request.method == "POST":
        try:
            principal = float(request.form.get("principal", 0))
            rate = float(request.form.get("rate", 0))
            time = float(request.form.get("time", 0))
        except ValueError:
            return "Invalid input"

        if principal < 0 or rate < 0 or time < 0:
            return "Values cannot be negative"

        interest = (principal * rate * time) / 100
        total_amount = principal + interest

    return render_template(
        "interest_calculator.html",
        interest=interest,
        total_amount=total_amount
    )

# =========================
# CHANGE PIN
# =========================
@app.route("/change_pin", methods=["GET", "POST"])
def change_pin():
    if not login_required():
        return redirect("/")

    if request.method == "POST":
        old_pin = request.form.get("old_pin", "").strip()
        new_pin = request.form.get("new_pin", "").strip()
        confirm_pin = request.form.get("confirm_pin", "").strip()

        if not old_pin or not new_pin or not confirm_pin:
            return "All fields are required"

        if new_pin != confirm_pin:
            return "New PIN and Confirm PIN do not match"

        if len(new_pin) < 4:
            return "New PIN must be at least 4 characters"

        conn = get_conn()
        c = conn.cursor()

        c.execute("SELECT pin FROM users WHERE card=?", (session["card"],))
        user = c.fetchone()

        if user is None:
            conn.close()
            return "User not found"

        db_pin = user[0]

        if not check_password_hash(db_pin, old_pin):
            conn.close()
            return "Old PIN is incorrect"

        hashed_new_pin = generate_password_hash(new_pin)
        c.execute("UPDATE users SET pin=? WHERE card=?", (hashed_new_pin, session["card"]))
        conn.commit()
        conn.close()

        return "PIN changed successfully"

    return render_template("change_pin.html")

# =========================
# ACCOUNT DETAILS
# =========================
@app.route("/account_details")
def account_details():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT name, email, card, balance
        FROM users
        WHERE card=?
    """, (session["card"],))

    user = c.fetchone()
    conn.close()

    return render_template("account_details.html", user=user)

# =========================
# PROFILE
# =========================
@app.route("/profile")
def profile():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT card, name, email, balance, profile_pic
        FROM users
        WHERE card=?
    """, (session["card"],))

    user = c.fetchone()
    conn.close()

    return render_template("profile.html", user=user)

# =========================
# EDIT PROFILE
# =========================
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not email:
            conn.close()
            return "Name and email are required"

        file = request.files.get("profile_pic")

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            c.execute("""
                UPDATE users
                SET name=?, email=?, profile_pic=?
                WHERE card=?
            """, (name, email, filename, session["card"]))
        else:
            c.execute("""
                UPDATE users
                SET name=?, email=?
                WHERE card=?
            """, (name, email, session["card"]))

        conn.commit()
        conn.close()

        return redirect("/profile")

    c.execute("""
        SELECT card, name, email, profile_pic
        FROM users
        WHERE card=?
    """, (session["card"],))
    user = c.fetchone()
    conn.close()

    return render_template("edit_profile.html", user=user)

# =========================
# FILTER TRANSACTIONS
# =========================
@app.route("/filter_transactions", methods=["GET", "POST"])
def filter_transactions():
    if not login_required():
        return redirect("/")

    transactions = []

    if request.method == "POST":
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()

        if not start_date or not end_date:
            return render_template("filter_transactions.html", transactions=[])

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT type, amount, date
            FROM transactions
            WHERE card=?
            ORDER BY id DESC
        """, (session["card"],))

        all_rows = c.fetchall()
        conn.close()

        filtered = []
        for row in all_rows:
            try:
                tx_date = datetime.strptime(row[2], "%d-%m-%Y %H:%M:%S").date()
                s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
                e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

                if s_date <= tx_date <= e_date:
                    filtered.append(row)
            except Exception:
                pass

        transactions = filtered

    return render_template("filter_transactions.html", transactions=transactions)

# =========================
# EXPORT CSV
# =========================
@app.route("/export_csv")
def export_csv():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
    """, (session["card"],))

    data = c.fetchall()

    c.execute("SELECT name, card FROM users WHERE card=?", (session["card"],))
    user = c.fetchone()

    conn.close()

    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    file_name = os.path.join(reports_dir, "transaction_report.csv")

    with open(file_name, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        if user:
            writer.writerow(["ATM Management System"])
            writer.writerow(["Name", user[0]])
            writer.writerow(["Card Number", user[1]])
            writer.writerow(["Generated On", get_current_datetime()])
            writer.writerow([])

        writer.writerow(["Transaction Type", "Amount", "Date"])
        for row in data:
            writer.writerow(row)

    return send_file(file_name, as_attachment=True)

# =========================
# PDF REPORT
# =========================
@app.route("/download_pdf")
def download_pdf():
    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT name, card FROM users WHERE card=?", (session["card"],))
    user = c.fetchone()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
    """, (session["card"],))
    data = c.fetchall()

    conn.close()

    if not user:
        return "User not found"

    user_name = user[0]
    card_number = user[1]
    total_transactions = len(data)
    report_time = get_current_datetime()

    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    file_name = os.path.join(reports_dir, "transaction_report.pdf")

    pdf = canvas.Canvas(file_name)
    pdf.setTitle("ATM Transaction Report")

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(150, 810, "ATM Management System")

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(180, 785, "Transaction Report")

    pdf.line(40, 770, 550, 770)

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, 745, f"Name: {user_name}")
    pdf.drawString(50, 725, f"Card Number: {card_number}")
    pdf.drawString(50, 705, f"Generated On: {report_time}")
    pdf.drawString(50, 685, f"Total Transactions: {total_transactions}")

    pdf.line(40, 670, 550, 670)

    y = 645
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, "No.")
    pdf.drawString(90, y, "Transaction Type")
    pdf.drawString(280, y, "Amount")
    pdf.drawString(380, y, "Date & Time")

    pdf.line(40, y - 5, 550, y - 5)
    y -= 25

    pdf.setFont("Helvetica", 10)

    if not data:
        pdf.drawString(50, y, "No transactions found.")
    else:
        for index, row in enumerate(data, start=1):
            tx_type = str(row[0])
            amount = f"₹ {row[1]}"
            tx_date = str(row[2])

            pdf.drawString(50, y, str(index))
            pdf.drawString(90, y, tx_type[:28])
            pdf.drawString(280, y, amount)
            pdf.drawString(380, y, tx_date)

            y -= 20

            if y < 70:
                pdf.showPage()
                y = 800

                pdf.setFont("Helvetica-Bold", 14)
                pdf.drawString(180, 780, "ATM Transaction Report (Continued)")
                pdf.line(40, 765, 550, 765)

                y = 735
                pdf.setFont("Helvetica-Bold", 11)
                pdf.drawString(50, y, "No.")
                pdf.drawString(90, y, "Transaction Type")
                pdf.drawString(280, y, "Amount")
                pdf.drawString(380, y, "Date & Time")
                pdf.line(40, y - 5, 550, y - 5)

                y -= 25
                pdf.setFont("Helvetica", 10)

    pdf.line(40, 50, 550, 50)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(50, 35, "Generated by ATM Management System")
    pdf.drawRightString(545, 35, "End of Report")

    pdf.save()

    return send_file(file_name, as_attachment=True)

# =========================
# SEARCH TRANSACTION
# =========================
@app.route("/search", methods=["GET", "POST"])
def search():
    if not login_required():
        return redirect("/")

    data = []

    if request.method == "POST":
        keyword = request.form.get("keyword", "").strip()

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT type, amount, date
            FROM transactions
            WHERE card=? AND type LIKE ?
            ORDER BY id DESC
        """, (session["card"], "%" + keyword + "%"))

        data = c.fetchall()
        conn.close()

    return render_template("search.html", data=data)

# =========================
# ADMIN LOGIN
# =========================
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == "admin" and password == "admin123":
            session["admin"] = True
            return redirect("/admin_dashboard")
        else:
            return "Invalid Admin Username or Password"

    return render_template("admin_login.html")

# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    c.execute("SELECT SUM(balance) FROM users")
    total_balance = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Deposit'")
    total_deposits = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Withdraw'")
    total_withdrawals = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Money Transfer Sent'")
    total_transfers = c.fetchone()[0] or 0

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_balance=total_balance,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_transfers=total_transfers
    )

# =========================
# ADMIN CHART
# =========================
@app.route("/admin_chart")
def admin_chart():
    if "admin" not in session:
        return redirect("/admin_login")

    import matplotlib.pyplot as plt

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Deposit'")
    total_deposit = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Withdraw'")
    total_withdraw = c.fetchone()[0] or 0

    conn.close()

    labels = ["Deposit", "Withdraw"]
    values = [total_deposit, total_withdraw]

    plt.figure(figsize=(6, 4))
    plt.bar(labels, values)
    plt.title("ATM Transactions Chart")
    plt.ylabel("Amount")

    chart_path = os.path.join("static", "chart.png")
    plt.savefig(chart_path)
    plt.close()

    return render_template("admin_chart.html")

# =========================
# ALL USERS
# =========================
@app.route("/all_users")
def all_users():
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT id, name, email, card, balance, is_locked FROM users")
    users = c.fetchall()

    conn.close()

    return render_template("all_users.html", users=users)

# =========================
# ADD USER
# =========================
@app.route("/add_user", methods=["GET", "POST"])
def add_user():
    if "admin" not in session:
        return redirect("/admin_login")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        card = request.form.get("card", "").strip()
        pin = request.form.get("pin", "").strip()
        balance = request.form.get("balance", "0").strip()

        if not all([name, email, card, pin]):
            return "All required fields must be filled"

        hashed_pin = generate_password_hash(pin)

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            INSERT INTO users(name, email, card, pin, balance)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, card, hashed_pin, balance))

        conn.commit()
        conn.close()

        return redirect("/all_users")

    return render_template("add_user.html")

# =========================
# EDIT USER
# =========================
@app.route("/edit_user/<int:id>", methods=["GET", "POST"])
def edit_user(id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_conn()
    c = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        card = request.form.get("card", "").strip()
        pin = request.form.get("pin", "").strip()
        balance = request.form.get("balance", "0").strip()

        if not all([name, email, card, pin]):
            conn.close()
            return "All fields are required"

        hashed_pin = generate_password_hash(pin)

        c.execute("""
            UPDATE users
            SET name=?, email=?, card=?, pin=?, balance=?
            WHERE id=?
        """, (name, email, card, hashed_pin, balance, id))

        conn.commit()
        conn.close()

        return redirect("/all_users")

    c.execute("SELECT * FROM users WHERE id=?", (id,))
    user = c.fetchone()
    conn.close()

    return render_template("edit_user.html", user=user)

# =========================
# DELETE USER
# =========================
@app.route("/delete_user/<int:id>")
def delete_user(id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_conn()
    c = conn.cursor()

    c.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/all_users")

# =========================
# UNLOCK USER
# =========================
@app.route("/unlock_user/<int:id>")
def unlock_user(id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        UPDATE users
        SET failed_attempts=0, is_locked=0
        WHERE id=?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/all_users")

# =========================
# SEARCH USER
# =========================
@app.route("/search_user", methods=["GET", "POST"])
def search_user():
    if "admin" not in session:
        return redirect("/admin_login")

    users = []

    if request.method == "POST":
        keyword = request.form.get("keyword", "").strip()

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT id, name, email, card, balance
            FROM users
            WHERE name LIKE ? OR card LIKE ?
        """, ("%" + keyword + "%", "%" + keyword + "%"))

        users = c.fetchall()
        conn.close()

    return render_template("search_user.html", users=users)

# =========================
# FINAL APP RUN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)