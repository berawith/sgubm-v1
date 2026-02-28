
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Payment, Router
from src.application.services.mikrotik_operations import safe_suspend_client

def test_balance_none_fix():
    print("Testing balance None fix...")
    db = get_db()
    repo = db.get_client_repository()
    
    # Create temp client with None balance
    client = Client(
        legal_name="Test None Balance",
        subscriber_code="TEST-NONE",
        username="test_none",
        router_id=1,
        account_balance=None
    )
    db.session.add(client)
    db.session.commit()
    
    try:
        repo.update_balance(client.id, 100.0, operation='add')
        db.session.refresh(client)
        print(f"Success! Balance is now: {client.account_balance}")
        assert client.account_balance == 100.0
    except Exception as e:
        print(f"Failed! Error: {e}")
    finally:
        db.session.delete(client)
        db.session.commit()

if __name__ == "__main__":
    test_balance_none_fix()
