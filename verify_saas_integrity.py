
import sqlite3
import os

def check_integrity():
    db_path = 'sgubm.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    checks = {
        "Tenants": "SELECT count(*) FROM tenants",
        "Main Tenant": "SELECT id, name FROM tenants WHERE subdomain = 'main'",
        "Users in Main": "SELECT count(*) FROM users WHERE tenant_id = 1",
        "Clients in Main": "SELECT count(*) FROM clients WHERE tenant_id = 1",
        "Payments in Main": "SELECT count(*) FROM payments WHERE tenant_id = 1",
        "Support Tickets in Main": "SELECT count(*) FROM support_tickets WHERE tenant_id = 1",
        "Unassigned Users": "SELECT count(*) FROM users WHERE tenant_id IS NULL",
        "Unassigned Clients": "SELECT count(*) FROM clients WHERE tenant_id IS NULL"
    }

    print("--- SGUBM Multi-Tenancy Integrity Check ---")
    for description, query in checks.items():
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            print(f"{description}: {result[0] if result else 'N/A'}")
        except Exception as e:
            print(f"{description}: ERROR ({e})")

    conn.close()

if __name__ == "__main__":
    check_integrity()
