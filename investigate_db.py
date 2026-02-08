import sqlite3
import os

try:
    conn = sqlite3.connect('sgubm.db')
    c = conn.cursor()
    with open('db_dump_investigation.txt', 'w', encoding='utf-8') as f:
        f.write("--- Client 248 ---\n")
        c.execute('SELECT id, legal_name, subscriber_code, account_balance FROM clients WHERE id = 248')
        f.write(str(c.fetchone()) + "\n\n")
        
        f.write("--- Recent Payments ---\n")
        c.execute('SELECT id, amount, reference, client_id, payment_date FROM payments ORDER BY id DESC LIMIT 50')
        for r in c.fetchall():
            f.write(str(r) + "\n")
            
        f.write("\n--- Maria Flores Alcedo Payments ---\n")
        c.execute('SELECT id, amount, reference, payment_date FROM payments WHERE client_id = 248')
        for r in c.fetchall():
            f.write(str(r) + "\n")
            
    conn.close()
    print("Investigation dump complete.")
except Exception as e:
    print(f"Error: {e}")
