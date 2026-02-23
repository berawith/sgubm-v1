
import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, AuditLog
from src.application.services.audit_service import AuditService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def apply_correction():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("--- APLICANDO CORRECCIÓN DE DEUDA PARA ROMAN PERNIA (ID 58) ---")
    
    client = session.query(Client).get(58)
    if not client:
        print("❌ ERROR: No se encontró al cliente con ID 58.")
        return
        
    old_balance = client.account_balance
    new_balance = 90000.0
    
    if old_balance == new_balance:
        print(f"⚠️ El balance ya es {new_balance}. No se requiere ajuste.")
        return
        
    client.account_balance = new_balance
    
    # Registrar en Auditoría (Manualmente con SQLAlchemy para este script)
    audit = AuditLog(
        category='accounting',
        operation='manual_debt_correction',
        entity_type='client',
        entity_id=58,
        description=f"Corrección manual de deuda: ${old_balance:,.0f} -> ${new_balance:,.0f} (Ajuste por discrepancia en factura única).",
        previous_state=str({'balance': old_balance}),
        new_state=str({'balance': new_balance}),
        username='system_fix'
    )
    session.add(audit)
    
    session.commit()
    print(f"✅ Balance corregido: ${old_balance:,.0f} -> ${new_balance:,.0f}")
    print("✅ Cambio registrado en el log de auditoría.")
    
    session.close()

if __name__ == "__main__":
    apply_correction()
