from src.infrastructure.database.db_manager import get_db

def stop_auto_reply():
    db = get_db()
    settings_repo = db.get_system_setting_repository()
    settings_repo.set_value('whatsapp_auto_reply', 'false', category='whatsapp')
    print("✅ WhatsApp Auto-Reply has been successfully disabled in the database.")

if __name__ == "__main__":
    stop_auto_reply()
