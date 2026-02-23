import sqlite3
import json
import signal

def handler(signum, frame):
    raise Exception("Query timed out")

def find_clients():
    try:
        conn = sqlite3.connect('sgubm.db', timeout=10)
        cursor = conn.cursor()
        
        # Search for Marcelo Ramirez or similar
        query = "SELECT id, legal_name, subscriber_code FROM clients WHERE legal_name LIKE '%Marcelo%Ramirez%' OR legal_name LIKE '%Ramirez%Marcelo%' OR legal_name LIKE '%Marcelo%'"
        cursor.execute(query)
        clients = cursor.fetchall()
        
        print("MATCHING CLIENTS:")
        for c in clients:
            print(f"ID: {c[0]}, Name: {c[1]}, Code: {c[2]}")
            
        # Search for any payment with "Marcelo" in notes or reference
        query = "SELECT id, client_id, amount, payment_date, reference, notes FROM payments WHERE notes LIKE '%Marcelo%' OR reference LIKE '%Marcelo%' OR notes LIKE '%Ramirez%' OR reference LIKE '%Ramirez%'"
        cursor.execute(query)
        payments = cursor.fetchall()
        
        print("\nMATCHING PAYMENTS:")
        for p in payments:
            print(f"ID: {p[0]}, Client ID: {p[1]}, Amount: {p[2]}, Date: {p[3]}, Ref: {p[4]}, Notes: {p[5]}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_clients()
