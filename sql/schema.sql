CREATE TABLE IF NOT EXISTS sales (
    sale_id INTEGER PRIMARY KEY CHECK (sale_id > 0),
    sale_date TEXT NOT NULL,
    customer_id TEXT NOT NULL CHECK (length(trim(customer_id)) > 0),
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0)
);
