from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

db = get_db()
session = db.session
clients = session.query(Client).all()
count = 0

for client in clients:
    if client.plan_name and ' (Auto)' in client.plan_name:
        client.plan_name = client.plan_name.replace(' (Auto)', '')
        count += 1

session.commit()
print(f"✅ Se han actualizado {count} clientes eliminando la etiqueta (Auto).")
db.remove_session()
