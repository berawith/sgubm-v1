
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

def list_clients():
    db = get_db()
    clients = db.session.query(Client).limit(5).all()
    for c in clients:
        print(f"ID: {c.id}, Name: {c.legal_name}")

if __name__ == "__main__":
    list_clients()
