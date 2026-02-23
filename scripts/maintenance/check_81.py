
import sqlite3
import os

def check_client_81():
    db_path = "sgubm.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== HISTORY FOR CLIENT 81 (Ana Castro) ===")
    
    cursor.execute("SELECT * FROM clients WHERE id = 81")
    client = cursor.fetchone()
    print(f"Client Info: {dict(client)}")
    
    print("\n--- INVOICES ---")
    cursor.execute("SELECT * FROM invoices WHERE client_id = 81")
    invoices = cursor.fetchall()
    for inv in invoices:
        print(dict(inv))
        
    print("\n--- PAYMENTS ---")
    cursor.execute("SELECT * FROM payments WHERE client_id = 81")
    payments = cursor.fetchall()
    for pay in payments:
        print(dict(pay))
        
    print("\n--- DELETED PAYMENTS ---")
    cursor.execute("SELECT * FROM deleted_payments WHERE client_id = 81")
    deleted = cursor.fetchall()
    for d in deleted:
        print(dict(d))

    conn.close()

if __name__ == "__main__":
    check_client_81()
