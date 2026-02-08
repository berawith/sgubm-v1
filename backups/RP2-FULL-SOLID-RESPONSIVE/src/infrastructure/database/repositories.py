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
            (Client.legal_name.like(search_pattern)) |
            (Client.subscriber_code.like(search_pattern)) |
            (Client.identity_document.like(search_pattern)) |
            (Client.username.like(search_pattern)) |
            (Client.ip_address.like(search_pattern))
        ).all()
    
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
            Payment.status == 'paid'
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
