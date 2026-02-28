import logging
import calendar
from datetime import datetime, timedelta
from sqlalchemy import extract, and_
from src.infrastructure.database.db_manager import get_db
from src.infrastructure.database.models import Client, Invoice, InvoiceItem, InternetPlan, PaymentPromise, Payment
from src.application.services.audit_service import AuditService
from src.application.services.mikrotik_operations import safe_suspend_client
from src.domain.services.tax_engine import TaxEngine
from src.domain.services.currency_service import CurrencyService

logger = logging.getLogger(__name__)

class BillingService:
    def __init__(self):
        pass

    def _apply_billing_filters(self, query, router_id=None, client_ids=None, zone_names=None, excluded_zones=None, collector_ids=None, excluded_collectors=None, excluded_routers=None):
        """Helper para aplicar filtros avanzados de inclusión/exclusión"""
        from src.infrastructure.database.models import Client, Router

        if router_id:
            query = query.filter(Client.router_id == router_id)
        if excluded_routers:
            query = query.filter(Client.router_id.notin_(excluded_routers))
        if client_ids:
            query = query.filter(Client.id.in_(client_ids))
        if collector_ids:
            query = query.filter(Client.assigned_collector_id.in_(collector_ids))
        if excluded_collectors:
            query = query.filter(Client.assigned_collector_id.notin_(excluded_collectors))

        if zone_names or excluded_zones:
            query = query.join(Router, Client.router_id == Router.id)
            if zone_names:
                query = query.filter(Router.zone.in_(zone_names))
            if excluded_zones:
                query = query.filter(Router.zone.notin_(excluded_zones))

        return query

    def process_daily_cycle(self, router_id=None, client_ids=None, year=None, month=None, zone_names=None, excluded_zones=None, collector_ids=None, excluded_collectors=None, excluded_routers=None):
        """
        Ejecuta todas las tareas diarias de facturación y cortes.
        Invocado por el AutomationManager o manualmente.
        """
        logger.info(f"📅 BillingService: Iniciando ciclo {'filtrado' if (router_id or client_ids or zone_names or excluded_zones or collector_ids or excluded_collectors or excluded_routers) else 'diario'}...")

        # 2. Aplicar Prorrateo Dinámico (Día 16+)
        self.apply_daily_prorating(
            router_id=router_id, client_ids=client_ids,
            zone_names=zone_names, excluded_zones=excluded_zones,
            collector_ids=collector_ids, excluded_collectors=excluded_collectors,
            excluded_routers=excluded_routers
        )

        # 3. Procesar Suspensiones por falta de pago
        self.process_suspensions(
            router_id=router_id, client_ids=client_ids,
            zone_names=zone_names, excluded_zones=excluded_zones,
            collector_ids=collector_ids, excluded_collectors=excluded_collectors,
            excluded_routers=excluded_routers
        )

        return True

    def onboard_client_financially(self, client, strategy, initial_debt=0, registered_by='System'):
        """
        Maneja el onboarding financiero de un cliente importado/nuevo.
        Estrategias: 
        - 'debt': Crea factura vencida y el cliente inicia con saldo negativo.
        - 'grace': Crea factura pagada (beneficio) y reporte de pago especial.
        """
        db = get_db()
        session = db.session
        
        try:
            if strategy == 'debt':
                if initial_debt > 0:
                    inv = Invoice(
                        client_id=client.id,
                        issue_date=datetime.now(),
                        due_date=datetime.now(),
                        total_amount=initial_debt,
                        status='pending',
                        notes="Saldo Inicial (Importación con Deuda)"
                    )
                    session.add(inv)
                    session.flush()
                    
                    item = InvoiceItem(
                        invoice_id=inv.id,
                        description="Saldo Anterior Pendiente",
                        quantity=1,
                        unit_price=initial_debt,
                        total=initial_debt
                    )
                    session.add(item)
                    
                    # El balance se actualiza via triggers o manualmente si no hay
                    client.account_balance = (client.account_balance or 0) + initial_debt
                    client.status = 'suspended' # Inicia suspendido por deuda
                    
                    session.commit()
                    logger.info(f"Onboarding Debt: {client.legal_name} created with ${initial_debt} debt and suspended.")
                    return True
            
            elif strategy == 'grace':
                # El mes se carga y se abona (Gratis/Periodo de Gracia)
                amount = client.monthly_fee or 0.0
                if amount > 0:
                    # 1. Crear Factura
                    inv = Invoice(
                        client_id=client.id,
                        issue_date=datetime.now(),
                        due_date=datetime.now(),
                        total_amount=amount,
                        status='paid', # Ya marcada como pagada
                        notes="Periodo de Gracia (Aprovisionamiento Especial)"
                    )
                    session.add(inv)
                    session.flush()
                    
                    item = InvoiceItem(
                        invoice_id=inv.id,
                        description="Servicio de Internet - Mes de Cortesía",
                        quantity=1,
                        unit_price=amount,
                        total=amount
                    )
                    session.add(item)
                    
                    # 2. Registrar Pago Especial (Abono virtual para auditoría)
                    # Usamos un 'payment_method' identificable
                    payment = Payment(
                        client_id=client.id,
                        amount=amount,
                        currency='COP',
                        payment_method='cortesia', # Palabra clave para reporte especial
                        reference='GRACE_PERIOD_ONBOARDING',
                        notes=f"Beneficio de ingreso: Mes de cortesía para {client.legal_name}",
                        registered_by=registered_by,
                        status='paid'
                    )
                    session.add(payment)
                    
                    # El balance no cambia (Factura + Pago = 0)
                    session.commit()
                    logger.info(f"Onboarding Grace: {client.legal_name} credited with mes de cortesía (${amount}).")
                    return True
                    
        except Exception as e:
            session.rollback()
            logger.error(f"Error in onboarding_financially for {client.id}: {e}")
            return False
        
        return False

    def generate_monthly_invoices(self, year=None, month=None, router_id=None, client_ids=None, zone_names=None, excluded_zones=None, collector_ids=None, excluded_collectors=None, excluded_routers=None):
        """
        Generar facturas masivas para todos los clientes activos.
        Vencimiento: Basado en la configuración del Router (billing_day + grace_period).
        """
        db = get_db()
        session = db.session
        
        now = datetime.now()
        target_year = year or now.year
        target_month = month or now.month
        
        logger.info(f"📊 Iniciando Facturación Masiva: {target_year}-{target_month}")
        
        try:
            # 1. Obtener clientes activos o suspendidos que tengan la facturación habilitada
            query = session.query(Client).filter(
                Client.status.in_(['active', 'suspended']),
                Client.billing_enabled == True
            )
            
            query = self._apply_billing_filters(
                query, router_id=router_id, client_ids=client_ids,
                zone_names=zone_names, excluded_zones=excluded_zones,
                collector_ids=collector_ids, excluded_collectors=excluded_collectors,
                excluded_routers=excluded_routers
            )
                
            clients = query.all()
            
            # Obtener configuración global de hora de vencimiento
            settings_repo = db.get_system_setting_repository()
            due_time_str = settings_repo.get_value('ERP_BILLING_DUE_TIME', '17:00')
            try:
                due_hour, due_minute = map(int, due_time_str.split(':'))
            except:
                due_hour, due_minute = 17, 0

            # Cache de configuraciones de router
            router_configs = {}
            created_count = 0
            skipped_count = 0
            errors_count = 0
            
            for client in clients:
                try:
                    # ... (rest of the loop)
                    # Verificar si ya tiene factura este mes
                    existing = session.query(Invoice).filter(
                        Invoice.client_id == client.id,
                        extract('year', Invoice.issue_date) == target_year,
                        extract('month', Invoice.issue_date) == target_month
                    ).first()
                    
                    if existing:
                        skipped_count += 1
                        continue
                    
                    # Configuración del Router
                    if client.router_id not in router_configs:
                        from src.infrastructure.database.models import Router
                        router = session.query(Router).get(client.router_id)
                        if router:
                            router_configs[client.router_id] = {
                                'billing_day': router.billing_day or 1,
                                'grace_period': router.grace_period or 5,
                                'cut_day': router.cut_day or 5
                            }
                        else:
                            router_configs[client.router_id] = {'billing_day': 1, 'grace_period': 5, 'cut_day': 5}
                    
                    config = router_configs[client.router_id]
                    billing_day = config['billing_day']
                    
                    try:
                        issue_date = datetime(target_year, target_month, billing_day)
                    except ValueError:
                        issue_date = datetime(target_year, target_month, 1)
                        
                    due_date = issue_date + timedelta(days=config['grace_period'])
                    due_date = due_date.replace(hour=due_hour, minute=due_minute, second=0)
                    
                    # Precio y Plan
                    amount = client.monthly_fee or 0.0
                    plan_name = client.plan_name or "Servicio Internet"
                    
                    if client.plan_id:
                        plan = session.query(InternetPlan).get(client.plan_id)
                        if plan:
                            amount = plan.monthly_price
                            plan_name = plan.name
                    
                    if amount <= 0:
                        skipped_count += 1
                        continue

                    # ERP Data
                    settings_repo = db.get_system_setting_repository()
                    currency_service = CurrencyService(settings_repo)
                    currency = settings_repo.get_value('ERP_REPORTING_CURRENCY', 'COP')
                    base_currency = settings_repo.get_value('ERP_BASE_CURRENCY', 'USD')
                    rate = currency_service.get_rate(currency, base_currency)
                    base_amount = amount * rate

                    # Crear Factura
                    new_invoice = Invoice(
                        client_id=client.id,
                        issue_date=issue_date,
                        due_date=due_date,
                        total_amount=amount,
                        subtotal_amount=amount,
                        base_amount=base_amount,
                        currency=currency,
                        exchange_rate=rate,
                        status='pending',
                        notes=f"Ciclo Mensual {target_year}-{target_month:02d}"
                    )
                    session.add(new_invoice)
                    session.flush()
                    
                    item = InvoiceItem(
                        invoice_id=new_invoice.id,
                        description=f"Internet {plan_name} - {issue_date.strftime('%B %Y')}",
                        quantity=1,
                        unit_price=amount,
                        total=amount
                    )
                    session.add(item)
                    
                    # Actualizar Balance del Cliente (Reset Contabilidad implicito o acumulado)
                    # El usuario quiere que todos pasen a tener deuda.
                    # En este sistema balance > 0 es DEUDA.
                    # Mantenemos la deuda anterior + nueva factura.
                    client.account_balance = (client.account_balance or 0.0) + amount
                    client.due_date = due_date
                    
                    created_count += 1
                    
                except Exception as e_inner:
                    logger.error(f"Error facturando cliente {client.id}: {e_inner}")
                    errors_count += 1
            
            # Cierre de mes (Accounting Reset Log)
            self.close_month_accounting(target_year, target_month, commit=False)
            
            session.commit()
            logger.info(f"✅ Facturación completada: Creadas={created_count}, Errores={errors_count}")
            
            # Registrar Audit Log Masivo
            from src.application.services.audit_service import AuditService
            AuditService.log(
                operation='mass_invoicing',
                category='accounting',
                entity_type='system',
                entity_id=0,
                description=f"Generación de ciclo {target_year}-{target_month:02d}. Total: {created_count} facturas creadas.",
                commit=True
            )
            return True
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error crítico en generate_monthly_invoices: {e}")
            return False

    def close_month_accounting(self, year, month, commit=True):
        """Identifica el cierre de mes administrativo"""
        from src.application.services.audit_service import AuditService
        db = get_db()
        session = db.session
        try:
            AuditService.log(
                operation='accounting_reset',
                category='finance',
                entity_type='system',
                entity_id=0,
                description=f"Reinicio de contabilidad para el nuevo ciclo {year}-{month:02d}. Operaciones nuevas iniciadas.",
                commit=False
            )
            if commit: session.commit()
            return True
        except Exception as e:
            if commit: session.rollback()
            return False

    def request_cycle_approval(self, tenant_id, year, month):
        """Crea notificación de aprobación para el ciclo de facturación"""
        from src.infrastructure.database.models import SystemNotification
        db = get_db()
        session = db.session
        
        action_key = f"billing_cycle_{year}_{month:02d}"
        existing = session.query(SystemNotification).filter(
            SystemNotification.action_key == action_key
        ).first()
        
        if existing: return False
        
        notif = SystemNotification(
            tenant_id=tenant_id,
            title="Inicio de Ciclo de Facturación",
            message=f"Ya estamos a principio de un nuevo ciclo de facturacion ({year}-{month:02d}) desea implementarlo?",
            type='approval_required',
            action_key=action_key,
            action_data=f'{{"year": {year}, "month": {month}}}',
            status='pending',
            remind_at=datetime.now()
        )
        session.add(notif)
        session.commit()
        return True
        return True

    def apply_daily_prorating(self, router_id=None, client_ids=None, force=False, zone_names=None, excluded_zones=None, collector_ids=None, excluded_collectors=None, excluded_routers=None):
        """
        Aplica descuentos automáticos (Prorrateo) después del día configurado.
        'force' permite ignorar la validación de día si se requiere aplicación manual.
        """
        db = get_db()
        session = db.session
        now = datetime.now()
        
        settings_repo = db.get_system_setting_repository()
        enabled = settings_repo.get_value('PRORATING_ENABLED', 'true').lower() == 'true'
        start_day = int(settings_repo.get_value('PRORATING_START_DAY', 15))
        
        # Si no está forzado, validamos el día de inicio
        if not force:
            if not enabled or now.day <= start_day:
                return 0
            
        logger.info(f"⚖️ BillingService: Aplicando Prorrateo Dinámico (Día {now.day}, force={force})...")
        
        try:
            # 1. Obtener facturas impagas del mes actual
            # 1. Obtener facturas impagas del mes actual
            query = session.query(Invoice).join(Client).filter(
                Invoice.status == 'unpaid',
                extract('year', Invoice.issue_date) == now.year,
                extract('month', Invoice.issue_date) == now.month
            )
            
            query = self._apply_billing_filters(
                query, router_id=router_id, client_ids=client_ids,
                zone_names=zone_names, excluded_zones=excluded_zones,
                collector_ids=collector_ids, excluded_collectors=excluded_collectors,
                excluded_routers=excluded_routers
            )
                
            unpaid_invoices = query.all()
            
            _, days_in_month = calendar.monthrange(now.year, now.month)
            # Días restantes incluyendo hoy hasta el fin de mes
            days_remaining = days_in_month - now.day + 1
            
            updated_count = 0
            
            for inv in unpaid_invoices:
                client = inv.client
                if not client: continue
                
                # EXCEPCIÓN: Promesa de Pago activa
                if client.promise_date and client.promise_date >= now:
                    continue
                    
                # Obtener monto original desde el ítem de la factura
                # (Para evitar degradación si se corre varias veces el mismo día)
                original_amount = 0.0
                item = session.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).first()
                if item:
                    original_amount = item.total
                else:
                    original_amount = client.monthly_fee or inv.total_amount
                
                if original_amount <= 0: continue
                
                # Calcular nuevo monto prorrateado (Basado en regla: cuenta desde día 5 en adelante)
                # Si el mes tiene 30 días, el denominador es 25 (30 - 5)
                import math
                denominator = days_in_month - 5
                new_amount = math.ceil((original_amount * days_remaining) / denominator)
                
                # Solo aplicar si el nuevo monto es menor al actual (para evitar subir precios)
                if new_amount < inv.total_amount:
                    diff = inv.total_amount - new_amount
                    inv.total_amount = new_amount
                    
                    # El balance del cliente también debe bajar por la diferencia
                    client.account_balance = (client.account_balance or 0) - diff
                    updated_count += 1
            
            session.commit()
            if updated_count > 0:
                logger.info(f"✅ Prorrateo completado: {updated_count} facturas ajustadas.")
            return updated_count
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error en prorrateo diario: {e}")

    def process_suspensions(self, router_id=None, client_ids=None, zone_names=None, excluded_zones=None, collector_ids=None, excluded_collectors=None, excluded_routers=None):
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
        query = session.query(Invoice).join(Client).filter(
            Invoice.status == 'unpaid',
            Invoice.due_date <= now
        )
        
        query = self._apply_billing_filters(
            query, router_id=router_id, client_ids=client_ids,
            zone_names=zone_names, excluded_zones=excluded_zones,
            collector_ids=collector_ids, excluded_collectors=excluded_collectors,
            excluded_routers=excluded_routers
        )
                
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
            
            # Si el cliente tenía una promesa vencida, marcarla como INCUMPLIDA
            if client.promise_date and client.promise_date < now:
                broken_promises = session.query(PaymentPromise).filter(
                    PaymentPromise.client_id == client.id,
                    PaymentPromise.status == 'pending'
                ).all()
                for bp in broken_promises:
                    bp.status = 'broken'
                    bp.notes = (bp.notes or "") + f" | Incumplida el {now.strftime('%Y-%m-%d')}"
                
                # Incrementar contador de promesas incumplidas consecutivas
                client.broken_promises_count = (client.broken_promises_count or 0) + 1
                logger.warning(f"💔 Promesa INCUMPLIDA por {client.legal_name}. Contador: {client.broken_promises_count}")
                
            logger.warning(f"🚫 Suspendiendo cliente {client.legal_name} por deuda acumulada (${client.account_balance}).")
            
            # Ejecutar suspensión técnica de forma segura
            if client.router_id:
                router = db.get_router_repository().get_by_id(client.router_id)
                if router:
                    result = safe_suspend_client(
                        db=db,
                        client=client,
                        router=router,
                        audit_service=AuditService,
                        audit_details=f"Suspensión automática por deuda: ${client.account_balance}"
                    )
                    if result['status'] in ['success', 'queued']:
                        suspended_count += 1

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

    def register_payment(self, client_id, amount, payment_data, status='verified'):
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

        # --- NUEVO: Aplicar Prorrateo SOLO SI se solicita en la transacción ---
        # User Feedback: "el monto real no debe variar solo que en el momento de realizar el pago se muestra el descuento"
        apply_prorating = payment_data.get('apply_prorating', False)
        
        if apply_prorating:
            try:
                # Forzamos aplicación de prorrateo para este pago específico
                self.apply_daily_prorating(client_ids=[client.id], force=True)
                session.refresh(client) # Refrescar para obtener el balance ajustado
                logger.info(f"🎁 Prorrateo aplicado exitosamente para el pago del cliente {client.id}")
            except Exception as e:
                logger.error(f"Error aplicando prorrateo en el pago para cliente {client_id}: {e}")

        # --- SOPORTE PARA PAGOS MIXTOS (NUEVO) ---
        parts = payment_data.get('parts', [])
        is_mixed = len(parts) > 1
        
        # Obtener CurrencyService
        currency_service = CurrencyService(db.get_system_setting_repository())
        base_currency = db.get_system_setting_repository().get_value('ERP_BASE_CURRENCY', 'USD')
        
        total_debt_reduction = 0.0 # En moneda de balance (COP)
        total_base_amount = 0.0   # En moneda base (USD)
        total_tax_amount = 0.0
        tax_details_list = []
        
        prepared_details = []
        
        if parts:
            for part in parts:
                p_amount = float(part.get('amount', 0))
                p_currency = part.get('currency', 'COP')
                p_method = part.get('method', 'cash')
                
                # Conversión a COP para balance
                p_cop_amount = currency_service.convert(p_amount, p_currency, 'COP')
                total_debt_reduction += p_cop_amount
                
                # Conversión a USD para auditoría
                p_base_amount = currency_service.get_base_amount(p_amount, p_currency)
                total_base_amount += p_base_amount
                
                # Impuestos por parte
                p_country = 'VEN' if p_currency.upper() in ['VES', 'USD'] else 'COL'
                p_tax = TaxEngine.calculate_taxes(p_amount, p_country, p_method, p_currency)
                total_tax_amount += currency_service.convert(p_tax['total_tax'], p_currency, 'COP') # Ojo: impuestos sumados en COP? 
                # Generalmente los impuestos se guardan en la moneda del pago, pero aquí los agregamos
                
                tax_details_list.append(TaxEngine.format_tax_details(p_tax))
                
                prepared_details.append({
                    'amount': p_amount,
                    'currency': p_currency,
                    'method': p_method,
                    'exchange_rate': currency_service.get_rate(p_currency, base_currency),
                    'base_amount': p_base_amount,
                    'reference': part.get('reference', ''),
                    'notes': part.get('notes', '')
                })
            
            # Si hay partes, el 'amount' principal es la reducción total de deuda (COP)
            amount = total_debt_reduction
            currency = 'COP' 
            main_method = 'mixed' if is_mixed else prepared_details[0]['method']
        else:
            # Comportamiento legacy (pago simple)
            currency = payment_data.get('currency', 'COP')
            main_method = payment_data.get('payment_method', 'cash')
            
            total_debt_reduction = currency_service.convert(amount, currency, 'COP')
            total_base_amount = currency_service.get_base_amount(amount, currency)
            
            p_country = 'VEN' if currency.upper() in ['VES', 'USD'] else 'COL'
            tax_results = TaxEngine.calculate_taxes(amount, p_country, main_method, currency)
            total_tax_amount = tax_results['total_tax']
            tax_details_list = [TaxEngine.format_tax_details(tax_results)]
            
            prepared_details.append({
                'amount': amount,
                'currency': currency,
                'method': main_method,
                'exchange_rate': currency_service.get_rate(currency, base_currency),
                'base_amount': total_base_amount,
                'reference': payment_data.get('reference', ''),
                'notes': payment_data.get('notes', '')
            })

        # VALIDACIÓN: Pagos Incompletos (NUEVO REQUERIMIENTO)
        current_debt = client.account_balance or 0.0
        # Comparamos la reducción de deuda real vs la deuda actual
        is_partial = (total_debt_reduction + 0.01) < current_debt # Margen de error para redondeo
        authorized = payment_data.get('authorized', False)
        allow_duplicate = payment_data.get('allow_duplicate', False)

        if is_partial and not authorized:
            # Lanzamos error específico para que el frontend pida autorización
            raise ValueError(f"PARTIAL_PAYMENT_REQUIRED|Monto ${amount} es menor a la deuda ${current_debt}. ¿Es un abono parcial o error de tipeo?")

        # VALIDACIÓN INTELIGENTE: Detectar Pagos Duplicados (Mismo cliente, mismo monto, últimos 10 min)
        if not allow_duplicate:
            ten_minutes_ago = datetime.now() - timedelta(minutes=10)
            recent_duplicate = session.query(Payment).filter(
                Payment.client_id == client.id,
                Payment.amount == amount,
                Payment.currency == currency,
                Payment.payment_date >= ten_minutes_ago
            ).first()

            if recent_duplicate:
                # Formatear hora para mostrar al usuario
                dup_time = recent_duplicate.payment_date.strftime("%I:%M %p")
                raise ValueError(f"DUPLICATE_PAYMENT|Se detectó un pago idéntico de ${amount} registrado hoy a las {dup_time}. ¿Desea registrarlo de nuevo?")

        # VALIDACIÓN: Problema 3 - Evitar pagos duplicados si no hay deuda
        unpaid_invoices = session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).count()
        
        if current_debt <= 0 and unpaid_invoices == 0:
            if not payment_data.get('is_overpayment', False):
                raise ValueError("El cliente ya está al día. No tiene saldo pendiente ni facturas por pagar.")

        # 1. Crear el pago
        payment_date = payment_data.get('payment_date')
        if isinstance(payment_date, str):
            try:
                # Handle ISO format or just date
                payment_date = datetime.fromisoformat(payment_date.replace('Z', '+00:00'))
            except:
                try:
                    payment_date = datetime.strptime(payment_date.split(' ')[0], '%Y-%m-%d')
                except:
                    payment_date = datetime.now()
        elif not payment_date:
            payment_date = datetime.now()

        from src.infrastructure.database.models import Payment, PaymentDetail
        
        new_payment = Payment(
            client_id=client.id,
            amount=amount, # Total COP
            currency=currency, # COP
            base_amount=total_base_amount, # Total USD
            exchange_rate=currency_service.get_rate(currency, base_currency),
            tax_amount=total_tax_amount,
            tax_details="; ".join(tax_details_list),
            payment_date=payment_date,
            payment_method=main_method,
            reference=payment_data.get('reference', '') if not is_mixed else 'Mixed Payment',
            notes=payment_data.get('notes', ''),
            status=status,
            registered_by=payment_data.get('registered_by', 'system')
        )
        
        # Agregar detalles
        for detail_data in prepared_details:
            detail = PaymentDetail(
                amount=detail_data['amount'],
                currency=detail_data['currency'],
                method=detail_data['method'],
                exchange_rate=detail_data['exchange_rate'],
                base_amount=detail_data['base_amount'],
                reference=detail_data['reference'],
                notes=detail_data['notes']
            )
            new_payment.details.append(detail)

        # Calcular Hash de Integridad Final antes de persistir
        from src.domain.services.audit_service import AuditService as DomainAudit
        new_payment.transaction_hash = DomainAudit.calculate_transaction_hash('payment', new_payment.to_dict())
        
        session.add(new_payment)
        
        if status == 'pending':
            # User feedback: En confirmacion, no actualiza la contabilidad aun
            logger.info(f"⏳ Pago registrado en estado 'pending' (En confirmación) para el cliente {client.id}. Saltando contabilidad.")
            from src.application.services.audit_service import AuditService as AppAuditService
            AppAuditService.log(
                operation='payment_reported',
                category='accounting',
                entity_type='payment',
                entity_id=new_payment.id,
                description=f"Pago en confirmación reportado. Monto: {amount}. Ref: {payment_data.get('reference', 'N/A')}",
                commit=False
            )
            return new_payment
            
        return self._apply_accounting(db, session, client, new_payment, amount, payment_data)

    def confirm_payment(self, payment_id):
        """
        Confirma un pago que estaba en estado 'pending'.
        Ejecuta todas las operaciones contables y de reactivación que fueron omitidas.
        """
        db = get_db()
        session = db.session
        from src.infrastructure.database.models import Payment
        
        payment = session.query(Payment).get(payment_id)
        if not payment:
            raise ValueError("Pago no encontrado")
            
        if payment.status != 'pending':
            raise ValueError(f"El pago ya está procesado (Estado: {payment.status})")
            
        client = payment.client
        
        # Generar un payment_data simulado basado en el pago para que _apply_accounting reciba el contexto
        payment_data = {
            'payment_method': payment.payment_method,
            'reference': payment.reference,
            'notes': payment.notes,
            'activate_service': None # Auto-decide based on debt
        }
        
        # Cambiamos el estado a verified/paid ANTES de aplicar la contabilidad para estar listos
        payment.status = 'verified'
        
        try:
            payment = self._apply_accounting(db, session, client, payment, payment.amount, payment_data)
            session.commit()
            return payment
        except Exception as e:
            session.rollback()
            raise e

    def _apply_accounting(self, db, session, client, new_payment, amount, payment_data):
        from src.infrastructure.database.models import Invoice, PaymentPromise
        from src.application.services.batch_service import BatchService
        
        # 2. Actualizar balance y limpiar promesa
        client.account_balance = (client.account_balance or 0) - amount
        client.last_payment_date = new_payment.payment_date
        
        # Marcar promesas como CUMPLIDAS o INCUMPLIDAS según la fecha
        now = datetime.now()
        pending_promises = session.query(PaymentPromise).filter(
            PaymentPromise.client_id == client.id,
            PaymentPromise.status == 'pending'
        ).all()
        for pp in pending_promises:
            if now <= pp.promise_date:
                pp.status = 'fulfilled'
                pp.notes = (pp.notes or "") + f" | Pagada a tiempo el {now.strftime('%Y-%m-%d')}"
                client.broken_promises_count = 0
            else:
                pp.status = 'broken'
                pp.notes = (pp.notes or "") + f" | Pagada FUERA DE PLAZO el {now.strftime('%Y-%m-%d')}"
                client.broken_promises_count = (client.broken_promises_count or 0) + 1
        
        client.promise_date = None
        
        # 3. Actualizar facturas (FIFO) e Identificar Diferencia en Cambio (FX Variance)
        invoices = session.query(Invoice).filter(
            Invoice.client_id == client.id,
            Invoice.status == 'unpaid'
        ).order_by(Invoice.issue_date).all()
        
        remaining = amount
        total_fx_variance = 0.0
        
        for inv in invoices:
            if remaining <= 0: break
            
            applied_amount = min(remaining, inv.total_amount)
            historical_rate = inv.exchange_rate or 1.0 
            current_rate = new_payment.exchange_rate or 1.0
            historical_base = applied_amount * historical_rate
            current_base = applied_amount * current_rate
            invoice_variance = current_base - historical_base
            total_fx_variance += invoice_variance
            
            if remaining >= inv.total_amount:
                inv.status = 'paid'
                remaining -= inv.total_amount
            else:
                remaining = 0
                break
                
        new_payment.fx_variance = total_fx_variance
        
        # 4. Reactivación Automática o Condicional
        should_activate = payment_data.get('activate_service')
        
        if should_activate is True:
             BatchService()._restore_client(client, commit=False)
             logger.info(f"🚀 Cliente {client.username} reactivado por solicitud explícita en pago.")
             AuditService.log(
                operation='client_reactivated',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description="Reactivación manual solicitada al registrar pago",
                previous_state={'status': client.status},
                new_state={'status': 'active'},
                commit=False
             )
        elif should_activate is False:
            logger.info(f"⚠️ Cliente {client.username} NO reactivado (activate_service=False explícito).")
        elif client.status == 'suspended' and (client.account_balance or 0) <= 0:
            BatchService()._restore_client(client, commit=False)
            logger.info(f"🚀 Cliente {client.username} reactivado automáticamente tras pago (Deuda saldada).")
            AuditService.log(
                operation='client_reactivated',
                category='client',
                entity_type='client',
                entity_id=client.id,
                description="Reactivación automática tras pago total",
                previous_state={'status': 'suspended'},
                new_state={'status': 'active'},
                commit=False
            )
            
        # Auditoría de Pago
        AuditService.log_accounting(
            operation='payment_registered',
            amount=amount,
            client_id=client.id,
            description=f"Pago registrado vía {payment_data.get('payment_method', 'cash')}. Ref: {payment_data.get('reference', 'N/A')}",
            entity_id=new_payment.id,
            entity_type='payment',
            commit=False
        )

        return new_payment

    def revert_payment(self, payment_id, reason="Reversión por incumplimiento"):
        """
        Revierte un pago realizado:
        1. Archiva el pago en la papelera.
        2. Restaura el balance del cliente.
        3. Revierte el estatus de las facturas (Reverse FIFO).
        4. Suspende al cliente en sistema y MikroTik.
        """
        from src.infrastructure.database.models import Payment, DeletedPayment
        
        db = get_db()
        session = db.session
        
        payment = session.query(Payment).get(payment_id)
        if not payment:
            raise ValueError("Pago no encontrado")
            
        client = session.query(Client).get(payment.client_id)
        if not client:
            raise ValueError("Cliente asociado al pago no encontrado")

        amount_to_revert = payment.amount
        
        try:
            # 1. Archivar en papelera
            deleted_payment = DeletedPayment(
                original_id=payment.id,
                client_id=client.id,
                amount=payment.amount,
                currency=payment.currency,
                payment_date=payment.payment_date,
                payment_method=payment.payment_method,
                reference=payment.reference,
                notes=payment.notes,
                deleted_by='admin',
                reason=reason
            )
            session.add(deleted_payment)
            
            # 2. Restaurar balance del cliente
            old_balance = client.account_balance or 0.0
            client.account_balance = old_balance + amount_to_revert
            
            # 3. Revertir facturas (Reverse FIFO: de la más reciente a la más antigua)
            # Buscamos facturas pagadas
            paid_invoices = session.query(Invoice).filter(
                Invoice.client_id == client.id,
                Invoice.status == 'paid'
            ).order_by(Invoice.issue_date.desc()).all()
            
            remaining = amount_to_revert
            for inv in paid_invoices:
                if remaining <= 0: break
                # Revertimos el estatus a unpaid
                # Nota: Una factura pudo haber sido pagada parcialmente por múltiples pagos,
                # pero aquí simplificamos revirtiendo el estatus si el monto calza o supera.
                inv.status = 'unpaid'
                remaining -= inv.total_amount
            
            # 4. Cambiar estatus a suspendido (Requerimiento explícito)
            previous_status = client.status
            client.status = 'suspended'
            
            # 5. Auditoría de Reversión
            AuditService.log(
                operation='payment_reverted',
                category='accounting',
                entity_type='payment',
                entity_id=payment.id,
                description=f"Pago de ${amount_to_revert} REVERTIDO. Cliente: {client.legal_name}. Motivo: {reason}",
                previous_state={'balance': old_balance, 'status': previous_status},
                new_state={'balance': client.account_balance, 'status': 'suspended'}
            )
            
            # 6. Eliminar el pago original
            session.delete(payment)
            session.commit()
            
            # 7. Ejecutar suspensión en MikroTik (Safe Suspend)
            router = db.get_router_repository().get_by_id(client.router_id)
            if router:
                safe_suspend_client(
                    db=db,
                    client=client,
                    router=router,
                    audit_service=AuditService,
                    audit_details=f"Suspensión por reversión de pago: {reason}"
                )
            
            return True
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Error al revertir pago {payment_id}: {e}")
            raise e
