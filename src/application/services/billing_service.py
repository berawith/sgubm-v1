
import logging
from datetime import datetime, timedelta
from sqlalchemy import extract, and_
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, InvoiceItem, InternetPlan
from src.application.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self):
        pass

    def process_daily_cycle(self, router_id=None, client_ids=None, year=None, month=None):
        """
        Ejecuta todas las tareas diarias de facturación y cortes.
        Invocado por el AutomationManager o manualmente.
        """
        logger.info(f"📅 BillingService: Iniciando ciclo {'filtrado' if router_id or client_ids else 'diario'}...")
        
        # 1. Generar facturas mensuales (es idempotente)
        self.generate_monthly_invoices(router_id=router_id, client_ids=client_ids, year=year, month=month)
        
        # 2. Procesar Suspensiones por falta de pago
        self.process_suspensions(router_id=router_id, client_ids=client_ids)
        
        return True

    def generate_monthly_invoices(self, year=None, month=None, router_id=None, client_ids=None):
        """
        Generar facturas masivas para todos los clientes activos.
        Vencimiento: Basado en la configuración del Router (billing_day + grace_period).
        """
        db = get_db()
        session = db.session
        
        now = datetime.now()
        target_year = year or now.year
        target_month = month or now.month
        
        # Fecha de emisión base (Día 1 del mes objetivo)
        issue_date_base = datetime(target_year, target_month, 1)
        
        logger.info(f"📊 Iniciando Facturación Masiva: {target_year}-{target_month}")
        
        try:
            # 1. Obtener clientes activos o suspendidos
            query = session.query(Client).filter(
                Client.status.in_(['active', 'suspended'])
            )
            
            if router_id:
                query = query.filter(Client.router_id == router_id)
            if client_ids:
                query = query.filter(Client.id.in_(client_ids))
                
            clients = query.all()
            
            # Cache de configuraciones de router para evitar consultas repetitivas
            router_configs = {}
            
            created_count = 0
            skipped_count = 0
            errors_count = 0
            
            for client in clients:
                try:
                    # Verificar si ya tiene factura este mes
                    existing = session.query(Invoice).filter(
                        Invoice.client_id == client.id,
                        extract('year', Invoice.issue_date) == target_year,
                        extract('month', Invoice.issue_date) == target_month
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Determinar configuración de vencimiento según el Router
                    if client.router_id not in router_configs:
                        from src.infrastructure.database.models import Router
                        router = session.query(Router).get(client.router_id)
                        if router:
                            router_configs[client.router_id] = {
                                'billing_day': router.billing_day or 1,
                                'grace_period': router.grace_period or 5
                            }
                        else:
                            router_configs[client.router_id] = {'billing_day': 1, 'grace_period': 5}
                    
                    config = router_configs[client.router_id]
                    billing_day = config['billing_day']
                    grace_period = config['grace_period']
                    
                    # Fecha de emisión real (Día configurado en el router)
                    # Nota: Si el billing_day es 0 o > 28, simplificamos a 1 para evitar errores de calendario
                    try:
                        issue_date = datetime(target_year, target_month, billing_day)
                    except ValueError:
                        issue_date = datetime(target_year, target_month, 1)
                        
                    # Vencimiento: Día de facturación + periodo de gracia (A las 5:00 PM por defecto)
                    due_date = issue_date + timedelta(days=grace_period)
                    due_date = due_date.replace(hour=17, minute=0, second=0)
                    
                    # Determinar precio
                    amount = client.monthly_fee or 0.0
                    plan_name = f"Plan Internet: {client.plan_name or 'Básico'}"
                    
                    if client.plan_id:
                        plan = session.query(InternetPlan).get(client.plan_id)
                        if plan:
                            amount = plan.monthly_price
                            plan_name = f"Plan Internet: {plan.name}"
                    
                    if amount <= 0:
                        logger.warning(f"⚠️ Cliente {client.legal_name} ({client.id}) tiene costo 0. Saltando.")
                        errors_count += 1
                        continue
                        
                    # Crear Factura
                    new_invoice = Invoice(
                        client_id=client.id,
                        issue_date=issue_date,
                        due_date=due_date,
                        total_amount=amount,
                        status='unpaid'
                    )
                    session.add(new_invoice)
                    session.flush()
                    
                    # Crear Item
                    item = InvoiceItem(
                        invoice_id=new_invoice.id,
                        description=f"{plan_name} - {issue_date.strftime('%B %Y')}",
                        amount=amount
                    )
                    session.add(item)
                    
                    # --- Nueva Regla: Deuda No Acumulativa (Kardex Style) ---
                    # Si no hay promesa de pago, el balance se "reinicia" al monto del nuevo mes.
                    # Esto evita que la deuda se sume para efectos de corte, a menos que se pacte lo contrario.
                    current_balance = client.account_balance or 0.0
                    has_promise = client.promise_date is not None and client.promise_date >= now
                    
                    old_balance = current_balance
                    if has_promise or current_balance < 0:
                        # Acumular si hay promesa o si tiene saldo a favor (crédito)
                        client.account_balance = current_balance + amount
                        operation_type = "accumulated"
                    else:
                        # Borrón y cuenta nueva: El balance pasa a ser solo el nuevo mes
                        client.account_balance = amount
                        operation_type = "reset_non_cumulative"
                    
                    client.due_date = due_date
                    
                    # Registrar ajuste en Auditoría (Kardex)
                    if operation_type == "reset_non_cumulative" and old_balance > 0:
                        AuditService.log(
                            operation='balance_reset_cycle',
                            category='accounting',
                            entity_type='client',
                            entity_id=client.id,
                            description=f"Balance reiniciado por nuevo ciclo (No acumulativo). Deuda anterior ${old_balance} ignorada para balance activo.",
                            previous_state={'balance': old_balance},
                            new_state={'balance': client.account_balance}
                        )
                    
                    created_count += 1
                    
                except Exception as e_inner:
                    logger.error(f"❌ Error facturando cliente {client.id}: {e_inner}")
                    errors_count += 1
            
            session.commit()
            summary = {'created': created_count, 'skipped': skipped_count, 'errors': errors_count}
            logger.info(f"✅ Facturación completada: {summary}")
            
            # Registrar en Auditoría
            AuditService.log(
                operation='mass_invoicing',
                category='accounting',
                description=f"Generación masiva de facturas para {target_month}/{target_year}. Creadas: {created_count}, Saltadas: {skipped_count}, Errores: {errors_count}"
            )
            
            return summary
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error crítico en facturación: {e}")
            raise e

    def process_suspensions(self, router_id=None, client_ids=None):
        """
        Identifica clientes con deuda (invoices unpaid) pasada la fecha de vencimiento
        y ejecuta la suspensión automática en MikroTik.
        Respeta la 'Fecha de Promesa' del cliente.
        """
        from src.infrastructure.mikrotik.adapter import MikroTikAdapter
        db = get_db()
        session = db.session
        now = datetime.now()
        
        # --- Verificación de Congelación de Suspensiones ---
        try:
            from src.infrastructure.config.settings import get_config
            config = get_config()
            freeze_until_str = config.billing.suspension_freeze_until
            if freeze_until_str:
                freeze_until = datetime.fromisoformat(freeze_until_str)
                if now < freeze_until:
                    logger.info(f"❄️ BillingService: Suspensiones CONGELADAS hasta {freeze_until.strftime('%Y-%m-%d %H:%M:%S')}. Saltando proceso.")
                    return
        except Exception as e_freeze:
            logger.error(f"Error verificando freeze de suspensiones: {e_freeze}")

        logger.info("⚡ Iniciando proceso de suspensiones automáticas...")
        
        # 1. Obtener facturas vencidas de clientes que aún están 'active'
        query = session.query(Invoice).filter(
            Invoice.status == 'unpaid',
            Invoice.due_date <= now
        )
        
        if router_id or client_ids:
            query = query.join(Client)
            if router_id:
                query = query.filter(Client.router_id == router_id)
            if client_ids:
                query = query.filter(Client.id.in_(client_ids))
                
        overdue_invoices = query.all()
        
        # 2. PROCESAR CORTES
        client_ids_to_suspend = set([inv.client_id for inv in overdue_invoices])
        suspended_count = 0
        skipped_promise_count = 0
        skipped_paid_count = 0
        
        for client_id in client_ids_to_suspend:
            client = session.query(Client).get(client_id)
            if not client or client.status != 'active':
                continue
            
            # FILTRO CRÍTICO: Verificar Balance real (Problema 1 y 2)
            if (client.account_balance or 0) <= 0:
                logger.info(f"🛡️ BillingService: Saltando suspensión accidental de {client.legal_name}. Balance: {client.account_balance} (Ya pagó)")
                # Corregir estatus de facturas vencidas si el balance es 0
                for inv in overdue_invoices:
                    if inv.client_id == client.id:
                        inv.status = 'paid'
                skipped_paid_count += 1
                continue

            # FILTRO: Promesa de Pago
            if client.promise_date and client.promise_date >= now:
                logger.info(f"🤝 Postponiendo suspensión de {client.legal_name} por PROMESA activa hasta {client.promise_date}")
                skipped_promise_count += 1
                continue
                
            logger.warning(f"🚫 Suspendiendo cliente {client.legal_name} por deuda acumulada (${client.account_balance}).")
            
            # Marcar como suspendido en BD
            client.status = 'suspended'
            session.commit()
            
            # Ejecutar suspensión en MikroTik
            if client.router_id:
                router = db.get_router_repository().get_by_id(client.router_id)
                if router and router.status == 'online':
                    adapter = MikroTikAdapter()
                    try:
                        if adapter.connect(router.host_address, router.api_username, router.api_password, router.api_port):
                            adapter.suspend_client_service(client.to_dict())
                            adapter.disconnect()
                            suspended_count += 1
                    except Exception as e:
                        logger.error(f"Error sincronizando suspensión en MikroTik para {client.legal_name}: {e}")

            # Auditoría de Suspensión
            AuditService.log(
                operation='client_suspended',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description=f"Suspensión automática por deuda: ${client.account_balance}",
                previous_state={'status': 'active'},
                new_state={'status': 'suspended'}
            )

        # 3. PROCESAR RESTAURACIONES (Auto-fix para clientes que ya pagaron pero siguen cortados)
        restored_count = 0
        query_suspended = session.query(Client).filter(Client.status == 'suspended')
        if router_id:
            query_suspended = query_suspended.filter(Client.router_id == router_id)
        if client_ids:
            query_suspended = query_suspended.filter(Client.id.in_(client_ids))
            
        suspended_clients = query_suspended.all()
        for s_client in suspended_clients:
            # Si el balance es <= 0 y no tiene facturas unpaid vencidas, RESTAURAR
            if (s_client.account_balance or 0) <= 0:
                logger.info(f"✅ Restaurando servicio para {s_client.legal_name} (Balance {s_client.account_balance} <= 0)")
                from src.application.services.batch_service import BatchService
                BatchService()._restore_client(s_client)
                restored_count += 1
        
        session.commit()
        logger.info(f"✅ Proceso finalizado. Suspendidos: {suspended_count}, Restaurados: {restored_count}, Saltados (Promesa): {skipped_promise_count}, Saltados (Ya pagó): {skipped_paid_count}")
        return {
            'suspended': suspended_count,
            'restored': restored_count,
            'skipped_promise': skipped_promise_count,
            'skipped_paid': skipped_paid_count
        }

    def register_payment(self, client_id, amount, payment_data):
        """
        Registra un pago centralizadamente:
        1. Crea el registro de pago.
        2. Actualiza balance del cliente.
        3. Actualiza estatus de facturas (FIFO).
        4. Reactiva servicio si el balance llega a <= 0.
        """
        from src.infrastructure.database.models import Payment
        from src.application.services.batch_service import BatchService
        
        db = get_db()
        session = db.session
        
        client = session.query(Client).get(client_id)
        if not client:
            raise ValueError("Cliente no encontrado")

        # VALIDACIÓN: Pagos Incompletos (NUEVO REQUERIMIENTO)
        current_debt = client.account_balance or 0.0
        is_partial = amount < current_debt
        authorized = payment_data.get('authorized', False)

        if is_partial and not authorized:
            # Lanzamos error específico para que el frontend pida autorización
            raise ValueError(f"PARTIAL_PAYMENT_REQUIRED|Monto ${amount} es menor a la deuda ${current_debt}. ¿Es un abono parcial o error de tipeo?")

        # VALIDACIÓN: Problema 3 - Evitar pagos duplicados si no hay deuda
        unpaid_invoices = session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).count()
        
        if current_debt <= 0 and unpaid_invoices == 0:
            if not payment_data.get('is_overpayment', False):
                raise ValueError("El cliente ya está al día. No tiene saldo pendiente ni facturas por pagar.")

        # 1. Crear el pago
        new_payment = Payment(
            client_id=client.id,
            amount=amount,
            payment_date=datetime.now(),
            payment_method=payment_data.get('payment_method', 'cash'),
            reference=payment_data.get('reference', ''),
            notes=payment_data.get('notes', ''),
            status='verified'
        )
        session.add(new_payment)
        
        # 2. Actualizar balance
        client.account_balance = (client.account_balance or 0) - amount
        client.last_payment_date = new_payment.payment_date
        
        # 3. Actualizar facturas (FIFO)
        invoices = session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).order_by(Invoice.issue_date).all()
        
        remaining = amount
        for inv in invoices:
            if remaining <= 0: break
            if remaining >= inv.total_amount:
                inv.status = 'paid'
                remaining -= inv.total_amount
            else:
                # Pago parcial: No marcamos como paid, pero el balance general del cliente ya bajó.
                # Futura mejora: tracking de amount_paid en Invoice.
                break
                
        session.commit()
        
        # 4. Reactivación Automática
        if client.status == 'suspended' and (client.account_balance or 0) <= 0:
            BatchService()._restore_client(client)
            logger.info(f"🚀 Cliente {client.username} reactivado automáticamente tras pago.")
            
            # Auditoría de Reactivación
            AuditService.log(
                operation='client_reactivated',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description="Reactivación automática tras pago total",
                previous_state={'status': 'suspended'},
                new_state={'status': 'active'}
            )
            
        # Auditoría de Pago
        AuditService.log_accounting(
            operation='payment_registered',
            amount=amount,
            client_id=client.id,
            description=f"Pago registrado vía {payment_data.get('payment_method', 'cash')}. Ref: {payment_data.get('reference', 'N/A')}",
            entity_id=new_payment.id,
            entity_type='payment'
        )

        return new_payment
