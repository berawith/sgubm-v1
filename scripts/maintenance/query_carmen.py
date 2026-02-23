import sqlite3
import os

db_path = 'sgubm.db'
conn = sqlite3.connect(db_path, timeout=10)
cursor = conn.cursor()
try:
    cursor.execute("SELECT id, legal_name, account_balance FROM clients WHERE subscriber_code = 'CLI-0555'")
    row = cursor.fetchone()
    if row:
        print(f"ID:{row[0]}, NAME:{row[1]}, BAL:{row[2]}")
    else:
        print("CLIENT_NOT_FOUND")
        
    cursor.execute("SELECT id, amount, deleted_at FROM deleted_payments WHERE client_id = (SELECT id FROM clients WHERE subscriber_code = 'CLI-0555') ORDER BY deleted_at DESC LIMIT 1")
    row = cursor.fetchone()
    if row:
        print(f"DELETED_ID:{row[0]}, AMT:{row[1]}, AT:{row[2]}")
    else:
        print("NO_RECENT_DELETED_PAYMENT")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    conn.close()
