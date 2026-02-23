
import sqlite3
import os

def run_sqlite_audit():
    db_path = "sgubm.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=== SQLITE FINANCIAL AUDIT REPORT ===")
        
        # 1. Counts
        cursor.execute("SELECT COUNT(*) FROM clients")
        total_clients = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payments")
        total_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM invoices")
        total_invoices = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE status = 'unpaid'")
        unpaid_invoices = cursor.fetchone()[0]
        
        print(f"Total Clients: {total_clients}")
        print(f"Total Payments: {total_payments}")
        print(f"Total Invoices: {total_invoices}")
        print(f"Total Unpaid Invoices: {unpaid_invoices}")
        
        # 2. Balance Sum
        cursor.execute("SELECT SUM(account_balance) FROM clients")
        total_balance = cursor.fetchone()[0] or 0
        print(f"Total Portfolio Balance (Sum of account_balance): ${total_balance:,.2f}")
        
        # 3. Sum of Unpaid Invoices
        cursor.execute("SELECT SUM(total_amount) FROM invoices WHERE status = 'unpaid'")
        sum_unpaid = cursor.fetchone()[0] or 0
        print(f"Sum of Unpaid Invoices: ${sum_unpaid:,.2f}")
        
        diff_total = total_balance - sum_unpaid
        print(f"Global Discrepancy (Balance - UnpaidSum): ${diff_total:,.2f}")
        print("-" * 30)
        
        # 4. Top 10 Discrepancies
        print("Top 10 Client Discrepancies:")
        cursor.execute("""
            SELECT c.id, c.legal_name, c.account_balance, 
                   (SELECT SUM(i.total_amount) FROM invoices i WHERE i.client_id = c.id AND i.status = 'unpaid') as unpaid_sum
            FROM clients c
            WHERE abs(c.account_balance - IFNULL((SELECT SUM(total_amount) FROM invoices WHERE client_id = c.id AND status = 'unpaid'), 0)) > 0.01
            ORDER BY abs(c.account_balance - IFNULL((SELECT SUM(total_amount) FROM invoices WHERE client_id = c.id AND status = 'unpaid'), 0)) DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        for r in rows:
            ub = r['account_balance']
            us = r['unpaid_sum'] or 0
            diff = ub - us
            print(f"ID {r['id']} | {r['legal_name']:30} | Bal: ${ub:10.2f} | Unpaid: ${us:10.2f} | Diff: ${diff:10.2f}")
            
        print("-" * 30)
        
        # 5. Suspended clients with 0 balance (Potential restoration candidates)
        print("Suspended Clients with $0 or Negative Balance:")
        cursor.execute("SELECT id, legal_name, account_balance FROM clients WHERE status = 'suspended' AND account_balance <= 0")
        rows = cursor.fetchall()
        for r in rows:
            print(f"ID {r['id']} | {r['legal_name']:30} | Bal: ${r['account_balance']:10.2f}")
        
        print("-" * 30)
        
        # 6. Active clients with high debt (> 2 months fee)
        print("Active Clients with High Debt (Potential suspension candidates):")
        # Estimate debt by comparing balance with monthly_fee
        cursor.execute("SELECT id, legal_name, account_balance, monthly_fee FROM clients WHERE status = 'active' AND account_balance > (monthly_fee * 1.5) AND monthly_fee > 0 LIMIT 10")
        rows = cursor.fetchall()
        for r in rows:
             print(f"ID {r['id']} | {r['legal_name']:30} | Bal: ${r['account_balance']:10.2f} | Fee: ${r['monthly_fee']:10.2f}")

        print("-" * 30)
        
        # 7. Recent accounting logs
        print("Last 10 Accounting Logs:")
        cursor.execute("SELECT timestamp, operation, description FROM audit_logs WHERE category = 'accounting' ORDER BY timestamp DESC LIMIT 10")
        rows = cursor.fetchall()
        for r in rows:
            print(f"[{r['timestamp']}] {r['operation']:20} | {r['description']}")
            
        conn.close()
    except Exception as e:
        print(f"Audit Error: {e}")

if __name__ == "__main__":
    run_sqlite_audit()
