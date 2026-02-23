
import sys
import os
from datetime import datetime

# Añadir src al path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Router, Invoice

def diagnose():
    db = get_db()
    session = db.session
    
    # Buscar cliente Marthajoyo
    client = session.query(Client).filter(Client.legal_name.like('%Marthajoyo%')).first()
    if not client:
        print("Cliente no encontrado")
        return
    
    print(f"--- Datos del Cliente: {client.legal_name} ---")
    print(f"ID: {client.id}")
    print(f"Status: {client.status}")
    print(f"Balance: {client.account_balance}")
    print(f"Due Date (DB): {client.due_date}")
    print(f"Router ID: {client.router_id}")
    
    # Buscar Router
    router = session.query(Router).get(client.router_id)
    if router:
        print(f"\n--- Datos del Router: {router.alias} ---")
        print(f"Billing Day: {router.billing_day}")
        print(f"Grace Period: {router.grace_period}")
        print(f"Cut Day: {router.cut_day}")
    
    # Buscar Facturas
    invoices = session.query(Invoice).filter(Invoice.client_id == client.id).order_by(Invoice.issue_date.desc()).limit(3).all()
    print("\n--- Últimas Facturas ---")
    for inv in invoices:
        print(f"ID: {inv.id}, Issue: {inv.issue_date}, Due: {inv.due_date}, Amount: {inv.total_amount}, Status: {inv.status}")

if __name__ == "__main__":
    diagnose()
