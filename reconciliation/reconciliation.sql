-- SQL-запросы для сверки наших записей с выпиской партнёра.
-- Таблицы our_records и partner_statement предварительно загружаются из CSV.
-- Ключ сопоставления — ref. Дубликаты партнёра намеренно сохраняются в отчёте.

-- Операции только у партнёра и дубликаты в его выписке.
SELECT p.ref, p.amount, p.currency, p.status
FROM partner_statement AS p
LEFT JOIN our_records AS o ON o.ref = p.ref
WHERE o.ref IS NULL
   OR p.ref IN (
       SELECT ref FROM partner_statement GROUP BY ref HAVING COUNT(*) > 1
   );

-- Операции, которые есть у нас, но отсутствуют у партнёра.
SELECT o.payment_id, o.ref, o.amount, o.currency, o.status
FROM our_records AS o
LEFT JOIN partner_statement AS p ON p.ref = o.ref
WHERE p.ref IS NULL;

-- Расхождения суммы, валюты или статуса по одинаковому ref.
SELECT o.ref,
       o.amount AS our_amount,
       p.amount AS partner_amount,
       o.currency AS our_currency,
       p.currency AS partner_currency,
       o.status AS our_status,
       p.status AS partner_status
FROM our_records AS o
JOIN partner_statement AS p ON p.ref = o.ref
WHERE o.amount <> p.amount
   OR o.currency <> p.currency
   OR o.status <> p.status;

-- Расхождения дат создания и расчёта.
SELECT o.ref,
       o.created_at,
       p.settled_at,
       julianday(p.settled_at) - julianday(o.created_at) AS days_between
FROM our_records AS o
JOIN partner_statement AS p ON p.ref = o.ref
WHERE o.created_at <> p.settled_at;