import sys
import os
sys.path.append('.')
from src.infrastructure.database.db_manager import DatabaseManager
from src.application.services.billing_service import BillingService
from src.infrastructure.database.models import Client, Payment

db = DatabaseManager()
session = db.session
billing_service = BillingService()
client_repo = db.get_client_repository()
payment_repo = db.get_payment_repository()

client_id = 594
amount = 10000

try:
    client = client_repo.get_by_id(client_id)
    initial_bal = client.account_balance
    print(f"Initial Balance: {initial_bal}")

    # 1. Register
    print("Registering payment...")
    p = billing_service.register_payment(client_id, amount, {'payment_method': 'cash', 'notes': 'VERIFY_MANUAL', 'authorized': True})
    session.commit()
    p_id = p.id
    bal_after = client_repo.get_by_id(client_id).account_balance
    print(f"Balance after pay: {bal_after}")

    # 2. Delete
    print(f"Deleting payment {p_id}...")
    payment_repo.delete(p_id, commit=False)
    client_repo.update_balance(client_id, amount, operation='add', commit=False)
    session.commit()

    final_bal = client_repo.get_by_id(client_id).account_balance
    print(f"Final Balance: {final_bal}")
    
    if final_bal == initial_bal:
        print("VERIFICATION SUCCESSFUL!")
    else:
        print(f"VERIFICATION FAILED: {final_bal} != {initial_bal}")
except Exception as e:
    print(f"ERROR: {e}")
    session.rollback()
finally:
    db.remove_session()
