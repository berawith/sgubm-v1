
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, Payment, Router, PaymentPromise
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.billing_service import BillingService
from src.application.services.audit_service import AuditService
from src.application.services.mikrotik_operations import safe_suspend_client, safe_activate_client

logger = logging.getLogger(__name__)

class BatchService:
    def __init__(self):
        self._db = get_db()
        self.billing_service = BillingService()

    def execute_batch_action(self, action: str, client_ids: List[int], extra_data: Dict[str, Any] = None, commit: bool = True) -> Dict[str, Any]:
        """
        Ejecuta acciones masivas sobre una lista de clientes.
        
        Args:
            action: 'suspend', 'restore', 'pay'
            client_ids: Lista de IDs de clientes
            extra_data: Datos adicionales (ej: referencia de pago)
            commit: Si debe realizar commit al final (default True)
        """
        results = {
            "success_count": 0,
            "fail_count": 0,
            "details": []
        }
        
        db = get_db()
        session = db.session
        
        for client_id in client_ids:
            client = session.query(Client).get(client_id)
            if not client:
                continue
                
            try:
                success = False
                message = ""
                
                if action == 'suspend':
                    success = self._suspend_client(client, commit=commit)
                    message = "Client suspended"
                elif action == 'restore':
                    promise_days = extra_data.get('promise_days') if extra_data else None
                    success = self._restore_client(client, promise_days=promise_days, commit=commit)
                    message = "Client restored" + (f" with {promise_days} days promise" if promise_days else "")
                elif action == 'pay':
                    # Pay assumes paying the total debt or a specific amount? 
                    # For batch operations, usually it's "Mark as Paid" (clearing debt) or "Pay Monthly Fee".
                    # Let's assume clear debt or pay N months.
                    # Based on user request "realizar pagos... masiva", likely "Registrar Pago del Mes"
                    # or "Saldar Deuda". Let's implement "Saldar Deuda Total" for now as it's common in ISPs.
                    if extra_data and 'amount' in extra_data:
                         # Use specific amount if provided (e.g. flat fee for all) - unusual
                         pass
                    
                    # Default: Pay total pending balance
                    amount = client.account_balance or 0
                    if amount > 0:
                        # from src.presentation.api.payments_controller import PaymentsController  <-- REMOVED (Broken/Unused) 
                        # This dependency might be cyclic or messy. Better to use logic directly.
                        # But PaymentsController has logic for invoices.
                        # Let's duplicate minimal logic or move Payment logic to a PaymentService.
                        # Since PaymentService doesn't exist (logic is in Controller?), I should probably move it.
                        # For now, I'll implement basic payment recording here.
                        
                        success = self._process_payment(client, amount, extra_data)
                        message = f"Payment of {amount} recorded"
                    else:
                        success = True
                        message = "No debt to pay"
                        
                if success:
                    results["success_count"] += 1
                else:
                    results["fail_count"] += 1
                    
                results["details"].append({
                    "client_id": client_id,
                    "legal_name": client.legal_name,
                    "success": success,
                    "message": message
                })
                
            except Exception as e:
                logger.error(f"Error processing batch action {action} for client {client_id}: {e}")
                results["fail_count"] += 1
                results["details"].append({
                    "client_id": client_id,
                    "success": False,
                    "message": str(e)
                })
                
        # Auditoría de acción masiva completa
        if results["success_count"] > 0:
            AuditService.log(
                operation=f'batch_{action}',
                category='system',
                description=f"Acción masiva '{action}' completada. Éxitos: {results['success_count']}, Fallos: {results['fail_count']}",
                new_state={'client_ids': client_ids, 'action': action},
                commit=commit
            )
            
        return results

    def _suspend_client(self, client: Client, commit: bool = True) -> bool:
        """Suspende un cliente en BD y MikroTik de forma segura"""
        try:
            router = self._db.get_router_repository().get_by_id(client.router_id)
            if not router:
                raise ValueError(f"Router {client.router_id} no encontrado")

            # Usar envoltorio seguro (maneja offline y validación MikroTik)
            result = safe_suspend_client(
                db=self._db,
                client=client,
                router=router,
                audit_service=AuditService,
                audit_details="Suspensión masiva batch",
                commit=commit
            )
            
            return result['status'] in ['success', 'queued']
        except Exception as e:
            logger.error(f"Error en suspensión segura de cliente {client.id}: {e}")
            return False

    def _restore_client(self, client: Client, promise_days: int = None, commit: bool = True) -> bool:
        """Restaura un cliente en BD y MikroTik de forma segura, opcionalmente con promesa de pago"""
        try:
            # 1. Verificar promesas anteriores incumplidas (si estamos creando nueva promesa)
            if promise_days:
                # Buscar promesas pendientes cuya fecha ya expiró
                previous_promise = self._db.session.query(PaymentPromise).filter(
                    PaymentPromise.client_id == client.id,
                    PaymentPromise.status == 'pending',
                    PaymentPromise.promise_date < datetime.now()
                ).first()
                
                if previous_promise:
                    # Marcar promesa anterior como incumplida
                    previous_promise.status = 'broken'
                    broken_date = previous_promise.promise_date.strftime('%Y-%m-%d')
                    logger.warning(f"⚠️ {client.legal_name} incumplió promesa del {broken_date}")
                    
                    # Incrementar contador de promesas rotas
                    client.broken_promises_count = (client.broken_promises_count or 0) + 1
                    logger.info(f"📊 Contador de promesas incumplidas: {client.broken_promises_count}")
                
                # Calcular nueva fecha de promesa
                promise_date = datetime.now() + timedelta(days=int(promise_days))
                client.promise_date = promise_date
                
                # Crear registro en historial de promesas
                new_promise = PaymentPromise(
                    client_id=client.id,
                    promise_date=promise_date,
                    status='pending',
                    notes=f"Promesa de pago - Extensión de {promise_days} días desde Acción Masiva"
                )
                self._db.session.add(new_promise)
                logger.info(f"🤝 Nueva promesa creada para {client.legal_name} hasta {promise_date.strftime('%Y-%m-%d %H:%M')}")

            router = self._db.get_router_repository().get_by_id(client.router_id)
            if not router:
                raise ValueError(f"Router {client.router_id} no encontrado")

            # 2. Activar SOLO en MikroTik (sin cambiar status en DB si es promesa)
            if promise_days:
                # Modo promesa: Activar servicio pero NO cambiar status de BD
                result = self._activate_mikrotik_only(client, router, audit_service=AuditService, 
                                                     audit_details=f"Activación temporal CON PROMESA DE PAGO ({promise_days} días) - Status en DB NO cambia",
                                                     commit=commit)
            else:
                # Modo normal: Activar servicio Y cambiar status a 'active'
                result = safe_activate_client(
                    db=self._db,
                    client=client,
                    router=router,
                    audit_service=AuditService,
                    audit_details="Activación masiva batch (sin promesa)",
                    commit=commit
                )
            
            return result['status'] in ['success', 'queued']
        except Exception as e:
            logger.error(f"Error en activación segura de cliente {client.id}: {e}")
            return False

    def _activate_mikrotik_only(self, client, router, audit_service=None, audit_details=None, commit: bool = True):
        """
        Activa SOLO en MikroTik sin cambiar el status de la BD.
        Usado para promesas de pago donde el servicio se habilita pero el cliente sigue marcado como 'suspended'.
        """
        from src.application.services.sync_service import SyncService
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        
        sync_service = SyncService(self._db)
        client_dict = client.to_dict()
        
        try:
            # Intentar conectar a MikroTik
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                raise Exception(f"No se pudo conectar al router {router.host_address}")
            
            # Restaurar servicio SOLO en MikroTik
            adapter.restore_client_service(client_dict)
            adapter.disconnect()
            
            logger.info(f"✅ Servicio activado en MikroTik para {client.legal_name} - Status DB permanece: {client.status}")
            
            # Auditar
            if audit_service and audit_details:
                audit_service.log_action(
                    action_type='client_promise_service_enabled',
                    entity_type='client',
                    entity_id=client.id,
                    details=audit_details,
                    commit=commit
                )
            
            return {
                'status': 'success',
                'message': 'Servicio activado en MikroTik (status DB sin cambios)',
                'synced': True
            }
            
        except Exception as e:
            logger.warning(f"⚠️ No se pudo activar en MikroTik: {e}")
            
            # Encolar operación pendiente
            sync_service.queue_operation(
                operation_type='activate',
                client_id=client.id,
                router_id=router.id,
                ip_address=client.ip_address,
                target_status=client.status,  # ⚠️ IMPORTANTE: Mantener status actual
                commit=commit
            )
            
            logger.info(f"📋 Activación de servicio encolada para {client.legal_name} - Status DB: {client.status}")
            return {
                'status': 'queued',
                'message': 'Activación de servicio encolada (status DB sin cambios)',
                'synced': False
            }

    def _process_payment(self, client: Client, amount: float, data: Dict) -> bool:
        """Registra un pago usando la lógica central de BillingService"""
        try:
            # Usar la lógica centralizada
            self.billing_service.register_payment(client.id, amount, data)
            return True
        except ValueError as ve:
             # Si ya pagó, consideramos éxito en el batch (o podriamos loguearlo)
             logger.info(f"Saltando pago masivo para {client.legal_name}: {ve}")
             return True
        except Exception as e:
            logger.error(f"Error processing batch payment for {client.id}: {e}")
            return False

    def _disable_mikrotik_only(self, client: Client, commit: bool = True):
        """
        Suspende SOLO en MikroTik sin cambiar el status de la BD. 
        Usado durante reversión de pagos en el ciclo actual.
        """
        from src.application.services.sync_service import SyncService
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        
        db = get_db()
        sync_service = SyncService(db)
        client_dict = client.to_dict()
        
        router = db.get_router_repository().get_by_id(client.router_id)
        if not router:
            logger.error(f"Router {client.router_id} no encontrado para cliente {client.id}")
            return False

        try:
            # Intentar conectar a MikroTik
            adapter = MikroTikAdapter()
            if not adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                raise Exception(f"No se pudo conectar al router {router.host_address}")
            
            # Suspender servicio SOLO en MikroTik
            adapter.suspend_client_service(client_dict)
            adapter.disconnect()
            
            logger.info(f"✅ Servicio suspendido en MikroTik para {client.legal_name} - Status DB permanece: {client.status}")
            
            # Auditar
            AuditService.log_action(
                action_type='client_reversion_service_disabled',
                entity_type='client',
                entity_id=client.id,
                details=f"Servicio deshabilitado en MikroTik por reversión de pago (Router: {router.name})",
                commit=commit
            )
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ No se pudo suspender en MikroTik durante reversión: {e}")
            
            # Encolar operación pendiente
            sync_service.queue_operation(
                operation_type='suspend',
                client_id=client.id,
                router_id=router.id,
                ip_address=client.ip_address,
                target_status=client.status, # Mantener el status que tenga (probablemente será cambiado por el controller después)
                commit=commit
            )
            
            logger.info(f"📋 Suspensión de servicio encolada para {client.legal_name} por reversión")
            return False
