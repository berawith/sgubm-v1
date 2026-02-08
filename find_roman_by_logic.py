
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def find_roman_ip_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- BUSCANDO PAGOS POR LA IP DE ROMAN (177.77.73.39) ---")
    
    # 1. Identificar clientes que hayan tenido esa IP
    # En el reporte de auditoría vimos que el ID 58 y 143 tenían esa IP.
    roman_ids = [58, 143, 71] # 71 por si acaso aunque era la IP de Grabiela
    
    # Buscamos en la tabla de pagos cualquier cosa vinculada a estos IDs
    for rid in roman_ids:
        ps = session.query(Payment).filter(Payment.client_id == rid).all()
        if ps:
            print(f"✅ Pagos encontrados en ID {rid}:")
            for p in ps:
                print(f"   ID: {p.id} | Monto: {p.amount} | Fecha: {p.payment_date}")
        else:
            print(f"ID {rid} no tiene pagos.")

    # 2. Buscar por montos (¿De cuánto fue el pago de Roman?)
    print("\n--- BUSCANDO PAGOS POR MONTO $90,000 (COMÚN) ---")
    common_payments = session.query(Payment).filter(Payment.amount == 90000.0).order_by(Payment.payment_date.desc()).limit(10).all()
    for cp in common_payments:
        owner = session.query(Client).get(cp.client_id)
        print(f"Pago $90k | ID: {cp.id} | Cliente: {owner.legal_name if owner else '??'} | Fecha: {cp.payment_date}")

    session.close()

if __name__ == "__main__":
    find_roman_ip_payments()
