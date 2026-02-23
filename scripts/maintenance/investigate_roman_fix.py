
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment
from sqlalchemy import or_

def investigate_roman():
    db = get_db()
    session = db.session
    
    # Search for Roman (name likely Roman Pernia or similar based on previous context)
    roman = session.query(Client).filter(Client.legal_name.ilike('%Roman%')).first()
    
    if not roman:
        print("Client 'Roman' not found.")
        return
        
    print(f"--- Client Found: {roman.legal_name} (ID: {roman.id}) ---")
    print(f"Current Balance: {roman.account_balance}")
    print(f"Status: {roman.status}")
    
    # Check payments
    payments = session.query(Payment).filter(Payment.client_id == roman.id).order_by(Payment.payment_date.desc()).all()
    print(f"\n--- Payment History (Last 5) ---")
    for p in payments[:5]:
        print(f"ID: {p.id}, Amount: {p.amount}, Date: {p.payment_date}, Status: {p.status}, Ref: {p.reference}")

if __name__ == "__main__":
    investigate_roman()
