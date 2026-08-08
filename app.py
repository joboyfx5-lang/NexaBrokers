import os
import secrets
import smtplib

from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, timezone
from functools import wraps
from email.mime.text import MIMEText

from flask import (
    Flask,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    render_template,
)

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import CheckConstraint
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)


# ============================================================
# APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "SECRET_KEY must be configured in Render environment variables."
    )


database_url = os.environ.get(
    "DATABASE_URL",
    "sqlite:///nexabrokers.db",
)

if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1,
    )


app.config["SQLALCHEMY_DATABASE_URI"] = database_url

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get(
        "COOKIE_SECURE",
        "true",
    ).lower()
    == "true"
)


db = SQLAlchemy(app)


# ============================================================
# DEVELOPMENT VERIFICATION MODE
# ============================================================

DEV_VERIFICATION_MODE = (
    os.environ.get(
        "DEV_VERIFICATION_MODE",
        "false",
    ).lower()
    == "true"
)


# ============================================================
# MODELS
# ============================================================

class User(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False,
    )

    email = db.Column(
        db.String(255),
        unique=True,
        nullable=False,
    )

    password_hash = db.Column(
        db.String(255),
        nullable=True,
    )

    balance = db.Column(
        db.Numeric(18, 2),
        nullable=False,
        default=0,
    )

    is_verified = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    verification_code_hash = db.Column(
        db.String(255),
        nullable=True,
    )

    verification_expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    is_admin = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    transactions = db.relationship(
        "Transaction",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan",
    )


class Transaction(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    type = db.Column(
        db.String(20),
        nullable=False,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    crypto_currency = db.Column(
        db.String(20),
        nullable=False,
        default="USDT",
    )

    txid = db.Column(
        db.String(255),
        nullable=True,
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
    )

    admin_note = db.Column(
        db.Text,
        nullable=True,
    )

    reviewed_by = db.Column(
        db.Integer,
        nullable=True,
    )

    reviewed_at = db.Column(
        db.DateTime(timezone=True),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="positive_transaction_amount",
        ),
    )


class BalanceAdjustment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    admin_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    amount = db.Column(
        db.Numeric(18, 2),
        nullable=False,
    )

    direction = db.Column(
        db.String(10),
        nullable=False,
    )

    reason = db.Column(
        db.String(500),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# ============================================================
# HELPERS
# ============================================================

def money(value):

    try:

        amount = Decimal(
            str(value)
        ).quantize(
            Decimal("0.01")
        )

        if amount <= 0:
            raise ValueError

        return amount

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):

        raise ValueError(
            "Amount must be a positive number."
        )


def valid_email(email):

    if not email or len(email) > 255:
        return False

    if "@" not in email:
        return False

    local, domain = email.rsplit(
        "@",
        1,
    )

    return bool(
        local
        and domain
        and "." in domain
    )


def current_user():

    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return None

    return db.session.get(
        User,
        user_id,
    )


def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        user = current_user()

        if (
            not user
            or not user.is_active
        ):

            return jsonify({
                "error":
                    "Authentication required."
            }), 401

        if not user.is_verified:

            return jsonify({
                "error":
                    "Account verification required."
            }), 403

        return fn(
            *args,
            **kwargs,
        )

    return wrapper


def admin_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        user = current_user()

        if (
            not user
            or not user.is_active
            or not user.is_admin
        ):

            return jsonify({
                "error":
                    "Administrator access required."
            }), 403

        return fn(
            *args,
            **kwargs,
        )

    return wrapper


def issue_otp(user):

    code = (
        f"{secrets.randbelow(1_000_000):06d}"
    )

    user.verification_code_hash = (
        generate_password_hash(
            code
        )
    )

    user.verification_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=10)
    )

    return code


def send_otp_email(
    to_email,
    code,
):

    sender = os.environ.get(
        "MAIL_USERNAME"
    )

    password = os.environ.get(
        "MAIL_PASSWORD"
    )

    if not sender or not password:

        app.logger.warning(
            "MAIL_USERNAME/MAIL_PASSWORD are not configured."
        )

        return False

    message = MIMEText(
        (
            "Your NexaBrokers verification "
            f"code is {code}. "
            "It expires in 10 minutes."
        ),
        "plain",
    )

    message["Subject"] = (
        "NexaBrokers Verification Code"
    )

    message["From"] = sender

    message["To"] = to_email

    try:

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465,
            timeout=10,
        ) as smtp:

            smtp.login(
                sender,
                password,
            )

            smtp.sendmail(
                sender,
                to_email,
                message.as_string(),
            )

        return True

    except Exception:

        app.logger.exception(
            "SMTP error"
        )

        return False


