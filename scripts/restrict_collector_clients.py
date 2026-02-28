
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.models import RolePermission

def restrict_collector():
    # Detect DB path
    db_path = 'sgubm.db'
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found in current directory.")
        return

    DATABASE_URL = f'sqlite:///{db_path}'
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    print("Applying STRICT Collector Restrictions...")
    
    # Target module: clients:list
    perm = session.query(RolePermission).filter_by(role_name='collector', module='clients:list').first()
    if perm:
        print(f"Found permission record for [collector] on [clients:list].")
        print(f" - Previous state: Edit={perm.can_edit}, Delete={perm.can_delete}, Create={perm.can_create}")
        
        perm.can_edit = False
        perm.can_delete = False
        perm.can_create = False
        
        print(f" - New state: Edit=False, Delete=False, Create=False")
        session.commit()
        print("Database updated successfully.")
    else:
        print("Error: Permission record for 'collector' on 'clients:list' not found.")
        print("Ensure the system has been initialized with initialize_collector_finance.py first.")

    session.close()

if __name__ == "__main__":
    restrict_collector()
