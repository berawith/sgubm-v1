"""
Database Repositories
Implementaciones de IRepository para acceso a datos
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from src.infrastructure.database.models import Router, Client, Payment, RouterStatus, ClientStatus, Invoice, InvoiceItem, WhatsAppMessage, SystemSetting, Expense, ClientTrafficHistory
from src.domain.services.audit_service import AuditService


class RouterRepository:
    """Repositorio para gestión de Routers"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any], commit: bool = True) -> Router:
        """Crea un nuevo router"""
        router = Router(**data)
        self.session.add(router)
        if commit:
            self.session.commit()
            self.session.refresh(router)
        return router
    
    def get_by_id(self, router_id: int) -> Optional[Router]:
        """Obtiene un router por ID"""
        return self.session.query(Router).filter(Router.id == router_id).first()
    
    def get_all(self) -> List[Router]:
        """Obtiene todos los routers"""
        return self.session.query(Router).all()
    
    def get_by_status(self, status: str) -> List[Router]:
        """Obtiene routers por estado"""
        return self.session.query(Router).filter(Router.status == status).all()
    
    def update(self, router_id: int, data: Dict[str, Any], commit: bool = True) -> Optional[Router]:
        """Actualiza un router"""
        router = self.get_by_id(router_id)
        if router:
            for key, value in data.items():
                if hasattr(router, key) and key != 'id':
                    setattr(router, key, value)
            router.updated_at = datetime.now()
            if commit:
                self.session.commit()
                self.session.refresh(router)
        return router
    
    def delete(self, router_id: int, commit: bool = True) -> bool:
        """Elimina un router"""
        router = self.get_by_id(router_id)
        if router:
            self.session.delete(router)
            if commit:
                self.session.commit()
            return True
        return False
    
    def update_metrics(self, router_id: int, metrics: Dict[str, Any], commit: bool = True) -> Optional[Router]:
        """Actualiza métricas del router"""
        router = self.get_by_id(router_id)
        if router:
            router.cpu_usage = metrics.get('cpu_usage', router.cpu_usage)
            router.memory_usage = metrics.get('memory_usage', router.memory_usage)
            router.clients_connected = metrics.get('clients_connected', router.clients_connected)
            router.uptime = metrics.get('uptime', router.uptime)
            router.status = metrics.get('status', router.status)
            router.last_sync = datetime.now()
            if commit:
                self.session.commit()
                self.session.refresh(router)
        return router


