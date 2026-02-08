"""
Database Repositories
Implementaciones de IRepository para acceso a datos
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from src.infrastructure.database.models import Router, Client, Payment, RouterStatus, ClientStatus


class RouterRepository:
    """Repositorio para gestión de Routers"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any]) -> Router:
        """Crea un nuevo router"""
        router = Router(**data)
        self.session.add(router)
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
    
    def update(self, router_id: int, data: Dict[str, Any]) -> Optional[Router]:
        """Actualiza un router"""
        router = self.get_by_id(router_id)
        if router:
            for key, value in data.items():
                if hasattr(router, key) and key != 'id':
                    setattr(router, key, value)
            router.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(router)
        return router
    
    def delete(self, router_id: int) -> bool:
        """Elimina un router"""
        router = self.get_by_id(router_id)
        if router:
            self.session.delete(router)
            self.session.commit()
            return True
        return False
    
    def update_metrics(self, router_id: int, metrics: Dict[str, Any]) -> Optional[Router]:
        """Actualiza métricas del router"""
        router = self.get_by_id(router_id)
        if router:
            router.cpu_usage = metrics.get('cpu_usage', router.cpu_usage)
            router.memory_usage = metrics.get('memory_usage', router.memory_usage)
            router.clients_connected = metrics.get('clients_connected', router.clients_connected)
            router.uptime = metrics.get('uptime', router.uptime)
            router.status = metrics.get('status', router.status)
            router.last_sync = datetime.utcnow()
            self.session.commit()
            self.session.refresh(router)
        return router


class ClientRepository:
    """Repositorio para gestión de Clientes"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any]) -> Client:
        """Crea un nuevo cliente"""
        client = Client(**data)
        self.session.add(client)
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
    
    def get_by_router(self, router_id: int) -> List[Client]:
        """Obtiene clientes de un router específico"""
        return self.session.query(Client).filter(Client.router_id == router_id).all()
    
    def get_by_status(self, status: str) -> List[Client]:
        """Obtiene clientes por estado"""
        return self.session.query(Client).filter(Client.status == status).all()
    
    def search(self, query: str) -> List[Client]:
        """Busca clientes por nombre, código, documento o IP"""
        search_pattern = f"%{query}%"
        return self.session.query(Client).filter(
            (Client.legal_name.ilike(search_pattern)) |
            (Client.subscriber_code.ilike(search_pattern)) |
            (Client.identity_document.ilike(search_pattern)) |
            (Client.username.ilike(search_pattern)) |
            (Client.plan_name.ilike(search_pattern)) |
            (Client.ip_address.ilike(search_pattern))
        ).all()

    def get_filtered(self, router_id: Optional[int] = None, status: Optional[str] = None, search: Optional[str] = None, plan_id: Optional[int] = None) -> List[Client]:
        """Obtiene clientes con filtros combinados"""
        query_obj = self.session.query(Client)

        if router_id:
            query_obj = query_obj.filter(Client.router_id == router_id)

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
    
    def update(self, client_id: int, data: Dict[str, Any]) -> Optional[Client]:
        """Actualiza un cliente"""
        client = self.get_by_id(client_id)
        if client:
            for key, value in data.items():
                if hasattr(client, key) and key != 'id':
                    setattr(client, key, value)
            client.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(client)
        return client
    
    def delete(self, client_id: int) -> bool:
        """Elimina un cliente"""
        client = self.get_by_id(client_id)
        if client:
            self.session.delete(client)
            self.session.commit()
            return True
        return False
    
    def suspend(self, client_id: int) -> Optional[Client]:
        """Suspende un cliente"""
        client = self.get_by_id(client_id)
        if client:
            client.status = 'suspended'
            client.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(client)
        return client
    
    def activate(self, client_id: int) -> Optional[Client]:
        """Activa un cliente"""
        client = self.get_by_id(client_id)
        if client:
            client.status = 'active'
            client.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(client)
        return client
    
    def update_balance(self, client_id: int, amount: float, operation: str = 'add') -> Optional[Client]:
        """Actualiza el balance del cliente"""
        client = self.get_by_id(client_id)
        if client:
            if operation == 'add':
                client.account_balance += amount
            elif operation == 'subtract':
                client.account_balance -= amount
            elif operation == 'set':
                client.account_balance = amount
            self.session.commit()
            self.session.refresh(client)
        return client


class PaymentRepository:
    """Repositorio para gestión de Pagos"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: Dict[str, Any]) -> Payment:
        """Registra un nuevo pago"""
        payment = Payment(**data)
        self.session.add(payment)
        self.session.commit()
        self.session.refresh(payment)
        return payment
    
    def get_by_id(self, payment_id: int) -> Optional[Payment]:
        """Obtiene un pago por ID"""
        return self.session.query(Payment).filter(Payment.id == payment_id).first()
    
    def get_all(self, limit: int = 100) -> List[Payment]:
        """Obtiene todos los pagos (limitado)"""
        return self.session.query(Payment).order_by(Payment.payment_date.desc()).limit(limit).all()
    
    def get_by_client(self, client_id: int) -> List[Payment]:
        """Obtiene todos los pagos de un cliente"""
        return self.session.query(Payment).filter(Payment.client_id == client_id).order_by(Payment.payment_date.desc()).all()
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Payment]:
        """Obtiene pagos en un rango de fechas"""
        return self.session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date
        ).order_by(Payment.payment_date.desc()).all()

    def get_filtered(self, client_id: Optional[int] = None, start_date: Optional[datetime] = None, 
                     end_date: Optional[datetime] = None, method: Optional[str] = None, 
                     search: Optional[str] = None, limit: int = 100) -> List[Payment]:
        """Obtiene pagos con filtros combinados"""
        query = self.session.query(Payment).join(Client, Payment.client_id == Client.id)

        if client_id:
            query = query.filter(Payment.client_id == client_id)
        
        if start_date:
            query = query.filter(Payment.payment_date >= start_date)
            
        if end_date:
            query = query.filter(Payment.payment_date <= end_date)
            
        if method and method != 'all':
            query = query.filter(Payment.payment_method == method)
            
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
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.session.query(Payment).filter(
            Payment.payment_date >= today_start
        ).order_by(Payment.payment_date.desc()).all()
    
    def get_total_by_date_range(self, start_date: datetime, end_date: datetime) -> float:
        """Calcula el total de pagos en un rango"""
        result = self.session.query(Payment).filter(
            Payment.payment_date >= start_date,
            Payment.payment_date <= end_date,
            Payment.status.in_(['paid', 'verified'])
        ).all()
        return sum(p.amount for p in result)
    
    def update(self, payment_id: int, data: Dict[str, Any]) -> Optional[Payment]:
        """Actualiza un pago"""
        payment = self.get_by_id(payment_id)
        if payment:
            for key, value in data.items():
                if hasattr(payment, key) and key != 'id':
                    setattr(payment, key, value)
            payment.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(payment)
        return payment
    
    def delete(self, payment_id: int) -> bool:
        """Elimina un pago"""
        payment = self.get_by_id(payment_id)
        if payment:
            self.session.delete(payment)
            self.session.commit()
            return True
        return False


