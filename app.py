from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session,
    send_file
)

from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from reportlab.pdfgen import canvas
from psycopg2.errors import UniqueViolation

import psycopg2
import os
import csv
import smtplib
import uuid

from email.mime.text import MIMEText


# ==================================================
# FLASK APPLICATION
# ==================================================

app = Flask(__name__)

# ==================================================
# ENVIRONMENT CONFIGURATION
# ==================================================

SECRET_KEY = os.environ.get("SECRET_KEY") or "atm-development-secret-key-2026"
DATABASE_URL = os.environ.get("DATABASE_URL")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME") or "admin"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD") or "admin123"

SENDER_EMAIL = os.environ.get("ATM_EMAIL") or ""
SENDER_PASSWORD = os.environ.get("ATM_EMAIL_PASSWORD") or ""

# Flask sessions require a non-empty secret key.
app.config["SECRET_KEY"] = SECRET_KEY

# ==================================================
# POSTGRESQL URL FIX
# ==================================================

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )


# ==================================================
# SESSION SECURITY
# ==================================================

app.permanent_session_lifetime = timedelta(minutes=10)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

if os.environ.get("VERCEL"):
    app.config["SESSION_COOKIE_SECURE"] = True


# ==================================================
# FOLDER CONFIGURATION
# ==================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

if os.environ.get("VERCEL"):
    RUNTIME_DIR = "/tmp"
else:
    RUNTIME_DIR = BASE_DIR


UPLOAD_FOLDER = os.path.join(
    RUNTIME_DIR,
    "uploads"
)

REPORTS_FOLDER = os.path.join(
    RUNTIME_DIR,
    "reports"
)


os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

os.makedirs(
    REPORTS_FOLDER,
    exist_ok=True
)


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is missing")

    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        connect_timeout=10
    )

# ==================================================
# CURRENT DATE TIME
# ==================================================

def get_current_datetime():

    return datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    )


# ==================================================
# TRANSACTION REFERENCE ID
# ==================================================

def generate_reference_id():

    return "ATM-" + uuid.uuid4().hex[:12].upper()


# ==================================================
# CARD MASKING
# ==================================================

def mask_card(card):

    card = str(card)

    if len(card) <= 4:
        return card

    return "*" * (
        len(card) - 4
    ) + card[-4:]


# ==================================================
# LOGIN CHECK
# ==================================================

def login_required():

    return "card" in session


# ==================================================
# ADMIN CHECK
# ==================================================

def admin_required():

    return session.get(
        "admin"
    ) is True


# ==================================================
# DATABASE SETUP
# ==================================================

def create_database():

    conn = get_conn()

    c = conn.cursor()

    try:

        # ==========================================
        # USERS TABLE
        # ==========================================

        c.execute("""
            CREATE TABLE IF NOT EXISTS users(

                id BIGSERIAL PRIMARY KEY,

                card TEXT UNIQUE NOT NULL,

                pin TEXT NOT NULL,

                name TEXT NOT NULL,

                email TEXT,

                balance DOUBLE PRECISION DEFAULT 0,

                failed_attempts INTEGER DEFAULT 0,

                is_locked INTEGER DEFAULT 0,

                security_question TEXT,

                security_answer TEXT,

                last_login TEXT,

                login_ip TEXT,

                profile_pic TEXT,

                created_at TEXT

            )
        """)


        # ==========================================
        # TRANSACTIONS TABLE
        # ==========================================

        c.execute("""
            CREATE TABLE IF NOT EXISTS transactions(

                id BIGSERIAL PRIMARY KEY,

                reference_id TEXT UNIQUE,

                card TEXT NOT NULL,

                type TEXT NOT NULL,

                amount DOUBLE PRECISION NOT NULL,

                date TEXT

            )
        """)


        # ==========================================
        # FIXED DEPOSITS TABLE
        # ==========================================

        c.execute("""
            CREATE TABLE IF NOT EXISTS fixed_deposits(

                id BIGSERIAL PRIMARY KEY,

                card TEXT NOT NULL,

                amount DOUBLE PRECISION NOT NULL,

                months INTEGER NOT NULL,

                interest_rate DOUBLE PRECISION NOT NULL,

                maturity_amount DOUBLE PRECISION,

                created_at TEXT

            )
        """)


        # ==========================================
        # WITHDRAWAL LIMIT TABLE
        # ==========================================

        c.execute("""
            CREATE TABLE IF NOT EXISTS withdrawal_limits(

                id BIGSERIAL PRIMARY KEY,

                card TEXT NOT NULL,

                amount DOUBLE PRECISION NOT NULL,

                withdrawal_date DATE NOT NULL

            )
        """)


        # ==========================================
        # DATABASE MIGRATION
        # ==========================================

        c.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS created_at TEXT
        """)

        c.execute("""
            ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS reference_id TEXT
        """)

        c.execute("""
            ALTER TABLE fixed_deposits
            ADD COLUMN IF NOT EXISTS maturity_amount
            DOUBLE PRECISION
        """)


        # ==========================================
        # CREATE MISSING TRANSACTION REFERENCES
        # ==========================================

        c.execute("""
            SELECT id
            FROM transactions
            WHERE reference_id IS NULL
        """)

        transactions = c.fetchall()

        for transaction in transactions:

            c.execute(
                """
                UPDATE transactions
                SET reference_id=%s
                WHERE id=%s
                """,
                (
                    generate_reference_id(),
                    transaction[0]
                )
            )


        conn.commit()

        print(
            "DATABASE INITIALIZED SUCCESSFULLY"
        )

    except Exception as error:

        conn.rollback()

        print(
            "DATABASE SETUP ERROR:",
            error
        )

        raise

    finally:

        c.close()

        conn.close()


# Database initialization runs when the application starts locally.
# For Vercel, initialize lazily once before handling the first request.
_database_initialized = False


# ==================================================
# SESSION CONFIGURATION
# ==================================================

@app.before_request
def make_session_permanent():
    global _database_initialized

    if not _database_initialized:
        create_database()
        _database_initialized = True

    session.permanent = True


# ==================================================
# EMAIL RECEIPT
# ==================================================

def send_email_receipt(
    to_email,
    subject,
    message
):

    if (
        not SENDER_EMAIL
        or not SENDER_PASSWORD
        or not to_email
    ):

        print(
            "Email skipped: Email configuration missing"
        )

        return


    try:

        msg = MIMEText(
            message
        )

        msg["Subject"] = subject

        msg["From"] = SENDER_EMAIL

        msg["To"] = to_email


        with smtplib.SMTP(
            "smtp.gmail.com",
            587,
            timeout=20
        ) as server:

            server.starttls()

            server.login(
                SENDER_EMAIL,
                SENDER_PASSWORD
            )

            server.sendmail(
                SENDER_EMAIL,
                to_email,
                msg.as_string()
            )


    except Exception as error:

        print(
            "EMAIL ERROR:",
            error
        )


# ==================================================
# ADD TRANSACTION HELPER
# ==================================================

def add_transaction(
    cursor,
    card,
    transaction_type,
    amount
):

    reference_id = generate_reference_id()

    transaction_date = get_current_datetime()

    cursor.execute(
        """
        INSERT INTO transactions(
            reference_id,
            card,
            type,
            amount,
            date
        )
        VALUES(
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            reference_id,
            card,
            transaction_type,
            amount,
            transaction_date
        )
    )

    return reference_id


