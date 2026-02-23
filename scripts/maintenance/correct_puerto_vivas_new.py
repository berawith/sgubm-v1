
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, AuditLog
from datetime import datetime

def correct_puerto_vivas():
    db = get_db()
    session = db.session
    
    # Target IDs: Marceloramirez(591), Anamunoz(592), Josemancilla(593), Carmenruiz(594)
    target_ids = [591, 592, 593, 594]
    clients = session.query(Client).filter(Client.id.in_(target_ids)).all()
    
    print(f"Correcting {len(clients)} clients in Puerto Vivas...")
    
    for c in clients:
        old_status = c.status
        old_balance = c.account_balance
        
        # Apply corrections
        c.status = 'suspended'
        c.account_balance = 70000.0  # Common fee for these clients
        
        # Log the change
        log = AuditLog(
            category='client',
            operation='client_data_correction',
            entity_type='client',
            entity_id=c.id,
            description=f"Corrección manual: {c.legal_name}. Estado: {old_status}->suspended, Balance: {old_balance}->70000.0",
            timestamp=datetime.now(),
            username='Antigravity'
        )
        session.add(log)
        print(f"Updated {c.legal_name} (ID: {c.id})")
    
    try:
        session.commit()
        print("Successfully committed changes.")
    except Exception as e:
        session.rollback()
        print(f"Error committing changes: {e}")

if __name__ == "__main__":
    correct_puerto_vivas()
