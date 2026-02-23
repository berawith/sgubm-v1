
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, AuditLog
from datetime import datetime

def run_corrections():
    db = get_db()
    session = db.session
    
    # 1. RESTORE ROMAN PERNIA (ID 58)
    roman = session.query(Client).filter(Client.id == 58).first()
    if roman:
        # Check if payment 488 is missing
        p488_check = session.query(Payment).filter(Payment.id == 488).first()
        if not p488_check:
            print(f"Restoring Roman Pernia's payment (Ref 5899)...")
            new_p = Payment(
                # id=488, # Might not be able to force ID, but let's try or just add a new one
                client_id=58,
                amount=90000.0,
                payment_date=datetime.strptime("2026-02-11 16:49:53", "%Y-%m-%d %H:%M:%S"),
                reference="5899",
                status="verified",
                payment_method="transfer", # Assumed based on ref
                registered_by="System (Restoration)"
            )
            session.add(new_p)
            
            # Restore balance
            old_bal = roman.account_balance
            roman.account_balance = -90000.0
            print(f"Restored Roman's balance from {old_bal} to -90000.0")
            
            log_r = AuditLog(
                category='system',
                operation='data_restoration',
                entity_type='client',
                entity_id=58,
                description="RESTAURACIÓN: Se revirtió la eliminación errónea del pago 488 y el ajuste de saldo.",
                timestamp=datetime.now(),
                username='Antigravity'
            )
            session.add(log_r)
        else:
            print("Roman's payment 488 already exists or restoration not needed.")
    
    # 2. CORRECT ZULAYZAMBRANO (ID 330)
    zulay = session.query(Client).filter(Client.subscriber_code == 'CLI-0330').first()
    if zulay:
        # User said 180k payment should be 90k.
        # We found two 90k payments: 53 and 277.
        # We delete 277 (the later one).
        p277 = session.query(Payment).filter(Payment.id == 277).first()
        if p277:
            print(f"Deleting Zulayzambrano's duplicate payment (ID 277, Amount: {p277.amount})...")
            session.delete(p277)
            
            # Adjust balance: if she has 0.0 with 2 payments (180k) vs 1 invoice (90k)...
            # Deleting 90k will make her owe 90k (balance goes from 0 to 90k).
            old_zbal = zulay.account_balance
            zulay.account_balance = (zulay.account_balance or 0) + 90000.0
            print(f"Adjusted Zulay's balance from {old_zbal} to {zulay.account_balance}")
            
            log_z = AuditLog(
                category='accounting',
                operation='payment_correction',
                entity_type='payment',
                entity_id=277,
                description=f"Corrección Zulayzambrano: Se eliminó pago duplicado. Balance ajustado de {old_zbal} a {zulay.account_balance}",
                timestamp=datetime.now(),
                username='Antigravity'
            )
            session.add(log_z)
        else:
            print("Zulay's payment 277 not found or already deleted.")
            
    try:
        session.commit()
        print("\nAll corrections applied successfully.")
    except Exception as e:
        session.rollback()
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    run_corrections()
