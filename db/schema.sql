PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS orders (
  order_id INTEGER PRIMARY KEY,
  customer_id INTEGER,
  product_id INTEGER,
  order_date TEXT,
  amount REAL
);

CREATE TABLE IF NOT EXISTS summary (
  id INTEGER PRIMARY KEY,
  order_id INTEGER,
  quantity INTEGER,
  discount REAL,
  tax REAL,
  FOREIGN KEY(order_id) REFERENCES orders(order_id)
);

INSERT INTO orders(order_id, customer_id, product_id, order_date, amount) VALUES
(1, 101, 1001, '2025-06-15', 299.99),
(2, 102, 1002, '2025-07-02', 149.50),
(3, 103, 1001, '2025-08-10', 499.00),
(4, 101, 1003, '2025-09-01', 79.99),
(5, 104, 1002, '2025-10-11', 199.99),
(6, 105, 1004, '2025-11-20', 349.75);

INSERT INTO summary(order_id, quantity, discount, tax) VALUES
(1, 1, 0, 18.0),
(2, 2, 10.0, 7.5),
(3, 1, 0, 28.0),
(4, 3, 5.0, 5.5),
(5, 1, 0, 15.0),
(6, 2, 20.0, 24.0);
