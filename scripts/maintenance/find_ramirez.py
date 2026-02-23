import sqlite3
import json

def find_client():
    conn = sqlite3.connect('sgubm.db')
    cursor = conn.cursor()
    
    query = "SELECT id, legal_name, subscriber_code, status, account_balance, due_date FROM clients WHERE legal_name LIKE '%Ramirez%'"
    cursor.execute(query)
    clients = cursor.fetchall()
    
    results = []
    for c in clients:
        results.append({
            "id": c[0],
            "legal_name": c[1],
            "subscriber_code": c[2],
            "status": c[3],
            "account_balance": c[4],
            "due_date": c[5]
        })
    
    print(json.dumps(results, indent=2))
    conn.close()

if __name__ == "__main__":
    find_client()
