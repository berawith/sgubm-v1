"""
Script para verificar que los datos se importaron correctamente
"""
from src.infrastructure.database.db_manager import get_db
from collections import defaultdict

def main():
    print("="*80)
    print("🔍 VERIFICANDO DATOS IMPORTADOS")
    print("="*80)
    print()
    
    db = get_db()
    router_repo = db.get_router_repository()
    client_repo = db.get_client_repository()
    payment_repo = db.get_payment_repository()
    
    # Verificar routers
    routers = router_repo.get_all()
    print(f"📡 ROUTERS: {len(routers)}")
    print("-" * 80)
    
    for router in routers:
        status_icon = "🟢" if router.status == 'online' else "🔴"
        print(f"{status_icon} {router.alias}")
        print(f"   IP: {router.host_address}:{router.api_port}")
        print(f"   CPU: {router.cpu_usage}% | RAM: {router.memory_usage}%")
        print(f"   Uptime: {router.uptime}")
        print(f"   Última sync: {router.last_sync}")
        print()
    
    # Verificar clientes
    clients = client_repo.get_all()
    print(f"\n👥 CLIENTES: {len(clients)}")
    print("-" * 80)
    
    by_router = defaultdict(int)
    by_status = defaultdict(int)
    by_type = defaultdict(int)
    
    for client in clients:
        by_router[client.router_id] += 1
        by_status[client.status] += 1
        by_type[client.service_type] += 1
    
    print("Por Router:")
    for router in routers:
        count = by_router.get(router.id, 0)
        print(f"   {router.alias}: {count} clientes")
    
    print(f"\nPor Estado:")
    for status, count in by_status.items():
        icon = "✅" if status == 'ACTIVE' else "⏸️" if status == 'SUSPENDED' else "❌"
        print(f"   {icon} {status}: {count}")
    
    print(f"\nPor Tipo de Servicio:")
    for stype, count in by_type.items():
        print(f"   {stype}: {count}")
    
    # Mostrar algunos clientes de ejemplo
    print(f"\n📋 EJEMPLO DE CLIENTES (primeros 5):")
    print("-" * 80)
    
    for i, client in enumerate(clients[:5], 1):
        router = router_repo.get_by_id(client.router_id)
        print(f"{i}. {client.legal_name or client.username}")
        print(f"   Router: {router.alias if router else 'N/A'}")
        print(f"   Usuario: {client.username}")
        print(f"   IP: {client.ip_address or 'N/A'}")
        print(f"   Plan: {client.plan_name or 'N/A'}")
        print(f"   Tipo: {client.service_type}")
        print(f"   Estado: {client.status}")
        print()
    
    # Verificar pagos
    payments = payment_repo.get_all()
    print(f"\n💰 PAGOS: {len(payments)}")
    print("-" * 80)
    
    if payments:
        total_amount = sum(p.amount for p in payments)
        print(f"Total recaudado: ${total_amount:.2f}")
        
        by_method = defaultdict(float)
        for payment in payments:
            by_method[payment.payment_method] += payment.amount
        
        print("Por método:")
        for method, amount in by_method.items():
            print(f"   {method}: ${amount:.2f}")
    else:
        print("⚠️  No hay pagos registrados aún")
    
    print("\n" + "="*80)
    print("✅ VERIFICACIÓN COMPLETADA")
    print("="*80)


if __name__ == '__main__':
    main()
