
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client

def correct_balance(subscriber_code, new_balance):
    db = get_db()
    session = db.session
    
    client = session.query(Client).filter(Client.subscriber_code == subscriber_code).first()
    if not client:
        print(f"Client {subscriber_code} not found.")
        return

    print(f"Old Balance: {client.account_balance}")
    client.account_balance = new_balance
    session.commit()
    print(f"New Balance: {client.account_balance}")
    print("Correction applied successfully.")

if __name__ == "__main__":
    correct_balance("CLI-0009", 0.0)
