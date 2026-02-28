
from src.infrastructure.database.models import Base, CollectorTransfer, RolePermission, UserRole, init_db, get_session
from src.infrastructure.database.db_manager import get_db
import os
from sqlalchemy import create_engine, inspect

def initialize_collector_finance():
    print("🚀 Initializing Collector Finance tables and permissions...")
    
    # 1. Ensure table exists
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///sgubm.db')
    engine = create_engine(DATABASE_URL)
    
    inspector = inspect(engine)
    if 'collector_transfers' not in inspector.get_table_names():
        print("Creating 'collector_transfers' table...")
        CollectorTransfer.__table__.create(engine)
    else:
        print("'collector_transfers' table already exists.")

    # 2. Backfill RBAC permissions
    session = get_db().session
    try:
        # Nombres granulares requeridos por el frontend
        modules = [
            'dashboard', 
            'clients:list', 'clients:import', 'clients:actions', 'clients-trash',
            'finance:reports', 'finance:payments', 'finance:invoices', 'finance:expenses', 'finance:promises',
            'routers:list', 'system:users', 'whatsapp:chats', 'collector-finance',
            'automation', 'sync', 'trash', 'metrics'
        ]
        roles = [r.value for r in UserRole]
        
        for role in roles:
            for mod in modules:
                # Check if permission exists
                perm = session.query(RolePermission).filter_by(role_name=role, module=mod).first()
                
                if not perm:
                    print(f"Adding permission for {role} on {mod}...")
                    perm = RolePermission(role_name=role, module=mod)
                    session.add(perm)
                
                # Apply specific rules
                if role in [UserRole.ADMIN.value, UserRole.ADMIN_FEM.value]:
                    perm.can_view = True
                    perm.can_create = True
                    perm.can_edit = True
                    perm.can_delete = True
                
                elif role == UserRole.COLLECTOR.value:
                    if mod == 'collector-finance':
                        perm.can_view = True
                        perm.can_create = True
                        perm.can_edit = True
                        perm.can_delete = True
                    elif mod in ['clients:list', 'dashboard']:
                        perm.can_view = True
                        perm.can_create = False # El cobrador no puede crear clientes por política de SGUBM
                        perm.can_edit = False
                        perm.can_delete = False
                    else:
                        perm.can_view = False
                        perm.can_create = False
                        perm.can_edit = False
                        perm.can_delete = False
                
                # Others (Partner, Tech, Sec) - keep existing defaults if they had them, 
                # or set collector-finance to false
                elif mod == 'collector-finance':
                    perm.can_view = False
        
        session.commit()
        print("✅ Permissions backfilled successfully.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error initializing permissions: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    # Mocking app context if needed or run directly
    initialize_collector_finance()
