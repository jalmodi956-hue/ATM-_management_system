# ATM Management System

## Project Overview

ATM Management System is a Flask-based web application developed using Python and SQLite.
This project simulates ATM banking operations such as account login, balance checking, deposit, withdrawal, money transfer, transaction history, fixed deposit, PDF/CSV reports, and admin management.

---

## Features

### User Features

* User Login
* User Registration
* Forgot PIN using Security Question
* Check Balance
* Deposit Money
* Withdraw Money
* Fast Cash
* Money Transfer
* Mini Statement
* Transaction History
* Search Transaction
* Account Details
* Change PIN
* Fixed Deposit (FD)
* Interest Calculator
* Edit Profile
* Profile Picture Upload
* Download PDF Report
* Export CSV Report
* Print Receipt
* Filter Transactions by Date
* Dark Mode
* ATM Card Design

### Security Features

* PIN Encryption using Werkzeug
* 3 Wrong PIN Attempts Account Lock
* Auto Logout
* Last Login Date & Time
* Login IP Address

### Admin Features

* Admin Login
* View All Users
* Add User
* Edit User
* Delete User
* Search User
* Total Deposits and Withdrawals
* Charts / Transaction Graph

### Notification Features

* Email Receipt after Deposit / Withdraw

---

## Technologies Used

* Python
* Flask
* SQLite3
* HTML
* CSS
* JavaScript
* Bootstrap / Custom Styling
* Matplotlib
* ReportLab

---

## Project Structure

ATM management system/
│── app.py
│── database.db
│── README.md
│── static/
│   ├── style.css
│   ├── logo.png
│   ├── chart.png
│   └── uploads/
│
│── templates/
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── deposit.html
│   ├── withdraw.html
│   ├── transfer.html
│   ├── history.html
│   ├── profile.html
│   ├── edit_profile.html
│   ├── fixed_deposit.html
│   ├── interest_calculator.html
│   ├── receipt.html
│   ├── filter_transactions.html
│   ├── admin_dashboard.html
│   ├── admin_chart.html
│   └── other html files...

---

## Installation Steps

1. Clone the repository:

```bash
git clone <your-github-repo-link>
```

2. Open the project folder:

```bash
cd ATM-management-system
```

3. Install required packages:

```bash
pip install flask werkzeug matplotlib reportlab
```

4. Run the project:

```bash
python app.py
```

5. Open in browser:

```bash
http://127.0.0.1:5000
```

---

## Default Demo Login

### User Login

* Card Number: `246450307052`
* PIN: `#Rm_54321`

### Admin Login

* Username: `admin`
* Password: `admin123`

---

## Future Enhancements

* SMS Alert Integration
* Responsive Design for Mobile
* Better UI Improvements
* OTP Verification
* Online Banking API Integration

---

## Author

**Jal Modi**
Diploma Computer Engineering Student
GTU Project / SBTP Project