def json_user(user):

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "balance": str(user.balance),
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
    }


def request_data():

    return (
        request.form
        if request.form
        else (
            request.get_json(
                silent=True
            )
            or {}
        )
    )


def normalize_datetime(value):

    if value is None:
        return None

    if value.tzinfo is None:

        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


# ============================================================
# PUBLIC PAGES
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


@app.route("/signup-page")
def signup_page():

    return render_template(
        "signup.html"
    )


@app.route("/login-page")
def login_page():

    return render_template(
        "login.html"
    )


@app.route("/verify-page")
def verify_page():

    return render_template(
        "verify.html"
    )


@app.route("/dashboard-page")
@login_required
def dashboard_page():

    user = current_user()

    if user.is_admin:

        return redirect(
            url_for("admin_page")
        )

    return render_template(
        "dashboard.html"
    )


@app.route("/admin-page")
def admin_page():

    return render_template(
        "admin.html"
    )


# ============================================================
# SIGNUP
# ============================================================

@app.route(
    "/signup",
    methods=["POST"],
)
def signup():

    data = request_data()

    username = (
        str(
            data.get("username")
            or ""
        )
        .strip()
    )

    email = (
        str(
            data.get("email")
            or ""
        )
        .strip()
        .lower()
    )

    password = str(
        data.get("password")
        or ""
    )


    if len(username) < 3:

        return jsonify({
            "error":
                "Username must contain at least 3 characters."
        }), 400


    if len(password) < 8:

        return jsonify({
            "error":
                "Password must contain at least 8 characters."
        }), 400


    if not valid_email(email):

        return jsonify({
            "error":
                "Please enter a valid email address."
        }), 400


    existing_user = User.query.filter(
        (
            User.email == email
        )
        |
        (
            User.username == username
        )
    ).first()


    if existing_user:

        return jsonify({
            "error":
                "Email or username already exists."
        }), 409


    user = User(
        username=username,
        email=email,
        password_hash=generate_password_hash(
            password
        ),
        is_verified=False,
        balance=Decimal("0.00"),
    )


    code = issue_otp(
        user
    )


    db.session.add(
        user
    )

    db.session.commit()


    sent = send_otp_email(
        email,
        code,
    )


    response = {
        "message":
            "Account created. Verification code generated."
    }


    if DEV_VERIFICATION_MODE:

        response[
            "development_code"
        ] = code

        app.logger.info(
            "DEVELOPMENT VERIFICATION CODE for %s: %s",
            email,
            code,
        )


    elif not sent:

        app.logger.error(
            "Verification email could not be sent to %s.",
            email,
        )


    return jsonify(
        response
    ), 201


# ============================================================
# LOGIN REQUEST
# ============================================================

@app.route(
    "/login-request",
    methods=["POST"],
)
def login_request():

    data = request_data()

    email = (
        str(
            data.get("email")
            or ""
        )
        .strip()
        .lower()
    )

    password = str(
        data.get("password")
        or ""
    )


    user = User.query.filter_by(
        email=email
    ).first()


    if (
        not user
        or not user.password_hash
        or not check_password_hash(
            user.password_hash,
            password,
        )
    ):

        return jsonify({
            "error":
                "Invalid email or password."
        }), 401


    if not user.is_active:

        return jsonify({
            "error":
                "Account is disabled."
        }), 403


    code = issue_otp(
        user
    )


    db.session.commit()


    sent = send_otp_email(
        user.email,
        code,
    )


    response = {
        "message":
            "Verification code generated."
    }


    if DEV_VERIFICATION_MODE:

        response[
            "development_code"
        ] = code

        app.logger.info(
            "DEVELOPMENT LOGIN CODE for %s: %s",
            user.email,
            code,
        )

    elif not sent:

        app.logger.error(
            "Login verification email could not be sent to %s.",
            user.email,
        )


    return jsonify(
        response
    )


# ============================================================
# VERIFY CODE
# ============================================================

