
import sqlite3
import os

def check_client_9():
    db_path = "sgubm.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== HISTORY FOR CLIENT 9 (Josevillamizar) ===")
    
    cursor.execute("SELECT * FROM clients WHERE id = 9")
    client = cursor.fetchone()
    print(f"Client Info: {dict(client)}")
    
    print("\n--- INVOICES ---")
    cursor.execute("SELECT * FROM invoices WHERE client_id = 9")
    invoices = cursor.fetchall()
    for inv in invoices:
        print(dict(inv))
        
    print("\n--- PAYMENTS ---")
    cursor.execute("SELECT * FROM payments WHERE client_id = 9")
    payments = cursor.fetchall()
    for pay in payments:
        print(dict(pay))
    
    print("\n--- AUDIT LOGS FOR CLIENT 9 ---")
    cursor.execute("SELECT * FROM audit_logs WHERE entity_id = 9 AND entity_type = 'client' ORDER BY timestamp DESC")
    logs = cursor.fetchall()
    for log in logs:
        print(dict(log))

    conn.close()

if __name__ == "__main__":
    check_client_9()
