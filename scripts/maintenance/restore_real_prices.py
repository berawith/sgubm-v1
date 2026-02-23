
import sys
import os
from datetime import datetime

# Añadir el path del src para importar los modelos
sys.path.append(os.path.join(os.getcwd()))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Invoice, InvoiceItem, Client

def restore_real_prices():
    db = get_db()
    session = db.session
    now = datetime.now()
    
    print(f"🔄 Restaurando precios reales para facturas de {now.year}-{now.month:02d}...")
    
    # 1. Buscar facturas impagas del mes actual que han sido prorrateadas
    # Sabemos que han sido prorrateadas si total_amount < suma de items
    unpaid_invoices = session.query(Invoice).filter(
        Invoice.status == 'unpaid',
        Invoice.issue_date >= datetime(now.year, now.month, 1),
        Invoice.issue_date <= now
    ).all()
    
    restored_count = 0
    total_balance_adjustment = 0.0
    
    for inv in unpaid_invoices:
        # Sumar items para saber el precio "real" original
        original_price = sum(item.amount for item in inv.items)
        
        if original_price > inv.total_amount + 0.01:
            diff = original_price - inv.total_amount
            print(f"📍 Restaurando Invoice #{inv.id} (Cliente {inv.client_id}): {inv.total_amount} -> {original_price}")
            
            inv.total_amount = original_price
            
            # Ajustar balance del cliente (volver a subir la deuda)
            if inv.client:
                inv.client.account_balance = (inv.client.account_balance or 0.0) + diff
                total_balance_adjustment += diff
            
            restored_count += 1
            
    try:
        session.commit()
        print(f"✅ Éxito: {restored_count} facturas restauradas.")
        print(f"💰 Se re-estableció un total de ${total_balance_adjustment:,.2f} en deudas pendientes.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error al guardar cambios: {e}")

if __name__ == "__main__":
    restore_real_prices()
