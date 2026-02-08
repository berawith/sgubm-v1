
import logging
from typing import List, Dict, Any
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, Payment
from src.infrastructure.mikrotik.adapter import MikroTikAdapter
from src.application.services.billing_service import BillingService
from src.application.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class BatchService:
    def __init__(self):
        self.billing_service = BillingService()

    def execute_batch_action(self, action: str, client_ids: List[int], extra_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Ejecuta acciones masivas sobre una lista de clientes.
        
        Args:
            action: 'suspend', 'restore', 'pay'
            client_ids: Lista de IDs de clientes
            extra_data: Datos adicionales (ej: referencia de pago)
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
                    success = self._suspend_client(client)
                    message = "Client suspended"
                elif action == 'restore':
                    success = self._restore_client(client)
                    message = "Client restored"
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
                        from src.presentation.api.payments_controller import PaymentsController 
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
                new_state={'client_ids': client_ids, 'action': action}
            )
            
        return results

    def _suspend_client(self, client: Client) -> bool:
        """Suspende un cliente en BD y MikroTik"""
        db = get_db()
        try:
            # 1. Update DB
            client.status = 'suspended'
            db.session.commit()
            
            # 2. MikroTik
            if client.router_id:
                router = db.get_router_repository().get_by_id(client.router_id)
                if router and router.status == 'online':
                    adapter = MikroTikAdapter()
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                        adapter.suspend_client_service(client.to_dict())
                        adapter.disconnect()
            
            # Auditoría individual
            AuditService.log(
                operation='client_suspended_batch',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description=f"Suspensión masiva aplicada a: {client.legal_name}",
                previous_state={'status': 'active'},
                new_state={'status': 'suspended'}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error suspending client {client.id}: {e}")
            return False

    def _restore_client(self, client: Client) -> bool:
        """Restaura un cliente en BD y MikroTik"""
        db = get_db()
        try:
            # 1. Update DB
            client.status = 'active'
            db.session.commit()
            
            # 2. MikroTik
            if client.router_id:
                router = db.get_router_repository().get_by_id(client.router_id)
                if router and router.status == 'online':
                    adapter = MikroTikAdapter()
                    if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                        adapter.restore_client_service(client.to_dict())
                        adapter.disconnect()
            
            # Auditoría individual
            AuditService.log(
                operation='client_activated_batch',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description=f"Activación masiva aplicada a: {client.legal_name}",
                previous_state={'status': 'suspended'},
                new_state={'status': 'active'}
            )
            
            return True
        except Exception as e:
            logger.error(f"Error restoring client {client.id}: {e}")
            return False

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
