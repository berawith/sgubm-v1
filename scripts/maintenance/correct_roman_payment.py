
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, AuditLog
from datetime import datetime

def correct_roman_payment():
    db = get_db()
    session = db.session
    
    # Target: Roman Pernia (ID 58)
    # Erroneous Payment ID: 488 (Ref 5899)
    payment_to_delete = session.query(Payment).filter(Payment.id == 488).first()
    roman = session.query(Client).filter(Client.id == 58).first()
    
    if not payment_to_delete:
        print("Payment 488 not found.")
        return
        
    print(f"Deleting payment 488 (Ref: {payment_to_delete.reference}, Amount: {payment_to_delete.amount})...")
    session.delete(payment_to_delete)
    
    if roman:
        old_balance = roman.account_balance
        roman.account_balance = 0.0
        print(f"Reset Roman's balance from {old_balance} to 0.0")
        
        # Log the correction
        log = AuditLog(
            category='accounting',
            operation='payment_correction',
            entity_type='payment',
            entity_id=488,
            description=f"Eliminación de pago duplicado para Roman Pernia. Balance ajustado de {old_balance} a 0.0",
            timestamp=datetime.now(),
            username='Antigravity'
        )
        session.add(log)
    
    try:
        session.commit()
        print("Successfully corrected Roman's data.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")

if __name__ == "__main__":
    correct_roman_payment()
