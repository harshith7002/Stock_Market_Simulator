from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import mysql.connector
import numpy as np
import uuid
import hashlib
from datetime import datetime
from functools import wraps
import yfinance as yf

app = Flask(__name__)
app.secret_key = 'stocksim_secret_key_2026'
app.jinja_env.globals.update(enumerate=enumerate)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '306714',
    'database': 'stockdb'
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def gen_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8].upper()}"

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ── yfinance helpers ───────────────────────────────────────────────────────────

def get_usd_inr():
    """Live USD → INR exchange rate, fallback 84.5."""
    try:
        return round(float(yf.Ticker('USDINR=X').fast_info.last_price), 2)
    except Exception:
        return 84.5

def fetch_yf_price(symbol):
    """Try symbol as-is, then .NS, then .BO. Returns dict or None."""
    candidates = [symbol, f"{symbol}.NS", f"{symbol}.BO"]
    for sym in candidates:
        try:
            t = yf.Ticker(sym)
            fi = t.fast_info
            price = fi.last_price
            prev  = fi.previous_close
            if price and price > 0:
                change     = round(float(price - prev), 2)
                change_pct = round((change / float(prev)) * 100, 2) if prev else 0
                return {
                    'yf_symbol':  sym,
                    'price':      round(float(price), 2),
                    'prev_close': round(float(prev), 2),
                    'change':     change,
                    'change_pct': change_pct,
                }
        except Exception:
            continue
    return None

def yf_info(yf_symbol):
    """Fetch company name and sector (slow call — use only when creating a new stock row)."""
    try:
        info = yf.Ticker(yf_symbol).info
        return info.get('longName', yf_symbol.split('.')[0]), info.get('sector', 'Unknown')
    except Exception:
        return yf_symbol.split('.')[0], 'Unknown'

def ensure_stock_in_db(symbol, cur):
    """Return (stock_id, live_price). Creates the row if missing."""
    cur.execute("SELECT stock_id, current_price FROM STOCK WHERE symbol=%s", (symbol,))
    row = cur.fetchone()
    if row:
        return row['stock_id'], float(row['current_price'])

    data = fetch_yf_price(symbol)
    if not data:
        return None, None

    name, sector = yf_info(data['yf_symbol'])
    stock_id = gen_id('STK')
    cur.execute(
        "INSERT INTO STOCK (stock_id, symbol, company_name, current_price, mu, sigma, sector) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (stock_id, symbol, name, data['price'], 0.0003, 0.020, sector)
    )
    return stock_id, data['price']

# ── GBM Engine ─────────────────────────────────────────────────────────────────

