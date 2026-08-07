import os
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-broker-key')

# Configure Database
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Active')
    verification_code = db.Column(db.String(6), nullable=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade="all, delete-orphan")

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.drop_all()
    db.create_all()

# --- SMTP EMAIL SENDER HELPER ---
def send_email_code(to_email, code):
    sender_email = os.environ.get('MAIL_USERNAME')
    sender_password = os.environ.get('MAIL_PASSWORD')
    
    # If credentials are not set up yet, fallback for safety
    if not sender_email or not sender_password:
        print(f"[SMTP WARNING]: MAIL_USERNAME or MAIL_PASSWORD not set. Code for {to_email}: {code}")
        return False

    message = MIMEMultipart("alternative")
    message["Subject"] = "Your NexaBrokers Verification Code"
    message["From"] = sender_email
    message["To"] = to_email
    
    html = f"""
    <div style="font-family: 'Inter', system-ui, sans-serif; background: #0f172a; color: white; padding: 30px; border-radius: 16px; max-width: 400px; margin: auto;">
        <h2 style="color: #38bdf8; margin-top: 0;">NexaBrokers Security</h2>
        <p style="color: #94a3b8; font-size: 0.95rem;">Use the secure verification code below to access your trading portfolio:</p>
        <div style="background: rgba(30, 41, 59, 0.8); border: 1px solid #334155; padding: 16px; text-align: center; border-radius: 12px; margin: 20px 0;">
            <span style="color: #34d399; font-size: 2rem; font-weight: 800; letter-spacing: 6px;">{code}</span>
        </div>
        <p style="font-size: 0.8rem; color: #64748b;">If you did not request this login, please ignore this email safely.</p>
    </div>
    """
    message.attach(MIMEText(html, "html"))
    
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        return True
    except Exception as e:
        print("SMTP Error Dispatching Email:", e)
        return False

# --- AUTH & USER ROUTES ---

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid payload"}), 400
        
    email = data.get('email')
    username = data.get('username')

    if not email or not username:
        return jsonify({"error": "Email and username required"}), 400

    existing = User.query.filter((User.email == email) | (User.username == username)).first()
    if existing:
        return jsonify({"error": "Email or username already exists"}), 400

    code = str(random.randint(100000, 999999))
    new_user = User(email=email, username=username, verification_code=code, balance=0.0)
    db.session.add(new_user)
    db.session.commit()

    # Send code via SMTP email
    send_email_code(email, code)

    return jsonify({"message": "Verification code sent to your email address."}), 200

@app.route('/login-request', methods=['POST'])
def login_request():
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid payload"}), 400
        
    user = User.query.filter_by(email=data.get('email')).first()
    if not user:
        return jsonify({"error": "Email not found"}), 404

    code = str(random.randint(100000, 999999))
    user.verification_code = code
    db.session.commit()

    # Send code via SMTP email
    send_email_code(user.email, code)

    return jsonify({"message": "Verification code sent to your email address."}), 200

@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.get_json()
    if not data: return jsonify({"error": "Invalid payload"}), 400
        
    user = User.query.filter_by(email=data.get('email')).first()
    if not user or user.verification_code != data.get('code'):
        return jsonify({"error": "Invalid code or email"}), 400

    if user.status == 'Suspended':
        return jsonify({"error": "Account is suspended. Contact support."}), 403

    session['username'] = user.username
    return jsonify({"message": "Login successful", "username": user.username}), 200

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('auth_page'))

# --- ADMIN API ROUTES ---

@app.route('/api/users', methods=['GET'])
def get_all_users():
    users = User.query.all()
    return jsonify([{
        "username": u.username, 
        "email": u.email, 
        "balance": u.balance, 
        "status": u.status
    } for u in users])

@app.route('/api/update-balance', methods=['POST'])
def update_balance():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if not user: return jsonify({"error": "User not found"}), 404
    
    amount = float(data['amount'])
    if data['action'] == 'add': user.balance += amount
    elif data['action'] == 'remove': 
        if user.balance < amount: return jsonify({"error": "Insufficient funds"}), 400
        user.balance -= amount
    
    db.session.add(Transaction(user_id=user.id, action=data['action'], amount=amount))
    db.session.commit()
    return jsonify({"new_balance": user.balance})

@app.route('/api/toggle-status/<username>', methods=['POST'])
def toggle_status(username):
    user = User.query.filter_by(username=username).first()
    if user:
        user.status = 'Suspended' if user.status == 'Active' else 'Active'
        db.session.commit()
    return jsonify({"status": user.status})

# --- FRONTEND PAGES WITH LIVELY UI ---

