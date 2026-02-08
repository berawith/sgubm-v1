import sys
import os

# Add src to path
sys.path.append(os.path.abspath('.'))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import InternetPlan, Client, Router

def debug_plans():
    print("Testing /api/plans logic...")
    db = get_db()
    try:
        plans = db.session.query(InternetPlan).all()
        print(f"Found {len(plans)} plans.")
        
        result = []
        for p in plans:
            print(f"Processing plan: {p.name} (ID: {p.id})")
            count = db.session.query(Client).filter(Client.plan_id == p.id).count()
            print(f"  Clients count: {count}")
            data = p.to_dict()
            data['clients_count'] = count
            result.append(data)
            print(f"  Plan data: {data}")
            
        print("Success!")
    except Exception as e:
        print(f"FAILED with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_plans()
