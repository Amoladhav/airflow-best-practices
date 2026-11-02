INSERT INTO sales (sale_id, sale_date, customer_id, amount_cents)
VALUES (:sale_id, :sale_date, :customer_id, :amount_cents)
ON CONFLICT (sale_id) DO UPDATE SET
    sale_date = excluded.sale_date,
    customer_id = excluded.customer_id,
    amount_cents = excluded.amount_cents;
