# NexaBrokers — Institutional‑Grade Crypto Broker Platform

A premium, secure, and fully functional cryptocurrency broker platform built with **Python / Flask** and a stunning, responsive UI.  
Perfect for startups, fintech demos, or as a white‑label solution. **Ready to deploy and sell.**

![NexaBrokers Screenshot](https://via.placeholder.com/800x400?text=NexaBrokers+Preview)

---

## 🚀 Quick Demo

**Live demo:** *(replace with your Render URL after deployment)*  
**Demo account:** Click the **“Try Demo Account”** button on the login page to instantly access a pre‑funded $10,000 account.

---

## ✨ Key Features

### 🔐 Rock‑Solid Security
- CSRF protection on all state‑changing requests
- Rate limiting on sensitive endpoints (login, signup, password reset)
- Passwords hashed with Werkzeug (bcrypt‑like)
- OTP email verification (with development bypass mode)
- XSS‑safe rendering in all dynamic content
- HTTP‑only, SameSite session cookies

### 👥 User Experience
- Sleek, modern UI with a professional navy/gold palette
- Full‑screen background imagery
- Glass‑morphism cards and smooth animations
- Fully responsive — works beautifully on mobile, tablet, and desktop
- Sidebar navigation with mobile hamburger toggle

### 💰 Broker Functionality
- **Deposit** and **Withdrawal** requests with crypto currency support (USDT, BTC, ETH, USD)
- Real‑time balance updates
- Transaction status tracking (Pending, Approved, Rejected)
- Automatic balance adjustment on admin approval

### 🛠️ Powerful Admin Panel
- Tabbed interface: Overview, Users, Transactions, Audit Log
- **Overview**: live counts of users, active, pending/approved/rejected transactions
- **Users**: view all users, toggle active status, adjust balances with a reason
- **Transactions**: full list with approve/reject buttons
- **Audit Log**: complete history of balance adjustments (admin, user, amount, direction, reason, date)

### 🧪 Developer & Demo Friendly
- One‑click **demo account** creation
- **Development verification mode** – bypasses email sending and shows OTP codes directly in the API response
- Placeholder notification email hooks – ready to plug into Resend, SendGrid, or any SMTP service
- Clean separation of front‑end and API logic

### 📄 Additional Pages
- Privacy Policy & Terms of Service (customizable placeholders)
- Forgot Password page (front‑end ready, backend logs placeholder)
- Custom 404 and 500 error pages

---

## 🧰 Tech Stack

| Layer       | Technology                                      |
|-------------|-------------------------------------------------|
| Backend     | Python 3, Flask, Flask‑SQLAlchemy, Flask‑WTF, Flask‑Limiter |
| Database    | SQLite (development) / PostgreSQL (production‑ready) |
| Frontend    | HTML5, CSS3, vanilla JavaScript, Google Fonts (Inter) |
| Security    | CSRF, rate limiting, hashed passwords, XSS prevention |
| Deployment  | Ready for Render, Railway, or any WSGI server     |

---

## 📦 Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/nexabrokers.git
cd nexabrokers
