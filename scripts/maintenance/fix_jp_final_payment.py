
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment
except ImportError:
    sys.exit(1)

def fix_jp_payments():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- AJUSTE DE PAGOS PARA JUAN PABLO BARRIOS ---")
    
    # 1. Pago 191 (la flecha roja en la imagen, 09:55 p. m.)
    p191 = session.query(Payment).get(191)
    if p191:
        print(f"🗑️ Eliminando Pago ID 191 ($90,000 - 09:55 p. m.)")
        session.delete(p191)
    else:
        print("⚠️ No se encontró el Pago ID 191.")

    # 2. Pago 229 (la flecha azul en la imagen, 11:37 p. m.)
    p229 = session.query(Payment).get(229)
    if p229:
        print(f"🔄 Actualizando Pago ID 229 ($90 -> $90,000 - 11:37 p. m.)")
        p229.amount = 90000.0
    else:
        print("⚠️ No se encontró el Pago ID 229.")

    try:
        session.commit()
        print("✅ Ajustes realizados con éxito.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")

    session.close()

if __name__ == "__main__":
    fix_jp_payments()
