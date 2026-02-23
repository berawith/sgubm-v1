
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

def check_client_exists(client_id):
    db = get_db()
    session = db.session
    client = session.query(Client).filter(Client.id == client_id).first()
    if client:
        print(f"Client {client_id} EXISTS: {client.legal_name}")
    else:
        print(f"Client {client_id} NOT FOUND in main table.")

if __name__ == "__main__":
    check_client_exists(460)
