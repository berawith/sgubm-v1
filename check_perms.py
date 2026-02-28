
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.models import RolePermission, UserRole

def check_perms():
    DATABASE_URL = 'sqlite:///sgubm.db'
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("Permissions for COLLECTOR:")
    perms = session.query(RolePermission).filter_by(role_name='collector').all()
    for p in perms:
        print(f"Module: {p.module:20} | View: {p.can_view} | Create: {p.can_create} | Edit: {p.can_edit}")
    
    session.close()

if __name__ == "__main__":
    check_perms()
