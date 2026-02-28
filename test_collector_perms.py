
from src.application.services.auth import AuthService
from src.infrastructure.database.models import UserRole

def verify():
    role = 'collector'
    module = 'clients:list'
    
    perms = ['view', 'edit', 'delete', 'create']
    print(f"--- Verifying permissions for role: {role} in module: {module} ---")
    
    for p in perms:
        has_perm = AuthService.check_permission(role, module, p)
        print(f"Action '{p}': {'ALLOWED' if has_perm else 'RESTRICTED'}")

if __name__ == "__main__":
    verify()
