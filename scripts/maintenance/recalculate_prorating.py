
import sys
import os
import math
from datetime import datetime

# Añadir el path actual para que 'src' sea un paquete válido e imports funcionen
# Asegurándonos de que C:\SGUBM-V1 está en el sys.path
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

from src.application.services.billing_service import BillingService

def run_global_prorating_fix():
    print("🚀 Iniciando recalculo global de prorrateo...")
    
    # BillingService no requiere argumentos en __init__ según el código fuente
    service = BillingService()
    
    # Aplicar la lógica de prorrateo actualizada a todos los clientes (router_id=None aplica a todos)
    try:
        updated_count = service.apply_daily_prorating()
        print(f"✅ Proceso completado. Se actualizaron {updated_count} clientes con su nuevo monto prorrateado.")
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_global_prorating_fix()
