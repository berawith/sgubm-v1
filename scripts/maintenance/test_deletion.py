
import sqlite3
import os

def test_deletion():
    db_path = "sgubm.db"
    conn = sqlite3.connect(db_path)
    # Enable FKs manually for sqlite3 (testing if the PRAGMA works)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()
    
    print("=== TESTING CLIENT DELETION WITH CASCADE ===")
    
    # Create test client
    try:
        cursor.execute("INSERT INTO clients (router_id, subscriber_code, legal_name, username, status) VALUES (1, 'TEST-DEL-1', 'Test Deletion', 'testdel', 'active')")
        client_id = cursor.lastrowid
        print(f"Created Test Client ID: {client_id}")
        
        # Add dependencies
        cursor.execute("INSERT INTO invoices (client_id, issue_date, due_date, total_amount, status) VALUES (?, '2026-02-01', '2026-02-15', 70000, 'unpaid')", (client_id,))
        print("Added invoice.")
        
        cursor.execute("INSERT INTO client_traffic_history (client_id, timestamp, download_bps, upload_bps) VALUES (?, '2026-02-11 10:00:00', 1000, 500)", (client_id,))
        print("Added traffic history.")
        
        # Now try to delete
        print(f"Attempting to delete client {client_id}...")
        cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        print("Delete command executed successfully.")
        
        # Verify cascades
        cursor.execute("SELECT COUNT(*) FROM invoices WHERE client_id = ?", (client_id,))
        inv_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM client_traffic_history WHERE client_id = ?", (client_id,))
        traff_count = cursor.fetchone()[0]
        
        if inv_count == 0 and traff_count == 0:
            print("VERIFICATION SUCCESS: All dependencies were cascaded.")
        else:
            print(f"VERIFICATION FAILURE: Records remain! Invoices: {inv_count}, Traffic: {traff_count}")
            
        conn.commit()
    except Exception as e:
        print(f"Deletion Test Failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    test_deletion()
