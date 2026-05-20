# 🚀 SmartTravels — Kenya's Unified Transport Booking Platform

A full-stack Django system integrating **Bus · Train · Flight** bookings, live GPS tracking,
M-Pesa payments, dynamic seat allocation, parcel delivery, QR tickets, and admin dashboards.

---

## ⚡ Quick Start (2 steps)

### 1. Install Python 3.10–3.12
Download: https://python.org

### 2. Run
```bash
cd smarttravels
python run.py
```
Open **http://127.0.0.1:8000**

> No pip install needed — all dependencies are bundled in the `/lib` folder.

---

## 🔑 Test Accounts

| Role           | Username       | Password        | Dashboard                        |
|----------------|----------------|-----------------|----------------------------------|
| System Admin   | `admin`        | `Admin1234!`    | /systemadmin/dashboard/          |
| Bus Admin      | `bus_admin`    | `BusAdmin1!`    | /buses/dashboard/                |
| Train Admin    | `train_admin`  | `TrainAdmin1!`  | /trains/dashboard/               |
| Flight Admin   | `flight_admin` | `FlightAdmin1!` | /flights/dashboard/              |
| Driver         | `driver01`     | `Driver1234!`   | /drivers/dashboard/              |
| Passenger      | `passenger`    | `Pass1234!`     | /accounts/dashboard/             |

Login at: **http://127.0.0.1:8000/accounts/login/**

---

## 📁 Project Structure

```
smarttravels/                    ← Django project root
│
├── run.py                       ← ONE-CLICK START SCRIPT
├── manage.py
├── db.sqlite3                   ← SQLite database (auto-created)
├── requirements.txt
│
├── smarttravels/
│   ├── settings.py              ← All config (DB, M-Pesa, static)
│   └── urls.py                  ← Root URL routing
│
├── apps/
│   ├── accounts/                ← Auth, login, register, unified booking view
│   │   └── views.py             ← dashboard_view, book_trip, passenger_seat_layout,
│   │                               download_ticket (PDF with QR)
│   │
│   ├── systemadmin/             ← System Admin: full control
│   │   ├── views.py             ← dashboard, manage_users, manage_admins, analytics,
│   │   │                           audit_logs, system_settings
│   │   └── seat_layout.py       ← DYNAMIC SEAT ENGINE (bus/train/flight)
│   │
│   ├── buses/                   ← Bus company admin
│   │   └── views.py             ← bus_dashboard, add_buses, add_driver, add_route,
│   │                               schedule, booking, reports, bus_seat_preview
│   │
│   ├── trains/                  ← Train company admin
│   │   └── views.py             ← train_dashboard, add_trains, add_conductor,
│   │                               schedule, booking, reports, train_seat_preview
│   │
│   ├── flights/                 ← Flight company admin
│   │   └── views.py             ← flight_dashboard, add_flights, add_pilot,
│   │                               schedule, booking, reports, flight_seat_preview
│   │
│   ├── drivers/                 ← Driver dashboard, GPS, incident reports
│   ├── payments/                ← M-Pesa STK Push, callback, status polling
│   ├── parcels/                 ← Parcel booking, tracking, delivery status
│   ├── gps/                     ← Live GPS tracking, location API
│   └── notifications/           ← In-app notifications
│
└── templates/
    ├── index.html               ← Public landing page (all features)
    ├── base/base.html           ← Global nav + footer
    ├── auth/                    ← login.html, register.html
    ├── passenger/               ← dashboard.html (search+AI+SOS), book_trip.html,
    │                               seat_selection with dynamic layout
    ├── bus_admin/               ← dashboard, add_buses (dynamic seats), schedule,
    │                               booking, reports, add_driver, add_route
    ├── train_admin/             ← dashboard, add_trains (dynamic seats), schedule,
    │                               booking, reports, add_conductor
    ├── flight_admin/            ← dashboard, add_flights (dynamic seats), schedule,
    │                               booking, reports, add_pilot
    ├── system_admin/            ← dashboard (charts), manage_users, manage_admins,
    │                               analytics, audit_logs, settings
    ├── driver/                  ← driver.html: GPS, trip status, incident report
    ├── payments/                ← checkout.html (M-Pesa), pending.html (polling),
    │                               success.html (confirmed + code)
    ├── parcels/                 ← book.html, my_parcels.html, track.html, detail.html
    ├── tracking/                ← live.html (GPS map, SOS button)
    └── notifications/           ← list.html
```

---

## 🪑 Dynamic Seat Allocation

The system generates seat maps **dynamically** based on vehicle capacity:

### How it works:
1. Admin enters **Total Passengers** (e.g. 45)
2. System auto-calculates: VIP = 15%, Normal = 85% (bus); or First/Business/Economy split
3. **Live seat map renders instantly** in the browser — no page reload
4. Passengers see the real seat map when booking, with booked seats greyed out
5. Select N seats (matching number of passengers), confirm, pay via M-Pesa

### Seat patterns:
| Mode   | Layout              | Sections                        |
|--------|---------------------|---------------------------------|
| Bus    | 2+2 (aisle middle)  | VIP (front) + Normal (rear)     |
| Train  | 2+2 then 2+3        | First Class + Business + Economy|
| Flight | 2+2 then 3+3+3      | First + Business + Economy      |

---

## ✅ All Features Implemented

### Passenger
- [x] Register, login, logout
- [x] Multi-mode search (bus/train/flight) with time filters
- [x] Dynamic interactive seat selection
- [x] M-Pesa STK Push payment with status polling
- [x] PDF ticket download with QR code
- [x] AI travel chatbot + recommendations
- [x] Live GPS tracking with SOS button
- [x] Parcel booking and tracking
- [x] In-app notifications
- [x] Loyalty program display
- [x] Weather alerts panel

### Bus / Train / Flight Admin
- [x] Company dashboard with bookings & revenue
- [x] Add vehicles with **dynamic seat allocation** (enter total → auto-generates)
- [x] Live seat preview (updates as you type)
- [x] Add drivers / conductors / pilots
- [x] Create schedules with pricing
- [x] View and manage bookings
- [x] Revenue and booking reports

### System Admin
- [x] Full analytics dashboard with Chart.js graphs
- [x] Manage all users (search, filter by role, suspend/activate)
- [x] Create admin accounts and assign roles
- [x] Audit logs for all bookings and parcels
- [x] System settings

### Technical
- [x] M-Pesa Daraja API (STK Push, callback, simulation)
- [x] QR-coded PDF tickets (ReportLab)
- [x] Dynamic seat layout engine (any capacity)
- [x] Real-time seat availability
- [x] GPS coordinate storage
- [x] Role-based access control (6 roles)

---

## 💳 M-Pesa Configuration (Production)

```python
# In smarttravels/settings.py
MPESA_ENVIRONMENT     = 'production'  # or 'sandbox'
MPESA_CONSUMER_KEY    = 'your_key'
MPESA_CONSUMER_SECRET = 'your_secret'
MPESA_SHORTCODE       = 'your_shortcode'
MPESA_PASSKEY         = 'your_passkey'
MPESA_CALLBACK_URL    = 'https://yourdomain.co.ke/payments/mpesa/callback/'
```

For local testing with sandbox, use ngrok:
```bash
ngrok http 8000
# Copy HTTPS URL → set as MPESA_CALLBACK_URL
```

---

## 🗄️ PostgreSQL (Production)

Uncomment in `settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'smarttravels_db',
        'USER': 'smarttravels_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

---

Built with ❤️ for Kenya 🇰🇪 | SmartTravels 2026
