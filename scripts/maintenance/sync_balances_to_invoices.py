
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice
from sqlalchemy import func

def sync_balances():
    db = get_db()
    session = db.session
    
    print("🔄 SINCRONIZANDO SALDOS CON FACTURAS PENDIENTES...")
    print("="*60)
    
    clients = session.query(Client).all()
    updated_count = 0
    total_new_debt = 0
    
    for client in clients:
        # Sumar todas las facturas impagas del cliente
        unpaid_total = session.query(func.sum(Invoice.total_amount))\
            .filter(Invoice.client_id == client.id, Invoice.status == 'unpaid')\
            .scalar() or 0.0
            
        old_balance = client.account_balance or 0.0
        
        if old_balance != unpaid_total:
            client.account_balance = unpaid_total
            updated_count += 1
            total_new_debt += unpaid_total
            print(f"✅ {client.legal_name}: ${old_balance:,.0f} -> ${unpaid_total:,.0f}")
            
    session.commit()
    print("-" * 60)
    print(f"📊 Sincronización completada.")
    print(f"👥 Clientes corregidos: {updated_count}")
    print(f"💰 Nueva Cartera Pendiente Total: ${total_new_debt:,.0f}")
    print("="*60)

if __name__ == "__main__":
    sync_balances()
