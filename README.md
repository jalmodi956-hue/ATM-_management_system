# ATM Management System

## Project Overview

**ATM Management System** is a Flask-based web application developed using **Python** and **SQLite**.
This project simulates core ATM and banking operations such as account login, balance checking, deposit, withdrawal, money transfer, transaction history, fixed deposit, profile management, PDF/CSV report generation, and admin management.

The goal of this project is to provide a practical banking simulation system with both **user-side** and **admin-side** features while also demonstrating basic **security mechanisms** such as PIN encryption, account lock after multiple failed attempts, session timeout, and login tracking.

---

# Features

## User Features

* User Login
* User Registration
* Forgot PIN using Security Question
* Check Balance
* Deposit Money
* Withdraw Money
* Fast Cash
* Money Transfer
* Mini Statement
* Full Transaction History
* Search Transactions
* Filter Transactions by Date
* Print Receipt
* Download PDF Report
* Export CSV Report
* Account Details
* Change PIN
* Fixed Deposit (FD)
* Interest Calculator
* Edit Profile
* Profile Picture Upload
* ATM Card Design UI
* Dark Mode

---

## Security Features

* PIN Encryption using **Werkzeug Security**
* Account Lock after **3 Wrong PIN Attempts**
* Auto Logout using Session Timeout
* Last Login Date & Time Tracking
* Login IP Address Tracking

---

## Admin Features

* Admin Login
* View All Users
* Add User
* Edit User
* Delete User
* Unlock Locked User
* Search User
* View Total Users
* View Total Deposits / Withdrawals / Transfers
* Transaction Chart / Graph

---

## Notification Features

* Email Receipt after Deposit
* Email Receipt after Withdrawal
* Email Receipt after Money Transfer

---

# Technologies Used

* **Python**
* **Flask**
* **SQLite3**
* **HTML**
* **CSS**
* **JavaScript**
* **Bootstrap / Custom Styling**
* **Matplotlib**
* **ReportLab**
* **Werkzeug Security**
* **SMTP (Email Sending)**
* **Jinja2 Templates**

---

# Project Structure

```bash
ATM-management-system/
│── app.py
│── database.db
│── README.md
│
├── static/
│   ├── style.css
│   ├── logo.png
│   ├── chart.png
│   └── uploads/
│
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── forgot_pin.html
│   ├── dashboard.html
│   ├── balance.html
│   ├── deposit.html
│   ├── withdraw.html
│   ├── fast_cash.html
│   ├── transfer.html
│   ├── history.html
│   ├── mini_statement.html
│   ├── receipt.html
│   ├── fixed_deposit.html
│   ├── interest_calculator.html
│   ├── account_details.html
│   ├── change_pin.html
│   ├── profile.html
│   ├── edit_profile.html
│   ├── filter_transactions.html
│   ├── search.html
│   ├── admin_login.html
│   ├── admin_dashboard.html
│   ├── admin_chart.html
│   ├── all_users.html
│   ├── add_user.html
│   ├── edit_user.html
│   ├── search_user.html
│   └── other related templates...
```

---

# Installation Steps

## 1) Clone the repository

```bash
git clone <your-github-repo-link>
```

## 2) Open the project folder

```bash
cd ATM-management-system
```

## 3) Install required packages

```bash
pip install flask werkzeug matplotlib reportlab
```

## 4) Run the project

```bash
python app.py
```

## 5) Open in browser

```bash
http://127.0.0.1:5000
```

---

# Default Demo Login

## User Login

* **Card Number:** `246450307052`
* **PIN:** `#Rm_54321`

## Admin Login

* **Username:** `admin`
* **Password:** `admin123`

---

# Main Modules

## 1. Authentication Module

Handles:

* User Login
* User Registration
* Forgot PIN
* Session management
* Account lock after wrong PIN attempts

## 2. Banking Operations Module

Handles:

* Deposit
* Withdraw
* Fast Cash
* Balance Checking
* Money Transfer

## 3. Transaction Module

Handles:

* Transaction History
* Mini Statement
* Receipt
* Search Transactions
* Filter by Date
* PDF / CSV Reports

## 4. Profile Management Module

Handles:

* View Profile
* Edit Profile
* Upload Profile Picture
* Change PIN
* Account Details

## 5. Fixed Deposit Module

Handles:

* Fixed Deposit creation
* FD maturity amount calculation
* Interest calculator

## 6. Admin Module

Handles:

* Admin Login
* User management
* Unlocking users
* Viewing statistics
* Viewing charts

---

# Security Implementation

This project includes basic security features for a student-level banking simulation system:

* User PINs are stored in **hashed form** using Werkzeug.
* User account gets locked after **3 failed login attempts**.
* Session timeout is enabled to support **auto logout**.
* Last login date/time and login IP are stored for activity tracking.

---

# Screens / Pages Included

* Login Page
* Register Page
* Forgot PIN Page
* Dashboard
* Deposit Page
* Withdraw Page
* Transfer Page
* Fast Cash Page
* Balance Page
* Mini Statement Page
* Full History Page
* Receipt Page
* Fixed Deposit Page
* Interest Calculator Page
* Profile Page
* Edit Profile Page
* Admin Dashboard
* User Management Pages

---

# Future Enhancements

* SMS Alert Integration
* OTP Verification
* Better Mobile Responsive UI
* Email Verification during Registration
* Transaction Fraud Detection
* Online Banking API Integration
* Better Admin Analytics Dashboard
* More secure role-based admin system

---

# Important Note

If you are using **email receipt functionality**, do **not** upload your real email password to GitHub.

Instead of hardcoding email credentials inside `app.py`, use environment variables or a separate secure config file.

Example:

```python
import os
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
```

---

# Conclusion

The **ATM Management System** is a practical Flask-based mini banking project that demonstrates both **core banking operations** and **basic security concepts**.
It is suitable for academic project submission, Flask practice, and learning how real-world banking workflows can be simulated in a web application.

---

# Author

**Jal Modi**
Diploma Computer Engineering Student
GTU Project / SBTP Project
