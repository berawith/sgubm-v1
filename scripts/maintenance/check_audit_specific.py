
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import AuditLog

def check_audit_specific():
    db = get_db()
    session = db.session
    new_ids = [591, 592, 593, 594]
    logs = session.query(AuditLog).filter(AuditLog.entity_id.in_(new_ids)).order_by(AuditLog.id.desc()).all()
    
    print(f"--- Audit Logs for IDs {new_ids} ---")
    for l in logs:
        print(f"ID: {l.id}, Date: {l.timestamp}, Op: {l.operation}, EntityID: {l.entity_id}, Desc: {l.description}")

if __name__ == "__main__":
    check_audit_specific()
