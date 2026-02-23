
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Añadir el path del proyecto para importar modelos
sys.path.append(os.getcwd())

try:
    from src.infrastructure.database.models import Client, Invoice
except ImportError:
    print("Error: No se pudieron importar los modelos.")
    sys.exit(1)

def check_ip_status(target_ip):
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"\nBuscando información para la IP: {target_ip}")
    print("-" * 50)

    # Buscar cliente por IP (usando LIKE por si tiene máscara /32 o similar)
    client = session.query(Client).filter(Client.ip_address.like(f"{target_ip}%")).first()

    if not client:
        print(f"❌ No se encontró ningún cliente con la IP {target_ip} en la base de datos.")
        session.close()
        return

    # Obtener facturas pendientes
    unpaid_invoices = session.query(Invoice).filter(
        Invoice.client_id == client.id,
        Invoice.status == 'unpaid'
    ).all()

    print(f"Cliente: {client.legal_name}")
    print(f"ID Cliente: {client.id}")
    print(f"Estatus de Servicio: {client.status.upper()}")
    print(f"Saldo en Cuenta (Balance): ${client.account_balance}")
    print(f"Facturas Pendientes: {len(unpaid_invoices)}")
    
    if unpaid_invoices:
        print("\nDetalle de Facturas Impagas:")
        for inv in unpaid_invoices:
            print(f" - Factura ID: {inv.id}, Monto: ${inv.total_amount}, Vencimiento: {inv.due_date}")
    
    # Resumen Financiero
    if (client.account_balance or 0) <= 0 and len(unpaid_invoices) == 0:
        print("\n✅ ESTADO FINANCIERO: AL DÍA (Pagado)")
    else:
        print("\n⚠️ ESTADO FINANCIERO: DEUDOR (Pendiente de Pago)")

    session.close()

if __name__ == "__main__":
    check_ip_status("77.16.10.239")
