
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def fix_grabiela_double_payment():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- CORRIGIENDO DOBLE PAGO DE GRABIELA ---")
    
    # 1. Pago ID 191 (el más reciente con referencia 06390)
    p191 = session.query(Payment).get(191)
    jp = session.query(Client).filter(Client.legal_name.ilike('%Juan Pablo Barrios%')).first()
    grabiela = session.query(Client).filter(Client.legal_name.ilike('%Grabiela Alvarado%')).first()

    if p191 and jp and grabiela:
        print(f"Moviendo Pago ID 191 ($90,000) de Grabiela (ID {grabiela.id}) a Juan Pablo (ID {jp.id})")
        p191.client_id = jp.id
        session.commit()
        print("✅ Pago reasignado correctamente.")
    else:
        print("❌ No se pudo realizar la reasignación (IDs no encontrados).")

    session.close()

if __name__ == "__main__":
    fix_grabiela_double_payment()