class ClientRepository:
    """Repositorio para gestión de Clientes"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any], commit: bool = True) -> Client:
        """Crea un nuevo cliente"""
        client = Client(**data)
        self.session.add(client)
        if commit:
            self.session.commit()
            self.session.refresh(client)
        return client
    
    def get_by_id(self, client_id: int) -> Optional[Client]:
        """Obtiene un cliente por ID"""
        return self.session.query(Client).filter(Client.id == client_id).first()
    
    def get_by_subscriber_code(self, code: str) -> Optional[Client]:
        """Obtiene un cliente por código de suscriptor"""
        return self.session.query(Client).filter(Client.subscriber_code == code).first()
    
    def get_all(self) -> List[Client]:
        """Obtiene todos los clientes"""
        return self.session.query(Client).all()
    
    def get_by_username(self, username: str) -> Optional[Client]:
        """Obtiene un cliente por nombre de usuario"""
        return self.session.query(Client).filter(Client.username == username).first()
    
    def get_by_router(self, router_id: int) -> List[Client]:
        """Obtiene clientes de un router específico"""
        return self.session.query(Client).filter(Client.router_id == router_id).all()
    
    def get_by_status(self, status: str) -> List[Client]:
        """Obtiene clientes por estado"""
        return self.session.query(Client).options(joinedload(Client.router), joinedload(Client.assigned_collector), joinedload(Client.internet_plan)).filter(Client.status == status).all()
    
    def search(self, query: str) -> List[Client]:
        """Busca clientes por nombre, código, documento o IP"""
        search_pattern = f"%{query}%"
        return self.session.query(Client).options(joinedload(Client.router), joinedload(Client.assigned_collector), joinedload(Client.internet_plan)).filter(
            (Client.legal_name.ilike(search_pattern)) |
            (Client.subscriber_code.ilike(search_pattern)) |
            (Client.identity_document.ilike(search_pattern)) |
            (Client.username.ilike(search_pattern)) |
            (Client.plan_name.ilike(search_pattern)) |
            (Client.ip_address.ilike(search_pattern))
        ).all()

    def get_filtered(self, router_id: Optional[Any] = None, status: Optional[str] = None, 
                     search: Optional[str] = None, plan_id: Optional[int] = None,
                     assigned_collector_id: Optional[int] = None) -> List[Client]:
        """Obtiene clientes con filtros combinados, con carga ansiosa de relaciones"""
        query_obj = self.session.query(Client).options(
            joinedload(Client.router), 
            joinedload(Client.assigned_collector), 
            joinedload(Client.internet_plan)
        )

        if router_id:
            if isinstance(router_id, list):
                query_obj = query_obj.filter(Client.router_id.in_(router_id))
            else:
                query_obj = query_obj.filter(Client.router_id == router_id)

        if assigned_collector_id:
            # Logic: Explicitly assigned OR (Not explicitly assigned AND router is assigned to this collector)
            from src.infrastructure.database.models import User, CollectorAssignment
            
            # Get router IDs from multi-router assignments (new system)
            assigned_router_subq = self.session.query(CollectorAssignment.router_id).filter(
                CollectorAssignment.user_id == assigned_collector_id
            )
            # Fallback: also check legacy assigned_router_id
            legacy_router_subq = self.session.query(User.assigned_router_id).filter(
                User.id == assigned_collector_id,
                User.assigned_router_id != None
            )
            
            query_obj = query_obj.filter(
                (Client.assigned_collector_id == assigned_collector_id) |
                (
                    (Client.assigned_collector_id == None) & 
                    (Client.router_id.in_(assigned_router_subq.union(legacy_router_subq)))
                )
            )

        if plan_id:
            query_obj = query_obj.filter(Client.plan_id == plan_id)

        if status and status.upper() != 'ALL':
            s_upper = status.upper()
            # print(f"DEBUG: Filtering Clients - Status: {s_upper}")
            if s_upper == 'ONLINE':
                 query_obj = query_obj.filter(Client.is_online == True)
            elif s_upper == 'OFFLINE':
                 # Handle both False and NULL as offline
                 query_obj = query_obj.filter((Client.is_online == False) | (Client.is_online == None))
            elif s_upper == 'DEBTORS': 
                 # Clientes con deuda positiva
                 query_obj = query_obj.filter(Client.account_balance > 0)
            elif s_upper == 'DELETED':
                query_obj = query_obj.filter(Client.status == 'deleted')
            else:
                # Default: Filter by status column (lowercase)
                # Valid statuses: active, suspended, inactive
                query_obj = query_obj.filter(Client.status == status.lower())
        else:
             # Default: Exclude deleted unless specifically asked via 'ALL' or 'deleted' filter
             # If status is ALL, strictly speaking we usually want active/suspended, not deleted.
             query_obj = query_obj.filter(Client.status != 'deleted')

        if search:
            search_pattern = f"%{search}%"
            query_obj = query_obj.filter(
                (Client.legal_name.ilike(search_pattern)) |
                (Client.subscriber_code.ilike(search_pattern)) |
                (Client.identity_document.ilike(search_pattern)) |
                (Client.username.ilike(search_pattern)) |
                (Client.plan_name.ilike(search_pattern)) |
                (Client.ip_address.ilike(search_pattern))
            )
        
        return query_obj.all()
    
    def update(self, client_id: int, data: Dict[str, Any], commit: bool = True) -> Optional[Client]:
        """Actualiza un cliente"""
        client = self.get_by_id(client_id)
        if client:
            for key, value in data.items():
                if hasattr(client, key) and key != 'id':
                    setattr(client, key, value)
            client.updated_at = datetime.now()
            if commit:
                self.session.commit()
                self.session.refresh(client)
        return client
    
    def delete(self, client_id: int, commit: bool = True) -> bool:
        """Elimina un cliente"""
        client = self.get_by_id(client_id)
        if client:
            self.session.delete(client)
            if commit:
                self.session.commit()
            return True
        return False
    
    def suspend(self, client_id: int, commit: bool = True) -> Optional[Client]:
        """Suspende un cliente"""
        client = self.get_by_id(client_id)
        if client:
            client.status = 'suspended'
            client.updated_at = datetime.now()
            if commit:
                self.session.commit()
                self.session.refresh(client)
        return client
    
    def activate(self, client_id: int, commit: bool = True) -> Optional[Client]:
        """Activa un cliente"""
        client = self.get_by_id(client_id)
        if client:
            client.status = 'active'
            client.updated_at = datetime.now()
            if commit:
                self.session.commit()
                self.session.refresh(client)
        return client
    
    def update_balance(self, client_id: int, amount: float, operation: str = 'add', commit: bool = True) -> Optional[Client]:
        """Actualiza el balance del cliente"""
        client = self.get_by_id(client_id)
        if client:
            current_balance = client.account_balance or 0.0
            if operation == 'add':
                client.account_balance = current_balance + amount
            elif operation == 'subtract':
                client.account_balance = current_balance - amount
            elif operation == 'set':
                client.account_balance = amount
            if commit:
                self.session.commit()
                self.session.refresh(client)
        return client



class PaymentRepository:
    """Repositorio para gestión de Pagos"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any], commit: bool = True) -> Payment:
        """Registra un nuevo pago con integridad ERP"""
        # Calcular campos ERP si no vienen (por defecto 1:1)
        if 'base_amount' not in data:
            data['base_amount'] = data.get('amount')
        if 'exchange_rate' not in data:
            data['exchange_rate'] = 1.0
            
        # Calcular Hash de integridad inicial
        data['transaction_hash'] = AuditService.calculate_transaction_hash('payment', data)
        
        payment = Payment(**data)
        self.session.add(payment)
        if commit:
            self.session.commit()
            self.session.refresh(payment)
        return payment
    
    def get_by_id(self, payment_id: int) -> Optional[Payment]:
        """Obtiene un pago por ID"""
        return self.session.query(Payment).filter(Payment.id == payment_id).first()
    
    def get_all(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: int = 100, status: Optional[str] = None) -> List[Payment]:
        """Obtiene todos los pagos (limitado) con filtro opcional de fechas y estado"""
        query = self.session.query(Payment)
        
        if start_date:
            query = query.filter(Payment.payment_date >= start_date)
        if end_date:
            query = query.filter(Payment.payment_date <= end_date)
        if status:
            query = query.filter(Payment.status == status)
            
        return query.order_by(Payment.payment_date.desc()).limit(limit).all()
    
    def get_by_client(self, client_id: int) -> List[Payment]:
        """Obtiene todos los pagos de un cliente"""
        return self.session.query(Payment).filter(Payment.client_id == client_id).order_by(Payment.payment_date.desc()).all()
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime, router_id: Optional[Any] = None) -> List[Payment]:
        """Obtiene pagos en un rango de fechas"""
        query = self.session.query(Payment)
        if router_id:
            query = query.join(Client, Payment.client_id == Client.id)
            if isinstance(router_id, list):
                query = query.filter(Client.router_id.in_(router_id))
            else:
                query = query.filter(Client.router_id == router_id)
            
        return query.filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date
        ).order_by(Payment.payment_date.desc()).all()

    def get_filtered(self, client_id: Optional[int] = None, router_id: Optional[int] = None, 
                     start_date: Optional[datetime] = None, 
                     end_date: Optional[datetime] = None, method: Optional[str] = None, 
                     search: Optional[str] = None, limit: int = 100,
                     router_ids: Optional[List[int]] = None, status: Optional[str] = None) -> List[Payment]:
        """Obtiene pagos con filtros combinados (Optimizado con joinedload)"""
        query = self.session.query(Payment).options(joinedload(Payment.client)).join(Client, Payment.client_id == Client.id)

        if router_ids:
            query = query.filter(Client.router_id.in_(router_ids))
        elif router_id:
            query = query.filter(Client.router_id == router_id)

        if client_id:
            query = query.filter(Payment.client_id == client_id)
        
        if start_date:
            query = query.filter(Payment.payment_date >= start_date)
            
        if end_date:
            query = query.filter(Payment.payment_date <= end_date)
            
        if method and method != 'all':
            query = query.filter(Payment.payment_method == method)
            
        if status:
            query = query.filter(Payment.status == status)
            
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Client.legal_name.ilike(search_pattern)) |
                (Client.subscriber_code.ilike(search_pattern)) |
                (Payment.reference.ilike(search_pattern))
            )

        return query.order_by(Payment.payment_date.desc()).limit(limit).all()
    
    def get_today_payments(self) -> List[Payment]:
        """Obtiene los pagos de hoy"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.session.query(Payment).filter(
            Payment.payment_date >= today_start
        ).order_by(Payment.payment_date.desc()).all()
    
    def get_total_by_date_range(self, start_date: datetime, end_date: datetime, client_id: Optional[int] = None, router_id: Optional[int] = None, router_ids: Optional[List[int]] = None) -> float:
        """Calcula el total de pagos en un rango, con filtros opcionales (soporta multi-router)"""
        query = self.session.query(Payment).join(Client, Payment.client_id == Client.id)
        
        query = query.filter(Payment.payment_date >= start_date)
        query = query.filter(Payment.payment_date <= end_date)
        
        # Consistent with SUCCESS_STATUSES in controller
        query = query.filter(Payment.status.in_(['paid', 'verified', 'approved', 'success']))
        
        if client_id:
            query = query.filter(Payment.client_id == client_id)
        if router_id:
            if isinstance(router_id, list):
                query = query.filter(Client.router_id.in_(router_id))
            else:
                query = query.filter(Client.router_id == router_id)
        if router_ids:
            query = query.filter(Client.router_id.in_(router_ids))
            
        result = query.all()
        return sum(p.amount for p in result)
    
    def update(self, payment_id: int, data: Dict[str, Any], commit: bool = True) -> Optional[Payment]:
        """Actualiza un pago"""
        payment = self.get_by_id(payment_id)
        if payment:
            for key, value in data.items():
                if hasattr(payment, key) and key != 'id':
                    setattr(payment, key, value)
            payment.updated_at = datetime.now()
            if commit:
                self.session.commit()
                self.session.refresh(payment)
        return payment
    
    def delete(self, payment_id: int, commit: bool = True) -> bool:
        """Elimina un pago"""
        payment = self.get_by_id(payment_id)
        if payment:
            self.session.delete(payment)
            if commit:
                self.session.commit()
            return True
        return False


class DeletedPaymentRepository:
    """Repositorio para gestión de Pagos Eliminados (Papelera)"""
    
    def __init__(self, session: Session):
        self.session = session
        
    def create_from_payment(self, payment, deleted_by: str = 'system', reason: str = '', commit: bool = True) -> 'DeletedPayment':
        from src.infrastructure.database.models import DeletedPayment
        deleted = DeletedPayment(
            original_id=payment.id,
            client_id=payment.client_id,
            amount=payment.amount,
            currency=payment.currency,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            reference=payment.reference,
            notes=payment.notes,
            deleted_by=deleted_by,
            reason=reason
        )
        self.session.add(deleted)
        if commit:
            self.session.commit()
        return deleted

    def get_all(self, limit: int = 100) -> List['DeletedPayment']:
        from src.infrastructure.database.models import DeletedPayment
        return self.session.query(DeletedPayment).order_by(DeletedPayment.deleted_at.desc()).limit(limit).all()

    def get_by_id(self, deleted_id: int) -> Optional['DeletedPayment']:
        from src.infrastructure.database.models import DeletedPayment
        return self.session.query(DeletedPayment).filter(DeletedPayment.id == deleted_id).first()

    def delete(self, deleted_id: int, commit: bool = True) -> bool:
        deleted = self.get_by_id(deleted_id)
        if deleted:
            self.session.delete(deleted)
            if commit:
                self.session.commit()
            return True
        return False

    def delete_batch(self, deleted_ids: List[int], commit: bool = True) -> int:
        from src.infrastructure.database.models import DeletedPayment
        count = self.session.query(DeletedPayment).filter(DeletedPayment.id.in_(deleted_ids)).delete(synchronize_session=False)
        if commit:
            self.session.commit()
        return count

    def clear_all(self, commit: bool = True) -> int:
        from src.infrastructure.database.models import DeletedPayment
        count = self.session.query(DeletedPayment).delete()
        if commit:
            self.session.commit()
        return count





class TrafficRepository:
    """Repositorio para historial de tráfico"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def add_snapshot(self, data: Dict[str, Any], commit: bool = True) -> ClientTrafficHistory:
        """Agrega un snapshot de tráfico al historial"""
        from src.infrastructure.database.models import ClientTrafficHistory
        snapshot = ClientTrafficHistory(**data)
        self.session.add(snapshot)
        if commit:
            self.session.commit()
        return snapshot
    
    def get_history(self, client_id: int, hours: int = 24) -> List[ClientTrafficHistory]:
        """Obtiene historial de un cliente en un rango de horas"""
        from src.infrastructure.database.models import ClientTrafficHistory
        from datetime import datetime, timedelta
        
        since = datetime.now() - timedelta(hours=hours)
        return self.session.query(ClientTrafficHistory)\
            .filter(ClientTrafficHistory.client_id == client_id)\
            .filter(ClientTrafficHistory.timestamp >= since)\
            .order_by(ClientTrafficHistory.timestamp.asc()).all()
    
    def delete_old_history(self, days: int = 30):
        """Limpia historial antiguo para evitar crecimiento excesivo de la BD"""
        from src.infrastructure.database.models import ClientTrafficHistory
        from datetime import datetime, timedelta
        
        limit = datetime.now() - timedelta(days=days)
        self.session.query(ClientTrafficHistory)\
            .filter(ClientTrafficHistory.timestamp < limit).delete()
        self.session.commit()


