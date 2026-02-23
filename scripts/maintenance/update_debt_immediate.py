import logging
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client
from run import create_app

# Configuración de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def update_debt_immediate():
    """
    Establece a TODOS los clientes activos como 'pendiente de pago'
    y actualiza su deuda (account_balance) para que sea igual a su mensualidad.
    """
    app = create_app()
    with app.app_context():
        db = get_db()
        session = db.session
        
        # Obtener clientes activos
        active_clients = session.query(Client).filter(Client.status == 'active').all()
        
        updated_count = 0
        total_debt_generated = 0.0
        
        print(f"\n💸 Iniciando actualización masiva de deuda...")
        print("-" * 60)
        
        for client in active_clients:
            # Reglas de precio (Hardcoded logic duplicada por seguridad del script)
            # Puerto Vivas ID = 2 -> 70.000
            # Resto -> 90.000
            
            # Asegurar fee correcto si estaba en 0
            current_fee = client.monthly_fee
            if not current_fee or current_fee == 0:
                if client.router_id == 2:
                    current_fee = 70000.0
                else:
                    current_fee = 90000.0
                client.monthly_fee = current_fee
            
            # Aplicar deuda
            client.account_balance = current_fee
            # Nota: No cambiamos status a 'suspended' ni 'pending' en el modelo porque
            # el status 'active' es necesario para que tengan servicio.
            # La "deuda" se refleja en account_balance > 0.
            # Sin embargo, si el usuario quiere un estado visual de "Pendiente", 
            # usaremos 'active' pero con deuda. 
            # (El modelo actual usa status para servicio: active/suspended).
            
            # Si se requiere un campo específico de pago, lo ideal sería 'payment_status',
            # pero por ahora usaremos account_balance como indicador.
            
            updated_count += 1
            total_debt_generated += current_fee
            
            print(f"💰 Cliente {client.username}: Deuda actualizada a ${current_fee:,.0f}")
        
        session.commit()
        
        print("-" * 60)
        print(f"✅ Proceso completado.")
        print(f"📊 Clientes procesados: {updated_count}")
        print(f"💵 Deuda total generada: ${total_debt_generated:,.0f}")

if __name__ == "__main__":
    update_debt_immediate()
