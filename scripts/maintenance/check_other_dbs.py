
import sqlite3

def check_db(db_name):
    print(f"\n--- REVISANDO {db_name} ---")
    try:
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT id, legal_name, account_balance FROM clients WHERE legal_name LIKE '%Roman Pernia%'")
        rows = cursor.fetchall()
        for row in rows:
            print(f"ID: {row[0]} | Name: {row[1]} | Balance: {row[2]}")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

check_db('sgubm_unlocked.db')
check_db('sgubm_audit.db')