class InvoiceRepository:
    """Repositorio para gestión de Facturas"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any], commit: bool = True) -> Invoice:
        """Crea una nueva factura"""
        invoice = Invoice(**data)
        self.session.add(invoice)
        if commit:
            self.session.commit()
            self.session.refresh(invoice)
        return invoice
    
    def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """Obtiene una factura por ID"""
        return self.session.query(Invoice).filter(Invoice.id == invoice_id).first()
    
    def get_all(self, limit: int = 100) -> List[Invoice]:
        """Obtiene todas las facturas"""
        return self.session.query(Invoice).order_by(Invoice.issue_date.desc()).limit(limit).all()
    
    def get_by_client(self, client_id: int) -> List[Invoice]:
        """Obtiene facturas de un cliente"""
        return self.session.query(Invoice).filter(Invoice.client_id == client_id).order_by(Invoice.issue_date.desc()).all()
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime, router_id: Optional[Any] = None) -> List[Invoice]:
        """Obtiene facturas en un rango de fechas de emisión"""
        query = self.session.query(Invoice)
        if router_id:
            query = query.join(Client, Invoice.client_id == Client.id)
            if isinstance(router_id, list):
                query = query.filter(Client.router_id.in_(router_id))
            else:
                query = query.filter(Client.router_id == router_id)
            
        return query.filter(
            Invoice.issue_date >= start_date,
            Invoice.issue_date <= end_date
        ).all()

    def get_filtered(self, client_id: Optional[int] = None, router_id: Optional[int] = None, 
                      start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, 
                      status: Optional[str] = None, limit: int = 100) -> List[Invoice]:
        """Obtiene facturas con filtros avanzados"""
        from src.infrastructure.database.models import Client
        query = self.session.query(Invoice).join(Client, Invoice.client_id == Client.id)
        
        if client_id:
            query = query.filter(Invoice.client_id == client_id)
        if router_id:
            query = query.filter(Client.router_id == router_id)
        if start_date:
            query = query.filter(Invoice.issue_date >= start_date)
        if end_date:
            query = query.filter(Invoice.issue_date <= end_date)
        if status and status != 'all':
            query = query.filter(Invoice.status == status)
            
        return query.order_by(Invoice.issue_date.desc()).limit(limit).all()

class WhatsAppRepository:
    """Repositorio para gestión de historial de WhatsApp"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any], commit: bool = True) -> WhatsAppMessage:
        """Guarda un nuevo mensaje en el historial"""
        message = WhatsAppMessage(**data)
        self.session.add(message)
        if commit:
            self.session.commit()
            self.session.refresh(message)
        return message
    
    def get_by_client(self, client_id: int, limit: int = 50) -> List[WhatsAppMessage]:
        """Obtiene historial de un cliente"""
        return self.session.query(WhatsAppMessage)\
            .filter(WhatsAppMessage.client_id == client_id)\
            .order_by(WhatsAppMessage.timestamp.desc())\
            .limit(limit).all()
            
    def get_latest_conversations(self, limit: int = 20) -> List[WhatsAppMessage]:
        """Obtiene los últimos mensajes de conversaciones únicas"""
        from sqlalchemy import func
        subquery = self.session.query(
            WhatsAppMessage.phone, 
            func.max(WhatsAppMessage.timestamp).label('max_ts')
        ).group_by(WhatsAppMessage.phone).subquery()
        
        return self.session.query(WhatsAppMessage)\
            .join(subquery, (WhatsAppMessage.phone == subquery.c.phone) & (WhatsAppMessage.timestamp == subquery.c.max_ts))\
            .order_by(WhatsAppMessage.timestamp.desc())\
            .limit(limit).all()

    def get_history_by_phone(self, phone: str, limit: int = 50) -> List[WhatsAppMessage]:
        """Obtiene historial por número de teléfono"""
        return self.session.query(WhatsAppMessage)\
            .filter(WhatsAppMessage.phone == phone)\
            .order_by(WhatsAppMessage.timestamp.asc())\
            .limit(limit).all()

    def get_recent_context(self, phone: str, limit: int = 5) -> str:
        """Obtiene los últimos mensajes formateados como contexto para la IA"""
        messages = self.session.query(WhatsAppMessage)\
            .filter(WhatsAppMessage.phone == phone)\
            .order_by(WhatsAppMessage.timestamp.desc())\
            .limit(limit).all()
        
        context = []
        for msg in reversed(messages):
            role = "Asistente" if msg.is_outgoing else "Cliente"
            context.append(f"{role}: {msg.message_text}")
            
        return "\n".join(context)

