
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, AuditLog
from datetime import datetime

def investigate_and_restore():
    db = get_db()
    session = db.session
    
    # 1. Investigate Zulayzambrano
    zulay = session.query(Client).filter(Client.subscriber_code == 'CLI-0330').first()
    if zulay:
        print(f"--- Client Found: {zulay.legal_name} (ID: {zulay.id}) ---")
        print(f"Current Balance: {zulay.account_balance}")
        payments = session.query(Payment).filter(Payment.client_id == zulay.id).order_by(Payment.payment_date.desc()).all()
        print(f"\n--- Zulay's Payment History ---")
        for p in payments:
            print(f"ID: {p.id}, Amount: {p.amount}, Date: {p.payment_date}, Ref: {p.reference}, Status: {p.status}")
    else:
        print("Zulayzambrano (CLI-0330) not found.")

    # 2. Check Roman Pernia (ID 58) - I deleted payment 488
    # I should restore it if the user says they didn't ask for it.
    # Actually, I'll wait to restore until I'm sure, but I'll see what the status is.
    roman = session.query(Client).filter(Client.id == 58).first()
    if roman:
        print(f"\n--- Roman Pernia (ID 58) Status ---")
        print(f"Balance: {roman.account_balance}")
        # Check if payment 488 is actually gone
        p488 = session.query(Payment).filter(Payment.id == 488).first()
        print(f"Payment 488 exists: {p488 is not None}")

if __name__ == "__main__":
    investigate_and_restore()
