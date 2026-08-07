import os
import requests
from flask import Flask, render_template_string, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'nexabrokers-secret-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nexabrokers.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    balance = db.Column(db.Float, default=10000.0)
    is_admin = db.Column(db.Boolean, default=False)
    trades = db.relationship('Trade', backref='user', lazy=True)

class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    trade_type = db.Column(db.String(4), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_live_prices():
    try:
        res = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd', timeout=5)
        data = res.json()
        return {
            'BTC': data.get('bitcoin', {}).get('usd', 60000.0),
            'ETH': data.get('ethereum', {}).get('usd', 3000.0),
            'SOL': data.get('solana', {}).get('usd', 150.0)
        }
    except Exception:
        return {'BTC': 65000.0, 'ETH': 3500.0, 'SOL': 140.0}

HTML_HEADER = """
<!DOCTYPE html>
<html>
<head>
    <title>NexaBrokers | Web Platform</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { background-color: #0b0e14; color: #e1e6ed; font-family: system-ui, -apple-system, sans-serif; }
        .card { background-color: #151a23; border: 1px solid #232a36; color: #fff; }
        .btn-primary { background-color: #0066ff; border: none; }
        .btn-success { background-color: #00c076; border: none; }
        .btn-danger { background-color: #ff3b30; border: none; }
    </style>
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark px-3 mb-4 border-bottom border-secondary">
  <a class="navbar-brand fw-bold text-primary" href="#">NEXA<span class="text-white">BROKERS</span></a>
  <div class="ms-auto">
    {% if current_user.is_authenticated %}
      <span class="me-3 text-light">User: <strong>{{ current_user.username }}</strong></span>
      {% if current_user.is_admin %}
        <a href="/admin" class="btn btn-sm btn-warning me-2">Admin Panel</a>
      {% endif %}
      <a href="/logout" class="btn btn-sm btn-outline-light">Logout</a>
    {% else %}
      <a href="/login" class="btn btn-sm btn-outline-light me-2">Login</a>
      <a href="/register" class="btn btn-sm btn-primary">Register</a>
    {% endif %}
  </div>
</nav>
<div class="container-fluid px-4">
"""

HTML_FOOTER = """
</div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    prices = get_live_prices()
    user_trades = Trade.query.filter_by(user_id=current_user.id).all()
    
    html = HTML_HEADER + """
    <div class="row">
        <!-- Interactive TradingView Chart -->
        <div class="col-lg-8 mb-4">
            <div class="card p-3">
                <h5 class="mb-3">Live Market Chart (BTC/USD)</h5>
                <div class="tradingview-widget-container" style="height:450px;width:100%;">
                  <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_1&symbol=BINANCE%3ABTCUSDT&interval=D&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=f1f3f6&studies=[]&theme=dark&style=1&timezone=Etc%2FUTC" style="width: 100%; height: 100%; border: none;"></iframe>
                </div>
            </div>
        </div>

        <!-- Execution & Account Info -->
        <div class="col-lg-4 mb-4">
            <div class="card p-3 mb-3">
                <h5>Account Balance</h5>
                <h2 class="text-success">${{ "%.2f"|format(current_user.balance) }}</h2>
                <p class="text-muted small">Virtual Trading Capital</p>
            </div>

            <div class="card p-3 mb-3">
                <h5>Execute Order</h5>
                <form action="/trade" method="POST">
                    <div class="mb-3">
                        <label class="form-label">Symbol</label>
                        <select name="symbol" class="form-select bg-dark text-white border-secondary">
                            <option value="BTC">BTC/USD (${{ prices['BTC'] }})</option>
                            <option value="ETH">ETH/USD (${{ prices['ETH'] }})</option>
                            <option value="SOL">SOL/USD (${{ prices['SOL'] }})</option>
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Trade Amount ($)</label>
                        <input type="number" step="0.01" name="amount" class="form-control bg-dark text-white border-secondary" required>
                    </div>
                    <div class="d-flex gap-2">
                        <button type="submit" name="type" value="BUY" class="btn btn-success w-50">BUY</button>
                        <button type="submit" name="type" value="SELL" class="btn btn-danger w-50">SELL</button>
                    </div>
                </form>
            </div>

            <div class="card p-3">
                <h5>Recent Trades</h5>
                <ul class="list-group list-group-flush">
                    {% for t in trades %}
                        <li class="list-group-item bg-dark text-white border-secondary d-flex justify-content-between">
                            <span><strong class="{{ 'text-success' if t.trade_type == 'BUY' else 'text-danger' }}">{{ t.trade_type }}</strong> {{ t.symbol }}</span>
                            <span>${{ "%.2f"|format(t.amount) }}</span>
                        </li>
                    {% else %}
                        <li class="list-group-item bg-dark text-muted">No trades opened.</li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER
    return render_template_string(html, prices=prices, trades=user_trades)

@app.route('/trade', methods=['POST'])
@login_required
def execute_trade():
    symbol = request.form.get('symbol')
    amount = float(request.form.get('amount', 0))
    trade_type = request.form.get('type')
    
    if amount <= 0 or (trade_type == 'BUY' and amount > current_user.balance):
        flash('Invalid trade execution amount or insufficient capital.', 'danger')
        return redirect(url_for('dashboard'))
    
    prices = get_live_prices()
    execution_price = prices.get(symbol, 1.0)
    
    if trade_type == 'BUY':
        current_user.balance -= amount
    else:
        current_user.balance += amount

    new_trade = Trade(symbol=symbol, trade_type=trade_type, amount=amount, price=execution_price, user_id=current_user.id)
    db.session.add(new_trade)
    db.session.commit()
    
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials entered.', 'danger')
        
    html = HTML_HEADER + """
    <div class="row justify-content-center">
        <div class="col-md-4">
            <div class="card p-4">
                <h4 class="mb-3 text-center">NexaBrokers Login</h4>
                <form method="POST">
                    <div class="mb-3">
                        <label>Username</label>
                        <input type="text" name="username" class="form-control bg-dark text-white border-secondary" required>
                    </div>
                    <div class="mb-3">
                        <label>Password</label>
                        <input type="password" name="password" class="form-control bg-dark text-white border-secondary" required>
                    </div>
                    <button class="btn btn-primary w-100" type="submit">Sign In</button>
                </form>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER
    return render_template_string(html)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username is taken.', 'danger')
            return redirect(url_for('register'))
            
        hashed_pw = generate_password_hash(password, method='scrypt')
        is_admin = User.query.count() == 0
        
        new_user = User(username=username, password=hashed_pw, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))

    html = HTML_HEADER + """
    <div class="row justify-content-center">
        <div class="col-md-4">
            <div class="card p-4">
                <h4 class="mb-3 text-center">Create Trading Account</h4>
                <form method="POST">
                    <div class="mb-3">
                        <label>Username</label>
                        <input type="text" name="username" class="form-control bg-dark text-white border-secondary" required>
                    </div>
                    <div class="mb-3">
                        <label>Password</label>
                        <input type="password" name="password" class="form-control bg-dark text-white border-secondary" required>
                    </div>
                    <button class="btn btn-primary w-100" type="submit">Register</button>
                </form>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER
    return render_template_string(html)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        return "Unauthorized Access", 403
    users = User.query.all()
    trades = Trade.query.all()
    
    html = HTML_HEADER + """
    <h3>Admin Management Console</h3>
    <div class="row mt-3">
        <div class="col-md-6 mb-3">
            <div class="card p-3">
                <h5>Registered Users ({{ users|length }})</h5>
                <ul class="list-group list-group-flush">
                    {% for u in users %}
                        <li class="list-group-item bg-dark text-white d-flex justify-content-between">
                            <span>{{ u.username }} {% if u.is_admin %}<span class="badge bg-warning text-dark">Admin</span>{% endif %}</span>
                            <span>Balance: ${{ "%.2f"|format(u.balance) }}</span>
                        </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
        <div class="col-md-6 mb-3">
            <div class="card p-3">
                <h5>All Network Executions ({{ trades|length }})</h5>
                <ul class="list-group list-group-flush">
                    {% for t in trades %}
                        <li class="list-group-item bg-dark text-white border-secondary small">
                            User #{{ t.user_id }} - {{ t.trade_type }} {{ t.symbol }} worth ${{ "%.2f"|format(t.amount) }}
                        </li>
                    {% endfor %}
                </ul>
            </div>
        </div>
    </div>
    """ + HTML_FOOTER
    return render_template_string(html, users=users, trades=trades)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
