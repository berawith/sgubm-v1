from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router

db = get_db()
r = db.session.query(Router).get(1)
if r:
    print(f"ID: {r.id}")
    print(f"Alias: {r.alias}")
    print(f"Host: {r.host_address}")
    print(f"Port: {r.api_port}")
    print(f"User: {r.api_username}")
    print(f"Status: {r.status}")
else:
    print("Router 1 not found")
