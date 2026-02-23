
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment

def verify_final():
    db = get_db()
    session = db.session
    
    # Check Roman (ID 58)
    roman = session.query(Client).filter(Client.id == 58).first()
    r_payments = session.query(Payment).filter(Payment.client_id == 58).all()
    print(f"--- Roman Pernia (ID 58) ---")
    print(f"Balance: {roman.account_balance}")
    print(f"Payments Count: {len(r_payments)}")
    for p in r_payments:
        print(f" - Payment ID: {p.id}, Ref: {p.reference}, Amount: {p.amount}")
        
    # Check Zulay (CLI-0330 / ID 330)
    zulay = session.query(Client).filter(Client.subscriber_code == 'CLI-0330').first()
    z_payments = session.query(Payment).filter(Payment.client_id == zulay.id).all()
    print(f"\n--- Zulayzambrano (ID {zulay.id}) ---")
    print(f"Balance: {zulay.account_balance}")
    print(f"Payments Count: {len(z_payments)}")
    for p in z_payments:
        print(f" - Payment ID: {p.id}, Ref: {p.reference}, Amount: {p.amount}")

if __name__ == "__main__":
    verify_final()
