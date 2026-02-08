
import sqlite3
from datetime import datetime, timedelta

def simulate_billing_cycle():
    try:
        conn = sqlite3.connect('sgubm.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("📊 SIMULACIÓN DE FACTURACIÓN - MARZO 2026")
        print("="*60)
        
        # 1. Obtener todos los routers y sus configuraciones de facturación
        cursor.execute("SELECT id, alias, zone, billing_day, grace_period, cut_day FROM routers")
        routers = cursor.fetchall()
        
        total_projected_revenue = 0
        total_clients = 0
        
        router_stats = []
        
        for router in routers:
            # 2. Obtener clientes por router
            cursor.execute("""
                SELECT COUNT(*) as count, SUM(monthly_fee) as revenue 
                FROM clients 
                WHERE router_id = ? AND status != 'inactive'
            """, (router['id'],))
            stats = cursor.fetchone()
            
            count = stats['count'] or 0
            revenue = stats['revenue'] or 0
            
            total_clients += count
            total_projected_revenue += revenue
            
            # Fechas proyectadas para Marzo
            gen_date = f"2026-03-{router['billing_day']:02d}"
            due_date = f"2026-03-{router['billing_day'] + router['grace_period']:02d}"
            cut_date = f"2026-03-{router['cut_day']:02d}"
            
            router_stats.append({
                'alias': router['alias'],
                'zone': router['zone'],
                'clients': count,
                'monthly_fee': (revenue / count) if count > 0 else 0,
                'total_revenue': revenue,
                'dates': f"Gen: {gen_date} | Ven: {due_date} | Corte: {cut_date}"
            })
        
        # Imprimir resultados por Router
        for stat in router_stats:
            print(f"📡 Router: {stat['alias']} ({stat['zone']})")
            print(f"   👥 Clientes: {stat['clients']}")
            print(f"   💰 Precio Promedio: ${stat['monthly_fee']:,.0f}")
            print(f"   📈 Recaudación Proyectada: ${stat['total_revenue']:,.0f}")
            print(f"   📅 Ciclo: {stat['dates']}")
            print("-" * 60)
            
        print("\n" + "="*60)
        print("💼 RESUMEN GENERAL")
        print("="*60)
        print(f"👥 Total Clientes Activos: {total_clients}")
        print(f"💰 Recaudación Mensual Proyectada: ${total_projected_revenue:,.0f}")
        print(f"🗓️ Próximo Inicio de Ciclo: 01 de Marzo de 2026")
        print("="*60)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error en la simulación: {e}")

if __name__ == "__main__":
    simulate_billing_cycle()
