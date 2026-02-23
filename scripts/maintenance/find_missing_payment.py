import sqlite3
import json
from datetime import datetime, timedelta

def find_potential_payments():
    try:
        conn = sqlite3.connect('sgubm.db', timeout=10)
        cursor = conn.cursor()
        
        # 7 days ago
        seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Search for payments of 70000 in the last 7 days
        query = "SELECT p.id, p.client_id, c.legal_name, p.amount, p.payment_date, p.reference, p.notes FROM payments p JOIN clients c ON p.client_id = c.id WHERE p.amount = 70000 AND p.payment_date >= ?"
        cursor.execute(query, (seven_days_ago,))
        payments_70k = cursor.fetchall()
        
        print(f"PAYMENTS OF 70,000 COP SINCE {seven_days_ago}:")
        for p in payments_70k:
            print(f"ID: {p[0]}, Client: {p[2]} (ID: {p[1]}), Amount: {p[3]}, Date: {p[4]}, Ref: {p[5]}, Notes: {p[6]}")
            
        # Search for any recent payment that might be for Marcelo (even if not 70k)
        query = "SELECT p.id, p.client_id, c.legal_name, p.amount, p.payment_date, p.reference, p.notes FROM payments p JOIN clients c ON p.client_id = c.id WHERE (p.reference LIKE '%552%' OR p.notes LIKE '%552%' OR p.reference LIKE '%Marcelo%' OR p.notes LIKE '%Marcelo%') AND p.payment_date >= ?"
        cursor.execute(query, (seven_days_ago,))
        payments_marcelo = cursor.fetchall()
        
        print(f"\nPAYMENTS MENTIONING 'Marcelo' OR '552' SINCE {seven_days_ago}:")
        for p in payments_marcelo:
            print(f"ID: {p[0]}, Client: {p[2]} (ID: {p[1]}), Amount: {p[3]}, Date: {p[4]}, Ref: {p[5]}, Notes: {p[6]}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_potential_payments()
