import sqlite3
import json
from datetime import datetime

def get_history(client_id):
    conn = sqlite3.connect('sgubm.db')
    cursor = conn.cursor()
    
    # Payments
    cursor.execute("SELECT id, amount, payment_date, reference, notes, status FROM payments WHERE client_id = ? ORDER BY payment_date DESC", (client_id,))
    payments = cursor.fetchall()
    
    # Invoices
    cursor.execute("SELECT id, total_amount, issue_date, due_date, status FROM invoices WHERE client_id = ? ORDER BY issue_date DESC", (client_id,))
    invoices = cursor.fetchall()
    
    # Deleted Payments (check if some payment was deleted)
    cursor.execute("SELECT id, amount, payment_date, reference, notes, deleted_at, reason FROM deleted_payments WHERE client_id = ? ORDER BY deleted_at DESC", (client_id,))
    deleted = cursor.fetchall()

    history = {
        "payments": [],
        "invoices": [],
        "deleted_payments": []
    }
    
    for p in payments:
        history["payments"].append({
            "id": p[0],
            "amount": p[1],
            "payment_date": p[2],
            "reference": p[3],
            "notes": p[4],
            "status": p[5]
        })
        
    for i in invoices:
        history["invoices"].append({
            "id": i[0],
            "total_amount": i[1],
            "issue_date": i[2],
            "due_date": i[3],
            "status": i[4]
        })
        
    for d in deleted:
        history["deleted_payments"].append({
            "id": d[0],
            "amount": d[1],
            "payment_date": d[2],
            "reference": d[3],
            "notes": d[4],
            "deleted_at": d[5],
            "reason": d[6]
        })
        
    print(json.dumps(history, indent=2))
    conn.close()

if __name__ == "__main__":
    get_history(591)
