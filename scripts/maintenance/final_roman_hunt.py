
from src.infrastructure.database.models import Client, Payment
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- REVISANDO PAGOS DEL ID 143 (ANTERIOR ROMAN PERNIA FINCA ROMPE) ---")
# Buscamos en la base de datos completa por el ID anterior
p_143 = session.query(Payment).filter(Payment.client_id == 143).all()
if p_143:
    print(f"✅ Se encontraron {len(p_143)} pagos!")
    for p in p_143:
        print(f"   ID: {p.id} | Monto: {p.amount} | Fecha: {p.payment_date}")
else:
    print("❌ No hay pagos registrados para el ID 143.")

print("\n--- REVISANDO PAGOS DEL ID 217 (QUE APARECÍA COMO JUAN PABLO BARRIOS HACE UN MOMENTO) ---")
p_217 = session.query(Payment).filter(Payment.id == 217).first()
if p_217:
    print(f"✅ Pago ID 217: Monto {p_217.amount} | Dueño actual ID: {p_217.client_id}")
    owner = session.query(Client).get(p_217.client_id)
    print(f"   Dueño actual nombre: {owner.legal_name if owner else '??'}")

session.close()
