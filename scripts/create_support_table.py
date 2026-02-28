import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Base

def create_table():
    db = get_db()
    print("Creating SupportTicket table if it doesn't exist...")
    
    # db_manager exposes _engine internally initialized via init_db
    engine = db._engine
    Base.metadata.create_all(engine)
    print("Done!")

if __name__ == '__main__':
    create_table()
