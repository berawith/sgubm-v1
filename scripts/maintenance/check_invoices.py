
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice
except ImportError:
    sys.exit(1)

def audit_invoices_and_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- REVISIÓN DE FACTURAS DE JUAN PABLO (ID 86) ---")
    invs_jp = session.query(Invoice).filter(Invoice.client_id == 86).all()
    for inv in invs_jp:
        print(f"Factura ID: {inv.id} | Monto: {inv.total_amount} | Estatus: {inv.status} | Fecha: {inv.created_at}")

    print("\n--- REVISIÓN DE FACTURAS DE GRABIELA (ID 543) ---")
    invs_g = session.query(Invoice).filter(Invoice.client_id == 543).all()
    for inv in invs_g:
        print(f"Factura ID: {inv.id} | Monto: {inv.total_amount} | Estatus: {inv.status} | Fecha: {inv.created_at}")

    print("\n--- REVISIÓN DE FACTURAS DE ROMAN (ID 58) ---")
    invs_r = session.query(Invoice).filter(Invoice.client_id == 58).all()
    for inv in invs_r:
        print(f"Factura ID: {inv.id} | Monto: {inv.total_amount} | Estatus: {inv.status} | Fecha: {inv.created_at}")

    session.close()

if __name__ == "__main__":
    audit_invoices_and_payments()
