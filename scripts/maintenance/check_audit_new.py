
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import AuditLog

def check_audit():
    db = get_db()
    session = db.session
    # Look for client creation logs recently
    logs = session.query(AuditLog).filter(AuditLog.entity_type == 'client').order_by(AuditLog.id.desc()).limit(20).all()
    
    print(f"--- Audit Logs for Clients ---")
    for l in logs:
        print(f"ID: {l.id}, Date: {l.timestamp}, Operation: {l.operation}, EntityID: {l.entity_id}, Desc: {l.description}")

if __name__ == "__main__":
    check_audit()