# ==================================================
# USER LOGIN
# ==================================================

@app.route(
    "/",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        card = request.form.get(
            "card",
            ""
        ).strip()

        pin = request.form.get(
            "pin",
            ""
        ).strip()


        if not card or not pin:

            return (
                "Card Number and PIN are required"
            )


        conn = get_conn()

        c = conn.cursor()


        try:

            c.execute(
                """
                SELECT
                    id,
                    card,
                    pin,
                    failed_attempts,
                    is_locked
                FROM users
                WHERE card=%s
                """,
                (card,)
            )


            user = c.fetchone()


            if not user:

                return "Card Number Not Found"


            user_id = user[0]

            db_pin = user[2]

            failed_attempts = (
                user[3] or 0
            )

            is_locked = (
                user[4] or 0
            )


            if is_locked == 1:

                return (
                    "Your account is locked due to "
                    "3 wrong PIN attempts."
                )


            if check_password_hash(
                db_pin,
                pin
            ):

                last_login = (
                    get_current_datetime()
                )

                login_ip = (
                    request.remote_addr
                )


                c.execute(
                    """
                    UPDATE users
                    SET
                        failed_attempts=0,
                        last_login=%s,
                        login_ip=%s
                    WHERE id=%s
                    """,
                    (
                        last_login,
                        login_ip,
                        user_id
                    )
                )


                conn.commit()


                session.clear()

                session["card"] = card

                session.permanent = True


                return redirect(
                    "/dashboard"
                )


            failed_attempts += 1


            if failed_attempts >= 3:

                c.execute(
                    """
                    UPDATE users
                    SET
                        failed_attempts=%s,
                        is_locked=1
                    WHERE id=%s
                    """,
                    (
                        failed_attempts,
                        user_id
                    )
                )


                conn.commit()


                return (
                    "Account Locked! "
                    "Wrong PIN entered 3 times."
                )


            c.execute(
                """
                UPDATE users
                SET failed_attempts=%s
                WHERE id=%s
                """,
                (
                    failed_attempts,
                    user_id
                )
            )


            conn.commit()


            return (
                f"Wrong PIN! "
                f"Attempt {failed_attempts}/3"
            )


        finally:

            c.close()

            conn.close()


    return render_template(
        "login.html"
    )


# ==================================================
# USER REGISTER
# ==================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        card = request.form.get(
            "card",
            ""
        ).strip()

        pin = request.form.get(
            "pin",
            ""
        ).strip()

        security_question = request.form.get(
            "security_question",
            ""
        ).strip()

        security_answer = request.form.get(
            "security_answer",
            ""
        ).strip().lower()


        if not all([
            name,
            email,
            card,
            pin,
            security_question,
            security_answer
        ]):

            return "All fields are required"


        if not card.isdigit():

            return (
                "Card Number must contain "
                "only numbers"
            )


        if not pin.isdigit():

            return (
                "PIN must contain only numbers"
            )


        if len(pin) < 4:

            return (
                "PIN must be at least "
                "4 digits"
            )


        hashed_pin = generate_password_hash(
            pin
        )


        conn = get_conn()

        c = conn.cursor()


        try:

            c.execute(
                """
                INSERT INTO users(
                    card,
                    pin,
                    name,
                    email,
                    balance,
                    security_question,
                    security_answer,
                    created_at
                )
                VALUES(
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    card,
                    hashed_pin,
                    name,
                    email,
                    0,
                    security_question,
                    security_answer,
                    get_current_datetime()
                )
            )


            conn.commit()


        except UniqueViolation:

            conn.rollback()

            return (
                "Card Number Already Exists"
            )


        finally:

            c.close()

            conn.close()


        return redirect("/")


    return render_template(
        "register.html"
    )


# ==================================================
# FORGOT PIN
# ==================================================

@app.route(
    "/forgot_pin",
    methods=["GET", "POST"]
)
def forgot_pin():

    if request.method == "POST":

        card = request.form.get(
            "card",
            ""
        ).strip()

        security_question = request.form.get(
            "security_question",
            ""
        ).strip()

        security_answer = request.form.get(
            "security_answer",
            ""
        ).strip().lower()

        new_pin = request.form.get(
            "new_pin",
            ""
        ).strip()


        if not all([
            card,
            security_question,
            security_answer,
            new_pin
        ]):

            return "All fields are required"


        if (
            not new_pin.isdigit()
            or len(new_pin) < 4
        ):

            return (
                "New PIN must contain "
                "at least 4 digits"
            )


        conn = get_conn()

        c = conn.cursor()


        try:

            c.execute(
                """
                SELECT id
                FROM users
                WHERE card=%s
                AND security_question=%s
                AND LOWER(security_answer)=LOWER(%s)
                """,
                (
                    card,
                    security_question,
                    security_answer
                )
            )


            user = c.fetchone()


            if not user:

                return (
                    "Invalid Card Number, "
                    "Security Question or Answer"
                )


            hashed_new_pin = (
                generate_password_hash(
                    new_pin
                )
            )


            c.execute(
                """
                UPDATE users
                SET
                    pin=%s,
                    failed_attempts=0,
                    is_locked=0
                WHERE card=%s
                """,
                (
                    hashed_new_pin,
                    card
                )
            )


            conn.commit()


            return (
                "PIN Reset Successfully! "
                "Login with your new PIN."
            )


        finally:

            c.close()

            conn.close()


    return render_template(
        "forgot_pin.html"
    )


# ==================================================
# PART 1 COMPLETE
# NEXT CODE CONTINUES FROM DASHBOARD
# ==================================================

# ==================================================
# DASHBOARD
# ==================================================

@app.route("/dashboard")
def dashboard():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                name,
                card,
                balance,
                last_login,
                login_ip
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        if not user:
            session.clear()
            return redirect("/")

        c.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE card=%s
            """,
            (session["card"],)
        )

        total_transactions = c.fetchone()[0]

        c.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE card=%s
            AND type='Deposit'
            """,
            (session["card"],)
        )

        total_deposit = c.fetchone()[0]

        c.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE card=%s
            AND type IN (
                'Withdraw',
                'Fast Cash Withdraw'
            )
            """,
            (session["card"],)
        )

        total_withdraw = c.fetchone()[0]

        return render_template(
            "dashboard.html",
            name=user[0],
            card=user[1],
            balance=user[2],
            last_login=user[3],
            login_ip=user[4],
            total_transactions=total_transactions,
            total_deposit=total_deposit,
            total_withdraw=total_withdraw
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# BALANCE
# ==================================================

@app.route("/balance")
def balance():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT balance
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        if not user:
            session.clear()
            return redirect("/")

        return render_template(
            "balance.html",
            balance=user[0]
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# DEPOSIT
# ==================================================

@app.route(
    "/deposit",
    methods=["GET", "POST"]
)
def deposit():

    if not login_required():
        return redirect("/")

    if request.method == "POST":

        try:

            amount = float(
                request.form.get(
                    "amount",
                    0
                )
            )

        except (ValueError, TypeError):

            return "Invalid Amount"

        if amount <= 0:

            return (
                "Amount must be greater than 0"
            )

        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                UPDATE users
                SET balance=balance+%s
                WHERE card=%s
                RETURNING email, balance
                """,
                (
                    amount,
                    session["card"]
                )
            )

            user = c.fetchone()

            if not user:

                conn.rollback()

                return "User Not Found"

            reference_id = add_transaction(
                c,
                session["card"],
                "Deposit",
                amount
            )

            conn.commit()

            user_email = user[0]

            new_balance = user[1]

        except Exception as error:

            conn.rollback()

            print(
                "DEPOSIT ERROR:",
                error
            )

            return "Deposit Failed"

        finally:

            c.close()
            conn.close()

        send_email_receipt(
            user_email,
            "ATM Deposit Receipt",
            (
                "Dear User,\n\n"
                "Deposit Successful.\n\n"
                f"Reference ID: {reference_id}\n"
                f"Amount: INR {amount:.2f}\n"
                f"Balance: INR {new_balance:.2f}\n"
                f"Date: {get_current_datetime()}"
            )
        )

        return redirect("/receipt")

    return render_template(
        "deposit.html"
    )


# ==================================================
# DAILY WITHDRAWAL LIMIT
# ==================================================

DAILY_WITHDRAWAL_LIMIT = 50000


def get_today_withdrawal(
    cursor,
    card
):

    cursor.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        FROM withdrawal_limits
        WHERE card=%s
        AND withdrawal_date=CURRENT_DATE
        """,
        (card,)
    )

    result = cursor.fetchone()

    return float(
        result[0] or 0
    )


# ==================================================
# WITHDRAWAL PROCESS
# ==================================================

def process_withdrawal(
    amount,
    transaction_type
):

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                balance,
                email
            FROM users
            WHERE card=%s
            FOR UPDATE
            """,
            (session["card"],)
        )

        user = c.fetchone()

        if not user:

            conn.rollback()

            return (
                False,
                "User Not Found",
                None,
                None
            )

        current_balance = float(
            user[0]
        )

        user_email = user[1]

        if current_balance < amount:

            conn.rollback()

            return (
                False,
                "Insufficient Balance",
                user_email,
                None
            )

        today_withdrawal = (
            get_today_withdrawal(
                c,
                session["card"]
            )
        )

        if (
            today_withdrawal + amount
            > DAILY_WITHDRAWAL_LIMIT
        ):

            remaining_limit = max(
                0,
                DAILY_WITHDRAWAL_LIMIT
                - today_withdrawal
            )

            conn.rollback()

            return (
                False,
                (
                    "Daily Withdrawal Limit Exceeded. "
                    f"Remaining Limit: INR "
                    f"{remaining_limit:.2f}"
                ),
                user_email,
                None
            )

        c.execute(
            """
            UPDATE users
            SET balance=balance-%s
            WHERE card=%s
            RETURNING balance
            """,
            (
                amount,
                session["card"]
            )
        )

        updated_user = c.fetchone()

        new_balance = float(
            updated_user[0]
        )

        reference_id = add_transaction(
            c,
            session["card"],
            transaction_type,
            amount
        )

        c.execute(
            """
            INSERT INTO withdrawal_limits(
                card,
                amount,
                withdrawal_date
            )
            VALUES(
                %s,
                %s,
                CURRENT_DATE
            )
            """,
            (
                session["card"],
                amount
            )
        )

        conn.commit()

        return (
            True,
            (
                f"Withdrawal Successful. "
                f"Reference ID: {reference_id}"
            ),
            user_email,
            new_balance
        )

    except Exception as error:

        conn.rollback()

        print(
            "WITHDRAWAL ERROR:",
            error
        )

        return (
            False,
            "Transaction Failed",
            None,
            None
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# WITHDRAW
# ==================================================

@app.route(
    "/withdraw",
    methods=["GET", "POST"]
)
def withdraw():

    if not login_required():
        return redirect("/")

    if request.method == "POST":

        try:

            amount = float(
                request.form.get(
                    "amount",
                    0
                )
            )

        except (ValueError, TypeError):

            return "Invalid Amount"

        if amount <= 0:

            return (
                "Amount must be greater than 0"
            )

        success, message, email, new_balance = (
            process_withdrawal(
                amount,
                "Withdraw"
            )
        )

        if not success:

            return message

        send_email_receipt(
            email,
            "ATM Withdrawal Receipt",
            (
                "Dear User,\n\n"
                "Withdrawal Successful.\n\n"
                f"Amount: INR {amount:.2f}\n"
                f"Balance: INR {new_balance:.2f}\n"
                f"Date: {get_current_datetime()}"
            )
        )

        return redirect("/receipt")

    return render_template(
        "withdraw.html"
    )


# ==================================================
# FAST CASH
# ==================================================

@app.route(
    "/fast_cash",
    methods=["GET", "POST"]
)
def fast_cash():

    if not login_required():
        return redirect("/")

    fast_cash_amounts = [
        500,
        1000,
        2000,
        5000,
        10000
    ]

    if request.method == "POST":

        try:

            amount = float(
                request.form.get(
                    "amount",
                    0
                )
            )

        except (ValueError, TypeError):

            return "Invalid Amount"

        if amount not in fast_cash_amounts:

            return (
                "Invalid Fast Cash Amount"
            )

        success, message, email, new_balance = (
            process_withdrawal(
                amount,
                "Fast Cash Withdraw"
            )
        )

        if not success:

            return message

        send_email_receipt(
            email,
            "ATM Fast Cash Receipt",
            (
                "Dear User,\n\n"
                "Fast Cash Withdrawal Successful.\n\n"
                f"Amount: INR {amount:.2f}\n"
                f"Balance: INR {new_balance:.2f}\n"
                f"Date: {get_current_datetime()}"
            )
        )

        return redirect("/receipt")

    return render_template(
        "fast_cash.html",
        fast_cash_amounts=fast_cash_amounts
    )


# ==================================================
# MONEY TRANSFER
# ==================================================

@app.route(
    "/transfer",
    methods=["GET", "POST"]
)
def transfer():

    if not login_required():
        return redirect("/")

    if request.method == "POST":

        receiver = request.form.get(
            "receiver",
            ""
        ).strip()

        if not receiver:

            receiver = request.form.get(
                "receiver_card",
                ""
            ).strip()

        try:

            amount = float(
                request.form.get(
                    "amount",
                    0
                )
            )

        except (ValueError, TypeError):

            return "Invalid Amount"

        if not receiver:

            return (
                "Receiver Card Number is required"
            )

        if amount <= 0:

            return (
                "Amount must be greater than 0"
            )

        if receiver == session["card"]:

            return (
                "You cannot transfer money "
                "to your own account"
            )

        conn = get_conn()
        c = conn.cursor()

        try:

            cards = sorted([
                session["card"],
                receiver
            ])

            c.execute(
                """
                SELECT
                    card,
                    balance,
                    email
                FROM users
                WHERE card IN (%s, %s)
                ORDER BY card
                FOR UPDATE
                """,
                (
                    cards[0],
                    cards[1]
                )
            )

            users = {
                row[0]: row
                for row in c.fetchall()
            }

            sender = users.get(
                session["card"]
            )

            receiver_user = users.get(
                receiver
            )

            if not sender:

                conn.rollback()

                return "Sender Not Found"

            if not receiver_user:

                conn.rollback()

                return (
                    "Receiver Card Number Not Found"
                )

            sender_balance = float(
                sender[1]
            )

            if sender_balance < amount:

                conn.rollback()

                return "Insufficient Balance"

            c.execute(
                """
                UPDATE users
                SET balance=balance-%s
                WHERE card=%s
                RETURNING balance
                """,
                (
                    amount,
                    session["card"]
                )
            )

            new_sender_balance = float(
                c.fetchone()[0]
            )

            c.execute(
                """
                UPDATE users
                SET balance=balance+%s
                WHERE card=%s
                """,
                (
                    amount,
                    receiver
                )
            )

            sender_reference = add_transaction(
                c,
                session["card"],
                "Money Transfer Sent",
                amount
            )

            add_transaction(
                c,
                receiver,
                "Money Transfer Received",
                amount
            )

            conn.commit()

            sender_email = sender[2]

        except Exception as error:

            conn.rollback()

            print(
                "TRANSFER ERROR:",
                error
            )

            return "Money Transfer Failed"

        finally:

            c.close()
            conn.close()

        send_email_receipt(
            sender_email,
            "ATM Transfer Receipt",
            (
                "Dear User,\n\n"
                "Money Transfer Successful.\n\n"
                f"Reference ID: {sender_reference}\n"
                f"Receiver: {mask_card(receiver)}\n"
                f"Amount: INR {amount:.2f}\n"
                f"Balance: INR {new_sender_balance:.2f}\n"
                f"Date: {get_current_datetime()}"
            )
        )

        return redirect("/receipt")

    return render_template(
        "transfer.html"
    )


# ==================================================
# FIXED DEPOSIT
# ==================================================

@app.route(
    "/fixed_deposit",
    methods=["GET", "POST"]
)
def fixed_deposit():

    if not login_required():
        return redirect("/")

    maturity_amount = None

    if request.method == "POST":

        try:

            amount = float(
                request.form.get(
                    "amount",
                    0
                )
            )

            months = int(
                request.form.get(
                    "months",
                    0
                )
            )

        except (ValueError, TypeError):

            return (
                "Invalid Amount or Months"
            )

        if amount <= 0 or months <= 0:

            return (
                "Amount and Months must "
                "be greater than 0"
            )

        interest_rate = 7.5

        maturity_amount = (
            amount
            + (
                amount
                * interest_rate
                * (months / 12)
                / 100
            )
        )

        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                SELECT balance
                FROM users
                WHERE card=%s
                FOR UPDATE
                """,
                (session["card"],)
            )

            user = c.fetchone()

            if not user:

                conn.rollback()

                return "User Not Found"

            if float(user[0]) < amount:

                conn.rollback()

                return "Insufficient Balance"

            c.execute(
                """
                UPDATE users
                SET balance=balance-%s
                WHERE card=%s
                """,
                (
                    amount,
                    session["card"]
                )
            )

            c.execute(
                """
                INSERT INTO fixed_deposits(
                    card,
                    amount,
                    months,
                    interest_rate,
                    maturity_amount,
                    created_at
                )
                VALUES(
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    session["card"],
                    amount,
                    months,
                    interest_rate,
                    maturity_amount,
                    get_current_datetime()
                )
            )

            add_transaction(
                c,
                session["card"],
                "Fixed Deposit",
                amount
            )

            conn.commit()

        except Exception as error:

            conn.rollback()

            print(
                "FIXED DEPOSIT ERROR:",
                error
            )

            return "Fixed Deposit Failed"

        finally:

            c.close()
            conn.close()

    return render_template(
        "fixed_deposit.html",
        maturity_amount=maturity_amount
    )


# ==================================================
# FIXED DEPOSIT LIST
# ==================================================

@app.route("/fixed_deposit_list")
def fixed_deposit_list():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                id,
                amount,
                months,
                interest_rate,
                maturity_amount,
                created_at
            FROM fixed_deposits
            WHERE card=%s
            ORDER BY id DESC
            """,
            (session["card"],)
        )

        deposits = c.fetchall()

        return render_template(
            "fixed_deposit_list.html",
            deposits=deposits
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# INTEREST CALCULATOR
# ==================================================

@app.route(
    "/interest_calculator",
    methods=["GET", "POST"]
)
def interest_calculator():

    interest = None
    total_amount = None

    if request.method == "POST":

        try:

            principal = float(
                request.form.get(
                    "principal",
                    0
                )
            )

            rate = float(
                request.form.get(
                    "rate",
                    0
                )
            )

            time = float(
                request.form.get(
                    "time",
                    0
                )
            )

        except (ValueError, TypeError):

            return "Invalid Input"

        if (
            principal < 0
            or rate < 0
            or time < 0
        ):

            return (
                "Values cannot be negative"
            )

        interest = (
            principal
            * rate
            * time
        ) / 100

        total_amount = (
            principal + interest
        )

    return render_template(
        "interest_calculator.html",
        interest=interest,
        total_amount=total_amount
    )

# ==================================================
# PART 2 COMPLETE
# PART 3 CONTINUES FROM TRANSACTION HISTORY
# ==================================================

# ==================================================
# TRANSACTION HISTORY
# ==================================================

@app.route("/history")
def history():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                reference_id,
                type,
                amount,
                date
            FROM transactions
            WHERE card=%s
            ORDER BY id DESC
            """,
            (session["card"],)
        )

        data = c.fetchall()

        return render_template(
            "history.html",
            data=data
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# MINI STATEMENT
# ==================================================

@app.route("/mini_statement")
def mini_statement():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                reference_id,
                type,
                amount,
                date
            FROM transactions
            WHERE card=%s
            ORDER BY id DESC
            LIMIT 5
            """,
            (session["card"],)
        )

        data = c.fetchall()

        return render_template(
            "mini_statement.html",
            data=data
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# LATEST RECEIPT
# ==================================================

@app.route("/receipt")
def receipt():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                reference_id,
                type,
                amount,
                date
            FROM transactions
            WHERE card=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            (session["card"],)
        )

        transaction = c.fetchone()

        if not transaction:
            return "No Transaction Found"

        return render_template(
            "receipt.html",
            card=session["card"],
            masked_card=mask_card(
                session["card"]
            ),
            transaction=transaction
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# CHANGE PIN
# ==================================================

@app.route(
    "/change_pin",
    methods=["GET", "POST"]
)
def change_pin():

    if not login_required():
        return redirect("/")

    if request.method == "POST":

        old_pin = request.form.get(
            "old_pin",
            ""
        ).strip()

        new_pin = request.form.get(
            "new_pin",
            ""
        ).strip()

        confirm_pin = request.form.get(
            "confirm_pin",
            ""
        ).strip()

        if not all([
            old_pin,
            new_pin,
            confirm_pin
        ]):

            return "All Fields Are Required"

        if new_pin != confirm_pin:

            return (
                "New PIN and Confirm PIN "
                "do not match"
            )

        if (
            not new_pin.isdigit()
            or len(new_pin) < 4
        ):

            return (
                "New PIN must contain "
                "at least 4 digits"
            )

        if old_pin == new_pin:

            return (
                "New PIN cannot be same "
                "as Old PIN"
            )

        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                SELECT pin
                FROM users
                WHERE card=%s
                """,
                (session["card"],)
            )

            user = c.fetchone()

            if not user:
                return "User Not Found"

            if not check_password_hash(
                user[0],
                old_pin
            ):

                return "Old PIN Is Incorrect"

            c.execute(
                """
                UPDATE users
                SET
                    pin=%s,
                    failed_attempts=0
                WHERE card=%s
                """,
                (
                    generate_password_hash(
                        new_pin
                    ),
                    session["card"]
                )
            )

            conn.commit()

            return "PIN Changed Successfully"

        finally:

            c.close()
            conn.close()

    return render_template(
        "change_pin.html"
    )


# ==================================================
# ACCOUNT DETAILS
# ==================================================

@app.route("/account_details")
def account_details():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                name,
                email,
                card,
                balance,
                created_at,
                last_login
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        if not user:
            session.clear()
            return redirect("/")

        return render_template(
            "account_details.html",
            user=user
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# PROFILE
# ==================================================

@app.route("/profile")
def profile():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                card,
                name,
                email,
                balance,
                profile_pic
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        if not user:
            session.clear()
            return redirect("/")

        return render_template(
            "profile.html",
            user=user
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# EDIT PROFILE
# ==================================================

@app.route(
    "/edit_profile",
    methods=["GET", "POST"]
)
def edit_profile():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        if request.method == "POST":

            name = request.form.get(
                "name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip()

            if not name or not email:

                return (
                    "Name and Email are required"
                )

            file = request.files.get(
                "profile_pic"
            )

            if file and file.filename:

                if "." not in file.filename:

                    return "Invalid Image File"

                extension = (
                    file.filename
                    .rsplit(".", 1)[-1]
                    .lower()
                )

                allowed_extensions = {
                    "png",
                    "jpg",
                    "jpeg",
                    "webp"
                }

                if extension not in allowed_extensions:

                    return (
                        "Only PNG, JPG, JPEG "
                        "and WEBP images are allowed"
                    )

                safe_filename = secure_filename(
                    file.filename
                )

                filename = (
                    f"{session['card']}_"
                    f"{int(datetime.now().timestamp())}_"
                    f"{safe_filename}"
                )

                file.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        filename
                    )
                )

                c.execute(
                    """
                    UPDATE users
                    SET
                        name=%s,
                        email=%s,
                        profile_pic=%s
                    WHERE card=%s
                    """,
                    (
                        name,
                        email,
                        filename,
                        session["card"]
                    )
                )

            else:

                c.execute(
                    """
                    UPDATE users
                    SET
                        name=%s,
                        email=%s
                    WHERE card=%s
                    """,
                    (
                        name,
                        email,
                        session["card"]
                    )
                )

            conn.commit()

            return redirect("/profile")

        c.execute(
            """
            SELECT
                card,
                name,
                email,
                profile_pic
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        if not user:
            session.clear()
            return redirect("/")

        return render_template(
            "edit_profile.html",
            user=user
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# SEARCH TRANSACTION
# ==================================================

@app.route(
    "/search",
    methods=["GET", "POST"]
)
def search():

    if not login_required():
        return redirect("/")

    data = []

    if request.method == "POST":

        keyword = request.form.get(
            "keyword",
            ""
        ).strip()

        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                SELECT
                    reference_id,
                    type,
                    amount,
                    date
                FROM transactions
                WHERE card=%s
                AND (
                    type ILIKE %s
                    OR COALESCE(
                        reference_id,
                        ''
                    ) ILIKE %s
                )
                ORDER BY id DESC
                """,
                (
                    session["card"],
                    f"%{keyword}%",
                    f"%{keyword}%"
                )
            )

            data = c.fetchall()

        finally:

            c.close()
            conn.close()

    return render_template(
        "search.html",
        data=data
    )


# ==================================================
# FILTER TRANSACTIONS
# ==================================================

@app.route(
    "/filter_transactions",
    methods=["GET", "POST"]
)
def filter_transactions():

    if not login_required():
        return redirect("/")

    transactions = []

    if request.method == "POST":

        start_date = request.form.get(
            "start_date",
            ""
        ).strip()

        end_date = request.form.get(
            "end_date",
            ""
        ).strip()

        if not start_date or not end_date:

            return (
                "Start Date and End Date "
                "are required"
            )

        try:

            start = datetime.strptime(
                start_date,
                "%Y-%m-%d"
            ).date()

            end = datetime.strptime(
                end_date,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            return "Invalid Date"

        if start > end:

            return (
                "Start Date cannot be after "
                "End Date"
            )

        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                SELECT
                    reference_id,
                    type,
                    amount,
                    date
                FROM transactions
                WHERE card=%s
                ORDER BY id DESC
                """,
                (session["card"],)
            )

            data = c.fetchall()

        finally:

            c.close()
            conn.close()

        for transaction in data:

            try:

                transaction_date = (
                    datetime.strptime(
                        transaction[3],
                        "%d-%m-%Y %H:%M:%S"
                    ).date()
                )

                if (
                    start
                    <= transaction_date
                    <= end
                ):

                    transactions.append(
                        transaction
                    )

            except (
                ValueError,
                TypeError
            ):

                pass

    return render_template(
        "filter_transactions.html",
        transactions=transactions
    )


# ==================================================
# EXPORT CSV
# ==================================================

@app.route("/export_csv")
def export_csv():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT name, card
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        c.execute(
            """
            SELECT
                reference_id,
                type,
                amount,
                date
            FROM transactions
            WHERE card=%s
            ORDER BY id DESC
            """,
            (session["card"],)
        )

        data = c.fetchall()

    finally:

        c.close()
        conn.close()

    if not user:
        return "User Not Found"

    filename = os.path.join(
        REPORTS_FOLDER,
        (
            "transaction_report_"
            f"{session['card']}.csv"
        )
    )

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            "ATM Management System"
        ])

        writer.writerow([
            "Name",
            user[0]
        ])

        writer.writerow([
            "Card Number",
            mask_card(user[1])
        ])

        writer.writerow([
            "Generated On",
            get_current_datetime()
        ])

        writer.writerow([])

        writer.writerow([
            "Reference ID",
            "Transaction Type",
            "Amount",
            "Date"
        ])

        writer.writerows(data)

    return send_file(
        filename,
        as_attachment=True,
        download_name=(
            "ATM_Transaction_Report.csv"
        )
    )


