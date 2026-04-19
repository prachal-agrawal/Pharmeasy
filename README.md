# MathuraPharmeasy — Full Stack Online Pharmacy
## React + FastAPI + MySQL + Razorpay

---

## 📁 Project Structure

```
medkart_full/
├── backend/                    ← Python FastAPI
│   ├── main.py                 ← App entry point + all routers
│   ├── config.py               ← Settings (reads .env)
│   ├── database.py             ← MySQL connection pool
│   ├── auth.py                 ← JWT helpers + FastAPI deps
│   ├── invoice.py              ← PDF generation (ReportLab)
│   ├── schema.sql              ← DB schema + seed data
│   ├── requirements.txt
│   ├── .env.example            ← Copy to .env
│   └── routes/
│       ├── auth_router.py      ← /api/auth/*
│       ├── medicines_router.py ← /api/medicines/*
│       ├── cart_router.py      ← /api/cart/*
│       ├── orders_router.py    ← /api/orders/*
│       ├── addresses_router.py ← /api/addresses/*
│       ├── payment_router.py   ← /api/payment/* (Razorpay)
│       └── admin_router.py     ← /api/admin/*
│
└── frontend/                   ← React + Vite + Tailwind
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx             ← Routes
        ├── index.css           ← Tailwind + custom
        ├── utils/
        │   ├── api.js          ← Axios instance + all API calls
        │   └── razorpay.js     ← Razorpay payment flow helper
        ├── context/
        │   ├── AuthContext.jsx ← JWT auth state
        │   └── CartContext.jsx ← Cart state
        ├── components/
        │   ├── Navbar.jsx
        │   └── MedicineCard.jsx
        └── pages/
            ├── Home.jsx          ← Catalog + search
            ├── ProductDetail.jsx ← Variant picker (Omnigel-style)
            ├── Cart.jsx
            ├── Checkout.jsx      ← 3-step + Razorpay
            ├── Orders.jsx        ← Tracking + invoice
            ├── Login.jsx
            ├── Register.jsx
            └── admin/
                ├── AdminLayout.jsx
                ├── AdminDashboard.jsx
                ├── AdminMedicines.jsx ← Full CRUD + image upload
                └── AdminOrders.jsx    ← Status management
```

---

## 🚀 Setup — Backend

### Step 1 — Install MySQL & create database
```bash
# macOS
brew install mysql && brew services start mysql

# Ubuntu
sudo apt install mysql-server && sudo systemctl start mysql

# Load schema
mysql -u root -p < backend/schema.sql
```

### Step 2 — Python environment
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 3 — Configure .env
```bash
cp .env.example .env
```
Edit `.env`:
```env
DB_PASSWORD=hg77
SECRET_KEY=<run: python -c "import secrets; print(secrets.token_hex(32))">
RAZORPAY_KEY_ID=rzp_test_SdERrXRjeh3SOo
RAZORPAY_KEY_SECRET=O26x6UTBlt3hTiM3rVSOf0zX
```

### Step 4 — Start backend
```bash
python main.py
# OR
uvicorn main:app --reload --port 8000
```

Backend URLs:
- API: http://localhost:8000
- **Swagger Docs**: http://localhost:8000/docs  ← test all endpoints here

---

## 🚀 Setup — Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173

The Vite proxy automatically forwards `/api/*` to `http://localhost:8000`.

---

## 💳 Razorpay Payment Setup

### 1. Get credentials
1. Sign up at **https://razorpay.com** (free)
2. Go to **Settings → API Keys → Generate Test Key**
3. Copy Key ID and Key Secret

### 2. Add to backend `.env`
```env
RAZORPAY_KEY_ID=rzp_test_XXXXXXXXXXXXXXXX
RAZORPAY_KEY_SECRET=XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### 3. How the payment flow works

```
Frontend                    Backend                     Razorpay
────────                    ───────                     ────────
Click "Pay"
    │
    ├─POST /api/payment/create-order──►  rzp.order.create()
    │                                          │
    │◄── { razorpay_order_id, key_id } ────────┘
    │
    ├─ Open Razorpay Modal (JS SDK)
    │         (user pays)
    │
    ├─ Razorpay calls handler() with:
    │   { razorpay_order_id,
    │     razorpay_payment_id,
    │     razorpay_signature }
    │
    ├─POST /api/payment/verify ──────►  HMAC-SHA256 verify signature
    │                                   UPDATE orders SET status='confirmed'
    │◄── { verified: true } ────────────────────────────────────────┘
    │
    └─POST /api/orders ──────────────►  Place order with payment_ref
```

### 4. Webhook (optional but recommended)
Configure in Razorpay Dashboard → Settings → Webhooks:
- URL: `https://yourdomain.com/api/payment/webhook`
- Events: `payment.captured`, `payment.failed`, `refund.created`

---

## 🔐 Default Credentials

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@mathurapharmeasy.in | Admin@123 |

> ⚠️ Change admin password after first login!

Generate a new bcrypt hash:
```python
from passlib.context import CryptContext
pwd = CryptContext(schemes=["bcrypt"])
print(pwd.hash("YourNewPassword"))
# Then: UPDATE users SET password_hash='...' WHERE email='admin@mathurapharmeasy.in';
```

---

## 🌐 Production Deployment

### Backend (e.g. Ubuntu VPS)
```bash
pip install gunicorn
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Frontend
```bash
npm run build
# Serve the dist/ folder with Nginx or upload to Vercel/Netlify
```

### Nginx config
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Frontend
    location / {
        root /var/www/mathurapharmeasy/dist;
        try_files $uri /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }

    # Uploads / Invoices
    location /uploads/ { proxy_pass http://localhost:8000; }
    location /invoices/ { proxy_pass http://localhost:8000; }
}
```

---

## 🗄️ Database Tables

| Table | Purpose |
|-------|---------|
| `users` | Customers + admins |
| `addresses` | Saved delivery addresses |
| `categories` | Medicine categories |
| `medicines` | Parent medicine record |
| `medicine_variants` | Sizes / strengths / pack options |
| `orders` | Orders with 4-state machine |
| `order_items` | Line items per order |
| `order_status_log` | Full audit trail |
| `cart_items` | Persistent cart per user |
| `invoices` | Invoice number + PDF path |

---

## 📄 Invoice PDF

Invoices are auto-generated after every order using ReportLab.
- Saved to: `backend/public/invoices/INV-MK-XXXXXX.pdf`
- Download: `GET /api/orders/{id}/invoice`
- Full layout: logo, address, itemised table, totals, footer

---

## 🧪 Test the Full Flow

1. `npm run dev` (frontend) + `python main.py` (backend)
2. Go to http://localhost:5173
3. Register a customer account
4. Browse catalog → click Omnigel → select "100 gm Gel"
5. Add to cart → Proceed to checkout
6. Add delivery address
7. Select "UPI" → enter test UPI ID → Place order
8. Razorpay test modal opens → use test card `4111 1111 1111 1111`
9. Order confirmed → download PDF invoice
10. Login as admin → go to /admin → update order status → view all orders
