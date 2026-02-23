
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import Client, Invoice, ClientTrafficHistory, PendingOperation
from sqlalchemy import text

def test_sqlalchemy_deletion():
    db = DatabaseManager()
    session = db.session
    
    print("=== TESTING CLIENT DELETION WITH SQLALCHEMY CASCADE ===")
    
    try:
        # Create test client
        test_client = Client(
            router_id=1,
            subscriber_code='TEST-SA-1',
            legal_name='Test SQLAlchemy Deletion',
            username='testsa',
            status='active'
        )
        session.add(test_client)
        session.flush()
        client_id = test_client.id
        print(f"Created Test Client ID: {client_id}")
        
        # Add dependencies
        inv = Invoice(client_id=client_id, issue_date=text("datetime('now')"), due_date=text("datetime('now')"), total_amount=70000, status='unpaid')
        traff = ClientTrafficHistory(client_id=client_id, timestamp=text("datetime('now')"), download_bps=1000, upload_bps=500)
        pending = PendingOperation(client_id=client_id, router_id=1, operation_type='suspend', status='pending')
        
        session.add(inv)
        session.add(traff)
        session.add(pending)
        session.commit()
        print("Added dependencies (Invoice, Traffic, PendingOp).")
        
        # Now try to delete via SQLAlchemy
        print(f"Attempting to delete client {client_id} via session.delete()...")
        client_to_del = session.query(Client).get(client_id)
        session.delete(client_to_del)
        session.commit()
        print("Delete command executed successfully.")
        
        # Verify
        inv_count = session.query(Invoice).filter_by(client_id=client_id).count()
        traff_count = session.query(ClientTrafficHistory).filter_by(client_id=client_id).count()
        pending_count = session.query(PendingOperation).filter_by(client_id=client_id).count()
        
        if inv_count == 0 and traff_count == 0 and pending_count == 0:
            print("VERIFICATION SUCCESS: SQLAlchemy handled cascades (including PendingOp) correctly.")
        else:
            print(f"VERIFICATION FAILURE: Records remain! Invoices: {inv_count}, Traffic: {traff_count}, Pending: {pending_count}")
            
    except Exception as e:
        session.rollback()
        print(f"Deletion Test Failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    test_sqlalchemy_deletion()
