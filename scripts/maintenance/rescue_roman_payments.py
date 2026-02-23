
import os
import sys
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def find_lost_roman_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- BUSCANDO PAGOS DE ROMAN PERNIA ---")
    
    # 1. Buscar el cliente actual
    roman = session.query(Client).filter(Client.legal_name.ilike('%Roman Pernia%')).first()
    if roman:
        print(f"Cliente actual: {roman.legal_name} (ID: {roman.id})")
        payments = session.query(Payment).filter(Payment.client_id == roman.id).all()
        print(f"Pagos vinculados actualmente: {len(payments)}")
        for p in payments:
            print(f"  - Pago ID {p.id}: ${p.amount} | Fecha: {p.payment_date}")

    # 2. Buscar pagos que hayan quedado "huérfanos" (con IDs de clientes que ya no existen)
    # IDs que borramos: 71, 143
    print("\n--- BUSCANDO PAGOS EN IDs ELIMINADOS (71, 143) ---")
    lost_ids = [71, 143]
    for old_id in lost_ids:
        lost_payments = session.query(Payment).filter(Payment.client_id == old_id).all()
        if lost_payments:
            print(f"⚠️ ¡ENCONTRADOS {len(lost_payments)} pagos en el ID {old_id}!")
            for lp in lost_payments:
                print(f"   - Pago ID {lp.id}: ${lp.amount} | Fecha: {lp.payment_date}")
                if roman:
                    lp.client_id = roman.id
                    print(f"     ✅ Reasignado al Roman oficial (ID: {roman.id})")
        else:
            print(f"No hay pagos huérfanos en ID {old_id}.")

    # 3. Guardar cambios si hubo reasignaciones
    session.commit()
    print("\n--- PROCESO COMPLETADO ---")
    session.close()

if __name__ == "__main__":
    find_lost_roman_payments()