def run_gbm(S0, mu, sigma, days, n_paths):
    dt = 1
    paths, finals = [], []
    for _ in range(n_paths):
        prices = [S0]
        for _ in range(days):
            Z = np.random.standard_normal()
            S = prices[-1] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z)
            prices.append(round(float(S), 2))
        paths.append(prices)
        finals.append(prices[-1])
    n = len(finals)
    return {
        'paths':       paths[:50],
        'median':      round(np.median(finals), 2),
        'p10':         round(np.percentile(finals, 10), 2),
        'p90':         round(np.percentile(finals, 90), 2),
        'mean':        round(float(np.mean(finals)), 2),
        'std':         round(float(np.std(finals)), 2),
        'prob_profit': round(sum(1 for f in finals if f > S0) / n * 100, 1),
        'finals':      [round(f, 2) for f in finals]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form['name'].strip()
        email    = request.form['email'].strip()
        password = request.form['password']
        if not name or not email or not password:
            flash('All fields are required.', 'error')
            return render_template('register.html')
        db = get_db(); cur = db.cursor(dictionary=True)
        try:
            user_id = gen_id('USR'); wallet_id = gen_id('WLT')
            cur.execute(
                "INSERT INTO USER (user_id, name, email, password_hash) VALUES (%s,%s,%s,%s)",
                (user_id, name, email, hash_pw(password))
            )
            cur.execute(
                "INSERT INTO WALLET (wallet_id, user_id, balance) VALUES (%s,%s,100000.00)",
                (wallet_id, user_id)
            )
            db.commit()
            flash('Account created! You start with $100,000 virtual cash.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.IntegrityError:
            flash('Email already registered.', 'error')
        finally:
            cur.close(); db.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        pw    = hash_pw(request.form['password'])
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM USER WHERE email=%s AND password_hash=%s", (email, pw))
        user = cur.fetchone()
        cur.close(); db.close()
        if user:
            session['user_id']   = user['user_id']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    db = get_db(); cur = db.cursor(dictionary=True)

    cur.execute("SELECT balance FROM WALLET WHERE user_id=%s", (user_id,))
    wallet = cur.fetchone()

    cur.execute("""
        SELECT p.stock_id, s.symbol, s.company_name, s.current_price,
               p.quantity, p.avg_cost,
               ROUND((s.current_price - p.avg_cost) * p.quantity, 2) AS pnl
        FROM PORTFOLIO p JOIN STOCK s ON p.stock_id = s.stock_id
        WHERE p.user_id=%s AND p.quantity > 0
    """, (user_id,))
    holdings = cur.fetchall()

    portfolio_value = sum(h['quantity'] * float(h['current_price']) for h in holdings)

    cur.execute("""
        SELECT t.transaction_type, t.quantity, t.price, t.total_amount,
               t.timestamp, s.symbol
        FROM `TRANSACTION` t JOIN STOCK s ON t.stock_id = s.stock_id
        WHERE t.user_id=%s ORDER BY t.timestamp DESC LIMIT 10
    """, (user_id,))
    transactions = cur.fetchall()

    cur.execute("SELECT * FROM STOCK")
    stocks = cur.fetchall()

    cur.close(); db.close()
    return render_template('dashboard.html',
        wallet=wallet, holdings=holdings,
        portfolio_value=round(portfolio_value, 2),
        transactions=transactions, stocks=stocks,
        total_value=round(float(wallet['balance']) + portfolio_value, 2)
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATOR
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/simulator')
@login_required
def simulator():
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM STOCK")
    stocks = cur.fetchall()
    cur.close(); db.close()
    return render_template('simulator.html', stocks=stocks)

@app.route('/api/simulate', methods=['POST'])
@login_required
def api_simulate():
    data     = request.json
    stock_id = data.get('stock_id')
    symbol   = (data.get('symbol') or '').upper().strip()
    n_paths  = min(int(data.get('n_paths', 100)), 10000)
    days     = min(int(data.get('days', 120)), 365)

    db = get_db(); cur = db.cursor(dictionary=True)

    if stock_id:
        cur.execute("SELECT * FROM STOCK WHERE stock_id=%s", (stock_id,))
        stock = cur.fetchone()
    elif symbol:
        sid, _ = ensure_stock_in_db(symbol, cur)
        db.commit()
        cur.execute("SELECT * FROM STOCK WHERE stock_id=%s", (sid,))
        stock = cur.fetchone()
    else:
        cur.close(); db.close()
        return jsonify({'error': 'No stock specified'}), 400

    cur.close(); db.close()
    if not stock:
        return jsonify({'error': 'Stock not found'}), 404

    mu    = float(stock['mu'])
    sigma = float(stock['sigma'])
    S0    = float(stock['current_price'])

    # Fetch live price and convert USD → INR if needed
    live = fetch_yf_price(stock['symbol'])
    usd_inr = None
    if live:
        raw_price = live['price']
        yf_sym    = live['yf_symbol']
        is_indian = yf_sym.endswith('.NS') or yf_sym.endswith('.BO')
        if is_indian:
            S0 = raw_price          # already INR
        else:
            usd_inr = get_usd_inr()
            S0 = round(raw_price * usd_inr, 2)   # USD → INR

    result = run_gbm(S0=S0, mu=mu, sigma=sigma, days=days, n_paths=n_paths)
    result['stock'] = {
        'symbol':        stock['symbol'],
        'company_name':  stock['company_name'],
        'current_price': S0,
        'usd_inr':       usd_inr,   # None if stock is already INR
    }
    return jsonify(result)

# ═══════════════════════════════════════════════════════════════════════════════
# TRADING
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/trade', methods=['POST'])
@login_required
def api_trade():
    user_id    = session['user_id']
    data       = request.json
    stock_id   = data.get('stock_id')
    symbol     = (data.get('symbol') or '').upper().strip()
    trade_type = data.get('type', '').upper()
    quantity   = int(data.get('quantity', 0))

    if quantity <= 0:
        return jsonify({'error': 'Quantity must be positive'}), 400
    if trade_type not in ('BUY', 'SELL'):
        return jsonify({'error': 'Invalid trade type'}), 400

    db = get_db(); cur = db.cursor(dictionary=True)
    try:
        # resolve stock
        if not stock_id and symbol:
            stock_id, _ = ensure_stock_in_db(symbol, cur)
            if not stock_id:
                return jsonify({'error': f'Cannot find stock: {symbol}'}), 404

        cur.execute("SELECT * FROM STOCK WHERE stock_id=%s", (stock_id,))
        stock = cur.fetchone()
        if not stock:
            return jsonify({'error': 'Stock not found'}), 404

        # use live price if available
        price = float(stock['current_price'])
        live  = fetch_yf_price(stock['symbol'])
        if live:
            price = live['price']
            cur.execute("UPDATE STOCK SET current_price=%s WHERE stock_id=%s", (price, stock_id))

        total_amount = round(price * quantity, 2)
        cur.execute("SELECT * FROM WALLET WHERE user_id=%s FOR UPDATE", (user_id,))
        wallet = cur.fetchone()

        if trade_type == 'BUY':
            if float(wallet['balance']) < total_amount:
                return jsonify({'error': 'Insufficient wallet balance'}), 400
            cur.execute("UPDATE WALLET SET balance=balance-%s WHERE user_id=%s", (total_amount, user_id))
            cur.execute("SELECT * FROM PORTFOLIO WHERE user_id=%s AND stock_id=%s", (user_id, stock_id))
            ex = cur.fetchone()
            if ex:
                nq   = ex['quantity'] + quantity
                nc   = round((float(ex['avg_cost']) * ex['quantity'] + total_amount) / nq, 2)
                cur.execute("UPDATE PORTFOLIO SET quantity=%s, avg_cost=%s WHERE user_id=%s AND stock_id=%s",
                            (nq, nc, user_id, stock_id))
            else:
                cur.execute("INSERT INTO PORTFOLIO (portfolio_id,user_id,stock_id,quantity,avg_cost) VALUES (%s,%s,%s,%s,%s)",
                            (gen_id('PRT'), user_id, stock_id, quantity, price))
        else:
            cur.execute("SELECT * FROM PORTFOLIO WHERE user_id=%s AND stock_id=%s", (user_id, stock_id))
            h = cur.fetchone()
            if not h or h['quantity'] < quantity:
                return jsonify({'error': 'Not enough shares to sell'}), 400
            cur.execute("UPDATE PORTFOLIO SET quantity=%s WHERE user_id=%s AND stock_id=%s",
                        (h['quantity'] - quantity, user_id, stock_id))
            cur.execute("UPDATE WALLET SET balance=balance+%s WHERE user_id=%s", (total_amount, user_id))

        cur.execute("""INSERT INTO `TRANSACTION`
            (transaction_id,user_id,stock_id,transaction_type,quantity,price,total_amount)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (gen_id('TXN'), user_id, stock_id, trade_type, quantity, price, total_amount))
        cur.execute("""INSERT INTO ORDER_TABLE
            (order_id,user_id,stock_id,order_type,quantity,price,status)
            VALUES (%s,%s,%s,%s,%s,%s,'COMPLETED')""",
            (gen_id('ORD'), user_id, stock_id, trade_type, quantity, price))

        db.commit()
        cur.execute("SELECT balance FROM WALLET WHERE user_id=%s", (user_id,))
        nb = cur.fetchone()
        return jsonify({'success': True,
                        'message': f"{trade_type} {quantity} × {stock['symbol']} @ ₹{price:,.2f}",
                        'new_balance': float(nb['balance'])})
    except mysql.connector.Error as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close(); db.close()

# ═══════════════════════════════════════════════════════════════════════════════
# LIVE DATA APIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/api/search')
@login_required
def api_search():
    q = request.args.get('q', '').strip().upper()
    if not q:
        return jsonify([])

    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("""SELECT stock_id, symbol, company_name, current_price, sector
                   FROM STOCK WHERE symbol LIKE %s OR company_name LIKE %s LIMIT 6""",
                (f'{q}%', f'%{q}%'))
    db_rows = cur.fetchall()
    cur.close(); db.close()

    results = [{'stock_id': r['stock_id'], 'symbol': r['symbol'],
                'company_name': r['company_name'], 'price': float(r['current_price']),
                'sector': r.get('sector',''), 'source': 'db'} for r in db_rows]

    if len(q) <= 7 and not any(r['symbol'] == q for r in results):
        data = fetch_yf_price(q)
        if data:
            name, sector = yf_info(data['yf_symbol'])
            results.append({'stock_id': None, 'symbol': q, 'company_name': name,
                            'price': data['price'], 'change_pct': data['change_pct'],
                            'sector': sector, 'source': 'live',
                            'yf_symbol': data['yf_symbol']})
    return jsonify(results)

@app.route('/api/price/<symbol>')
@login_required
def api_price(symbol):
    symbol = symbol.upper().strip()
    data   = fetch_yf_price(symbol)
    if not data:
        return jsonify({'error': 'Not found'}), 404

    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT stock_id, company_name FROM STOCK WHERE symbol=%s", (symbol,))
    row = cur.fetchone()
    cur.close(); db.close()

    return jsonify({
        'symbol':       symbol,
        'company_name': row['company_name'] if row else symbol,
        'stock_id':     row['stock_id'] if row else None,
        'price':        data['price'],
        'change':       data['change'],
        'change_pct':   data['change_pct'],
    })

@app.route('/api/market/trending')
@login_required
def api_trending():
    symbols_map = {
        'RELIANCE': 'RELIANCE.NS', 'TCS': 'TCS.NS',
        'INFY': 'INFY.NS', 'HDFCBANK': 'HDFCBANK.NS',
        'WIPRO': 'WIPRO.NS', 'AAPL': 'AAPL',
        'TSLA': 'TSLA', 'GOOGL': 'GOOGL',
        'MSFT': 'MSFT', 'NVDA': 'NVDA',
    }
    results = []
    for display, yf_sym in symbols_map.items():
        try:
            t  = yf.Ticker(yf_sym)
            fi = t.fast_info
            p  = fi.last_price; prev = fi.previous_close
            if p and prev and prev > 0:
                results.append({'symbol': display, 'price': round(float(p), 2),
                                'change_pct': round((p - prev) / prev * 100, 2)})
        except Exception:
            pass
    return jsonify(results)

@app.route('/api/chart/<symbol>')
@login_required
def api_chart(symbol):
    symbol = symbol.upper().strip()
    period = request.args.get('period', '1mo')
    for sym in [symbol, f'{symbol}.NS']:
        try:
            hist = yf.Ticker(sym).history(period=period)
            if not hist.empty:
                return jsonify([{
                    'time':   ts.strftime('%Y-%m-%d'),
                    'open':   round(float(r['Open']), 2),
                    'high':   round(float(r['High']), 2),
                    'low':    round(float(r['Low']), 2),
                    'close':  round(float(r['Close']), 2),
                    'volume': int(r['Volume'])
                } for ts, r in hist.iterrows()])
        except Exception:
            pass
    return jsonify([])

@app.route('/api/usd_inr')
@login_required
def api_usd_inr():
    return jsonify({'rate': get_usd_inr()})

@app.route('/api/portfolio/chart')
@login_required
def api_portfolio_chart():
    user_id = session['user_id']
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT s.symbol, s.company_name,
               ROUND(p.quantity * s.current_price, 2) AS value
        FROM PORTFOLIO p JOIN STOCK s ON p.stock_id = s.stock_id
        WHERE p.user_id=%s AND p.quantity > 0
    """, (user_id,))
    rows = cur.fetchall()
    cur.close(); db.close()
    return jsonify([{'symbol': r['symbol'], 'company_name': r['company_name'],
                     'value': float(r['value'])} for r in rows])

# ═══════════════════════════════════════════════════════════════════════════════
# LEADERBOARD & WATCHLIST
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/leaderboard')
@login_required
def leaderboard():
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT u.name, w.balance AS wallet_balance,
               COALESCE(SUM(p.quantity * s.current_price), 0) AS portfolio_value,
               COALESCE(SUM(p.quantity * s.current_price), 0) + w.balance AS total_value
        FROM USER u JOIN WALLET w ON u.user_id=w.user_id
        LEFT JOIN PORTFOLIO p ON u.user_id=p.user_id AND p.quantity>0
        LEFT JOIN STOCK s ON p.stock_id=s.stock_id
        GROUP BY u.user_id, u.name, w.balance
        ORDER BY total_value DESC
    """)
    rows = cur.fetchall()
    cur.close(); db.close()
    return render_template('leaderboard.html', rows=rows)

@app.route('/api/watchlist/add', methods=['POST'])
@login_required
def add_watchlist():
    user_id  = session['user_id']
    stock_id = request.json.get('stock_id')
    db = get_db(); cur = db.cursor()
    try:
        cur.execute("INSERT IGNORE INTO WATCHLIST (watchlist_id,user_id,stock_id) VALUES (%s,%s,%s)",
                    (gen_id('WCH'), user_id, stock_id))
        db.commit()
        return jsonify({'success': True})
    finally:
        cur.close(); db.close()

if __name__ == '__main__':
    app.run(debug=True)
