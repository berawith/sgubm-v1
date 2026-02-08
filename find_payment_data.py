
import sqlite3
import json

def find_deleted_payments():
    conn = sqlite3.connect('sgubm.db')
    cursor = conn.cursor()
    
    print("--- Searching for deleted payments in audit_logs ---")
    cursor.execute("SELECT id, timestamp, description, previous_state, new_state FROM audit_logs WHERE operation = 'payment_deleted' ORDER BY timestamp DESC LIMIT 5")
    rows = cursor.fetchall()
    
    for row in rows:
        print(f"ID: {row[0]}")
        print(f"Timestamp: {row[1]}")
        print(f"Description: {row[2]}")
        print(f"Previous State: {row[3]}")
        print("-" * 30)

    print("\n--- Searching for payments with 'incomplete' in notes or description ---")
    cursor.execute("SELECT id, client_id, amount, notes, payment_date FROM payments WHERE notes LIKE '%incompleto%' OR notes LIKE '%error%' ORDER BY payment_date DESC LIMIT 5")
    rows = cursor.fetchall()
    for row in rows:
        print(f"Payment ID: {row[0]}, Client ID: {row[1]}, Amount: {row[2]}, Notes: {row[3]}, Date: {row[4]}")

    conn.close()

if __name__ == "__main__":
    find_deleted_payments()
