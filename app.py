from flask import Flask, render_template, request, redirect, session
import sqlite3
from datetime import datetime,timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import send_file
from reportlab.pdfgen import canvas
from werkzeug.utils import secure_filename
import os
import csv
import matplotlib.pyplot as plt
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "atm_secret_key"
app.permanent_session_lifetime = timedelta(minutes=2)
SENDER_EMAIL = "jalmodi360@gmail.com"
SENDER_PASSWORD = "jal@2008"

def create_database():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card TEXT UNIQUE,
        pin TEXT,
        name TEXT,
        email TEXT,
        balance REAL,
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

    c.execute("SELECT * FROM users WHERE card='246450307052'")
    user = c.fetchone()

    if user is None:
        demo_pin = generate_password_hash("#Rm_54321")
        c.execute("""
        INSERT INTO users(card, pin, name, email, balance)
        VALUES (?, ?, ?, ?, ?)
        """, ('246450307052', demo_pin, 'Jal Modi', 'jal@example.com', 10000))

    conn.commit()
    conn.close()

create_database()

@app.before_request
def make_session_permanent():
    session.permanent = True

def send_email_receipt(to_email, subject, message):
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

@app.route("/", methods=["GET","POST"])
def login():

    if request.method == "POST":
        card = request.form["card"]
        pin = request.form["pin"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE card=?", (card,))
        user = c.fetchone()

        if user:
            user_id = user[0]
            db_pin = user [2]
            failed_attempts = user[6]
            is_locked = user[7]

            # Account locked check
            if is_locked == 1:
                conn.close()
                return "Your account is locked due to 3 wrong login attempts."

            # Correct PIN
            if check_password_hash(db_pin, pin):
                last_login = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                login_ip = request.remote_addr

                c.execute("""
                UPDATE users
                SET failed_attempts=0, last_login=?,login_ip=?
                WHERE id=?
                """, (login_ip,last_login, user_id))
                conn.commit()
                conn.close()
                
                session.permanent = True
                session["card"] = card
                return redirect("/dashboard")

            # Wrong PIN
            else:
                failed_attempts += 1

                if failed_attempts >= 3:
                    c.execute(
                        "UPDATE users SET failed_attempts=?, is_locked=1 WHERE id=?",
                        (failed_attempts, user_id)
                    )
                    conn.commit()
                    conn.close()
                    return "Account locked! You entered wrong PIN 3 times."

                else:
                    c.execute(
                        "UPDATE users SET failed_attempts=? WHERE id=?",
                        (failed_attempts, user_id)
                    )
                    conn.commit()
                    conn.close()
                    return f"Wrong PIN! Attempt {failed_attempts}/3"

        conn.close()
        return "Card Number Not Found"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        card = request.form["card"]
        pin = request.form["pin"]
        security_question = request.form["security_question"]
        security_answer = request.form["security_answer"]

        hashed_pin = generate_password_hash(pin)

        conn = sqlite3.connect("database.db")
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

@app.route("/forgot_pin", methods=["GET", "POST"])
def forgot_pin():

    if request.method == "POST":
        card = request.form["card"]
        security_question = request.form["security_question"]
        security_answer = request.form["security_answer"]
        new_pin = request.form["new_pin"]

        conn = sqlite3.connect("database.db")
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

@app.route("/dashboard")
def dashboard():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT name,card,balance,last_login, login_ip FROM users WHERE card=?",(session["card"],))
    user = c.fetchone()

    conn.close()

    return render_template("dashboard.html",
                           name=user[0],
                           balance=user[1],
                           last_login=user[2],
                           login_ip=user[3]
                           )

@app.route("/balance")
def balance():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
    balance = c.fetchone()[0]

    conn.close()

    return render_template("balance.html", balance=balance)

@app.route("/deposit", methods=["GET","POST"])
def deposit():

    if "card" not in session:
        return redirect("/")

    if request.method=="POST":

        amount=float(request.form["amount"])

        conn=sqlite3.connect("database.db")
        c=conn.cursor()

        c.execute("UPDATE users SET balance=balance+? WHERE card=?",
                  (amount,session["card"]))

        c.execute("""
        INSERT INTO transactions(card,type,amount,date)
        VALUES(?,?,?,?)
        """,(session["card"],"Deposit",amount,
             datetime.now().strftime("%d-%m-%Y %H:%M")))

        conn.commit()

        c.execute("SELECT email FROM users WHERE card=?", (session["card"],))
        user_email = c.fetchone()[0]

        send_email_receipt(
        user_email,
        "ATM Deposit Receipt",
        f"Dear User,\n\nYour deposit of ₹{amount} was successful.\n\nThank you for using ATM Management System."
        )
        conn.close()

        return redirect("/dashboard")

    return render_template("deposit.html")

@app.route("/withdraw", methods=["GET","POST"])
def withdraw():

    if "card" not in session:
        return redirect("/")

    if request.method=="POST":

        amount = float(request.form["amount"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
        balance = c.fetchone()[0]

        if balance >= amount:

            c.execute("UPDATE users SET balance=balance-? WHERE card=?",
                      (amount, session["card"]))

            c.execute("""
            INSERT INTO transactions(card,type,amount,date)
            VALUES(?,?,?,?)
            """, (session["card"], "Withdraw", amount,
                  datetime.now().strftime("%d-%m-%Y %H:%M")))

            conn.commit()

            c.execute("SELECT email FROM users WHERE card=?", (session["card"],))
            user_email = c.fetchone()[0]

            send_email_receipt(
                user_email,
                "ATM Withdrawal Receipt",
                f"Dear User,\n\nYour withdrawal of ₹{amount} was successful.\n\nThank you for using ATM Management System."
            )

            conn.close()
            return redirect("/dashboard")

        else:
            conn.close()
            return "Insufficient Balance"

    return render_template("withdraw.html")

@app.route("/fast_cash", methods=["GET", "POST"])
def fast_cash():

    if "card" not in session:
        return redirect("/")

    if request.method == "POST":
        amount = int(request.form["amount"])

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
        user = c.fetchone()

        if user:
            balance = user[0]

            if balance >= amount:
                new_balance = balance - amount

                c.execute("UPDATE users SET balance=? WHERE card=?", (new_balance, session["card"]))

                c.execute("""
                    INSERT INTO transactions(card, type, amount)
                    VALUES (?, ?, ?)
                """, (session["card"], "Fast Cash Withdraw", amount))

                conn.commit()
                conn.close()

                return f"₹{amount} withdrawn successfully using Fast Cash"
            else:
                conn.close()
                return "Insufficient Balance"

        conn.close()
        return "User not found"

    return render_template("fast_cash.html")

@app.route("/fixed_deposit", methods=["GET", "POST"])
def fixed_deposit():

    if "card" not in session:
        return redirect("/")

    if request.method == "POST":
        amount = float(request.form["amount"])
        months = int(request.form["months"])
        interest_rate = 7.5
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
        user = c.fetchone()

        if user:
            balance = user[0]

            if balance >= amount:
                new_balance = balance - amount

                # user balance update
                c.execute("UPDATE users SET balance=? WHERE card=?", (new_balance, session["card"]))

                # fixed deposit save
                c.execute("""
                    INSERT INTO fixed_deposits(card, amount, months, interest_rate, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (session["card"], amount, months, interest_rate, created_at))

                # transaction history entry
                c.execute("""
                    INSERT INTO transactions(card, type, amount)
                    VALUES (?, ?, ?)
                """, (session["card"], "Fixed Deposit", amount))

                conn.commit()
                conn.close()

                return f"Fixed Deposit of ₹{amount} created successfully for {months} months"

            else:
                conn.close()
                return "Insufficient Balance"

        conn.close()
        return "User not found"

    return render_template("fixed_deposit.html",maturity_amount=None)

@app.route("/interest_calculator", methods=["GET", "POST"])
def interest_calculator():

    interest = None
    total_amount = None

    if request.method == "POST":
        principal = float(request.form["principal"])
        rate = float(request.form["rate"])
        time = float(request.form["time"])

        interest = (principal * rate * time) / 100
        total_amount = principal + interest

    return render_template(
        "interest_calculator.html",
        interest=interest,
        total_amount=total_amount
    )

@app.route("/history")
def history():

    if "card" not in session:
        return redirect("/")

    conn=sqlite3.connect("database.db")
    c=conn.cursor()

    c.execute("""
    SELECT type,amount,date
    FROM transactions
    WHERE card=?
    ORDER BY id DESC
    """,(session["card"],))

    data=c.fetchall()

    conn.close()

    return render_template("history.html",data=data)

@app.route("/filter_transactions", methods=["GET", "POST"])
def filter_transactions():

    if "card" not in session:
        return redirect("/")

    transactions = []

    if request.method == "POST":
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            SELECT type, amount, date
            FROM transactions
            WHERE card=? AND date BETWEEN ? AND ?
            ORDER BY id DESC
        """, (session["card"], start_date, end_date))

        transactions = c.fetchall()
        conn.close()

    return render_template("filter_transactions.html", transactions=transactions)

@app.route("/download_pdf")
def download_pdf():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
    """, (session["card"],))

    data = c.fetchall()
    conn.close()

    file_name = "transaction_report.pdf"
    pdf = canvas.Canvas(file_name)

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(180, 800, "ATM Transaction Report")

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, 770, f"Card Number: {session['card']}")

    y = 740
    pdf.drawString(50, y, "Type")
    pdf.drawString(220, y, "Amount")
    pdf.drawString(320, y, "Date")

    y -= 20

    for row in data:
        pdf.drawString(50, y, str(row[0]))
        pdf.drawString(220, y, f"₹ {row[1]}")
        pdf.drawString(320, y, str(row[2]))
        y -= 20

        if y < 50:
            pdf.showPage()
            y = 800

    pdf.save()

    return send_file(file_name, as_attachment=True)

@app.route("/export_csv")
def export_csv():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        SELECT type, amount, date
        FROM transactions
        WHERE card=?
        ORDER BY id DESC
    """, (session["card"],))

    data = c.fetchall()
    conn.close()

    file_name = "transaction_report.csv"

    with open(file_name, mode="w", newline="") as file:
        writer = csv.writer(file)

        writer.writerow(["Transaction Type", "Amount", "Date"])

        for row in data:
            writer.writerow(row)

    return send_file(file_name, as_attachment=True)

@app.route("/receipt")
def receipt():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
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

    return render_template("receipt.html",
                           card=session["card"],
                           transaction=transaction)

@app.route("/transfer", methods=["GET", "POST"])
def transfer():
    if "card" not in session:
        return redirect("/")

    if request.method == "POST":
        receiver = request.form.get("receiver")
        try:
            amount = float(request.form.get("amount", 0))
        except ValueError:
            return "Invalid amount"

        if receiver == session["card"]:
            return "You cannot transfer money to your own account"

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        # Sender Balance
        c.execute("SELECT balance FROM users WHERE card=?", (session["card"],))
        sender = c.fetchone()

        if sender is None:
            conn.close()
            return "Sender not found"

        sender_balance = sender[0]

        # Receiver Check
        c.execute("SELECT * FROM users WHERE card=?", (receiver,))
        user = c.fetchone()

        if user is None:
            conn.close()
            return "Receiver Card Number Not Found"

        if sender_balance < amount:
            conn.close()
            return "Insufficient Balance"

        # Deduct Sender Balance
        c.execute(
            "UPDATE users SET balance=balance-? WHERE card=?",
            (amount, session["card"])
        )

        # Add Receiver Balance
        c.execute(
            "UPDATE users SET balance=balance+? WHERE card=?",
            (amount, receiver)
        )

        # Sender History
        c.execute("""
        INSERT INTO transactions(card,type,amount,date)
        VALUES(?,?,?,?)
        """, (
            session["card"],
            "Money Transfer",
            amount,
            datetime.now().strftime("%d-%m-%Y %H:%M")
        ))

        conn.commit()
        conn.close()

        return redirect("/dashboard")

    return render_template("transfer.html")

@app.route("/change_pin", methods=["GET", "POST"])
def change_pin():
    if "card" not in session:
        return redirect("/")

    if request.method == "POST":
        old_pin = request.form["old_pin"]
        new_pin = request.form["new_pin"]
        confirm_pin = request.form["confirm_pin"]
        
        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("SELECT pin FROM users WHERE card=?", (session["card"],))
        user = c.fetchone()
        
        if user is None:
            conn.close()
            return "User not found"

        db_pin = user[0]

        # Check old PIN
        if not check_password_hash(db_pin, old_pin):
            conn.close()
            return "Old PIN is incorrect"

        # Check new PIN and confirm PIN match
        if new_pin != confirm_pin:
            conn.close()
            return "New PIN and Confirm PIN do not match"

        # Update PIN
        hashed_new_pin = generate_password_hash(new_pin)
        c.execute("UPDATE users SET pin=? WHERE card=?", (hashed_new_pin, session["card"]))
        conn.commit()
        conn.close()

        return "PIN changed successfully"

    return render_template("change_pin.html")

@app.route("/profile")
def profile():
    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute(
        "SELECT card, name, email, balance, profile_pic FROM users WHERE card=?",
        (session["card"],)
    )

    user = c.fetchone()

    conn.close()

    return render_template("profile.html", user=user)

@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]

        profile_pic = None
        file = request.files.get("profile_pic")

        if file and file.filename != "":
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            profile_pic = filename

            c.execute("""
                UPDATE users
                SET name=?, email=?, profile_pic=?
                WHERE card=?
            """, (name, email, profile_pic, session["card"]))
        else:
            c.execute("""
                UPDATE users
                SET name=?, email=?
                WHERE card=?
            """, (name, email, session["card"]))

        conn.commit()
        conn.close()

        return redirect("/profile")

    c.execute("SELECT card, name, email, profile_pic FROM users WHERE card=?", (session["card"],))
    user = c.fetchone()
    conn.close()

    return render_template("edit_profile.html", user=user)

@app.route("/mini_statement")
def mini_statement():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
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

@app.route("/account_details")
def account_details():

    if "card" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    SELECT name,email,card,balance
    FROM users
    WHERE card=?
    """, (session["card"],))

    user = c.fetchone()

    conn.close()

    return render_template("account_details.html", user=user)

@app.route("/search", methods=["GET","POST"])
def search():

    if "card" not in session:
        return redirect("/")

    data=[]

    if request.method=="POST":

        keyword=request.form["keyword"]

        conn=sqlite3.connect("database.db")
        c=conn.cursor()

        c.execute("""
        SELECT type,amount,date
        FROM transactions
        WHERE card=?
        AND type LIKE ?
        """,(session["card"],"%"+keyword+"%"))

        data=c.fetchall()

        conn.close()

    return render_template("search.html",data=data)

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "admin" and password == "admin123":
            session.permanent = True
            session["admin"] = True
            return redirect("/admin_dashboard")
        else:
            return "Invalid Admin Username or Password"

    return render_template("admin_login.html")


@app.route("/admin_dashboard")
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Total Users
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]

    # Total Balance
    c.execute("SELECT SUM(balance) FROM users")
    total_balance = c.fetchone()[0]
    if total_balance is None:
        total_balance = 0

    # Total Deposits
    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Deposit'")
    total_deposits = c.fetchone()[0]
    if total_deposits is None:
        total_deposits = 0

    # Total Withdrawals
    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Withdraw'")
    total_withdrawals = c.fetchone()[0]
    if total_withdrawals is None:
        total_withdrawals = 0

    # Total Transfers
    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Money Transfer'")
    total_transfers = c.fetchone()[0]
    if total_transfers is None:
        total_transfers = 0

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_balance=total_balance,
        total_deposits=total_deposits,
        total_withdrawals=total_withdrawals,
        total_transfers=total_transfers
    )

@app.route("/admin_chart")
def admin_chart():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Deposit'")
    total_deposit = c.fetchone()[0] or 0

    c.execute("SELECT SUM(amount) FROM transactions WHERE type='Withdraw'")
    total_withdraw = c.fetchone()[0] or 0

    conn.close()

    labels = ["Deposit", "Withdraw"]
    values = [total_deposit, total_withdraw]

    plt.figure(figsize=(6,4))
    plt.bar(labels, values)
    plt.title("ATM Transactions Chart")
    plt.ylabel("Amount")
    plt.savefig("static/chart.png")
    plt.close()

    return render_template("admin_chart.html")

@app.route("/all_users")
def all_users():

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT id, name, email, card, balance, is_locked FROM users")
    users = c.fetchall()

    conn.close()

    return render_template("all_users.html", users=users)


@app.route("/add_user", methods=["GET", "POST"])
def add_user():

    if "admin" not in session:
        return redirect("/admin_login")

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        card = request.form["card"]
        pin = request.form["pin"]
        hashed_pin = generate_password_hash(pin)
        balance = request.form["balance"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            INSERT INTO users(name, email, card, pin, balance)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, card, hashed_pin, balance))

        conn.commit()
        conn.close()

        return redirect("/all_users")

    return render_template("add_user.html")


@app.route("/edit_user/<int:id>", methods=["GET", "POST"])
def edit_user(id):

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        card = request.form["card"]
        pin = request.form["pin"]
        balance = request.form["balance"]
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


@app.route("/delete_user/<int:id>")
def delete_user(id):

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("DELETE FROM users WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect("/all_users")

@app.route("/unlock_user/<int:id>")
def unlock_user(id):

    if "admin" not in session:
        return redirect("/admin_login")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        UPDATE users
        SET failed_attempts = 0,
            is_locked = 0
        WHERE id = ?
    """, (id,))

    conn.commit()
    conn.close()

    return redirect("/all_users")

@app.route("/search_user", methods=["GET", "POST"])
def search_user():

    if "admin" not in session:
        return redirect("/admin_login")

    users = []

    if request.method == "POST":
        keyword = request.form["keyword"]

        conn = sqlite3.connect("database.db")
        c = conn.cursor()

        c.execute("""
            SELECT id, name, email, card, balance
            FROM users
            WHERE name LIKE ? OR card LIKE ?
        """, ("%"+keyword+"%", "%"+keyword+"%"))

        users = c.fetchall()
        conn.close()

    return render_template("search_user.html", users=users)

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000,debug=True)