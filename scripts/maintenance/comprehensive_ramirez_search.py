import sqlite3
import json

def comprehensive_search():
    try:
        conn = sqlite3.connect('sgubm.db', timeout=10)
        cursor = conn.cursor()
        
        # 1. Search audit logs for ANY mention of Marcelo or 591
        print("--- SEARCHING AUDIT LOGS ---")
        query = "SELECT id, timestamp, username, operation, description FROM audit_logs WHERE description LIKE '%Marcelo%' OR description LIKE '%591%' OR description LIKE '%552%' ORDER BY timestamp DESC"
        cursor.execute(query)
        audit_entries = cursor.fetchall()
        for a in audit_entries:
            print(f"Audit ID: {a[0]} | Time: {a[1]} | User: {a[2]} | Op: {a[3]} | Desc: {a[4]}")
            
        # 2. Search deleted payments for ANY mention of Marcelo or his potential payment
        print("\n--- SEARCHING DELETED PAYMENTS ---")
        query = "SELECT id, original_id, client_id, amount, payment_date, reference, notes, deleted_at, reason FROM deleted_payments WHERE notes LIKE '%Marcelo%' OR reference LIKE '%Marcelo%' OR notes LIKE '%591%' OR reference LIKE '%591%' OR amount = 70000 ORDER BY deleted_at DESC"
        cursor.execute(query)
        deleted_entries = cursor.fetchall()
        for d in deleted_entries:
            print(f"Deleted ID: {d[0]} | Orig ID: {d[1]} | Client ID: {d[2]} | Amount: {d[3]} | Date: {d[4]} | Ref: {d[5]} | Reason: {d[8]}")

        # 3. Search for ANY payment registered today that isn't in my previous list
        print("\n--- NEW PAYMENTS TODAY ---")
        query = "SELECT p.id, p.client_id, c.legal_name, p.amount, p.payment_date FROM payments p JOIN clients c ON p.client_id = c.id WHERE p.payment_date >= '2026-02-13 14:00:00' ORDER BY p.id DESC"
        cursor.execute(query)
        recent_payments = cursor.fetchall()
        for rp in recent_payments:
            print(f"Pay ID: {rp[0]} | Client: {rp[2]} (ID: {rp[1]}) | Amt: {rp[3]} | Time: {rp[4]}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    comprehensive_search()
