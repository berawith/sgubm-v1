import os
import sys
from datetime import datetime
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Añadir el directorio actual al path para importar módulos locales
sys.path.append(os.getcwd())

from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, InvoiceItem, Router
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from sqlalchemy import extract

def close_february_2026_cycle():
    db = get_db()
    session = db.session
    adapter = MikroTikAdapter()
    
    target_year = 2026
    target_month = 2
    
    logger.info("🚀 Iniciando Cierre de Ciclo: Febrero 2026 y Sincronización Masiva")
    
    # Obtener todos los clientes
    clients = session.query(Client).all()
    logger.info(f"📋 Procesando {len(clients)} clientes...")
    
    # Cache de adaptadores por router para no conectar/desconectar por cada cliente
    router_connections = {}
    
    stats = {
        'activated': 0,
        'cut': 0,
        'invoices_created': 0,
        'errors': 0
    }
    
    for client in clients:
        try:
            balance = client.account_balance or 0.0
            
            # --- 1. Asegurar Factura de Febrero 2026 ---
            feb_invoice = session.query(Invoice).filter(
                Invoice.client_id == client.id,
                extract('year', Invoice.issue_date) == target_year,
                extract('month', Invoice.issue_date) == target_month
            ).first()
            
            if not feb_invoice:
                # Crear factura si no existe (basada en su mensualidad)
                amount = client.monthly_fee or 0.0
                if amount > 0:
                    logger.info(f"🆕 Generando factura Feb 2026 para {client.legal_name} (${amount})")
                    feb_invoice = Invoice(
                        client_id=client.id,
                        issue_date=datetime(2026, 2, 1),
                        due_date=datetime(2026, 2, 5),
                        total_amount=amount,
                        status='unpaid'
                    )
                    session.add(feb_invoice)
                    session.flush()
                    
                    item = InvoiceItem(
                        invoice_id=feb_invoice.id,
                        description=f"Plan Internet - Febrero 2026",
                        amount=amount
                    )
                    session.add(item)
                    stats['invoices_created'] += 1
            
            # --- 2. Sincronización de Estado ---
            should_be_active = balance <= 0
            current_status = client.status
            
            # Conexión al Router si es necesario
            router = None
            if client.router_id:
                if client.router_id not in router_connections:
                    r_obj = session.query(Router).get(client.router_id)
                    if r_obj and r_obj.status == 'online':
                        try:
                            conn = MikroTikAdapter()
                            if conn.connect(r_obj.host_address, r_obj.api_username, r_obj.api_password, r_obj.api_port):
                                router_connections[client.router_id] = conn
                                logger.info(f"🔌 Conectado al router: {r_obj.alias}")
                            else:
                                router_connections[client.router_id] = None
                        except Exception as e:
                            logger.error(f"❌ Error conectando a {r_obj.alias}: {e}")
                            router_connections[client.router_id] = None
                router_adapter = router_connections.get(client.router_id)
            else:
                router_adapter = None

            if should_be_active:
                # AL DÍA -> Debe estar ACTIVO
                if feb_invoice:
                    feb_invoice.status = 'paid'
                
                if current_status != 'active':
                    logger.info(f"✅ ACTIVANDO: {client.legal_name} (Saldo: {balance})")
                    client.status = 'active'
                    if router_adapter:
                        router_adapter.restore_client_service(client.to_dict())
                    stats['activated'] += 1
            else:
                # CON DEUDA -> Debe estar CORTADO
                if feb_invoice:
                    feb_invoice.status = 'unpaid'
                
                if current_status == 'active':
                    logger.info(f"🚫 CORTANDO: {client.legal_name} (Saldo: {balance})")
                    client.status = 'cut'
                    if router_adapter:
                        router_adapter.suspend_client_service(client.to_dict())
                    stats['cut'] += 1
            
        except Exception as e:
            logger.error(f"❌ Error procesando cliente {client.id} ({client.legal_name}): {e}")
            stats['errors'] += 1
            session.rollback()
            continue

    # Commit final
    session.commit()
    
    # Desconectar routers
    for r_id, r_adapter in router_connections.items():
        if r_adapter:
            try:
                r_adapter.disconnect()
            except:
                pass
                
    logger.info("🏁 PROCESO FINALIZADO")
    logger.info(f"📊 Resumen: ACTIVADOS: {stats['activated']}, CORTADOS: {stats['cut']}, FACTURAS GEN: {stats['invoices_created']}, ERRORES: {stats['errors']}")

if __name__ == "__main__":
    close_february_2026_cycle()
