"""
Script para actualizar precios de clientes por router
"""
import sys
from src.infrastructure.database.db_manager import get_db

def update_prices_by_router(router_ip, monthly_fee):
    """
    Actualiza el precio mensual de todos los clientes de un router específico
    
    Args:
        router_ip: IP del router (ej: '12.12.12.1')
        monthly_fee: Nuevo precio mensual
    """
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    
    # Buscar el router por IP
    all_routers = router_repo.get_all()
    target_router = None
    
    for router in all_routers:
        if router.host_address == router_ip:
            target_router = router
            break
    
    if not target_router:
        print(f"❌ No se encontró router con IP {router_ip}")
        return
    
    print(f"📡 Router encontrado: {target_router.alias} (ID: {target_router.id})")
    print(f"   IP: {target_router.host_address}:{target_router.api_port}")
    print()
    
    # Obtener clientes de este router
    clients = client_repo.get_by_router(target_router.id)
    
    if not clients:
        print(f"⚠️  No hay clientes en este router")
        return
    
    print(f"👥 Se encontraron {len(clients)} clientes")
    print(f"💰 Nuevo precio mensual: ${monthly_fee:,.2f}")
    print()
    
    # Confirmar
    response = input("¿Desea continuar con la actualización? (s/n): ")
    if response.lower() != 's':
        print("❌ Operación cancelada")
        return
    
    # Actualizar cada cliente
    updated_count = 0
    errors = 0
    
    print("\n🔄 Actualizando precios...")
    for client in clients:
        try:
            client_repo.update(client.id, {'monthly_fee': monthly_fee})
            updated_count += 1
            print(f"   ✅ {client.legal_name or client.username}: ${monthly_fee:,.2f}")
        except Exception as e:
            errors += 1
            print(f"   ❌ Error en {client.username}: {e}")
    
    print()
    print("="*80)
    print("📊 RESUMEN")
    print("="*80)
    print(f"✅ Clientes actualizados: {updated_count}")
    print(f"❌ Errores: {errors}")
    print(f"💰 Precio aplicado: ${monthly_fee:,.2f}")
    print("="*80)


def main():
    print("="*80)
    print("💰 ACTUALIZACIÓN MASIVA DE PRECIOS")
    print("="*80)
    print()
    
    # Configuración
    ROUTER_IP = '12.12.12.1'  # Router PRINCIPAL
    MONTHLY_FEE = 90000.00    # $90.000
    
    update_prices_by_router(ROUTER_IP, MONTHLY_FEE)
    
    print("\n✅ Proceso completado")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Proceso interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