@app.route(
    "/verify-code",
    methods=["POST"],
)
def verify_code():

    data = request_data()

    email = (
        str(
            data.get("email")
            or ""
        )
        .strip()
        .lower()
    )

    code = (
        str(
            data.get("code")
            or ""
        )
        .strip()
    )


    user = User.query.filter_by(
        email=email
    ).first()


    if (
        not user
        or not user.verification_code_hash
    ):

        return jsonify({
            "error":
                "Invalid verification code."
        }), 400


    expires = (
        normalize_datetime(
            user.verification_expires_at
        )
    )


    now = datetime.now(
        timezone.utc
    )


    if (
        not expires
        or expires < now
    ):

        return jsonify({
            "error":
                "Invalid or expired verification code."
        }), 400


    if not check_password_hash(
        user.verification_code_hash,
        code,
    ):

        return jsonify({
            "error":
                "Invalid or expired verification code."
        }), 400


    user.is_verified = True

    user.verification_code_hash = None

    user.verification_expires_at = None


    session.clear()

    session["user_id"] = user.id

    session.permanent = True


    db.session.commit()


    return jsonify({

        "message":
            "Verification successful. Login successful.",

        "user":
            json_user(user),

    })


# ============================================================
# LOGOUT
# ============================================================

@app.route(
    "/logout",
    methods=["POST"],
)
def logout():

    session.clear()

    return jsonify({
        "message":
            "Logged out."
    })


# ============================================================
# TEMPORARY RESET PASSWORD
# ============================================================

@app.route(
    "/temporary-reset-password",
    methods=["POST"],
)
def temporary_reset_password():

    data = request_data()

    reset_secret = str(
        data.get("reset_secret")
        or ""
    )

    expected_secret = os.environ.get(
        "RESET_SECRET"
    )


    if not expected_secret:

        return jsonify({
            "error":
                "RESET_SECRET is not configured."
        }), 503


    if not secrets.compare_digest(
        reset_secret,
        expected_secret,
    ):

        return jsonify({
            "error":
                "Invalid reset secret."
        }), 403


    username = (
        str(
            data.get("username")
            or ""
        )
        .strip()
    )

    new_password = str(
        data.get("new_password")
        or ""
    )


    if not username:

        return jsonify({
            "error":
                "Username is required."
        }), 400


    if len(new_password) < 8:

        return jsonify({
            "error":
                "Password must contain at least 8 characters."
        }), 400


    user = User.query.filter_by(
        username=username
    ).first()


    if not user:

        return jsonify({
            "error":
                "User not found."
        }), 404


    user.password_hash = (
        generate_password_hash(
            new_password
        )
    )


    db.session.commit()


    return jsonify({
        "message":
            "Password reset successfully."
    })


# ============================================================
# USER DASHBOARD API
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()


    transactions = (
        Transaction.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Transaction.created_at.desc()
        )
        .all()
    )


    return jsonify({

        "message":
            "Dashboard API",

        "user":
            json_user(user),

        "transactions": [

            {
                "id": t.id,
                "type": t.type,
                "amount": str(t.amount),
                "currency": t.crypto_currency,
                "txid": t.txid,
                "status": t.status,
                "admin_note": t.admin_note,
                "created_at":
                    (
                        t.created_at.isoformat()
                        if t.created_at
                        else None
                    ),
            }

            for t in transactions

        ]

    })


# ============================================================
# WALLET REQUEST
# ============================================================

