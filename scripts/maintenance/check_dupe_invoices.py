
import sqlite3
import os

def check_duplicate_invoices():
    db_path = "sgubm.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== DUPLICATE INVOICES AUDIT (Feb 2026) ===")
    
    cursor.execute("""
        SELECT client_id, COUNT(*) as invoice_count, SUM(total_amount) as total_amount
        FROM invoices
        WHERE issue_date LIKE '2026-02%'
        GROUP BY client_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    rows = cursor.fetchall()
    print(f"Found {len(rows)} clients with duplicate invoices for Feb 2026.")
    for r in rows:
        print(f"Client ID {r['client_id']:3} | Count: {r['invoice_count']:3} | Total Amount: ${r['total_amount']:10.2f}")
        
    conn.close()

if __name__ == "__main__":
    check_duplicate_invoices()
