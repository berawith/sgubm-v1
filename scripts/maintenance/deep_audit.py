
import sqlite3
import os

def deep_financial_audit():
    db_path = "sgubm.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=== DEEP FINANCIAL AUDIT ===")
    
    # 1. Check for Duplicate Payments
    print("Checking for duplicate payments (same client, amount, date)...")
    cursor.execute("""
        SELECT client_id, amount, payment_date, reference, COUNT(*) as occurs
        FROM payments
        GROUP BY client_id, amount, payment_date, reference
        HAVING COUNT(*) > 1
    """)
    dupes = cursor.fetchall()
    if dupes:
        print(f"Found {len(dupes)} sets of potential duplicate payments.")
        for d in dupes[:5]:
            print(f"- Client {d['client_id']} | Amt: {d['amount']} | Date: {d['payment_date']} | Ref: {d['reference']} | Occurs: {d['occurs']}")
    else:
        print("No duplicate payments found by Exact Match.")
    
    # 2. Check for Invoice/Balance Mismatch (Historical)
    print("\nChecking Historical Balance Mismatch (TotalInvoices - TotalPayments vs AccountBalance)...")
    # We ignore the 'reset' logic here to see the TRUE historical debt
    cursor.execute("""
        SELECT c.id, c.legal_name, c.account_balance,
               IFNULL((SELECT SUM(total_amount) FROM invoices WHERE client_id = c.id AND status != 'cancelled'), 0) as total_invoiced,
               IFNULL((SELECT SUM(amount) FROM payments WHERE client_id = c.id AND status != 'cancelled'), 0) as total_paid
        FROM clients c
        LIMIT 20
    """)
    rows = cursor.fetchall()
    for r in rows:
        expected = r['total_invoiced'] - r['total_paid']
        actual = r['account_balance']
        diff = actual - expected
        if abs(diff) > 0.01:
            print(f"ID {r['id']:3} | {r['legal_name']:30} | Expected (Inv-Paid): ${expected:10.2f} | Actual: ${actual:10.2f} | Diff: ${diff:10.2f}")

    # 3. Check for Payments without Invoice markers
    print("\nPayments not linked to any 'paid' invoice status (potential orphaned payments in terms of FIFO)...")
    # This is harder to check via SQL, but we can look for clients with balance > 0 while they have high payments
    
    # 4. Clients with NEGATIVE balance (Credit)
    print("\nClients with Significant Credit (Negative Balance):")
    cursor.execute("SELECT id, legal_name, account_balance FROM clients WHERE account_balance < -100")
    rows = cursor.fetchall()
    for r in rows:
        print(f"ID {r['id']} | {r['legal_name']:30} | Credit: ${-r['account_balance']:10.2f}")

    conn.close()

if __name__ == "__main__":
    deep_financial_audit()
