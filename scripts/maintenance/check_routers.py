from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Router

db = get_db()
routers = db.session.query(Router).all()
for r in routers:
    print(f"ID: {r.id}, Alias: {r.alias}, Host: {r.host_address}, Status: {r.status}")
