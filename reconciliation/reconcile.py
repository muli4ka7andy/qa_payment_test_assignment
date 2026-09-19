import csv
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_csv(connection, table, path, columns):
    placeholders = ",".join("?" for _ in columns)
    with path.open(newline="", encoding="utf-8") as source:
        rows = csv.DictReader(source)
        connection.executemany(
            "INSERT INTO %s (%s) VALUES (%s)" % (table, ",".join(columns), placeholders),
            ([row[column] for column in columns] for row in rows),
        )


def main():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE our_records (
            payment_id TEXT, ref TEXT, corridor TEXT, amount INTEGER,
            currency TEXT, status TEXT, created_at TEXT
        );
        CREATE TABLE partner_statement (
            ref TEXT, amount INTEGER, currency TEXT, status TEXT, settled_at TEXT
        );
        """
    )
    load_csv(
        connection,
        "our_records",
        ROOT / "recon_our_records (2).csv",
        ("payment_id", "ref", "corridor", "amount", "currency", "status", "created_at"),
    )
    load_csv(
        connection,
        "partner_statement",
        ROOT / "recon_partner_statement.csv",
        ("ref", "amount", "currency", "status", "settled_at"),
    )

    report = {
        "partner_only": [row[0] for row in connection.execute(
            "SELECT p.ref FROM partner_statement p LEFT JOIN our_records o ON o.ref=p.ref "
            "WHERE o.ref IS NULL GROUP BY p.ref ORDER BY p.ref"
        )],
        "our_only": [row[0] for row in connection.execute(
            "SELECT o.ref FROM our_records o LEFT JOIN partner_statement p ON p.ref=o.ref "
            "WHERE p.ref IS NULL ORDER BY o.ref"
        )],
        "duplicate_partner_refs": [row[0] for row in connection.execute(
            "SELECT ref FROM partner_statement GROUP BY ref HAVING COUNT(*) > 1 ORDER BY ref"
        )],
        "field_mismatches": [dict(row) for row in connection.execute(
            """SELECT o.ref, o.amount AS our_amount, p.amount AS partner_amount,
                      o.currency AS our_currency, p.currency AS partner_currency,
                      o.status AS our_status, p.status AS partner_status
               FROM our_records o JOIN partner_statement p ON p.ref=o.ref
               WHERE o.amount <> p.amount OR o.currency <> p.currency OR o.status <> p.status
               ORDER BY o.ref"""
        )],
    }
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()