AUTH_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaBrokers — Secure Portal</title>
    <style>
        body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background: radial-gradient(circle at top, #1e1b4b, #0f172a); color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); padding: 32px; border-radius: 20px; width: 100%; max-width: 420px; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5); box-sizing: border-box; }
        h2 { text-align: center; color: #38bdf8; margin-top: 0; font-weight: 800; letter-spacing: -0.5px; }
        p.subtitle { text-align: center; color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }
        label { font-size: 0.8rem; font-weight: 600; color: #cbd5e1; text-transform: uppercase; letter-spacing: 0.5px; }
        input { width: 100%; padding: 12px 16px; margin: 6px 0 16px 0; background: rgba(15, 23, 42, 0.8); border: 1px solid #334155; color: white; border-radius: 10px; box-sizing: border-box; font-size: 0.95rem; transition: border-color 0.2s; }
        input:focus { outline: none; border-color: #38bdf8; box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.15); }
        button { width: 100%; padding: 14px; background: linear-gradient(135deg, #0284c7, #2563eb); color: white; border: none; border-radius: 10px; font-weight: bold; font-size: 1rem; cursor: pointer; transition: transform 0.1s, opacity 0.2s; margin-top: 5px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3); }
        button:hover { opacity: 0.95; transform: translateY(-1px); }
        .toggle { text-align: center; margin-top: 20px; font-size: 0.9rem; color: #38bdf8; cursor: pointer; font-weight: 500; }
        .toggle:hover { text-decoration: underline; }
        #infoAlert { background: rgba(6, 78, 59, 0.8); border: 1px solid #059669; color: #34d399; padding: 12px; border-radius: 10px; margin-top: 15px; font-size: 0.85rem; display: none; text-align: center; }
    </style>
</head>
<body>
    <div class="card">
        <h2 id="formTitle">NexaBrokers</h2>
        <p class="subtitle" id="formSubtitle">Access your trading portfolio</p>
        
        <div id="step1">
            <label>Email Address</label>
            <input type="email" id="email" placeholder="name@example.com">
            
            <div id="usernameBox" style="display:none;">
                <label>Username</label>
                <input type="text" id="username" placeholder="Choose a unique handle">
            </div>
            
            <button id="mainBtn" onclick="handleAuthAction()">Continue with Email</button>
        </div>

        <div id="step2" style="display:none;">
            <p style="font-size: 0.9rem; color: #cbd5e1; text-align: center;">We've emailed your verification code. Check your inbox (and spam folder)!</p>
            <label>6-Digit Token Code</label>
            <input type="text" id="code" placeholder="• • • • • •" style="text-align: center; font-size: 1.2rem; letter-spacing: 4px;">
            <button onclick="verifyCode()">Verify & Launch Dashboard</button>
        </div>

        <div id="infoAlert"></div>
        <div class="toggle" onclick="switchMode()" id="switchText">Don't have an account? Sign up</div>
    </div>

<script>
    let isSignup = false;
    function switchMode() {
        isSignup = !isSignup;
        document.getElementById('formTitle').innerText = isSignup ? 'Create Account' : 'NexaBrokers';
        document.getElementById('formSubtitle').innerText = isSignup ? 'Start your brokerage journey' : 'Access your trading portfolio';
        document.getElementById('usernameBox').style.display = isSignup ? 'block' : 'none';
        document.getElementById('mainBtn').innerText = isSignup ? 'Create Free Account' : 'Continue with Email';
        document.getElementById('switchText').innerText = isSignup ? 'Already registered? Log in' : "Don't have an account? Sign up";
    }

    async function handleAuthAction() {
        const email = document.getElementById('email').value;
        const username = document.getElementById('username').value;
        const endpoint = isSignup ? '/signup' : '/login-request';
        
        const res = await fetch(endpoint, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email, username })
        });
        const data = await res.json();
        if(res.ok) {
            document.getElementById('step1').style.display = 'none';
            document.getElementById('step2').style.display = 'block';
            const alertDiv = document.getElementById('infoAlert');
            alertDiv.style.display = 'block';
            alertDiv.innerText = data.message;
        } else {
            alert(data.error);
        }
    }

    async function verifyCode() {
        const email = document.getElementById('email').value;
        const code = document.getElementById('code').value;
        const res = await fetch('/verify-code', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ email, code })
        });
        const data = await res.json();
        if(res.ok) {
            window.location.href = '/dashboard';
        } else {
            alert(data.error);
        }
    }
</script>
</body>
</html>
"""

USER_DASH_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard — NexaBrokers</title>
    <style>
        body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background: radial-gradient(circle at top, #0f172a, #020617); color: #f8fafc; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; }
        .dashboard-container { width: 100%; max-width: 440px; padding: 20px; box-sizing: border-box; }
        .card { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); padding: 32px; border-radius: 24px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); text-align: center; position: relative; overflow: hidden; }
        .card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 4px; background: linear-gradient(90deg, #38bdf8, #34d399); }
        .avatar { width: 64px; height: 64px; background: linear-gradient(135deg, #0284c7, #38bdf8); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.6rem; font-weight: bold; margin: 0 auto 16px auto; box-shadow: 0 10px 15px -3px rgba(2, 132, 199, 0.4); }
        .username { font-size: 1.3rem; font-weight: 700; color: #fff; margin-bottom: 4px; }
        .email { font-size: 0.85rem; color: #94a3b8; margin-bottom: 24px; }
        .balance-box { background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255, 255, 255, 0.05); padding: 20px; border-radius: 16px; margin-bottom: 20px; }
        .balance-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; color: #94a3b8; font-weight: 600; }
        .bal { font-size: 2.5rem; color: #34d399; font-weight: 800; margin-top: 8px; letter-spacing: -1px; text-shadow: 0 0 20px rgba(52, 211, 153, 0.2); }
        .status-badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(52, 211, 153, 0.1); color: #34d399; padding: 6px 14px; border-radius: 20px; font-size: 0.85rem; font-weight: 600; margin-bottom: 24px; border: 1px solid rgba(52, 211, 153, 0.2); }
        .status-dot { width: 8px; height: 8px; background: #34d399; border-radius: 50%; box-shadow: 0 0 8px #34d399; }
        .logout-btn { display: block; width: 100%; padding: 12px; background: rgba(239, 68, 68, 0.1); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 12px; text-decoration: none; font-weight: 600; transition: background 0.2s; }
        .logout-btn:hover { background: rgba(239, 68, 68, 0.2); }
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div class="card">
            <div class="avatar">{{ user.username[0]|upper }}</div>
            <div class="username">@{{ user.username }}</div>
            <div class="email">{{ user.email }}</div>
            
            <div class="status-badge">
                <div class="status-dot"></div>
                Account {{ user.status }}
            </div>

            <div class="balance-box">
                <div class="balance-title">Portfolio Balance</div>
                <div class="bal">${{ "%.2f"|format(user.balance) }}</div>
            </div>

            <a href="/logout" class="logout-btn">Sign Out</a>
        </div>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Command Center — NexaBrokers</title>
    <style>
        body { font-family: 'Inter', system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 30px; }
        h2 { color: #38bdf8; font-weight: 800; }
        .table-container { background: #1e293b; border-radius: 16px; border: 1px solid #334155; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.3); margin-top: 20px; }
        table { width: 100%; border-collapse: collapse; text-align: left; }
        th { background: rgba(15, 23, 42, 0.6); padding: 16px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; color: #94a3b8; border-bottom: 1px solid #334155; }
        td { padding: 16px; border-bottom: 1px solid #334155; font-size: 0.95rem; }
        tr:last-child td { border-bottom: none; }
        .active { color: #34d399; font-weight: 600; }
        .suspended { color: #f87171; font-weight: 600; }
        button { cursor: pointer; padding: 8px 12px; border-radius: 8px; border: none; font-weight: 600; font-size: 0.85rem; margin-right: 4px; transition: opacity 0.2s; }
        button:hover { opacity: 0.85; }
        .btn-add { background: #059669; color: white; }
        .btn-remove { background: #dc2626; color: white; }
        .btn-toggle { background: #475569; color: white; }
    </style>
</head>
<body>
    <h2>⚡ NexaBrokers Master Command Center</h2>
    <div class="table-container">
        <table>
            <thead><tr><th>Client Handle</th><th>Email Address</th><th>Balance</th><th>Status</th><th>Quick Actions</th></tr></thead>
            <tbody id="userTable"></tbody>
        </table>
    </div>
    <script>
        async function loadUsers() {
            const res = await fetch('/api/users');
            const users = await res.json();
            document.getElementById('userTable').innerHTML = users.map(u => `
                <tr>
                    <td><b>@${u.username}</b></td>
                    <td style="color:#94a3b8;">${u.email}</td>
                    <td style="font-weight:700; color:#34d399;">$${u.balance.toFixed(2)}</td>
                    <td class="${u.status.toLowerCase()}">${u.status}</td>
                    <td>
                        <button class="btn-add" onclick="adjust('${u.username}', 'add', 100)">+ $100</button>
                        <button class="btn-remove" onclick="adjust('${u.username}', 'remove', 50)">- $50</button>
                        <button class="btn-toggle" onclick="toggle('${u.username}')">Toggle Status</button>
                    </td>
                </tr>
            `).join('');
        }
        async function adjust(username, action, amount) {
            await fetch('/api/update-balance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ username, action, amount })
            });
            loadUsers();
        }
        async function toggle(username) {
            await fetch(`/api/toggle-status/${username}`, {method: 'POST'});
            loadUsers();
        }
        loadUsers();
    </script>
</body>
</html>
"""

@app.route('/')
def auth_page(): return render_template_string(AUTH_HTML)

@app.route('/dashboard')
def user_dashboard():
    username = session.get('username')
    if not username: return redirect(url_for('auth_page'))
    user = User.query.filter_by(username=username).first()
    if not user: return redirect(url_for('auth_page'))
    return render_template_string(USER_DASH_HTML, user=user)

@app.route('/admin')
def admin_panel(): return render_template_string(ADMIN_HTML)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
