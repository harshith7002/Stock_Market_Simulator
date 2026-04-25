CREATE DATABASE IF NOT EXISTS stockdb;
USE stockdb;

CREATE TABLE IF NOT EXISTS USER (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS WALLET (
    wallet_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    balance DECIMAL(18,2) DEFAULT 100000.00,
    FOREIGN KEY (user_id) REFERENCES USER(user_id)
);

CREATE TABLE IF NOT EXISTS STOCK (
    stock_id VARCHAR(50) PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    company_name VARCHAR(100) NOT NULL,
    current_price DECIMAL(18,2) NOT NULL,
    mu DECIMAL(10,6) NOT NULL COMMENT 'daily drift for GBM',
    sigma DECIMAL(10,6) NOT NULL COMMENT 'daily volatility for GBM',
    sector VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS PORTFOLIO (
    portfolio_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    stock_id VARCHAR(50) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    avg_cost DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    FOREIGN KEY (user_id) REFERENCES USER(user_id),
    FOREIGN KEY (stock_id) REFERENCES STOCK(stock_id),
    UNIQUE KEY uq_user_stock (user_id, stock_id)
);

CREATE TABLE IF NOT EXISTS `TRANSACTION` (
    transaction_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    stock_id VARCHAR(50) NOT NULL,
    transaction_type ENUM('BUY','SELL') NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(18,2) NOT NULL,
    total_amount DECIMAL(18,2) NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USER(user_id),
    FOREIGN KEY (stock_id) REFERENCES STOCK(stock_id)
);

CREATE TABLE IF NOT EXISTS ORDER_TABLE (
    order_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    stock_id VARCHAR(50) NOT NULL,
    order_type ENUM('BUY','SELL') NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(18,2) NOT NULL,
    status ENUM('PENDING','COMPLETED','PARTIAL','CANCELLED') DEFAULT 'PENDING',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USER(user_id),
    FOREIGN KEY (stock_id) REFERENCES STOCK(stock_id)
);

CREATE TABLE IF NOT EXISTS PRICE_HISTORY (
    history_id VARCHAR(50) PRIMARY KEY,
    stock_id VARCHAR(50) NOT NULL,
    price DECIMAL(18,2) NOT NULL,
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (stock_id) REFERENCES STOCK(stock_id)
);

CREATE TABLE IF NOT EXISTS WATCHLIST (
    watchlist_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    stock_id VARCHAR(50) NOT NULL,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES USER(user_id),
    FOREIGN KEY (stock_id) REFERENCES STOCK(stock_id)
);

-- Trigger: prevent wallet going negative
DELIMITER $$
CREATE TRIGGER before_update_wallet_balance
BEFORE UPDATE ON WALLET
FOR EACH ROW
BEGIN
    IF NEW.balance < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Wallet balance cannot be negative';
    END IF;
END$$
DELIMITER ;

-- Sample data
INSERT INTO STOCK (stock_id, symbol, company_name, current_price, mu, sigma, sector) VALUES
('STK_001', 'RELIANCE', 'Reliance Industries Ltd', 2850.00, 0.000400, 0.018000, 'Energy'),
('STK_002', 'TCS',      'Tata Consultancy Services', 3920.00, 0.000300, 0.015000, 'IT'),
('STK_003', 'HDFCBANK', 'HDFC Bank Ltd', 1670.00, 0.000350, 0.016000, 'Banking'),
('STK_004', 'GHOST',    'Ghost Corp (Illiquid)', 45.00,   -0.001000, 0.040000, 'Penny');

INSERT INTO USER (user_id, name, email, password_hash) VALUES
('USR_001', 'Original Trader',  'trader@stockdb.com',  'pbkdf2:sha256:placeholder1'),
('USR_002', 'Parishrut Singh',   'parishrut@stockdb.com','pbkdf2:sha256:placeholder2'),
('USR_003', 'Sai Harshith',      'harshith@stockdb.com', 'pbkdf2:sha256:placeholder3');

INSERT INTO WALLET (wallet_id, user_id, balance) VALUES
('WLT_001', 'USR_001', 100000.00),
('WLT_002', 'USR_002', 100000.00),
('WLT_003', 'USR_003', 100000.00);
