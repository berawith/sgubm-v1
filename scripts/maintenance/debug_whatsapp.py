import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.infrastructure.database.db_manager import get_db
import logging

logging.basicConfig(level=logging.INFO)

def debug_whatsapp_repo():
    try:
        print("--- Debugging WhatsApp Repository ---")
        db = get_db()
        repo = db.get_whatsapp_repository()
        
        print("Fetching latest conversations...")
        convs = repo.get_latest_conversations()
        print(f"Found {len(convs)} conversations.")
        
        for c in convs:
            print(f"Conv: {c.phone} - {c.message_text[:20]}")
            try:
                d = c.to_dict()
                print(f"  to_dict success: {d.get('client_name')}")
            except Exception as e:
                print(f"  to_dict FAILED: {str(e)}")
                
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_whatsapp_repo()