class DeletedPaymentRepository:
    """Repositorio para gestión de Pagos Eliminados (Papelera)"""
    
    def __init__(self, session: Session):
        self.session = session
        
    def create_from_payment(self, payment, deleted_by: str = 'system', reason: str = '') -> 'DeletedPayment':
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
        self.session.commit()
        return deleted

    def get_all(self, limit: int = 100) -> List['DeletedPayment']:
        from src.infrastructure.database.models import DeletedPayment
        return self.session.query(DeletedPayment).order_by(DeletedPayment.deleted_at.desc()).limit(limit).all()

    def get_by_id(self, deleted_id: int) -> Optional['DeletedPayment']:
        from src.infrastructure.database.models import DeletedPayment
        return self.session.query(DeletedPayment).filter(DeletedPayment.id == deleted_id).first()

    def delete(self, deleted_id: int) -> bool:
        deleted = self.get_by_id(deleted_id)
        if deleted:
            self.session.delete(deleted)
            self.session.commit()
            return True
        return False


class SyncRepository:
    """Repositorio para Cola de Sincronización"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def add_task(self, router_id: int, operation: str, payload: Dict[str, Any], client_id: int = None) -> SyncQueue:
        """Agrega una tarea a la cola"""
        import json
        from src.infrastructure.database.models import SyncQueue
        
        task = SyncQueue(
            router_id=router_id,
            client_id=client_id,
            operation=operation,
            payload=json.dumps(payload),
            status='pending',
            attempts=0
        )
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task
        
    def get_pending_for_router(self, router_id: int) -> List[SyncQueue]:
        """Obtiene tareas pendientes para un router"""
        from src.infrastructure.database.models import SyncQueue
        return self.session.query(SyncQueue).filter(
            SyncQueue.router_id == router_id,
            SyncQueue.status.in_(['pending', 'retry'])
        ).order_by(SyncQueue.created_at.asc()).all()
        
    def mark_completed(self, task_id: int):
        """Marca tarea como completada y la elimina (o archiva)"""
        # Por limpieza, eliminamos si se completó con éxito
        from src.infrastructure.database.models import SyncQueue
        task = self.session.query(SyncQueue).get(task_id)
        if task:
            self.session.delete(task)
            self.session.commit()

    def mark_failed(self, task_id: int, error: str):
        """Marca tarea como fallida o para reintento"""
        from src.infrastructure.database.models import SyncQueue
        task = self.session.query(SyncQueue).get(task_id)
        if task:
            task.attempts += 1
            task.last_error = str(error)
            if task.attempts >= 5: # Max retries
                task.status = 'failed'
            else:
                task.status = 'retry'
            self.session.commit()


class TrafficRepository:
    """Repositorio para historial de tráfico"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def add_snapshot(self, data: Dict[str, Any]) -> ClientTrafficHistory:
        """Agrega un snapshot de tráfico al historial"""
        from src.infrastructure.database.models import ClientTrafficHistory
        snapshot = ClientTrafficHistory(**data)
        self.session.add(snapshot)
        self.session.commit()
        return snapshot
    
    def get_history(self, client_id: int, hours: int = 24) -> List[ClientTrafficHistory]:
        """Obtiene historial de un cliente en un rango de horas"""
        from src.infrastructure.database.models import ClientTrafficHistory
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(hours=hours)
        return self.session.query(ClientTrafficHistory)\
            .filter(ClientTrafficHistory.client_id == client_id)\
            .filter(ClientTrafficHistory.timestamp >= since)\
            .order_by(ClientTrafficHistory.timestamp.asc()).all()
    
    def delete_old_history(self, days: int = 30):
        """Limpia historial antiguo para evitar crecimiento excesivo de la BD"""
        from src.infrastructure.database.models import ClientTrafficHistory
        from datetime import datetime, timedelta
        
        limit = datetime.utcnow() - timedelta(days=days)
        self.session.query(ClientTrafficHistory)\
            .filter(ClientTrafficHistory.timestamp < limit).delete()
        self.session.commit()