# ==================================================
# PDF REPORT
# ==================================================

@app.route("/download_pdf")
def download_pdf():

    if not login_required():
        return redirect("/")

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT name, card
            FROM users
            WHERE card=%s
            """,
            (session["card"],)
        )

        user = c.fetchone()

        c.execute(
            """
            SELECT
                reference_id,
                type,
                amount,
                date
            FROM transactions
            WHERE card=%s
            ORDER BY id DESC
            """,
            (session["card"],)
        )

        data = c.fetchall()

    finally:

        c.close()
        conn.close()

    if not user:
        return "User Not Found"

    filename = os.path.join(
        REPORTS_FOLDER,
        (
            "transaction_report_"
            f"{session['card']}.pdf"
        )
    )

    pdf = canvas.Canvas(filename)

    pdf.setTitle(
        "ATM Transaction Report"
    )

    pdf.setFont(
        "Helvetica-Bold",
        18
    )

    pdf.drawString(
        150,
        810,
        "ATM Management System"
    )

    pdf.setFont(
        "Helvetica-Bold",
        14
    )

    pdf.drawString(
        190,
        785,
        "Transaction Report"
    )

    pdf.line(
        40,
        770,
        550,
        770
    )

    pdf.setFont(
        "Helvetica",
        11
    )

    pdf.drawString(
        50,
        745,
        f"Name: {user[0]}"
    )

    pdf.drawString(
        50,
        725,
        (
            "Card Number: "
            f"{mask_card(user[1])}"
        )
    )

    pdf.drawString(
        50,
        705,
        (
            "Generated On: "
            f"{get_current_datetime()}"
        )
    )

    pdf.drawString(
        50,
        685,
        (
            "Total Transactions: "
            f"{len(data)}"
        )
    )

    y = 645

    pdf.setFont(
        "Helvetica-Bold",
        8
    )

    pdf.drawString(
        35,
        y,
        "No."
    )

    pdf.drawString(
        60,
        y,
        "Reference ID"
    )

    pdf.drawString(
        175,
        y,
        "Transaction Type"
    )

    pdf.drawString(
        330,
        y,
        "Amount"
    )

    pdf.drawString(
        410,
        y,
        "Date & Time"
    )

    y -= 22

    pdf.setFont(
        "Helvetica",
        8
    )

    for index, transaction in enumerate(
        data,
        start=1
    ):

        if y < 60:

            pdf.showPage()

            y = 790

            pdf.setFont(
                "Helvetica",
                8
            )

        reference_id = (
            transaction[0]
            or "-"
        )

        pdf.drawString(
            35,
            y,
            str(index)
        )

        pdf.drawString(
            60,
            y,
            str(reference_id)[:18]
        )

        pdf.drawString(
            175,
            y,
            str(transaction[1])[:24]
        )

        pdf.drawString(
            330,
            y,
            (
                "INR "
                f"{float(transaction[2]):.2f}"
            )
        )

        pdf.drawString(
            410,
            y,
            str(transaction[3])[:22]
        )

        y -= 18

    pdf.save()

    return send_file(
        filename,
        as_attachment=True,
        download_name=(
            "ATM_Transaction_Report.pdf"
        )
    )

# ==================================================
# PART 3 COMPLETE
# PART 4 CONTINUES FROM ADMIN LOGIN
# ==================================================

# ==================================================
# SECURE ADMIN LOGIN
# ==================================================

@app.route(
    "/admin_login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        import hmac

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        ).strip()

        username_valid = hmac.compare_digest(
            username,
            ADMIN_USERNAME
        )

        password_valid = hmac.compare_digest(
            password,
            ADMIN_PASSWORD
        )

        if (
            username_valid
            and password_valid
        ):

            session.clear()

            session["admin"] = True

            session.permanent = True

            return redirect(
                "/admin_dashboard"
            )

        return (
            "Invalid Admin Username "
            "or Password"
        )

    return render_template(
        "admin_login.html"
    )


# ==================================================
# ADMIN LOGOUT
# ==================================================

@app.route("/admin_logout")
def admin_logout():

    session.clear()

    return redirect(
        "/admin_login"
    )


# ==================================================
# ADMIN DASHBOARD
# ==================================================

@app.route("/admin_dashboard")
def admin_dashboard():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT COUNT(*)
            FROM users
            """
        )

        total_users = c.fetchone()[0]


        c.execute(
            """
            SELECT COUNT(*)
            FROM users
            WHERE is_locked=1
            """
        )

        locked_users = c.fetchone()[0]


        c.execute(
            """
            SELECT COALESCE(
                SUM(balance),
                0
            )
            FROM users
            """
        )

        total_balance = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type='Deposit'
            """
        )

        total_deposits = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type IN (
                'Withdraw',
                'Fast Cash Withdraw'
            )
            """
        )

        total_withdrawals = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type='Money Transfer Sent'
            """
        )

        total_transfers = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            """
        )

        total_transactions = (
            c.fetchone()[0]
        )


        c.execute(
            """
            SELECT COUNT(*)
            FROM fixed_deposits
            """
        )

        total_fixed_deposits = (
            c.fetchone()[0]
        )


        return render_template(
            "admin_dashboard.html",
            total_users=total_users,
            locked_users=locked_users,
            total_balance=total_balance,
            total_deposits=total_deposits,
            total_withdrawals=total_withdrawals,
            total_transfers=total_transfers,
            total_transactions=total_transactions,
            total_fixed_deposits=total_fixed_deposits
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# ADMIN CHART PAGE
# ==================================================

@app.route("/admin_chart")
def admin_chart():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    return render_template(
        "admin_chart.html"
    )


# ==================================================
# ADMIN CHART IMAGE
# ==================================================

@app.route("/admin_chart_image")
def admin_chart_image():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    import matplotlib

    matplotlib.use("Agg")

    import matplotlib.pyplot as plt


    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type='Deposit'
            """
        )

        total_deposit = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type IN (
                'Withdraw',
                'Fast Cash Withdraw'
            )
            """
        )

        total_withdraw = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type='Money Transfer Sent'
            """
        )

        total_transfer = float(
            c.fetchone()[0] or 0
        )


        c.execute(
            """
            SELECT COALESCE(
                SUM(amount),
                0
            )
            FROM transactions
            WHERE type='Fixed Deposit'
            """
        )

        total_fd = float(
            c.fetchone()[0] or 0
        )

    finally:

        c.close()
        conn.close()


    chart_path = os.path.join(
        RUNTIME_DIR,
        "admin_chart.png"
    )


    plt.figure(
        figsize=(8, 5)
    )

    plt.bar(
        [
            "Deposit",
            "Withdraw",
            "Transfer",
            "Fixed Deposit"
        ],
        [
            total_deposit,
            total_withdraw,
            total_transfer,
            total_fd
        ]
    )

    plt.title(
        "ATM Transaction Statistics"
    )

    plt.xlabel(
        "Transaction Type"
    )

    plt.ylabel(
        "Total Amount"
    )

    plt.tight_layout()

    plt.savefig(
        chart_path
    )

    plt.close()


    return send_file(
        chart_path,
        mimetype="image/png"
    )


# ==================================================
# ALL USERS
# ==================================================

@app.route("/all_users")
def all_users():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                id,
                name,
                email,
                card,
                balance,
                is_locked
            FROM users
            ORDER BY id DESC
            """
        )

        users = c.fetchall()

        return render_template(
            "all_users.html",
            users=users
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# ADD USER
# ==================================================

@app.route(
    "/add_user",
    methods=["GET", "POST"]
)
def add_user():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        card = request.form.get(
            "card",
            ""
        ).strip()

        pin = request.form.get(
            "pin",
            ""
        ).strip()

        try:

            balance = float(
                request.form.get(
                    "balance",
                    0
                )
            )

        except (
            ValueError,
            TypeError
        ):

            return "Invalid Balance"


        if not all([
            name,
            email,
            card,
            pin
        ]):

            return (
                "All Required Fields "
                "Must Be Filled"
            )


        if not card.isdigit():

            return (
                "Card Number must contain "
                "only numbers"
            )


        if (
            not pin.isdigit()
            or len(pin) < 4
        ):

            return (
                "PIN must contain at least "
                "4 digits"
            )


        if balance < 0:

            return (
                "Balance cannot be negative"
            )


        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                INSERT INTO users(
                    name,
                    email,
                    card,
                    pin,
                    balance,
                    created_at
                )
                VALUES(
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    email,
                    card,
                    generate_password_hash(
                        pin
                    ),
                    balance,
                    get_current_datetime()
                )
            )

            conn.commit()


        except UniqueViolation:

            conn.rollback()

            return (
                "Card Number Already Exists"
            )


        finally:

            c.close()
            conn.close()


        return redirect(
            "/all_users"
        )


    return render_template(
        "add_user.html"
    )


