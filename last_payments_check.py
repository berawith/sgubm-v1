
from src.infrastructure.database.models import Payment, Client
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
engine = create_engine('sqlite:///sgubm.db')
Session = sessionmaker(bind=engine)
session = Session()

print("--- ÚLTIMOS 30 PAGOS REGISTRADOS ---")
ps = session.query(Payment).order_by(Payment.id.desc()).limit(30).all()
for p in ps:
    c = session.query(Client).get(p.client_id)
    print(f"ID: {p.id} | Cliente: {c.legal_name if c else 'DESCONOCIDO'} (ID: {p.client_id}) | Monto: {p.amount} | Fecha: {p.payment_date}")

session.close()
