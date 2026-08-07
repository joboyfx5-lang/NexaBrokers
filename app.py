import os
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Fetch database URL from Render environment variables
db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url or "sqlite:///nexabrokers.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Database Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    balance = db.Column(db.Float, default=0.0)

with app.app_context():
    db.create_all()

# --- ROUTES ---

@app.route('/')
def home():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>NexaBrokers API</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #121212; color: #fff; text-align: center; padding: 40px 20px; }
            .card { background: #1e1e1e; border-radius: 12px; padding: 24px; max-width: 450px; margin: auto; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
            h1 { color: #00e676; margin-bottom: 8px; }
            p { color: #aaa; font-size: 14px; }
            .status { display: inline-block; background: rgba(0, 230, 118, 0.15); color: #00e676; padding: 6px 12px; border-radius: 20px; font-weight: bold; margin-top: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>NexaBrokers</h1>
            <p>User Balance & Transaction API is running successfully.</p>
            <div class="status">System Online ●</div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

# 1. Create or view a user balance
@app.route('/user/<username>', methods=['GET', 'POST'])
def handle_user(username):
    user = User.query.filter_by(username=username).first()
    if request.method == 'POST':
        if not user:
            user = User(username=username, balance=0.0)
            db.session.add(user)
            db.session.commit()
            return jsonify({"message": f"User {username} created.", "balance": user.balance}), 201
        return jsonify({"message": "User already exists.", "balance": user.balance}), 200

    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"username": user.username, "balance": user.balance})

# 2. Add or Remove Funds (Admin / Deposit feature)
@app.route('/update-balance', methods=['POST'])
def update_balance():
    data = request.get_json() or {}
    username = data.get('username')
    amount = data.get('amount')
    action = data.get('action')  # "add" or "remove"

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({"error": "Amount must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid amount specified"}), 400

    if action == "add":
        user.balance += amount
    elif action == "remove":
        if user.balance < amount:
            return jsonify({"error": "Insufficient balance to perform reduction"}), 400
        user.balance -= amount
    else:
        return jsonify({"error": "Action must be 'add' or 'remove'"}), 400

    db.session.commit()
    return jsonify({"message": f"Successfully updated balance for {username}", "new_balance": user.balance})

# 3. Withdraw Funds Feature
@app.route('/withdraw', methods=['POST'])
def withdraw():
    data = request.get_json() or {}
    username = data.get('username')
    amount = data.get('amount')

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        amount = float(amount)
        if amount <= 0:
            return jsonify({"error": "Withdrawal amount must be greater than zero"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid withdrawal amount"}), 400

    if user.balance < amount:
        return jsonify({"error": "Insufficient funds for withdrawal"}), 400

    user.balance -= amount
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Withdrawal of ${amount:.2f} processed successfully.",
        "remaining_balance": user.balance
    })

if __name__ == '__main__':
    app.run()
