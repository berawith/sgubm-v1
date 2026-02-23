from src.infrastructure.database.db_manager import get_db
from sqlalchemy import text
import sys

try:
    db = get_db()
    db.session.execute(text('ALTER TABLE routers ADD COLUMN last_billing_date DATETIME'))
    db.session.commit()
    print("SUCCESS: last_billing_date added to routers")
except Exception as e:
    if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
        print("INFO: Column already exists")
    else:
        print(f"ERROR: {e}")
        sys.exit(1)