# ==================================================
# EDIT USER
# ==================================================

@app.route(
    "/edit_user/<int:id>",
    methods=["GET", "POST"]
)
def edit_user(id):

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        if request.method == "POST":

            name = request.form.get(
                "name",
                ""
            ).strip()

            email = request.form.get(
                "email",
                ""
            ).strip()

            card = request.form.get(
                "card",
                ""
            ).strip()

            pin = request.form.get(
                "pin",
                ""
            ).strip()


            try:

                balance = float(
                    request.form.get(
                        "balance",
                        0
                    )
                )

            except (
                ValueError,
                TypeError
            ):

                return "Invalid Balance"


            if not all([
                name,
                email,
                card
            ]):

                return (
                    "Name, Email and Card "
                    "are required"
                )


            if not card.isdigit():

                return (
                    "Card Number must contain "
                    "only numbers"
                )


            if balance < 0:

                return (
                    "Balance cannot be negative"
                )


            if pin and (
                not pin.isdigit()
                or len(pin) < 4
            ):

                return (
                    "PIN must contain at least "
                    "4 digits"
                )


            c.execute(
                """
                SELECT card
                FROM users
                WHERE id=%s
                FOR UPDATE
                """,
                (id,)
            )

            old_user = c.fetchone()


            if not old_user:

                return "User Not Found"


            old_card = old_user[0]


            if pin:

                c.execute(
                    """
                    UPDATE users
                    SET
                        name=%s,
                        email=%s,
                        card=%s,
                        pin=%s,
                        balance=%s
                    WHERE id=%s
                    """,
                    (
                        name,
                        email,
                        card,
                        generate_password_hash(
                            pin
                        ),
                        balance,
                        id
                    )
                )

            else:

                c.execute(
                    """
                    UPDATE users
                    SET
                        name=%s,
                        email=%s,
                        card=%s,
                        balance=%s
                    WHERE id=%s
                    """,
                    (
                        name,
                        email,
                        card,
                        balance,
                        id
                    )
                )


            if old_card != card:

                c.execute(
                    """
                    UPDATE transactions
                    SET card=%s
                    WHERE card=%s
                    """,
                    (
                        card,
                        old_card
                    )
                )


                c.execute(
                    """
                    UPDATE fixed_deposits
                    SET card=%s
                    WHERE card=%s
                    """,
                    (
                        card,
                        old_card
                    )
                )


                c.execute(
                    """
                    UPDATE withdrawal_limits
                    SET card=%s
                    WHERE card=%s
                    """,
                    (
                        card,
                        old_card
                    )
                )


            conn.commit()


            return redirect(
                "/all_users"
            )


        c.execute(
            """
            SELECT *
            FROM users
            WHERE id=%s
            """,
            (id,)
        )

        user = c.fetchone()


        if not user:

            return "User Not Found"


        return render_template(
            "edit_user.html",
            user=user
        )


    except UniqueViolation:

        conn.rollback()

        return (
            "Card Number Already Exists"
        )


    except Exception as error:

        conn.rollback()

        print(
            "EDIT USER ERROR:",
            error
        )

        return "User Update Failed"


    finally:

        c.close()
        conn.close()