@app.route(
    "/wallet/request",
    methods=["POST"],
)
@login_required
def wallet_request():

    data = request_data()


    tx_type = (
        str(
            data.get("type")
            or ""
        )
        .strip()
        .title()
    )


    currency = (
        str(
            data.get(
                "crypto_currency"
            )
            or "USDT"
        )
        .strip()
        .upper()
    )


    txid = (
        str(
            data.get("txid")
            or ""
        )
        .strip()
        [:255]
    )


    try:

        amount = money(
            data.get("amount")
        )

    except ValueError as exc:

        return jsonify({
            "error":
                str(exc)
        }), 400


    if tx_type not in {
        "Deposit",
        "Withdrawal",
    }:

        return jsonify({
            "error":
                "Type must be Deposit or Withdrawal."
        }), 400


    if currency not in {
        "USDT",
        "BTC",
        "ETH",
        "USD",
    }:

        return jsonify({
            "error":
                "Unsupported currency."
        }), 400


    user = current_user()


    if (
        tx_type == "Withdrawal"
        and amount > Decimal(
            str(user.balance)
        )
    ):

        return jsonify({
            "error":
                "Insufficient available balance."
        }), 400


    tx = Transaction(

        user_id=user.id,

        type=tx_type,

        amount=amount,

        crypto_currency=currency,

        txid=txid,

        status="Pending",

    )


    db.session.add(
        tx
    )

    db.session.commit()


    return jsonify({

        "message":
            f"{tx_type} request submitted.",

        "transaction_id":
            tx.id,

        "status":
            tx.status,

    }), 201


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["POST"],
)
def admin_login():

    data = request_data()


    username = (
        str(
            data.get("username")
            or ""
        )
        .strip()
    )


    password = str(
        data.get("password")
        or ""
    )


    admin = User.query.filter_by(
        username=username,
        is_admin=True,
    ).first()


    if (
        not admin
        or not admin.is_active
        or not admin.password_hash
    ):

        return jsonify({
            "error":
                "Invalid admin credentials."
        }), 401


    if not check_password_hash(
        admin.password_hash,
        password,
    ):

        return jsonify({
            "error":
                "Invalid admin credentials."
        }), 401


    session.clear()

    session["user_id"] = admin.id

    session.permanent = True


    return jsonify({

        "message":
            "Admin login successful.",

        "user":
            json_user(admin),

    })


# ============================================================
# ADMIN OVERVIEW
# ============================================================

@app.route("/admin/overview")
@admin_required
def admin_overview():

    return jsonify({

        "users":
            User.query.count(),

        "active_users":
            User.query.filter_by(
                is_active=True
            ).count(),

        "pending_transactions":
            Transaction.query.filter_by(
                status="Pending"
            ).count(),

        "approved_transactions":
            Transaction.query.filter_by(
                status="Approved"
            ).count(),

        "rejected_transactions":
            Transaction.query.filter_by(
                status="Rejected"
            ).count(),

    })


# ============================================================
# ADMIN USERS
# ============================================================

@app.route("/admin/users")
@admin_required
def admin_users():

    users = (
        User.query
        .order_by(
            User.created_at.desc()
        )
        .all()
    )


    return jsonify([

        {
            **json_user(user),

            "created_at":
                (
                    user.created_at.isoformat()
                    if user.created_at
                    else None
                ),
        }

        for user in users

    ])


@app.route(
    "/admin/users/<int:user_id>",
    methods=["GET"],
)
@admin_required
def admin_user_detail(
    user_id
):

    user = db.session.get(
        User,
        user_id
    )


    if not user:

        return jsonify({
            "error":
                "User not found."
        }), 404


    transactions = (
        Transaction.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Transaction.created_at.desc()
        )
        .all()
    )


    return jsonify({

        "user":
            json_user(user),

        "transactions": [

            {
                "id": t.id,
                "type": t.type,
                "amount": str(t.amount),
                "currency": t.crypto_currency,
                "txid": t.txid,
                "status": t.status,
                "admin_note": t.admin_note,
                "created_at":
                    (
                        t.created_at.isoformat()
                        if t.created_at
                        else None
                    ),
            }

            for t in transactions

        ]

    })


@app.route(
    "/admin/users/<int:user_id>/status",
    methods=["POST"],
)
@admin_required
def admin_user_status(
    user_id
):

    data = request_data()


    user = db.session.get(
        User,
        user_id
    )


    if not user:

        return jsonify({
            "error":
                "User not found."
        }), 404


    active = data.get(
        "active"
    )


    if str(active).lower() not in {
        "true",
        "false",
        "1",
        "0",
    }:

        return jsonify({
            "error":
                "active must be true or false."
        }), 400


    user.is_active = (
        str(active).lower()
        in {
            "true",
            "1",
        }
    )


    db.session.commit()


    return jsonify({

        "message":
            "User status updated.",

        "user":
            json_user(user),

    })


# ============================================================
# ADMIN BALANCE ADJUSTMENT
# ============================================================

