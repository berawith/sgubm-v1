
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.models import RolePermission

def fix_perms():
    DATABASE_URL = 'sqlite:///sgubm.db'
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("Fixing permissions for COLLECTOR...")
    
    # 1. client:list -> can_create = False
    perm = session.query(RolePermission).filter_by(role_name='collector', module='clients:list').first()
    if perm:
        print(f"Setting can_create=False for clients:list (was {perm.can_create})")
        perm.can_create = False
    else:
        print("Warning: clients:list permission not found for collector")

    # 2. payments -> can_create = False
    perm_pay = session.query(RolePermission).filter_by(role_name='collector', module='payments').first()
    if perm_pay:
        print(f"Setting can_create=False for payments (was {perm_pay.can_create})")
        perm_pay.can_create = False

    session.commit()
    print("✅ Permissions updated.")
    session.close()

if __name__ == "__main__":
    fix_perms()
