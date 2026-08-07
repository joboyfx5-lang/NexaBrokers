import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configure Database (PostgreSQL URL from Render environment variables)
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///local.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Database Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)

# Create database tables automatically on startup
with app.app_context():
    db.create_all()

# Route 1: Create User
@app.route('/user/<username>', methods=['POST'])
def create_user(username):
    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({"error": "User already exists"}), 400
    
    new_user = User(username=username, balance=0.0)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": f"User {username} created successfully"}), 200

# Route 2: Get User Balance (GET) / Info
@app.route('/user/<username>', methods=['GET'])
def get_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"username": user.username, "balance": user.balance}), 200

# Route 3: Update Balance (Add or Remove Funds)
@app.route('/update-balance', methods=['POST'])
def update_balance():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    username = data.get('username')
    amount = data.get('amount')
    action = data.get('action') # 'add' or 'remove'

    if not username or amount is None or action not in ['add', 'remove']:
        return jsonify({"error": "Missing or invalid parameters"}), 400

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        amount = float(amount)
    except ValueError:
        return jsonify({"error": "Amount must be a number"}), 400

    if action == 'add':
        user.balance += amount
    elif action == 'remove':
        if user.balance < amount:
            return jsonify({"error": "Insufficient balance"}), 400
        user.balance -= amount

    db.session.commit()
    return jsonify({"message": "Balance updated successfully", "new_balance": user.balance}), 200

# Route 4: Admin Dashboard UI
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NexaBrokers Admin Panel</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; max-width: 500px; margin: auto; }
        .card { background: #1e293b; padding: 24px; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3); }
        h2 { text-align: center; color: #38bdf8; margin-top: 0; }
        label { display: block; margin: 12px 0 4px; font-weight: 600; font-size: 0.9rem; }
        input, select { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; }
        button { width: 100%; padding: 12px; margin-top: 20px; border: none; border-radius: 6px; background: #0284c7; color: white; font-weight: bold; cursor: pointer; }
        button:hover { background: #0369a1; }
        #result { margin-top: 15px; padding: 12px; border-radius: 6px; text-align: center; font-weight: bold; display: none; }
        .success { background: #064e3b; color: #34d399; }
        .error { background: #7f1d1d; color: #f87171; }
    </style>
</head>
<body>
    <div class="card">
        <h2>Admin Balance Manager</h2>
        
        <label>Username</label>
        <input type="text" id="username" placeholder="e.g. alex">
        
        <label>Action</label>
        <select id="action">
            <option value="add">Add Funds (+)</option>
            <option value="remove">Deduct Funds (-)</option>
        </select>
        
        <label>Amount</label>
        <input type="number" id="amount" placeholder="e.g. 100">
        
        <button onclick="updateBalance()">Update Balance</button>
        
        <div id="result"></div>
    </div>

    <script>
        async function updateBalance() {
            const username = document.getElementById('username').value.trim();
            const action = document.getElementById('action').value;
            const amount = parseFloat(document.getElementById('amount').value);
            const resDiv = document.getElementById('result');

            if (!username || isNaN(amount)) {
                resDiv.className = 'error';
                resDiv.innerText = 'Please enter a valid username and amount.';
                resDiv.style.display = 'block';
                return;
            }

            try {
                const response = await fetch('/update-balance', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, action, amount })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    resDiv.className = 'success';
                    resDiv.innerText = `Success! New Balance: $${data.new_balance}`;
                } else {
                    resDiv.className = 'error';
                    resDiv.innerText = data.error || 'Failed to update balance.';
                }
            } catch (err) {
                resDiv.className = 'error';
                resDiv.innerText = 'Network error connecting to backend.';
            }
            resDiv.style.display = 'block';
        }
    </script>
</body>
</html>
"""

@app.route('/admin')
def admin_panel():
    return render_template_string(ADMIN_HTML)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
