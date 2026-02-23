
from src.infrastructure.database.db_manager import DatabaseManager
from src.infrastructure.database.models import WhatsAppMessage

def cleanup_whatsapp():
    db = DatabaseManager()
    session = db.session
    
    # Buscamos IDs que no parezcan números de teléfono individuales o que tengan guiones (grupos)
    # Los números de WhatsApp suelen tener entre 10 y 15 dígitos sin caracteres especiales internos
    all_msgs = session.query(WhatsAppMessage).all()
    deleted_count = 0
    
    for msg in all_msgs:
        # Si tiene guión o es demasiado largo (>15) y no es nulo, probablemente es basura técnica
        if msg.phone and ('-' in msg.phone or len(msg.phone) > 15):
            print(f"Eliminando mensaje de ID técnico: {msg.phone}")
            session.delete(msg)
            deleted_count += 1
            
    session.commit()
    print(f"✅ Se han eliminado {deleted_count} mensajes con IDs técnicos/grupos.")

if __name__ == "__main__":
    cleanup_whatsapp()
