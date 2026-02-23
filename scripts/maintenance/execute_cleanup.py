
import sqlite3
import os
from datetime import datetime

def run_cleanup():
    db_path = "sgubm.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("=== EXECUTING FINANCIAL CLEANUP ===")
        
        # 1. DELETE DUPLICATE INVOICES for Feb 2026
        # We keep the oldest one for each client/issue_date
        print("Cleaning up duplicate Feb 2026 invoices...")
        cursor.execute("""
            DELETE FROM invoices 
            WHERE id NOT IN (
                SELECT MIN(id) 
                FROM invoices 
                WHERE issue_date LIKE '2026-02%'
                GROUP BY client_id, issue_date
            )
            AND issue_date LIKE '2026-02%'
        """)
        print(f"Removed {cursor.rowcount} duplicate invoices.")
        
        # 2. CORRECT CLIENT 81 (Ana Castro)
        print("Correcting Client 81 (Ana Castro) balance...")
        # Check the payment first
        cursor.execute("SELECT id, amount FROM payments WHERE client_id = 81 AND amount = 900000")
        pay = cursor.fetchone()
        if pay:
            print(f"Found wrong payment {pay['id']} with amount {pay['amount']}. Correcting to 90000.")
            cursor.execute("UPDATE payments SET amount = 90000 WHERE id = ?", (pay['id'],))
            print("Payment corrected.")
        
        # Recalculate balance for Client 81
        cursor.execute("""
            SELECT 
                (SELECT SUM(total_amount) FROM invoices WHERE client_id = 81 AND status != 'cancelled') as invoiced,
                (SELECT SUM(amount) FROM payments WHERE client_id = 81 AND status != 'cancelled') as paid
        """)
        stats = cursor.fetchone()
        new_balance = (stats['invoiced'] or 0) - (stats['paid'] or 0)
        cursor.execute("UPDATE clients SET account_balance = ? WHERE id = 81", (new_balance,))
        print(f"Client 81 balance adjusted to ${new_balance:,.2f}")

        # 3. RECONCILE CLIENT 9 (Josevillamizar)
        print("Reconciling Client 9 (Josevillamizar)...")
        cursor.execute("""
            SELECT 
                (SELECT SUM(total_amount) FROM invoices WHERE client_id = 9 AND status != 'cancelled') as invoiced,
                (SELECT SUM(amount) FROM payments WHERE client_id = 9 AND status != 'cancelled') as paid
        """)
        stats9 = cursor.fetchone()
        new_balance9 = (stats9['invoiced'] or 0) - (stats9['paid'] or 0)
        # Note: If negative, we might want to set to 0 if the user prefers "non-cumulative"
        # but here we follow the TRUE debt logic as requested for cleanup.
        cursor.execute("UPDATE clients SET account_balance = ? WHERE id = 9", (new_balance9,))
        print(f"Client 9 balance adjusted to ${new_balance9:,.2f} (Invoiced: {stats9['invoiced']}, Paid: {stats9['paid']})")

        # 4. GLOBAL OPTIMIZATION: Fix all clients where balance is 0 but have unpaid invoices
        # or vice versa (Simple sync)
        print("Syncing other discrepancies...")
        cursor.execute("""
            UPDATE clients 
            SET account_balance = (
                SELECT IFNULL(SUM(total_amount), 0) FROM invoices WHERE client_id = clients.id AND status = 'unpaid'
            )
            WHERE id IN (455, 457, 543, 292, 86) -- Identifying the most problematic from audit
        """)
        print(f"Synced {cursor.rowcount} additional clients.")

        conn.commit()
        print("Cleanup complete.")
        conn.close()
    except Exception as e:
        print(f"Cleanup Error: {e}")

if __name__ == "__main__":
    run_cleanup()
