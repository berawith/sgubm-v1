
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Payment, Client, Invoice
except ImportError:
    print("Error: No se pudieron importar los modelos.")
    sys.exit(1)

def fix_identities():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- INICIANDO CORRECCIÓN DE IDENTIDAD (CONTABILIDAD PROTEGIDA) ---")
    
    # IDs involucrados
    OLD_ID = 508 # Leocadia (El error)
    REAL_ID = 86 # Juan Pablo (El real)
    REAL_IP = "77.16.10.239"

    # 1. Mover Pagos de 508 a 86
    payments_to_move = session.query(Payment).filter(Payment.client_id == OLD_ID).all()
    print(f"\n[1] Moviendo {len(payments_to_move)} pagos de ID {OLD_ID} a ID {REAL_ID}...")
    for p in payments_to_move:
        p.client_id = REAL_ID
        print(f"    - Pago ID {p.id} (${p.amount}) movido.")

    # 2. Mover Facturas (si existen)
    invoices_to_move = session.query(Invoice).filter(Invoice.client_id == OLD_ID).all()
    print(f"\n[2] Moviendo {len(invoices_to_move)} facturas...")
    for inv in invoices_to_move:
        inv.client_id = REAL_ID
        print(f"    - Factura ID {inv.id} movida.")

    # 3. Actualizar Datos Técnicos de Juan Pablo
    print(f"\n[3] Actualizando IP técnica de Juan Pablo Barrios a {REAL_IP}...")
    juan_pablo = session.query(Client).get(REAL_ID)
    if juan_pablo:
        juan_pablo.ip_address = REAL_IP
        juan_pablo.status = 'active'
        # Recalcular balance de Juan Pablo (simplificado: 0 si ya pagó)
        juan_pablo.account_balance = 0 
    
    # 4. Eliminar el registro erróneo (Soft Delete o Hard Delete preventivo)
    print(f"\n[4] Eliminando registro duplicado de Leocadia (ID {OLD_ID})...")
    leocadia = session.query(Client).get(OLD_ID)
    if leocadia:
        session.delete(leocadia)

    session.commit()
    print("\n✅ PROCESO COMPLETADO EN BASE DE DATOS.")
    session.close()

if __name__ == "__main__":
    fix_identities()
