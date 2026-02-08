
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.infrastructure.database.db_manager import get_db
from src.application.services.billing_service import BillingService
from src.infrastructure.database.models import Client, Payment, DeletedPayment

def verify_workflow():
    db = get_db()
    session = db.session
    billing_service = BillingService()
    
    # 1. Pick a client with debt
    client = session.query(Client).filter(Client.account_balance > 0).first()
    if not client:
        print("No client with debt found for testing. Creating one...")
        # (Actually I'll just pick any client and give them debt for a moment)
        client = session.query(Client).first()
        client.account_balance = 100000
        session.commit()
    
    client_id = client.id
    initial_balance = client.account_balance
    print(f"Testing with Client ID: {client_id}, Name: {client.legal_name}, Initial Balance: {initial_balance}")
    
    # 2. Register Partial Payment (Unauthorized) - Should fail
    try:
        amount = initial_balance / 2
        print(f"Attempting partial payment of ${amount} without authorization...")
        billing_service.register_payment(client_id, amount, {'payment_method': 'cash'})
        print("FAIL: Partial payment succeeded without authorization!")
    except ValueError as e:
        if "PARTIAL_PAYMENT_REQUIRED" in str(e):
            print(f"SUCCESS: Partial payment blocked as expected. Error: {e}")
        else:
            print(f"FAIL: Unexpected error: {e}")
            
    # 3. Register Partial Payment (Authorized) - Should succeed
    try:
        print(f"Attempting partial payment of ${amount} WITH authorization...")
        payment = billing_service.register_payment(client_id, amount, {'payment_method': 'cash', 'authorized': True})
        session.refresh(client)
        print(f"SUCCESS: Payment registered. New Balance: {client.account_balance}")
        if client.account_balance != initial_balance - amount:
            print(f"FAIL: Balance mismatch! Expected {initial_balance - amount}, got {client.account_balance}")
        
        payment_id = payment.id
        
        # 4. Deletion (Archiving)
        print(f"Deleting (Archiving) payment ID: {payment_id}...")
        # We simulate the controller logic here
        from src.infrastructure.database.repositories import PaymentRepository, DeletedPaymentRepository, ClientRepository
        pay_repo = PaymentRepository(session)
        del_repo = DeletedPaymentRepository(session)
        cli_repo = ClientRepository(session)
        
        payment_obj = pay_repo.get_by_id(payment_id)
        del_repo.create_from_payment(payment_obj, deleted_by='tester', reason='Verification test')
        cli_repo.update_balance(client_id, amount, operation='add')
        pay_repo.delete(payment_id)
        
        session.refresh(client)
        print(f"SUCCESS: Payment deleted. Restored Balance: {client.account_balance}")
        if client.account_balance != initial_balance:
            print(f"FAIL: Balance mismatch! Expected {initial_balance}, got {client.account_balance}")
            
        # Check trash
        deleted_entry = session.query(DeletedPayment).filter(DeletedPayment.original_id == payment_id).first()
        if deleted_entry:
            print(f"SUCCESS: Payment found in trash. Reason: {deleted_entry.reason}")
            deleted_id = deleted_entry.id
            
            # 5. Restoration
            print(f"Restoring payment from trash ID: {deleted_id}...")
            # Simulate controller restore logic
            data = {
                'payment_method': deleted_entry.payment_method,
                'authorized': True
            }
            new_payment = billing_service.register_payment(client_id, amount, data)
            del_repo.delete(deleted_id)
            
            session.refresh(client)
            print(f"SUCCESS: Payment restored. Final Balance: {client.account_balance}")
            if client.account_balance != initial_balance - amount:
                print(f"FAIL: Balance mismatch! Expected {initial_balance - amount}, got {client.account_balance}")
        else:
            print("FAIL: Payment not found in trash!")
            
    except Exception as e:
        print(f"CRITICAL ERROR during verification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    verify_workflow()
