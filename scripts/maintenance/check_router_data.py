import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import Router

def check_data():
    try:
        db = DatabaseManager()
        session = db.session  # This returns a session object
        
        routers = session.query(Router).all()
        print(f"Total Routers: {len(routers)}")
        for r in routers:
            print(f"Router: {r.alias} (ID: {r.id})")
            print(f"  - Management Method (DB): {r.management_method}")
            print(f"  - PPPoE Ranges (DB): '{r.pppoe_ranges}'")
            print(f"  - DHCP Ranges (DB): '{r.dhcp_ranges}'")
            print("-" * 20)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_data()
