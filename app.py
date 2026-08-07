import os
import random
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
    status = db.Column(db.String(20), default='Active') # 'Active' or 'Suspended'
    verification_code = db.Column(db.String(6), nullable=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade="all, delete-orphan")

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(20), nullable=False) # 'add' or 'remove'
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# --- AUTH & USER ROUTES ---

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid payload"}), 400
        
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

    return jsonify({"message": "Verification code generated", "dev_code": code}), 200

@app.route('/login-request', methods=['POST'])
def login_request():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid payload"}), 400
        
    user = User.query.filter_by(email=data.get('email')).first()
    if not user:
        return jsonify({"error": "Email not found"}), 404

    code = str(random.randint(100000, 999999))
    user.verification_code = code
    db.session.commit()

    return jsonify({"message": "Code sent", "dev_code": code}), 200

@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid payload"}), 400
        
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

# --- FRONTEND PAGES ---

AUTH_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaBrokers Portal</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 24px; border-radius: 12px; width: 100%; max-width: 400px; box-shadow: 0 10px 15px rgba(0,0,0,0.3); }
        input { width: 100%; padding: 10px; margin: 8px 0; background: #0f172a; border: 1px solid #334155; color: white; border-radius: 6px; box-sizing: border-box; }
        button { width: 100%; padding: 10px; background: #0284c7; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; margin-top: 10px; }
        .toggle { text-align: center; margin-top: 15px; font-size: 0.85rem; color: #38bdf8; cursor: pointer; }
        #devAlert { background: #064e3b; color: #34d399; padding: 10px; border-radius: 6px; margin-top: 10px; font-size: 0.85rem; display: none; word-break: break-all; }
    </style>
</head>
<body>
    <div class="card">
        <h2 id="formTitle" style="text-align:center; color:#38bdf8;">Login Portal</h2>
        
        <div id="step1">
            <input type="email" id="email" placeholder="Enter your email">
            <input type="text" id="username" placeholder="Choose Username (Signup only)" style="display:none;">
            <button id="mainBtn" onclick="handleAuthAction()">Send Code</button>
        </div>

        <div id="step2" style="display:none;">
            <p style="font-size: 0.85rem; color: #94a3b8;">Enter the 6-digit code sent to your email:</p>
            <input type="text" id="code" placeholder="123456">
            <button onclick="verifyCode()">Verify & Login</button>
        </div>

        <div id="devAlert"></div>
        <div class="toggle" onclick="switchMode()" id="switchText">Need an account? Sign up</div>
    </div>

<script>
    let isSignup = false;
    function switchMode() {
        isSignup = !isSignup;
        document.getElementById('formTitle').innerText = isSignup ? 'Create Account' : 'Login Portal';
        document.getElementById('username').style.display = isSignup ? 'block' : 'none';
        document.getElementById('mainBtn').innerText = isSignup ? 'Register & Get Code' : 'Send Code';
        document.getElementById('switchText').innerText = isSignup ? 'Already have an account? Login' : 'Need an account? Sign up';
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
            const devDiv = document.getElementById('devAlert');
            devDiv.style.display = 'block';
            devDiv.innerText = `[DEV TEST CODE]: ${data.dev_code}`;
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
    <title>Dashboard</title>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: white; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: #1e293b; padding: 24px; border-radius: 12px; width: 100%; max-width: 400px; text-align: center; box-shadow: 0 10px 15px rgba(0,0,0,0.3); }
        .bal { font-size: 2rem; color: #34d399; font-weight: bold; margin: 15px 0; }
        a { color: #f87171; text-decoration: none; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Welcome, @{{ user.username }}</h2>
        <div style="font-size: 0.85rem; color:#94a3b8;">{{ user.email }}</div>
        <div class="bal">${{ "%.2f"|format(user.balance) }}</div>
        <div style="margin: 15px 0; color: #38bdf8; font-weight:bold;">Status: {{ user.status }}</div>
        <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
        <a href="/logout">Logout</a>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <style>
        body { font-family: sans-serif; background: #0f172a; color: white; padding: 20px; }
        table { width: 100%; border-collapse: collapse; background: #1e293b; margin-top: 15px; }
        th, td { padding: 12px; border: 1px solid #334155; text-align: left; }
        .active { color: #34d399; }
        .suspended { color: #f87171; }
        button { cursor: pointer; padding: 6px 12px; border-radius: 4px; border: none; background: #0284c7; color: white; margin-right: 4px; }
    </style>
</head>
<body>
    <h2>NexaBrokers Master Admin Control</h2>
    <table>
        <thead><tr><th>Username</th><th>Email</th><th>Balance</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody id="userTable"></tbody>
    </table>
    <script>
        async function loadUsers() {
            const res = await fetch('/api/users');
            const users = await res.json();
            document.getElementById('userTable').innerHTML = users.map(u => `
                <tr>
                    <td><b>${u.username}</b></td>
                    <td>${u.email}</td>
                    <td>$${u.balance.toFixed(2)}</td>
                    <td class="${u.status.toLowerCase()}">${u.status}</td>
                    <td>
                        <button onclick="adjust('${u.username}', 'add', 100)">+ $100</button>
                        <button onclick="adjust('${u.username}', 'remove', 50)" style="background:#7f1d1d;">- $50</button>
                        <button onclick="toggle('${u.username}')" style="background:#475569;">Toggle Status</button>
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
