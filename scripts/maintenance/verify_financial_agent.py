import json
from run import create_app
from datetime import datetime

def verify_statistics():
    print("🚀 Iniciando verificación de Financial Agent...")
    app = create_app()
    app.config['TESTING'] = True
    
    with app.test_client() as client:
        print("📊 Solicitando estadísticas a /api/payments/statistics...")
        response = client.get('/api/payments/statistics')
        
        if response.status_code != 200:
            print(f"❌ Error: Status code {response.status_code}")
            return
            
        data = response.json
        print("✅ Respuesta recibida exitosamente.")
        
        # Verificar presencia de campos de gastos y utilidad neta
        totals = data.get('totals', {})
        expected_keys = [
            'today_expenses', 'month_expenses', 'year_expenses',
            'today_net', 'month_net', 'year_net'
        ]
        
        missing_keys = [k for k in expected_keys if k not in totals]
        if missing_keys:
            print(f"❌ Faltan campos en totals: {missing_keys}")
        else:
            print("✅ Todos los campos de contabilidad están presentes en 'totals'.")
            
        # Verificar Annual Trend
        trend = data.get('annual_trend', [])
        if not trend:
            print("⚠️ Advertencia: No hay datos en annual_trend.")
        else:
            first_item = trend[0]
            if 'expenses' in first_item and 'net_profit' in first_item:
                print("✅ Campos 'expenses' y 'net_profit' presentes en annual_trend.")
            else:
                print(f"❌ Faltan campos en annual_trend: {[k for k in ['expenses', 'net_profit'] if k not in first_item]}")

        # Mostrar muestra de datos
        print("\n📈 Muestra de totales:")
        print(f"   - Ingresos Hoy: ${totals.get('today', 0):,.2f}")
        print(f"   - Gastos Hoy:   ${totals.get('today_expenses', 0):,.2f}")
        print(f"   - Utilidad Hoy: ${totals.get('today_net', 0):,.2f}")
        print(f"   - Ingresos Mes: ${totals.get('month', 0):,.2f}")
        print(f"   - Gastos Mes:   ${totals.get('month_expenses', 0):,.2f}")
        print(f"   - Utilidad Mes: ${totals.get('month_net', 0):,.2f}")

        print("\n📅 Último mes en tendencia:")
        last_month = trend[-1] if trend else {}
        print(f"   - Mes: {last_month.get('label')} {last_month.get('year')}")
        print(f"   - Recaudado: ${last_month.get('collected', 0):,.2f}")
        print(f"   - Gastos:    ${last_month.get('expenses', 0):,.2f}")
        print(f"   - Utilidad:  ${last_month.get('net_profit', 0):,.2f}")

if __name__ == "__main__":
    verify_statistics()
