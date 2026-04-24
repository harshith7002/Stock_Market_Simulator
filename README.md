# StockSim — Monte Carlo Stock Market Simulator
### DBMS Mini Project | 21CSC205P | SRM Institute of Science and Technology
**Team 26 | Parishrut Singh & Sai Harshith Moluguri**

---

## Project Structure
```
stocksim/
├── app.py              ← Flask backend (all routes + Monte Carlo engine)
├── schema.sql          ← MySQL schema + sample data + trigger
├── requirements.txt    ← Python dependencies
└── templates/
    ├── base.html       ← Navbar + shared styles
    ├── login.html
    ├── register.html
    ├── dashboard.html  ← Portfolio, trading, transactions
    ├── simulator.html  ← Monte Carlo chart + stats
    └── leaderboard.html
```

---

## Setup Instructions

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up MySQL database
```bash
mysql -u root -p < schema.sql
```

### 3. Update DB password in app.py
Open `app.py` and set your MySQL password:
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'YOUR_PASSWORD',   # ← change this
    'database': 'stockdb'
}
```

### 4. Run the Flask app
```bash
python app.py
```

### 5. Open in browser
```
http://localhost:5000
```

---

## Features
| Feature | DB Tables Used |
|---|---|
| User registration / login | USER, WALLET |
| Portfolio tracking | PORTFOLIO, STOCK |
| Buy / Sell stocks | TRANSACTION, ORDER_TABLE, WALLET |
| Monte Carlo GBM simulation | STOCK (mu, sigma) |
| Leaderboard | USER, WALLET, PORTFOLIO |
| Watchlist | WATCHLIST |
| Wallet trigger | WALLET (BEFORE UPDATE trigger) |

---

## Monte Carlo Formula
```
S(t+1) = S(t) × exp((μ − ½σ²)dt + σ√dt × Z)
where Z ~ N(0,1) (standard normal random variable)
```

| Parameter | Meaning |
|---|---|
| S(t) | Current stock price |
| μ (mu) | Expected daily return (drift) |
| σ (sigma) | Daily volatility |
| Z | Random shock from standard normal distribution |
| dt | Time step (1 day) |

---

## Stock Parameters
| Symbol | Price | μ (daily) | σ (daily) | Sector |
|---|---|---|---|---|
| RELIANCE | ₹2,850 | 0.04% | 1.8% | Energy |
| TCS | ₹3,920 | 0.03% | 1.5% | IT |
| HDFCBANK | ₹1,670 | 0.035% | 1.6% | Banking |
| GHOST | ₹45 | -0.1% | 4.0% | Penny |
