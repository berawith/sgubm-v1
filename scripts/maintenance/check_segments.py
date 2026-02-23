import sys
import os

# Ensure src is in path
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import Router, NetworkSegment

def check_segments():
    try:
        db = DatabaseManager()
        session = db.session
        
        segments = session.query(NetworkSegment).all()
        print(f"Total Network Segments: {len(segments)}")
        for s in segments:
            print(f"Segment: {s.name} - CIDR: {s.cidr} (Router ID: {s.router_id})")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_segments()