@app.route(
    "/admin/users/<int:user_id>/balance",
    methods=["POST"],
)
@admin_required
def admin_balance_adjustment(
    user_id
):

    data = request_data()


    user = db.session.get(
        User,
        user_id
    )

    admin = current_user()


    if not user:

        return jsonify({
            "error":
                "User not found."
        }), 404


    direction = (
        str(
            data.get("direction")
            or ""
        )
        .lower()
    )


    reason = (
        str(
            data.get("reason")
            or ""
        )
        .strip()
    )


    if direction not in {
        "add",
        "remove",
    }:

        return jsonify({
            "error":
                "direction must be add or remove."
        }), 400


    if not reason:

        return jsonify({
            "error":
                "A reason is required."
        }), 400


    try:

        amount = money(
            data.get("amount")
        )

    except ValueError as exc:

        return jsonify({
            "error":
                str(exc)
        }), 400


    old_balance = Decimal(
        str(user.balance)
    )


    if (
        direction == "remove"
        and amount > old_balance
    ):

        return jsonify({
            "error":
                "Cannot remove more than the user's balance."
        }), 400


    if direction == "add":

        new_balance = (
            old_balance
            + amount
        )

    else:

        new_balance = (
            old_balance
            - amount
        )


    user.balance = new_balance


    adjustment = BalanceAdjustment(

        user_id=user.id,

        admin_id=admin.id,

        amount=amount,

        direction=direction,

        reason=reason,

    )


    db.session.add(
        adjustment
    )

    db.session.commit()


    return jsonify({

        "message":
            "Balance updated.",

        "old_balance":
            str(old_balance),

        "new_balance":
            str(new_balance),

    })


# ============================================================
# ADMIN TRANSACTIONS
# ============================================================

@app.route("/admin/transactions")
@admin_required
def admin_transactions():

    transactions = (
        Transaction.query
        .order_by(
            Transaction.created_at.desc()
        )
        .all()
    )


    return jsonify([

        {
            "id": t.id,
            "user_id": t.user_id,
            "username": t.user.username,
            "email": t.user.email,
            "type": t.type,
            "amount": str(t.amount),
            "currency": t.crypto_currency,
            "txid": t.txid,
            "status": t.status,
            "admin_note": t.admin_note,
            "created_at":
                (
                    t.created_at.isoformat()
                    if t.created_at
                    else None
                ),
        }

        for t in transactions

    ])


@app.route(
    "/admin/transactions/<int:tx_id>/review",
    methods=["POST"],
)
@admin_required
def review_transaction(
    tx_id
):

    data = request_data()


    action = (
        str(
            data.get("action")
            or ""
        )
        .lower()
    )


    note = (
        str(
            data.get("note")
            or ""
        )
        .strip()
        [:500]
    )


    if action not in {
        "approve",
        "reject",
    }:

        return jsonify({
            "error":
                "action must be approve or reject."
        }), 400


    tx = db.session.get(
        Transaction,
        tx_id
    )


    if not tx:

        return jsonify({
            "error":
                "Transaction not found."
        }), 404


    if tx.status != "Pending":

        return jsonify({
            "error":
                "Only pending transactions can be reviewed."
        }), 409


    user = db.session.get(
        User,
        tx.user_id
    )


    admin = current_user()


    if action == "approve":

        if tx.type == "Deposit":

            user.balance = (
                Decimal(
                    str(user.balance)
                )
                +
                Decimal(
                    str(tx.amount)
                )
            )


        elif tx.type == "Withdrawal":

            current_balance = Decimal(
                str(user.balance)
            )

            amount = Decimal(
                str(tx.amount)
            )


            if amount > current_balance:

                return jsonify({
                    "error":
                        "Cannot approve withdrawal: insufficient balance."
                }), 400


            user.balance = (
                current_balance
                - amount
            )


        tx.status = "Approved"


    else:

        tx.status = "Rejected"


    tx.admin_note = (
        note
        or None
    )


    tx.reviewed_by = admin.id


    tx.reviewed_at = (
        datetime.now(
            timezone.utc
        )
    )


    db.session.commit()


    return jsonify({

        "message":
            f"Transaction {tx.status.lower()}.",

        "transaction_id":
            tx.id,

        "status":
            tx.status,

        "user_balance":
            str(user.balance),

    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    response = {
        "status":
            "ok"
    }


    if DEV_VERIFICATION_MODE:

        response[
            "verification_mode"
        ] = "development"


    return jsonify(
        response
    )


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

with app.app_context():

    db.create_all()


# ============================================================
# SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )
