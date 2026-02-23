"""
Sync Service - Sincronización automática de operaciones pendientes con MikroTik
Ejecuta operaciones que fallaron cuando el router estaba offline
"""
import logging
from datetime import datetime
from typing import List, Dict
from src.infrastructure.database.models import PendingOperation
from src.infrastructure.mikrotik.adapter import MikroTikAdapter

logger = logging.getLogger(__name__)


class SyncService:
    """Servicio de sincronización de operaciones pendientes"""
    
    def __init__(self, db):
        self.db = db
        logger.info(f"SyncService init with db: {db}")
        
    def queue_operation(self, operation_type: str, client_id: int, router_id: int, 
                       ip_address: str, target_status: str = None, operation_data: str = None, commit: bool = True):
        """
        Encola una operación pendiente
        
        Args:
            operation_type: 'suspend', 'activate', 'restore'
            client_id: ID del cliente
            router_id: ID del router
            ip_address: IP del cliente
            target_status: Estado objetivo del cliente
            operation_data: Datos adicionales en JSON
            commit: Si debe realizar commit inmediato (default True)
        """
        try:
            pending_op = PendingOperation(
                operation_type=operation_type,
                client_id=client_id,
                router_id=router_id,
                ip_address=ip_address,
                target_status=target_status,
                operation_data=operation_data,
                status='pending'
            )
            
            # Guardar en BD
            session = self.db.session
            session.add(pending_op)
            if commit:
                session.commit()
            
            logger.info(f"✅ Operación encolada ({'COMMITTED' if commit else 'PENDING'}): {operation_type} para cliente {client_id}")
            return pending_op.id
            
        except Exception as e:
            logger.error(f"❌ Error encolando operación: {e}")
            if commit:
                try: self.db.session.rollback()
                except: pass
            return None
    
    def get_pending_operations(self, router_id: int = None) -> List[PendingOperation]:
        """
        Obtiene operaciones pendientes
        
        Args:
            router_id: Filtrar por router específico (opcional)
        """
        session = self.db.session
        
        try:
            query = session.query(PendingOperation).filter(
                PendingOperation.status == 'pending'
            )
            
            if router_id:
                query = query.filter(PendingOperation.router_id == router_id)
            
            operations = query.order_by(PendingOperation.created_at.asc()).all()
            return operations
            
        finally:
            session.close()
    
    def sync_router_operations(self, router_id: int, router_dict: Dict) -> Dict:
        """
        Sincroniza todas las operaciones pendientes de un router
        
        Args:
            router_id: ID del router
            router_dict: Diccionario con datos del router para conexión
            
        Returns:
            Dict con estadísticas de sincronización
        """
        operations = self.get_pending_operations(router_id)
        
        if not operations:
            logger.info(f"📭 No hay operaciones pendientes para router {router_id}")
            return {'total': 0, 'completed': 0, 'failed': 0}
        
        logger.info(f"🔄 Sincronizando {len(operations)} operaciones pendientes para router {router_id}")
        
        adapter = None
        completed = 0
        failed = 0
        session = self.db.session
        
        try:
            adapter = MikroTikAdapter()
            connected = adapter.connect(
                host=router_dict.get('ip_address') or router_dict.get('host'),
                username=router_dict.get('username'),
                password=router_dict.get('password'),
                port=router_dict.get('api_port') or router_dict.get('port', 8728)
            )
            
            if not connected:
                raise ConnectionError(f"Could not connect to router {router_id}")
            
            for op in operations:
                try:
                    import json
                    client_data = {}
                    if op.operation_data:
                        try:
                            client_data = json.loads(op.operation_data)
                        except:
                            logger.warning(f"Could not parse operation_data for op {op.id}")
                    
                    # Fallback context if JSON is empty/missing
                    if not client_data:
                        client_data = {
                            'id': op.client_id,
                            'ip_address': op.ip_address,
                            'status': op.target_status
                        }

                    # Ejecutar operación según tipo usando métodos reales del adaptador
                    success = False
                    if op.operation_type == 'create':
                        success = adapter.create_client_service(client_data)
                        logger.info(f"✅ Cliente {op.client_id} creado (sincronización): {success}")
                        
                    elif op.operation_type == 'update':
                        current_username = client_data.get('old_username') or client_data.get('username')
                        old_ip = client_data.get('old_ip')
                        success = adapter.update_client_service(current_username, client_data, old_ip=old_ip)
                        logger.info(f"✅ Cliente {op.client_id} actualizado (sincronización): {success}")

                    elif op.operation_type == 'suspend':
                        success = adapter.suspend_client_service(client_data)
                        logger.info(f"✅ Cliente {op.client_id} suspendido (sincronización): {success}")
                        
                    elif op.operation_type in ['activate', 'restore']:
                        success = adapter.restore_client_service(client_data)
                        logger.info(f"✅ Cliente {op.client_id} activado/restaurado (sincronización): {success}")
                    
                    elif op.operation_type == 'delete':
                        success = adapter.remove_client_service(client_data)
                        logger.info(f"✅ Cliente {op.client_id} eliminado de MikroTik (sincronización): {success}")

                    if success:
                        # Marcar como completada
                        op.status = 'completed'
                        op.last_attempt = datetime.now()
                        op.attempts += 1
                        completed += 1
                    else:
                        raise Exception("Adapter operation returned False (failed)")
                    
                except Exception as e:
                    logger.error(f"❌ Error ejecutando operación {op.id} ({op.operation_type}): {e}")
                    op.attempts += 1
                    op.last_attempt = datetime.now()
                    op.error_message = str(e)
                    
                    # Marcar como fallida si supera intentos
                    if op.attempts >= 5:
                        op.status = 'failed'
                        failed += 1
                
                session.merge(op)
            
            session.commit()
            logger.info(f"✅ Sincronización completa: {completed} exitosas, {failed} fallidas")
            
        except Exception as e:
            logger.error(f"❌ Error conectando al router para sincronización: {e}")
            
        finally:
            if adapter:
                adapter.disconnect()
            session.close()
        
        return {
            'total': len(operations),
            'completed': completed,
            'failed': failed
        }
    
    def clean_old_operations(self, days: int = 30):
        """Elimina operaciones completadas o fallidas más antiguas que N días"""
        session = self.db.session
        
        try:
            from datetime import timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            
            deleted = session.query(PendingOperation).filter(
                PendingOperation.status.in_(['completed', 'failed']),
                PendingOperation.created_at < cutoff_date
            ).delete()
            
            session.commit()
            logger.info(f"🗑️ Eliminadas {deleted} operaciones antiguas")
            return deleted
            
        except Exception as e:
            logger.error(f"❌ Error limpiando operaciones antiguas: {e}")
            session.rollback()
            return 0
            
        finally:
            session.close()
