
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, AuditLog
from datetime import datetime

def fix_zulay_balance():
    db = get_db()
    session = db.session
    
    zulay = session.query(Client).filter(Client.subscriber_code == 'CLI-0330').first()
    if zulay:
        old_bal = zulay.account_balance
        zulay.account_balance = 0.0
        print(f"Setting Zulayzambrano (ID: {zulay.id}) balance from {old_bal} to 0.0")
        
        log = AuditLog(
            category='accounting',
            operation='balance_correction',
            entity_type='client',
            entity_id=zulay.id,
            description=f"Corrección final: Saldo ajustado a 0.0 ya que febrero es el primer ciclo y el pago de 90k lo cubre. (Anterior: {old_bal})",
            timestamp=datetime.now(),
            username='Antigravity'
        )
        session.add(log)
        
        try:
            session.commit()
            print("Successfully updated balance.")
        except Exception as e:
            session.rollback()
            print(f"Error: {e}")
    else:
        print("Zulay not found.")

if __name__ == "__main__":
    fix_zulay_balance()
