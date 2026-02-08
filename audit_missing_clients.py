from run import create_app
from src.infrastructure.database.db_manager import get_db

app = create_app()
with app.app_context():
    db = get_db()
    repo = db.get_client_repository()
    ids = [47, 50, 74, 123, 291]
    
    print("-" * 30)
    print("CLIENT AUDIT REPORT")
    print("-" * 30)
    
    for i in ids:
        c = repo.get_by_id(i)
        if c:
            print(f"ID: {c.id}")
            print(f"Name: {c.legal_name}")
            print(f"IP: {c.ip_address}")
            print(f"Status: '{c.status}'")
            print(f"Router ID: {c.router_id}")
            print("-" * 15)
        else:
            print(f"ID {i}: NOT FOUND")
    print("-" * 30)
