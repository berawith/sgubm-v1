from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import User, RolePermission, UserRole
from src.application.services.auth import AuthService

def diag():
    db = get_db()
    session = db.session
    
    print("--- Users ---")
    users = session.query(User).all()
    for u in users:
        print(f"User: {u.username}, Role: {u.role}")
        
    print("\n--- UserRole Enum Values ---")
    for role in UserRole:
        print(f"{role.name}: {role.value}")
        
    print("\n--- Checking AuthService.check_permission ---")
    admin_roles = [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value]
    print(f"Admin Roles defined in bypass: {admin_roles}")
    
    for u in users:
        has_perm = AuthService.check_permission(u.role, 'system:users', 'view')
        print(f"User {u.username} ({u.role}) has 'system:users':'view' permission? {has_perm}")

if __name__ == "__main__":
    diag()
