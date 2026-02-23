
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.getcwd())
try:
    from src.infrastructure.database.models import Client, Payment, Invoice
except ImportError:
    sys.exit(1)

def surgical_cleanup():
    engine = create_engine('sqlite:///sgubm.db')
    Session = sessionmaker(bind=engine)
    session = Session()

    print("--- INICIANDO LIMPIEZA QUIRÚRGICA ---")

    # 1. Eliminar duplicado Roman Pernia (ID 71) que estorbaba a Grabiela
    rp71 = session.query(Client).get(71)
    if rp71 and rp71.ip_address == '177.77.70.23':
        session.delete(rp71)
        print("✅ Eliminado registro fantasma Roman Pernia (ID 71) que colisionaba con Grabiela.")

    # 2. Unificar Roman Pernia Finca Rompe (IDs 58 y 143)
    c58 = session.query(Client).get(58)
    c143 = session.query(Client).get(143)
    if c58 and c143:
        # No tienen pagos según auditoría, así que solo eliminamos el duplicado
        session.delete(c143)
        print("✅ Unificado Roman Pernia Finca Rompe (Mantenido ID 58, Eliminado ID 143).")

    # 3. Asegurar que Grabiela Alvarado tenga IP 177.77.70.23
    grabiela = session.query(Client).filter(Client.legal_name.ilike('%Grabiela%')).first()
    if grabiela:
        grabiela.ip_address = '177.77.70.23'
        grabiela.router_id = 1
        print(f"✅ Grabiela Alvarado Piscuri verificada con IP: {grabiela.ip_address}")

    # 4. Asegurar que Juan Pablo Barrios tenga IP 177.77.70.9
    jp = session.query(Client).filter(Client.legal_name.ilike('%Juan Pablo Barrios%')).first()
    if jp:
        jp.ip_address = '177.77.70.9'
        jp.router_id = 1
        print(f"✅ Juan Pablo Barrios verificado con IP: {jp.ip_address}")

    # 5. Asegurar que Leocadia Mora tenga IP 77.16.10.239
    leocadia = session.query(Client).filter(Client.legal_name.ilike('%Leocadia Mora%')).first()
    if leocadia:
        leocadia.ip_address = '77.16.10.239'
        leocadia.router_id = 4
        print(f"✅ Leocadia Mora verificada con IP: {leocadia.ip_address}")

    session.commit()
    print("--- LIMPIEZA COMPLETADA ---")
    session.close()

if __name__ == "__main__":
    surgical_cleanup()
