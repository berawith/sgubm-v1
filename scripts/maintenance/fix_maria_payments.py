import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment
from src.application.services.audit_service import AuditService
from datetime import datetime

def fix_payments():
    db = get_db()
    session = db.session
    
    # 1. IDENTIFY TARGETS
    client_maria = session.query(Client).filter(Client.legal_name.like('%Maria Flores Alcedo%')).first()
    if not client_maria:
        print("❌ Maria Flores Alcedo not found by name, trying ID 248")
        client_maria = session.query(Client).get(248)
    
    if not client_maria:
        print("❌ Maria Flores Alcedo not found")
        return

    # Check for the $90 payment to delete (Client 228 or linked to Maria mistakenly)
    # Based on audit log ID 19: "Pago de $90.0 (#228) eliminado" -> WAIT, logic in file says ID 228 is the payment ID
    # Let's check payment with ID 228
    payment_to_delete = session.query(Payment).get(228)
    
    # 2. RESTORE PAYMENT 120 ($90,000)
    # Check if it already exists to avoid duplication
    existing_120 = session.query(Payment).get(120)
    if not existing_120:
        print(f"🔄 Restoring Payment 120 ($90,000) for {client_maria.legal_name}")
        restored_payment = Payment(
            id=120,
            client_id=client_maria.id,
            amount=90000.0,
            payment_date=datetime.fromisoformat('2026-02-06 21:26:32.462833'),
            payment_method='cash',
            status='paid', # Set directly to paid (PAGADO)
            notes='Restaurado por corrección de error de agente AI (Approved by user)'
        )
        session.add(restored_payment)
        # Update balance (Subtracting the payment from debt)
        client_maria.account_balance -= 90000.0
    else:
        print("⚠️ Payment 120 already exists.")

    # 3. DELETE PAYMENT 228 ($90)
    if payment_to_delete:
        print(f"🗑️ Deleting incorrect Payment 228 (${payment_to_delete.amount})")
        # Update balance for deletion (Adding the payment back to debt)
        # We need the client of THIS payment
        target_client = session.query(Client).get(payment_to_delete.client_id)
        if target_client:
            target_client.account_balance += payment_to_delete.amount
            
        session.delete(payment_to_delete)
        
        # Log Audit for 228
        AuditService.log(
            operation='payment_deleted',
            category='accounting',
            entity_type='payment',
            entity_id=228,
            description=f"Pago de ${payment_to_delete.amount} (#228) eliminado por corrección (monto incompleto)."
        )
    else:
        print("ℹ️ Payment 228 not found (already deleted or wrong ID).")
    
    # Log Audit for 120 restoration
    AuditService.log(
        operation='payment_restored',
        category='accounting',
        entity_type='payment',
        entity_id=120,
        description=f"Pago de $90,000 (#120) restaurado por corrección para {client_maria.legal_name}."
    )
    
    session.commit()
    print(f"🚀 Fixed! Final Balance for {client_maria.legal_name}: {client_maria.account_balance}")


if __name__ == "__main__":
    fix_payments()