class SystemSettingRepository:
    """Repositorio para gestión de configuración del sistema"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Obtiene el valor de una configuración"""
        setting = self.session.query(SystemSetting).filter(SystemSetting.key == key).first()
        return setting.value if setting else default
    
    def set_value(self, key: str, value: Any, category: str = 'general', description: str = '', commit: bool = True) -> SystemSetting:
        """Guarda o actualiza una configuración"""
        setting = self.session.query(SystemSetting).filter(SystemSetting.key == key).first()
        
        if setting:
            setting.value = str(value)
            if description:
                setting.description = description
            if category:
                setting.category = category
        else:
            setting = SystemSetting(
                key=key,
                value=str(value),
                category=category,
                description=description
            )
            self.session.add(setting)
            
        if commit:
            self.session.commit()
            self.session.refresh(setting)
        return setting

    def get_all_by_category(self, category: str) -> Dict[str, str]:
        """Obtiene todas las configuraciones de una categoría"""
class ExpenseRepository:
    """Repositorio para gestión de Gastos y Deducibles"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any], commit: bool = True) -> Expense:
        """Registra un nuevo gasto con integridad ERP"""
        # Calcular campos ERP si no vienen (por defecto 1:1)
        if 'base_amount' not in data:
            data['base_amount'] = data.get('amount')
        if 'exchange_rate' not in data:
            data['exchange_rate'] = 1.0
            
        # Calcular Hash de integridad inicial
        data['transaction_hash'] = AuditService.calculate_transaction_hash('expense', data)
        
        expense = Expense(**data)
        self.session.add(expense)
        if commit:
            self.session.commit()
            self.session.refresh(expense)
        return expense
    
    def get_by_id(self, expense_id: int) -> Optional[Expense]:
        """Obtiene un gasto por ID"""
        return self.session.query(Expense).filter(Expense.id == expense_id).first()
    
    def get_all(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None, limit: int = 100) -> List[Expense]:
        """Obtiene todos los gastos con filtros opcionales"""
        query = self.session.query(Expense)
        
        if start_date:
            query = query.filter(Expense.expense_date >= start_date)
        if end_date:
            query = query.filter(Expense.expense_date <= end_date)
            
        return query.order_by(Expense.expense_date.desc()).limit(limit).all()

    def get_filtered(self, category: Optional[str] = None, start_date: Optional[datetime] = None, 
                     end_date: Optional[datetime] = None, min_amount: Optional[float] = None,
                     max_amount: Optional[float] = None, search: Optional[str] = None, 
                     is_recurring: Optional[bool] = None, user_id: Optional[int] = None,
                     router_id: Optional[int] = None, limit: int = 100) -> List[Expense]:
        """Obtiene gastos con filtros avanzados"""
        query = self.session.query(Expense)
        
        if category and category != 'all':
            query = query.filter(Expense.category == category)
            
        if start_date:
            query = query.filter(Expense.expense_date >= start_date)
        if end_date:
            query = query.filter(Expense.expense_date <= end_date)

        if user_id:
            query = query.filter(Expense.user_id == user_id)
        if router_id:
            query = query.filter(Expense.router_id == router_id)
            
        if start_date:
            query = query.filter(Expense.expense_date >= start_date)
        if end_date:
            query = query.filter(Expense.expense_date <= end_date)
            
        if min_amount is not None:
            query = query.filter(Expense.amount >= min_amount)
        if max_amount is not None:
            query = query.filter(Expense.amount <= max_amount)

        if is_recurring is not None:
            query = query.filter(Expense.is_recurring == is_recurring)
            
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (Expense.description.ilike(search_pattern)) | 
                (Expense.notes.ilike(search_pattern))
            )

        return query.order_by(Expense.expense_date.desc()).limit(limit).all()

    def get_total_by_date_range(self, start_date: datetime, end_date: datetime) -> float:
        """Calcula el total de gastos en un rango de fechas"""
        from sqlalchemy import func
        query = self.session.query(func.sum(Expense.amount)) \
            .filter(Expense.expense_date >= start_date) \
            .filter(Expense.expense_date <= end_date)
        
        result = query.scalar()
        return float(result or 0.0)

    def get_summary(self, month: int, year: int) -> Dict[str, float]:
        """Obtiene resumen de gastos por categoría para un mes específico"""
        from sqlalchemy import extract, func
        
        # Filtro de fecha
        query = self.session.query(
            Expense.category,
            func.sum(Expense.amount).label('total')
        ).filter(
            extract('month', Expense.expense_date) == month,
            extract('year', Expense.expense_date) == year
        ).group_by(Expense.category)
        
        results = query.all()
        
        summary = {
            'fixed': 0.0,
            'variable': 0.0,
            'total': 0.0
        }
        
        for category, total in results:
            if category in summary:
                summary[category] = total or 0.0
                
        summary['total'] = summary['fixed'] + summary['variable']
        return summary
    
    def update(self, expense_id: int, data: Dict[str, Any], commit: bool = True) -> Optional[Expense]:
        """Actualiza un gasto"""
        expense = self.get_by_id(expense_id)
        if expense:
            for key, value in data.items():
                if hasattr(expense, key) and key != 'id':
                    setattr(expense, key, value)
            if commit:
                self.session.commit()
                self.session.refresh(expense)
        return expense
    
    def delete(self, expense_id: int, commit: bool = True) -> bool:
        """Elimina un gasto"""
        expense = self.get_by_id(expense_id)
        if expense:
            self.session.delete(expense)
            if commit:
                self.session.commit()
            return True
        return False
