import os
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-change-this')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///nexabrokers.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'Deposit' or 'Withdrawal'
    amount = db.Column(db.Float, nullable=False)
    crypto_currency = db.Column(db.String(20), nullable=True) # e.g., 'USDT', 'BTC'
    txid = db.Column(db.String(255), nullable=True) # Blockchain transaction hash for verification
    status = db.Column(db.String(20), default='Pending') # 'Pending', 'Approved', 'Rejected'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- HELPER FUNCTION: EMAIL DISPATCHER ---

def send_email_code(to_email, code):
    sender_email = os.environ.get('MAIL_USERNAME')
    sender_password = os.environ.get('MAIL_PASSWORD')
    
    if not sender_email or not sender_password:
        print("SMTP Credentials not configured in environment variables.")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = "Your NexaBrokers Verification Code"
    message["From"] = sender_email
    message["To"] = to_email
    
    html = f"""
    <div style="font-family: sans-serif; background: #0f172a; color: white; padding: 20px; border-radius: 10px;">
        <h2 style="color: #38bdf8;">NexaBrokers Security</h2>
        <p>Your verification code is:</p>
        <h1 style="color: #34d399; letter-spacing: 4px;">{code}</h1>
        <p style="font-size: 0.8rem; color: #94a3b8;">If you didn't request this, please ignore this email.</p>
    </div>
    """
    message.attach(MIMEText(html, "html"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        return True
    except Exception as e:
        print("SMTP Error:", e)
        return False

# --- ROUTES: FRONTEND VIEWS & LANDING PAGE ---

@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NexaBrokers | Professional Online Trading & Investments</title>
        <style>
            body {
                margin: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #0b0f19;
                color: #ffffff;
                display: flex;
                flex-direction: column;
                min-height: 100vh;
                justify-content: space-between;
            }
            .container {
                max-width: 1000px;
                margin: 0 auto;
                padding: 60px 20px;
                text-align: center;
            }
            h1 {
                font-size: 3rem;
                color: #38bdf8;
                margin-bottom: 15px;
            }
            p.subtitle {
                font-size: 1.2rem;
                color: #94a3b8;
                margin-bottom: 40px;
            }
            .btn-group {
                display: flex;
                gap: 20px;
                justify-content: center;
                margin-bottom: 50px;
            }
            .btn {
                padding: 12px 30px;
                font-size: 1rem;
                font-weight: bold;
                border-radius: 6px;
                text-decoration: none;
                transition: background 0.3s ease;
            }
            .btn-primary {
                background-color: #38bdf8;
                color: #0b0f19;
            }
            .btn-primary:hover {
                background-color: #0ea5e9;
            }
            .btn-secondary {
                background-color: transparent;
                border: 2px solid #38bdf8;
                color: #38bdf8;
            }
            .btn-secondary:hover {
                background-color: rgba(56, 189, 248, 0.1);
            }
            footer {
                background-color: #07090e;
                padding: 20px;
                text-align: center;
                font-size: 0.85rem;
                color: #64748b;
                border-top: 1px solid #1e293b;
            }
            footer a {
                color: #38bdf8;
                text-decoration: none;
                margin: 0 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>NexaBrokers</h1>
            <p class="subtitle">Institutional-Grade Multi-Asset Trading & Secure Crypto Investment Platform</p>
            
            <div class="btn-group">
                <a href="/login-page" class="btn btn-primary">Login to Account</a>
                <a href="/signup-page" class="btn btn-secondary">Create Account</a>
            </div>
        </div>

        <footer>
            <p>© 2026 NexaBrokers International Ltd. All rights reserved.</p>
            <div>
                <a href="/terms">Terms of Service</a> | 
                <a href="/privacy">Privacy Policy</a> | 
                <a href="/compliance">Regulatory Disclosure</a>
            </div>
        </footer>
    </body>
    </html>
    """

@app.route('/terms')
def terms():
    return """
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333;">
        <h1>Terms of Service</h1>
        <p>Welcome to NexaBrokers. By using our platform, you agree to our standard terms and conditions regarding financial trading and account usage.</p>
        <a href="/">Back to Home</a>
    </div>
    """

@app.route('/privacy')
def privacy():
    return """
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333;">
        <h1>Privacy Policy</h1>
        <p>Your privacy is important to us. We securely encrypt and protect all user data, credentials, and transaction logs.</p>
        <a href="/">Back to Home</a>
    </div>
    """

@app.route('/compliance')
def compliance():
    return """
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; color: #333;">
        <h1>Regulatory Disclosure & Risk Warning</h1>
        <p>Trading financial assets and cryptocurrencies involves high risks. Client funds are handled in secure environments, but you should never trade with capital you cannot afford to lose.</p>
        <a href="/">Back to Home</a>
    </div>
    """

# --- ROUTES: AUTH & USER ---

@app.route('/signup', methods=['POST'])
def signup():
    data = request.form if request.form else (request.get_json() or {})
    email = data.get('email')
    username = data.get('username')

    if not email or not username:
        return jsonify({"error": "Email and username are required"}), 400
        
    existing = User.query.filter((User.email == email) | (User.username == username)).first()
    if existing:
        return jsonify({"error": "Email or username already exists"}), 400

    code = str(random.randint(100000, 999999))
    new_user = User(email=email, username=username, verification_code=code)
    db.session.add(new_user)
    db.session.commit()

    send_email_code(email, code)
    
    return jsonify({"message": "Verification code sent successfully!"})

@app.route('/login-request', methods=['POST'])
def login_request():
    data = request.form if request.form else (request.get_json() or {})
    email = data.get('email')
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "Email not found"}), 404

    code = str(random.randint(100000, 999999))
    user.verification_code = code
    db.session.commit()

    send_email_code(user.email, code)
    
    return jsonify({"message": "Verification code sent to your email!"})

@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.form if request.form else (request.get_json() or {})
    email = data.get('email')
    code = data.get('code')

    user = User.query.filter_by(email=email).first()
    if not user or user.verification_code != code:
        return jsonify({"error": "Invalid verification code"}), 400

    user.is_verified = True
    user.verification_code = None
    db.session.commit()

    session['user_id'] = user.id
    return jsonify({"message": "Login successful!"})

# --- ROUTES: WALLET & CRYPTO TRANSACTIONS ---

@app.route('/wallet/request', methods=['POST'])
def wallet_request():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.form if request.form else (request.get_json() or {})
    tx_type = data.get('type') # 'Deposit' or 'Withdrawal'
    amount = float(data.get('amount', 0))
    crypto_currency = data.get('crypto_currency', 'USDT')
    txid = data.get('txid', '')
    
    if amount <= 0 or tx_type not in ['Deposit', 'Withdrawal']:
        return jsonify({"error": "Invalid transaction data"}), 400
        
    new_tx = Transaction(
        user_id=session['user_id'], 
        type=tx_type, 
        amount=amount, 
        crypto_currency=crypto_currency,
        txid=txid
    )
    db.session.add(new_tx)
    db.session.commit()
    
    return jsonify({"message": f"{crypto_currency} {tx_type} request of ${amount} submitted successfully. It will be processed after confirmation."})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