# ==================================================
# DELETE USER
# ==================================================

@app.route("/delete_user/<int:id>")
def delete_user(id):

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT card
            FROM users
            WHERE id=%s
            FOR UPDATE
            """,
            (id,)
        )

        user = c.fetchone()


        if not user:

            return "User Not Found"


        card = user[0]


        c.execute(
            """
            DELETE FROM withdrawal_limits
            WHERE card=%s
            """,
            (card,)
        )


        c.execute(
            """
            DELETE FROM fixed_deposits
            WHERE card=%s
            """,
            (card,)
        )


        c.execute(
            """
            DELETE FROM transactions
            WHERE card=%s
            """,
            (card,)
        )


        c.execute(
            """
            DELETE FROM users
            WHERE id=%s
            """,
            (id,)
        )


        conn.commit()


        return redirect(
            "/all_users"
        )


    except Exception as error:

        conn.rollback()

        print(
            "DELETE USER ERROR:",
            error
        )

        return "User Delete Failed"


    finally:

        c.close()
        conn.close()


# ==================================================
# UNLOCK USER
# ==================================================

@app.route("/unlock_user/<int:id>")
def unlock_user(id):

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            UPDATE users
            SET
                failed_attempts=0,
                is_locked=0
            WHERE id=%s
            """,
            (id,)
        )

        conn.commit()

        return redirect(
            "/all_users"
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# LOCK USER
# ==================================================

@app.route("/lock_user/<int:id>")
def lock_user(id):

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            UPDATE users
            SET is_locked=1
            WHERE id=%s
            """,
            (id,)
        )

        conn.commit()

        return redirect(
            "/all_users"
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# SEARCH USER
# ==================================================

@app.route(
    "/search_user",
    methods=["GET", "POST"]
)
def search_user():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    users = []

    if request.method == "POST":

        keyword = request.form.get(
            "keyword",
            ""
        ).strip()

        conn = get_conn()
        c = conn.cursor()

        try:

            c.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    card,
                    balance,
                    is_locked
                FROM users
                WHERE name ILIKE %s
                OR card ILIKE %s
                OR COALESCE(
                    email,
                    ''
                ) ILIKE %s
                ORDER BY id DESC
                """,
                (
                    f"%{keyword}%",
                    f"%{keyword}%",
                    f"%{keyword}%"
                )
            )

            users = c.fetchall()

        finally:

            c.close()
            conn.close()


    return render_template(
        "search_user.html",
        users=users
    )


# ==================================================
# ADMIN ALL TRANSACTIONS
# ==================================================

@app.route("/admin_transactions")
def admin_transactions():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                reference_id,
                card,
                type,
                amount,
                date
            FROM transactions
            ORDER BY id DESC
            """
        )

        transactions = c.fetchall()

        return render_template(
            "admin_transactions.html",
            transactions=transactions
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# ADMIN FIXED DEPOSITS
# ==================================================

@app.route("/admin_fixed_deposits")
def admin_fixed_deposits():

    if not admin_required():

        return redirect(
            "/admin_login"
        )

    conn = get_conn()
    c = conn.cursor()

    try:

        c.execute(
            """
            SELECT
                id,
                card,
                amount,
                months,
                interest_rate,
                maturity_amount,
                created_at
            FROM fixed_deposits
            ORDER BY id DESC
            """
        )

        deposits = c.fetchall()

        return render_template(
            "admin_fixed_deposits.html",
            deposits=deposits
        )

    finally:

        c.close()
        conn.close()


# ==================================================
# USER LOGOUT
# ==================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# ==================================================
# ERROR HANDLER - FILE TOO LARGE
# ==================================================

@app.errorhandler(413)
def file_too_large(error):

    return (
        "Uploaded File Is Too Large. "
        "Maximum File Size Is 2 MB.",
        413
    )


# ==================================================
# ERROR HANDLER - PAGE NOT FOUND
# ==================================================

@app.errorhandler(404)
def page_not_found(error):

    return (
        "404 - Page Not Found",
        404
    )


# ==================================================
# START APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )